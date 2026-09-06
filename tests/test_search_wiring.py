import ast
from pathlib import Path

APP = Path(__file__).resolve().parent.parent / "app.py"


def _defined_names() -> set[str]:
    tree = ast.parse(APP.read_text(encoding="utf-8"))
    return {n.name for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}


def test_app_has_no_private_search_implementation():
    """Поиск живёт в пакете; в интерфейсе не должно остаться своей копии."""
    leftovers = _defined_names() & {
        "normalize", "tokenize", "expand_query", "_word_match",
        "_count_hits", "score_tip", "search_tips",
    }

    assert not leftovers, f"в app.py осталась своя реализация поиска: {sorted(leftovers)}"


def test_app_imports_the_index():
    source = APP.read_text(encoding="utf-8")

    assert "SearchIndex" in source
    assert "STOPWORDS" not in source, "список стоп-слов переехал в longevity.text"


def test_knowledge_filter_narrows_results():
    """Регресс на находку №1: «витамин д» не должен выдавать всю базу.

    Индекс строится здесь напрямую: в приложении он создаётся внутри main(),
    и при простом импорте модуля был бы ещё не готов.
    """
    from longevity.content import load_content
    from longevity.search import SearchIndex

    content = load_content()
    hits = SearchIndex(content).search("витамин д")

    assert 0 < len(hits) < 20
    assert len(hits) < len(content.tips)


def test_both_screens_agree():
    """Одинаковый запрос обязан давать одинаковый порядок на обеих вкладках."""
    from longevity.content import load_content
    from longevity.search import SearchIndex

    index = SearchIndex(load_content())
    query = "омега-3"

    assistant = [h.tip.id for h in index.search(query, limit=5)]
    knowledge = [h.tip.id for h in index.search(query)][:5]

    assert assistant == knowledge
