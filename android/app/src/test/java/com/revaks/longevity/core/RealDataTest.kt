package com.revaks.longevity.core

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.time.LocalDate

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

    private fun jsonFiles(): JsonFiles = JsonFiles(
        tips = resource("tips.json"),
        schedule = resource("schedule.json"),
        synonyms = resource("synonyms.json"),
        mind = resource("mind.json"),
        meta = resource("meta.json"),
        books = resource("books.json"),
        extras = resource("extras.json"),
    )

    @Test
    fun `real data loads and passes integrity checks`() {
        val content = ContentLoader.buildContent(jsonFiles())

        assertEquals(82, content.tips.size)
        assertEquals(24, content.schedule.size)
        assertEquals(3, content.books.size)
        assertEquals(848, content.passages.size)
        assertEquals(
            listOf("Образ жизни", "Питание", "Добавки", "Процедуры"),
            content.categories,
        )
        assertTrue(content.tips.all { it.cat in content.categories })
        assertEquals("Ассистент долголетия", content.appTitle)
    }

    @Test
    fun `extras give rotation, focus weeks and screenings`() {
        val content = ContentLoader.buildContent(jsonFiles())

        assertTrue(content.rotations.isNotEmpty())
        assertTrue(content.focus.size >= 12)
        assertTrue(content.screenings.size >= 10)
        // Ссылки ротации указывают на реальные пункты расписания.
        val scheduleIds = content.schedule.map { it.id }.toSet()
        assertTrue(content.rotations.keys.all { it in scheduleIds })
        assertTrue(content.focus.all { it.tasks.size >= 3 })
        assertTrue(content.screenings.all { it.periodMonths > 0 })

        // Тема недели и вариант ротации определяются для любого дня.
        val day = LocalDate.of(2026, 9, 9)
        assertNotNull(Plan.focusForWeek(content, day))
        val aerobic = content.schedule.first { it.id == "train_aerobic" }
        assertNotNull(Plan.variantFor(content, aerobic, day, Profile(activity = 1)))
    }

    @Test
    fun `plan respects hidden and custom items`() {
        val content = ContentLoader.buildContent(jsonFiles())
        val day = LocalDate.of(2026, 9, 9) // среда
        val custom = Plan.parseCustomItems(
            Plan.serializeCustomItems(
                listOf(
                    ScheduleItem(
                        id = Plan.newCustomId(), title = "Дневник сна", detail = "Отметить часы",
                        cat = content.categories.first(), days = listOf(day.dayOfWeek.value - 1),
                        anchor = "clock", time = "08:00", tips = emptyList(),
                    )
                )
            ),
            content.categories,
        )
        val profile = Profile(activity = 2, hidden = setOf("sauna"))
        val items = Plan.itemsForDay(content, profile, custom, day)
        assertTrue(items.none { it.id == "sauna" })
        assertTrue(items.any { it.title == "Дневник сна" })
    }

    @Test
    fun `tips search over real data works`() {
        val content = ContentLoader.buildContent(jsonFiles())
        val index = SearchIndex(content)
        val hits = index.search("как спать", limit = 5)
        assertTrue(hits.isNotEmpty())
        assertTrue(hits.first().score > 0)
    }

    @Test
    fun `book search over real books json is fast and finds excerpts`() {
        val content = ContentLoader.buildContent(jsonFiles())
        val start = System.nanoTime()
        val bookSearch = BookSearch(content)
        val hits = bookSearch.search("мелатонин и сон", limit = 10)
        assertTrue(hits.isNotEmpty())
        val ms = (System.nanoTime() - start) / 1_000_000
        assertTrue("поиск по 848 отрывкам занял ${ms}мс", ms < 3_000)
    }

    @Test
    fun `assistant answers a real question offline`() {
        val content = ContentLoader.buildContent(jsonFiles())
        val answer = AssistantEngine.answer(
            content, SearchIndex(content), BookSearch(content),
            "Какие добавки полезны после 50 лет?",
        )
        assertTrue(answer.isNotBlank())
        assertFalse(answer.startsWith("Внимание"))
        assertNotNull(answer)
    }
}
