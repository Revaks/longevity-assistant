package com.revaks.longevity.ui.calendar

import android.graphics.Color
import android.graphics.drawable.GradientDrawable
import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.LinearLayout
import android.widget.TextView
import androidx.fragment.app.Fragment
import com.revaks.longevity.LongevityApp
import com.revaks.longevity.R
import com.revaks.longevity.core.Dates
import com.revaks.longevity.core.Schedule
import com.revaks.longevity.databinding.FragmentCalendarBinding
import com.revaks.longevity.ui.Ui
import java.time.LocalDate

/** Вкладка «Календарь»: неделя, отметки о заметках, план выбранного дня. */
class CalendarFragment : Fragment() {

    private var _binding: FragmentCalendarBinding? = null
    private val binding get() = _binding!!

    private var weekStart: LocalDate = Dates.mondayOf(LocalDate.now())
    private var selectedDay: LocalDate = LocalDate.now()

    private val app get() = requireActivity().application as LongevityApp

    override fun onCreateView(
        inflater: LayoutInflater, container: ViewGroup?, savedInstanceState: Bundle?,
    ): View {
        _binding = FragmentCalendarBinding.inflate(inflater, container, false)
        return binding.root
    }

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)
        val ready = app.state as? LongevityApp.State.Ready
        if (ready == null) {
            // Экран загрузки ещё идёт — фрагмент без данных не показываем.
            return
        }
        Ui.pageSubtitle(this, binding.tvPageSubtitle)
        binding.btnPrev.setOnClickListener {
            weekStart = weekStart.minusWeeks(1)
            refresh()
        }
        binding.btnNext.setOnClickListener {
            weekStart = weekStart.plusWeeks(1)
            refresh()
        }
        binding.btnToday.setOnClickListener {
            weekStart = Dates.mondayOf(LocalDate.now())
            selectedDay = LocalDate.now()
            refresh()
        }
        refresh()
    }

    private fun content() = (app.state as LongevityApp.State.Ready).content
    private fun storage() = app.storage()

    private fun refresh() {
        if (_binding == null) return
        val content = content()

        val sunday = weekStart.plusDays(6)
        binding.tvWeekLabel.text = String.format(
            "%02d.%02d – %02d.%02d.%d",
            weekStart.dayOfMonth, weekStart.monthValue,
            sunday.dayOfMonth, sunday.monthValue, sunday.year,
        )

        buildLegend(content.categories.map { it to content.catColor(it) })
        buildDayChips()
        buildDayDetail()
    }

    private fun buildLegend(colored: List<Pair<String, Int>>) {
        binding.legendRow.removeAllViews()
        val ctx = requireContext()
        for ((cat, color) in colored) {
            val tv = TextView(ctx)
            tv.text = "● $cat"
            tv.setTextColor(color)
            tv.textSize = 12f
            val lp = LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT,
            ).apply { marginEnd = Ui.dp(tv, 10) }
            binding.legendRow.addView(tv, lp)
        }
    }

    private fun buildDayChips() {
        binding.dayRow.removeAllViews()
        val ctx = requireContext()
        val today = LocalDate.now()

        for (i in 0 until 7) {
            val day = weekStart.plusDays(i.toLong())
            val chip = LinearLayout(ctx).apply {
                orientation = LinearLayout.VERTICAL
                gravity = android.view.Gravity.CENTER
                isClickable = true
                isFocusable = true
                setPadding(Ui.dp(this, 4), Ui.dp(this, 8), Ui.dp(this, 4), Ui.dp(this, 8))
                background = roundedDayBg(day == today, day == selectedDay)
            }
            val wd = day.dayOfWeek.value - 1
            val title = TextView(ctx).apply {
                text = Dates.WEEKDAYS[wd]
                textSize = 12f
                setTextColor(if (day == today) Color.WHITE else 0xFF111827.toInt())
                gravity = android.view.Gravity.CENTER
            }
            val number = TextView(ctx).apply {
                text = "%02d".format(day.dayOfMonth)
                textSize = 14f
                setTextColor(if (day == today) Color.WHITE else 0xFF111827.toInt())
                gravity = android.view.Gravity.CENTER
            }
            chip.addView(title)
            chip.addView(number)
            if (storage().hasDiaryNotes(Dates.iso(day))) {
                val dot = TextView(ctx).apply {
                    text = "•"
                    textSize = 10f
                    gravity = android.view.Gravity.CENTER
                    setTextColor(
                        if (day == today) Color.WHITE
                        else ctx.getColor(R.color.note_accent)
                    )
                }
                chip.addView(dot)
            }
            chip.setOnClickListener {
                selectedDay = day
                refresh()
            }
            val lp = LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f).apply {
                marginEnd = if (i < 6) Ui.dp(chip, 4) else 0
            }
            binding.dayRow.addView(chip, lp)
        }
    }

    private fun roundedDayBg(isToday: Boolean, isSelected: Boolean): GradientDrawable {
        val (bg, _) = when {
            isToday -> R.color.today_bg to 0
            isSelected -> R.color.header_selected to Ui.SELECTED_HEADER_TEXT
            else -> R.color.header_default to 0
        }
        val drawable = GradientDrawable()
        drawable.cornerRadius = Ui.dp(binding.root, 8).toFloat()
        drawable.setColor(requireContext().getColor(bg))
        return drawable
    }

    private fun buildDayDetail() {
        val content = content()
        val container = binding.llDay
        container.removeAllViews()
        val ctx = requireContext()
        val storage = storage()

        // Заголовок выбранного дня
        val head = TextView(ctx).apply {
            text = Dates.fmtDayFull(selectedDay)
            setTextColor(0xFF111827.toInt())
            textSize = 16f
            setTypeface(typeface, android.graphics.Typeface.BOLD)
        }
        container.addView(head, marginBottom(6))

        val date = Dates.iso(selectedDay)
        val items = Schedule.getDayPlan(content, selectedDay)

        if (items.isEmpty()) {
            container.addView(
                mutedLabel(ctx, "В этот день пунктов расписания нет."), marginBottom(6)
            )
        } else {
            for (item in items) {
                val time = TextView(ctx).apply {
                    text = Schedule.displayTime(item)
                    setTextColor(content.catColor(item.cat))
                    textSize = 13f
                    setTypeface(typeface, android.graphics.Typeface.BOLD)
                }
                val title = TextView(ctx).apply {
                    text = item.title
                    setTextColor(0xFF111827.toInt())
                    textSize = 15f
                    setTypeface(typeface, android.graphics.Typeface.BOLD)
                }
                val block = LinearLayout(ctx).apply {
                    orientation = LinearLayout.VERTICAL
                    setPadding(0, Ui.dp(this, 6), 0, Ui.dp(this, 2))
                }
                block.addView(time)
                block.addView(title)
                if (item.detail.isNotEmpty()) {
                    block.addView(mutedLabel(ctx, item.detail))
                }
                container.addView(block, marginBottom(4))
            }
        }

        val notes = storage.diaryEntriesOn(date)
        if (notes.isNotEmpty()) {
            val noteHead = TextView(ctx).apply {
                text = "Заметки"
                setTextColor(0xFF92400E.toInt())
                textSize = 14f
                setTypeface(typeface, android.graphics.Typeface.BOLD)
            }
            val lp = LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT,
            ).apply { topMargin = Ui.dp(noteHead, 8) }
            container.addView(noteHead, lp)
            for (entry in notes) {
                val note = TextView(ctx).apply {
                    text = entry.text
                    setTextColor(0xFF92400E.toInt())
                    textSize = 14f
                    setTypeface(typeface, android.graphics.Typeface.ITALIC)
                    setTextIsSelectable(true)
                }
                container.addView(note, marginBottom(6))
            }
        }
    }

    private fun mutedLabel(ctx: android.content.Context, text: String): TextView =
        TextView(ctx).apply {
            this.text = text
            setTextColor(0xFF6B7280.toInt())
            textSize = 13f
        }

    private fun marginBottom(dpValue: Int): LinearLayout.LayoutParams =
        LinearLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT,
        ).apply { bottomMargin = Ui.dp(binding.root, dpValue) }

    override fun onDestroyView() {
        super.onDestroyView()
        _binding = null
    }
}
