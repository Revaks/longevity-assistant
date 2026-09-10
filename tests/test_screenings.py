"""Обследования: применимость по возрасту/полу, сроки."""

import datetime as dt

from longevity.content import Content
from longevity.plan import Profile
from longevity.screenings import for_profile, is_applicable, is_due, next_due


def _content():
    screenings = [
        {"id": "any", "title": "т", "detail": "т", "period_months": 12,
         "age_min": 18, "sex": None},
        {"id": "after40", "title": "т", "detail": "т", "period_months": 24,
         "age_min": 40, "sex": None},
        {"id": "women", "title": "т", "detail": "т", "period_months": 24,
         "age_min": 40, "sex": "ж"},
    ]
    return Content.build(
        tips=[], schedule=[], synonyms={},
        mind={"good": [], "limit": [], "menu": []},
        meta={"app_title": "т", "app_subtitle": "т", "disclaimer": "т",
              "categories": ["Питание"], "cat_colors": {"Питание": "#1"},
              "quick_questions": []},
        extras={"rotations": [], "focus": [], "screenings": screenings},
    )


def test_applicability_respects_age_and_sex():
    content = _content()
    young = Profile(age=30)
    ids = [s.id for s in content.screenings if is_applicable(s, young)]
    assert ids == ["any"]

    woman = Profile(age=50, sex="ж")
    woman_ids = [s.id for s in content.screenings if is_applicable(s, woman)]
    assert woman_ids == ["any", "after40", "women"]

    man = Profile(age=50, sex="м")
    man_ids = [s.id for s in content.screenings if is_applicable(s, man)]
    assert "women" not in man_ids

    unknown = Profile(age=50)
    assert any(is_applicable(s, unknown) for s in content.screenings if s.id == "women")


def test_due_and_next_date_follow_the_period():
    content = _content()
    any_screening = next(s for s in content.screenings if s.id == "any")
    today = dt.date(2026, 9, 9)

    assert is_due(None, any_screening, today)
    assert next_due(None, any_screening, today) == today

    recent = dt.date(2026, 6, 9)  # три месяца назад
    assert not is_due(recent, any_screening, today)
    assert next_due(recent, any_screening, today) == dt.date(2027, 6, 9)

    old = dt.date(2025, 8, 1)
    assert is_due(old, any_screening, today)


def test_list_puts_due_items_first():
    content = _content()
    today = dt.date(2026, 9, 9)
    last_done = {
        "any": today - dt.timedelta(days=30),  # не пора
        "after40": None,                        # пора
    }
    entries = for_profile(content, Profile(age=50, sex="м"), today,
                          last_done=lambda iid: last_done.get(iid))
    assert entries
    assert entries[0][0].id == "after40"
