# -*- coding: utf-8 -*-
"""Общие виджеты интерфейса.

ModelStore — единственный источник истины о списке моделей Ollama и текущем
выборе. Раньше страницы «Питание» и «Ассистент» держали каждая свою копию
списка моделей и свой выпадающий список — сервис опрашивался дважды, а смена
модели на одной вкладке была не видна на другой. Теперь опрос и хранение
выбора живут в ModelStore (один экземпляр на приложение, опрашивается один
раз при старте); ModelBar — тонкое отображение, подписанное на изменения
store через subscribe() и не хранящее собственного состояния.
"""

import threading
import tkinter as tk
from tkinter import ttk

from .ollama import generative, list_models

UNAVAILABLE = "Ollama недоступна"


def choose_model(available, saved):
    """Какую модель выбрать: сохранённую, если она ещё есть в списке, иначе первую.

    Вынесено отдельной чистой функцией — её видно и проверяемо без Tk и без
    фонового потока, в отличие от остальной механики ModelStore.
    """
    if not available:
        return ""
    if saved in available:
        return saved
    return available[0]


class ModelStore:
    """Список моделей Ollama, текущий выбор и опрос сервиса — в одном месте.

    Создаётся один раз на приложение (см. ui/app.py) и передаётся обеим
    страницам; каждая строит свою ModelBar поверх одного и того же store,
    поэтому опрос сервиса происходит один раз, а смена модели на одной
    панели немедленно видна на другой через subscribe().

    Окно может быть закрыто в любой момент незавершённого опроса — это
    нормальный сценарий, а не исключительный: root.after(...), вызванный из
    фонового потока после того как окно уже уничтожено, около секунды
    пытается достучаться до исчезнувшего цикла событий и в итоге бросает
    RuntimeError('main thread is not in main loop'). _deliver() эту (и
    любую другую) ошибку планирования гасит — поток обязан завершиться
    тихо, а не уронить threading.excepthook трассировкой.
    """

    STORAGE_KEY = "app.ollama_model"

    def __init__(self, root, storage):
        self._root = root
        self.storage = storage
        self.models: list = []
        self.current: str = ""
        self.status: str = ""
        self.busy: bool = False
        self._subscribers = []
        self._thread = None  # ссылка нужна только тестам, чтобы дождаться потока

    def subscribe(self, callback) -> None:
        """callback(store) вызывается сразу с текущим состоянием и при каждом изменении."""
        self._subscribers.append(callback)
        callback(self)

    def select(self, model: str) -> None:
        """Пользователь выбрал модель на одной из панелей — сохранить и разослать всем."""
        if model not in self.models or model == self.current:
            return
        self.current = model
        self._save(model)
        self._notify()

    def refresh(self) -> None:
        """Опросить Ollama в фоновом потоке. Один вызов — один сетевой опрос
        независимо от того, сколько панелей на store подписано."""
        if self.busy:
            return
        self.busy = True
        self.status = "Опрашиваю Ollama..."
        self._notify()

        def work():
            models = generative(list_models())
            self._deliver(models)

        self._thread = threading.Thread(target=work, daemon=True)
        self._thread.start()

    def _deliver(self, models: list) -> None:
        """Выполняется в фоновом потоке — не должна бросать исключений наружу."""
        try:
            self._root.after(0, lambda: self._apply(models))
        except Exception:
            pass

    def _apply(self, models: list) -> None:
        self.models = models
        self.busy = False
        if not models:
            self.current = ""
            self.status = "Ollama недоступна или нет подходящих моделей"
        else:
            self.current = choose_model(models, self._load_saved())
            self.status = ""
            self._save(self.current)
        self._notify()

    def _notify(self) -> None:
        for callback in list(self._subscribers):
            try:
                callback(self)
            except Exception:
                pass

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


class ModelBar(ttk.Frame):
    """Выпадающий список генеративных моделей Ollama + кнопка «Обновить».

    Никакого собственного состояния не хранит — только отображает ModelStore
    и пересылает ему действия пользователя (выбор в списке, клик «Обновить»).
    """

    def __init__(self, master, theme, store: ModelStore, label="Модель:"):
        super().__init__(master, style="Page.TFrame")
        self.theme = theme
        self.store = store

        colors = theme.colors
        tk.Label(self, text=label, bg=colors["bg"], fg=colors["muted"]).pack(
            side="left", padx=(0, 4))
        self.model_var = tk.StringVar(value=UNAVAILABLE)
        self.combo = ttk.Combobox(self, textvariable=self.model_var, state="disabled",
                                  values=[UNAVAILABLE], width=16)
        self.combo.pack(side="left")
        self.combo.bind("<<ComboboxSelected>>", self._on_select)
        self.refresh_btn = ttk.Button(self, text="Обновить", command=self.store.refresh)
        self.refresh_btn.pack(side="left", padx=(6, 0))
        self.status = tk.Label(self, text="", bg=colors["bg"], fg=colors["muted"])
        self.status.pack(side="left", padx=(8, 0))

        self.store.subscribe(self._on_store_change)

    def current(self) -> str:
        """Текущая выбранная модель или "" — если ни одной подходящей нет."""
        return self.store.current

    def _on_select(self, _event=None):
        self.store.select(self.model_var.get())

    def _on_store_change(self, store: ModelStore) -> None:
        # store уведомляет о себе синхронно из subscribe() и из after(0, ...) —
        # оба раза на главном потоке, но виджет к этому моменту мог быть уже
        # уничтожен (закрытие окна), поэтому обращения к нему защищены.
        try:
            self._render(store)
        except tk.TclError:
            pass

    def _render(self, store: ModelStore) -> None:
        self.refresh_btn.config(state="disabled" if store.busy else "normal")
        self.status.config(text=store.status)
        if not store.models:
            self.combo.config(state="disabled", values=[UNAVAILABLE])
            self.model_var.set(UNAVAILABLE)
            return
        self.combo.config(state="readonly", values=store.models)
        self.model_var.set(store.current)
