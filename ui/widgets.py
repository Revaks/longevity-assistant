# -*- coding: utf-8 -*-
"""Общие виджеты интерфейса.

Сейчас единственный: ModelBar — панель выбора модели Ollama. Раньше страницы
«Питание» и «Ассистент» держали каждая свою копию списка моделей и свой
выпадающий список, опрашивая сервис синхронно в конструкторе (до 3 секунд
блокировки окна на страницу). Здесь — один виджет на обе страницы: опрос
идёт в фоновом потоке, результат приходит в интерфейс через after(0, ...).
"""

import threading
import tkinter as tk
from tkinter import ttk

from .ollama import generative, list_models

UNAVAILABLE = "Ollama недоступна"


def choose_model(available, saved):
    """Какую модель выбрать: сохранённую, если она ещё есть в списке, иначе первую.

    Вынесено отдельной чистой функцией — её видно и проверяемо без Tk и без
    фонового потока, в отличие от остальной механики ModelBar.
    """
    if not available:
        return ""
    if saved in available:
        return saved
    return available[0]


class ModelBar(ttk.Frame):
    """Выпадающий список генеративных моделей Ollama + кнопка «Обновить».

    Опрос сервиса (list_models) сам гасит любые сетевые ошибки и таймауты и
    в худшем случае возвращает пустой список — здесь достаточно перенести
    этот вызов в отдельный поток, чтобы неотвечающий порт не задерживал
    отрисовку окна. Выбор модели сохраняется в storage под ключом
    STORAGE_KEY и восстанавливается при следующем запуске; если сохранённой
    модели больше нет в списке, берётся первая доступная.
    """

    STORAGE_KEY = "app.ollama_model"

    def __init__(self, master, theme, storage, label="Модель:"):
        super().__init__(master, style="Page.TFrame")
        self.theme = theme
        self.storage = storage
        self.models: list = []
        self._on_change = None

        colors = theme.colors
        tk.Label(self, text=label, bg=colors["bg"], fg=colors["muted"]).pack(
            side="left", padx=(0, 4))
        self.model_var = tk.StringVar(value=UNAVAILABLE)
        self.combo = ttk.Combobox(self, textvariable=self.model_var, state="disabled",
                                  values=[UNAVAILABLE], width=16)
        self.combo.pack(side="left")
        self.combo.bind("<<ComboboxSelected>>", self._on_select)
        self.refresh_btn = ttk.Button(self, text="Обновить", command=self.refresh)
        self.refresh_btn.pack(side="left", padx=(6, 0))
        self.status = tk.Label(self, text="", bg=colors["bg"], fg=colors["muted"])
        self.status.pack(side="left", padx=(8, 0))

        self.refresh()

    def on_change(self, callback):
        """callback(model_name) вызывается всякий раз, когда выбор меняется.

        При отсутствии моделей вызывается с пустой строкой.
        """
        self._on_change = callback

    def current(self) -> str:
        """Текущая выбранная модель или "" — если ни одной подходящей нет."""
        value = self.model_var.get()
        return value if value in self.models else ""

    def refresh(self):
        """Переопросить Ollama в фоновом потоке. Безопасно звать сколько угодно раз."""
        self.refresh_btn.config(state="disabled")
        self.status.config(text="Опрашиваю Ollama...")

        def work():
            models = generative(list_models())
            self.after(0, lambda: self._apply(models))

        threading.Thread(target=work, daemon=True).start()

    def _apply(self, models: list) -> None:
        self.models = models
        self.refresh_btn.config(state="normal")
        if not models:
            self.combo.config(state="disabled", values=[UNAVAILABLE])
            self.model_var.set(UNAVAILABLE)
            self.status.config(text="Ollama недоступна или нет подходящих моделей")
            self._notify("")
            return
        self.combo.config(state="readonly", values=models)
        chosen = choose_model(models, self._load_saved())
        self.model_var.set(chosen)
        self.status.config(text="")
        self._save(chosen)
        self._notify(chosen)

    def _on_select(self, _event=None):
        chosen = self.model_var.get()
        self._save(chosen)
        self._notify(chosen)

    def _notify(self, model: str) -> None:
        if self._on_change:
            self._on_change(model)

    def _load_saved(self):
        if self.storage is None:
            return None
        try:
            return self.storage.get_value(self.STORAGE_KEY)
        except Exception:
            return None

    def _save(self, model: str) -> None:
        if self.storage is None or not model:
            return
        try:
            self.storage.set_value(self.STORAGE_KEY, model)
        except Exception:
            pass
