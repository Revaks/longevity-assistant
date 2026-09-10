package com.revaks.longevity.core

/** Виды измерений биодневника с единицами. */
object Measures {

    data class Kind(val id: String, val title: String, val unit: String)

    val KINDS: List<Kind> = listOf(
        Kind("weight", "Вес", "кг"),
        Kind("waist", "Окружность талии", "см"),
        Kind("bp_sys", "Давление систолическое", "мм рт.ст."),
        Kind("bp_dia", "Давление диастолическое", "мм рт.ст."),
        Kind("pulse", "Пульс", "уд/мин"),
        Kind("walk6m", "Тест 6-минутной ходьбы", "м"),
        Kind("grip", "Сила хвата", "кг"),
    )

    fun kind(id: String): Kind? = KINDS.firstOrNull { it.id == id }

    /** Текст значения с единицей: «72.5 кг». */
    fun format(kindId: String, value: Double): String {
        val unit = kind(kindId)?.unit ?: ""
        val number = if (value == value.toLong().toDouble()) {
            value.toLong().toString()
        } else {
            String.format(java.util.Locale.US, "%.1f", value)
        }
        return if (unit.isEmpty()) number else "$number $unit"
    }

    /** Изменение относительно предыдущего значения: «+0.4 кг», «−1.2 кг» или «0.0 кг». */
    fun delta(kindId: String, current: Double, previous: Double): String {
        val diff = current - previous
        val sign = when {
            diff > 0.049 -> "+"
            diff < -0.049 -> "−"
            else -> ""
        }
        val unit = kind(kindId)?.unit ?: ""
        val number = String.format(java.util.Locale.US, "%.1f", kotlin.math.abs(diff))
        return "$sign$number $unit".trim()
    }
}
