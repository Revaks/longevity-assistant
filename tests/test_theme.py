from ui.theme import FONT_CANDIDATES, pick_family


def test_prefers_first_available_candidate():
    assert pick_family({"DejaVu Sans", "Noto Sans"}) == "Noto Sans"
    assert pick_family({"DejaVu Sans"}) == "DejaVu Sans"


def test_falls_back_when_nothing_matches():
    result = pick_family(set())

    assert isinstance(result, str) and result, "должно вернуться хоть какое-то семейство"


def test_candidates_cover_three_platforms():
    joined = " ".join(FONT_CANDIDATES)

    assert "Noto Sans" in joined          # Linux
    assert "Segoe UI" in joined           # Windows
    assert any(f in joined for f in ("Helvetica Neue", "SF Pro Text"))  # macOS


def test_no_emoji_in_ui_sources():
    """Эмодзи из интерфейса убраны: на целевых машинах шрифта для них может не быть."""
    from pathlib import Path

    ui = Path(__file__).resolve().parent.parent / "ui"
    bad = []
    for path in ui.glob("*.py"):
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if any(ord(ch) > 0x1F000 for ch in line):
                bad.append(f"{path.name}:{n}")

    assert not bad, f"эмодзи в интерфейсе: {bad}"
