package com.revaks.longevity.core

import java.time.LocalDate

/**
 * Логика профилактических обследований: применимость по возрасту и полу,
 * следующая дата и «пора ли». Отметки о прохождении хранятся в профиле.
 */
object Screenings {

    /**
     * Относится ли обследование к пользователю.
     * Пол неизвестен — показываем (интерфейс добавит подсказку уточнить профиль).
     */
    fun isApplicable(screening: Screening, profile: Profile): Boolean {
        val age = profile.age
        if (age != null && age < screening.ageMin) return false
        val sex = profile.sex
        if (screening.sex != null && sex != null && screening.sex != sex) return false
        return true
    }

    /** Следующая дата обследования; без отметки — «пора сейчас». */
    fun nextDue(lastDone: LocalDate?, screening: Screening, today: LocalDate): LocalDate =
        lastDone?.plusMonths(screening.periodMonths.toLong()) ?: today

    /** Пора ли проходить (не проходили или срок вышел). */
    fun isDue(lastDone: LocalDate?, screening: Screening, today: LocalDate): Boolean {
        if (lastDone == null) return true
        return !lastDone.plusMonths(screening.periodMonths.toLong()).isAfter(today)
    }

    /** Применимые обследования, сначала те, что пора проходить. */
    fun forProfile(
        content: Content,
        profile: Profile,
        today: LocalDate,
        lastDone: (String) -> LocalDate?,
    ): List<Triple<Screening, LocalDate?, Boolean>> =
        content.screenings
            .filter { isApplicable(it, profile) }
            .map { Triple(it, lastDone(it.id), isDue(lastDone(it.id), it, today)) }
            .sortedWith(
                compareBy(
                    { (_, _, due) -> if (due) 0 else 1 },
                    { (screening, last, _) -> nextDue(last, screening, today) },
                    { (screening, _, _) -> screening.id },
                )
            )
}
