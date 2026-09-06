# -*- coding: utf-8 -*-
"""Страница «Календарь»."""

import datetime as dt
import tkinter as tk
from tkinter import messagebox, ttk

from longevity.schedule import display_time, get_today_plan

from .app import WEEKDAYS_FULL, fmt_day


class CalendarPage(ttk.Frame):
    def __init__(self, master, app):
        super().__init__(master, style="Page.TFrame")
        self.app = app
        self.theme = self.app.theme
        self.storage = self.app.storage
        self.week_start = self._monday(dt.date.today())
        self.selected_day = dt.date.today()
        self._build()

    @staticmethod
    def _monday(d: dt.date) -> dt.date:
        return d - dt.timedelta(days=d.weekday())

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
        for cat, color in self.app.content.cat_colors.items():
            tk.Label(legend, text="●", fg=color, bg=colors["bg"]).pack(side="left", padx=(8, 1))
            tk.Label(legend, text=cat, bg=colors["bg"], fg=colors["muted"]).pack(side="left")

        # Сетка дней недели
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
            txt = tk.Text(col, height=24, wrap="word", cursor="hand2",
                          relief="groove", bd=1, padx=6, pady=6,
                          font=self.theme.font(9), state="disabled",
                          bg=colors["card"], fg=colors["text"])
            txt.pack(fill="both", expand=True)
            header.bind("<Button-1>", lambda e, idx=i: self._on_col_click(idx))
            txt.bind("<Button-1>", lambda e, idx=i: self._on_col_click(idx))
            self.day_widgets.append((header, txt, col))
        self.grid_frame.rowconfigure(0, weight=1)

        # Нижняя панель с деталями выбранного дня
        self.detail = tk.Text(self, height=8, wrap="word", relief="groove", bd=1,
                              padx=10, pady=8, font=self.theme.font(10),
                              bg=colors["card"], fg=colors["text"], state="disabled")
        self.detail.pack(fill="x", padx=12, pady=(6, 6))

        # Панель заметок на выбранный день
        notes_bar = ttk.Frame(self, style="Page.TFrame")
        notes_bar.pack(fill="x", padx=12, pady=(0, 12))
        tk.Label(notes_bar, text="Заметка на день:", bg=colors["bg"],
                 fg=colors["text"]).pack(side="left")
        self.note_var = tk.StringVar()
        self.note_entry = ttk.Entry(notes_bar, textvariable=self.note_var,
                                    font=self.theme.font(10))
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
        colors = self.theme.colors
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
            header.config(text=fmt_day(day))
            if day == today:
                header.config(bg=colors["accent"], fg=colors["card"])
            elif day == self.selected_day:
                header.config(bg="#cffafe", fg="#134e4a")
            else:
                header.config(bg="#e5e7eb", fg=colors["text"])

            txt.config(state="normal")
            txt.delete("1.0", "end")
            items = get_today_plan(self.app.content, day)
            for it in items:
                color = self.app.content.cat_colors.get(it.cat, "#333333")
                tag = f"cat{i}_{it.cat.replace(' ', '')}"
                txt.tag_configure(tag, foreground=color,
                                  font=self.theme.font(9, "bold"))
                txt.insert("end", f"{display_time(it)}  ", "time")
                txt.insert("end", it.title + "\n", tag)
            note = week_notes.get(key)
            if note:
                txt.insert("end", "\n" + note + "\n", "note")
                txt.tag_configure("note", foreground="#92400e",
                                  font=self.theme.font(9, slant="italic"))
            txt.tag_configure("time", foreground=colors["muted"], font=self.theme.font(9))
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
        colors = self.theme.colors
        self.detail.config(state="normal")
        self.detail.delete("1.0", "end")
        day = self.selected_day
        items = get_today_plan(self.app.content, day)
        self.detail.insert("end", f"{WEEKDAYS_FULL[day.weekday()]}, "
                                  f"{day.day:02d}.{day.month:02d}.{day.year}\n", "h")
        self.detail.tag_configure("h", font=self.theme.font(11, "bold"))
        for it in items:
            color = self.app.content.cat_colors.get(it.cat, "#333333")
            tag = "d_" + it.cat.replace(" ", "")
            self.detail.tag_configure(tag, foreground=color,
                                      font=self.theme.font(10, "bold"))
            self.detail.insert("end", f"\n{display_time(it)} — {it.title} ", tag)
            self.detail.insert("end", f"({it.cat})\n", "cat")
            if it.detail:
                self.detail.insert("end", it.detail + "\n", "det")
        self.detail.tag_configure("cat", foreground=colors["muted"])
        self.detail.tag_configure("det", foreground="#374151")
        self.detail.config(state="disabled")
