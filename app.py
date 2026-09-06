# -*- coding: utf-8 -*-
"""
«Ассистент долголетия» — десктоп-приложение на Tkinter.
Календарь рекомендаций + база знаний + умный ассистент по книге
А. А. Москалева «120 лет жизни — только начало. Как победить старение?»

Запуск:  python3 app.py
"""

import datetime as dt
import json
import re
import sqlite3
import sys
import threading
import tkinter as tk
import urllib.request
from pathlib import Path
from tkinter import messagebox, ttk

from longevity import paths
from longevity.content import Content, ContentError, MenuDay, load_content
from longevity.schedule import display_time, get_today_plan
from longevity.storage import Storage, StorageError

OLLAMA_URL = "http://localhost:11434"

#: Данные книги. Заполняются в main() — на уровне модуля их грузить нельзя:
#: до создания окна показать ошибку нечем, а под pythonw и в macOS-бандле
#: консоли нет вообще, и приложение просто молча не открывалось бы.
CONTENT: Content = None

_STORAGE: Storage | None = None


def get_storage() -> Storage:
    if _STORAGE is None:
        raise RuntimeError("Хранилище не открыто: main() не выполнялся")
    return _STORAGE


WEEKDAYS = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
WEEKDAYS_FULL = ["Понедельник", "Вторник", "Среда", "Четверг",
                 "Пятница", "Суббота", "Воскресенье"]

BG = "#f4f5f7"
SIDEBAR_BG = "#1f2937"
SIDEBAR_ACTIVE = "#374151"
ACCENT = "#0f766e"
TEXT_FG = "#111827"
MUTED = "#6b7280"


# ----------------------------------------------------------------------
# Вспомогательные функции для поиска
# ----------------------------------------------------------------------
STOPWORDS = {
    "что", "как", "какие", "какой", "какая", "какое", "сколько", "для", "это",
    "этот", "эта", "эти", "при", "надо", "нужно", "можно", "ли", "или", "не",
    "да", "нет", "очень", "вообще", "просто", "если", "чтобы", "почему",
    "зачем", "где", "когда", "мне", "я", "вы", "мы", "принимать", "делать",
    "сдавать", "посоветуй", "подскажи", "расскажи", "хочу", "хочется",
}


def normalize(text: str) -> str:
    text = text.lower().replace("ё", "е")
    return re.sub(r"[^a-zа-я0-9]+", " ", text).strip()


def tokenize(text: str) -> list:
    return [t for t in normalize(text).split() if t]


def expand_query(query: str) -> list:
    tokens = tokenize(query)
    expanded = []
    for t in tokens:
        if t in STOPWORDS:
            continue
        expanded.append(t)
        if t in CONTENT.synonyms:
            expanded.extend(CONTENT.synonyms[t].split())
    return expanded


def _word_match(a: str, b: str) -> bool:
    """Совпадение с учётом простейшего отсечения русских окончаний."""
    if a == b:
        return True
    if min(len(a), len(b)) >= 5:
        return b.startswith(a) or a.startswith(b)
    return False


def _count_hits(query_tokens, field: str, weight: float) -> float:
    words = field.split()
    score = 0.0
    for t in query_tokens:
        if len(t) < 2:
            continue
        for w in words:
            if _word_match(t, w):
                score += weight
    return score


def score_tip(query_tokens: list, tip) -> float:
    title = normalize(tip.title)
    tags = normalize(tip.tags)
    text = normalize(tip.text)
    cat = normalize(tip.cat)
    score = 0.0
    score += _count_hits(query_tokens, title, 3.0)
    score += _count_hits(query_tokens, tags, 2.0)
    score += _count_hits(query_tokens, text, 1.0)
    for t in query_tokens:
        if any(_word_match(t, w) for w in cat.split()):
            score += 0.5
    return score


def search_tips(query: str, limit: int = 5):
    tokens = expand_query(query)
    scored = []
    for tip in CONTENT.tips:
        s = score_tip(tokens, tip)
        if s > 0:
            scored.append((s, tip))
    scored.sort(key=lambda x: -x[0])
    return [tip for _, tip in scored[:limit]]


def fmt_day(day: dt.date) -> str:
    return f"{WEEKDAYS[day.weekday()]} {day.day:02d}.{day.month:02d}"


# ----------------------------------------------------------------------
# Работа с локальной нейросетью Ollama
# ----------------------------------------------------------------------
def ollama_models() -> list:
    """Список доступных моделей Ollama (пусто, если сервис недоступен)."""
    try:
        req = urllib.request.Request(OLLAMA_URL + "/api/tags", method="GET")
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return [m["name"] for m in data.get("models", [])]
    except Exception:
        return []


