import pytest

from longevity.content import Content, ContentError, MenuDay, ScheduleItem, Tip, load_content


def test_loads_everything():
    content = load_content()

    assert len(content.tips) == 70
    assert len(content.schedule) == 22
    assert len(content.mind_good) == 10
    assert len(content.mind_limit) == 5
    assert len(content.menu) == 7
    assert len(content.synonyms) == 43
    assert len(content.quick_questions) == 8
    assert content.app_title == "Ассистент долголетия"


def test_returns_typed_objects():
    content = load_content()

    assert isinstance(content.tips[0], Tip)
    assert isinstance(content.schedule[0], ScheduleItem)
    assert isinstance(content.menu[0], MenuDay)
    assert isinstance(content.schedule[0].days, tuple)


def test_objects_are_immutable():
    from dataclasses import FrozenInstanceError

    content = load_content()

    with pytest.raises(FrozenInstanceError):
        content.tips[0].title = "другое"


def test_lookup_by_id():
    content = load_content()

    assert content.tip("zh06").title == "Ложиться спать около 23:00"
    with pytest.raises(KeyError):
        content.tip("нет-такого")


def test_content_is_cached():
    assert load_content() is load_content()


def test_rejects_duplicate_tip_ids():
    tips = [
        {"id": "a1", "cat": "Питание", "title": "т", "text": "т", "sched": "т",
         "source": "т", "tags": "т", "age_min": None, "rx": False},
        {"id": "a1", "cat": "Питание", "title": "д", "text": "д", "sched": "д",
         "source": "д", "tags": "д", "age_min": None, "rx": False},
    ]

    with pytest.raises(ContentError, match="дубл"):
        Content.build(tips=tips, schedule=[], synonyms={}, mind={"good": [], "limit": [], "menu": []},
                      meta=_meta())


def test_rejects_unknown_category():
    tips = [
        {"id": "a1", "cat": "Магия", "title": "т", "text": "т", "sched": "т",
         "source": "т", "tags": "т", "age_min": None, "rx": False},
    ]

    with pytest.raises(ContentError, match="категор"):
        Content.build(tips=tips, schedule=[], synonyms={}, mind={"good": [], "limit": [], "menu": []},
                      meta=_meta())


def test_rejects_empty_source():
    tips = [
        {"id": "a1", "cat": "Питание", "title": "т", "text": "т", "sched": "т",
         "source": "  ", "tags": "т", "age_min": None, "rx": False},
    ]

    with pytest.raises(ContentError, match="источник"):
        Content.build(tips=tips, schedule=[], synonyms={}, mind={"good": [], "limit": [], "menu": []},
                      meta=_meta())


def test_rejects_schedule_pointing_at_missing_tip():
    schedule = [
        {"id": "s1", "title": "т", "detail": "т", "cat": "Питание", "days": [0],
         "anchor": "allday", "time": None, "tips": ["нет-такого"]},
    ]

    with pytest.raises(ContentError, match="несуществующ"):
        Content.build(tips=[], schedule=schedule, synonyms={},
                      mind={"good": [], "limit": [], "menu": []}, meta=_meta())


def test_rejects_clock_item_without_time():
    schedule = [
        {"id": "s1", "title": "т", "detail": "т", "cat": "Питание", "days": [0],
         "anchor": "clock", "time": None, "tips": []},
    ]

    with pytest.raises(ContentError, match="врем"):
        Content.build(tips=[], schedule=schedule, synonyms={},
                      mind={"good": [], "limit": [], "menu": []}, meta=_meta())


def test_rejects_unknown_anchor():
    schedule = [
        {"id": "s1", "title": "т", "detail": "т", "cat": "Питание", "days": [0],
         "anchor": "когда-нибудь", "time": None, "tips": []},
    ]

    with pytest.raises(ContentError, match="anchor"):
        Content.build(tips=[], schedule=schedule, synonyms={},
                      mind={"good": [], "limit": [], "menu": []}, meta=_meta())


def _meta():
    return {
        "app_title": "т", "app_subtitle": "т", "disclaimer": "т",
        "categories": ["Образ жизни", "Питание", "Добавки", "Процедуры"],
        "cat_colors": {"Образ жизни": "#1", "Питание": "#2", "Добавки": "#3", "Процедуры": "#4"},
        "quick_questions": [],
    }
