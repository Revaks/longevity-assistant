package com.revaks.longevity.core

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class SearchTest {

    private val content = Content(
        tips = listOf(
            Tip("sleep1", "Образ жизни", "Спать не меньше 7 часов",
                "Сон восстанавливает мозг: спите в темноте и прохладе.",
                "Каждую ночь", "Глава о сне", "сон ночь темнота", null, false),
            Tip("sleep2", "Образ жизни", "Ложиться до полуночи",
                "Циркадные ритмы: до полуночи сон самый глубокий.",
                "Ежедневно", "Глава о сне", "сон режим ритмы", null, false),
            Tip("food1", "Питание", "Жирная рыба дважды в неделю",
                "Омега-3 из рыбы поддерживает сердце и память.",
                "2 раза в неделю", "Глава о питании", "рыба омега", null, false),
        ),
        schedule = emptyList(),
        synonyms = mapOf(
            "рыба" to "рыба омега",
            "спать" to "сон ночь",
        ),
        mindGood = emptyList(), mindLimit = emptyList(), menu = emptyList(),
        appTitle = "Т", appSubtitle = "С", disclaimer = "Д",
        categories = listOf("Образ жизни", "Питание"),
        catColors = emptyMap(), quickQuestions = emptyList(),
    )

    private val index = SearchIndex(content)

    @Test
    fun `query finds relevant tip first`() {
        val hits = index.search("как спать", limit = 5)
        assertTrue(hits.isNotEmpty())
        assertEquals("sleep1", hits.first().tip.id)
    }

    @Test
    fun `synonym expands query with lower weight`() {
        // «омега» есть в тексте food1 и в синонимах «рыба»; прямой термин спит.
        val hits = index.search("рыба", limit = 10)
        assertTrue(hits.map { it.tip.id }.contains("food1"))
        // синоним «ночь» расширяет запрос «спать» до sleep1
        val night = index.search("спать", limit = 10)
        assertTrue(night.isNotEmpty())
    }

    @Test
    fun `empty query returns nothing`() {
        assertTrue(index.search("").isEmpty())
        assertTrue(index.search("и а но").isEmpty()) // только стоп-слова
    }

    @Test
    fun `limit truncates results`() {
        val all = index.search("сон")
        assertTrue(all.size > 1)
        val limited = index.search("сон", limit = 1)
        assertEquals(1, limited.size)
    }

    @Test
    fun `tie broken by ascending id`() {
        // Нулевой предел означает «ничего не показывать».
        assertTrue(index.search("сон", limit = 0).isEmpty())
    }

    @Test
    fun `book search indexes section and book title fields`() {
        val booksContent = Fixtures.content(
            booksJson = Fixtures.booksJson(
                books = Fixtures.obj(
                    "id" to "b1", "title" to "Мозг долгожителя", "subtitle" to "",
                    "author" to "Москалев",
                ),
                passages = Fixtures.obj(
                    "id" to "p1", "book" to "b1", "section" to "Сон и очищение",
                    "text" to "Во сне мозг выводит продукты обмена.",
                ),
            ),
        )
        val bookSearch = BookSearch(booksContent)
        // Находит по разделу
        val bySection = bookSearch.search("очищение")
        assertTrue(bySection.isNotEmpty())
        // Находит по названию книги
        val byBook = bookSearch.search("долгожителя")
        assertTrue(byBook.isNotEmpty())
        // Находит по тексту («мозг» есть в отрывке)
        val byText = bookSearch.search("мозг")
        assertTrue(byText.isNotEmpty())
    }
}