def ask_ollama(model: str, prompt: str, timeout: int = 180) -> str:
    """Однократный запрос к Ollama /api/generate (stream=false)."""
    payload = json.dumps({"model": model, "prompt": prompt,
                          "stream": False, "options": {"temperature": 0.4}})
    req = urllib.request.Request(
        OLLAMA_URL + "/api/generate", data=payload.encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data.get("response", "").strip()


# ----------------------------------------------------------------------
# Страница «Календарь»
# ----------------------------------------------------------------------
class CalendarPage(ttk.Frame):
    def __init__(self, master, app):
        super().__init__(master, style="Page.TFrame")
        self.app = app
        self.storage = get_storage()
        self.week_start = self._monday(dt.date.today())
        self.selected_day = dt.date.today()
        self._build()

    @staticmethod
    def _monday(d: dt.date) -> dt.date:
        return d - dt.timedelta(days=d.weekday())

    def _build(self):
        # Верхняя панель навигации
        nav = ttk.Frame(self, style="Page.TFrame")
        nav.pack(fill="x", padx=12, pady=(12, 6))

        self.btn_prev = ttk.Button(nav, text="◀", width=4, command=self.prev_week)
        self.btn_prev.pack(side="left")
        ttk.Button(nav, text="Сегодня", command=self.goto_today).pack(side="left", padx=6)
        self.btn_next = ttk.Button(nav, text="▶", width=4, command=self.next_week)
        self.btn_next.pack(side="left")

        self.week_label = tk.Label(nav, text="", font=("Noto Sans", 13, "bold"),
                                   bg=BG, fg=TEXT_FG)
        self.week_label.pack(side="left", padx=16)

        legend = ttk.Frame(nav, style="Page.TFrame")
        legend.pack(side="right")
        for cat, color in CONTENT.cat_colors.items():
            tk.Label(legend, text="●", fg=color, bg=BG).pack(side="left", padx=(8, 1))
            tk.Label(legend, text=cat, bg=BG, fg=MUTED).pack(side="left")

        # Сетка дней недели
        self.grid_frame = ttk.Frame(self, style="Page.TFrame")
        self.grid_frame.pack(fill="both", expand=True, padx=12)

        self.day_widgets = []  # [(header, text_widget, col_frame)]
        for i in range(7):
            col = ttk.Frame(self.grid_frame, style="Page.TFrame")
            col.grid(row=0, column=i, sticky="nsew", padx=2)
            self.grid_frame.columnconfigure(i, weight=1)
            header = tk.Label(col, text="", font=("Noto Sans", 10, "bold"),
                              pady=6, relief="groove", bd=1)
            header.pack(fill="x")
            txt = tk.Text(col, height=24, wrap="word", cursor="hand2",
                          relief="groove", bd=1, padx=6, pady=6,
                          font=("Noto Sans", 9), state="disabled",
                          bg="white", fg=TEXT_FG)
            txt.pack(fill="both", expand=True)
            header.bind("<Button-1>", lambda e, idx=i: self._on_col_click(idx))
            txt.bind("<Button-1>", lambda e, idx=i: self._on_col_click(idx))
            self.day_widgets.append((header, txt, col))
        self.grid_frame.rowconfigure(0, weight=1)

        # Нижняя панель с деталями выбранного дня
        self.detail = tk.Text(self, height=8, wrap="word", relief="groove", bd=1,
                              padx=10, pady=8, font=("Noto Sans", 10),
                              bg="#ffffff", fg=TEXT_FG, state="disabled")
        self.detail.pack(fill="x", padx=12, pady=(6, 6))

        # Панель заметок на выбранный день
        notes_bar = ttk.Frame(self, style="Page.TFrame")
        notes_bar.pack(fill="x", padx=12, pady=(0, 12))
        tk.Label(notes_bar, text="📝 Заметка на день:", bg=BG, fg=TEXT_FG).pack(side="left")
        self.note_var = tk.StringVar()
        self.note_entry = ttk.Entry(notes_bar, textvariable=self.note_var,
                                    font=("Noto Sans", 10))
        self.note_entry.pack(side="left", fill="x", expand=True, padx=6)
        ttk.Button(notes_bar, text="Сохранить",
                   command=self._save_note).pack(side="left", padx=2)
        ttk.Button(notes_bar, text="Удалить",
                   command=self._delete_note).pack(side="left", padx=2)

        self.refresh()

    # -- навигация -----------------------------------------------------
    def prev_week(self):
        self.week_start -= dt.timedelta(days=7)
        self.refresh()

    def next_week(self):
        self.week_start += dt.timedelta(days=7)
        self.refresh()

    def goto_today(self):
        self.week_start = self._monday(dt.date.today())
        self.selected_day = dt.date.today()
        self.refresh()

    def _on_col_click(self, idx):
        self.selected_day = self.week_start + dt.timedelta(days=idx)
        self.refresh()

    # -- отрисовка -----------------------------------------------------
    def refresh(self):
        today = dt.date.today()
        sunday = self.week_start + dt.timedelta(days=6)
        self.week_label.config(
            text=f"{self.week_start.day:02d}.{self.week_start.month:02d} – "
                 f"{sunday.day:02d}.{sunday.month:02d}.{sunday.year}")

        week_notes = self.storage.notes_in_range(
            self.week_start.isoformat(),
            (self.week_start + dt.timedelta(days=6)).isoformat(),
        )

        for i, (header, txt, _col) in enumerate(self.day_widgets):
            day = self.week_start + dt.timedelta(days=i)
            key = day.isoformat()
            note_mark = " 📝" if week_notes.get(key) else ""
            header.config(text=fmt_day(day) + note_mark)
            if day == today:
                header.config(bg="#0f766e", fg="white")
            elif day == self.selected_day:
                header.config(bg="#cffafe", fg="#134e4a")
            else:
                header.config(bg="#e5e7eb", fg=TEXT_FG)

            txt.config(state="normal")
            txt.delete("1.0", "end")
            items = get_today_plan(CONTENT, day)
            for it in items:
                color = CONTENT.cat_colors.get(it.cat, "#333333")
                tag = f"cat{i}_{it.cat.replace(' ', '')}"
                txt.tag_configure(tag, foreground=color,
                                  font=("Noto Sans", 9, "bold"))
                txt.insert("end", f"{display_time(it)}  ", "time")
                txt.insert("end", it.title + "\n", tag)
            note = week_notes.get(key)
            if note:
                txt.insert("end", "\n📝 " + note + "\n", "note")
                txt.tag_configure("note", foreground="#92400e",
                                  font=("Noto Sans", 9, "italic"))
            txt.tag_configure("time", foreground=MUTED, font=("Noto Sans", 9))
            txt.config(state="disabled")

        self._show_day_detail()
        self._load_note_to_entry()

    # -- заметки -------------------------------------------------------
    def _load_note_to_entry(self):
        key = self.selected_day.isoformat()
        self.note_var.set(self.storage.get_note(key))

    def _save_note(self):
        key = self.selected_day.isoformat()
        try:
            self.storage.set_note(key, self.note_var.get())
        except Exception as exc:
            messagebox.showerror("Не удалось сохранить заметку", str(exc))
            return
        self.refresh()

    def _delete_note(self):
        key = self.selected_day.isoformat()
        try:
            self.storage.set_note(key, "")
        except Exception as exc:
            messagebox.showerror("Не удалось удалить заметку", str(exc))
            return
        self.note_var.set("")
        self.refresh()

    def _show_day_detail(self):
        self.detail.config(state="normal")
        self.detail.delete("1.0", "end")
        day = self.selected_day
        items = get_today_plan(CONTENT, day)
        self.detail.insert("end", f"{WEEKDAYS_FULL[day.weekday()]}, "
                                  f"{day.day:02d}.{day.month:02d}.{day.year}\n", "h")
        self.detail.tag_configure("h", font=("Noto Sans", 11, "bold"))
        for it in items:
            color = CONTENT.cat_colors.get(it.cat, "#333333")
            tag = "d_" + it.cat.replace(" ", "")
            self.detail.tag_configure(tag, foreground=color,
                                      font=("Noto Sans", 10, "bold"))
            self.detail.insert("end", f"\n{display_time(it)} — {it.title} ", tag)
            self.detail.insert("end", f"({it.cat})\n", "cat")
            if it.detail:
                self.detail.insert("end", it.detail + "\n", "det")
        self.detail.tag_configure("cat", foreground=MUTED)
        self.detail.tag_configure("det", foreground="#374151")
        self.detail.config(state="disabled")


# ----------------------------------------------------------------------
# Страница «База знаний»
# ----------------------------------------------------------------------
class KnowledgePage(ttk.Frame):
    def __init__(self, master, app):
        super().__init__(master, style="Page.TFrame")
        self.app = app
        self._filtered = list(CONTENT.tips)
        self._build()
        self.refresh_list()

    def _build(self):
        top = ttk.Frame(self, style="Page.TFrame")
        top.pack(fill="x", padx=12, pady=(12, 6))

        tk.Label(top, text="Поиск:", bg=BG, fg=TEXT_FG).pack(side="left")
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *a: self.refresh_list())
        ent = ttk.Entry(top, textvariable=self.search_var, width=36)
        ent.pack(side="left", padx=6)

        tk.Label(top, text="Категория:", bg=BG, fg=TEXT_FG).pack(side="left", padx=(10, 0))
        self.cat_var = tk.StringVar(value="Все категории")
        combo = ttk.Combobox(top, textvariable=self.cat_var, state="readonly",
                             values=["Все категории"] + list(CONTENT.categories), width=16)
        combo.pack(side="left", padx=6)
        combo.bind("<<ComboboxSelected>>", lambda e: self.refresh_list())

        ttk.Button(top, text="Сбросить",
                   command=self.reset_filter).pack(side="left", padx=6)
        self.count_label = tk.Label(top, text="", bg=BG, fg=MUTED)
        self.count_label.pack(side="right")

        # Таблица советов
        table_frame = ttk.Frame(self, style="Page.TFrame")
        table_frame.pack(fill="both", expand=True, padx=12)
        self.tree = ttk.Treeview(table_frame, columns=("cat", "title", "sched"),
                                 show="headings", selectmode="browse")
        self.tree.heading("cat", text="Категория")
        self.tree.heading("title", text="Совет")
        self.tree.heading("sched", text="Когда / как часто")
        self.tree.column("cat", width=120, anchor="w")
        self.tree.column("title", width=420, anchor="w")
        self.tree.column("sched", width=260, anchor="w")
        vsb = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        self.tree.bind("<<TreeviewSelect>>", self.on_select)

        # Детали выбранного совета
        self.detail = tk.Text(self, height=12, wrap="word", relief="groove", bd=1,
                              padx=10, pady=8, font=("Noto Sans", 10),
                              bg="white", fg=TEXT_FG, state="disabled")
        self.detail.pack(fill="x", padx=12, pady=(6, 12))

    def reset_filter(self):
        self.search_var.set("")
        self.cat_var.set("Все категории")
        self.refresh_list()

    def refresh_list(self):
        q = normalize(self.search_var.get())
        cat = self.cat_var.get()
        self._filtered = []
        for tip in CONTENT.tips:
            if cat != "Все категории" and tip.cat != cat:
                continue
            if q:
                hay = normalize(tip.title + " " + tip.text + " " +
                                tip.tags + " " + tip.cat)
                if not any(t in hay for t in q.split()):
                    continue
            self._filtered.append(tip)
        self.tree.delete(*self.tree.get_children())
        for tip in self._filtered:
            self.tree.insert("", "end", iid=tip.id,
                             values=(tip.cat, tip.title, tip.sched))
        self.count_label.config(text=f"Найдено: {len(self._filtered)}")

    def on_select(self, _event=None):
        sel = self.tree.selection()
        if not sel:
            return
        tip = CONTENT.tip(sel[0])
        self.detail.config(state="normal")
        self.detail.delete("1.0", "end")
        color = CONTENT.cat_colors.get(tip.cat, "#333333")
        self.detail.tag_configure("cat", foreground=color,
                                  font=("Noto Sans", 10, "bold"))
        self.detail.tag_configure("h", font=("Noto Sans", 12, "bold"))
        self.detail.tag_configure("lab", foreground=MUTED,
                                  font=("Noto Sans", 9, "bold"))
        self.detail.insert("end", tip.title + "\n\n", "h")
        self.detail.insert("end", f"[{tip.cat}]  ", "cat")
        self.detail.insert("end", tip.text + "\n\n")
        self.detail.insert("end", "Когда / как часто: ", "lab")
        self.detail.insert("end", tip.sched + "\n")
        self.detail.insert("end", "Источник: ", "lab")
        self.detail.insert("end", tip.source + "\n")
        self.detail.config(state="disabled")


