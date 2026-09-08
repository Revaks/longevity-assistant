package com.revaks.longevity.core

import org.json.JSONArray
import org.json.JSONObject

/** Данные приложения противоречивы и работать с ними нельзя. */
class ContentError(message: String) : Exception(message)

/**
 * Сырые тексты JSON-файлов приложения — те же данные, что у десктопа.
 * Имена ключей совпадают с именами файлов для сообщений об ошибках.
 */
data class JsonFiles(
    val tips: String,
    val schedule: String,
    val synonyms: String,
    val mind: String,
    val meta: String,
    val books: String,
)

/**
 * Разбор JSON и проверка целостности — порт longevity/content.py.
 *
 * Функция не зависит от Android: файлы читает вызывающий код, сюда приходят
 * уже строки. Поэтому ядро покрывается обычными JVM-тестами.
 */
object ContentLoader {

    private val ANCHORS = setOf("clock", "morning", "allday")

    fun buildContent(files: JsonFiles): Content {
        val metaObj = obj(files.meta, "meta.json")
        val categories = strList(field(metaObj, "categories", "list", "meta.json"), "meta.json")
        val tipRows = records(files.tips, "tips.json")
        val tips = tipRows.mapIndexed { i, rec -> buildTip(rec, i) }
        checkTips(tips, categories)

        val scheduleRows = records(files.schedule, "schedule.json")
        val schedule = scheduleRows.mapIndexed { i, rec -> buildItem(rec, i) }
        checkSchedule(schedule, tips.map { it.id }.toSet())

        val synObj = obj(files.synonyms, "synonyms.json")
        val synonyms = LinkedHashMap<String, String>()
        synObj.keys().forEach { key ->
            val v = synObj.opt(key)
            if (v !is String) {
                throw ContentError("synonyms.json: значение '$key' должно быть строкой")
            }
            synonyms[key] = v
        }

        val (books, passages) = buildBooks(files.books)

        val mindObj = obj(files.mind, "mind.json")
        val goodRows = list(field(mindObj, "good", "list", "mind.json"), "mind.json, good")
        val limitRows = list(field(mindObj, "limit", "list", "mind.json"), "mind.json, limit")
        val menuRows = list(field(mindObj, "menu", "list", "mind.json"), "mind.json, menu")

        return Content(
            tips = tips,
            schedule = schedule,
            synonyms = synonyms,
            mindGood = goodRows.mapIndexed { i, r -> buildMindGroup(r, i, "good") },
            mindLimit = limitRows.mapIndexed { i, r -> buildMindGroup(r, i, "limit") },
            menu = menuRows.mapIndexed { i, r -> buildMenuDay(r, i) },
            appTitle = str(field(metaObj, "app_title", "str", "meta.json"), "app_title", "meta.json"),
            appSubtitle = str(field(metaObj, "app_subtitle", "str", "meta.json"), "app_subtitle", "meta.json"),
            disclaimer = str(field(metaObj, "disclaimer", "str", "meta.json"), "disclaimer", "meta.json"),
            categories = categories,
            catColors = strMap(field(metaObj, "cat_colors", "dict", "meta.json"), "meta.json", "cat_colors"),
            quickQuestions = strList(field(metaObj, "quick_questions", "list", "meta.json"), "meta.json"),
            books = books,
            passages = passages,
        )
    }

    // ------------------------------------------------------------------ helpers

    private fun obj(text: String, where: String): JSONObject = try {
        JSONObject(text)
    } catch (e: Exception) {
        throw ContentError("$where: файл данных не читается (${e.message})")
    }

    private fun records(text: String, where: String): List<Any> = try {
        val arr = JSONArray(text)
        (0 until arr.length()).map { arr.get(it) }
    } catch (e: ContentError) {
        throw e
    } catch (e: Exception) {
        throw ContentError("$where: файл данных не читается (${e.message})")
    }

    private fun list(value: Any?, where: String): List<Any> {
        if (value !is JSONArray) throw ContentError("$where: ожидался список")
        return (0 until value.length()).map { value.get(it) }
    }

    private fun strList(value: Any?, where: String): List<String> =
        list(value, where).mapIndexed { i, v ->
            if (v !is String) throw ContentError("$where: элемент №${i + 1} должен быть строкой")
            v
        }

