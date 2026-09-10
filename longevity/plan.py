"""Профиль, свои пункты, ротация вариантов и фокус недели.

Чистая логика календаря без Tkinter: здесь считаются пункты конкретного дня
с учётом профиля (скрытые и свои пункты, ротация вариантов по неделям) и тема
недели («фокус»). Всё детерминированно — id пунктов не меняются, поэтому
отметки выполнения не сбиваются при смене недели или уровня активности.
"""

import datetime as dt
import json
import uuid
from dataclasses import dataclass, replace

from .content import Content, ScheduleItem
from .schedule import sort_key

#: Префикс id для своих пунктов пользователя.
CUSTOM_PREFIX = "custom:"

_MAX_CUSTOM_ITEMS = 50
_ANCHORS = {"clock", "morning", "allday"}


@dataclass(frozen=True)
class Profile:
    """Настройки пользователя, влияющие на календарь.

    ``activity`` — уровень активности: 0 низкий, 1 средний, 2 высокий (им
    выбираются варианты ротации). ``hidden`` — id скрытых пунктов расписания.
    """

    age: int | None = None
    sex: str | None = None
    activity: int = 1
    deload: bool = False
    hidden: frozenset[str] = frozenset()


def iso_week(day: dt.date) -> int:
    """Номер ISO-недели — по нему чередуются варианты и тема недели."""
    return day.isocalendar()[1]


def focus_for_week(content: Content, day: dt.date):
    """Тема недели: детерминированно по номеру недели (или None, если тем нет)."""
    if not content.focus:
        return None
    return content.focus[(iso_week(day) - 1) % len(content.focus)]


def focus_task_ids(focus) -> tuple[str, ...]:
    """Идентификаторы заданий фокуса — по ним хранятся отметки выполнения."""
    if focus is None:
        return ()
    return tuple(f"focus:{focus.id}:{i}" for i in range(len(focus.tasks)))


def variant_for(content: Content, item: ScheduleItem, day: dt.date,
                profile: Profile):
    """Вариант пункта: доступные уровню активности, чередуются по ISO-неделям."""
    variants = content.rotations.get(item.id)
    if not variants:
        return None
    allowed = [v for v in variants if v.level <= profile.activity]
    pool = allowed or list(variants)
    if profile.deload:
        return min(pool, key=lambda v: v.level)
    return pool[(iso_week(day) - 1) % len(pool)]


def apply_rotation(content: Content, item: ScheduleItem, day: dt.date,
                   profile: Profile) -> ScheduleItem:
    """Пункт с подставленным вариантом ротации; id и дни недели не меняются."""
    variant = variant_for(content, item, day, profile)
    if variant is None:
        return item
    return replace(item, title=variant.title, detail=variant.detail)


def items_for_day(content: Content, profile: Profile, custom_items: list[ScheduleItem],
                  day: dt.date) -> list[ScheduleItem]:
    """Пункты дня: базовое расписание (без скрытых) плюс свои пункты, с ротацией."""
    from .schedule import get_today_plan

    result = []
    for item in get_today_plan(content, day):
        if item.id in profile.hidden:
            continue
        result.append(apply_rotation(content, item, day, profile))

    weekday = day.weekday()  # Пн=0..Вс=6, как в days
    for item in custom_items:
        if weekday not in item.days or item.id in profile.hidden:
            continue
        result.append(apply_rotation(content, item, day, profile))

    # Стабильная сортировка по времени показа: порядок базовых пунктов
    # (schedule.json) не меняется, свои пункты встают в свою временную группу.
    return sorted(result, key=sort_key)


def item_ids_for_day(content: Content, profile: Profile,
                     custom_items: list[ScheduleItem], day: dt.date) -> frozenset[str]:
    """Идентификаторы пунктов дня — для подсчёта прогресса и серий."""
    return frozenset(item.id for item in items_for_day(content, profile, custom_items, day))


# ---------------------------------------------------------------------- свои пункты

def new_custom_id() -> str:
    """Новый идентификатор своего пункта."""
    return CUSTOM_PREFIX + uuid.uuid4().hex[:8]


def parse_custom_items(json_str, categories: list[str]) -> list[ScheduleItem]:
    """Разбор своих пунктов из профиля (JSON-массив). Повреждённые записи пропускаются."""
    if not json_str:
        return []
    try:
        raw = json.loads(json_str)
    except ValueError:
        return []
    if not isinstance(raw, list):
        return []

    result: list[ScheduleItem] = []
    for entry in raw[:_MAX_CUSTOM_ITEMS]:
        if not isinstance(entry, dict):
            continue
        item_id = entry.get("id")
        if not isinstance(item_id, str) or not item_id.startswith(CUSTOM_PREFIX):
            continue
        title = entry.get("title")
        if not isinstance(title, str) or not title.strip():
            continue
        anchor = entry.get("anchor")
        if anchor not in _ANCHORS:
            anchor = "allday"
        time = None
        if anchor == "clock":
            raw_time = entry.get("time")
            if isinstance(raw_time, str) and raw_time.strip():
                time = raw_time.strip()
            else:
                continue  # clock-пункт без времени не берём
        raw_days = entry.get("days")
        if not isinstance(raw_days, list):
            continue
        days = [d for d in raw_days
                if isinstance(d, int) and not isinstance(d, bool) and 0 <= d <= 6]
        if not days:
            continue
        cat = entry.get("cat")
        if cat not in categories:
            cat = categories[0] if categories else ""
        detail = entry.get("detail")
        result.append(ScheduleItem(
            id=item_id,
            title=title.strip(),
            detail=detail.strip() if isinstance(detail, str) else "",
            cat=cat,
            days=tuple(sorted(set(days))),
            anchor=anchor,
            time=time,
            tips=(),
            requires={},
            alt=None,
        ))
    return result


def serialize_custom_items(items: list[ScheduleItem]) -> str:
    """Сериализация своих пунктов для хранения в профиле."""
    return json.dumps([
        {
            "id": item.id,
            "title": item.title,
            "detail": item.detail,
            "cat": item.cat,
            "days": list(item.days),
            "anchor": item.anchor,
            "time": item.time or "",
        }
        for item in items
    ], ensure_ascii=False)


def parse_hidden(json_str) -> frozenset[str]:
    """Скрытые пункты из профиля (JSON-массив id). Повреждённые данные — пусто."""
    if not json_str:
        return frozenset()
    try:
        raw = json.loads(json_str)
    except ValueError:
        return frozenset()
    if not isinstance(raw, list):
        return frozenset()
    return frozenset(x for x in raw if isinstance(x, str) and x)


def serialize_hidden(ids) -> str:
    """Сериализация скрытых пунктов для хранения в профиле."""
    return json.dumps(sorted(ids), ensure_ascii=False)
