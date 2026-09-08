"""Векторный поиск по отрывкам книг: кэш эмбеддингов и косинус.

Сами вектора считает внешний сервис (Ollama) — этот модуль не знает про
сеть: только хранение в Storage, проверку актуальности кэша и поиск по
косинусу. Вызовы эмбеддингов живут в ui/ollama.py, оркестрация — в ui/rag.py.
"""

import hashlib
import math

#: Префикс ключа модели в таблице embeddings: модель -> «emb:<имя модели>».
MODEL_PREFIX = "emb:"


def model_key(model: str) -> str:
    """Ключ для Storage.put_vectors/get_vectors."""
    return f"{MODEL_PREFIX}{model}"


def corpus_hash(passages) -> str:
    """Хэш корпуса: меняется, только если изменились сами отрывки.

    По нему Storage решает, что кэш эмбеддингов устарел и вектора
    надо пересчитать.
    """
    hasher = hashlib.sha1()
    for passage in passages:
        hasher.update(passage.id.encode("utf-8", errors="replace"))
        hasher.update(b"\x00")
        hasher.update(passage.text.encode("utf-8", errors="replace"))
        hasher.update(b"\x00")
    return hasher.hexdigest()[:16]


def cosine(a: list[float], b: list[float]) -> float:
    """Косинусная близость двух векторов."""
    if not a or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


def top_k(vectors: dict[str, list[float]], query: list[float], k: int,
          ) -> list[tuple[str, float]]:
    """k ближайших к запросу отрывков: список (id, score), по убыванию."""
    scored = [(pid, cosine(vec, query)) for pid, vec in vectors.items()]
    scored.sort(key=lambda pair: (-pair[1], pair[0]))
    return scored[:k] if k else []


class BookVectors:
    """Кэш эмбеддингов отрывков поверх Storage (таблица embeddings).

    Набор векторов хранится под ключом модели и хэшем корпуса; смена модели
    или текстов книг автоматически означает пересчёт (см. _is_cached).
    """

    def __init__(self, content, storage):
        self._passages = list(content.passages)
        self._storage = storage

    @property
    def size(self) -> int:
        return len(self._passages)

    def _vectors(self, model: str) -> dict[str, list[float]]:
        return self._storage.get_vectors(model_key(model),
                                         corpus_hash(self._passages))

    def is_cached(self, model: str) -> bool:
        """Есть ли полный набор векторов этой модели для текущего корпуса."""
        vectors = self._vectors(model)
        return bool(vectors) and len(vectors) == self.size

    def load(self, model: str) -> dict[str, list[float]]:
        """Вектора из кэша. Возвращает {} , если кэш неполон/устарел."""
        return self._vectors(model)

    def save(self, model: str, vectors: dict[str, list[float]]) -> None:
        self._storage.put_vectors(model_key(model),
                                  corpus_hash(self._passages), vectors)

    def search(self, model: str, vectors: dict[str, list[float]],
               query: list[float], k: int) -> list[tuple[str, float]]:
        """Поиск по уже загруженным векторам корпуса."""
        return top_k(vectors, query, k)
