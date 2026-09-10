"""extras.json: ротации, фокусы недель и обследования на настоящих данных."""

import datetime as dt

import pytest

from longevity.content import Content, ContentError, load_content
from longevity.plan import Profile, focus_for_week, items_for_day, variant_for


def test_real_data_loads_extras():
    content = load_content()

    assert content.rotations
    assert len(content.focus) >= 12
    assert len(content.screenings) >= 10

    schedule_ids = {item.id for item in content.schedule}
    assert set(content.rotations) <= schedule_ids
    assert all(fw.tasks and len(fw.tasks) >= 3 for fw in content.focus)
    assert all(s.period_months > 0 for s in content.screenings)


def test_focus_and_rotation_defined_for_any_day():
    content = load_content()
    day = dt.date(2026, 9, 9)

    assert focus_for_week(content, day) is not None
    aerobic = next(item for item in content.schedule if item.id == "train_aerobic")
    assert variant_for(content, aerobic, day, Profile(activity=1)) is not None


def test_plan_respects_hidden_and_custom_items():
    content = load_content()
    day = dt.date(2026, 9, 9)  # среда

    custom = [
        _custom_item(content, "Дневник сна", days=(day.weekday(),))
    ]
    profile = Profile(activity=2, hidden=frozenset(["sauna"]))
    items = items_for_day(content, profile, custom, day)

    assert all(item.id != "sauna" for item in items)
    assert any(item.title == "Дневник сна" for item in items)


def _custom_item(content, title, days):
    from longevity.plan import new_custom_id
    from longevity.content import ScheduleItem

    return ScheduleItem(
        id=new_custom_id(), title=title, detail="", cat=content.categories[0],
        days=tuple(days), anchor="clock", time="08:00", tips=(), requires={}, alt=None,
    )


def test_rotation_does_not_change_item_id():
    content = load_content()
    day = dt.date(2026, 9, 9)
    base = items_for_day(content, Profile(activity=2), [], day)
    rotated = items_for_day(content, Profile(activity=2), [], day)

    assert [item.id for item in base] == [item.id for item in rotated]


def test_extras_reject_unknown_rotation_target():
    with pytest.raises(ContentError, match="несуществующ"):
        Content.build(
            tips=[], schedule=[], synonyms={},
            mind={"good": [], "limit": [], "menu": []},
            meta=_meta(),
            extras={"rotations": [{"item_id": "нет-такого", "variants": [
                {"level": 0, "title": "т", "detail": "д"}]}],
                "focus": [], "screenings": []},
        )


def test_extras_reject_bad_sex():
    with pytest.raises(ContentError, match="пол"):
        Content.build(
            tips=[], schedule=[], synonyms={},
            mind={"good": [], "limit": [], "menu": []},
            meta=_meta(),
            extras={"rotations": [], "focus": [], "screenings": [
                {"id": "s", "title": "т", "detail": "т",
                 "period_months": 12, "age_min": 18, "sex": "х"}]},
        )


def _meta():
    return {"app_title": "т", "app_subtitle": "т", "disclaimer": "т",
            "categories": ["Питание"], "cat_colors": {"Питание": "#1"},
            "quick_questions": []}
