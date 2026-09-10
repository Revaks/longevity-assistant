# -*- coding: utf-8 -*-
"""Вкладка «Активность»: отмечаем выполнение пунктов расписания.

На выбранный день показываются пункты (items_for_day — с учётом профиля,
скрытых и своих пунктов, ротации) с чекбоксами и сериями; состояние хранится
в Storage.completions (date + item_id). Под списком — прогресс дня, сводка по
текущей неделе и «слабые места» за 30 дней.
"""

import datetime as dt
import tkinter as tk
from tkinter import ttk

from longevity.habits import streaks, weak_spots
from longevity.plan import item_ids_for_day, items_for_day
from longevity.schedule import display_time

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

    def on_show(self):
        self.refresh()

    # -- данные ---------------------------------------------------------
    def _profile(self):
        return self.storage.load_profile()

    def _custom_items(self):
        return self.storage.load_custom_items(self.app.content.categories)

    def _items_for(self, day):
        return items_for_day(self.app.content, self._profile(), self._custom_items(), day)

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
        self.week_label.pack(fill="x", padx=12, pady=(0, 4))
        self.weak_label = tk.Label(self, text="", bg=colors["bg"],
                                   fg=colors["muted"], anchor="w",
                                   justify="left", wraplength=1200,
                                   font=self.theme.font(9))
        self.weak_label.pack(fill="x", padx=12, pady=(0, 10))

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
        content = self.app.content
        self.date_label.config(
            text=f"{WEEKDAYS_FULL[day.weekday()]}, "
                 f"{day.day:02d}.{day.month:02d}.{day.year}")

        date = day.isoformat()
        done = self.storage.completions_on(date)
        items = self._items_for(day)
        colors = self.theme.colors

        ids_for = lambda d: item_ids_for_day(content, self._profile(), self._custom_items(), d)
        done_for = lambda d: self.storage.completions_on(d.isoformat())
        streak_map = streaks([item.id for item in items], day, ids_for, done_for)

        for item in items:
            var = tk.BooleanVar(value=item.id in done)
            self._vars[item.id] = var
            text = f"{display_time(item)} — {item.title}"
            streak = streak_map.get(item.id, 0)
            if streak:
                text += f"   • серия {streak}"
            ttk.Checkbutton(
                self.list_frame, text=text, variable=var,
                command=lambda iid=item.id, v=var: self._toggle(iid, v)).pack(
                anchor="w", padx=4, pady=1)
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
        content = self.app.content
        done = self.storage.completions_on(day.isoformat())
        items = self._items_for(day)
        done_count = sum(1 for item in items if item.id in done)
        total = len(items)
        self.progress_label.config(
            text=f"Сделано: {done_count} из {total}" if total
            else "На этот день расписания нет")

        # Сводка по текущей неделе: сделано/всего по каждому дню
        monday = day - dt.timedelta(days=day.weekday())
        counts = []
        for i in range(7):
            d = monday + dt.timedelta(days=i)
            d_items = self._items_for(d)
            d_done = self.storage.completions_on(d.isoformat())
            d_count = sum(1 for item in d_items if item.id in d_done)
            counts.append(f"{WEEKDAYS[i]} {d.day:02d}: {d_count}/{len(d_items)}")
        self.week_label.config(text="Неделя: " + "   ".join(counts))

        self.weak_label.config(text=self._weak_spots_text(monday))

    def _weak_spots_text(self, monday) -> str:
        """Какие пункты чаще всего пропускались за последние 30 дней."""
        content = self.app.content
        profile = self._profile()
        custom = self._custom_items()
        today = dt.date.today()

        planned: dict[str, int] = {}
        done_counts: dict[str, int] = {}
        titles: dict[str, str] = {}
        for offset in range(30):
            d = today - dt.timedelta(days=offset)
            done_today = self.storage.completions_on(d.isoformat())
            for item in items_for_day(content, profile, custom, d):
                planned[item.id] = planned.get(item.id, 0) + 1
                titles[item.id] = item.title
                if item.id in done_today:
                    done_counts[item.id] = done_counts.get(item.id, 0) + 1

        weak = weak_spots(planned, done_counts, limit=3, min_planned=3)
        weak = [(titles.get(iid, iid), ratio) for iid, ratio in weak if ratio < 0.999]
        if not weak:
            return ""
        parts = [f"{title} — {int(ratio * 100)}%" for title, ratio in weak]
        return "Чаще всего пропускаете: " + "; ".join(parts)
