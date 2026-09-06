from pathlib import Path

ICONS = Path(__file__).resolve().parent.parent / "longevity" / "data" / "icons"
NAMES = ("calendar", "nutrition", "knowledge", "assistant", "note", "clock")


def test_every_icon_exists_in_both_sizes():
    for name in NAMES:
        for size in (16, 32):
            path = ICONS / f"{name}-{size}.png"
            assert path.is_file(), f"нет иконки {path.name}"


def test_icons_are_real_pngs():
    for path in ICONS.glob("*.png"):
        assert path.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n", f"{path.name} не PNG"
        assert path.stat().st_size < 8192, f"{path.name} подозрительно велик"


def test_generator_is_committed():
    assert (Path(__file__).resolve().parent.parent / "tools" / "generate_icons.py").is_file(), (
        "генератор должен остаться в репозитории, чтобы иконки можно было перерисовать")


def test_theme_loads_icons(tk):
    from ui.theme import Theme

    root = tk.Tk()
    root.withdraw()
    try:
        theme = Theme(root)
        icon = theme.icon("calendar", 16)
        assert icon.width() == 16 and icon.height() == 16
        assert theme.icon("calendar", 16) is icon, "иконки должны кэшироваться по ссылке"
    finally:
        root.destroy()


def test_note_light_icon_exists_in_both_sizes():
    """Светлый вариант заметки — для тёмного фона шапки "сегодня" (см. ниже)."""
    for size in (16, 32):
        path = ICONS / f"note-light-{size}.png"
        assert path.is_file(), f"нет иконки {path.name}"


def test_note_icon_contrast_meets_wcag_aa():
    """Иконка заметки обязана быть различима на всех трёх фонах шапки дня.

    Раньше вся шапка красилась одним и тем же тёмным цветом иконки — на фоне
    обычного и выбранного дня (светлые) это давало отличный контраст, но на
    фоне "сегодня" (тёмный бирюзовый PALETTE["accent"]) контраст падал до
    2.68:1 — ниже порога WCAG AA для нетекстовой графики (3:1). CalendarPage
    выбирает между "note" (тёмная, для обычного/выбранного дня) и
    "note-light" (светлая, для "сегодня") — этот тест считает контраст по
    формуле WCAG для обеих пар, а не оценивает на глаз, поэтому будущая
    смена палитры не сможет тихо всё сломать.
    """
    from ui.calendar_page import CalendarPage
    from ui.theme import PALETTE, contrast_ratio

    dark_icon = PALETTE["sidebar"]   # цвет иконки "note"
    light_icon = PALETTE["card"]     # цвет иконки "note-light"

    cases = [
        ("note на обычном дне", dark_icon, CalendarPage.HEADER_BG_DEFAULT),
        ("note на выбранном дне", dark_icon, CalendarPage.HEADER_BG_SELECTED),
        ("note-light на «сегодня»", light_icon, PALETTE["accent"]),
    ]
    for label, icon_color, bg in cases:
        ratio = contrast_ratio(icon_color, bg)
        assert ratio >= 3.0, f"{label}: контраст {ratio:.2f}:1 ниже порога WCAG AA (3:1)"
