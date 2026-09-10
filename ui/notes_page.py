# -*- coding: utf-8 -*-
"""Вкладка «Заметки»: дневник с несколькими записями на каждый день.

В отличие от старого поля в календаре, «Сохранить» не заменяет прошлую
заметку: запись добавляется, а редактируются они по отдельности. Данные
живут в таблице diary (см. longevity/storage.py).
"""

import datetime as dt
import tkinter as tk
from tkinter import ttk

from .app import WEEKDAYS_FULL


class NotesPage(ttk.Frame):
    def __init__(self, master, app):
        super().__init__(master, style="Page.TFrame")
        self.app = app
        self.theme = self.app.theme
        self.storage = self.app.storage
        self.selected_day = dt.date.today()
        self.current_id = None          # выбранная запись в списке
        self._loaded_text = ""          # текст при последней загрузке
        self._build()
        self.refresh()

    # -- внешний вид ----------------------------------------------------
    def _build(self):
        colors = self.theme.colors
        nav = ttk.Frame(self, style="Page.TFrame")
        nav.pack(fill="x", padx=12, pady=(12, 6))
        ttk.Button(nav, text="◀", width=4, command=self.prev_day).pack(side="left")
        ttk.Button(nav, text="Сегодня", command=self.goto_today).pack(
            side="left", padx=6)
        ttk.Button(nav, text="▶", width=4, command=self.next_day).pack(side="left")
        self.date_label = tk.Label(nav, text="", font=self.theme.font(13, "bold"),
                                   bg=colors["bg"], fg=colors["text"])
        self.date_label.pack(side="left", padx=16)
        self.count_label = tk.Label(nav, text="", bg=colors["bg"],
                                    fg=colors["muted"])
        self.count_label.pack(side="right")
        ttk.Button(nav, text="+ Заметка",
                   command=self.add_new).pack(side="right", padx=4)

        # Список записей дня
        list_frame = ttk.Frame(self, style="Page.TFrame")
        list_frame.pack(fill="both", expand=True, padx=12)
        self.tree = ttk.Treeview(list_frame, columns=("time", "preview"),
                                 show="headings", selectmode="browse")
        self.tree.heading("time", text="Время")
        self.tree.heading("preview", text="Заметка")
        self.tree.column("time", width=110, anchor="w")
        self.tree.column("preview", width=640, anchor="w")
        vsb = ttk.Scrollbar(list_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        self.tree.bind("<<TreeviewSelect>>", self._on_select)

        # Редактор записи
        editor = ttk.Frame(self, style="Page.TFrame")
        editor.pack(fill="x", padx=12, pady=(6, 12))
        self.note_text = tk.Text(editor, height=5, wrap="word",
                                 relief="groove", bd=1, padx=6, pady=4,
                                 font=self.theme.font(11),
                                 bg=colors["card"], fg=colors["text"])
        self.note_text.pack(side="left", fill="x", expand=True, padx=(0, 6))
        btns = ttk.Frame(editor, style="Page.TFrame")
        btns.pack(side="left", anchor="n")
        ttk.Button(btns, text="Сохранить", command=self.save).pack(pady=(0, 4), fill="x")
        ttk.Button(btns, text="Удалить", command=self.delete_entry).pack(fill="x")

    # -- навигация по дням ----------------------------------------------
    def prev_day(self):
        self._change_day(self.selected_day - dt.timedelta(days=1))

    def next_day(self):
        self._change_day(self.selected_day + dt.timedelta(days=1))

    def goto_today(self):
        self._change_day(dt.date.today())

    def _change_day(self, day):
        self._commit_dirty()
        self.selected_day = day
        self.refresh()

    def _fmt(self, day: dt.date) -> str:
        return f"{WEEKDAYS_FULL[day.weekday()]}, {day.day:02d}.{day.month:02d}.{day.year}"

    # -- работа с записями ----------------------------------------------
    def _human_time(self, iso: str) -> str:
        """HH:MM из ISO-времени создания (UTC -> локальное смещение не
        пересчитываем: время создания записи — служебная подпись)."""
        return iso[11:16] if len(iso) >= 16 else iso

    def refresh(self):
        """Перечитать записи выбранного дня и очистить редактор."""
        self.date_label.config(text=self._fmt(self.selected_day))
        date = self.selected_day.isoformat()
        entries = self.storage.diary_entries_on(date)

        self.tree.delete(*self.tree.get_children())
        for e in entries:
            text = " ".join(e["text"].split())
            self.tree.insert("", "end", iid=str(e["id"]),
                             values=(self._human_time(e["created"]),
                                     text[:140]))
        self.current_id = None
        self._loaded_text = ""
        self.note_text.delete("1.0", "end")
        self.count_label.config(
            text=f"Записей: {len(entries)}" if entries else "Нет записей на этот день")

    def _on_select(self, _event=None):
        sel = self.tree.selection()
        if not sel:
            return
        target_id = int(sel[0])
        self._commit_dirty()          # несохранённые правки уходят в свою запись
        rows = self.storage.diary_entries_on(self.selected_day.isoformat())
        entry = next((e for e in rows if e["id"] == target_id), None)
        if entry is None:
            self.refresh()
            return
        self.current_id = target_id
        self._loaded_text = entry["text"]
        self.note_text.delete("1.0", "end")
        self.note_text.insert("1.0", entry["text"])
        self.note_text.focus_set()

    def add_new(self):
        """Начать новую запись: редактор очищается и станет «+». Сохранить
        создаст отдельную запись, а не заменит выбранную."""
        self._commit_dirty()
        self.tree.selection_remove(self.tree.selection())
        self.current_id = None
        self._loaded_text = ""
        self.note_text.delete("1.0", "end")
        self.note_text.focus_set()

    def save(self):
        """Обновить выбранную запись или создать новую (если записи нет)."""
        self._commit_dirty()
        saved_id = self.current_id
        saved_text = self._loaded_text
        self.refresh()
        if saved_id is not None:
            self.tree.selection_set(str(saved_id))
            self.tree.see(str(saved_id))
            self.note_text.insert("1.0", saved_text)
            self._loaded_text = saved_text

    def _commit_dirty(self):
        """Сохранить несохранённый текст без перестройки списка.

        Не делает refresh(): обновление записи на месте, переключение дня и
        списка не дёргает дерево и не теряет выбор пользователя.
        """
        text = self.note_text.get("1.0", "end-1c").strip()
        if not text or text == self._loaded_text:
            return
        if self.current_id is not None:
            self.storage.update_diary(self.current_id, text)
        else:
            self.current_id = self.storage.add_diary(
                self.selected_day.isoformat(), text)
        self._loaded_text = text

    def delete_entry(self):
        if self.current_id is None:
            return
        self.storage.delete_diary(self.current_id)
        self.current_id = None
        self._loaded_text = ""
        self.refresh()
