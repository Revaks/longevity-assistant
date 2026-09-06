# -*- coding: utf-8 -*-
"""Страница «Питание» (диета MIND + меню недели + Ollama)."""

import json
import threading
import tkinter as tk
from tkinter import ttk

from longevity.content import MenuDay

from .app import BG, MUTED, TEXT_FG
from .ollama import ask_ollama, ollama_models


class NutritionPage(ttk.Frame):
    def __init__(self, master, app):
        super().__init__(master, style="Page.TFrame")
        self.app = app
        self.models = ollama_models()
        self._build()
        self._fill_menu(self.app.content.menu)

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
        for g in self.app.content.mind_good:
            rules.insert("end", f"  • {g.name} — {g.amount}", "good")
            rules.insert("end", f" ({g.note})\n")
        rules.insert("end", "\nОГРАНИЧИТЬ\n", "h")
        for g in self.app.content.mind_limit:
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
            self._fill_menu(self.app.content.menu)
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
                        self.app.content.menu, "Ollama вернула не JSON — показано базовое меню."))
            except Exception as exc:
                self.after(0, lambda: self._menu_done(
                    self.app.content.menu, f"Ошибка Ollama ({exc}) — показано базовое меню."))

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
