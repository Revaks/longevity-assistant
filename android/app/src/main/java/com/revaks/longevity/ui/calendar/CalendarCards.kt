package com.revaks.longevity.ui.calendar

import android.content.Context
import android.graphics.drawable.GradientDrawable
import android.view.Gravity
import android.view.View
import android.view.ViewGroup
import android.widget.CheckBox
import android.widget.LinearLayout
import android.widget.TextView
import androidx.core.content.ContextCompat
import com.google.android.material.button.MaterialButton
import com.google.android.material.card.MaterialCardView
import com.revaks.longevity.R
import com.revaks.longevity.core.Dates
import com.revaks.longevity.core.FocusWeek
import com.revaks.longevity.core.Measures
import com.revaks.longevity.core.Screening
import com.revaks.longevity.data.Measurement
import java.time.LocalDate

/**
 * Карточки календаря: прогресс недели, фокус недели, биодневник и обследования.
 * Строятся кодом — данных немного, отдельные layout-файлы не нужны.
 */
internal object CalendarCards {

    /** Карточка с заголовком; возвращает колонку для содержимого. */
    fun card(ctx: Context, parent: LinearLayout, title: String?): LinearLayout {
        val card = MaterialCardView(ctx).apply {
            layoutParams = LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT,
            ).apply { topMargin = dp(ctx, 10) }
            radius = dp(ctx, 12).toFloat()
            cardElevation = 0f
            strokeColor = 0xFFE2E8F0.toInt()
            strokeWidth = dp(ctx, 1)
        }
        val column = LinearLayout(ctx).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(ctx, 12), dp(ctx, 12), dp(ctx, 12), dp(ctx, 12))
        }
        if (title != null) {
            column.addView(
                TextView(ctx).apply {
                    text = title
                    textSize = 16f
                    setTypeface(typeface, android.graphics.Typeface.BOLD)
                    setTextColor(ContextCompat.getColor(ctx, R.color.text_primary))
                }
            )
        }
        card.addView(column)
        parent.addView(card)
        return column
    }

    // ------------------------------------------------------------------ прогресс

    fun renderProgress(
        ctx: Context,
        parent: LinearLayout,
        done: Int,
        total: Int,
        ratios: List<Float>,
        weekLabels: List<String>,
        weak: List<Pair<String, Int>>,
    ) {
        if (total == 0 && weak.isEmpty()) return
        val column = card(ctx, parent, "Прогресс недели")
        val percent = if (total > 0) done * 100 / total else 0
        column.addView(
            TextView(ctx).apply {
                text = "Выполнено $done из $total ($percent%)"
                textSize = 14f
                setTextColor(ContextCompat.getColor(ctx, R.color.text_primary))
            }
        )

        val bars = LinearLayout(ctx).apply {
            orientation = LinearLayout.HORIZONTAL
            layoutParams = LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT,
            ).apply { topMargin = dp(ctx, 8) }
        }
        for (i in ratios.indices) {
            val cell = LinearLayout(ctx).apply {
                orientation = LinearLayout.VERTICAL
                gravity = Gravity.CENTER
            }
            val bar = View(ctx).apply {
                background = GradientDrawable().apply {
                    cornerRadius = dp(ctx, 3).toFloat()
                    setColor(ContextCompat.getColor(ctx, R.color.primary))
                    alpha = (60 + 195 * ratios[i].coerceIn(0f, 1f)).toInt()
                }
                layoutParams = LinearLayout.LayoutParams(dp(ctx, 10), dp(ctx, 28))
            }
            val label = TextView(ctx).apply {
                text = weekLabels.getOrElse(i) { "" }
                textSize = 10f
                setTextColor(ContextCompat.getColor(ctx, R.color.text_muted))
            }
            cell.addView(bar)
            cell.addView(label)
            bars.addView(cell, LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f))
        }
        column.addView(bars)

        if (weak.isNotEmpty()) {
            val text = weak.joinToString("; ") { "${it.first} — ${it.second}%" }
            column.addView(
                TextView(ctx).apply {
                    this.text = "Чаще всего пропускаете: $text"
                    textSize = 12f
                    setTextColor(ContextCompat.getColor(ctx, R.color.text_muted))
                    setPadding(0, dp(ctx, 8), 0, 0)
                }
            )
        }
    }

    // ------------------------------------------------------------------ фокус недели

    fun renderFocus(
        ctx: Context,
        parent: LinearLayout,
        focus: FocusWeek?,
        taskIds: List<String>,
        done: Set<String>,
        onToggle: (String) -> Unit,
    ) {
        if (focus == null) return
        val column = card(ctx, parent, focus.title)
        column.addView(
            TextView(ctx).apply {
                text = focus.detail
                textSize = 13f
                setTextColor(ContextCompat.getColor(ctx, R.color.text_muted))
            }
        )
        for ((index, task) in focus.tasks.withIndex()) {
            val id = taskIds.getOrNull(index) ?: continue
            val box = CheckBox(ctx).apply {
                text = task
                textSize = 14f
                isChecked = id in done
                setPadding(0, dp(ctx, 4), 0, 0)
                setOnClickListener { onToggle(id) }
            }
            column.addView(box)
        }
    }

    // ------------------------------------------------------------------ биодневник

    fun renderBio(
        ctx: Context,
        parent: LinearLayout,
        measurements: Map<String, List<Measurement>>,
        onAdd: () -> Unit,
        onDelete: (Measurement) -> Unit,
    ) {
        val column = card(ctx, parent, "Биодневник")
        val add = MaterialButton(ctx).apply {
            text = "Добавить измерение"
            textSize = 13f
            setOnClickListener { onAdd() }
        }
        column.addView(add)

        val filled = measurements.filterValues { it.isNotEmpty() }
        if (filled.isEmpty()) {
            column.addView(
                TextView(ctx).apply {
                    text = "Пока пусто. Записывайте вес, талию, давление, пульс — здесь появится динамика."
                    textSize = 12f
                    setTextColor(ContextCompat.getColor(ctx, R.color.text_muted))
                    setPadding(0, dp(ctx, 6), 0, 0)
                }
            )
            return
        }

        for ((kind, list) in filled) {
            val latest = list.first()
            val previous = list.getOrNull(1)
            val title = Measures.kind(kind)?.title ?: kind
            var line = "$title: ${Measures.format(kind, latest.value)} (${Dates.fmtShort(latest.date)})"
            if (previous != null) {
                line += ", ${Measures.delta(kind, latest.value, previous.value)}"
            }
            val minMax = list.minByOrNull { it.value }?.value to list.maxByOrNull { it.value }?.value
            val range = "за ${list.size} записей: ${Measures.format(kind, minMax.first ?: 0.0)} — " +
                Measures.format(kind, minMax.second ?: 0.0)
            val row = TextView(ctx).apply {
                text = "$line\n$range"
                textSize = 13f
                setTextColor(ContextCompat.getColor(ctx, R.color.text_primary))
                setPadding(0, dp(ctx, 8), 0, 0)
                setOnLongClickListener { v ->
                    com.google.android.material.dialog.MaterialAlertDialogBuilder(v.context)
                        .setTitle("Удалить последнюю запись?")
                        .setMessage(line)
                        .setNegativeButton("Отмена", null)
                        .setPositiveButton("Удалить") { _, _ -> onDelete(latest) }
                        .show()
                    true
                }
            }
            column.addView(row)
        }
        column.addView(
            TextView(ctx).apply {
                text = "Долгое нажатие на строку — удалить последнюю запись."
                textSize = 11f
                setTextColor(ContextCompat.getColor(ctx, R.color.text_muted))
                setPadding(0, dp(ctx, 6), 0, 0)
            }
        )
    }

    // ------------------------------------------------------------------ обследования

    fun renderScreenings(
        ctx: Context,
        parent: LinearLayout,
        entries: List<Triple<Screening, LocalDate?, Boolean>>,
        onMark: (Screening) -> Unit,
        onClear: (Screening) -> Unit,
        disclaimer: String,
    ) {
        if (entries.isEmpty()) return
        val column = card(ctx, parent, "Обследования")
        for ((screening, last, due) in entries) {
            val head = TextView(ctx).apply {
                text = screening.title
                textSize = 14f
                setTypeface(typeface, android.graphics.Typeface.BOLD)
                setTextColor(
                    if (due) ContextCompat.getColor(ctx, R.color.note_accent)
                    else ContextCompat.getColor(ctx, R.color.text_primary)
                )
                setPadding(0, dp(ctx, 8), 0, 0)
            }
            column.addView(head)
            column.addView(
                TextView(ctx).apply {
                    text = screening.detail
                    textSize = 12f
                    setTextColor(ContextCompat.getColor(ctx, R.color.text_muted))
                }
            )

            val status = when {
                due && last == null -> "Не проходили — стоит запланировать"
                due -> "Пора: последний раз ${Dates.fmtShort(last!!)}"
                else -> "Следующее: ${Dates.fmtShort(com.revaks.longevity.core.Screenings.nextDue(last, screening, LocalDate.now()))}"
            }
            column.addView(
                TextView(ctx).apply {
                    text = status
                    textSize = 12f
                    setTextColor(ContextCompat.getColor(ctx, R.color.text_muted))
                }
            )

            val buttons = LinearLayout(ctx).apply {
                orientation = LinearLayout.HORIZONTAL
                setPadding(0, dp(ctx, 4), 0, 0)
            }
            buttons.addView(
                MaterialButton(ctx).apply {
                    text = "Отмечено сегодня"
                    textSize = 12f
                    setOnClickListener { onMark(screening) }
                }
            )
            if (last != null) {
                buttons.addView(
                    MaterialButton(ctx).apply {
                        text = "Сбросить"
                        textSize = 12f
                        setOnClickListener { onClear(screening) }
                    }
                )
            }
            column.addView(buttons)
        }
        column.addView(
            TextView(ctx).apply {
                text = disclaimer
                textSize = 11f
                setTextColor(ContextCompat.getColor(ctx, R.color.text_muted))
                setPadding(0, dp(ctx, 8), 0, 0)
            }
        )
    }

    private fun dp(ctx: Context, value: Int): Int =
        (value * ctx.resources.displayMetrics.density).toInt()
}
