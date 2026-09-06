import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SEARCH_CONSUMERS = sorted((ROOT / "ui").glob("*.py")) + [ROOT / "longevity" / "__main__.py"]


def _defined_names() -> set[str]:
    names = set()
    for path in SEARCH_CONSUMERS:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        names |= {n.name for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
    return names


def _combined_source() -> str:
    return "\n".join(p.read_text(encoding="utf-8") for p in SEARCH_CONSUMERS)


def test_app_has_no_private_search_implementation():
    """Поиск живёт в пакете; в интерфейсе не должно остаться своей копии."""
    leftovers = _defined_names() & {
        "normalize", "tokenize", "expand_query", "_word_match",
        "_count_hits", "score_tip", "search_tips",
    }

    assert not leftovers, f"в интерфейсе осталась своя реализация поиска: {sorted(leftovers)}"


def test_app_imports_the_index():
    source = _combined_source()

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
