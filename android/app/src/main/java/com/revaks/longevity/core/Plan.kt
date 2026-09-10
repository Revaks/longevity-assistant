package com.revaks.longevity.core

import org.json.JSONArray
import org.json.JSONObject
import java.time.LocalDate
import java.time.temporal.WeekFields
import java.util.UUID

/**
 * Профиль пользователя, влияющий на календарь.
 *
 * [activity] — уровень активности: 0 низкий, 1 средний, 2 высокий (им выбираются
 * варианты ротации). [hidden] — id скрытых пунктов расписания.
 */
data class Profile(
    val age: Int? = null,
    val sex: String? = null,
    val activity: Int = 1,
    val deload: Boolean = false,
    val hidden: Set<String> = emptySet(),
)

/**
 * План дня с учётом профиля: скрытые пункты, свои пункты и ротация вариантов
 * по неделям. Только чистые функции — покрываются обычными JVM-тестами.
 */
object Plan {

    /** Свои пункты пользователя имеют такой префикс id. */
    const val CUSTOM_PREFIX = "custom:"

    private const val MAX_CUSTOM_ITEMS = 50
    private val ANCHORS = setOf("clock", "morning", "allday")

    /** Номер ISO-недели — по нему чередуются варианты и тема недели. */
    fun isoWeek(day: LocalDate): Int = day.get(WeekFields.ISO.weekOfWeekBasedYear())

    /** Тема недели: детерминированно по номеру недели. */
    fun focusForWeek(content: Content, day: LocalDate): FocusWeek? {
        if (content.focus.isEmpty()) return null
        val index = Math.floorMod(isoWeek(day) - 1, content.focus.size)
        return content.focus[index]
    }

    /** Идентификаторы заданий фокуса — по ним хранятся отметки выполнения. */
    fun focusTaskIds(focus: FocusWeek?): List<String> {
        if (focus == null) return emptyList()
        return focus.tasks.indices.map { "focus:${focus.id}:$it" }
    }

    /** Вариант пункта: доступные уровню активности, чередуются по ISO-неделям. */
    fun variantFor(
        content: Content,
        item: ScheduleItem,
        day: LocalDate,
        profile: Profile,
    ): RotationVariant? {
        val variants = content.rotations[item.id] ?: return null
        val allowed = variants.filter { it.level <= profile.activity }
        val pool = allowed.ifEmpty { variants }
        if (profile.deload) return pool.minByOrNull { it.level } ?: pool.first()
        return pool[Math.floorMod(isoWeek(day) - 1, pool.size)]
    }

    /** Пункт с подставленным вариантом ротации; id и дни недели не меняются. */
    fun applyRotation(
        content: Content,
        item: ScheduleItem,
        day: LocalDate,
        profile: Profile,
    ): ScheduleItem {
        val variant = variantFor(content, item, day, profile) ?: return item
        return item.copy(title = variant.title, detail = variant.detail)
    }

    /** Пункты дня: базовое расписание (без скрытых) плюс свои пункты, с ротацией. */
    fun itemsForDay(
        content: Content,
        profile: Profile,
        customItems: List<ScheduleItem>,
        day: LocalDate,
    ): List<ScheduleItem> {
        val weekday = day.dayOfWeek.value - 1
        val result = ArrayList<ScheduleItem>()
        for (item in Schedule.getDayPlan(content, day)) {
            if (item.id in profile.hidden) continue
            result.add(applyRotation(content, item, day, profile))
        }
        for (item in customItems) {
            if (weekday !in item.days || item.id in profile.hidden) continue
            result.add(applyRotation(content, item, day, profile))
        }
        return sorted(result)
    }

    /** Идентификаторы пунктов дня — для подсчёта прогресса и серий. */
    fun itemIdsForDay(
        content: Content,
        profile: Profile,
        customItems: List<ScheduleItem>,
        day: LocalDate,
    ): Set<String> = itemsForDay(content, profile, customItems, day).mapTo(HashSet()) { it.id }

    private fun sorted(items: List<ScheduleItem>): List<ScheduleItem> =
        items.sortedWith { a, b ->
            compareBy<ScheduleItem>(
                { Schedule.timeKey(Schedule.displayTime(it)).first },
                { Schedule.timeKey(Schedule.displayTime(it)).second },
                { Schedule.timeKey(Schedule.displayTime(it)).third },
                { it.id },
            ).compare(a, b)
        }

    // ------------------------------------------------------------------ свои пункты

    /** Новый идентификатор своего пункта. */
    fun newCustomId(): String = CUSTOM_PREFIX + UUID.randomUUID().toString().substring(0, 8)

    /**
     * Разбор своих пунктов из профиля (JSON-массив). Повреждённые записи
     * пропускаются — календарь не должен падать из-за настроек.
     */
    fun parseCustomItems(json: String?, categories: List<String>): List<ScheduleItem> {
        if (json.isNullOrBlank()) return emptyList()
        val array = runCatching { JSONArray(json) }.getOrNull() ?: return emptyList()
        val result = ArrayList<ScheduleItem>()
        for (i in 0 until minOf(array.length(), MAX_CUSTOM_ITEMS)) {
            val obj = array.optJSONObject(i) ?: continue
            val id = obj.optString("id")
            if (!id.startsWith(CUSTOM_PREFIX)) continue
            val title = obj.optString("title").trim()
            if (title.isEmpty()) continue
            val anchor = obj.optString("anchor").takeIf { it in ANCHORS } ?: "allday"
            val time = obj.optString("time").trim().takeIf { anchor == "clock" && it.isNotEmpty() }
            if (anchor == "clock" && time == null) continue
            val days = ArrayList<Int>()
            val rawDays = obj.optJSONArray("days") ?: continue
            for (d in 0 until rawDays.length()) {
                val value = rawDays.optInt(d, -1)
                if (value in 0..6) days.add(value)
            }
            if (days.isEmpty()) continue
            val cat = obj.optString("cat").takeIf { it in categories }
                ?: categories.firstOrNull().orEmpty()
            result.add(
                ScheduleItem(
                    id = id,
                    title = title,
                    detail = obj.optString("detail").trim(),
                    cat = cat,
                    days = days.distinct().sorted(),
                    anchor = anchor,
                    time = time,
                    tips = emptyList(),
                )
            )
        }
        return result
    }

    /** Сериализация своих пунктов для хранения в профиле. */
    fun serializeCustomItems(items: List<ScheduleItem>): String {
        val array = JSONArray()
        for (item in items) {
            array.put(
                JSONObject()
                    .put("id", item.id)
                    .put("title", item.title)
                    .put("detail", item.detail)
                    .put("cat", item.cat)
                    .put("days", JSONArray(item.days))
                    .put("anchor", item.anchor)
                    .put("time", item.time ?: "")
            )
        }
        return array.toString()
    }

    /** Скрытые пункты из профиля (JSON-массив id). Повреждённые данные — пусто. */
    fun parseHidden(json: String?): Set<String> {
        if (json.isNullOrBlank()) return emptySet()
        val array = runCatching { JSONArray(json) }.getOrNull() ?: return emptySet()
        val result = HashSet<String>()
        for (i in 0 until array.length()) {
            val id = array.optString(i)
            if (id.isNotEmpty()) result.add(id)
        }
        return result
    }

    /** Сериализация скрытых пунктов для хранения в профиле. */
    fun serializeHidden(ids: Set<String>): String {
        val array = JSONArray()
        ids.sorted().forEach { array.put(it) }
        return array.toString()
    }
}
