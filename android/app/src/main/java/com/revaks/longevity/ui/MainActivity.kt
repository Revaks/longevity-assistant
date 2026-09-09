package com.revaks.longevity.ui

import android.os.Bundle
import android.util.TypedValue
import android.view.Gravity
import android.widget.LinearLayout
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import androidx.fragment.app.Fragment
import com.google.android.material.bottomsheet.BottomSheetDialog
import com.revaks.longevity.LongevityApp
import com.revaks.longevity.R
import com.revaks.longevity.databinding.ActivityMainBinding
import com.revaks.longevity.databinding.ActivityLoadingBinding
import com.revaks.longevity.ui.assistant.AssistantFragment
import com.revaks.longevity.ui.knowledge.KnowledgeFragment

/**
 * Главное окно. Внизу — три главных раздела (Календарь, Активность, Заметки)
 * и «Ещё», в котором живут справочные разделы: Питание, База знаний,
 * Ассистент. BottomNavigationView рассчитан максимум на 5 пунктов, поэтому
 * шестой раздел не помещается в нижнюю панель.
 * До готовности данных (загрузка книг) показывает экран загрузки.
 */
class MainActivity : AppCompatActivity() {

    private lateinit var app: LongevityApp
    private var loading: ActivityLoadingBinding? = null
    private var main: ActivityMainBinding? = null
    private var restoredTab: String? = null
    private var suppressNav = false
    private var currentKey = "calendar"

    private val listener = { onStateChanged() }

    /** Все шесть разделов приложения (порядок как в десктопе). */
    private val tags = listOf(
        "calendar", "activity", "notes", "nutrition", "knowledge", "assistant",
    )