# ----------------------------------------------------------------------
# Страница «Питание» (диета MIND + меню недели + Ollama)
# ----------------------------------------------------------------------
class NutritionPage(ttk.Frame):
    def __init__(self, master, app):
        super().__init__(master, style="Page.TFrame")
        self.app = app
        self.models = ollama_models()
        self._build()
        self._fill_menu(CONTENT.menu)

    def _build(self):
        # Верхняя панель: модель Ollama + генерация меню
        top = ttk.Frame(self, style="Page.TFrame")
        top.pack(fill="x", padx=12, pady=(12, 6))
        tk.Label(top, text="🥗 Диета MIND + принципы питания Москалева",
                 bg=BG, fg=TEXT_FG, font=("Noto Sans", 12, "bold")).pack(side="left")
        tk.Label(top, text="Модель:", bg=BG, fg=MUTED).pack(side="left", padx=(18, 4))
        self.model_var = tk.StringVar(value=self.models[0] if self.models else "")
        if self.models:
            combo = ttk.Combobox(top, textvariable=self.model_var, state="readonly",
                                 values=self.models, width=16)
        else:
            combo = ttk.Combobox(top, textvariable=self.model_var, state="disabled",
                                 values=["Ollama недоступна"], width=16)
        combo.pack(side="left")
        self.gen_btn = ttk.Button(top, text="Сгенерировать меню (Ollama)",
                                  command=self.generate_menu_ollama)
        self.gen_btn.pack(side="left", padx=6)
        self.status_var = tk.StringVar(value="")
        tk.Label(top, textvariable=self.status_var, bg=BG, fg=MUTED).pack(side="left", padx=6)

        # Таблица недельного меню
        table_frame = ttk.Frame(self, style="Page.TFrame")
        table_frame.pack(fill="both", expand=True, padx=12)
        self.tree = ttk.Treeview(table_frame, columns=("day", "breakfast", "lunch",
                                                       "dinner", "snack"),
                                 show="headings", selectmode="browse")
        for col, title, width in (("day", "День", 110),
                                  ("breakfast", "Завтрак", 260),
                                  ("lunch", "Обед", 300),
                                  ("dinner", "Ужин", 300),
                                  ("snack", "Перекус", 240)):
            self.tree.heading(col, text=title)
            self.tree.column(col, width=width, anchor="w")
        vsb = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        self.tree.tag_configure("odd", background="#f0fdf4")

        # Правила MIND
        rules = tk.Text(self, height=10, wrap="word", relief="groove", bd=1,
                        padx=10, pady=8, font=("Noto Sans", 9),
                        bg="white", fg=TEXT_FG, state="disabled")
        rules.pack(fill="x", padx=12, pady=(6, 12))
        rules.tag_configure("h", foreground="#0f766e", font=("Noto Sans", 10, "bold"))
        rules.tag_configure("good", foreground="#2e7d32")
        rules.tag_configure("bad", foreground="#b91c1c")
        rules.config(state="normal")
        rules.insert("end", "ПОЛЕЗНЫЕ ГРУППЫ (диета MIND)\n", "h")
        for g in CONTENT.mind_good:
            rules.insert("end", f"  • {g.name} — {g.amount}", "good")
            rules.insert("end", f" ({g.note})\n")
        rules.insert("end", "\nОГРАНИЧИТЬ\n", "h")
        for g in CONTENT.mind_limit:
            rules.insert("end", f"  • {g.name} — {g.amount}", "bad")
            rules.insert("end", f" ({g.note})\n")
        rules.config(state="disabled")

    def _fill_menu(self, menu):
        self.tree.delete(*self.tree.get_children())
        for i, row in enumerate(menu):
            self.tree.insert("", "end", values=(row.day, row.breakfast,
                                                row.lunch, row.dinner,
                                                row.snack),
                             tags=("odd",) if i % 2 else ())

    def generate_menu_ollama(self):
        model = self.model_var.get()
        if not model or not self.models:
            self.status_var.set("Ollama недоступна — показано базовое меню MIND.")
            self._fill_menu(CONTENT.menu)
            return
        self.status_var.set(f"⏳ Генерирую меню ({model})...")
        self.gen_btn.config(state="disabled")
        prompt = (
            "Ты — диетолог. Составь недельное меню (7 дней) по диете MIND, "
            "совмещённое с принципами питания Алексея Москалева: ограничение калорий "
            "без недоедания, низкий гликемический индекс, жирная рыба 2–3 раза в неделю, "
            "оливковое масло, зелёные листовые овощи 6+ раз в неделю, ягоды 2+ раза, "
            "орехи 5+ раз, цельные злаки ежедневно, бобовые 3+ раза, птица вместо "
            "красного мяса, минимум соли, сахара, трансжиров и жареного, готовка до 120°C, "
            "ужин за 3–4 часа до сна. Учти, что меню должно быть русским и доступным по "
            "продуктам. Ответь строго в формате JSON-массива из 7 объектов с ключами: "
            "day, breakfast, lunch, dinner, snack. Без лишнего текста."
        )

        def work():
            try:
                resp = ask_ollama(model, prompt, timeout=240)
                menu = self._parse_menu(resp)
                if menu:
                    self.after(0, lambda: self._menu_done(menu, "Меню сгенерировано Ollama."))
                else:
                    self.after(0, lambda: self._menu_done(
                        CONTENT.menu, "Ollama вернула не JSON — показано базовое меню."))
            except Exception as exc:
                self.after(0, lambda: self._menu_done(
                    CONTENT.menu, f"Ошибка Ollama ({exc}) — показано базовое меню."))

        threading.Thread(target=work, daemon=True).start()

    @staticmethod
    def _parse_menu(text: str):
        text = text.strip()
        start = text.find("[")
        end = text.rfind("]")
        if start == -1 or end == -1 or end <= start:
            return None
        try:
            data = json.loads(text[start:end + 1])
            menu = []
            for row in data:
                if all(k in row for k in ("day", "breakfast", "lunch",
                                          "dinner", "snack")):
                    menu.append(MenuDay(**{k: str(row[k]).strip() for k in
                                           ("day", "breakfast", "lunch", "dinner", "snack")}))
            return menu if len(menu) == 7 else None
        except Exception:
            return None

    def _menu_done(self, menu, status):
        self._fill_menu(menu)
        self.status_var.set(status)
        self.gen_btn.config(state="normal")


