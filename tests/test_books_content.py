"""books.json: чтение, целостность и Content.books/passages."""

import pytest

from longevity.content import Content, ContentError, load_content

META = {
    "app_title": "", "app_subtitle": "", "disclaimer": "",
    "categories": ["A"], "cat_colors": {}, "quick_questions": [],
}

GOOD = {
    "books": [
        {"id": "b1", "title": "Книга первая", "subtitle": "подзаголовок",
         "author": "Автор"},
    ],
    "passages": [
        {"id": "b1:0001", "book": "b1", "section": "Глава 1", "text": "Текст."},
    ],
}


def _content(books_raw):
    return Content.build(
        tips=[], schedule=[], synonyms={},
        mind={"good": [], "limit": [], "menu": []}, meta=META,
        books=books_raw,
    )


def test_books_and_passages_load_from_data_files():
    content = load_content()

    assert len(content.books) == 3
    assert len(content.passages) >= 800
    ids = {p.id for p in content.passages}
    assert len(ids) == len(content.passages), "id отрывков должны быть уникальны"
    book_ids = {b.id for b in content.books}
    assert {p.book for p in content.passages} <= book_ids


def test_every_passage_has_text_and_section_shape():
    for passage in load_content().passages:
        assert passage.text.strip()
        assert isinstance(passage.section, str)


def test_book_lookup_helpers():
    content = _content(GOOD)

    assert content.book("b1").title == "Книга первая"
    assert content.passage("b1:0001").section == "Глава 1"
    with pytest.raises(KeyError):
        content.book("нет")
    with pytest.raises(KeyError):
        content.passage("нет")


def test_empty_books_file_is_allowed():
    content = _content({"books": [], "passages": []})

    assert content.books == ()
    assert content.passages == ()


def test_duplicate_book_id_rejected():
    raw = {
        "books": [dict(GOOD["books"][0]), dict(GOOD["books"][0])],
        "passages": [],
    }
    with pytest.raises(ContentError, match="дубл"):
        _content(raw)


def test_duplicate_passage_id_rejected():
    raw = {"books": GOOD["books"],
           "passages": [GOOD["passages"][0], GOOD["passages"][0]]}
    with pytest.raises(ContentError, match="дубл"):
        _content(raw)


def test_passage_referencing_missing_book_rejected():
    raw = {"books": GOOD["books"], "passages": [
        {"id": "x:1", "book": "no-such-book", "section": "", "text": "текст"}]}
    with pytest.raises(ContentError, match="несуществующ"):
        _content(raw)


def test_empty_passage_text_rejected():
    raw = {"books": GOOD["books"], "passages": [
        {"id": "b1:0002", "book": "b1", "section": "", "text": "  "}]}
    with pytest.raises(ContentError, match="пустой"):
        _content(raw)


def test_books_root_must_be_object():
    with pytest.raises(ContentError, match="объект"):
        _content(["not", "a", "dict"])
