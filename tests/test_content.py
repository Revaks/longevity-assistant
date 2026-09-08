import pytest

from longevity.content import Content, ContentError, MenuDay, ScheduleItem, Tip, load_content


def test_loads_everything():
    content = load_content()

    assert len(content.tips) == 82
    assert len(content.schedule) == 24
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


def test_rejects_duplicate_schedule_item_ids():
    schedule = [
        {"id": "s1", "title": "т", "detail": "т", "cat": "Питание", "days": [0],
         "anchor": "allday", "time": None, "tips": []},
        {"id": "s1", "title": "д", "detail": "д", "cat": "Питание", "days": [1],
         "anchor": "allday", "time": None, "tips": []},
    ]

    with pytest.raises(ContentError, match="дубл"):
        Content.build(tips=[], schedule=schedule, synonyms={},
                      mind={"good": [], "limit": [], "menu": []}, meta=_meta())


def test_rejects_time_on_item_with_non_clock_anchor():
    """Время у якорного пункта разошлось бы с тем, что показывает display_time."""
    schedule = [
        {"id": "s1", "title": "т", "detail": "т", "cat": "Питание", "days": [0],
         "anchor": "morning", "time": "07:00", "tips": []},
    ]

    with pytest.raises(ContentError, match="anchor=morning"):
        Content.build(tips=[], schedule=schedule, synonyms={},
                      mind={"good": [], "limit": [], "menu": []}, meta=_meta())


def test_rejects_requires_without_alternative():
    """Условие без альтернативы просто вычеркнуло бы пункт из чужого дня."""
    schedule = [
        {"id": "s1", "title": "т", "detail": "т", "cat": "Питание", "days": [0],
         "anchor": "allday", "time": None, "tips": [], "requires": {"gym": True}},
    ]

    with pytest.raises(ContentError, match="альтернатив"):
        Content.build(tips=[], schedule=schedule, synonyms={},
                      mind={"good": [], "limit": [], "menu": []}, meta=_meta())


# -- отсутствующие и неверного типа поля -------------------------------
def _tip(**overrides):
    tip = {"id": "a1", "cat": "Питание", "title": "т", "text": "т", "sched": "т",
           "source": "т", "tags": "т", "age_min": None, "rx": False}
    tip.update(overrides)
    return tip


def _build(tips=(), schedule=(), meta=None):
    return Content.build(tips=list(tips), schedule=list(schedule), synonyms={},
                         mind={"good": [], "limit": [], "menu": []},
                         meta=meta if meta is not None else _meta())


def test_missing_tip_field_names_the_tip_and_the_field():
    broken = _tip()
    del broken["source"]

    with pytest.raises(ContentError) as exc:
        _build(tips=[broken])

    assert "a1" in str(exc.value), "в сообщении должен быть совет"
    assert "source" in str(exc.value), "в сообщении должно быть поле"


def test_tip_without_id_is_named_by_position():
    broken = _tip()
    del broken["id"]

    with pytest.raises(ContentError, match="№1"):
        _build(tips=[broken])


def test_tip_field_of_wrong_type_is_rejected():
    with pytest.raises(ContentError, match="title"):
        _build(tips=[_tip(title=42)])


def test_rx_must_be_boolean_not_string():
    with pytest.raises(ContentError, match="rx"):
        _build(tips=[_tip(rx="да")])


def test_age_min_does_not_accept_boolean():
    """True — это int в Python, но не возраст."""
    with pytest.raises(ContentError, match="age_min"):
        _build(tips=[_tip(age_min=True)])


def test_missing_schedule_field_names_the_item_and_the_field():
    item = {"id": "s1", "title": "т", "detail": "т", "cat": "Питание",
            "days": [0], "anchor": "allday", "tips": []}

    with pytest.raises(ContentError) as exc:
        _build(schedule=[item])

    assert "s1" in str(exc.value)
    assert "time" in str(exc.value)


def test_missing_meta_key_is_reported_as_content_error():
    meta = _meta()
    del meta["disclaimer"]

    with pytest.raises(ContentError, match="disclaimer"):
        _build(meta=meta)


def test_tips_file_must_be_a_list():
    with pytest.raises(ContentError, match="tips.json"):
        Content.build(tips={"a1": {}}, schedule=[], synonyms={},
                      mind={"good": [], "limit": [], "menu": []}, meta=_meta())


def test_mind_group_with_missing_field_is_reported():
    with pytest.raises(ContentError, match="amount"):
        Content.build(tips=[], schedule=[], synonyms={},
                      mind={"good": [{"name": "Зелень", "note": "т"}],
                            "limit": [], "menu": []},
                      meta=_meta())


def _meta():
    return {
        "app_title": "т", "app_subtitle": "т", "disclaimer": "т",
        "categories": ["Образ жизни", "Питание", "Добавки", "Процедуры"],
        "cat_colors": {"Образ жизни": "#1", "Питание": "#2", "Добавки": "#3", "Процедуры": "#4"},
        "quick_questions": [],
    }