# ----------------------------------------------------------------------
# Страница «Умный ассистент»
# ----------------------------------------------------------------------
class AssistantPage(ttk.Frame):
    def __init__(self, master, app):
        super().__init__(master, style="Page.TFrame")
        self.app = app
        self.models = ollama_models()
        self.use_ollama_var = tk.BooleanVar(value=bool(self.models))
        self._build()
        self._greet()

    def _build(self):
        self.chat = tk.Text(self, wrap="word", relief="groove", bd=1,
                            padx=10, pady=8, font=("Noto Sans", 10),
                            bg="white", fg=TEXT_FG, state="disabled")
        self.chat.pack(fill="both", expand=True, padx=12, pady=(12, 6))
        self.chat.tag_configure("user", foreground="#1d4ed8",
                                font=("Noto Sans", 10, "bold"))
        self.chat.tag_configure("bot", foreground="#0f766e",
                                font=("Noto Sans", 10, "bold"))
        self.chat.tag_configure("title", foreground="#111827",
                                font=("Noto Sans", 10, "bold"))
        self.chat.tag_configure("src", foreground=MUTED,
                                font=("Noto Sans", 8))

        quick_frame = ttk.Frame(self, style="Page.TFrame")
        quick_frame.pack(fill="x", padx=12)
        tk.Label(quick_frame, text="Быстрые вопросы:", bg=BG, fg=MUTED).grid(
            row=0, column=0, rowspan=2, sticky="w", padx=(0, 4))
        for n, q in enumerate(CONTENT.quick_questions):
            btn = tk.Button(quick_frame, text=q, relief="groove", bd=1,
                            bg="white", fg=TEXT_FG, cursor="hand2",
                            activebackground="#ccfbf1",
                            command=lambda text=q: self.send_question(text))
            btn.grid(row=n // 4, column=1 + n % 4, sticky="ew", padx=2, pady=2)
        quick_frame.columnconfigure(1, weight=1)
        quick_frame.columnconfigure(2, weight=1)
        quick_frame.columnconfigure(3, weight=1)
        quick_frame.columnconfigure(4, weight=1)

        # Панель Ollama
        ollama_bar = ttk.Frame(self, style="Page.TFrame")
        ollama_bar.pack(fill="x", padx=12, pady=(4, 0))
        self.ollama_check = ttk.Checkbutton(
            ollama_bar, text="Использовать локальную нейросеть Ollama",
            variable=self.use_ollama_var)
        self.ollama_check.pack(side="left")
        tk.Label(ollama_bar, text="Модель:", bg=BG, fg=MUTED).pack(side="left", padx=(10, 4))
        self.model_var = tk.StringVar(value=self.models[0] if self.models else "")
        if self.models:
            mcombo = ttk.Combobox(ollama_bar, textvariable=self.model_var,
                                  state="readonly", values=self.models, width=16)
        else:
            mcombo = ttk.Combobox(ollama_bar, textvariable=self.model_var,
                                  state="disabled", values=["Ollama недоступна"], width=16)
        mcombo.pack(side="left")
        self.ollama_status = tk.Label(ollama_bar, text="", bg=BG, fg=MUTED)
        self.ollama_status.pack(side="left", padx=8)

        input_frame = ttk.Frame(self, style="Page.TFrame")
        input_frame.pack(fill="x", padx=12, pady=(6, 12))
        self.entry = ttk.Entry(input_frame, font=("Noto Sans", 11))
        self.entry.pack(side="left", fill="x", expand=True, padx=(0, 6))
        self.entry.bind("<Return>", lambda e: self.send_question())
        ttk.Button(input_frame, text="Спросить",
                   command=self.send_question).pack(side="right")

    def _greet(self):
        text = ("Здравствуйте! Я — ассистент по книге Алексея Москалева "
                "«120 лет жизни — только начало».\n"
                "Спросите меня про питание, сон, спорт, добавки, анализы или "
                "попросите план на день.\n")
        self._append("Ассистент", text, is_user=False)

    def _append(self, who: str, text: str, is_user: bool):
        self.chat.config(state="normal")
        tag = "user" if is_user else "bot"
        self.chat.insert("end", f"{who}: ", tag)
        self.chat.insert("end", text + "\n\n")
        self.chat.see("end")
        self.chat.config(state="disabled")

    def _append_pending(self, text: str):
        self.chat.config(state="normal")
        self.pending_start = self.chat.index("end-1c")
        self.chat.insert("end", text + "\n\n", "pending")
        self.chat.tag_configure("pending", foreground=MUTED,
                                font=("Noto Sans", 10, "italic"))
        self.chat.see("end")
        self.chat.config(state="disabled")

    def _finish_pending(self, answer: str):
        self.chat.config(state="normal")
        if hasattr(self, "pending_start"):
            self.chat.delete(self.pending_start, "end")
        self.chat.config(state="disabled")
        self._append("Ассистент", answer, is_user=False)

    def send_question(self, text: str = None):
        if text is None:
            text = self.entry.get().strip()
        if not text:
            return
        self.entry.delete(0, "end")
        self._append("Вы", text, is_user=True)
        if self.use_ollama_var.get() and self.model_var.get() in self.models:
            self._answer_ollama_async(text)
        else:
            answer = self._answer(text)
            self._append("Ассистент", answer, is_user=False)

    # -- Ollama --------------------------------------------------------
    def _answer_ollama_async(self, query: str):
        model = self.model_var.get()
        self.entry.config(state="disabled")
        self.ollama_status.config(text="⏳ Думаю...")
        self._append_pending("Ассистент: ⏳ Думаю (Ollama, может занять 10–60 сек)...")
        prompt = self._build_ollama_prompt(query)

        def work():
            try:
                resp = ask_ollama(model, prompt)
                result = resp if resp else "Пустой ответ модели."
            except Exception as exc:
                result = (f"⚠️ Не удалось обратиться к Ollama: {exc}\n\n"
                          "Отвечаю по базе знаний:\n" + self._answer(query))
            self.after(0, lambda: self._ollama_done(result))

        threading.Thread(target=work, daemon=True).start()

    def _ollama_done(self, result: str):
        self._finish_pending(result)
        self.entry.config(state="normal")
        self.ollama_status.config(text="")

    def _build_ollama_prompt(self, query: str) -> str:
        q = normalize(query)
        parts = []
        if any(w in q for w in ("план", "сегодня", "расписан", "режим дня")):
            parts.append(self._day_plan(dt.date.today()))
        tips = search_tips(query, limit=6)
        for t in tips:
            parts.append(f"- {t.title} [{t.cat}]: {t.text} "
                         f"Когда: {t.sched}")
        if "mind" in q or "питани" in q or "меню" in q or "еда" in q or "есть" in q:
            good = "\n".join(f"- {g.name}: {g.amount} ({g.note})"
                             for g in CONTENT.mind_good)
            bad = "\n".join(f"- {g.name}: {g.amount}"
                            for g in CONTENT.mind_limit)
            parts.append("Правила диеты MIND (полезные группы):\n" + good +
                         "\nОграничить:\n" + bad)
        context = "\n".join(parts) if parts else "Контекст не найден."
        return (
            "Ты — «Ассистент долголетия», помощник по книге Алексея Москалева "
            "«120 лет жизни — только начало» и диете MIND. Отвечай на русском языке, "
            "кратко и по делу, с опорой на приведённый контекст. Если в контексте нет "
            "ответа — честно скажи, что этого нет в книге. Не выдумывай исследования "
            "и не давай медицинских назначений; напоминай, что лекарства и добавки — "
            "только по назначению врача.\n\n"
            "КОНТЕКСТ (советы из книги):\n" + context + "\n\n"
            "ВОПРОС ПОЛЬЗОВАТЕЛЯ: " + query
        )

    # -- логика ответов ------------------------------------------------
    def _answer(self, query: str) -> str:
        q = normalize(query)

        # План на день / календарь
        if any(w in q for w in ("план", "сегодня", "расписан", "режим дня", "график")):
            return self._day_plan(dt.date.today())

        if "календар" in q or "недел" in q:
            return self._week_plan()

        tips = search_tips(query, limit=4)
        if not tips:
            return self._fallback()
        return self._format_tips(tips)

    def _day_plan(self, day: dt.date) -> str:
        items = get_today_plan(CONTENT, day)
        lines = [f"План на {WEEKDAYS_FULL[day.weekday()].lower()}, "
                 f"{day.day:02d}.{day.month:02d} (по книге Москалева):\n"]
        for it in items:
            lines.append(f"• {display_time(it)} — {it.title}")
            if it.detail:
                lines.append(f"   {it.detail}")
        lines.append("\nПолный календарь — на вкладке «Календарь».")
        return "\n".join(lines)

    def _week_plan(self) -> str:
        monday = CalendarPage._monday(dt.date.today())
        lines = ["Расписание на текущую неделю:\n"]
        for i in range(7):
            day = monday + dt.timedelta(days=i)
            items = get_today_plan(CONTENT, day)
            lines.append(f"{WEEKDAYS[i]} {day.day:02d}.{day.month:02d}: " +
                         ", ".join(it.title for it in items) + ".")
        return "\n".join(lines)

    def _format_tips(self, tips) -> str:
        lines = ["Вот что советует А. А. Москалев:\n"]
        for i, tip in enumerate(tips, 1):
            lines.append(f"{i}. {tip.title}")
            lines.append(f"   {tip.text}")
            lines.append(f"   Когда: {tip.sched}")
            lines.append(f"   Источник: {tip.source}\n")
        lines.append("Подробнее — во вкладке «База знаний». "
                     "Лекарства и добавки — только по назначению врача.")
        return "\n".join(lines)

    def _fallback(self) -> str:
        return ("Не нашёл точного совета в книге. Попробуйте спросить иначе, например:\n"
                "• «Как спать?»\n"
                "• «Что есть, чтобы жить дольше?»\n"
                "• «Какие добавки полезны?»\n"
                "• «Какие анализы сдавать?»\n"
                "• «План на сегодня»\n"
                f"Или откройте вкладку «База знаний» — там все {len(CONTENT.tips)} советов из книги.")


# ----------------------------------------------------------------------
# Главное окно
# ----------------------------------------------------------------------
class LongevityApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(CONTENT.app_title)
        self.geometry("1280x820")
        self.minsize(1080, 700)
        self.configure(bg=BG)

        self._configure_styles()
        self._build_sidebar()
        self._build_header()
        self._build_pages()
        self._build_statusbar()
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def on_close(self):
        """Закрыть соединение с базой — иначе оно висит до конца процесса."""
        try:
            get_storage().close()
        except Exception:
            pass
        self.destroy()

    def _configure_styles(self):
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("Page.TFrame", background=BG)
        style.configure("TButton", font=("Noto Sans", 10))
        style.configure("TEntry", font=("Noto Sans", 10))
        style.configure("Treeview", font=("Noto Sans", 10), rowheight=26)
        style.configure("Treeview.Heading", font=("Noto Sans", 10, "bold"))

    def _build_sidebar(self):
        sidebar = tk.Frame(self, bg=SIDEBAR_BG, width=190)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)

        tk.Label(sidebar, text="🕰", bg=SIDEBAR_BG, fg="white",
                 font=("Noto Sans", 26)).pack(pady=(18, 0))
        tk.Label(sidebar, text=CONTENT.app_title, bg=SIDEBAR_BG, fg="white",
                 font=("Noto Sans", 11, "bold"), wraplength=170,
                 justify="center").pack(pady=(4, 2))
        tk.Label(sidebar, text="А. А. Москалев\n«120 лет жизни»", bg=SIDEBAR_BG,
                 fg="#9ca3af", font=("Noto Sans", 8), justify="center").pack(pady=(0, 14))

        self.nav_buttons = {}
        for key, label in (("calendar", "📅 Календарь"),
                           ("nutrition", "🥗 Питание"),
                           ("knowledge", "📚 База знаний"),
                           ("assistant", "🤖 Ассистент")):
            btn = tk.Button(sidebar, text=label, anchor="w", relief="flat",
                            bg=SIDEBAR_BG, fg="white", font=("Noto Sans", 11),
                            activebackground=SIDEBAR_ACTIVE, activeforeground="white",
                            bd=0, padx=16, pady=12, cursor="hand2",
                            command=lambda k=key: self.show_page(k))
            btn.pack(fill="x")
            self.nav_buttons[key] = btn

        tk.Label(sidebar, text="", bg=SIDEBAR_BG).pack(expand=True)

    def _build_header(self):
        header = tk.Frame(self, bg=BG)
        header.pack(fill="x", padx=16, pady=(12, 0))
        self.page_title = tk.Label(header, text="", bg=BG, fg=TEXT_FG,
                                   font=("Noto Sans", 15, "bold"))
        self.page_title.pack(side="left")
        tk.Label(header, text=CONTENT.app_subtitle, bg=BG, fg=MUTED,
                 font=("Noto Sans", 9)).pack(side="left", padx=12)

    def _build_pages(self):
        container = ttk.Frame(self, style="Page.TFrame")
        container.pack(fill="both", expand=True)
        container.rowconfigure(0, weight=1)
        container.columnconfigure(0, weight=1)

        self.pages = {}
        for key, cls in (("calendar", CalendarPage),
                         ("nutrition", NutritionPage),
                         ("knowledge", KnowledgePage),
                         ("assistant", AssistantPage)):
            page = cls(container, self)
            page.grid(row=0, column=0, sticky="nsew")
            self.pages[key] = page

        self.show_page("calendar")

    def _build_statusbar(self):
        bar = tk.Label(self, text=CONTENT.disclaimer, bg="#e5e7eb", fg=MUTED,
                       anchor="w", padx=10, pady=4, font=("Noto Sans", 8))
        bar.pack(side="bottom", fill="x")

    def show_page(self, key: str):
        titles = {"calendar": "Календарь рекомендаций",
                  "nutrition": "Питание (диета MIND + меню недели)",
                  "knowledge": "База знаний (советы из книги)",
                  "assistant": "Умный ассистент"}
        self.page_title.config(text=titles[key])
        for k, page in self.pages.items():
            if k == key:
                page.tkraise()
        for k, btn in self.nav_buttons.items():
            if k == key:
                btn.config(bg=SIDEBAR_ACTIVE)
            else:
                btn.config(bg=SIDEBAR_BG)


