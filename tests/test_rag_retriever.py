"""Оформление отрывков и BookRetriever (без окна и без сети)."""

from types import SimpleNamespace

from longevity.content import Content, Passage, load_content
from longevity.storage import Storage
from ui.formatting import passage_reference, truncate_passage
from ui.rag import BookRetriever


def _fake_store(embed_model=""):
    store = SimpleNamespace(embed_model=embed_model)

    def subscribe(callback):
        callback(store)

    store.subscribe = subscribe
    return store


def test_passage_reference_formats_book_and_section():
    content = load_content()
    passage = content.passages[0]

    reference = passage_reference(passage, content)

    assert reference.startswith("«")
    assert reference.count("»") >= 1


def test_passage_reference_unknown_book_falls_back_to_id():
    content = Content(tips=(), schedule=(), synonyms={}, mind_good=(),
                      mind_limit=(), menu=(), app_title="", app_subtitle="",
                      disclaimer="", categories=(), cat_colors={},
                      quick_questions=(), books=(), passages=())
    passage = Passage(id="x:1", book="unknown", section="Раздел", text="текст")

    assert passage_reference(passage, content) == "unknown, раздел «Раздел»"


def test_truncate_passage_keeps_short_text():
    assert truncate_passage("короткий текст", limit=100) == "короткий текст"


def test_truncate_passage_cuts_on_sentence_boundary():
    long_text = "Одно длинное предложение. " * 30
    cut = truncate_passage(long_text, limit=100)

    assert len(cut) <= 104
    assert cut.endswith("...")
    assert "Одно длинное предложение. " in cut


def test_retriever_works_without_ollama(tmp_path):
    content = load_content()
    storage = Storage(tmp_path / "test.db")
    retriever = BookRetriever(None, content, storage, _fake_store())

    assert not retriever.vector_ready
    hits = retriever.search("мелатонин и сон", limit=3)

    assert hits, "без Ollama поиск по книгам обязан работать через BM25"
    assert hits[0].passage.book in {b.id for b in content.books}


def test_hybrid_search_merges_bm25_and_vectors(tmp_path, monkeypatch):
    """При готовом кэше retriever.search возвращает слияние BM25 и векторов."""
    from longevity.content import Book, Content, Passage
    from ui import rag as rag_module

    book = (Book(id="b1", title="Книга", subtitle="", author="Автор"),)
    passages = (
        Passage(id="p1", book="b1", section="Питание",
                text="Омега-3 из жирной рыбы полезна."),
        Passage(id="p2", book="b1", section="Сон",
                text="Мелатонин регулирует сон."),
        Passage(id="p3", book="b1", section="Питание",
                text="Лосось и тунец богаты омега-3."),
    )
    content = Content(tips=(), schedule=(), synonyms={}, mind_good=(),
                      mind_limit=(), menu=(), app_title="", app_subtitle="",
                      disclaimer="", categories=(), cat_colors={},
                      quick_questions=(), books=book, passages=passages)
    retriever = BookRetriever(None, content, Storage(tmp_path / "t.db"),
                              _fake_store())
    retriever.model = "fake-emb"
    retriever._cached = {"p1": [1.0, 0.0, 0.0],
                         "p2": [0.0, 1.0, 0.0],
                         "p3": [0.95, 0.05, 0.0]}

    def fake_embed(model, texts):
        return [[1.0, 0.0, 0.0]] * len(texts)

    monkeypatch.setattr(rag_module, "embed_texts", fake_embed)

    assert retriever.vector_ready
    hits = retriever.search("рыба омега-3", limit=3)

    ids = [h.passage.id for h in hits]
    assert ids[0] == "p1"
    # Векторный вкладчик вернул и p3 (смыслово близкий к запросу) —
    # гибрид не ограничивается буквальным совпадением BM25.
    assert "p3" in ids
