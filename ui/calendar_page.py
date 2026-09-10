# -*- coding: utf-8 -*-
"""Страница «Календарь»."""

import datetime as dt
import tkinter as tk
from tkinter import ttk

from longevity.habits import streaks
from longevity.plan import focus_for_week, focus_task_ids, item_ids_for_day, items_for_day
from longevity.schedule import display_time

from .app import WEEKDAYS_FULL, fmt_day
from . import calendar_dialogs


class CalendarPage(ttk.Frame):
    #: Фон шапки обычного и выбранного дня — разовые оттенки этой страницы,
    #: не входят в PALETTE (см. task-6-report). Иконка заметки на них тёмная
    #: ("note"); в тестах на контраст (tests/test_icons.py) эти константы
    #: читаются напрямую, чтобы смена цвета здесь не разошлась с проверкой.
    HEADER_BG_DEFAULT = "#e5e7eb"
    HEADER_BG_SELECTED = "#cffafe"

    def __init__(self, master, app):
        super().__init__(master, style="Page.TFrame")
        self.app = app
        self.theme = self.app.theme
        self.storage = self.app.storage
        self.week_start = self._monday(dt.date.today())
        self.selected_day = dt.date.today()
        self._focus_vars = []
        self._build()
        self.refresh()

    @staticmethod
    def _monday(d: dt.date) -> dt.date:
        return d - dt.timedelta(days=d.weekday())

    # -- данные ---------------------------------------------------------
    def _profile(self):
        return self.storage.load_profile()

    def _custom_items(self):
        return self.storage.load_custom_items(self.app.content.categories)

    def _build(self):
        colors = self.theme.colors

        # Верхняя панель навигации
        nav = ttk.Frame(self, style="Page.TFrame")
        nav.pack(fill="x", padx=12, pady=(12, 6))

        self.btn_prev = ttk.Button(nav, text="◀", width=4, command=self.prev_week)
        self.btn_prev.pack(side="left")
        ttk.Button(nav, text="Сегодня", command=self.goto_today).pack(side="left", padx=6)
        self.btn_next = ttk.Button(nav, text="▶", width=4, command=self.next_week)
        self.btn_next.pack(side="left")

        self.week_label = tk.Label(nav, text="", font=self.theme.font(13, "bold"),
                                   bg=colors["bg"], fg=colors["text"])
        self.week_label.pack(side="left", padx=16)

        legend = ttk.Frame(nav, style="Page.TFrame")
        legend.pack(side="right")
        ttk.Button(legend, text="Настройки", command=self._open_settings).pack(
            side="left", padx=(0, 10))
        for cat, color in self.app.content.cat_colors.items():
            tk.Label(legend, text="●", fg=color, bg=colors["bg"]).pack(side="left", padx=(8, 1))
            tk.Label(legend, text=cat, bg=colors["bg"], fg=colors["muted"]).pack(side="left")

        # Заметки редактируются во вкладке «Заметки»; здесь — только индикатор.
        self.grid_frame = ttk.Frame(self, style="Page.TFrame")
        self.grid_frame.pack(fill="both", expand=True, padx=12)

        self.day_widgets = []  # [(header, text_widget, col_frame)]
        for i in range(7):
            col = ttk.Frame(self.grid_frame, style="Page.TFrame")
            col.grid(row=0, column=i, sticky="nsew", padx=2)
            self.grid_frame.columnconfigure(i, weight=1)
            header = tk.Label(col, text="", font=self.theme.font(10, "bold"),
                              pady=6, relief="groove", bd=1)
            header.pack(fill="x")
            txt = tk.Text(col, height=16, wrap="word", cursor="hand2",
                          relief="groove", bd=1, padx=6, pady=6,
                          font=self.theme.font(9), state="disabled",
                          bg=colors["card"], fg=colors["text"])
            txt.pack(fill="both", expand=True)
            header.bind("<Button-1>", lambda e, idx=i: self._on_col_click(idx))
            txt.bind("<Button-1>", lambda e, idx=i: self._on_col_click(idx))
            self.day_widgets.append((header, txt, col))
        self.grid_frame.rowconfigure(0, weight=1)

        # Фокус недели — тема с заданиями, отметки пишутся в completions.
        self.focus_frame = ttk.Frame(self, style="Page.TFrame")
        self.focus_frame.pack(fill="x", padx=12, pady=(6, 0))

        # Детали выбранного дня — внизу, компактно
        self.detail = tk.Text(self, height=4, wrap="word", relief="groove", bd=1,
                              padx=10, pady=6, font=self.theme.font(10),
                              bg=colors["card"], fg=colors["text"], state="disabled")
        self.detail.pack(fill="x", padx=12, pady=(6, 10))

    # -- настройки ------------------------------------------------------
    def _open_settings(self):
        calendar_dialogs.show_actions(
            self, self._edit_profile, self._edit_items, self._add_measure)

    def _edit_profile(self):
        profile = calendar_dialogs.show_profile(self, self._profile())
        if profile is not None:
            self.storage.save_profile(profile)
            self.refresh()

    def _edit_items(self):
        result = calendar_dialogs.show_items(
            self, self.app.content, self._custom_items(), self._profile().hidden)
        if result is not None:
            custom, hidden = result
            self.storage.save_custom_items(custom)
            self.storage.save_hidden(hidden)
            self.refresh()

    def _add_measure(self):
        values = calendar_dialogs.show_measure(self)
        if values:
            for kind, value in values:
                self.storage.add_measurement(kind, value)

    def on_show(self):
        """Перерисовать план при показе — профиль мог измениться на другой вкладке."""
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
        colors = self.theme.colors
        today = dt.date.today()
        content = self.app.content
        profile = self._profile()
        custom = self._custom_items()
        sunday = self.week_start + dt.timedelta(days=6)
        self.week_label.config(
            text=f"{self.week_start.day:02d}.{self.week_start.month:02d} – "
                 f"{sunday.day:02d}.{sunday.month:02d}.{sunday.year}")

        week_notes = self.storage.diary_entries_in_range(
            self.week_start.isoformat(),
            (self.week_start + dt.timedelta(days=6)).isoformat(),
        )

        for i, (header, txt, _col) in enumerate(self.day_widgets):
            day = self.week_start + dt.timedelta(days=i)
            key = day.isoformat()
            notes = [e for e in week_notes if e["date"] == key]
            is_today = day == today

            if notes:
                icon_name = "note-light" if is_today else "note"
                header.config(text=fmt_day(day), image=self.theme.icon(icon_name, 16),
                              compound="right")
            else:
                header.config(text=fmt_day(day), image="", compound="right")
            if is_today:
                header.config(bg=colors["accent"], fg=colors["card"])
            elif day == self.selected_day:
                header.config(bg=self.HEADER_BG_SELECTED, fg="#134e4a")
            else:
                header.config(bg=self.HEADER_BG_DEFAULT, fg=colors["text"])

            txt.config(state="normal")
            txt.delete("1.0", "end")
            items = items_for_day(content, profile, custom, day)
            for it in items:
                color = content.cat_colors.get(it.cat, "#333333")
                tag = f"cat{i}_{it.cat.replace(' ', '')}"
                txt.tag_configure(tag, foreground=color,
                                  font=self.theme.font(9, "bold"))
                txt.insert("end", f"{display_time(it)}  ", "time")
                txt.insert("end", it.title + "\n", tag)
            if notes:
                txt.tag_configure("note", foreground="#92400e",
                                  font=self.theme.font(9, slant="italic"))
                txt.insert("end", "\n")
                for entry in notes:
                    txt.insert("end", entry["text"] + "\n", "note")
            txt.tag_configure("time", foreground=colors["muted"], font=self.theme.font(9))
            txt.config(state="disabled")

        self._render_focus()
        self._show_day_detail()

    def _render_focus(self):
        colors = self.theme.colors
        for child in self.focus_frame.winfo_children():
            child.destroy()
        self._focus_vars = []

        content = self.app.content
        focus = focus_for_week(content, self.week_start)
        if focus is None:
            return

        head = ttk.Frame(self.focus_frame, style="Page.TFrame")
        head.pack(fill="x")
        tk.Label(head, text=focus.title, bg=colors["bg"], fg=colors["text"],
                 font=self.theme.font(11, "bold")).pack(side="left")
        tk.Label(head, text=focus.detail, bg=colors["bg"], fg=colors["muted"],
                 font=self.theme.font(9), wraplength=700, justify="left").pack(
            side="left", padx=10)

        date = self.selected_day.isoformat()
        done = self.storage.completions_on(date)
        for index, task in enumerate(focus.tasks):
            task_id = f"focus:{focus.id}:{index}"
            var = tk.BooleanVar(value=task_id in done)
            self._focus_vars.append((task_id, var))
            ttk.Checkbutton(
                self.focus_frame, text=task, variable=var,
                command=lambda tid=task_id, v=var: self._toggle_focus(tid, v),
            ).pack(anchor="w", padx=4)

    def _toggle_focus(self, task_id, var):
        self.storage.toggle_completion(self.selected_day.isoformat(), task_id)
        var.set(task_id in self.storage.completions_on(self.selected_day.isoformat()))

    def _show_day_detail(self):
        colors = self.theme.colors
        content = self.app.content
        profile = self._profile()
        custom = self._custom_items()
        self.detail.config(state="normal")
        self.detail.delete("1.0", "end")
        day = self.selected_day
        items = items_for_day(content, profile, custom, day)

        # Серии считаются по плановым id на день (не по скрытым/чужим).
        done_for = lambda d: self.storage.completions_on(d.isoformat())
        ids_for = lambda d: item_ids_for_day(content, profile, custom, d)
        streak_map = streaks([it.id for it in items], day, ids_for, done_for)

        self.detail.insert("end", f"{WEEKDAYS_FULL[day.weekday()]}, "
                                  f"{day.day:02d}.{day.month:02d}.{day.year}\n", "h")
        self.detail.tag_configure("h", font=self.theme.font(11, "bold"))
        for it in items:
            color = content.cat_colors.get(it.cat, "#333333")
            tag = "d_" + it.cat.replace(" ", "")
            self.detail.tag_configure(tag, foreground=color,
                                      font=self.theme.font(10, "bold"))
            self.detail.insert("end", f"\n{display_time(it)} — {it.title} ", tag)
            streak = streak_map.get(it.id, 0)
            if streak:
                self.detail.insert("end", f"(серия {streak}) ", "streak")
            self.detail.insert("end", f"({it.cat})\n", "cat")
            if it.detail:
                self.detail.insert("end", it.detail + "\n", "det")
        self.detail.tag_configure("cat", foreground=colors["muted"])
        self.detail.tag_configure("det", foreground="#374151")
        self.detail.tag_configure("streak", foreground=colors["accent"],
                                  font=self.theme.font(10, slant="italic"))
        self.detail.config(state="disabled")
