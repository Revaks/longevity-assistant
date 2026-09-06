import ast
from pathlib import Path

APP = Path(__file__).resolve().parent.parent / "app.py"


def _imported_modules() -> set[str]:
    tree = ast.parse(APP.read_text(encoding="utf-8"))
    modules = set()
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
    assert not (APP.parent / "knowledge_base.py").exists()


def test_app_has_no_dict_access_to_tips():
    """Датаклассы читаются через точку: tip['title'] после переезда — ошибка."""
    source = APP.read_text(encoding="utf-8")

    for pattern in ('tip["', "tip['", 'it["', "it['", 'kb.'):
        assert pattern not in source, f"остался словарный доступ: {pattern}"
