import ast
import subprocess
import sys
from dataclasses import fields
from pathlib import Path

from longevity.content import Content

APP = Path(__file__).resolve().parent.parent / "app.py"


def _tree() -> ast.Module:
    return ast.parse(APP.read_text(encoding="utf-8"))


def _imported_modules() -> set[str]:
    modules = set()
    for node in ast.walk(_tree()):
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
    assert not (APP.parent / "knowledge_base.py").exists()


def test_app_imports_without_a_display_and_without_side_effects(tmp_path):
    """Смок-тест: app импортируется в подпроцессе и ничего при этом не трогает.

    Работает без DISPLAY: tkinter импортируется, окно не создаётся. Данные и
    база открываются в main(), поэтому импорт не должен создавать даже каталог
    пользовательских данных.
    """
    env = {"PATH": "/usr/bin:/bin", "XDG_DATA_HOME": str(tmp_path / "xdg"),
           "PYTHONPATH": str(APP.parent), "HOME": str(tmp_path / "home")}

    result = subprocess.run(
        [sys.executable, "-c", "import app; assert app.CONTENT is None"],
        cwd=APP.parent, env=env, capture_output=True,
    )

    assert result.returncode == 0, (result.stdout + result.stderr).decode()
    assert not (tmp_path / "xdg").exists(), "импорт создал каталог данных"


def _content_attribute_names() -> set[str]:
    """Имена, к которым app.py обращается как CONTENT.<что-то>."""
    used = set()
    for node in ast.walk(_tree()):
        if (isinstance(node, ast.Attribute)
                and isinstance(node.value, ast.Name)
                and node.value.id == "CONTENT"):
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

    assert used, "app.py вообще не обращается к CONTENT — тест потерял смысл"
    assert used <= known, f"нет таких полей у Content: {sorted(used - known)}"


def test_app_does_not_read_content_data_as_dictionaries():
    """CONTENT.tips[0]["title"] — след старого knowledge_base, а не датакласса."""
    offenders = []
    for node in ast.walk(_tree()):
        if not isinstance(node, ast.Subscript):
            continue
        if not (isinstance(node.slice, ast.Constant) and isinstance(node.slice.value, str)):
            continue
        if _rooted_at_content(node.value):
            offenders.append(ast.unparse(node))

    assert not offenders, f"словарный доступ к данным книги: {offenders}"


def _rooted_at_content(node: ast.AST) -> bool:
    while isinstance(node, (ast.Attribute, ast.Subscript, ast.Call)):
        node = node.value if not isinstance(node, ast.Call) else node.func
    return isinstance(node, ast.Name) and node.id == "CONTENT"