def _show_start_error(title: str, reason: str) -> None:
    """Сообщить об ошибке старта окном, а не трассировкой в несуществующую консоль."""
    text = f"{title}\n\nПричина: {reason}"
    print(text, file=sys.stderr)
    try:
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("Ассистент долголетия", text)
        root.destroy()
    except tk.TclError:
        # Tk не поднялся — остаётся только stderr, он уже написан выше.
        pass


def main() -> int:
    """Точка входа: сначала данные и база, потом окно."""
    global CONTENT, _STORAGE

    try:
        CONTENT = load_content()
    except ContentError as exc:
        _show_start_error(
            "Не удалось загрузить данные приложения — они противоречивы "
            "или повреждены. Переустановите «Ассистент долголетия».", str(exc))
        return 1

    try:
        _STORAGE = Storage(paths.db_path())
        _STORAGE.migrate_notes_json([Path(__file__).resolve().parent / "notes.json"])
    except StorageError as exc:
        _show_start_error("Не удалось открыть базу данных.", str(exc))
        return 1
    except (OSError, sqlite3.Error) as exc:
        # Путь к базе не подставляем отдельно: paths.db_path() тут же снова
        # упал бы (например, каталог данных нельзя создать) и обработчик
        # уронил бы приложение повторно, только уже без диалога. Для ошибок
        # файловой системы str(exc) и так содержит путь.
        _show_start_error("Не удалось открыть базу данных.", str(exc))
        return 1

    try:
        app = LongevityApp()
    except tk.TclError as exc:
        _show_start_error(
            "Не удалось создать окно. Проверьте, что установлен Tk "
            "(подробности — в README).", str(exc))
        _STORAGE.close()
        return 1

    if _STORAGE.migration_warnings:
        warnings = "\n\n".join(_STORAGE.migration_warnings)
        app.after(200, lambda: messagebox.showwarning("Перенос старых заметок", warnings))

    try:
        app.mainloop()
    finally:
        _STORAGE.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
