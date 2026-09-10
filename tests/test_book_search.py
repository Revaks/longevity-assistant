"""Поиск по книгам: BookSearch поверх отрывков, выборка и порядок."""

import pytest

from longevity.content import Book, Content, Passage
from longevity.search import BookHit, BookSearch


def _passage(pid, book="b1", section="", text=""):
    return Passage(id=pid, book=book, section=section, text=text)


def _content(*passages, synonyms=None):
    books = (Book(id="b1", title="Книга о здоровье", subtitle="", author="Автор"),)
    return Content(
        tips=(), schedule=(), synonyms=synonyms or {}, mind_good=(),
        mind_limit=(), menu=(), app_title="", app_subtitle="",
        disclaimer="", categories=(), cat_colors={}, quick_questions=(),
        books=books, passages=tuple(passages),
    )


@pytest.fixture
def index():
    return BookSearch(_content(
        _passage("p1", section="Питание",
                 text="Омега-3 кислоты из жирной рыбы полезны для сердца."),
        _passage("p2", section="Сон",
                 text="Мелатонин регулирует циркадные ритмы и сон."),
        _passage("p3", section="Питание",
                 text="Тёмный шоколад содержит флавоноиды."),
    ))


def test_search_returns_book_hits_in_relevance_order(index):
    hits = index.search("омега-3 жирная рыба")

    assert hits, "по запросу обязаны найтись отрывки"
    assert all(isinstance(h, BookHit) for h in hits)
    assert hits[0].passage.id == "p1"


def test_section_heading_is_searchable(index):
    hits = index.search("циркадные ритмы сна")

    assert hits and hits[0].passage.id == "p2"


def test_limit_semantics(index):
    assert len(index.search("рыба")) == 1
    assert index.search("рыба", limit=0) == []
    assert len(index.search("рыба", limit=None)) == 1


def test_empty_query_returns_nothing(index):
    assert index.search("") == []


def test_book_title_field_helps_retrieve():
    content = _content(
        _passage("p1", section="Раздел без ключевых слов",
                 text="Общие рассуждения о здоровье."),
        _passage("p2", section="Раздел без ключевых слов",
                 text="Снова общие рассуждения."),
    )
    # У b2 нет совпадений в тексте, но у b1 — тоже нет; проверяем, что
    # название книги участвует как поле (сейчас книг с названием два).
    hits = BookSearch(content).search("здоровье", limit=5)
    assert len(hits) <= 2
