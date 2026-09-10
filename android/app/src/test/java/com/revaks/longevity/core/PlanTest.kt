package com.revaks.longevity.core

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.time.LocalDate

/** План дня: ротация вариантов, скрытые и свои пункты. */
class PlanTest {

    private fun content(): Content = Fixtures.content(
        scheduleJson = Fixtures.scheduleJson(
            Fixtures.scheduleItem(id = "fish_day", days = listOf(0, 1, 2, 3, 4, 5, 6)),
        ),
        extras = Fixtures.extrasJson(
            rotations = Fixtures.rowsJson(
                Fixtures.rotation(
                    itemId = "fish_day",
                    variants = Fixtures.rowsJson(
                        Fixtures.obj("level" to 0, "title" to "Лёгкий", "detail" to "д0"),
                        Fixtures.obj("level" to 1, "title" to "Средний", "detail" to "д1"),
                        Fixtures.obj("level" to 2, "title" to "Сильный", "detail" to "д2"),
                    ),
                ),
            ),
        ),
    )

    @Test
    fun `iso week is stable and focus cycles`() {
        val content = content()
        val monday = LocalDate.of(2026, 9, 7)
        assertEquals(Plan.isoWeek(monday), Plan.isoWeek(monday.plusDays(3)))
        val focus = Plan.focusForWeek(content, monday)
        assertEquals("f1", focus?.id)
        // Через число недель, кратное размеру списка, фокус повторяется.
        val later = monday.plusWeeks(content.focus.size.toLong())
        assertEquals(focus?.id, Plan.focusForWeek(content, later)?.id)
    }

    @Test
    fun `variant respects activity level and rotates by week`() {
        val content = content()
        val item = content.schedule.first()
        val low = Plan.variantFor(content, item, LocalDate.of(2026, 9, 7), Profile(activity = 0))
        assertEquals("Лёгкий", low?.title)
        // Высокий уровень видит все варианты — конкретный зависит от недели.
        assertNotNull(Plan.variantFor(content, item, LocalDate.of(2026, 9, 7), Profile(activity = 2)))

        // Соседние недели дают разные варианты (ротация).
        val week1 = Plan.variantFor(content, item, LocalDate.of(2026, 9, 7), Profile(activity = 2))
        val week2 = Plan.variantFor(content, item, LocalDate.of(2026, 9, 14), Profile(activity = 2))
        assertTrue(week1?.title != week2?.title)
    }

    @Test
    fun `deload week picks lightest variant`() {
        val content = content()
        val item = content.schedule.first()
        val variant = Plan.variantFor(
            content, item, LocalDate.of(2026, 9, 7), Profile(activity = 2, deload = true),
        )
        assertEquals("Лёгкий", variant?.title)
    }

    @Test
    fun `rotation changes only text, not the id`() {
        val content = content()
        val item = content.schedule.first()
        val rotated = Plan.applyRotation(content, item, LocalDate.of(2026, 9, 7), Profile(activity = 2))
        assertEquals(item.id, rotated.id)
        assertEquals(item.days, rotated.days)
    }

    @Test
    fun `custom items round trip and filter by weekday`() {
        val content = content()
        val monday = LocalDate.of(2026, 9, 7) // понедельник
        val custom = listOf(
            ScheduleItem(
                id = Plan.newCustomId(), title = "Дневник сна", detail = "8 часов",
                cat = content.categories.first(), days = listOf(0),
                anchor = "clock", time = "08:00", tips = emptyList(),
            )
        )
        val parsed = Plan.parseCustomItems(Plan.serializeCustomItems(custom), content.categories)
        assertEquals(1, parsed.size)
        assertEquals("Дневник сна", parsed.first().title)

        val mondayItems = Plan.itemsForDay(content, Profile(), parsed, monday)
        assertTrue(mondayItems.any { it.title == "Дневник сна" })
        val tuesdayItems = Plan.itemsForDay(content, Profile(), parsed, monday.plusDays(1))
        assertFalse(tuesdayItems.any { it.title == "Дневник сна" })
    }

    @Test
    fun `parse custom items skips broken rows`() {
        val categories = listOf("Питание")
        val broken = """
            [
              {"id":"wrong:1","title":"Плохой id","days":[0],"anchor":"allday"},
              {"id":"custom:1","title":"","days":[0],"anchor":"allday"},
              {"id":"custom:2","title":"Без дней","days":[],"anchor":"allday"},
              {"id":"custom:3","title":"Часы без времени","days":[0],"anchor":"clock"},
              {"id":"custom:4","title":"Хороший","days":[1],"anchor":"allday"}
            ]
        """.trimIndent()
        val items = Plan.parseCustomItems(broken, categories)
        assertEquals(1, items.size)
        assertEquals("Хороший", items.first().title)
        assertEquals("Питание", items.first().cat)
    }

    @Test
    fun `hidden items are excluded from the day`() {
        val content = content()
        val day = LocalDate.of(2026, 9, 7)
        val all = Plan.itemsForDay(content, Profile(), emptyList(), day)
        assertTrue(all.isNotEmpty())
        val hiddenId = all.first().id
        val filtered = Plan.itemsForDay(content, Profile(hidden = setOf(hiddenId)), emptyList(), day)
        assertTrue(filtered.none { it.id == hiddenId })
    }

    @Test
    fun `no rotation content means no override`() {
        val content = Fixtures.content(extras = Fixtures.extrasJson(rotations = "[]"))
        val item = content.schedule.first()
        assertNull(Plan.variantFor(content, item, LocalDate.of(2026, 9, 7), Profile()))
        assertEquals(item.title, Plan.applyRotation(content, item, LocalDate.of(2026, 9, 7), Profile()).title)
    }
}
