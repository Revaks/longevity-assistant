from pathlib import Path

README = Path(__file__).resolve().parent.parent / "README.md"


def test_documents_tk_installation_for_every_platform():
    text = README.read_text(encoding="utf-8")

    assert "pacman -S tk" in text
    assert "apt install python3-tk" in text
    assert "dnf install python3-tkinter" in text
    assert "brew install python-tk" in text
    assert "libtk8.6.so" in text, "самая частая ошибка должна быть названа прямо"


def test_documents_where_user_data_lives():
    text = README.read_text(encoding="utf-8")

    assert "XDG_DATA_HOME" in text
    assert "Application Support" in text
    assert "LOCALAPPDATA" in text


def test_documents_architecture():
    text = README.read_text(encoding="utf-8")

    for module in ("longevity/content.py", "longevity/storage.py", "longevity/paths.py"):
        assert module in text


def test_states_zero_dependencies():
    text = README.read_text(encoding="utf-8").lower()

    assert "стандартной библиотеки" in text or "зависимостей нет" in text


def test_keeps_the_disclaimer():
    text = README.read_text(encoding="utf-8")

    assert "не заменяет консультацию врача" in text
