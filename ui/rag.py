# -*- coding: utf-8 -*-
"""Книжный поиск для ассистента и «Базы знаний»: BM25 + вектора.

BM25 работает всегда и офлайн (индекс строится в памяти при старте).
Векторный поиск подключается, когда Ollama отдаёт модель эмбеддингов:
отрывки индексируются в фоновом потоке, вектора кэшируются в SQLite
(Storage, таблица embeddings), и повторные запуски не пересчитывают их.

Поиск выбирает вектора, если они готовы; иначе — BM25. Так ответ никогда
не ждёт сети: ретрив по BM25 синхронный, эмбеддинги — только в готовом виде.
"""

import threading
import tkinter as tk

from longevity.search import BookHit
from longevity.vectors import BookVectors

from .ollama import embed_texts

#: Сколько отрывков подмешивать в контекст ассистента.
ASSISTANT_LIMIT = 6
#: Сколько отрывков показывать во вкладке «Базы знаний».
BOOKS_PAGE_LIMIT = 50


class BookRetriever:
    """Единая точка поиска по книгам для всех экранов.

    Один экземпляр на приложение: строит BM25-индекс по отрывкам и держит
    векторный кэш (статус индексации виден страницам через subscribe()).
    """

    def __init__(self, root, content, storage, model_store):
        self._root = root
        self._content = content
        self._storage = storage
        self._vectors = BookVectors(content, storage)
        self._bm25 = self._build_bm25(content)
        self.model: str = ""            # модель эмбеддингов (если есть)
        self.status: str = ""           # человекочитаемый статус индексации
        self.busy: bool = False
        self._cached: dict[str, list[float]] | None = None
        self._subscribers: list = []
        model_store.subscribe(self._on_models)

    # -- наблюдатели -----------------------------------------------------
    def subscribe(self, callback) -> None:
        self._subscribers.append(callback)
        callback(self)

    def _notify(self) -> None:
        for callback in list(self._subscribers):
            try:
                callback(self)
            except Exception:
                pass

    # -- BM25-индекс -----------------------------------------------------
    @staticmethod
    def _build_bm25(content):
        from longevity.search import BookSearch
        return BookSearch(content)

    def search_bm25(self, query: str, limit: int | None = None) -> list[BookHit]:
        return self._bm25.search(query, limit)

    # -- векторная часть -------------------------------------------------
    @property
    def vector_ready(self) -> bool:
        """Вектора готовы и модель не поменялась."""
        return bool(self.model and self._cached)

    def _on_models(self, store) -> None:
        model = store.embed_model
        if model == self.model and self._cached is not None:
            return
        self.model = model
        self._cached = None
        if not model:
            self.status = ""
            self.busy = False
            self._notify()
            return
        self._ensure_indexed()

    def _ensure_indexed(self) -> None:
        """Загрузить кэш или запустить индексацию в фоне. Идемпотентна."""
        if self.busy or not self.model:
            return
        cached = self._vectors.load(self.model)
        if cached and len(cached) == self._vectors.size:
            self._cached = cached
            self.status = ""
            self._notify()
            return
        self.busy = True
        self.status = "Индексирую книги (первые запуски)..."
        self._notify()

        def work():
            try:
                passages = list(self._content.passages)
                vectors_list = embed_texts(
                    self.model, [p.text for p in passages])
                vectors = {p.id: vec for p, vec in zip(passages, vectors_list)}
                self._vectors.save(self.model, vectors)
                self._deliver(vectors)
            except Exception:
                self._deliver(None)

        threading.Thread(target=work, daemon=True).start()

    def _deliver(self, vectors: dict | None) -> None:
        """Выполняется в фоновом потоке."""
        def apply():
            if vectors is None:
                self.status = ("Векторный поиск недоступен "
                               "(ошибка Ollama/модели эмбеддингов)")
            else:
                self._cached = vectors
                self.status = ""
            self.busy = False
            self._notify()

        try:
            self._root.after(0, apply)
        except (RuntimeError, tk.TclError):
            self.busy = False

    def search_vector(self, query: str, limit: int) -> list[BookHit]:
        """Векторный поиск по готовому кэшу. Бросает исключения — вызывает
        код решает, откатываться ли на BM25."""
        if not self.vector_ready:
            return []
        model = self.model
        query_vec = embed_texts(model, [query])[0]
        hits = self._vectors.search(model, self._cached, query_vec, limit)
        return [BookHit(passage=self._content.passage(pid), score=score)
                for pid, score in hits]

    # -- общий поиск -----------------------------------------------------
    def search(self, query: str, limit: int | None = None,
               prefer_vector: bool = True) -> list[BookHit]:
        """Векторный поиск, если готов; иначе BM25."""
        if prefer_vector and self.vector_ready:
            try:
                hits = self.search_vector(query, limit or BOOKS_PAGE_LIMIT)
                if hits:
                    return hits
            except Exception:
                pass  # сеть/модель сбойнули — BM25 ниже
        return self.search_bm25(query, limit)
