package com.revaks.longevity.core

/** Русские названия дней недели и подписи дат (аналоги ui/app.py). */
object Dates {
    /** Короткие названия, индекс как dayOfWeek.value - 1 (Пн=0). */
    val WEEKDAYS = listOf("Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс")

    /** Полные названия: Понедельник..Воскресенье. */
    val WEEKDAYS_FULL = listOf(
        "Понедельник", "Вторник", "Среда", "Четверг",
        "Пятница", "Суббота", "Воскресенье",
    )

    fun mondayOf(date: java.time.LocalDate): java.time.LocalDate =
        date.minusDays((date.dayOfWeek.value - 1).toLong())

    /** «Пн 08.09» — подпись дня в сетке календаря. */
    fun fmtDay(day: java.time.LocalDate): String {
        val wd = day.dayOfWeek.value - 1
        val dd = "%02d".format(day.dayOfMonth)
        val mm = "%02d".format(day.monthValue)
        return "${WEEKDAYS[wd]} $dd.$mm"
    }

    /** «Среда, 08.09.2026» — полная подпись выбранного дня. */
    fun fmtDayFull(day: java.time.LocalDate): String {
        val wd = day.dayOfWeek.value - 1
        val dd = "%02d".format(day.dayOfMonth)
        val mm = "%02d".format(day.monthValue)
        return "${WEEKDAYS_FULL[wd]}, $dd.$mm.${day.year}"
    }

    /** ISO-строка даты: как date.isoformat() в Python. */
    fun iso(day: java.time.LocalDate): String = day.toString()
}
