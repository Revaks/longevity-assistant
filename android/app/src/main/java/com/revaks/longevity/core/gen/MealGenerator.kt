package com.revaks.longevity.core.gen

import com.revaks.longevity.core.Dates
import com.revaks.longevity.core.MenuDay
import kotlin.random.Random

/**
 * Встроенный генератор недельного меню по диете MIND.
 *
 * Каждый запуск (с новым [seed]) даёт свежий расклад на неделю. Все блюда
 * берутся из [MealCatalog], поэтому состав всегда соответствует принципам
 * питания Москалева: цельные злаки, ягоды и орехи на завтрак, бобовые,
 * птица и рыба без жарки, минимум сахара.
 */
object MealGenerator {

    /** Семь дней недели: понедельник..воскресенье. */
    fun generateMenu(seed: Long = Random.nextLong()): List<MenuDay> {
        val rnd = Random(seed)

        fun <T> pickSeven(pool: List<T>): List<T> = pool.shuffled(rnd).take(7)

        val breakfasts = pickSeven(MealCatalog.breakfasts)
        val snacks = pickSeven(MealCatalog.snacks)

        // Рыба в обедах 2–3 раза за неделю (+ возможно 1 раз в ужине).
        val fishLunchPool = MealCatalog.lunches.filter { it.fish }
        val plainLunchPool = MealCatalog.lunches.filter { !it.fish }
        val fishLunchCount = 2 + rnd.nextInt(2) // 2..3
        val fishLunches = fishLunchPool.shuffled(rnd).take(fishLunchCount)
        val plainLunches = plainLunchPool.shuffled(rnd).take(7 - fishLunchCount)
        val lunches = (fishLunches + plainLunches).shuffled(rnd)

        val fishDinnerPool = MealCatalog.dinners.filter { it.fish }
        val plainDinnerPool = MealCatalog.dinners.filter { !it.fish }
        // Если в обедах рыбы было 2 раза, добавляем 1 рыбный ужин (итого 3).
        val fishDinnerCount = if (fishLunchCount == 2) 1 else 0
        val fishDinners = fishDinnerPool.shuffled(rnd).take(fishDinnerCount)
        val plainDinners = plainDinnerPool.shuffled(rnd).take(7 - fishDinnerCount)
        val dinners = (fishDinners + plainDinners).shuffled(rnd)

        return (0 until 7).map { i ->
            MenuDay(
                day = Dates.WEEKDAYS_FULL[i],
                breakfast = breakfasts[i].name,
                lunch = lunches[i].name,
                dinner = dinners[i].name,
                snack = snacks[i].name,
            )
        }
    }

    /** Сколько рыбных приёмов (обед+ужин) в неделе — для проверок и подписей. */
    fun fishMealsCount(menu: List<MenuDay>): Int {
        val lunchNames = menu.map { it.lunch }.toSet()
        val dinnerNames = menu.map { it.dinner }.toSet()
        return MealCatalog.lunches.count { it.fish && it.name in lunchNames } +
            MealCatalog.dinners.count { it.fish && it.name in dinnerNames }
    }
}
