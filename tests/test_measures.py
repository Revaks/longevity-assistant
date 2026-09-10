"""Форматирование измерений биодневника."""

from longevity.measures import delta, format_value, kind


def test_kind_lookup():
    assert kind("weight").unit == "кг"
    assert kind("unknown") is None


def test_format_adds_unit_and_trims_zeros():
    assert format_value("weight", 72.5) == "72.5 кг"
    assert format_value("weight", 80.0) == "80 кг"
    assert format_value("bp_sys", 120.0) == "120 мм рт.ст."
    assert format_value("unknown_kind", 72.0) == "72"


def test_delta_shows_sign_and_unit():
    assert delta("weight", 72.9, 72.5) == "+0.4 кг"
    assert delta("weight", 71.3, 72.5) == "−1.2 кг"
    assert delta("weight", 72.5, 72.5) == "0.0 кг"
