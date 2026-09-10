# -*- coding: utf-8 -*-
"""Страница «Умный ассистент»."""

import datetime as dt
import threading
import tkinter as tk
from tkinter import ttk

from longevity.schedule import display_time, get_today_plan
from longevity.text import analyze, tokenize

from .app import WEEKDAYS, WEEKDAYS_FULL
from .calendar_page import CalendarPage
from .formatting import passage_reference, truncate_passage
from .ollama import ask_ollama
from .widgets import ModelBar

# Темы вопросов ассистента распознаются по основам слов (см. longevity.text.analyze),
# а не по подстрокам — иначе понадобилась бы своя копия нормализации, которую и
# убирает эта задача. Основы ниже — фактический вывод analyze() на соответствующих
# словах, проверено вручную:
#   analyze("план") == ["план"]
#   analyze("сегодня") == ["сегодн"]
#   analyze("расписание") == ["расписан"]
#   analyze("режим дня") == ["режим", "дня"]
#   analyze("график") == ["график"]
PLAN_STEMS = {"план", "сегодн", "расписан", "режим", "дня", "график"}

#   analyze("календарь") == ["календар"]
#   analyze("неделя") == ["недел"]
CALENDAR_STEMS = {"календар", "недел"}

#   analyze("mind") == ["mind"]
#   analyze("питание") == ["питан"]
#   analyze("еда") == ["еда"]
#   analyze("есть") == ["ест"]
NUTRITION_STEMS = {"mind", "питан", "еда", "ест"}

# «меню» по основе не распознать: analyze("меню") == ["мен"] — ровно то же, что
# у «меня» и «менее», из-за чего вопрос «у меня плохой сон» подмешивал в запрос
# к модели весь блок правил диеты MIND. Слово несклоняемое, форма у него одна,
# поэтому здесь оно сверяется целиком — по словоформе, а не по основе.
NUTRITION_WORDS = {"меню"}


