# -*- coding: utf-8 -*-
"""Главное окно «Ассистента долголетия»."""

import datetime as dt
import tkinter as tk
from tkinter import ttk

from longevity.content import Content
from longevity.search import SearchIndex
from longevity.storage import Storage

from .theme import Theme

WEEKDAYS = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
WEEKDAYS_FULL = ["Понедельник", "Вторник", "Среда", "Четверг",
                 "Пятница", "Суббота", "Воскресенье"]

PREFERRED_SIZE = (1280, 820)
MIN_SIZE = (900, 600)


def fit_geometry(screen_w: int, screen_h: int) -> tuple[int, int]:
    """Стартовый размер: желаемый, но не больше экрана и не меньше минимума."""
    width = max(MIN_SIZE[0], min(PREFERRED_SIZE[0], int(screen_w * 0.95)))
    height = max(MIN_SIZE[1], min(PREFERRED_SIZE[1], int(screen_h * 0.95)))
    return width, height


def fmt_day(day: dt.date) -> str:
    return f"{WEEKDAYS[day.weekday()]} {day.day:02d}.{day.month:02d}"


# ----------------------------------------------------------------------
# Главное окно
# ----------------------------------------------------------------------
class LongevityApp(tk.Tk):
    def __init__(self, content: Content, index: SearchIndex, storage: Storage):
        super().__init__()
        self.content = content
        self.index = index
        self.storage = storage
        self.theme = Theme(self)

        self.title(self.content.app_title)
        self.minsize(*MIN_SIZE)

        # Восстанавливаем сохранённый размер или используем подходящий для экрана
        saved_size = self.storage.get_value("app.window_size")
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()

        if isinstance(saved_size, (list, tuple)) and len(saved_size) == 2:
            try:
                w, h = int(saved_size[0]), int(saved_size[1])
                # Проверяем сохранённый размер на вместимость
                w = max(MIN_SIZE[0], min(w, int(screen_w * 0.95)))
                h = max(MIN_SIZE[1], min(h, int(screen_h * 0.95)))
                self.geometry(f"{w}x{h}")
            except (ValueError, TypeError):
                # Испорченный размер, используем подходящий для экрана
                w, h = fit_geometry(screen_w, screen_h)
                self.geometry(f"{w}x{h}")
        else:
            # Размер не сохранён, используем подходящий для экрана
            w, h = fit_geometry(screen_w, screen_h)
            self.geometry(f"{w}x{h}")

        self.configure(bg=self.theme.colors["bg"])

        self._configure_styles()
        self._build_sidebar()
        self._build_header()
        self._build_pages()
        self._build_statusbar()
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def on_close(self):
        """Закрыть соединение с базой и сохранить состояние окна."""
        # Сохраняем размер окна и активную вкладку
        try:
            w = self.winfo_width()
            h = self.winfo_height()
            # Сохраняем только правдоподобные размеры (не 1x1 для скрытого/неотрисованного окна)
            if w >= MIN_SIZE[0] and h >= MIN_SIZE[1]:
                self.storage.set_value("app.window_size", [w, h])
        except Exception:
            pass

        try:
            if hasattr(self, "current_page"):
                self.storage.set_value("app.active_page", self.current_page)
        except Exception:
            pass

        try:
            self.storage.close()
        except Exception:
            pass
        self.destroy()

    def _configure_styles(self):
        colors = self.theme.colors
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("Page.TFrame", background=colors["bg"])
        style.configure("TButton", font=self.theme.font(10))
        style.configure("TEntry", font=self.theme.font(10))
        style.configure("Treeview", font=self.theme.font(10), rowheight=26)
        style.configure("Treeview.Heading", font=self.theme.font(10, "bold"))

    def _build_sidebar(self):
        colors = self.theme.colors
        sidebar = tk.Frame(self, bg=colors["sidebar"], width=190)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)

        tk.Label(sidebar, image=self.theme.icon("clock", 32),
                 bg=colors["sidebar"]).pack(pady=(18, 2))
        tk.Label(sidebar, text=self.content.app_title, bg=colors["sidebar"],
                 fg=colors["card"], font=self.theme.font(11, "bold"), wraplength=170,
                 justify="center").pack(pady=(0, 2))
        tk.Label(sidebar, text="А. А. Москалев\n«120 лет жизни»", bg=colors["sidebar"],
                 fg="#9ca3af", font=self.theme.font(8), justify="center").pack(pady=(0, 14))

        self.nav_buttons = {}
        for key, label in (("calendar", "Календарь"),
                           ("nutrition", "Питание"),
                           ("knowledge", "База знаний"),
                           ("assistant", "Ассистент")):
            btn = tk.Button(sidebar, text=label, image=self.theme.icon(key, 16),
                            compound="left", anchor="w", relief="flat",
                            bg=colors["sidebar"], fg=colors["card"], font=self.theme.font(11),
                            activebackground=colors["sidebar_active"],
                            activeforeground=colors["card"],
                            bd=0, padx=16, pady=12, cursor="hand2",
                            command=lambda k=key: self.show_page(k))
            btn.pack(fill="x")
            self.nav_buttons[key] = btn

        tk.Label(sidebar, text="", bg=colors["sidebar"]).pack(expand=True)

    def _build_header(self):
        colors = self.theme.colors
        header = tk.Frame(self, bg=colors["bg"])
        header.pack(fill="x", padx=16, pady=(12, 0))
        self.page_title = tk.Label(header, text="", bg=colors["bg"], fg=colors["text"],
                                   font=self.theme.font(15, "bold"))
        self.page_title.pack(side="left")
        tk.Label(header, text=self.content.app_subtitle, bg=colors["bg"], fg=colors["muted"],
                 font=self.theme.font(9)).pack(side="left", padx=12)

    def _build_pages(self):
        # Импорт страниц отложен до вызова: ui/app.py и ui/*_page.py взаимно
        # используют друг друга (страницам нужна палитра и fmt_day отсюда,
        # этому методу — классы страниц), а к моменту вызова _build_pages
        # модуль ui.app уже полностью загружен и предоставляет своё содержимое.
        from .assistant_page import AssistantPage
        from .calendar_page import CalendarPage
        from .knowledge_page import KnowledgePage
        from .nutrition_page import NutritionPage

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

        # Восстанавливаем активную вкладку, если она известна
        saved_page = self.storage.get_value("app.active_page")
        if isinstance(saved_page, str) and saved_page in self.pages:
            self.show_page(saved_page)
        else:
            self.show_page("calendar")

    def _build_statusbar(self):
        bar = tk.Label(self, text=self.content.disclaimer, bg="#e5e7eb",
                       fg=self.theme.colors["muted"],
                       anchor="w", padx=10, pady=4, font=self.theme.font(8))
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
                btn.config(bg=self.theme.colors["sidebar_active"])
            else:
                btn.config(bg=self.theme.colors["sidebar"])
        self.current_page = key