    private fun strMap(value: Any?, where: String, keyName: String): Map<String, String> {
        if (value !is JSONObject) throw ContentError("$where: поле '$keyName' должно быть объектом")
        val result = LinkedHashMap<String, String>()
        value.keys().forEach { key ->
            val v = value.opt(key)
            if (v !is String) {
                throw ContentError("$where: значение '$key' должно быть строкой")
            }
            result[key] = v
        }
        return result
    }

    /** Проверка поля с понятной ошибкой — аналог _field в content.py. */
    private fun field(rec: Any?, key: String, check: String, where: String): Any? {
        if (rec !is JSONObject) throw ContentError("$where: ожидался объект")
        if (!rec.has(key)) throw ContentError("$where: нет обязательного поля '$key'")
        val value = rec.opt(key)
        val ok = when (check) {
            "str" -> value is String
            "str?" -> value == JSONObject.NULL || value is String
            "bool" -> value is Boolean
            "int?" -> value == JSONObject.NULL || value is Int || value is Long
            "list" -> value is JSONArray
            "dict" -> value is JSONObject
            "dict?" -> value == JSONObject.NULL || value is JSONObject
            else -> false
        }
        if (!ok) throw ContentError("$where: поле '$key' имеет неверный тип")
        return if (value == JSONObject.NULL) null else value
    }

    private fun optionalField(rec: Any?, key: String, check: String, where: String): Any? {
        if (rec !is JSONObject) throw ContentError("$where: ожидался объект")
        return if (rec.has(key)) field(rec, key, check, where) else null
    }

    private fun str(v: Any?, key: String, where: String): String =
        (v as? String) ?: throw ContentError("$where: поле '$key' должно быть строкой")

    private fun where(rec: Any?, index: Int, kind: String): String {
        if (rec is JSONObject) {
            val id = rec.opt("id")
            if (id is String && id.isNotEmpty()) return "$kind $id"
        }
        return "$kind №${index + 1}"
    }

    // ------------------------------------------------------------------ records

    private fun buildTip(t: Any?, index: Int): Tip {
        val w = where(t, index, "совет")
        return Tip(
            id = str(field(t, "id", "str", w), "id", w),
            cat = str(field(t, "cat", "str", w), "cat", w),
            title = str(field(t, "title", "str", w), "title", w),
            text = str(field(t, "text", "str", w), "text", w),
            sched = str(field(t, "sched", "str", w), "sched", w),
            source = str(field(t, "source", "str", w), "source", w),
            tags = str(field(t, "tags", "str", w), "tags", w),
            ageMin = (field(t, "age_min", "int?", w) as? Number)?.toInt(),
            rx = (field(t, "rx", "bool", w) as? Boolean) ?: false,
        )
    }

    private fun buildItem(s: Any?, index: Int): ScheduleItem {
        val w = where(s, index, "пункт расписания")
        val days = list(field(s, "days", "list", w), w).mapIndexed { i, v ->
            (v as? Number)?.toInt() ?: throw ContentError("$w: день №${i + 1} должен быть числом")
        }
        val tipsRaw = optionalField(s, "tips", "list", w) as? JSONArray
        val tips = if (tipsRaw == null) emptyList()
        else (0 until tipsRaw.length()).map { i ->
            val v = tipsRaw.get(i)
            if (v !is String) throw ContentError("$w: ссылка на совет должна быть строкой")
            v
        }
        val req = optionalField(s, "requires", "dict", w) as? JSONObject
        val requires = if (req == null) emptyMap()
        else {
            val m = LinkedHashMap<String, Any?>()
            req.keys().forEach { k -> m[k] = req.opt(k) }
            m
        }
        val altRaw = optionalField(s, "alt", "dict?", w) as? JSONObject
        val alt = if (altRaw == null) null
        else {
            val m = LinkedHashMap<String, String>()
            altRaw.keys().forEach { k ->
                val v = altRaw.opt(k)
                if (v !is String) throw ContentError("$w: alt['$k'] должно быть строкой")
                m[k] = v
            }
            m
        }
        return ScheduleItem(
            id = str(field(s, "id", "str", w), "id", w),
            title = str(field(s, "title", "str", w), "title", w),
            detail = str(field(s, "detail", "str", w), "detail", w),
            cat = str(field(s, "cat", "str", w), "cat", w),
            days = days,
            anchor = str(field(s, "anchor", "str", w), "anchor", w),
            time = (field(s, "time", "str?", w) as? String),
            tips = tips,
            requires = requires,
            alt = alt,
        )
    }

