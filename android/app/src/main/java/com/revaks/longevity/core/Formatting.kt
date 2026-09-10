package com.revaks.longevity.core

/**
 * Оформление отрывков книг для интерфейса и промпта — перенос ui/formatting.py.
 */
object Formatting {
    /** Предел длины отрывка книги в подписи. */
    const val MAX_CONTEXT_PASSAGE_CHARS = 700

    /** «Книга», раздел «Раздел» — читаемый источник отрывка. */
    fun passageReference(passage: Passage, content: Content): String {
        val book = content.books.firstOrNull { it.id == passage.book }
        val title = if (book != null) "«${book.title}»" else passage.book
        return if (passage.section.isNotEmpty()) "$title, раздел «${passage.section}»" else title
    }

    /** Обрезать отрывок по границе предложения, не разрывая мысль. */
    fun truncatePassage(text: String, limit: Int = MAX_CONTEXT_PASSAGE_CHARS): String {
        if (text.length <= limit) return text
        val cut = text.substring(0, limit)
        for (end in listOf(". ", "! ", "? ", ".\n")) {
            val pos = cut.lastIndexOf(end)
            if (pos > limit * 0.4) {
                val till = pos + end.trimEnd().length
                return cut.substring(0, till).trimEnd() + "..."
            }
        }
        return cut.trimEnd() + "..."
    }
}
