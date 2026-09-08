package com.revaks.longevity.core

import java.time.LocalDate

/**
 * Офлайн-логика «Умного ассистента» — перенос ui/assistant_page.py.
 *
 * Отвечает по базе знаний без сети: расписание, советы, отрывки книг (BM25).
 * Путь с локальной нейросетью Ollama на Android не переносится — там негде
 * запустить Ollama; при необходимости удалённый сервер добавляется отдельно.
 */

// Основы для распознавания темы вопроса — см. комментарии в assistant_page.py.
private val PLAN_STEMS = setOf("план", "сегодн", "расписан", "режим", "дня", "график")
private val CALENDAR_STEMS = setOf("календар", "недел")
private val NUTRITION_STEMS = setOf("mind", "питан", "еда", "ест")
private val NUTRITION_WORDS = setOf("меню")

object AssistantEngine {

    fun greet(): String =
        "Здравствуйте! Я — ассистент по книгам Алексея Москалева: " +
            "«120 лет жизни», «Мозг долгожителя» и «Кишечник долгожителя».\n" +
            "Спросите меня про питание, сон, спорт, добавки, мозг или " +
            "кишечник — отвечу по книгам или найду ответ в них."

    fun fallback(content: Content): String =
        "Не нашёл точного совета в книге. Попробуйте спросить иначе, например:\n" +
            "• «Как спать?»\n" +
            "• «Что есть, чтобы жить дольше?»\n" +
            "• «Какие добавки полезны?»\n" +
            "• «Какие анализы сдавать?»\n" +
            "• «План на сегодня»\n" +
            "Или откройте раздел «База знаний» — там все ${content.tips.size} советов из книги."

    /**
     * Офлайн-ответ на вопрос — аналог AssistantPage._answer().
     * Сначала расписание (неделя/день), затем советы BM25, затем книги.
     */
    fun answer(
        content: Content,
        index: SearchIndex,
        bookSearch: BookSearch,
        query: String,
        today: LocalDate = LocalDate.now(),
    ): String {
        val terms = Text.analyze(query).toSet()

        // «Расписание на неделю» подходит под оба набора — более узкое
        // требование (неделя) выигрывает, как и в десктопной версии.
        if (terms.any { it in CALENDAR_STEMS }) return weekPlan(content, today)

        if (terms.any { it in PLAN_STEMS }) return dayPlan(content, today)

        val tips = index.search(query, limit = 4).map { it.tip }
        if (tips.isNotEmpty()) return formatTips(tips)

        val hits = bookSearch.search(query, limit = 2)
        return if (hits.isNotEmpty()) formatBookExcerpts(content, hits)
        else fallback(content)
    }

    /** Текст «План на сегодня» для дня — аналог _day_plan. */
    fun dayPlan(content: Content, day: LocalDate): String {
        val wd = day.dayOfWeek.value - 1
        val sb = StringBuilder()
        sb.append(
            "План на ${Dates.WEEKDAYS_FULL[wd].lowercase()}, " +
                "%02d.%02d (по книге Москалева):\n".format(day.dayOfMonth, day.monthValue)
        )
        for (item in Schedule.getDayPlan(content, day)) {
            sb.append("• ${Schedule.displayTime(item)} — ${item.title}\n")
            if (item.detail.isNotEmpty()) sb.append("   ${item.detail}\n")
        }
        sb.append("\nПолный календарь — на вкладке «Календарь».")
        return sb.toString()
    }

    /** Расписание на текущую неделю — аналог _week_plan. */
    fun weekPlan(content: Content, today: LocalDate): String {
        val monday = Dates.mondayOf(today)
        val sb = StringBuilder("Расписание на текущую неделю:\n\n")
        for (i in 0 until 7) {
            val day = monday.plusDays(i.toLong())
            val titles = Schedule.getDayPlan(content, day).joinToString(", ") { it.title }
            sb.append(
                "${Dates.WEEKDAYS[i]} %02d.%02d: %s.\n".format(
                    day.dayOfMonth, day.monthValue, titles
                )
            )
        }
        return sb.toString().trimEnd()
    }

    private fun formatTips(tips: List<Tip>): String {
        val sb = StringBuilder("Вот что советует А. А. Москалев:\n")
        tips.forEachIndexed { i, tip ->
            sb.append("${i + 1}. ${tip.title}\n")
            sb.append("   ${tip.text}\n")
            sb.append("   Когда: ${tip.sched}\n")
            sb.append("   Источник: ${tip.source}\n\n")
        }
        sb.append(
            "Подробнее — в разделе «База знаний». " +
                "Лекарства и добавки — только по назначению врача."
        )
        return sb.toString()
    }

    private fun formatBookExcerpts(content: Content, hits: List<BookHit>): String {
        val sb = StringBuilder("Вот что пишет А. А. Москалев в книгах:\n")
        hits.forEachIndexed { i, hit ->
            sb.append("${i + 1}. Источник: ${Formatting.passageReference(hit.passage, content)}\n")
            sb.append("   ${Formatting.truncatePassage(hit.passage.text)}\n\n")
        }
        sb.append(
            "Подробнее — раздел «База знаний», вкладка «Книги». " +
                "Лекарства и добавки — только по назначению врача."
        )
        return sb.toString()
    }

    /** Спрашивают ли про питание — по основам плюс словоформа «меню». */
    fun isAboutNutrition(query: String): Boolean =
        Text.analyze(query).any { it in NUTRITION_STEMS } ||
            Text.tokenize(query).any { it in NUTRITION_WORDS }
}