class AssistantPage(ttk.Frame):
    def __init__(self, master, app):
        super().__init__(master, style="Page.TFrame")
        self.app = app
        self.theme = self.app.theme
        # Модели опрашиваются панелью в фоновом потоке (см. ui/widgets.py) —
        # на момент конструктора их список ещё не известен, поэтому
        # чекбокс включён по умолчанию: как только модель появится,
        # send_question сам её подхватит через self.model_bar.current().
        self.use_ollama_var = tk.BooleanVar(value=True)
        self._busy = False
        # Ретривер есть у реального приложения; в тестах страницы его нет —
        # тогда отрывки книг ищет локальный BM25-индекс (см. _book_hits).
        self._retriever = getattr(app, "retriever", None)
        self._local_book_search = None
        self._build()
        self._greet()

    def _build(self):
        colors = self.theme.colors
        self.chat = tk.Text(self, wrap="word", relief="groove", bd=1,
                            padx=10, pady=8, font=self.theme.font(10),
                            bg=colors["card"], fg=colors["text"], state="disabled")
        self.chat.pack(fill="both", expand=True, padx=12, pady=(12, 6))
        self.chat.tag_configure("user", foreground="#1d4ed8",
                                font=self.theme.font(10, "bold"))
        self.chat.tag_configure("bot", foreground=colors["accent"],
                                font=self.theme.font(10, "bold"))
        self.chat.tag_configure("title", foreground=colors["text"],
                                font=self.theme.font(10, "bold"))
        self.chat.tag_configure("src", foreground=colors["muted"],
                                font=self.theme.font(8))

        quick_frame = ttk.Frame(self, style="Page.TFrame")
        quick_frame.pack(fill="x", padx=12)
        tk.Label(quick_frame, text="Быстрые вопросы:", bg=colors["bg"], fg=colors["muted"]).grid(
            row=0, column=0, rowspan=2, sticky="w", padx=(0, 4))
        self.quick_buttons = []
        for n, q in enumerate(self.app.content.quick_questions):
            btn = tk.Button(quick_frame, text=q, relief="groove", bd=1,
                            bg=colors["card"], fg=colors["text"], cursor="hand2",
                            activebackground="#ccfbf1",
                            command=lambda text=q: self.send_question(text))
            btn.grid(row=n // 4, column=1 + n % 4, sticky="ew", padx=2, pady=2)
            self.quick_buttons.append(btn)
        quick_frame.columnconfigure(1, weight=1)
        quick_frame.columnconfigure(2, weight=1)
        quick_frame.columnconfigure(3, weight=1)
        quick_frame.columnconfigure(4, weight=1)

        # Панель Ollama: чекбокс страницы + общая панель выбора модели
        ollama_bar = ttk.Frame(self, style="Page.TFrame")
        ollama_bar.pack(fill="x", padx=12, pady=(4, 0))
        self.ollama_check = ttk.Checkbutton(
            ollama_bar, text="Использовать локальную нейросеть Ollama",
            variable=self.use_ollama_var)
        self.ollama_check.pack(side="left")
        self.model_bar = ModelBar(ollama_bar, self.theme, self.app.model_store)
        self.model_bar.pack(side="left", padx=(10, 0))
        # Отдельная метка «Думаю...» — про ответ на текущий вопрос, а не про
        # состояние опроса списка моделей (у того своя метка внутри ModelBar).
        self.thinking_status = tk.Label(ollama_bar, text="", bg=colors["bg"], fg=colors["muted"])
        self.thinking_status.pack(side="left", padx=8)

        input_frame = ttk.Frame(self, style="Page.TFrame")
        input_frame.pack(fill="x", padx=12, pady=(6, 12))
        self.entry = ttk.Entry(input_frame, font=self.theme.font(11))
        self.entry.pack(side="left", fill="x", expand=True, padx=(0, 6))
        self.entry.bind("<Return>", lambda e: self.send_question())
        self.ask_button = ttk.Button(input_frame, text="Спросить",
                                     command=self.send_question)
        self.ask_button.pack(side="right")

    def _greet(self):
        text = ("Здравствуйте! Я — ассистент по книгам Алексея Москалева: "
                "«120 лет жизни», «Мозг долгожителя» и «Кишечник долгожителя».\n"
                "Спросите меня про питание, сон, спорт, добавки, мозг или "
                "кишечник — отвечу по книгам или найду ответ в них.\n")
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
        self.chat.tag_configure("pending", foreground=self.theme.colors["muted"],
                                font=self.theme.font(10, slant="italic"))
        self.chat.see("end")
        self.chat.config(state="disabled")

    def _finish_pending(self, answer: str):
        self.chat.config(state="normal")
        if hasattr(self, "pending_start"):
            self.chat.delete(self.pending_start, "end")
        self.chat.config(state="disabled")
        self._append("Ассистент", answer, is_user=False)

    def _lock_input(self):
        self._busy = True
        self.entry.config(state="disabled")
        self.ask_button.config(state="disabled")
        for button in self.quick_buttons:
            button.config(state="disabled")

    def _unlock_input(self):
        self._busy = False
        self.entry.config(state="normal")
        self.ask_button.config(state="normal")
        for button in self.quick_buttons:
            button.config(state="normal")

    def send_question(self, text: str = None):
        if self._busy:
            return
        if text is None:
            text = self.entry.get().strip()
        if not text:
            return
        self.entry.delete(0, "end")
        self._append("Вы", text, is_user=True)
        if self.use_ollama_var.get() and self.model_bar.current():
            self._answer_ollama_async(text)
        else:
            answer = self._answer(text)
            self._append("Ассистент", answer, is_user=False)

    # -- Ollama --------------------------------------------------------
    def _answer_ollama_async(self, query: str):
        model = self.model_bar.current()
        self._lock_input()
        # Базовый промпт собирается синхронно (BM25, без сети): если он
        # упадёт, поток не запустится вовсе и разблокировать ввод должен
        # именно этот вызов — иначе интерфейс останется запертым.
        try:
            self.thinking_status.config(text="Думаю...")
            self._append_pending("Ассистент: Думаю (Ollama, может занять 10–60 сек)...")
            prompt = self._build_ollama_prompt(query)  # BM25, без сети
        except Exception:
            self._unlock_input()
            raise

        def work():
            # Векторный ретрив требует сети (эмбеддинг запроса) — делаем его
            # в фоне и тихо откатываемся на BM25-промпт при любом сбое.
            prompt_text = prompt
            try:
                prompt_text = self._build_ollama_prompt(query, prefer_vector=True)
            except Exception:
                pass
            try:
                result = self._ollama_answer_or_fallback(model, prompt_text, query)
            except Exception as exc:
                result = f"Не удалось получить ответ: {exc}"
            self._deliver(result)

        threading.Thread(target=work, daemon=True).start()

    def _deliver(self, result: str) -> None:
        """Передать готовый ответ в главный поток. Выполняется в фоновом.

        Окно могут закрыть, пока модель думает — и это самый вероятный момент
        закрытия: ответа ждут десятки секунд. after(), вызванный из чужого
        потока после destroy(), около секунды пытается достучаться до
        исчезнувшего цикла событий и бросает RuntimeError('main thread is not
        in main loop'), а до этого — TclError, если цикл ещё жив, но окно уже
        уничтожено. Оба гасим: интерфейса, который надо разблокировать, к
        этому моменту уже нет. Перехват узкий — любая другая ошибка обязана
        долететь до threading.excepthook, а не пропасть.
        """
        try:
            self.after(0, lambda: self._ollama_done(result))
        except (RuntimeError, tk.TclError):
            pass

    def _ollama_answer_or_fallback(self, model: str, prompt: str, query: str) -> str:
        """Выполняется в фоновом потоке — не должна бросать исключений.

        Если бросит, `work()` умрёт до вызова `self.after(...)`, и
        разблокировать интерфейс станет некому. Поэтому здесь нет
        необработанного пути: сбой самой Ollama, а следом и запасного
        локального поиска — оба перехватываются и превращаются в текст
        ответа, а не в исключение.
        """
        try:
            resp = ask_ollama(model, prompt)
            return resp if resp else "Пустой ответ модели."
        except Exception as exc:
            try:
                fallback = self._answer(query)
            except Exception as exc2:
                return (f"Внимание: не удалось обратиться к Ollama: {exc}\n\n"
                        f"Внимание: локальный поиск по базе знаний тоже не сработал: {exc2}")
            return (f"Внимание: не удалось обратиться к Ollama: {exc}\n\n"
                    "Отвечаю по базе знаний:\n" + fallback)

    def _ollama_done(self, result: str):
        # Вставка ответа в чат — та самая операция с меткой pending_start,
        # ради которой всё затевалось; если она упадёт, разблокировка всё
        # равно обязана произойти, поэтому она в finally, а не следующей
        # строкой после потенциально падающего вызова.
        try:
            self._finish_pending(result)
        finally:
            self._unlock_input()
            self.thinking_status.config(text="")

    def _is_about_nutrition(self, query: str) -> bool:
        """Спрашивают ли про питание: по основам плюс словоформа «меню»."""
        return bool(set(analyze(query)) & NUTRITION_STEMS
                    or set(tokenize(query)) & NUTRITION_WORDS)

    def _build_ollama_prompt(self, query: str, prefer_vector: bool = False) -> str:
        """Промпт для Ollama: расписание/советы + релевантные отрывки книг.

        prefer_vector=True вызывает сеть (эмбеддинг запроса), поэтому этот
        режим используется только из фонового потока; иначе — BM25.
        """
        terms = set(analyze(query))
        parts = []
        if terms & PLAN_STEMS:
            parts.append(self._day_plan(dt.date.today()))
        tips = [hit.tip for hit in self.app.index.search(query, limit=6)]
        for t in tips:
            parts.append(f"- {t.title} [{t.cat}]: {t.text} "
                         f"Когда: {t.sched}")
        if self._is_about_nutrition(query):
            good = "\n".join(f"- {g.name}: {g.amount} ({g.note})"
                             for g in self.app.content.mind_good)
            bad = "\n".join(f"- {g.name}: {g.amount}"
                            for g in self.app.content.mind_limit)
            parts.append("Правила диеты MIND (полезные группы):\n" + good +
                         "\nОграничить:\n" + bad)

        # Отрывки книг: BM25 или векторный поиск (когда кэш готов).
        content = self.app.content
        book_hits = self._book_hits(query, prefer_vector=prefer_vector, limit=4)
        for hit in book_hits:
            passage = hit.passage
            src = passage_reference(passage, content)
            parts.append(f"- Из книги {src}: "
                         f"{truncate_passage(passage.text)}")

        context = "\n".join(parts) if parts else "Контекст не найден."
        book_names = "», «".join(b.title for b in content.books) if content.books else "«120 лет жизни»"
        return (
            "Ты — «Ассистент долголетия», помощник по книгам Алексея Москалева: "
            f"«{book_names}», а также по диете MIND. Отвечай на русском языке, "
            "кратко и по делу, с опорой на приведённый контекст. Если отвечаешь "
            "по отрывку из книги, назови книгу и раздел. Если в контексте нет "
            "ответа — честно скажи, что этого нет в книгах. Не выдумывай "
            "исследования и не давай медицинских назначений; напоминай, что "
            "лекарства и добавки — только по назначению врача.\n\n"
            "КОНТЕКСТ (советы и отрывки из книг):\n" + context + "\n\n"
            "ВОПРОС ПОЛЬЗОВАТЕЛЯ: " + query
        )

    # -- логика ответов ------------------------------------------------
    def _book_hits(self, query: str, prefer_vector: bool, limit: int):
        """Отрывки книг по запросу. В тестах страницы retriever'а нет —
        тогда работает локальный BM25-индекс поверх контента."""
        if self._retriever is not None:
            return self._retriever.search(query, limit=limit,
                                          prefer_vector=prefer_vector)
        if self._local_book_search is None:
            from longevity.search import BookSearch
            self._local_book_search = BookSearch(self.app.content).search
        return self._local_book_search(query, limit)

    def _answer(self, query: str) -> str:
        terms = set(analyze(query))

        # Недельные формулировки проверяются первыми: «расписание на неделю»
        # подходит под оба набора сразу («расписан» — план, «недел» —
        # календарь), и при обратном порядке такой вопрос отдавал план на
        # один день. Более узкое требование (неделя, календарь) выигрывает.
        if terms & CALENDAR_STEMS:
            return self._week_plan()

        if terms & PLAN_STEMS:
            return self._day_plan(dt.date.today())

        tips = [hit.tip for hit in self.app.index.search(query, limit=4)]
        if not tips:
            # Советы не нашли — ищем в полных текстах книг (BM25, офлайн).
            hits = self._book_hits(query, prefer_vector=False, limit=2)
            if hits:
                return self._format_book_excerpts(hits)
            return self._fallback()
        return self._format_tips(tips)

    def _format_book_excerpts(self, hits) -> str:
        """Офлайн-ответ цитатами из книг, когда в советах ответа нет."""
        content = self.app.content
        lines = ["Вот что пишет А. А. Москалев в книгах:\n"]
        for i, hit in enumerate(hits, 1):
            passage = hit.passage
            src = passage_reference(passage, content)
            lines.append(f"{i}. Источник: {src}")
            lines.append(f"   {truncate_passage(passage.text)}\n")
        lines.append("Подробнее — вкладка «База знаний», раздел «Книги». "
                     "Лекарства и добавки — только по назначению врача.")
        return "\n".join(lines)

    def _day_plan(self, day: dt.date) -> str:
        items = get_today_plan(self.app.content, day)
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
            items = get_today_plan(self.app.content, day)
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
                f"Или откройте вкладку «База знаний» — там все {len(self.app.content.tips)} советов из книги.")
