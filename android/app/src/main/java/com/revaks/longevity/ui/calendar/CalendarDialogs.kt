package com.revaks.longevity.ui.calendar

import android.content.Context
import android.text.InputType
import android.view.Gravity
import android.widget.CheckBox
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.RadioButton
import android.widget.RadioGroup
import android.widget.ScrollView
import android.widget.TextView
import androidx.core.content.ContextCompat
import androidx.fragment.app.Fragment
import com.google.android.material.bottomsheet.BottomSheetDialog
import com.google.android.material.dialog.MaterialAlertDialogBuilder
import com.google.android.material.switchmaterial.SwitchMaterial
import com.revaks.longevity.R
import com.revaks.longevity.core.Content
import com.revaks.longevity.core.Dates
import com.revaks.longevity.core.Plan
import com.revaks.longevity.core.Profile
import com.revaks.longevity.core.ScheduleItem

/**
 * Диалоги календаря: профиль, управление пунктами и добавление измерений.
 * Все экраны строятся кодом — отдельные layout-файлы не нужны.
 */
internal object CalendarDialogs {

    private const val SEX_NONE = "не указан"
    private const val SEX_M = "м"
    private const val SEX_F = "ж"

    /** Нижний лист с действиями календаря. */
    fun showActions(
        fragment: Fragment,
        onProfile: () -> Unit,
        onItems: () -> Unit,
        onMeasure: () -> Unit,
    ) {
        val ctx = fragment.requireContext()
        val dialog = BottomSheetDialog(ctx)
        val column = LinearLayout(ctx).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(ctx, 12), dp(ctx, 6), dp(ctx, 12), dp(ctx, 18))
        }
        column.addView(
            TextView(ctx).apply {
                text = "Календарь"
                textSize = 13f
                setTextColor(ContextCompat.getColor(ctx, R.color.text_muted))
                setPadding(dp(ctx, 16), dp(ctx, 6), dp(ctx, 16), dp(ctx, 4))
            }
        )
        fun row(label: String, action: () -> Unit) {
            val view = TextView(ctx).apply {
                text = label
                textSize = 16f
                setTextColor(ContextCompat.getColor(ctx, R.color.text_primary))
                gravity = Gravity.CENTER_VERTICAL
                setPadding(dp(ctx, 16), dp(ctx, 15), dp(ctx, 16), dp(ctx, 15))
                val out = android.util.TypedValue()
                ctx.theme.resolveAttribute(android.R.attr.selectableItemBackground, out, true)
                setBackgroundResource(out.resourceId)
                setOnClickListener {
                    dialog.dismiss()
                    action()
                }
            }
            column.addView(view)
        }
        row("Профиль (возраст, пол, нагрузка)") { onProfile() }
        row("Пункты расписания и свои пункты") { onItems() }
        row("Добавить измерение в биодневник") { onMeasure() }
        dialog.setContentView(column)
        dialog.show()
    }

    /** Профиль: возраст, пол, уровень активности, разгрузочная неделя. */
    fun showProfile(fragment: Fragment, profile: Profile, onSaved: (Profile) -> Unit) {
        val ctx = fragment.requireContext()
        val column = LinearLayout(ctx).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(ctx, 20), dp(ctx, 8), dp(ctx, 20), dp(ctx, 4))
        }

        column.addView(label(ctx, "Возраст"))
        val ageInput = EditText(ctx).apply {
            inputType = InputType.TYPE_CLASS_NUMBER
            hint = "например, 45"
            setText(profile.age?.toString().orEmpty())
        }
        column.addView(ageInput)

        column.addView(label(ctx, "Пол (для списка обследований)"))
        val sexGroup = RadioGroup(ctx).apply { orientation = RadioGroup.HORIZONTAL }
        val sexOptions = listOf(SEX_NONE to "не указан", SEX_M to "мужской", SEX_F to "женский")
        sexOptions.forEach { (value, title) ->
            sexGroup.addView(RadioButton(ctx).apply {
                text = title
                tag = value
                isChecked = (profile.sex == value) || (profile.sex == null && value == SEX_NONE)
            })
        }
        column.addView(sexGroup)

        column.addView(label(ctx, "Уровень активности (подбирает варианты тренировок)"))
        val activityGroup = RadioGroup(ctx).apply { orientation = RadioGroup.VERTICAL }
        val activityTitles = listOf("Низкий — начинаю или щадящий режим", "Средний", "Высокий — регулярные тренировки")
        activityTitles.forEachIndexed { index, title ->
            activityGroup.addView(RadioButton(ctx).apply {
                text = title
                tag = index
                isChecked = profile.activity == index
            })
        }
        column.addView(activityGroup)

        val deload = SwitchMaterial(ctx).apply {
            text = "Разгрузочная (лёгкая) неделя"
            isChecked = profile.deload
        }
        column.addView(deload)

        MaterialAlertDialogBuilder(ctx)
            .setTitle("Профиль")
            .setView(column)
            .setNegativeButton("Отмена", null)
            .setPositiveButton("Сохранить") { _, _ ->
                val age = ageInput.text.toString().trim().toIntOrNull()?.takeIf { it in 1..120 }
                val sex = (sexGroup.checkedRadioButtonId.let { id ->
                    sexGroup.findViewById<RadioButton>(id)?.tag as? String
                })?.takeIf { it != SEX_NONE }
                val activity = (activityGroup.checkedRadioButtonId.let { id ->
                    activityGroup.findViewById<RadioButton>(id)?.tag as? Int
                }) ?: 1
                onSaved(profile.copy(age = age, sex = sex, activity = activity, deload = deload.isChecked))
            }
            .show()
    }

    /** Скрытие пунктов расписания и управление своими пунктами. */
    fun showItems(
        fragment: Fragment,
        content: Content,
        customItems: List<ScheduleItem>,
        hidden: Set<String>,
        onSaved: (List<ScheduleItem>, Set<String>) -> Unit,
    ) {
        val ctx = fragment.requireContext()
        val column = LinearLayout(ctx).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(ctx, 20), dp(ctx, 8), dp(ctx, 20), dp(ctx, 4))
        }
        val checkboxes = ArrayList<Pair<CheckBox, String>>()

        column.addView(label(ctx, "Отметьте пункты, которые должны быть в календаре:"))
        for (item in content.schedule) {
            val box = CheckBox(ctx).apply {
                text = item.title
                isChecked = item.id !in hidden
            }
            checkboxes.add(box to item.id)
            column.addView(box)
        }

        column.addView(label(ctx, "Свои пункты:"))
        if (customItems.isEmpty()) {
            column.addView(muted(ctx, "Пока нет. Добавьте свои — например, «Дневник сна 08:00»."))
        } else {
            for (item in customItems) {
                column.addView(
                    TextView(ctx).apply {
                        text = "• ${item.title} (${
                            Dates.WEEKDAYS.filterIndexed { index, _ -> index in item.days }
                                .joinToString(", ")
                        })"
                        textSize = 14f
                        setTextColor(ContextCompat.getColor(ctx, R.color.text_primary))
                        setOnLongClickListener { v ->
                            MaterialAlertDialogBuilder(v.context)
                                .setTitle("Удалить пункт?")
                                .setMessage(item.title)
                                .setNegativeButton("Отмена", null)
                                .setPositiveButton("Удалить") { _, _ ->
                                    onSaved(customItems.filter { it.id != item.id }, hidden)
                                    openItemsAgain(fragment, content, customItems.filter { it.id != item.id }, hidden, onSaved)
                                }
                                .show()
                            true
                        }
                    }
                )
            }
            column.addView(muted(ctx, "Долгое нажатие на пункт — удалить."))
        }

        val scroll = ScrollView(ctx).apply { addView(column) }

        MaterialAlertDialogBuilder(ctx)
            .setTitle("Пункты расписания")
            .setView(scroll)
            .setNeutralButton("Добавить пункт") { _, _ ->
                showAddCustomItem(fragment, content) { added ->
                    val updated = customItems + added
                    onSaved(updated, hidden)
                    openItemsAgain(fragment, content, updated, hidden, onSaved)
                }
            }
            .setNegativeButton("Отмена", null)
            .setPositiveButton("Сохранить") { _, _ ->
                val newHidden = checkboxes.filter { !it.first.isChecked }.map { it.second }.toSet()
                onSaved(customItems, newHidden)
            }
            .show()
    }

    private fun openItemsAgain(
        fragment: Fragment,
        content: Content,
        customItems: List<ScheduleItem>,
        hidden: Set<String>,
        onSaved: (List<ScheduleItem>, Set<String>) -> Unit,
    ) {
        fragment.view?.post {
            if (fragment.isAdded) showItems(fragment, content, customItems, hidden, onSaved)
        }
    }

    /** Новый свой пункт: название, деталь, время и дни недели. */
    fun showAddCustomItem(
        fragment: Fragment,
        content: Content,
        onAdded: (ScheduleItem) -> Unit,
    ) {
        val ctx = fragment.requireContext()
        val column = LinearLayout(ctx).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(ctx, 20), dp(ctx, 8), dp(ctx, 20), dp(ctx, 4))
        }
        val title = EditText(ctx).apply { hint = "Название, например «Дневник сна»" }
        val detail = EditText(ctx).apply { hint = "Деталь (необязательно)" }
        val time = EditText(ctx).apply { hint = "Время ЧЧ:ММ (пусто — весь день)" }
        column.addView(title)
        column.addView(detail)
        column.addView(time)
        column.addView(label(ctx, "Дни недели:"))
        val days = ArrayList<Pair<CheckBox, Int>>()
        for (index in Dates.WEEKDAYS.indices) {
            val box = CheckBox(ctx).apply { text = Dates.WEEKDAYS[index] }
            days.add(box to index)
            column.addView(box)
        }

        MaterialAlertDialogBuilder(ctx)
            .setTitle("Свой пункт")
            .setView(column)
            .setNegativeButton("Отмена", null)
            .setPositiveButton("Добавить") { _, _ ->
                val name = title.text.toString().trim()
                val selectedDays = days.filter { it.first.isChecked }.map { it.second }
                if (name.isEmpty() || selectedDays.isEmpty()) return@setPositiveButton
                val rawTime = time.text.toString().trim()
                val validTime = Regex("^\\d{1,2}:\\d{2}$").matches(rawTime)
                onAdded(
                    ScheduleItem(
                        id = Plan.newCustomId(),
                        title = name,
                        detail = detail.text.toString().trim(),
                        cat = content.categories.firstOrNull().orEmpty(),
                        days = selectedDays,
                        anchor = if (validTime) "clock" else "allday",
                        time = if (validTime) rawTime else null,
                        tips = emptyList(),
                    )
                )
            }
            .show()
    }

    /** Варианты измерений: для давления сохраняются два значения. */
    private val measureOptions = listOf(
        "Вес" to listOf("weight"),
        "Окружность талии" to listOf("waist"),
        "Давление (сист. / диаст.)" to listOf("bp_sys", "bp_dia"),
        "Пульс" to listOf("pulse"),
        "Тест 6-минутной ходьбы" to listOf("walk6m"),
        "Сила хвата" to listOf("grip"),
    )

    fun showMeasure(fragment: Fragment, onSave: (List<Pair<String, Double>>) -> Unit) {
        val ctx = fragment.requireContext()
        val titles = measureOptions.map { it.first }.toTypedArray()
        MaterialAlertDialogBuilder(ctx)
            .setTitle("Что измеряем?")
            .setItems(titles) { _, which ->
                val kinds = measureOptions[which].second
                showMeasureInput(fragment, kinds, onSave)
            }
            .setNegativeButton("Отмена", null)
            .show()
    }

    private fun showMeasureInput(
        fragment: Fragment,
        kinds: List<String>,
        onSave: (List<Pair<String, Double>>) -> Unit,
    ) {
        val ctx = fragment.requireContext()
        val column = LinearLayout(ctx).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(ctx, 20), dp(ctx, 8), dp(ctx, 20), dp(ctx, 4))
        }
        val inputs = ArrayList<Pair<String, EditText>>()
        for (kind in kinds) {
            val title = com.revaks.longevity.core.Measures.kind(kind)?.title ?: kind
            column.addView(label(ctx, title))
            val input = EditText(ctx).apply {
                inputType = InputType.TYPE_CLASS_NUMBER or InputType.TYPE_NUMBER_FLAG_DECIMAL
                hint = com.revaks.longevity.core.Measures.kind(kind)?.unit.orEmpty()
            }
            inputs.add(kind to input)
            column.addView(input)
        }

        MaterialAlertDialogBuilder(ctx)
            .setTitle("Новое измерение")
            .setView(column)
            .setNegativeButton("Отмена", null)
            .setPositiveButton("Сохранить") { _, _ ->
                val values = inputs.map { (kind, input) ->
                    kind to input.text.toString().trim().replace(',', '.').toDoubleOrNull()
                }
                if (values.any { it.second == null }) return@setPositiveButton
                onSave(values.map { it.first to it.second!! })
            }
            .show()
    }

    private fun label(ctx: Context, text: String): TextView =
        TextView(ctx).apply {
            this.text = text
            textSize = 13f
            setTextColor(ContextCompat.getColor(ctx, R.color.text_primary))
            setPadding(0, dp(ctx, 10), 0, 0)
        }

    private fun muted(ctx: Context, text: String): TextView =
        TextView(ctx).apply {
            this.text = text
            textSize = 12f
            setTextColor(ContextCompat.getColor(ctx, R.color.text_muted))
        }

    private fun dp(ctx: Context, value: Int): Int =
        (value * ctx.resources.displayMetrics.density).toInt()
}
