# -*- coding: utf-8 -*-
"""Оформление отрывков книг для интерфейса и промпта (без Tk).

Хелперы общие для «Ассистента» и страницы книг в «Базе знаний» и не требуют
окна, поэтому лежат отдельно от страниц.
"""

#: Предел длины отрывка книги в контексте промпта: цитата должна умещаться,
#: а не вытеснять остальной контекст.
MAX_CONTEXT_PASSAGE_CHARS = 700


def passage_reference(passage, content) -> str:
    """Человекочитаемый источник отрывка: «Книга», раздел «Раздел»."""
    try:
        book = content.book(passage.book)
    except KeyError:
        book = None
    title = f"«{book.title}»" if book else passage.book
    if passage.section:
        return f"{title}, раздел «{passage.section}»"
    return title


def truncate_passage(text: str, limit: int = MAX_CONTEXT_PASSAGE_CHARS) -> str:
    """Обрезать отрывок по границе предложения, не разрывая мысль."""
    if len(text) <= limit:
        return text
    cut = text[:limit]
    # Откатываемся до последней границы предложения в пределах лимита.
    for end in (". ", "! ", "? ", ".\n"):
        pos = cut.rfind(end)
        if pos > limit * 0.4:
            return cut[:pos + len(end.strip())].rstrip() + "..."
    return cut.rstrip() + "..."