    /** Разделы в нижней панели; остальные открываются через «Ещё». */
    private val barKeys = setOf("calendar", "activity", "notes")

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        restoredTab = savedInstanceState?.getString(KEY_TAB)
        app = application as LongevityApp
        loading = ActivityLoadingBinding.inflate(layoutInflater)
        setContentView(loading!!.root)
        app.addListener(listener)
        onStateChanged()
    }

    override fun onDestroy() {
        app.removeListener(listener)
        super.onDestroy()
    }

    private fun onStateChanged() {
        when (val state = app.state) {
            is LongevityApp.State.Ready -> showMain()
            is LongevityApp.State.Failed -> {
                val binding = loading ?: return
                binding.progress.visibility = android.view.View.GONE
                binding.btnRetry.visibility = android.view.View.VISIBLE
                binding.tvStatus.text = "Не удалось загрузить данные приложения"
                binding.tvError.visibility = android.view.View.VISIBLE
                binding.tvError.text = state.reason
                binding.btnRetry.setOnClickListener {
                    binding.progress.visibility = android.view.View.VISIBLE
                    binding.btnRetry.visibility = android.view.View.GONE
                    binding.tvError.visibility = android.view.View.GONE
                    app.startLoad()
                }
            }
            LongevityApp.State.Loading -> Unit // экран загрузки уже показан
        }
    }

    private fun showMain() {
        if (main != null) return
        val binding = ActivityMainBinding.inflate(layoutInflater)
        main = binding
        setContentView(binding.root)

        binding.bottomNav.setOnItemSelectedListener { item ->
            when (item.itemId) {
                R.id.nav_calendar -> showTab("calendar")
                R.id.nav_activity -> showTab("activity")
                R.id.nav_notes -> showTab("notes")
                R.id.nav_more -> {
                    if (!suppressNav) showMoreSheet()
                    suppressNav = false
                }
            }
            true
        }

        val saved = restoredTab ?: "calendar"
        // Восстанавливаем вкладку: выбираем пункт панели (для разделов «Ещё» —
        // сам пункт «Ещё», без открытия листа).
        suppressNav = true
        binding.bottomNav.selectedItemId = menuIdOf(saved)
        suppressNav = false
        showTab(saved)
    }

    /** Открыть раздел из списка «Ещё» (Питание / База знаний / Ассистент). */
    private fun openSecondary(key: String) {
        val binding = main ?: return
        suppressNav = true
        binding.bottomNav.selectedItemId = R.id.nav_more
        suppressNav = false
        showTab(key)
    }

    /** Нижний лист «Ещё» с остальными разделами. */
    private fun showMoreSheet() {
        val activity = this
        val dialog = BottomSheetDialog(activity)
        val column = LinearLayout(activity).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(12), dp(6), dp(12), dp(18))
        }
        val title = TextView(activity).apply {
            text = "Разделы"
            textSize = 13f
            setTextColor(ContextCompat.getColor(activity, R.color.text_muted))
            setPadding(dp(16), dp(6), dp(16), dp(4))
        }
        column.addView(title)

        val rows = listOf(
            Triple("Питание", R.drawable.ic_nutrition, "nutrition"),
            Triple("База знаний", R.drawable.ic_knowledge, "knowledge"),
            Triple("Ассистент", R.drawable.ic_assistant, "assistant"),
        )
        for ((label, iconRes, key) in rows) {
            val row = TextView(activity).apply {
                text = label
                textSize = 16f
                setTextColor(ContextCompat.getColor(activity, R.color.text_primary))
                gravity = Gravity.CENTER_VERTICAL
                setPadding(dp(16), dp(15), dp(16), dp(15))
                val icon = ContextCompat.getDrawable(activity, iconRes)
                icon?.setTint(ContextCompat.getColor(activity, R.color.primary))
                setCompoundDrawablesWithIntrinsicBounds(icon, null, null, null)
                compoundDrawablePadding = dp(16)
                val out = TypedValue()
                activity.theme.resolveAttribute(
                    android.R.attr.selectableItemBackground, out, true
                )
                setBackgroundResource(out.resourceId)
                setOnClickListener {
                    dialog.dismiss()
                    openSecondary(key)
                }
            }
            column.addView(row)
        }
        dialog.setContentView(column)
        dialog.show()
    }

    private fun dp(value: Int): Int =
        (value * resources.displayMetrics.density).toInt()

    private fun showTab(key: String) {
        currentKey = key
        val container = main ?: return
        val fm = supportFragmentManager
        val ft = fm.beginTransaction()
        for (tagKey in tags) {
            val existing = fm.findFragmentByTag(tagKey)
            if (tagKey == key) {
                if (existing == null) {
                    ft.add(container.fragmentContainer.id, newFragment(tagKey), tagKey)
                } else {
                    ft.show(existing)
                }
            } else if (existing != null) {
                ft.hide(existing)
            }
        }
        ft.commitAllowingStateLoss()
        fm.executePendingTransactions()
        // Гарантия единственного видимого фрагмента: FragmentTransaction.hide
        // прячет вью не всегда вовремя, если оно создалось позже — поэтому
        // принудительно оставляем видимым только активный раздел.
        for (fragment in fm.fragments) {
            if (!fragment.isAdded) continue
            val view = fragment.view ?: continue
            view.visibility =
                if (fragment.tag == key) android.view.View.VISIBLE else android.view.View.GONE
        }
    }

    private fun newFragment(key: String): Fragment = when (key) {
        "activity" -> com.revaks.longevity.ui.activity.ActivityFragment()
        "notes" -> com.revaks.longevity.ui.notes.NotesFragment()
        "nutrition" -> com.revaks.longevity.ui.nutrition.NutritionFragment()
        "knowledge" -> KnowledgeFragment()
        "assistant" -> AssistantFragment()
        else -> com.revaks.longevity.ui.calendar.CalendarFragment()
    }

    override fun onSaveInstanceState(outState: Bundle) {
        super.onSaveInstanceState(outState)
        outState.putString(KEY_TAB, currentKey)
    }

    private fun menuIdOf(key: String): Int = when (key) {
        "activity" -> R.id.nav_activity
        "notes" -> R.id.nav_notes
        "calendar" -> R.id.nav_calendar
        else -> R.id.nav_more
    }

    companion object {
        private const val KEY_TAB = "active_tab"
    }
}
