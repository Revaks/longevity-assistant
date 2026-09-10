package com.revaks.longevity.core

import org.json.JSONArray
import org.json.JSONObject

/**
 * Построение JSON-фикстур для тестов ядра — маленькие «честные» данные,
 * которые должны проходить ContentLoader целиком.
 */
object Fixtures {

    fun obj(vararg pairs: Pair<String, Any?>): String = jobj(*pairs).toString()

    /** Сырой JSONObject (для вложения в obj, а не строки). */
    fun jobj(vararg pairs: Pair<String, Any?>): JSONObject {
        val o = JSONObject()
        for ((k, v) in pairs) o.put(k, v ?: JSONObject.NULL)
        return o
    }

    fun arr(vararg values: Any?): JSONArray {
        val a = JSONArray()
        for (v in values) a.put(v ?: JSONObject.NULL)
        return a
    }

    private val defaultCategories = listOf("Питание", "Образ жизни")

    fun metaJson(categories: List<String> = defaultCategories): String = obj(
        "app_title" to "Ассистент долголетия",
        "app_subtitle" to "по книге",
        "disclaimer" to "Дисклеймер",
        "categories" to JSONArray(categories),
        "cat_colors" to JSONObject().put("Питание", "#e65100").put("Образ жизни", "#2e7d32"),
        "quick_questions" to JSONArray(),
    )

    fun tip(
        id: String = "t1",
        cat: String = "Питание",
        title: String = "Есть рыбу дважды в неделю",
        text: String = "Жирная рыба полезна для сердца и сосудов.",
        sched: String = "2 раза в неделю",
        source: String = "Глава «Питание»",
        tags: String = "рыба омега жиры",
        ageMin: Any? = null,
        rx: Boolean = false,
    ): String = obj(
        "id" to id, "cat" to cat, "title" to title, "text" to text, "sched" to sched,
        "source" to source, "tags" to tags, "age_min" to ageMin, "rx" to rx,
    )

    /** Список JSON-объектов из готовых строк: элементы обязаны быть объектами. */
    fun rowsJson(vararg rows: String): String {
        val arr = JSONArray()
        for (row in rows) arr.put(JSONObject(row))
        return arr.toString()
    }

    fun tipsJson(vararg tips: String): String = rowsJson(*tips)

    fun scheduleItem(
        id: String = "fish_day",
        title: String = "Ужин с рыбой",
        detail: String = "Омега-3 (совет t1).",
        cat: String = "Питание",
        days: List<Int> = listOf(0, 2, 4),
        anchor: String = "clock",
        time: String? = "19:00",
        tips: List<String> = listOf("t1"),
    ): String = obj(
        "id" to id, "title" to title, "detail" to detail, "cat" to cat,
        "days" to JSONArray(days), "anchor" to anchor, "time" to time,
        "tips" to JSONArray(tips),
    )

    fun scheduleJson(vararg items: String): String = rowsJson(*items)

    fun synonymsJson(vararg pairs: Pair<String, String>): String {
        val o = JSONObject()
        for ((k, v) in pairs) o.put(k, v)
        return o.toString()
    }

    fun mindJson(): String = obj("good" to JSONArray(), "limit" to JSONArray(), "menu" to JSONArray())

    fun booksJson(
        books: String = obj("id" to "b1", "title" to "Книга", "subtitle" to "Подзаголовок", "author" to "А. Автор"),
        passages: String = obj(
            "id" to "p1", "book" to "b1", "section" to "Глава 1",
            "text" to "Сон и мозг: ночью мозг очищается от токсинов.",
        ),
    ): String = obj(
        "version" to 1,
        "books" to JSONArray().put(JSONObject(books)),
        "passages" to JSONArray().put(JSONObject(passages)),
    )

    /** Полный валидный набор данных по умолчанию. */
    fun content(
        tipsJson: String = tipsJson(tip()),
        scheduleJson: String = scheduleJson(scheduleItem()),
        synonymsJson: String = synonymsJson("рыба" to "рыба омега"),
        booksJson: String = booksJson(),
        // По умолчанию ротация пустая: фикстуры со своим расписанием не должны
        // зависеть от ссылок на пункты «настоящих» данных.
        extras: String = extrasJson(rotations = "[]"),
    ): Content = ContentLoader.buildContent(
        JsonFiles(
            tips = tipsJson,
            schedule = scheduleJson,
            synonyms = synonymsJson,
            mind = mindJson(),
            meta = metaJson(),
            books = booksJson,
            extras = extras,
        )
    )

    fun rotation(
        itemId: String = "fish_day",
        variants: String = rowsJson(
            obj("level" to 0, "title" to "Вариант А", "detail" to "деталь А"),
            obj("level" to 1, "title" to "Вариант Б", "detail" to "деталь Б"),
        ),
    ): String = obj("item_id" to itemId, "variants" to JSONArray(variants))

    fun focusWeek(
        id: String = "f1",
        title: String = "Фокус недели",
        detail: String = "Описание фокуса",
        tasks: List<String> = listOf("задание 1", "задание 2", "задание 3"),
    ): String = obj(
        "id" to id, "title" to title, "detail" to detail,
        "tasks" to JSONArray(tasks),
    )

    fun screening(
        id: String = "s1",
        title: String = "Обследование",
        detail: String = "деталь",
        periodMonths: Int = 12,
        ageMin: Int = 40,
        sex: Any? = null,
    ): String = obj(
        "id" to id, "title" to title, "detail" to detail,
        "period_months" to periodMonths, "age_min" to ageMin, "sex" to sex,
    )

    fun extrasJson(
        rotations: String = rowsJson(rotation()),
        focus: String = rowsJson(focusWeek()),
        screenings: String = rowsJson(screening()),
    ): String = obj(
        "rotations" to JSONArray(rotations),
        "focus" to JSONArray(focus),
        "screenings" to JSONArray(screenings),
    )
}
