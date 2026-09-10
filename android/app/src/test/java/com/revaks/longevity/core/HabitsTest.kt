package com.revaks.longevity.core

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import java.time.LocalDate

/** Серии, прогресс недели и проблемные пункты. */
class HabitsTest {

    @Test
    fun `streak counts consecutive scheduled days and skips other days`() {
        val today = LocalDate.of(2026, 9, 9)
        // Пункт запланирован по нечётным дням: 9, 7, 5, 3 сентября.
        val scheduled: (LocalDate) -> Set<String> = { day ->
            if (day.dayOfMonth % 2 == 1) setOf("a") else emptySet()
        }
        val done: (LocalDate) -> Set<String> = { day ->
            when (day.dayOfMonth) {
                9, 7, 5 -> setOf("a")
                else -> emptySet()
            }
        }
        assertEquals(3, Habits.streaks(listOf("a"), today, scheduled, done)["a"])
    }

    @Test
    fun `today not done yet does not break the streak`() {
        val today = LocalDate.of(2026, 9, 9)
        val scheduled: (LocalDate) -> Set<String> = { setOf("a") }
        val done: (LocalDate) -> Set<String> = { day ->
            if (day.isBefore(today)) setOf("a") else emptySet()
        }
        assertEquals(180, Habits.streaks(listOf("a"), today, scheduled, done)["a"])
    }

    @Test
    fun `missed scheduled day breaks the streak`() {
        val today = LocalDate.of(2026, 9, 9)
        val scheduled: (LocalDate) -> Set<String> = { setOf("a") }
        val done: (LocalDate) -> Set<String> = { day ->
            // Пропущено 8 сентября.
            if (day.dayOfMonth == 8) emptySet() else setOf("a")
        }
        assertEquals(1, Habits.streaks(listOf("a"), today, scheduled, done)["a"])
    }

    @Test
    fun `streak is zero when never done`() {
        val today = LocalDate.of(2026, 9, 9)
        val scheduled: (LocalDate) -> Set<String> = { setOf("a") }
        val done: (LocalDate) -> Set<String> = { emptySet() }
        assertEquals(0, Habits.streaks(listOf("a"), today, scheduled, done)["a"])
    }

    @Test
    fun `week progress counts only planned and ignores future days`() {
        val monday = LocalDate.of(2026, 9, 7)
        val today = LocalDate.of(2026, 9, 9) // среда
        val plannedByDay = mapOf(
            monday to setOf("a", "b"),
            monday.plusDays(1) to setOf("a"),
            monday.plusDays(2) to setOf("a", "b"),
            monday.plusDays(3) to setOf("a"), // будущее — не считаем
        )
        val doneByDay = mapOf(
            monday to setOf("a"),
            monday.plusDays(1) to setOf("a"),
            monday.plusDays(2) to emptySet(),
        )
        val (done, total) = Habits.weekProgress(
            monday, today,
            itemIdsFor = { plannedByDay[it] ?: emptySet() },
            done = { doneByDay[it] ?: emptySet() },
        )
        assertEquals(2, done)
        assertEquals(5, total)

        val ratios = Habits.dailyRatios(
            monday, today,
            itemIdsFor = { plannedByDay[it] ?: emptySet() },
            done = { doneByDay[it] ?: emptySet() },
        )
        assertEquals(7, ratios.size)
        assertEquals(0.5f, ratios[0])
        assertEquals(1f, ratios[1])
        assertEquals(0f, ratios[2])
        assertEquals(0f, ratios[5]) // будущий день
    }

    @Test
    fun `weak spots are sorted by completion ratio`() {
        val planned = mapOf("a" to 10, "b" to 10, "c" to 10, "rare" to 1)
        val done = mapOf("a" to 9, "b" to 2, "c" to 5, "rare" to 0)
        val weak = Habits.weakSpots(planned, done, limit = 3, minPlanned = 3)
        assertEquals(listOf("b", "c", "a"), weak.map { it.first })
        assertTrue(weak.all { it.second <= 0.9 })
    }
}
