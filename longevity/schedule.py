"""Порядок и подписи пунктов расписания на конкретный день.

Модуль намеренно не знает про Tkinter: и подпись времени, и ключ сортировки
считаются здесь, поэтому показ и порядок не могут разойтись между собой.
"""

import datetime as dt
import re

from .content import Content, ScheduleItem

_CLOCK_RE = re.compile(r"^(\d{1,2}):(\d{2})$")


def display_time(item: ScheduleItem) -> str:
    """Текст времени для пункта расписания: якорь заменил старую строку 'time'."""
    if item.anchor == "clock":
        return item.time
    if item.anchor == "morning":
        return "утро"
    return "весь день"


def _time_key(t: str) -> tuple[int, int, int]:
    """Ключ сортировки по подписи времени: часы идут первыми, «весь день» — последним."""
    m = _CLOCK_RE.match(t)
    if m:
        return (0, int(m.group(1)), int(m.group(2)))
    if t.startswith("утро"):
        return (0, 6, 0)
    return (1, 0, 0)


def sort_key(item: ScheduleItem) -> tuple:
    """Ключ сортировки пункта дня: время показа («часы» раньше «весь день»).

    Отдельная функция — ею же пользуется longevity/plan.py, чтобы свои пункты
    вставали в те же временные группы, что и базовые, а не отдельным списком.
    """
    return _time_key(display_time(item))


def get_today_plan(content: Content, day: dt.date) -> list[ScheduleItem]:
    """Пункты расписания на конкретную дату в порядке показа."""
    wd = day.weekday()
    items = [s for s in content.schedule if wd in s.days]
    return sorted(items, key=sort_key)
