package com.revaks.longevity.llm

import com.revaks.longevity.core.BookSearch
import com.revaks.longevity.core.Content
import com.revaks.longevity.core.SearchIndex

/**
 * Сборка RAG-промптов: в контекст модели подставляются реальные данные
 * приложения — советы, правила MIND и отрывки книг, найденные BM25.
 * Так нейросеть отвечает «по книгам», а не по общим знаниям.
 */
object GroundedPrompts {

    private const val TIP_LIMIT = 6
    private const val PASSAGE_LIMIT = 3
    private const val PASSAGE_CHARS = 600

    private fun mindRules(content: Content): String {
        val good = content.mindGood.joinToString("\n") { "- ${it.name}: ${it.amount} (${it.note})" }
        val limit = content.mindLimit.joinToString("\n") { "- ${it.name}: ${it.amount}" }
        return buildString {
            append("Полезные группы диеты MIND:\n").append(good)
            if (limit.isNotBlank()) append("\nОграничить:\n").append(limit)
        }
    }

    private fun tipLines(content: Content, index: SearchIndex, query: String): String {
        val hits = index.search(query, limit = TIP_LIMIT)
        return if (hits.isEmpty()) ""
        else hits.joinToString("\n") { hit ->
            val t = hit.tip
            "- ${t.title} [${t.cat}]: ${t.text} Когда: ${t.sched}"
        }
    }

    private fun passageLines(content: Content, bookSearch: BookSearch?, query: String): String {
        if (bookSearch == null) return ""
        val hits = bookSearch.search(query, limit = PASSAGE_LIMIT)
        return if (hits.isEmpty()) ""
        else hits.joinToString("\n") { hit ->
            val p = hit.passage
            val book = content.books.firstOrNull { it.id == p.book }?.title ?: p.book
            val section = if (p.section.isNotEmpty()) ", раздел «${p.section}»" else ""
            val text = if (p.text.length > PASSAGE_CHARS) p.text.take(PASSAGE_CHARS) + "…" else p.text
            "- Из книги «$book»$section: $text"
        }
    }

    private fun contextBlock(content: Content, index: SearchIndex, bookSearch: BookSearch?, query: String): String {
        val blocks = listOfNotNull(
            tipLines(content, index, query).takeIf { it.isNotBlank() },
            passageLines(content, bookSearch, query).takeIf { it.isNotBlank() },
        )
        return blocks.joinToString("\n")
    }

    /** Промпт для генерации меню: правила MIND + релевантные советы/книги. */
    fun menuPrompt(content: Content, index: SearchIndex, bookSearch: BookSearch?): String {
        val knowledge = contextBlock(
            content, index, bookSearch,
            "питание рыба омега овощи ягоды орехи оливковое масло злаки",
        )
        return buildString {
            append(
                "Ты — диетолог, специалист по диете MIND и принципам питания " +
                    "А. А. Москалева. Составь меню на 7 дней строго по приведённому ниже " +
                    "контексту из книг.\n\n"
            )
            append("КОНТЕКСТ (правила MIND, советы и книги):\n")
            append(mindRules(content))
            append("\n")
            append(knowledge)
            append(
                "\n\nОТВЕТ: только JSON-массив из 7 объектов с ключами " +
                    "day, breakfast, lunch, dinner, snack. Без текста вокруг."
            )
        }
    }

    /** Промпт для программы тренировок на неделю. */
    fun workoutPrompt(content: Content, index: SearchIndex, bookSearch: BookSearch?, level: String): String {
        val knowledge = contextBlock(
            content, index, bookSearch,
            "тренировка нагрузка аэробная силовые упражнения ходьба бег активность",
        )
        return buildString {
            append(
                "Ты — тренер по оздоровительной физкультуре по принципам " +
                    "А. А. Москалева (аэробная 30–60 минут 3–5 раз в неделю, силовые 2 раза, " +
                    "ежедневная активность). Составь программу на неделю для уровня: $level. " +
                    "Отвечай строго по контексту из книг.\n\n"
            )
            append("КОНТЕКСТ (советы и книги):\n")
            append(if (knowledge.isBlank()) "Контекст не найден." else knowledge)
            append("\n\nДля каждого дня недели (Понедельник..Воскресенье) напиши день, время " +
                "и конкретные упражнения. По-русски, кратко, списком.")
        }
    }

    /** Промпт ассистента: запрос + релевантный контекст из базы знаний. */
    fun chatPrompt(content: Content, index: SearchIndex, bookSearch: BookSearch?, query: String): String {
        val knowledge = contextBlock(content, index, bookSearch, query)
        val nutritionBlock = if (knowledge.isBlank() || query.lowercase().contains("диет") ||
            query.lowercase().contains("меню") || query.lowercase().contains("ест")
        ) mindRules(content) else ""
        return buildString {
            append(
                "Ты — «Ассистент долголетия», помощник по книгам А. А. Москалева и диете MIND. " +
                    "Отвечай по-русски, кратко, только по приведённому контексту. " +
                    "Если в контексте нет ответа — честно скажи об этом. " +
                    "Не выдумывай исследования; лекарства и добавки — только по назначению врача.\n\n"
            )
            append("КОНТЕКСТ (советы, книги, MIND):\n")
            append(if (knowledge.isBlank() && nutritionBlock.isBlank()) "Контекст не найден."
            else listOf(knowledge, nutritionBlock).filter { it.isNotBlank() }.joinToString("\n"))
            append("\n\nВОПРОС ПОЛЬЗОВАТЕЛЯ: ").append(query)
        }
    }
}
