import ast
import subprocess
import sys
from dataclasses import fields
from pathlib import Path

from longevity.content import Content

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "app.py"
UI_DIR = ROOT / "ui"
UI_FILES = sorted(UI_DIR.glob("*.py"))


def _trees():
    return [ast.parse(p.read_text(encoding="utf-8")) for p in UI_FILES]


def _imported_modules() -> set[str]:
    """Модули, которые импортирует интерфейс (сейчас — пакет ui/, раньше был app.py)."""
    modules = set()
    for tree in _trees():
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                modules.add(node.module)
    return modules


def test_app_no_longer_imports_knowledge_base():
    assert "knowledge_base" not in _imported_modules()


def test_app_uses_the_package():
    modules = _imported_modules()

    assert any(m.startswith("longevity") for m in modules)


def test_knowledge_base_is_gone():
    assert not (ROOT / "knowledge_base.py").exists()


def test_app_imports_without_a_display_and_without_side_effects(tmp_path):
    """Смок-тест: app импортируется в подпроцессе и ничего при этом не трогает.

    Работает без DISPLAY: интерфейс (а с ним и tkinter) грузится только
    внутри main(), поэтому обычный импорт app.py не должен ни поднимать
    tkinter, ни создавать каталог пользовательских данных — данные и база
    открываются только при вызове main().
    """
    env = {"PATH": "/usr/bin:/bin", "XDG_DATA_HOME": str(tmp_path / "xdg"),
           "PYTHONPATH": str(APP.parent), "HOME": str(tmp_path / "home")}

    result = subprocess.run(
        [sys.executable, "-c", "import app; import sys; "
                                "assert 'tkinter' not in sys.modules"],
        cwd=APP.parent, env=env, capture_output=True,
    )

    assert result.returncode == 0, (result.stdout + result.stderr).decode()
    assert not (tmp_path / "xdg").exists(), "импорт создал каталог данных"


def _content_attribute_names() -> set[str]:
    """Имена, к которым интерфейс обращается как <...>.content.<что-то>.

    До переезда в ui/ единый объект данных книги лежал в модульной переменной
    CONTENT и являлся app.py; страницы обращались к ней как CONTENT.<attr>.
    Теперь она передаётся через приложение (self.app.content в страницах,
    self.content в самом LongevityApp) — синтаксически это всегда атрибут,
    у которого непосредственный родитель — атрибут с именем content.
    """
    used = set()
    for tree in _trees():
        for node in ast.walk(tree):
            if (isinstance(node, ast.Attribute)
                    and isinstance(node.value, ast.Attribute)
                    and node.value.attr == "content"):
                used.add(node.attr)
    return used


def test_every_content_attribute_used_by_app_exists():
    """Опечатка или переезд поля Content ловится без запуска Tk.

    Прежний тест искал в исходнике три литерала (tip[", it[", kb.) и
    отключался целиком от переименования переменной цикла. Этот смотрит на
    синтаксическое дерево и от имён переменных не зависит.
    """
    known = {f.name for f in fields(Content)}
    known |= {name for name, value in vars(Content).items()
              if callable(value) and not name.startswith("_")}

    used = _content_attribute_names()

    assert used, "интерфейс вообще не обращается к content — тест потерял смысл"
    assert used <= known, f"нет таких полей у Content: {sorted(used - known)}"


def test_app_does_not_read_content_data_as_dictionaries():
    """content.tips[0]["title"] — след старого knowledge_base, а не датакласса."""
    offenders = []
    for tree in _trees():
        for node in ast.walk(tree):
            if not isinstance(node, ast.Subscript):
                continue
            if not (isinstance(node.slice, ast.Constant) and isinstance(node.slice.value, str)):
                continue
            if _rooted_at_content(node.value):
                offenders.append(ast.unparse(node))

    assert not offenders, f"словарный доступ к данным книги: {offenders}"


def _rooted_at_content(node: ast.AST) -> bool:
    while isinstance(node, (ast.Attribute, ast.Subscript, ast.Call)):
        if isinstance(node, ast.Attribute) and node.attr == "content":
            return True
        node = node.value if not isinstance(node, ast.Call) else node.func
    return False
