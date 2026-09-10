package com.revaks.longevity.core

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import java.time.LocalDate

class AssistantEngineTest {

    private val scheduleJson = Fixtures.scheduleJson(
        Fixtures.scheduleItem(
            id = "a1", title = "Лёгкая зарядка", detail = "",
            days = (0..6).toList(), anchor = "morning", time = null,
            tips = emptyList(),
        ),
    )
    private val tipsJson = Fixtures.tipsJson(
        Fixtures.tip(
            id = "s1", cat = "Образ жизни", title = "Спать 7–9 часов",
            text = "Сон в темноте восстанавливает мозг.",
            tags = "сон ночь", source = "Глава о сне",
        ),
        Fixtures.tip(
            id = "f1", cat = "Питание", title = "Рыба дважды в неделю",
            text = "Омега-3 полезна.", tags = "рыба", source = "Глава о питании",
        ),
    )

    private val content = Fixtures.content(
        tipsJson = tipsJson,
        scheduleJson = scheduleJson,
    )
    private val index = SearchIndex(content)
    private val books = BookSearch(content)
    private val today: LocalDate = LocalDate.of(2026, 9, 8) // вторник

    private fun emptyBooks(): String = Fixtures.obj(
        "version" to 1, "books" to Fixtures.arr(), "passages" to Fixtures.arr(),
    )

    @Test
    fun `plan request returns day plan`() {
        val answer = AssistantEngine.answer(content, index, books, "План на сегодня", today)
        assertTrue(answer.contains("План на вторник"))
        assertTrue(answer.contains("Лёгкая зарядка"))
    }

    @Test
    fun `week request returns week plan with all days`() {
        val answer = AssistantEngine.answer(content, index, books, "расписание на неделю", today)
        assertTrue(answer.contains("Расписание на текущую неделю"))
        // Пункт назначен на все дни недели — упоминается в каждом дне
        assertEquals(7, answer.lines().count { it.contains("Лёгкая зарядка") })
    }

    @Test
    fun `question answers from tips`() {
        val answer = AssistantEngine.answer(content, index, books, "как спать лучше", today)
        assertTrue(answer.contains("Вот что советует А. А. Москалев"))
        assertTrue(answer.contains("Спать 7–9 часов"))
    }

    @Test
    fun `unknown question falls back when nothing found`() {
        val noBooks = Fixtures.content(
            tipsJson = tipsJson, scheduleJson = scheduleJson,
            booksJson = emptyBooks(),
        )
        val answer = AssistantEngine.answer(
            noBooks, SearchIndex(noBooks), BookSearch(noBooks),
            "парадокс квантовой запутанности", today,
        )
        assertTrue(answer.contains("Не нашёл точного совета"))
    }

    @Test
    fun `book excerpt path used when tips miss`() {
        val withBooks = Fixtures.content(
            tipsJson = Fixtures.tipsJson(
                Fixtures.tip(id = "x", title = "Только про еду",
                    text = "Текст про еду.", tags = "еда"),
            ),
            scheduleJson = Fixtures.scheduleJson(),
            booksJson = Fixtures.booksJson(
                passages = Fixtures.obj(
                    "id" to "p1", "book" to "b1", "section" to "Мозг",
                    "text" to "Мозг стареет медленнее при регулярных упражнениях.",
                ),
            ),
        )
        val bi = SearchIndex(withBooks)
        val bb = BookSearch(withBooks)
        val answer = AssistantEngine.answer(withBooks, bi, bb, "как тренировать мозг", today)
        assertTrue(answer.contains("Вот что пишет А. А. Москалев в книгах"))
    }

    @Test
    fun `nutrition detection`() {
        assertTrue(AssistantEngine.isAboutNutrition("что есть на ужин"))
        assertTrue(AssistantEngine.isAboutNutrition("диета mind"))
        assertTrue(AssistantEngine.isAboutNutrition("покажи меню"))
        assertTrue(!AssistantEngine.isAboutNutrition("как улучшить сон"))
    }

    @Test
    fun `greeting mentions books`() {
        val greeting = AssistantEngine.greet()
        assertTrue(greeting.contains("Москалева"))
        assertTrue(greeting.contains("120 лет жизни"))
    }
}
