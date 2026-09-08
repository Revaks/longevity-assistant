package com.revaks.longevity.ui.nutrition

import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.LinearLayout
import android.widget.TextView
import androidx.fragment.app.Fragment
import com.revaks.longevity.LongevityApp
import com.revaks.longevity.core.MenuDay
import com.revaks.longevity.core.MindGroup
import com.revaks.longevity.databinding.FragmentNutritionBinding
import com.revaks.longevity.ui.Ui

/**
 * Вкладка «Питание»: меню недели по диете MIND + правила (полезные группы
 * и что ограничить). Генерация меню локальной моделью (Ollama) на Android
 * не переносится — показывается базовое меню из данных.
 */
class NutritionFragment : Fragment() {

    private var _binding: FragmentNutritionBinding? = null
    private val binding get() = _binding!!

    private val app get() = requireActivity().application as LongevityApp

    override fun onCreateView(
        inflater: LayoutInflater, container: ViewGroup?, savedInstanceState: Bundle?,
    ): View {
        _binding = FragmentNutritionBinding.inflate(inflater, container, false)
        return binding.root
    }

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)
        val ready = app.state as? LongevityApp.State.Ready ?: return
        val content = ready.content

        Ui.pageSubtitle(this, binding.tvPageSubtitle)
        buildMenu(content.menu)
        buildGroups(content.mindGood, green = true)
        buildGroups(content.mindLimit, green = false)
    }

    private fun buildMenu(menu: List<MenuDay>) {
        val ctx = requireContext()
        for (day in menu) {
            val dayName = TextView(ctx).apply {
                text = day.day
                textSize = 15f
                setTypeface(typeface, android.graphics.Typeface.BOLD)
                setTextColor(0xFF0F766E.toInt())
            }
            binding.llMenu.addView(dayName, topMargin(6))

            fun meal(label: String, value: String) {
                val row = TextView(ctx).apply {
                    text = "$label: $value"
                    textSize = 13f
                    setTextColor(0xFF111827.toInt())
                }
                binding.llMenu.addView(row)
            }
            meal("Завтрак", day.breakfast)
            meal("Обед", day.lunch)
            meal("Ужин", day.dinner)
            meal("Перекус", day.snack)
        }
    }

    private fun buildGroups(groups: List<MindGroup>, green: Boolean) {
        val ctx = requireContext()
        val container = if (green) binding.llGood else binding.llLimit
        val color = if (green) 0xFF2E7D32.toInt() else 0xFFB91C1C.toInt()
        for (g in groups) {
            val line = TextView(ctx).apply {
                text = buildString {
                    append("• ${g.name} — ${g.amount}")
                    if (g.note.isNotEmpty()) append(" (${g.note})")
                }
                textSize = 13f
                setTextColor(color)
            }
            container.addView(line, topMargin(2))
        }
    }

    /** LayoutParams с верхним отступом (в dp от корня фрагмента). */
    private fun topMargin(dpValue: Int): LinearLayout.LayoutParams =
        LinearLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT,
        ).apply { topMargin = Ui.dp(binding.root, dpValue) }

    override fun onDestroyView() {
        super.onDestroyView()
        _binding = null
    }
}
