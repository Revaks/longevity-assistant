package com.revaks.longevity.ui

import android.os.Bundle
import androidx.appcompat.app.AppCompatActivity
import androidx.fragment.app.Fragment
import com.revaks.longevity.LongevityApp
import com.revaks.longevity.databinding.ActivityMainBinding
import com.revaks.longevity.databinding.ActivityLoadingBinding
import com.revaks.longevity.ui.assistant.AssistantFragment
import com.revaks.longevity.ui.knowledge.KnowledgeFragment

/**
 * Главное окно: нижняя навигация по шести вкладкам, как у десктопа.
 * До готовности данных (загрузка книг) показывает экран загрузки.
 */
class MainActivity : AppCompatActivity() {

    private lateinit var app: LongevityApp
    private var loading: ActivityLoadingBinding? = null
    private var main: ActivityMainBinding? = null
    private var restoredTab: String? = null

    private val listener = { onStateChanged() }

    private val tags = listOf(
        "calendar", "activity", "notes", "nutrition", "knowledge", "assistant",
    )

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
            val key = when (item.itemId) {
                com.revaks.longevity.R.id.nav_calendar -> "calendar"
                com.revaks.longevity.R.id.nav_activity -> "activity"
                com.revaks.longevity.R.id.nav_notes -> "notes"
                com.revaks.longevity.R.id.nav_nutrition -> "nutrition"
                com.revaks.longevity.R.id.nav_knowledge -> "knowledge"
                else -> "assistant"
            }
            showTab(key)
            true
        }

        val saved = restoredTab ?: "calendar"
        binding.bottomNav.selectedItemId = menuId(saved)
        showTab(saved)
    }

    private fun showTab(key: String) {
        val fm = supportFragmentManager
        val ft = fm.beginTransaction()
        for (tagKey in tags) {
            val existing = fm.findFragmentByTag(tagKey)
            if (tagKey == key) {
                if (existing == null) ft.add(
                    main!!.fragmentContainer.id, newFragment(tagKey), tagKey
                ) else ft.show(existing)
            } else if (existing != null && !existing.isHidden) {
                ft.hide(existing)
            }
        }
        ft.commitAllowingStateLoss()
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
        outState.putString(KEY_TAB, currentTab())
    }

    private fun currentTab(): String {
        val binding = main ?: return "calendar"
        return when (binding.bottomNav.selectedItemId) {
            com.revaks.longevity.R.id.nav_calendar -> "calendar"
            com.revaks.longevity.R.id.nav_activity -> "activity"
            com.revaks.longevity.R.id.nav_notes -> "notes"
            com.revaks.longevity.R.id.nav_nutrition -> "nutrition"
            com.revaks.longevity.R.id.nav_knowledge -> "knowledge"
            else -> "assistant"
        }
    }

    private fun menuId(key: String): Int = when (key) {
        "activity" -> com.revaks.longevity.R.id.nav_activity
        "notes" -> com.revaks.longevity.R.id.nav_notes
        "nutrition" -> com.revaks.longevity.R.id.nav_nutrition
        "knowledge" -> com.revaks.longevity.R.id.nav_knowledge
        "assistant" -> com.revaks.longevity.R.id.nav_assistant
        else -> com.revaks.longevity.R.id.nav_calendar
    }

    companion object {
        private const val KEY_TAB = "active_tab"
    }
}
