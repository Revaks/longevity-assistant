package com.revaks.longevity.core

import java.util.Locale

/**
 * Приведение русского текста к основам — перенос longevity/text.py.
 *
 * ВАЖНО: порядок окончаний сохранён как в Python: от длинных к коротким,
 * иначе «ами» никогда не сработает — раньше сработает «и». «ть» в списке нет
 * намеренно (см. комментарий в оригинале про слова на -ость).
 */
object Text {

    val STOPWORDS: Set<String> = setOf(
        // Вопросительные и указательные
        "что", "как", "какие", "какой", "какая", "какое", "сколько", "для", "это",
        "этот", "эта", "эти", "при", "надо", "нужно", "можно", "ли", "или", "не",
        "да", "нет", "очень", "вообще", "просто", "если", "чтобы", "почему",
        "зачем", "где", "когда", "мне", "я", "вы", "мы", "принимать", "делать",
        "сдавать", "посоветуй", "подскажи", "расскажи", "хочу", "хочется",
        // Предлоги
        "в", "на", "с", "у", "по", "к", "о", "об", "от", "до", "из", "через",
        "над", "под", "между", "перед", "после", "без", "вместо", "кроме", "вдоль",
        // Союзы и частицы
        "и", "а", "но", "то", "же", "во", "ни", "вот",
        // Порядковое числительное («2-го», «1-го»)
        "го",
    )

    // Окончания отсекаются от длинных к коротким. Список точно повторяет
    // кортеж _ENDINGS из longevity/text.py, включая «ам»/«ям» после «ах»/«ях».
    private val ENDINGS: List<String> = listOf(
        "иями", "ями", "ами", "ого", "его", "ому", "ему", "ыми", "ими",
        "ия", "ию", "ии", "ых", "их",
        "ая", "яя", "ое", "ее", "ые", "ие", "ой", "ей", "ом", "ем", "ах", "ях",
        "ам", "ям", // дательный падеж множественного числа
        "ов", "ев", "ий", "ый", "ую", "юю", "ся",
        "а", "я", "о", "е", "ы", "и", "у", "ю", "й", "ь",
    )

    // Основа короче трёх символов перестаёт различать слова.
    private const val MIN_STEM = 3

    // Слова с беглой гласной: полный набор форм семьи «сон».
    private val FLEETING_VOWEL_MAP = mapOf(
        "сон" to "сон", "сна" to "сон", "сну" to "сон", "сном" to "сон", "сне" to "сон",
    )

    private fun isWordChar(ch: Char): Boolean =
        ch in 'a'..'z' || ch in 'A'..'Z' || ch in 'а'..'я' || ch in 'А'..'Я' || ch in '0'..'9'

    /** Нижний регистр, ё как е, всё несловесное — пробел (аналог normalize). */
    fun normalize(text: String): String {
        val lower = text.lowercase(Locale.ROOT).replace('ё', 'е')
        val sb = StringBuilder(lower.length)
        for (ch in lower) sb.append(if (isWordChar(ch)) ch else ' ')
        // Python заменяет серии несловесных символов одним пробелом — то же самое.
        return sb.toString().split(' ').filter { it.isNotEmpty() }.joinToString(" ")
    }

    fun tokenize(text: String): List<String> =
        normalize(text).split(' ').filter { it.isNotEmpty() }

    /** Грубое отсечение русских окончаний с защитой от схлопывания основы. */
    fun stem(token: String): String {
        FLEETING_VOWEL_MAP[token]?.let { return it }
        for (ending in ENDINGS) {
            if (token.endsWith(ending) && token.length - ending.length >= MIN_STEM) {
                return token.substring(0, token.length - ending.length)
            }
        }
        return token
    }

    /** Полный разбор: токены без стоп-слов, приведённые к основам. */
    fun analyze(text: String): List<String> =
        tokenize(text).filter { it !in STOPWORDS }.map { stem(it) }
}
