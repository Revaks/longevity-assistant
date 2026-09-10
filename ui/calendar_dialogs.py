# -*- coding: utf-8 -*-
"""Диалоги календаря: профиль, пункты расписания, свои пункты, измерение.

Все окна — модальные ``Toplevel`` с ``grab_set``/``wait_window``. Функции
возвращают результат или ``None`` (отмена); состояние хранит вызывающий код
(``CalendarPage``), чтобы перерисовать план после сохранения.
"""

import re
import tkinter as tk
from dataclasses import replace
from tkinter import messagebox, ttk

from longevity.content import ScheduleItem
from longevity.measures import kind as measure_kind
from longevity.plan import new_custom_id

WEEKDAYS = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]

_TIME_RE = re.compile(r"^\d{1,2}:\d{2}$")

#: Пары «подпись — список id измерений» (для давления — два значения).
MEASURE_OPTIONS = (
    ("Вес", ("weight",)),
    ("Окружность талии", ("waist",)),
    ("Давление (сист. / диаст.)", ("bp_sys", "bp_dia")),
    ("Пульс", ("pulse",)),
    ("Тест 6-минутной ходьбы", ("walk6m",)),
    ("Сила хвата", ("grip",)),
)


class _Modal:
    """Обёртка модального окна: тело, кнопки, возврат результата."""

    def __init__(self, parent, title, width=460):
        self.top = tk.Toplevel(parent)
        self.top.title(title)
        self.top.transient(parent)
        self.top.resizable(False, False)
        self.body = ttk.Frame(self.top, padding=14)
        self.body.pack(fill="both", expand=True)
        self._buttons = ttk.Frame(self.top, padding=(14, 0, 14, 12))
        self._buttons.pack(fill="x")
        self.result = None
        self.top.bind("<Escape>", lambda _e: self.cancel())

    def add_ok_cancel(self, on_ok, ok_label="Сохранить"):
        ttk.Button(self._buttons, text="Отмена", command=self.cancel).pack(
            side="right", padx=(6, 0))
        ttk.Button(self._buttons, text=ok_label, command=on_ok).pack(side="right")

    def close(self, value=None):
        self.result = value
        self.top.destroy()

    def cancel(self):
        self.top.destroy()

    def wait(self):
        self.top.grab_set()
        self.top.wait_window()
        return self.result


def show_actions(parent, on_profile, on_items, on_measure):
    """Небольшой список действий календаря — аналог нижнего листа в Android."""
    dlg = _Modal(parent, "Календарь", width=320)
    for label, action in (("Профиль (возраст, пол, нагрузка)", on_profile),
                          ("Пункты расписания и свои пункты", on_items),
                          ("Добавить измерение в биодневник", on_measure)):
        ttk.Button(dlg.body, text=label, command=lambda a=action: (dlg.close(), a())).pack(
            fill="x", pady=2)
    dlg.wait()


def show_profile(parent, profile):
    """Профиль: возраст, пол, уровень активности, разгрузочная неделя."""
    dlg = _Modal(parent, "Профиль", width=420)

    ttk.Label(dlg.body, text="Возраст").pack(anchor="w", pady=(8, 2))
    age_var = tk.StringVar(value=str(profile.age) if profile.age is not None else "")
    ttk.Entry(dlg.body, textvariable=age_var).pack(fill="x")

    ttk.Label(dlg.body, text="Пол (для списка обследований)").pack(anchor="w", pady=(10, 2))
    sex_var = tk.StringVar(value=profile.sex or "")
    sex_row = ttk.Frame(dlg.body)
    sex_row.pack(anchor="w")
    for value, label in (("", "не указан"), ("м", "мужской"), ("ж", "женский")):
        ttk.Radiobutton(sex_row, text=label, variable=sex_var, value=value).pack(
            side="left", padx=(0, 10))

    ttk.Label(dlg.body, text="Уровень активности (подбирает варианты тренировок)").pack(
        anchor="w", pady=(10, 2))
    activity_var = tk.IntVar(value=profile.activity)
    for value, label in ((0, "Низкий — начинаю или щадящий режим"),
                         (1, "Средний"),
                         (2, "Высокий — регулярные тренировки")):
        ttk.Radiobutton(dlg.body, text=label, variable=activity_var, value=value).pack(
            anchor="w")

    deload_var = tk.BooleanVar(value=profile.deload)
    ttk.Checkbutton(dlg.body, text="Разгрузочная (лёгкая) неделя",
                    variable=deload_var).pack(anchor="w", pady=(10, 4))

    def on_ok():
        age_text = age_var.get().strip()
        age = int(age_text) if age_text.isdigit() and 1 <= int(age_text) <= 120 else None
        sex = sex_var.get() or None
        dlg.close(replace(profile, age=age, sex=sex, activity=activity_var.get(),
                          deload=deload_var.get()))

    dlg.add_ok_cancel(on_ok)
    return dlg.wait()


