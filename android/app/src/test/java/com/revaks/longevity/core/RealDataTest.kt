package com.revaks.longevity.core

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Прогон ядра на настоящих данных приложения (JSON из assets/longevity,
 * добавлены в ресурсы тестов в app/build.gradle.kts).
 */
class RealDataTest {

    private fun resource(name: String): String {
        val stream = javaClass.classLoader?.getResourceAsStream("longevity/$name")
            ?: throw IllegalStateException("Не найден ресурс longevity/$name")
        return stream.bufferedReader(Charsets.UTF_8).use { it.readText() }
    }

    @Test
    fun `real data loads and passes integrity checks`() {
        val content = ContentLoader.buildContent(
            JsonFiles(
                tips = resource("tips.json"),
                schedule = resource("schedule.json"),
                synonyms = resource("synonyms.json"),
                mind = resource("mind.json"),
                meta = resource("meta.json"),
                books = resource("books.json"),
            )
        )

        assertEquals(82, content.tips.size)
        assertEquals(24, content.schedule.size)
        assertEquals(3, content.books.size)
        assertEquals(848, content.passages.size)
        assertEquals(listOf("Образ жизни", "Питание", "Добавки", "Процедуры"),
            content.categories)
        assertTrue(content.tips.all { it.cat in content.categories })
        assertEquals("Ассистент долголетия", content.appTitle)
    }

    @Test
    fun `tips search over real data works`() {
        val content = ContentLoader.buildContent(
            JsonFiles(
                tips = resource("tips.json"), schedule = resource("schedule.json"),
                synonyms = resource("synonyms.json"), mind = resource("mind.json"),
                meta = resource("meta.json"), books = resource("books.json"),
            )
        )
        val index = SearchIndex(content)
        val hits = index.search("как спать", limit = 5)
        assertTrue(hits.isNotEmpty())
        assertTrue(hits.first().score > 0)
    }

    @Test
    fun `book search over real books json is fast and finds excerpts`() {
        val content = ContentLoader.buildContent(
            JsonFiles(
                tips = resource("tips.json"), schedule = resource("schedule.json"),
                synonyms = resource("synonyms.json"), mind = resource("mind.json"),
                meta = resource("meta.json"), books = resource("books.json"),
            )
        )
        val start = System.nanoTime()
        val bookSearch = BookSearch(content)
        val hits = bookSearch.search("мелатонин и сон", limit = 10)
        assertTrue(hits.isNotEmpty())
        val ms = (System.nanoTime() - start) / 1_000_000
        assertTrue("поиск по 848 отрывкам занял ${ms}мс", ms < 3_000)
    }

    @Test
    fun `assistant answers a real question offline`() {
        val content = ContentLoader.buildContent(
            JsonFiles(
                tips = resource("tips.json"), schedule = resource("schedule.json"),
                synonyms = resource("synonyms.json"), mind = resource("mind.json"),
                meta = resource("meta.json"), books = resource("books.json"),
            )
        )
        val answer = AssistantEngine.answer(
            content, SearchIndex(content), BookSearch(content),
            "Какие добавки полезны после 50 лет?",
        )
        assertTrue(answer.isNotBlank())
        assertFalse(answer.startsWith("Внимание"))
        assertNotNull(answer)
    }
}
