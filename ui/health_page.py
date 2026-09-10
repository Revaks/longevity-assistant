# -*- coding: utf-8 -*-
"""Вкладка «Здоровье»: биодневник (измерения) и профилактические обследования.

Измерения хранятся в таблице measurements (вид, значение, дата); здесь для
каждого вида показываются последнее значение, изменение к предыдущему и
минимум/максимум. Обследования выбираются по возрасту и полу из профиля
(longevity/screenings.py), отметки — в профиле под user.screen.<id>.
"""

import datetime as dt
import tkinter as tk
from tkinter import ttk

from longevity.measures import KINDS, delta, format_value
from longevity.screenings import for_profile, next_due

from . import calendar_dialogs


def _fmt_date(iso: str) -> str:
    try:
        d = dt.date.fromisoformat(iso)
    except ValueError:
        return iso
    return f"{d.day:02d}.{d.month:02d}.{d.year}"


class HealthPage(ttk.Frame):
    def __init__(self, master, app):
        super().__init__(master, style="Page.TFrame")
        self.app = app
        self.theme = self.app.theme
        self.storage = self.app.storage
        self._build()
        self.refresh()

    def on_show(self):
        self.refresh()

    def _build(self):
        colors = self.theme.colors
        nav = ttk.Frame(self, style="Page.TFrame")
        nav.pack(fill="x", padx=12, pady=(12, 6))
        ttk.Button(nav, text="+ Добавить измерение",
                   command=self._add_measure).pack(side="left")

        container = ttk.Frame(self, style="Page.TFrame")
        container.pack(fill="both", expand=True, padx=12)

        canvas = tk.Canvas(container, highlightthickness=0, bg=colors["bg"])
        scrollbar = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
        self.scroll_inner = ttk.Frame(canvas, style="Page.TFrame")
        self.scroll_inner.bind("<Configure>", lambda _e: canvas.configure(
            scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self.scroll_inner, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

    # -- действия -------------------------------------------------------
    def _add_measure(self):
        values = calendar_dialogs.show_measure(self)
        if values:
            for kind, value in values:
                self.storage.add_measurement(kind, value)
            self.refresh()

    # -- отрисовка ------------------------------------------------------
    def refresh(self):
        colors = self.theme.colors
        for child in self.scroll_inner.winfo_children():
            child.destroy()

        self._render_bio()
        self._render_screenings()

    def _render_bio(self):
        colors = self.theme.colors
        card = ttk.Frame(self.scroll_inner, style="Page.TFrame")
        card.pack(fill="x", pady=(0, 8))
        tk.Label(card, text="Биодневник", bg=colors["bg"], fg=colors["text"],
                 font=self.theme.font(12, "bold")).pack(anchor="w")

        filled = []
        for kind in KINDS:
            rows = self.storage.measurements_of_kind(kind.id)
            if rows:
                filled.append((kind, rows))

        if not filled:
            tk.Label(card, text="Пока пусто. Записывайте вес, талию, давление, "
                                "пульс — здесь появится динамика.",
                     bg=colors["bg"], fg=colors["muted"],
                     font=self.theme.font(9), justify="left").pack(anchor="w", pady=(4, 0))
            return

        for kind, rows in filled:
            latest = rows[0]
            previous = rows[1] if len(rows) > 1 else None
            line = f"{kind.title}: {format_value(kind.id, latest['value'])} " \
                   f"({_fmt_date(latest['date'])})"
            if previous is not None:
                line += f", {delta(kind.id, latest['value'], previous['value'])}"
            values = [r["value"] for r in rows]
            rng = (f"за {len(rows)} записей: {format_value(kind.id, min(values))} — "
                   f"{format_value(kind.id, max(values))}")

            row = ttk.Frame(card, style="Page.TFrame")
            row.pack(fill="x", pady=(6, 0))
            tk.Label(row, text=f"{line}\n{rng}", bg=colors["bg"], fg=colors["text"],
                     font=self.theme.font(9), justify="left", anchor="w").pack(
                side="left", fill="x", expand=True)
            ttk.Button(row, text="Удалить",
                       command=lambda mid=latest["id"]: self._delete_measure(mid)).pack(
                side="right")

        tk.Label(card, text="«Удалить» убирает последнюю запись этого вида.",
                 bg=colors["bg"], fg=colors["muted"], font=self.theme.font(8)).pack(
            anchor="w", pady=(6, 0))

    def _delete_measure(self, measurement_id):
        self.storage.delete_measurement(measurement_id)
        self.refresh()

    def _render_screenings(self):
        colors = self.theme.colors
        content = self.app.content
        profile = self.storage.load_profile()
        today = dt.date.today()
        entries = for_profile(content, profile, today,
                              last_done=self.storage.screening_last_done)

        card = ttk.Frame(self.scroll_inner, style="Page.TFrame")
        card.pack(fill="x")
        tk.Label(card, text="Обследования", bg=colors["bg"], fg=colors["text"],
                 font=self.theme.font(12, "bold")).pack(anchor="w")

        if not entries:
            tk.Label(card, text="Список пуст — укажите возраст в профиле, чтобы "
                                "показались подходящие обследования.",
                     bg=colors["bg"], fg=colors["muted"],
                     font=self.theme.font(9), justify="left").pack(anchor="w", pady=(4, 0))
        else:
            for screening, last, due in entries:
                block = ttk.Frame(card, style="Page.TFrame")
                block.pack(fill="x", pady=(8, 0))
                head_color = "#92400e" if due else colors["text"]
                tk.Label(block, text=screening.title, bg=colors["bg"], fg=head_color,
                         font=self.theme.font(10, "bold")).pack(anchor="w")
                tk.Label(block, text=screening.detail, bg=colors["bg"],
                         fg=colors["muted"], font=self.theme.font(9),
                         justify="left", wraplength=900).pack(anchor="w")

                if due and last is None:
                    status = "Не проходили — стоит запланировать"
                elif due:
                    status = f"Пора: последний раз {_fmt_date(last.isoformat())}"
                else:
                    status = f"Следующее: {_fmt_date(next_due(last, screening, today).isoformat())}"
                tk.Label(block, text=status, bg=colors["bg"], fg=colors["muted"],
                         font=self.theme.font(9)).pack(anchor="w")

                buttons = ttk.Frame(block, style="Page.TFrame")
                buttons.pack(anchor="w", pady=(2, 0))
                ttk.Button(buttons, text="Отмечено сегодня",
                           command=lambda s=screening: self._mark_screening(s)).pack(side="left")
                if last is not None:
                    ttk.Button(buttons, text="Сбросить",
                               command=lambda s=screening: self._clear_screening(s)).pack(
                        side="left", padx=(6, 0))

        tk.Label(card, text="Список ориентировочный — периодичность и необходимость "
                            "определяет врач.",
                 bg=colors["bg"], fg=colors["muted"], font=self.theme.font(8)).pack(
            anchor="w", pady=(10, 0))

    def _mark_screening(self, screening):
        self.storage.mark_screening(screening.id, dt.date.today())
        self.refresh()

    def _clear_screening(self, screening):
        self.storage.clear_screening(screening.id)
        self.refresh()
