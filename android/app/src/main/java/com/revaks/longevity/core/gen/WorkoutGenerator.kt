package com.revaks.longevity.core.gen

import com.revaks.longevity.core.Dates
import kotlin.random.Random

/** Один пункт дня программы тренировок. */
data class WorkoutRow(
    val time: String,     // «утро», «07:30», «весь день»
    val title: String,
    val detail: String = "",
)

/** Программа тренировок: для каждого дня недели — список пунктов. */
data class WorkoutProgram(
    val level: String,
    val rowsByDay: List<Pair<String, List<WorkoutRow>>>,
)

/**
 * Встроенный генератор недельной программы тренировок.
 *
 * Схема повторяет рекомендации А. А. Москалева: аэробная нагрузка
 * 30–60 минут 3–5 раз в неделю, силовые упражнения на основные группы мышц
 * 2 раза в неделю, ежедневная умеренная активность (ходьба).
 */
object WorkoutGenerator {

    val LEVELS = listOf("Легкий старт", "Умеренный", "Продвинутый")

    private val walkIntro = listOf(
        "Интенсивная ходьба в темпе разговора",
        "Быстрая ходьба с махами руками",
        "Скандинавская ходьба",
    )

    private val cardioEasy = listOf(
        "Ходьба или велосипед 30–40 минут",
        "Плавание 30 минут в спокойном темпе",
        "Лёгкий бег трусцой 20–30 минут",
    )

    private val cardioMid = listOf(
        "Бег трусцой 30–40 минут",
        "Велосипед 40–50 минут",
        "Плавание 40 минут",
    )

    private val cardioHard = listOf(
        "Интервалы: 8×1 мин быстрый темп / 1 мин спокойно",
        "Бег 45–60 минут в умеренном темпе",
        "Велосипед или гребля 45–60 минут",
    )

    private val strengthBasic = listOf(
        "Приседания — 3×12",
        "Отжимания от стола или пола — 3×8–10",
        "Выпады на месте — 3×10 на ногу",
    )

    private val strengthMid = listOf(
        "Приседания с гантелями — 4×12",
        "Отжимания — 4×10–12",
        "Тяга гантели в наклоне — 3×12",
        "Планка 3×40 секунд",
    )

    private val strengthHard = listOf(
        "Приседания со штангой/гантелями — 5×8",
        "Жим гантелей лёжа — 4×10",
        "Тяга в наклоне — 4×10",
        "Выпады с гантелями — 3×12",
        "Подъём корпуса на пресс — 3×15",
    )

    private val stretch = listOf(
        "Растяжка после тренировки — 10 минут",
        "Дыхательная гимнастика — 5 минут",
    )

    fun generate(level: String = LEVELS[1], seed: Long = Random.nextLong()): WorkoutProgram {
        val rnd = Random(seed)
        fun pick(list: List<String>): String = list[rnd.nextInt(list.size)]
        val walk = pick(walkIntro)
        val cooldown = pick(stretch)

        val baseAero = when (level) {
            LEVELS[0] -> cardioEasy
            LEVELS[2] -> cardioHard
            else -> cardioMid
        }
        val baseStrength = when (level) {
            LEVELS[0] -> strengthBasic
            LEVELS[2] -> strengthHard
            else -> strengthMid
        }

        fun aero(): WorkoutRow = WorkoutRow("07:30", "Аэробная нагрузка", pick(baseAero))
        fun strengthDay(n: Int): WorkoutRow =
            WorkoutRow("18:00", "Силовая тренировка №$n", pick(baseStrength))

        // Понедельник..Воскресенье: два силовых дня + 3–4 аэробных + прогулка.
        val days = List(7) { dayIndex ->
            val dayName = Dates.WEEKDAYS_FULL[dayIndex]
            val rows = when (dayIndex) {
                0 -> listOf(aero())
                1 -> listOf(strengthDay(1), WorkoutRow("", "Прогулка", walk))
                2 -> listOf(aero())
                3 -> listOf(WorkoutRow("", "Активный отдых", "Ходьба и растяжка"))
                4 -> listOf(strengthDay(2))
                5 -> listOf(aero())
                else -> listOf(WorkoutRow("", "Восстановление", walk))
            }
            dayName to rows.map { it.copy(detail = if (it.detail.isNotEmpty()) "${it.detail}. $cooldown." else cooldown) }
        }
        return WorkoutProgram(level = level, rowsByDay = days)
    }
}
