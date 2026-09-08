package com.revaks.longevity.core

import org.junit.Assert.assertEquals
import org.junit.Test
import java.time.LocalDate

class ScheduleTest {

    private fun item(id: String, time: String? = null, anchor: String = "clock",
                     days: List<Int> = listOf(0)) = ScheduleItem(
        id = id, title = "Пункт $id", detail = "", cat = "Питание",
        days = days, anchor = anchor, time = time, tips = emptyList(),
    )

    @Test
    fun `displayTime maps anchors`() {
        assertEquals("06:30", Schedule.displayTime(item("a", time = "06:30")))
        assertEquals("утро", Schedule.displayTime(item("b", anchor = "morning")))
        assertEquals("весь день", Schedule.displayTime(item("c", anchor = "allday")))
    }

    @Test
    fun `timeKey orders clocks, morning and allday`() {
        assertEquals(Schedule.timeKey("06:30"), Triple(0, 6, 30))
        assertEquals(Schedule.timeKey("утро"), Triple(0, 6, 0))
        assertEquals(Schedule.timeKey("весь день"), Triple(1, 0, 0))
        // Порядок («утро» < часы < «весь день») проверяется ниже:
        // в `day plan filters by weekday and sorts` пункты с утра идут
        // перед 06:30/07:00, а «весь день» — последним.
    }

    @Test
    fun `day plan filters by weekday and sorts`() {
        val content = Content(
            tips = emptyList(), schedule = listOf(
                item("all", anchor = "allday", days = (0..6).toList()),
                item("clock0700", time = "07:00", days = listOf(0)),
                item("clock0630", time = "06:30", days = listOf(0)),
                item("morning", anchor = "morning", days = listOf(0)),
                item("tuesday", time = "09:00", days = listOf(1)),
            ),
            synonyms = emptyMap(), mindGood = emptyList(), mindLimit = emptyList(),
            menu = emptyList(), appTitle = "Т", appSubtitle = "С", disclaimer = "Д",
            categories = listOf("Питание"), catColors = emptyMap(),
            quickQuestions = emptyList(),
        )
        // Понедельник: утро, 06:30, 07:00, весь день (вторник отсеян)
        val monday = LocalDate.of(2026, 9, 7) // понедельник
        val plan = Schedule.getDayPlan(content, monday)
        assertEquals(
            listOf("morning", "clock0630", "clock0700", "all"),
            plan.map { it.id },
        )
        // Вторник: только 09:00 и весь день
        val tuesday = LocalDate.of(2026, 9, 8)
        assertEquals(
            listOf("tuesday", "all"),
            Schedule.getDayPlan(content, tuesday).map { it.id },
        )
    }
}