def show_items(parent, content, custom_items, hidden):
    """Скрытие пунктов расписания и управление своими пунктами.

    Возвращает пару (custom_items, hidden) или ``None`` при отмене.
    """
    dlg = _Modal(parent, "Пункты расписания", width=460)

    canvas = tk.Canvas(dlg.body, highlightthickness=0, height=380)
    scrollbar = ttk.Scrollbar(dlg.body, orient="vertical", command=canvas.yview)
    inner = ttk.Frame(canvas)
    inner.bind("<Configure>", lambda _e: canvas.configure(
        scrollregion=canvas.bbox("all")))
    canvas.create_window((0, 0), window=inner, anchor="nw")
    canvas.configure(yscrollcommand=scrollbar.set)
    canvas.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")

    ttk.Label(inner, text="Отметьте пункты, которые должны быть в календаре:").pack(
        anchor="w", pady=(0, 4))
    checkboxes = []
    for item in content.schedule:
        var = tk.BooleanVar(value=item.id not in hidden)
        ttk.Checkbutton(inner, text=item.title, variable=var).pack(anchor="w")
        checkboxes.append((item.id, var))

    ttk.Label(inner, text="Свои пункты:").pack(anchor="w", pady=(12, 4))
    custom = list(custom_items)

    def render_custom():
        for child in custom_list.winfo_children():
            child.destroy()
        if not custom:
            ttk.Label(custom_list, text="Пока нет. Добавьте свои — например, «Дневник сна 08:00».",
                      foreground="#6b7280").pack(anchor="w")
            return
        for item in custom:
            row = ttk.Frame(custom_list)
            row.pack(fill="x", pady=1)
            days = ", ".join(WEEKDAYS[d] for d in item.days)
            ttk.Label(row, text=f"• {item.title} ({days})").pack(side="left")
            ttk.Button(row, text="Удалить",
                       command=lambda i=item: (custom.remove(i), render_custom())).pack(
                side="right")

    custom_list = ttk.Frame(inner)
    custom_list.pack(fill="x")
    render_custom()

    def on_add():
        added = show_add_custom_item(parent, content)
        if added is not None:
            custom.append(added)
            render_custom()

    ttk.Button(inner, text="+ Добавить пункт", command=on_add).pack(anchor="w", pady=(6, 0))

    def on_ok():
        new_hidden = frozenset(item_id for item_id, var in checkboxes if not var.get())
        dlg.close((custom, new_hidden))

    dlg.add_ok_cancel(on_ok)
    return dlg.wait()


def show_add_custom_item(parent, content):
    """Новый свой пункт: название, деталь, время и дни недели."""
    dlg = _Modal(parent, "Свой пункт", width=420)

    ttk.Label(dlg.body, text="Название").pack(anchor="w", pady=(8, 2))
    title_var = tk.StringVar()
    ttk.Entry(dlg.body, textvariable=title_var).pack(fill="x")

    ttk.Label(dlg.body, text="Деталь (необязательно)").pack(anchor="w", pady=(8, 2))
    detail_var = tk.StringVar()
    ttk.Entry(dlg.body, textvariable=detail_var).pack(fill="x")

    ttk.Label(dlg.body, text="Время ЧЧ:ММ (пусто — весь день)").pack(anchor="w", pady=(8, 2))
    time_var = tk.StringVar()
    ttk.Entry(dlg.body, textvariable=time_var).pack(fill="x")

    ttk.Label(dlg.body, text="Дни недели:").pack(anchor="w", pady=(10, 2))
    day_vars = []
    days_row = ttk.Frame(dlg.body)
    days_row.pack(anchor="w")
    for index, name in enumerate(WEEKDAYS):
        var = tk.BooleanVar(value=False)
        ttk.Checkbutton(days_row, text=name, variable=var).pack(side="left")
        day_vars.append((index, var))

    def on_ok():
        name = title_var.get().strip()
        selected_days = [i for i, var in day_vars if var.get()]
        if not name or not selected_days:
            messagebox.showinfo("Свой пункт", "Укажите название и хотя бы один день недели.",
                                parent=dlg.top)
            return
        raw_time = time_var.get().strip()
        valid_time = bool(_TIME_RE.match(raw_time))
        dlg.close(ScheduleItem(
            id=new_custom_id(),
            title=name,
            detail=detail_var.get().strip(),
            cat=content.categories[0] if content.categories else "",
            days=tuple(sorted(selected_days)),
            anchor="clock" if valid_time else "allday",
            time=raw_time if valid_time else None,
            tips=(),
            requires={},
            alt=None,
        ))

    dlg.add_ok_cancel(on_ok, ok_label="Добавить")
    return dlg.wait()


def show_measure(parent):
    """Ввод измерения: выбор вида и значения (для давления — два)."""
    dlg = _Modal(parent, "Новое измерение", width=360)

    ttk.Label(dlg.body, text="Что измеряем?").pack(anchor="w", pady=(8, 4))
    option_var = tk.StringVar(value=MEASURE_OPTIONS[0][0])
    combo = ttk.Combobox(dlg.body, textvariable=option_var, state="readonly",
                         values=[label for label, _ in MEASURE_OPTIONS])
    combo.pack(fill="x")

    inputs_frame = ttk.Frame(dlg.body)
    inputs_frame.pack(fill="x", pady=(8, 0))
    entries = {}

    def rebuild(_event=None):
        for child in inputs_frame.winfo_children():
            child.destroy()
        entries.clear()
        kinds = next(kinds for label, kinds in MEASURE_OPTIONS if label == option_var.get())
        for kind_id in kinds:
            k = measure_kind(kind_id)
            ttk.Label(inputs_frame, text=f"{k.title} ({k.unit})").pack(anchor="w")
            var = tk.StringVar()
            ttk.Entry(inputs_frame, textvariable=var).pack(fill="x")
            entries[kind_id] = var

    rebuild()
    combo.bind("<<ComboboxSelected>>", rebuild)

    def on_ok():
        values = []
        for kind_id, var in entries.items():
            raw = var.get().strip().replace(",", ".")
            if not raw:
                continue
            try:
                value = float(raw)
            except ValueError:
                messagebox.showerror("Измерение", f"Значение «{raw}» — не число.", parent=dlg.top)
                return
            values.append((kind_id, value))
        if not values:
            messagebox.showinfo("Измерение", "Введите значение.", parent=dlg.top)
            return
        dlg.close(values)

    dlg.add_ok_cancel(on_ok, ok_label="Сохранить")
    return dlg.wait()