    private fun buildMindGroup(g: Any?, index: Int, section: String): MindGroup {
        val w = "mind.json, $section №${index + 1}"
        return MindGroup(
            name = str(field(g, "name", "str", w), "name", w),
            amount = str(field(g, "amount", "str", w), "amount", w),
            note = str(field(g, "note", "str", w), "note", w),
        )
    }

    private fun buildMenuDay(row: Any?, index: Int): MenuDay {
        val w = "mind.json, меню, день №${index + 1}"
        return MenuDay(
            day = str(field(row, "day", "str", w), "day", w),
            breakfast = str(field(row, "breakfast", "str", w), "breakfast", w),
            lunch = str(field(row, "lunch", "str", w), "lunch", w),
            dinner = str(field(row, "dinner", "str", w), "dinner", w),
            snack = str(field(row, "snack", "str", w), "snack", w),
        )
    }

    private fun buildBooks(text: String): Pair<List<Book>, List<Passage>> {
        val raw = obj(text, "books.json")
        val bookRows = list(field(raw, "books", "list", "books.json"), "books.json")
        val passageRows = list(field(raw, "passages", "list", "books.json"), "books.json")

        val books = ArrayList<Book>()
        val seenIds = HashSet<String>()
        bookRows.forEachIndexed { i, row ->
            val w = where(row, i, "книга")
            val book = Book(
                id = str(field(row, "id", "str", w), "id", w),
                title = str(field(row, "title", "str", w), "title", w),
                subtitle = str(field(row, "subtitle", "str", w), "subtitle", w),
                author = str(field(row, "author", "str", w), "author", w),
            )
            if (!seenIds.add(book.id)) throw ContentError("books.json: дублирующийся id книги: ${book.id}")
            if (book.title.isBlank()) throw ContentError("$w: пустое название")
            books.add(book)
        }

        val passages = ArrayList<Passage>()
        val seen = HashSet<String>()
        passageRows.forEachIndexed { i, row ->
            val w = where(row, i, "отрывок")
            val passage = Passage(
                id = str(field(row, "id", "str", w), "id", w),
                book = str(field(row, "book", "str", w), "book", w),
                section = str(field(row, "section", "str", w), "section", w),
                text = str(field(row, "text", "str", w), "text", w),
            )
            if (!seen.add(passage.id)) throw ContentError("books.json: дублирующийся id отрывка: ${passage.id}")
            if (passage.book !in seenIds) {
                throw ContentError("$w: ссылка на несуществующую книгу '${passage.book}'")
            }
            if (passage.text.isBlank()) throw ContentError("$w: пустой текст отрывка")
            passages.add(passage)
        }
        return Pair(books, passages)
    }

    private fun checkTips(tips: List<Tip>, categories: List<String>) {
        val seen = HashSet<String>()
        for (tip in tips) {
            if (!seen.add(tip.id)) throw ContentError("дублирующийся id совета: ${tip.id}")
            if (tip.cat !in categories) throw ContentError("${tip.id}: неизвестная категория '${tip.cat}'")
            if (tip.source.isBlank()) throw ContentError("${tip.id}: пустой источник")
        }
    }

    private fun checkSchedule(items: List<ScheduleItem>, tipIds: Set<String>) {
        val seen = HashSet<String>()
        for (item in items) {
            if (!seen.add(item.id)) throw ContentError("дублирующийся id пункта расписания: ${item.id}")
            if (item.anchor !in ANCHORS) throw ContentError("${item.id}: неизвестный anchor '${item.anchor}'")
            if (item.anchor == "clock" && item.time == null) {
                throw ContentError("${item.id}: clock-пункт без времени")
            }
            if (item.anchor != "clock" && item.time != null) {
                throw ContentError("${item.id}: время указано у пункта с anchor=${item.anchor}")
            }
            for (ref in item.tips) {
                if (ref !in tipIds) throw ContentError("${item.id}: ссылка на несуществующий совет $ref")
            }
            if (item.requires.isNotEmpty() && item.alt == null) {
                throw ContentError("${item.id}: есть requires, но нет альтернативы alt")
            }
        }
    }
}
