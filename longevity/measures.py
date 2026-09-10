"""Виды измерений биодневника с единицами и форматированием."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Kind:
    id: str
    title: str
    unit: str


KINDS = (
    Kind("weight", "Вес", "кг"),
    Kind("waist", "Окружность талии", "см"),
    Kind("bp_sys", "Давление систолическое", "мм рт.ст."),
    Kind("bp_dia", "Давление диастолическое", "мм рт.ст."),
    Kind("pulse", "Пульс", "уд/мин"),
    Kind("walk6m", "Тест 6-минутной ходьбы", "м"),
    Kind("grip", "Сила хвата", "кг"),
)


def kind(kind_id: str) -> Kind | None:
    for k in KINDS:
        if k.id == kind_id:
            return k
    return None


def format_value(kind_id: str, value: float) -> str:
    """Текст значения с единицей: «72.5 кг», «80 кг»."""
    k = kind(kind_id)
    unit = k.unit if k else ""
    if value == int(value):
        number = str(int(value))
    else:
        number = f"{value:.1f}"
    return f"{number} {unit}".strip() if unit else number


def delta(kind_id: str, current: float, previous: float) -> str:
    """Изменение относительно предыдущего: «+0.4 кг», «−1.2 кг» или «0.0 кг»."""
    diff = current - previous
    if diff > 0.049:
        sign = "+"
    elif diff < -0.049:
        sign = "−"
    else:
        sign = ""
    k = kind(kind_id)
    unit = k.unit if k else ""
    return f"{sign}{abs(diff):.1f} {unit}".strip()
