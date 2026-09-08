package com.revaks.longevity.ui.activity

import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import androidx.fragment.app.Fragment
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.RecyclerView
import com.revaks.longevity.LongevityApp
import com.revaks.longevity.core.Dates
import com.revaks.longevity.core.Schedule
import com.revaks.longevity.core.ScheduleItem
import com.revaks.longevity.databinding.FragmentActivityBinding
import com.revaks.longevity.databinding.ItemActivityTaskBinding
import com.revaks.longevity.ui.Ui
import java.time.LocalDate

/**
 * Вкладка «Активность»: отмечаем выполнение пунктов расписания на день.
 * Состояние живёт в Storage.completions (date + item_id).
 */
class ActivityFragment : Fragment() {

    private var _binding: FragmentActivityBinding? = null
    private val binding get() = _binding!!

    private var selectedDay: LocalDate = LocalDate.now()
    private var adapter: TaskAdapter? = null

    private val app get() = requireActivity().application as LongevityApp

    override fun onCreateView(
        inflater: LayoutInflater, container: ViewGroup?, savedInstanceState: Bundle?,
    ): View {
        _binding = FragmentActivityBinding.inflate(inflater, container, false)
        return binding.root
    }

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)
        val ready = app.state as? LongevityApp.State.Ready
        if (ready == null) return

        Ui.pageSubtitle(this, binding.tvPageSubtitle)
        adapter = TaskAdapter(
            content = ready.content,
            storage = app.storage(),
            onToggle = { _ -> refresh() },
        )
        binding.rvTasks.layoutManager = LinearLayoutManager(requireContext())
        binding.rvTasks.adapter = adapter

        binding.btnPrev.setOnClickListener { changeDay(selectedDay.minusDays(1)) }
        binding.btnNext.setOnClickListener { changeDay(selectedDay.plusDays(1)) }
        binding.btnToday.setOnClickListener { changeDay(LocalDate.now()) }
        refresh()
    }

    private fun changeDay(day: LocalDate) {
        selectedDay = day
        refresh()
    }

    private fun refresh() {
        if (_binding == null) return
        val ready = app.state as? LongevityApp.State.Ready ?: return
        val storage = app.storage()

        binding.tvDateLabel.text = Dates.fmtDayFull(selectedDay)
        val items = Schedule.getDayPlan(ready.content, selectedDay)
        adapter?.submit(items, storage.completionsOn(Dates.iso(selectedDay)))

        // Прогресс дня
        val doneCount = storage.completionsOn(Dates.iso(selectedDay)).size
        val total = items.size
        if (total == 0) {
            binding.tvProgress.text = "На этот день расписания нет"
            binding.progressBar.progress = 0
        } else {
            binding.tvProgress.text = "Сделано: $doneCount из $total"
            binding.progressBar.progress = doneCount * 100 / total
        }

        // Сводка по текущей неделе
        val monday = Dates.mondayOf(selectedDay)
        val parts = ArrayList<String>(7)
        for (i in 0 until 7) {
            val d = monday.plusDays(i.toLong())
            val dTotal = Schedule.getDayPlan(ready.content, d).size
            val dDone = storage.completionsOn(Dates.iso(d)).size
            parts.add("${Dates.WEEKDAYS[i]} %02d: %d/%d".format(d.dayOfMonth, dDone, dTotal))
        }
        binding.tvWeek.text = "Неделя: ${parts.joinToString("   ")}"
    }

    override fun onDestroyView() {
        super.onDestroyView()
        _binding = null
        adapter = null
    }
}

/** Пункты дня с чекбоксами; состояние берётся из [done] на каждый submit. */
private class TaskAdapter(
    private val content: com.revaks.longevity.core.Content,
    private val storage: com.revaks.longevity.data.Storage,
    private val onToggle: (ScheduleItem) -> Unit,
) : RecyclerView.Adapter<TaskAdapter.Holder>() {

    private val items = ArrayList<ScheduleItem>()
    private val done = HashSet<String>()
    private var date: String = ""

    fun submit(newItems: List<ScheduleItem>, doneIds: Set<String>) {
        items.clear()
        items.addAll(newItems)
        done.clear()
        done.addAll(doneIds)
        notifyDataSetChanged()
    }

    class Holder(val binding: ItemActivityTaskBinding) : RecyclerView.ViewHolder(binding.root)

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): Holder {
        val binding = ItemActivityTaskBinding.inflate(
            LayoutInflater.from(parent.context), parent, false,
        )
        return Holder(binding)
    }

    override fun getItemCount(): Int = items.size

    override fun onBindViewHolder(holder: Holder, position: Int) {
        val item = items[position]
        val b = holder.binding
        b.tvTime.text = Schedule.displayTime(item)
        b.tvTitle.text = item.title
        b.tvDetail.text = item.detail
        b.tvDetail.visibility =
            if (item.detail.isNotEmpty()) View.VISIBLE else View.GONE
        b.tvTime.setTextColor(content.catColor(item.cat))

        // setChecked без слушателя: нажатие пользователя обрабатывает ниже.
        b.cbTask.setOnCheckedChangeListener(null)
        b.cbTask.isChecked = item.id in done
        b.cbTask.setOnCheckedChangeListener { _, _ ->
            onToggle(item)
        }
    }
}
