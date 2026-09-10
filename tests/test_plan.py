"""План дня: ротация вариантов, скрытые и свои пункты, фокус недели."""

import datetime as dt

from longevity.content import Content, ScheduleItem
from longevity.plan import (
    Profile,
    apply_rotation,
    focus_for_week,
    focus_task_ids,
    iso_week,
    items_for_day,
    new_custom_id,
    parse_custom_items,
    parse_hidden,
    serialize_custom_items,
    serialize_hidden,
    variant_for,
)

MONDAY = dt.date(2026, 9, 7)  # понедельник


def _item(item_id, days=(0, 1, 2, 3, 4, 5, 6), anchor="allday", time=None):
    return ScheduleItem(id=item_id, title=item_id, detail="", cat="Питание",
                        days=tuple(days), anchor=anchor, time=time,
                        tips=(), requires={}, alt=None)


def _content(rotations=(), focus=()):
    schedule = [_item("fish_day")]
    return Content.build(
        tips=[], schedule=[_schedule_dict(s) for s in schedule], synonyms={},
        mind={"good": [], "limit": [], "menu": []}, meta=_meta(),
        extras={"rotations": list(rotations), "focus": list(focus), "screenings": []},
    )


def _schedule_dict(item):
    return {"id": item.id, "title": item.title, "detail": item.detail,
            "cat": item.cat, "days": list(item.days), "anchor": item.anchor,
            "time": item.time, "tips": [], "requires": {}, "alt": None}


def _meta():
    return {"app_title": "т", "app_subtitle": "т", "disclaimer": "т",
            "categories": ["Питание"], "cat_colors": {"Питание": "#1"},
            "quick_questions": []}


def _rotation(item_id="fish_day", variants=None):
    if variants is None:
        variants = [
            {"level": 0, "title": "Лёгкий", "detail": "д0"},
            {"level": 1, "title": "Средний", "detail": "д1"},
            {"level": 2, "title": "Сильный", "detail": "д2"},
        ]
    return {"item_id": item_id, "variants": variants}


def test_iso_week_is_stable_and_focus_cycles():
    content = _content(focus=[{"id": "f1", "title": "Фокус", "detail": "д",
                               "tasks": ["1", "2", "3"]}])
    assert iso_week(MONDAY) == iso_week(MONDAY + dt.timedelta(days=3))
    assert focus_for_week(content, MONDAY).id == "f1"
    later = MONDAY + dt.timedelta(weeks=len(content.focus))
    assert focus_for_week(content, later).id == focus_for_week(content, MONDAY).id


def test_variant_respects_activity_level_and_rotates_by_week():
    content = _content(rotations=[_rotation()])
    item = content.schedule[0]
    low = variant_for(content, item, MONDAY, Profile(activity=0))
    assert low.title == "Лёгкий"
    assert variant_for(content, item, MONDAY, Profile(activity=2)) is not None

    week1 = variant_for(content, item, MONDAY, Profile(activity=2))
    week2 = variant_for(content, item, MONDAY + dt.timedelta(weeks=1), Profile(activity=2))
    assert week1.title != week2.title


def test_deload_week_picks_lightest_variant():
    content = _content(rotations=[_rotation()])
    item = content.schedule[0]
    variant = variant_for(content, item, MONDAY, Profile(activity=2, deload=True))
    assert variant.title == "Лёгкий"


def test_rotation_changes_only_text_not_the_id():
    content = _content(rotations=[_rotation()])
    item = content.schedule[0]
    rotated = apply_rotation(content, item, MONDAY, Profile(activity=2))
    assert rotated.id == item.id
    assert rotated.days == item.days


def test_custom_items_round_trip_and_filter_by_weekday():
    content = _content()
    custom = [ScheduleItem(
        id=new_custom_id(), title="Дневник сна", detail="8 часов",
        cat=content.categories[0], days=(0,), anchor="clock", time="08:00",
        tips=(), requires={}, alt=None,
    )]
    parsed = parse_custom_items(serialize_custom_items(custom), content.categories)
    assert len(parsed) == 1
    assert parsed[0].title == "Дневник сна"

    monday_items = items_for_day(content, Profile(), parsed, MONDAY)
    assert any(it.title == "Дневник сна" for it in monday_items)
    tuesday_items = items_for_day(content, Profile(), parsed, MONDAY + dt.timedelta(days=1))
    assert not any(it.title == "Дневник сна" for it in tuesday_items)


def test_parse_custom_items_skips_broken_rows():
    categories = ["Питание"]
    broken = [
        {"id": "wrong:1", "title": "Плохой id", "days": [0], "anchor": "allday"},
        {"id": "custom:1", "title": "", "days": [0], "anchor": "allday"},
        {"id": "custom:2", "title": "Без дней", "days": [], "anchor": "allday"},
        {"id": "custom:3", "title": "Часы без времени", "days": [0], "anchor": "clock"},
        {"id": "custom:4", "title": "Хороший", "days": [1], "anchor": "allday"},
    ]
    import json
    items = parse_custom_items(json.dumps(broken, ensure_ascii=False), categories)
    assert len(items) == 1
    assert items[0].title == "Хороший"
    assert items[0].cat == "Питание"


def test_hidden_items_are_excluded_from_the_day():
    content = _content()
    all_items = items_for_day(content, Profile(), [], MONDAY)
    assert all_items
    hidden_id = all_items[0].id
    filtered = items_for_day(content, Profile(hidden=frozenset([hidden_id])), [], MONDAY)
    assert all(it.id != hidden_id for it in filtered)


def test_no_rotation_content_means_no_override():
    content = _content()
    item = content.schedule[0]
    assert variant_for(content, item, MONDAY, Profile()) is None
    assert apply_rotation(content, item, MONDAY, Profile()).title == item.title


def test_hidden_round_trip():
    ids = frozenset(["a", "b"])
    assert parse_hidden(serialize_hidden(ids)) == ids
    assert parse_hidden("не json") == frozenset()
    assert parse_hidden(None) == frozenset()


def test_focus_task_ids():
    content = _content(focus=[{"id": "f1", "title": "т", "detail": "д",
                               "tasks": ["а", "б", "в"]}])
    focus = content.focus[0]
    assert focus_task_ids(focus) == ("focus:f1:0", "focus:f1:1", "focus:f1:2")
    assert focus_task_ids(None) == ()
