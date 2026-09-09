package com.revaks.longevity.core.gen

import com.revaks.longevity.core.Dates
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class GeneratorTest {

    @Test
    fun `menu has seven days monday to sunday with filled slots`() {
        val menu = MealGenerator.generateMenu(seed = 1L)
        assertEquals(7, menu.size)
        assertEquals(Dates.WEEKDAYS_FULL, menu.map { it.day })
        menu.forEach { day ->
            assertTrue(day.breakfast.isNotBlank())
            assertTrue(day.lunch.isNotBlank())
            assertTrue(day.dinner.isNotBlank())
            assertTrue(day.snack.isNotBlank())
        }
    }

    @Test
    fun `menu slots are distinct inside a week`() {
        val menu = MealGenerator.generateMenu(seed = 42L)
        listOf(menu.map { it.breakfast }, menu.map { it.lunch },
            menu.map { it.dinner }, menu.map { it.snack }).forEach {
            assertEquals("повторы в слоте: $it", 7, it.toSet().size)
        }
    }

    @Test
    fun `menu contains fish 2 to 3 meals per week`() {
        for (seed in 0L..40L) {
            val count = MealGenerator.fishMealsCount(MealGenerator.generateMenu(seed))
            assertTrue("seed=$seed fish=$count", count in 2..3)
        }
    }

    @Test
    fun `same seed gives same menu, different seeds differ`() {
        assertEquals(MealGenerator.generateMenu(7L), MealGenerator.generateMenu(7L))
        val a = MealGenerator.generateMenu(7L)
        val b = MealGenerator.generateMenu(8L)
        assertNotEquals(a, b)
    }

    @Test
    fun `workout program covers week with aerobic and two strength days`() {
        for (level in WorkoutGenerator.LEVELS) {
            val program = WorkoutGenerator.generate(level = level, seed = 5L)
            assertEquals(7, program.rowsByDay.size)
            assertEquals(Dates.WEEKDAYS_FULL, program.rowsByDay.map { it.first })

            val strengthDays = program.rowsByDay
                .flatMap { it.second }.count { it.title.startsWith("Силовая") }
            assertEquals("level=$level", 2, strengthDays)

            val aeroDays = program.rowsByDay.count { day ->
                day.second.any { it.title.contains("Аэробная") }
            }
            assertTrue("level=$level aero=$aeroDays", aeroDays >= 3)
        }
    }

    @Test
    fun `workout same seed deterministic`() {
        assertEquals(
            WorkoutGenerator.generate("Умеренный", seed = 9L),
            WorkoutGenerator.generate("Умеренный", seed = 9L),
        )
    }
}
