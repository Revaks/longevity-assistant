# -*- coding: utf-8 -*-
"""Вкладка «Активность»: отмечаем выполнение пунктов расписания.

На выбранный день показываются пункты (get_today_plan) с чекбоксами;
состояние хранится в Storage.completions (date + item_id). Под списком —
прогресс дня и сводка по текущей неделе.
"""

import datetime as dt
import tkinter as tk
from tkinter import ttk

from longevity.schedule import display_time, get_today_plan

from .app import WEEKDAYS, WEEKDAYS_FULL


class ActivityPage(ttk.Frame):
    def __init__(self, master, app):
        super().__init__(master, style="Page.TFrame")
        self.app = app
        self.theme = self.app.theme
        self.storage = self.app.storage
        self.selected_day = dt.date.today()
        self._vars: dict[str, tk.BooleanVar] = {}
        self._build()
        self.refresh()

    # -- внешний вид ----------------------------------------------------
    def _build(self):
        colors = self.theme.colors
        nav = ttk.Frame(self, style="Page.TFrame")
        nav.pack(fill="x", padx=12, pady=(12, 6))
        ttk.Button(nav, text="◀", width=4, command=self.prev_day).pack(side="left")
        ttk.Button(nav, text="Сегодня", command=self.goto_today).pack(side="left", padx=6)
        ttk.Button(nav, text="▶", width=4, command=self.next_day).pack(side="left")
        self.date_label = tk.Label(nav, text="", font=self.theme.font(13, "bold"),
                                   bg=colors["bg"], fg=colors["text"])
        self.date_label.pack(side="left", padx=16)

        self.list_frame = ttk.Frame(self, style="Page.TFrame")
        self.list_frame.pack(fill="both", expand=True, padx=12)

        self.progress_label = tk.Label(self, text="", bg=colors["bg"],
                                       fg=colors["text"], anchor="w",
                                       font=self.theme.font(10))
        self.progress_label.pack(fill="x", padx=12, pady=(4, 0))
        self.week_label = tk.Label(self, text="", bg=colors["bg"],
                                   fg=colors["muted"], anchor="w",
                                   justify="left", wraplength=1200,
                                   font=self.theme.font(9))
        self.week_label.pack(fill="x", padx=12, pady=(0, 10))

    # -- навигация ------------------------------------------------------
    def prev_day(self):
        self._change_day(self.selected_day - dt.timedelta(days=1))

    def next_day(self):
        self._change_day(self.selected_day + dt.timedelta(days=1))

    def goto_today(self):
        self._change_day(dt.date.today())

    def _change_day(self, day):
        self.selected_day = day
        self.refresh()

    # -- отрисовка ------------------------------------------------------
    def _clear_list(self):
        for child in self.list_frame.winfo_children():
            child.destroy()
        self._vars = {}

    def refresh(self):
        self._clear_list()
        day = self.selected_day
        self.date_label.config(
            text=f"{WEEKDAYS_FULL[day.weekday()]}, "
                 f"{day.day:02d}.{day.month:02d}.{day.year}")

        date = day.isoformat()
        done = self.storage.completions_on(date)
        items = get_today_plan(self.app.content, day)
        colors = self.theme.colors

        for item in items:
            var = tk.BooleanVar(value=item.id in done)
            self._vars[item.id] = var
            color = self.app.content.cat_colors.get(item.cat, "#333333")
            cb = ttk.Checkbutton(
                self.list_frame, text=f"{display_time(item)} — {item.title}",
                variable=var,
                command=lambda iid=item.id, v=var: self._toggle(iid, v))
            cb.pack(anchor="w", padx=4, pady=1)
            self.list_frame.columnconfigure(0, weight=1)
        if not items:
            tk.Label(self.list_frame, text="В этот день пунктов нет.",
                     bg=colors["bg"], fg=colors["muted"]).pack(anchor="w", padx=4)

        self._update_progress()

    def _toggle(self, item_id: str, var: tk.BooleanVar):
        new_state = self.storage.toggle_completion(
            self.selected_day.isoformat(), item_id)
        var.set(new_state)
        self._update_progress()

    def _update_progress(self):
        day = self.selected_day
        date = day.isoformat()
        done = self.storage.completions_on(date)
        total = len(get_today_plan(self.app.content, day))
        self.progress_label.config(
            text=f"Сделано: {len(done)} из {total}" if total
            else "На этот день расписания нет")

        # Сводка по текущей неделе: сделано/всего по каждому дню
        monday = day - dt.timedelta(days=day.weekday())
        counts = []
        for i in range(7):
            d = monday + dt.timedelta(days=i)
            d_total = len(get_today_plan(self.app.content, d))
            d_done = len(self.storage.completions_on(d.isoformat()))
            counts.append(f"{WEEKDAYS[i]} {d.day:02d}: {d_done}/{d_total}")
        self.week_label.config(text="Неделя: " + "   ".join(counts))
