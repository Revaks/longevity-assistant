package com.revaks.longevity.core

import java.time.LocalDate

/**
 * Подсчёт серий и прогресса по отметкам выполнения — чистые функции,
 * покрываются JVM-тестами. Неплановые дни серию не прерывают.
 */
object Habits {

    /**
     * Серии по пунктам: сколько подряд плановых дней пункт отмечен.
     *
     * Неплановые дни пропускаются. Если сегодняшний плановый день ещё не отмечен,
     * это не обрывает серию — считаем с предыдущего дня (успеть можно до вечера).
     *
     * @param scheduled для дня возвращает id пунктов, запланированных на этот день
     * @param done для дня возвращает id отмеченных пунктов
     */
    fun streaks(
        itemIds: Collection<String>,
        today: LocalDate,
        scheduled: (LocalDate) -> Set<String>,
        done: (LocalDate) -> Set<String>,
        maxLookbackDays: Int = 180,
    ): Map<String, Int> {
        val result = itemIds.associateWith { 0 }.toMutableMap()
        if (itemIds.isEmpty()) return result
        val active = HashSet(itemIds)
        var day = today
        var firstDay = true
        var steps = 0
        while (active.isNotEmpty() && steps <= maxLookbackDays) {
            val plannedToday = scheduled(day)
            val doneToday = done(day)
            val broken = ArrayList<String>(active.size)
            for (id in active) {
                if (id !in plannedToday) continue
                if (id in doneToday) {
                    result[id] = (result[id] ?: 0) + 1
                } else if (!firstDay) {
                    broken.add(id)
                }
            }
            active.removeAll(broken.toSet())
            firstDay = false
            day = day.minusDays(1)
            steps++
        }
        return result
    }

    /**
     * Прогресс недели по плановым пунктам: пары (сделано, всего).
     * Будущие дни недели не учитываются.
     */
    fun weekProgress(
        monday: LocalDate,
        today: LocalDate,
        itemIdsFor: (LocalDate) -> Set<String>,
        done: (LocalDate) -> Set<String>,
    ): Pair<Int, Int> {
        var total = 0
        var completed = 0
        for (i in 0 until 7) {
            val day = monday.plusDays(i.toLong())
            if (day.isAfter(today)) break
            val planned = itemIdsFor(day)
            total += planned.size
            val doneToday = done(day)
            completed += planned.count { it in doneToday }
        }
        return Pair(completed, total)
    }

    /** Прогресс по каждому дню недели: доля выполнения 0f..1f (для полосок). */
    fun dailyRatios(
        monday: LocalDate,
        today: LocalDate,
        itemIdsFor: (LocalDate) -> Set<String>,
        done: (LocalDate) -> Set<String>,
    ): List<Float> = (0 until 7).map { i ->
        val day = monday.plusDays(i.toLong())
        if (day.isAfter(today)) return@map 0f
        val planned = itemIdsFor(day)
        if (planned.isEmpty()) return@map 0f
        val doneToday = done(day)
        planned.count { it in doneToday }.toFloat() / planned.size
    }

    /**
     * Самые проблемные пункты за период: доля выполнения ниже всех
     * (учитываются пункты с не менее чем [minPlanned] запланированными днями).
     */
    fun weakSpots(
        planned: Map<String, Int>,
        done: Map<String, Int>,
        limit: Int = 3,
        minPlanned: Int = 3,
    ): List<Pair<String, Double>> = planned.entries
        .filter { it.value >= minPlanned }
        .map { entry -> entry.key to (done[entry.key] ?: 0).toDouble() / entry.value }
        .sortedWith(compareBy({ it.second }, { it.first }))
        .take(limit)
}
