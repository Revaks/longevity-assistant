"""Векторный кэш отрывков: хэш корпуса, косинус, хранение в Storage."""

import math

import pytest

from longevity.content import Book, Content, Passage
from longevity.storage import Storage
from longevity.vectors import BookVectors, corpus_hash, cosine, model_key, rrf_fuse, top_k


def _passage(pid, text):
    return Passage(id=pid, book="b1", section="", text=text)


def _content(*passages):
    books = (Book(id="b1", title="Книга", subtitle="", author="Автор"),)
    return Content(
        tips=(), schedule=(), synonyms={}, mind_good=(), mind_limit=(),
        menu=(), app_title="", app_subtitle="", disclaimer="",
        categories=(), cat_colors={}, quick_questions=(),
        books=books, passages=tuple(passages),
    )


def test_cosine_basics():
    assert cosine([1, 0], [1, 0]) == pytest.approx(1.0)
    assert cosine([1, 0], [0, 1]) == pytest.approx(0.0)
    assert cosine([1, 2], [2, 4]) == pytest.approx(1.0)
    assert cosine([], [1]) == 0.0


def test_top_k_orders_by_similarity():
    vectors = {"a": [1, 0], "b": [0.9, 0.1], "c": [-1, 0]}
    assert [pid for pid, _ in top_k(vectors, [1, 0], k=2)] == ["a", "b"]


def test_corpus_hash_changes_with_text():
    p1, p2 = _passage("x1", "один и тот же текст"), _passage("x1", "другой текст")
    c1 = _content(p1)
    c2 = _content(p2)
    assert corpus_hash(c1.passages) != corpus_hash(c2.passages)
    assert corpus_hash(_content(p1).passages) == corpus_hash(c1.passages)


def test_vectors_cache_and_search(tmp_path):
    storage = Storage(tmp_path / "test.db")
    content = _content(
        _passage("p1", "Собака гоняется за мячом по парку."),
        _passage("p2", "Кошки спят по двадцать часов в день."),
    )
    bv = BookVectors(content, storage)
    model = "fake-embed"

    assert not bv.is_cached(model)
    vectors = {
        "p1": [1.0, 0.0, 0.0],
        "p2": [0.0, 1.0, 0.0],
    }
    bv.save(model, vectors)

    assert bv.is_cached(model)
    assert bv.size == 2
    cached = bv.load(model)
    assert cached["p1"] == [1.0, 0.0, 0.0]

    hits = bv.search(model, cached, [0.9, 0.1, 0.0], k=1)
    assert hits[0][0] == "p1"
    assert math.isclose(hits[0][1], cosine([1.0, 0.0, 0.0], [0.9, 0.1, 0.0]))


def test_model_key_namespaced():
    assert model_key("nomic-embed-text") == "emb:nomic-embed-text"


def test_rrf_fuse_promotes_documents_present_in_both_lists():
    fused = rrf_fuse([["p1", "p2"], ["p1", "p3"]])

    assert fused[0] == "p1", "общий лидер списков должен выйти первым"
    assert set(fused) == {"p1", "p2", "p3"}


def test_rrf_fuse_is_deterministic():
    a = ["x", "y", "z"]
    b = ["z", "x"]
    assert rrf_fuse([a, b]) == rrf_fuse([a, b])


def test_rrf_fuse_handles_empty_lists():
    assert rrf_fuse([[], []]) == []
    assert rrf_fuse([["a"], []]) == ["a"]
