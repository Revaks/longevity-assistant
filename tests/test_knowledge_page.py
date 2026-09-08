"""Вкладка «База знаний»: поиск проверяется на самой странице.

Главный регресс фазы — «витамин д» выдавал все 70 советов — был закрыт
переходом на поисковый индекс, но проверялся только на индексе напрямую.
Финальное ревью вернуло подстрочный фильтр прямо внутрь
KnowledgePage.refresh_list, страница снова показала всю базу, и все тесты
остались зелёными. Эти тесты смотрят на то, что реально попало в таблицу.
"""

from types import SimpleNamespace

import pytest

QUERY = "витамин д"


def _make_page(root):
    from longevity.content import load_content
    from longevity.search import SearchIndex
    from ui.knowledge_page import KnowledgePage
    from ui.theme import Theme

    content = load_content()
    app = SimpleNamespace(content=content, index=SearchIndex(content),
                          theme=Theme(root), storage=None)
    return KnowledgePage(root, app)


@pytest.fixture
def page(tk):
    root = tk.Tk()
    root.withdraw()
    yield _make_page(root)
    root.destroy()


def _shown(page):
    """Идентификаторы советов в том порядке, в каком они в таблице."""
    return list(page.tree.get_children())


def test_search_shows_a_handful_not_the_whole_base(page):
    page.search_var.set(QUERY)

    shown = _shown(page)

    assert len(shown) < len(page.app.content.tips), \
        f"запрос «{QUERY}» показал всю базу: {len(shown)} из {len(page.app.content.tips)}"
    assert 5 <= len(shown) <= 15, \
        f"ожидалась горстка советов (около девяти), показано {len(shown)}"
    assert page.count_label.cget("text") == f"Найдено: {len(shown)}"


def test_search_shows_exactly_what_the_index_ranked(page):
    """Страница ничего не досыпает и не отбрасывает — показывает выдачу индекса."""
    page.search_var.set(QUERY)

    assert _shown(page) == [hit.tip.id for hit in page.app.index.search(QUERY)]


def test_empty_query_shows_everything(page):
    page.search_var.set(QUERY)
    assert len(_shown(page)) < len(page.app.content.tips)

    page.search_var.set("")

    assert _shown(page) == [tip.id for tip in page.app.content.tips]
    assert len(_shown(page)) == len(page.app.content.tips)


def test_category_filter_applies_after_ranking(page):
    """Категория сужает уже отранжированную выдачу, а не заменяет её.

    Порядок обязан остаться поисковым: если фильтр применить до
    ранжирования (или вместо него), в таблице окажется список в порядке
    базы, а не по релевантности.
    """
    ranked = [hit.tip for hit in page.app.index.search(QUERY)]
    category = ranked[0].cat
    expected = [tip.id for tip in ranked if tip.cat == category]
    assert 0 < len(expected) < len(ranked), "нужна категория, которая реально сужает выдачу"

    page.search_var.set(QUERY)
    page.cat_var.set(category)
    page.refresh_list()

    assert _shown(page) == expected


def test_reset_returns_the_whole_base(page):
    page.search_var.set(QUERY)
    page.cat_var.set("Добавки")
    page.refresh_list()

    page.reset_filter()

    assert page.search_var.get() == ""
    assert page.cat_var.get() == "Все категории"
    assert len(_shown(page)) == len(page.app.content.tips)


def test_books_tab_lists_everything_without_a_query(page):
    """Вкладка «Книги» не должна выглядеть пустой: без запроса — все отрывки."""
    rows = list(page.books_tree.get_children())

    assert len(rows) == len(page.app.content.passages), \
        f"ожидались все отрывки книг, показано {len(rows)}"


def test_books_tab_search_narrows_results(page):
    from ui.rag import BOOKS_PAGE_LIMIT

    page.books_var.set("мелатонин")

    rows = list(page.books_tree.get_children())
    assert 0 < len(rows) <= BOOKS_PAGE_LIMIT
    assert page.books_count.cget("text").startswith("Найдено:")


def test_books_tab_selection_shows_passage_text(page):
    page.books_var.set("мелатонин")
    sel = page.books_tree.selection()
    page.books_tree.selection_set(page.books_tree.get_children()[0])
    page.on_book_select()

    text = page.book_detail.get("1.0", "end")
    assert len(text.strip()) > 100, "в панели деталей должен быть текст отрывка"
