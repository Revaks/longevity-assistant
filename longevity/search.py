"""Единственный поисковый движок приложения: BM25F по советам."""

import math
from collections import Counter
from dataclasses import dataclass

from .content import Content, Tip
from .text import analyze, tokenize

FIELD_WEIGHTS = {"title": 3.0, "tags": 2.0, "text": 1.0, "cat": 0.5}
K1 = 1.2
B = 0.75
SYNONYM_WEIGHT = 0.4
DEFAULT_LIMIT = None


@dataclass(frozen=True)
class Hit:
    tip: Tip
    score: float


class SearchIndex:
    """Строится один раз при старте: 70 документов, четыре поля."""

    def __init__(self, content: Content):
        self._content = content
        self._tips = content.tips
        self._synonyms = {k: analyze(v) for k, v in content.synonyms.items()}
        self._fields: list[dict[str, Counter]] = []
        self._lengths: list[dict[str, int]] = []

        for tip in self._tips:
            counters, lengths = {}, {}
            for field in FIELD_WEIGHTS:
                terms = analyze(getattr(tip, field))
                counters[field] = Counter(terms)
                lengths[field] = len(terms)
            self._fields.append(counters)
            self._lengths.append(lengths)

        self._avg_len = {
            field: (sum(l[field] for l in self._lengths) / len(self._lengths)) or 1.0
            for field in FIELD_WEIGHTS
        }
        self._df: Counter = Counter()
        for counters in self._fields:
            seen = set()
            for counter in counters.values():
                seen.update(counter)
            self._df.update(seen)
        self._n = len(self._tips)

    # -- запрос --------------------------------------------------------
    def _weighted_terms(self, query: str) -> dict[str, float]:
        """Основы запроса с весами: прямые слова тяжелее подмешанных синонимов."""
        terms: dict[str, float] = {}
        for term in analyze(query):
            terms[term] = 1.0
        # Словарь синонимов ключуется по словам до стемминга, поэтому здесь нужен
        # сырой tokenize, а не analyze.
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
        for field, weight in FIELD_WEIGHTS.items():
            count = counters[field].get(term, 0)
            if not count:
                continue
            norm = 1 - B + B * (lengths[field] / self._avg_len[field])
            total += weight * count / norm
        return total

    def search(self, query: str, limit: int | None = DEFAULT_LIMIT) -> list[Hit]:
        terms = self._weighted_terms(query)
        if not terms:
            return []

        hits: list[Hit] = []
        for i, tip in enumerate(self._tips):
            score = 0.0
            for term, weight in terms.items():
                tf = self._tf(i, term)
                if not tf:
                    continue
                score += weight * self._idf(term) * (tf * (K1 + 1)) / (tf + K1)
            if score > 0:
                hits.append(Hit(tip=tip, score=score))

        hits.sort(key=lambda h: (-h.score, h.tip.id))
        # limit=0 — это «ничего не показывать», а не «показать всё»: снять
        # ограничение можно только limit=None (DEFAULT_LIMIT). Прежнее `if
        # limit` считало ноль ложью и возвращало всю выдачу целиком.
        return hits if limit is None else hits[:limit]
