package com.revaks.longevity.ui.notes

import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import androidx.fragment.app.Fragment
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.RecyclerView
import com.google.android.material.dialog.MaterialAlertDialogBuilder
import com.revaks.longevity.LongevityApp
import com.revaks.longevity.core.Dates
import com.revaks.longevity.data.DiaryEntry
import com.revaks.longevity.databinding.DialogNoteEditorBinding
import com.revaks.longevity.databinding.FragmentNotesBinding
import com.revaks.longevity.databinding.ItemNoteBinding
import com.revaks.longevity.ui.Ui
import java.time.LocalDate

/**
 * Вкладка «Заметки»: дневник с несколькими записями на каждый день.
 * «Сохранить» добавляет запись, а не заменяет прошлую (таблица diary).
 */
class NotesFragment : Fragment() {

    private var _binding: FragmentNotesBinding? = null
    private val binding get() = _binding!!

    private var selectedDay: LocalDate = LocalDate.now()
    private var adapter: NotesAdapter? = null

    private val app get() = requireActivity().application as LongevityApp

    override fun onCreateView(
        inflater: LayoutInflater, container: ViewGroup?, savedInstanceState: Bundle?,
    ): View {
        _binding = FragmentNotesBinding.inflate(inflater, container, false)
        return binding.root
    }

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)
        val ready = app.state as? LongevityApp.State.Ready
        if (ready == null) return

        Ui.pageSubtitle(this, binding.tvPageSubtitle)
        adapter = NotesAdapter { entry -> openEditor(entry) }
        binding.rvEntries.layoutManager = LinearLayoutManager(requireContext())
        binding.rvEntries.adapter = adapter

        binding.btnPrev.setOnClickListener { changeDay(selectedDay.minusDays(1)) }
        binding.btnNext.setOnClickListener { changeDay(selectedDay.plusDays(1)) }
        binding.btnToday.setOnClickListener { changeDay(LocalDate.now()) }
        binding.btnAdd.setOnClickListener { openEditor(null) }
        refresh()
    }

    private fun changeDay(day: LocalDate) {
        selectedDay = day
        refresh()
    }

    private fun refresh() {
        if (_binding == null) return
        val storage = app.storage()
        val date = Dates.iso(selectedDay)
        binding.tvDateLabel.text = Dates.fmtDayFull(selectedDay)
        val entries = storage.diaryEntriesOn(date)
        adapter?.submit(entries)
        binding.tvCount.text =
            if (entries.isEmpty()) "Нет записей на этот день" else "Записей: ${entries.size}"
        binding.tvEmpty.visibility =
            if (entries.isEmpty()) View.VISIBLE else View.GONE
    }

    private fun openEditor(entry: DiaryEntry?) {
        val storage = app.storage()
        val dialogBinding = DialogNoteEditorBinding.inflate(layoutInflater)
        if (entry != null) {
            dialogBinding.etText.setText(entry.text)
            dialogBinding.etText.setSelection(entry.text.length)
            dialogBinding.tvHint.visibility = View.GONE
        }

        val builder = MaterialAlertDialogBuilder(requireContext())
            .setTitle(if (entry == null) "Новая запись" else "Правка записи")
            .setView(dialogBinding.root)
            .setNegativeButton("Отмена", null)
            .setPositiveButton(if (entry == null) "Добавить" else "Сохранить") { _, _ ->
                val text = dialogBinding.etText.text?.toString()?.trim().orEmpty()
                if (text.isEmpty()) return@setPositiveButton
                if (entry == null) {
                    storage.addDiary(Dates.iso(selectedDay), text)
                } else {
                    storage.updateDiary(entry.id, text)
                }
                refresh()
            }
        if (entry != null) {
            builder.setNeutralButton("Удалить") { _, _ ->
                storage.deleteDiary(entry.id)
                refresh()
            }
        }
        val dialog = builder.create()
        dialog.setOnShowListener { dialogBinding.etText.requestFocus() }
        dialog.show()
    }

    override fun onDestroyView() {
        super.onDestroyView()
        _binding = null
        adapter = null
    }
}

/** Список записей дня; клик по записи открывает редактор. */
private class NotesAdapter(
    private val onClick: (DiaryEntry) -> Unit,
) : RecyclerView.Adapter<NotesAdapter.Holder>() {

    private val items = ArrayList<DiaryEntry>()

    fun submit(newItems: List<DiaryEntry>) {
        items.clear()
        items.addAll(newItems)
        notifyDataSetChanged()
    }

    class Holder(val binding: ItemNoteBinding) : RecyclerView.ViewHolder(binding.root)

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): Holder {
        val binding = ItemNoteBinding.inflate(LayoutInflater.from(parent.context), parent, false)
        return Holder(binding)
    }

    override fun getItemCount(): Int = items.size

    override fun onBindViewHolder(holder: Holder, position: Int) {
        val entry = items[position]
        holder.binding.tvTime.text = Ui.localTime(entry.created)
        holder.binding.tvText.text = entry.text
        holder.binding.root.setOnClickListener { onClick(entry) }
    }
}
