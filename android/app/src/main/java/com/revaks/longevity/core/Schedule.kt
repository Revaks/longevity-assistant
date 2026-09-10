package com.revaks.longevity.core

import java.time.LocalDate

/**
 * Порядок и подписи пунктов расписания на конкретный день —
 * перенос longevity/schedule.py.
 */
object Schedule {

    private val CLOCK_RE = Regex("^(\\d{1,2}):(\\d{2})$")

    /** Текст времени для пункта расписания: «06:30», «утро» или «весь день». */
    fun displayTime(item: ScheduleItem): String = when (item.anchor) {
        "clock" -> item.time ?: ""
        "morning" -> "утро"
        else -> "весь день"
    }

    /** Ключ сортировки по подписи: часы первыми, «весь день» — последним. */
    fun timeKey(time: String): Triple<Int, Int, Int> {
        val m = CLOCK_RE.matchEntire(time)
        return if (m != null) {
            Triple(0, m.groupValues[1].toInt(), m.groupValues[2].toInt())
        } else if (time.startsWith("утро")) {
            Triple(0, 6, 0)
        } else {
            Triple(1, 0, 0)
        }
    }

    /**
     * Пункты расписания на конкретную дату в порядке показа.
     * Дни недели нумеруются как в Python: понедельник = 0.
     */
    fun getDayPlan(content: Content, day: LocalDate): List<ScheduleItem> {
        val wd = day.dayOfWeek.value - 1 // ISO: Пн=1..Вс=7 -> 0..6
        return content.schedule
            .filter { wd in it.days }
            .sortedWith { a, b ->
                compareBy<ScheduleItem>(
                    { timeKey(displayTime(it)).first },
                    { timeKey(displayTime(it)).second },
                    { timeKey(displayTime(it)).third },
                    { it.id },
                ).compare(a, b)
            }
    }
}
