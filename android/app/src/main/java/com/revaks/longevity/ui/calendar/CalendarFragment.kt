package com.revaks.longevity.ui.calendar

import android.graphics.Color
import android.graphics.drawable.GradientDrawable
import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.CheckBox
import android.widget.LinearLayout
import android.widget.TextView
import androidx.core.content.ContextCompat
import androidx.fragment.app.Fragment
import com.revaks.longevity.LongevityApp
import com.revaks.longevity.R
import com.revaks.longevity.core.Content
import com.revaks.longevity.core.Dates
import com.revaks.longevity.core.Habits
import com.revaks.longevity.core.Measures
import com.revaks.longevity.core.Plan
import com.revaks.longevity.core.Profile
import com.revaks.longevity.core.Schedule
import com.revaks.longevity.core.ScheduleItem
import com.revaks.longevity.core.Screenings
import com.revaks.longevity.data.Storage
import com.revaks.longevity.databinding.FragmentCalendarBinding
import com.revaks.longevity.ui.Ui
import java.time.LocalDate

/**
 * Вкладка «Календарь»: неделя, план дня, прогресс привычек, фокус недели,
 * биодневник и обследования. Профиль, свои пункты и скрытие пунктов —
 * в «Настройках» календаря.
 */
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
        binding.btnSettings.setOnClickListener {
            CalendarDialogs.showActions(this, ::openProfile, ::openItems, ::openMeasure)
        }
        refresh()
    }

    private fun content(): Content = (app.state as LongevityApp.State.Ready).content
    private fun storage(): Storage = app.storage()

    // ------------------------------------------------------------------ профиль

    private fun openProfile() {
        CalendarDialogs.showProfile(this, storage().loadProfile()) { profile ->
            storage().saveProfile(profile)
            refresh()
        }
    }

    private fun openItems() {
        val content = content()
        val storage = storage()
        CalendarDialogs.showItems(
            this, content, storage.loadCustomItems(content.categories),
            storage.loadProfile().hidden,
        ) { items, hidden ->
            storage.saveCustomItems(items)
            storage.saveHidden(hidden)
            refresh()
        }
    }

    private fun openMeasure() {
        CalendarDialogs.showMeasure(this) { values ->
            val s = storage()
            for ((kind, value) in values) {
                s.addMeasurement(kind = kind, value = value)
            }
            refresh()
        }
    }

    // ------------------------------------------------------------------ отрисовка

    private fun refresh() {
        if (_binding == null) return
        val content = content()
        val storage = storage()
        val profile = storage.loadProfile()
        val custom = storage.loadCustomItems(content.categories)
        val ctx = requireContext()
        val today = LocalDate.now()

        val sunday = weekStart.plusDays(6)
        binding.tvWeekLabel.text = String.format(
            "%02d.%02d – %02d.%02d.%d",
            weekStart.dayOfMonth, weekStart.monthValue,
            sunday.dayOfMonth, sunday.monthValue, sunday.year,
        )

        buildLegend(content.categories.map { it to content.catColor(it) })
        buildDayChips(storage)

        // План каждого дня недели считается один раз за отрисовку.
        val planCache = HashMap<String, Set<String>>()
        fun idsFor(day: LocalDate): Set<String> =
            planCache.getOrPut(Dates.iso(day)) {
                Plan.itemIdsForDay(content, profile, custom, day)
            }
        fun doneFor(day: LocalDate): Set<String> = storage.completionsOn(Dates.iso(day))

        val (done, total) = Habits.weekProgress(weekStart, today, ::idsFor, ::doneFor)
        val ratios = Habits.dailyRatios(weekStart, today, ::idsFor, ::doneFor)
        val weak = weakSpots(content, profile, custom, storage, today)
        binding.llProgress.removeAllViews()
        CalendarCards.renderProgress(
            ctx, binding.llProgress, done, total, ratios, Dates.WEEKDAYS, weak,
        )

        binding.llFocus.removeAllViews()
        val focus = Plan.focusForWeek(content, weekStart)
        CalendarCards.renderFocus(
            ctx, binding.llFocus, focus, Plan.focusTaskIds(focus),
            doneFor(selectedDay),
        ) { taskId ->
            storage.toggleCompletion(Dates.iso(selectedDay), taskId)
            refresh()
        }

        buildDayDetail(content, profile, custom, storage, ::idsFor, ::doneFor)

        binding.llBio.removeAllViews()
        val measurements = Measures.KINDS.associate { it.id to storage.measurementsOfKind(it.id) }
        CalendarCards.renderBio(
            ctx, binding.llBio, measurements,
            onAdd = ::openMeasure,
            onDelete = { measurement ->
                storage.deleteMeasurement(measurement.id)
                refresh()
            },
        )

        binding.llScreens.removeAllViews()
        val entries = Screenings.forProfile(content, profile, today) { id ->
            storage.screeningLastDone(id)
        }
        CalendarCards.renderScreenings(
            ctx, binding.llScreens, entries,
            onMark = { screening ->
                storage.markScreening(screening.id, today)
                refresh()
            },
            onClear = { screening ->
                storage.clearScreening(screening.id)
                refresh()
            },
            disclaimer = "Список ориентировочный — периодичность и необходимость определяет врач.",
        )
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

    private fun buildDayChips(storage: Storage) {
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
            if (storage.hasDiaryNotes(Dates.iso(day))) {
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

    private fun buildDayDetail(
        content: Content,
        profile: Profile,
        custom: List<ScheduleItem>,
        storage: Storage,
        idsFor: (LocalDate) -> Set<String>,
        doneFor: (LocalDate) -> Set<String>,
    ) {
        val container = binding.llDay
        container.removeAllViews()
        val ctx = requireContext()

        val head = TextView(ctx).apply {
            text = Dates.fmtDayFull(selectedDay)
            setTextColor(0xFF111827.toInt())
            textSize = 16f
            setTypeface(typeface, android.graphics.Typeface.BOLD)
        }
        container.addView(head, marginBottom(6))

        val date = Dates.iso(selectedDay)
        val items = Plan.itemsForDay(content, profile, custom, selectedDay)
        val done = doneFor(selectedDay)

        if (items.isEmpty()) {
            container.addView(
                mutedLabel(ctx, "В этот день пунктов нет. Добавить свои можно в «Настройках»."),
                marginBottom(6),
            )
        } else {
            val streaks = Habits.streaks(
                items.map { it.id }, selectedDay, idsFor, doneFor,
            )
            for (item in items) {
                container.addView(dayItemRow(ctx, content, item, date, done, streaks[item.id] ?: 0))
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

    /** Строка пункта дня: чекбокс, время, название, деталь и серия. */
    private fun dayItemRow(
        ctx: android.content.Context,
        content: Content,
        item: ScheduleItem,
        date: String,
        done: Set<String>,
        streak: Int,
    ): View {
        val row = LinearLayout(ctx).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = android.view.Gravity.TOP
            setPadding(0, Ui.dp(this, 4), 0, Ui.dp(this, 4))
        }
        val check = CheckBox(ctx).apply {
            isChecked = item.id in done
            setOnCheckedChangeListener { _, _ ->
                storage().toggleCompletion(date, item.id)
                refresh()
            }
        }
        row.addView(check)

        val column = LinearLayout(ctx).apply {
            orientation = LinearLayout.VERTICAL
            layoutParams = LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f)
        }
        column.addView(
            TextView(ctx).apply {
                text = Schedule.displayTime(item)
                setTextColor(content.catColor(item.cat))
                textSize = 12f
                setTypeface(typeface, android.graphics.Typeface.BOLD)
            }
        )
        val titleRow = LinearLayout(ctx).apply { orientation = LinearLayout.HORIZONTAL }
        titleRow.addView(
            TextView(ctx).apply {
                text = item.title
                setTextColor(0xFF111827.toInt())
                textSize = 15f
                setTypeface(typeface, android.graphics.Typeface.BOLD)
            }
        )
        if (streak > 0) {
            titleRow.addView(
                TextView(ctx).apply {
                    text = "  • серия $streak"
                    textSize = 12f
                    setTextColor(ContextCompat.getColor(ctx, R.color.primary))
                }
            )
        }
        column.addView(titleRow)
        if (item.detail.isNotEmpty()) {
            column.addView(mutedLabel(ctx, item.detail))
        }
        row.addView(column)
        return row
    }

    /** Пункты, которые чаще всего пропускаются за последние 30 дней. */
    private fun weakSpots(
        content: Content,
        profile: Profile,
        custom: List<ScheduleItem>,
        storage: Storage,
        today: LocalDate,
    ): List<Pair<String, Int>> {
        val planned = HashMap<String, Int>()
        val done = HashMap<String, Int>()
        val titles = HashMap<String, String>()
        for (offset in 0 until 30) {
            val day = today.minusDays(offset.toLong())
            val doneToday = storage.completionsOn(Dates.iso(day))
            for (item in Plan.itemsForDay(content, profile, custom, day)) {
                planned[item.id] = (planned[item.id] ?: 0) + 1
                titles[item.id] = item.title
                if (item.id in doneToday) done[item.id] = (done[item.id] ?: 0) + 1
            }
        }
        return Habits.weakSpots(planned, done, limit = 3, minPlanned = 3)
            .filter { it.second < 0.999 }
            .map { (id, ratio) -> (titles[id] ?: id) to (ratio * 100).toInt() }
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
