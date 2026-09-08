package com.revaks.longevity.core

/**
 * Модели данных приложения — точный перенос датаклассов из longevity/content.py.
 * JSON-данные (tips.json, schedule.json, mind.json, meta.json, books.json)
 * лежат в assets/longevity и загружаются [ContentLoader].
 */

data class Tip(
    val id: String,
    val cat: String,
    val title: String,
    val text: String,
    val sched: String,
    val source: String,
    val tags: String,
    val ageMin: Int?,
    val rx: Boolean,
)

data class ScheduleItem(
    val id: String,
    val title: String,
    val detail: String,
    val cat: String,
    val days: List<Int>,
    val anchor: String,
    val time: String?,
    val tips: List<String>,
    val requires: Map<String, Any?> = emptyMap(),
    val alt: Map<String, String>? = null,
)

data class MindGroup(
    val name: String,
    val amount: String,
    val note: String,
)

data class Book(
    val id: String,
    val title: String,
    val subtitle: String,
    val author: String,
)

/** Отрывок книги — единица поиска по книгам и контекста ассистента. */
data class Passage(
    val id: String,
    val book: String,
    val section: String,
    val text: String,
)

data class MenuDay(
    val day: String,
    val breakfast: String,
    val lunch: String,
    val dinner: String,
    val snack: String,
)

class Content(
    val tips: List<Tip>,
    val schedule: List<ScheduleItem>,
    val synonyms: Map<String, String>,
    val mindGood: List<MindGroup>,
    val mindLimit: List<MindGroup>,
    val menu: List<MenuDay>,
    val appTitle: String,
    val appSubtitle: String,
    val disclaimer: String,
    val categories: List<String>,
    val catColors: Map<String, String>,
    val quickQuestions: List<String>,
    val books: List<Book> = emptyList(),
    val passages: List<Passage> = emptyList(),
) {
    fun tip(id: String): Tip = tips.firstOrNull { it.id == id } ?: throw NoSuchElementException(id)
    fun book(id: String): Book = books.firstOrNull { it.id == id } ?: throw NoSuchElementException(id)
    fun passage(id: String): Passage = passages.firstOrNull { it.id == id } ?: throw NoSuchElementException(id)

    /** Цвет категории как целое ARGB; для неизвестной категории — серый #333333. */
    fun catColor(cat: String): Int {
        val hex = catColors[cat] ?: return 0xFF333333.toInt()
        return parseColor(hex)
    }
}

/** Парсинг "#rrggbb" -> ARGB int; невалидный цвет даёт серый. */
fun parseColor(hex: String): Int = try {
    val h = hex.removePrefix("#")
    when (h.length) {
        6 -> 0xFF000000.toInt() or h.toLong(16).toInt()
        8 -> h.toLong(16).toInt()
        else -> 0xFF333333.toInt()
    }
} catch (e: NumberFormatException) {
    0xFF333333.toInt()
}
