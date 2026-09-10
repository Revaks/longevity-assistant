"""Единый поисковый движок приложения: BM25F по советам и по книгам.

Один класс `_BM25F` делает всю статистику и скоринг для любого набора
документов; `SearchIndex` индексирует советы (поля title/tags/text/cat),
`BookSearch` — отрывки книг (поля section/book/text). Поведение поиска
по советам не менялось: прежние тесты проходят как есть.
"""

import math
from collections import Counter
from dataclasses import dataclass

from .content import Content, Passage, Tip
from .text import analyze, tokenize

FIELD_WEIGHTS = {"title": 3.0, "tags": 2.0, "text": 1.0, "cat": 0.5}
BOOK_FIELD_WEIGHTS = {"section": 3.0, "book": 2.0, "text": 1.0}
K1 = 1.2
B = 0.75
SYNONYM_WEIGHT = 0.4
DEFAULT_LIMIT = None


@dataclass(frozen=True)
class Hit:
    tip: Tip
    score: float


@dataclass(frozen=True)
class BookHit:
    passage: Passage
    score: float


class _BM25F:
    """Общая механика BM25F над списком документов.

    Документ — произвольный объект; текст его поля берётся функцией
    field_text(field, doc) -> str. Синонимы — словарь «слово до стемминга →
    список основ», тот же, что у советов (content.synonyms).
    """

    def __init__(self, docs, weights: dict[str, float], field_text,
                 synonyms: dict[str, str]):
        self._docs = list(docs)
        self._weights = weights
        self._synonyms = {k: analyze(v) for k, v in synonyms.items()}
        self._fields: list[dict[str, Counter]] = []
        self._lengths: list[dict[str, int]] = []

        for doc in self._docs:
            counters, lengths = {}, {}
            for field in weights:
                terms = analyze(field_text(field, doc))
                counters[field] = Counter(terms)
                lengths[field] = len(terms)
            self._fields.append(counters)
            self._lengths.append(lengths)

        n = len(self._docs)
        self._n = n
        self._avg_len = {
            field: (sum(l[field] for l in self._lengths) / n) or 1.0
            for field in weights
        } if n else {field: 1.0 for field in weights}
        self._df: Counter = Counter()
        for counters in self._fields:
            seen = set()
            for counter in counters.values():
                seen.update(counter)
            self._df.update(seen)

    # -- запрос --------------------------------------------------------
    def _weighted_terms(self, query: str) -> dict[str, float]:
        """Основы запроса с весами: прямые слова тяжелее синонимов."""
        terms: dict[str, float] = {}
        for term in analyze(query):
            terms[term] = 1.0
        # Словарь синонимов ключуется по словам до стемминга, поэтому здесь
        # нужен сырой tokenize, а не analyze.
        for word in set(tokenize(query)):
            for term in self._synonyms.get(word, ()):
                terms.setdefault(term, SYNONYM_WEIGHT)
        return terms

    def _idf(self, term: str) -> float:
        df = self._df.get(term, 0)
        return math.log((self._n - df + 0.5) / (df + 0.5) + 1)

    def _tf(self, index: int, term: str) -> float:
        counters, lengths = self._fields[index], self._lengths[index]
        total = 0.0
        for field, weight in self._weights.items():
            count = counters[field].get(term, 0)
            if not count:
                continue
            norm = 1 - B + B * (lengths[field] / self._avg_len[field])
            total += weight * count / norm
        return total

    def search(self, query: str, limit: int | None = DEFAULT_LIMIT):
        """Документы и оценки, отсортированные по (-score, id)."""
        terms = self._weighted_terms(query)
        if not terms:
            return []
        hits = []
        for i, doc in enumerate(self._docs):
            score = 0.0
            for term, weight in terms.items():
                tf = self._tf(i, term)
                if not tf:
                    continue
                score += weight * self._idf(term) * (tf * (K1 + 1)) / (tf + K1)
            if score > 0:
                hits.append((doc, score))
        hits.sort(key=lambda pair: (-pair[1], pair[0].id))
        # limit=0 — «ничего не показывать»; без ограничения — None.
        return hits if limit is None else hits[:limit]


def _tip_field(field: str, tip: Tip) -> str:
    return getattr(tip, field)


class SearchIndex:
    """Индекс советов: 70 документов, четыре поля. Строится один раз при старте."""

    def __init__(self, content: Content):
        self._content = content
        self._engine = _BM25F(content.tips, FIELD_WEIGHTS, _tip_field,
                              content.synonyms)
        # Прежние тесты читают внутренности индекса напрямую — пробрасываем.
        self._n = self._engine._n
        self._df = self._engine._df
        self._synonyms = self._engine._synonyms

    def _weighted_terms(self, query: str) -> dict[str, float]:
        return self._engine._weighted_terms(query)

    def _idf(self, term: str) -> float:
        return self._engine._idf(term)

    def search(self, query: str, limit: int | None = DEFAULT_LIMIT) -> list[Hit]:
        return [Hit(tip=doc, score=score)
                for doc, score in self._engine.search(query, limit)]


def _book_field(book_titles: dict[str, str]):
    """Функция «поле -> текст» для отрывка: book-поле отдаёт название книги."""

    def field_text(field: str, passage: Passage) -> str:
        if field == "book":
            return book_titles.get(passage.book, passage.book)
        if field == "section":
            return passage.section
        return passage.text

    return field_text


class BookSearch:
    """Индекс отрывков книг. Название книги подмешивается в «book»-поле."""

    def __init__(self, content: Content):
        self._content = content
        book_titles = {b.id: f"{b.title} {b.subtitle}".strip()
                       for b in content.books}
        self._engine = _BM25F(content.passages, BOOK_FIELD_WEIGHTS,
                              _book_field(book_titles), content.synonyms)

    def search(self, query: str, limit: int | None = DEFAULT_LIMIT) -> list[BookHit]:
        return [BookHit(passage=doc, score=score)
                for doc, score in self._engine.search(query, limit)]
