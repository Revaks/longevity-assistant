package com.revaks.longevity.core

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import java.time.LocalDate

/** Обследования: применимость по возрасту/полу, сроки. */
class ScreeningsTest {

    private fun content(): Content = Fixtures.content(
        extras = Fixtures.extrasJson(
            screenings = Fixtures.rowsJson(
                Fixtures.screening(id = "any", ageMin = 18, periodMonths = 12),
                Fixtures.screening(id = "after40", ageMin = 40, periodMonths = 24),
                Fixtures.screening(id = "women", ageMin = 40, periodMonths = 24, sex = "ж"),
            ),
        ),
    )

    @Test
    fun `applicability respects age and sex`() {
        val content = content()
        val young = Profile(age = 30)
        val ids = content.screenings.filter { Screenings.isApplicable(it, young) }.map { it.id }
        assertEquals(listOf("any"), ids)

        val woman = Profile(age = 50, sex = "ж")
        val womanIds = content.screenings.filter { Screenings.isApplicable(it, woman) }.map { it.id }
        assertEquals(listOf("any", "after40", "women"), womanIds)

        val man = Profile(age = 50, sex = "м")
        val manIds = content.screenings.filter { Screenings.isApplicable(it, man) }.map { it.id }
        assertFalse("women" in manIds)

        // Пол неизвестен — обследование не скрываем.
        val unknown = Profile(age = 50)
        assertTrue(content.screenings.filter { Screenings.isApplicable(it, unknown) }.any { it.id == "women" })
    }

    @Test
    fun `due and next date follow the period`() {
        val content = content()
        val any = content.screenings.first { it.id == "any" }
        val today = LocalDate.of(2026, 9, 9)

        assertTrue(Screenings.isDue(null, any, today))
        assertEquals(today, Screenings.nextDue(null, any, today))

        val recent = today.minusMonths(3)
        assertFalse(Screenings.isDue(recent, any, today))
        assertEquals(today.plusMonths(9), Screenings.nextDue(recent, any, today))

        val old = today.minusMonths(13)
        assertTrue(Screenings.isDue(old, any, today))
    }

    @Test
    fun `list puts due items first`() {
        val content = content()
        val today = LocalDate.of(2026, 9, 9)
        val lastDone = mapOf(
            "any" to today.minusMonths(1),   // не пора
            "after40" to null,               // пора
        )
        val list = Screenings.forProfile(
            content, Profile(age = 50, sex = "м"), today,
            lastDone = { id -> lastDone[id] },
        )
        assertTrue(list.isNotEmpty())
        assertEquals("after40", list.first().first.id)
    }
}
