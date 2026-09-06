from pathlib import Path

import pytest

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


def test_theme_loads_icons():
    tk = pytest.importorskip("tkinter")
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
