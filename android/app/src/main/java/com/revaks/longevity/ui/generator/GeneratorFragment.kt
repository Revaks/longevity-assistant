package com.revaks.longevity.ui.generator

import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.TextView
import androidx.activity.result.contract.ActivityResultContracts
import androidx.fragment.app.Fragment
import androidx.core.content.ContextCompat
import com.google.android.material.dialog.MaterialAlertDialogBuilder
import com.revaks.longevity.LongevityApp
import com.revaks.longevity.R
import com.revaks.longevity.core.MenuDay
import com.revaks.longevity.core.gen.MealGenerator
import com.revaks.longevity.core.gen.WorkoutGenerator
import com.revaks.longevity.core.gen.WorkoutProgram
import com.revaks.longevity.databinding.FragmentGeneratorBinding
import com.revaks.longevity.llm.GroundedPrompts
import com.revaks.longevity.llm.LlmSession
import com.revaks.longevity.llm.LocalLlm
import com.revaks.longevity.llm.ModelDownloader
import com.revaks.longevity.llm.ModelManager
import com.revaks.longevity.ui.Ui
import org.json.JSONArray
import java.io.File
import java.util.concurrent.ExecutorService
import java.util.concurrent.Executors
import kotlin.random.Random

/**
 * Вкладка «Генератор»: меню недели (MIND) и программа тренировок.
 *
 * По умолчанию работает встроенный генератор на каталогах из книг.
 * Если установлена модель нейросети (LiteRT-LM, .litertlm), запрос уходит
 * модели, а при сбое автоматически включается встроенный генератор.
 */
class GeneratorFragment : Fragment() {

    private var _binding: FragmentGeneratorBinding? = null
    private val binding get() = _binding!!

    private val app get() = requireActivity().application as LongevityApp
    private val worker: ExecutorService = Executors.newSingleThreadExecutor()
    private val main = Handler(Looper.getMainLooper())

    /** Идёт ли загрузка модели (защита от повторной параллельной загрузки). */
    @Volatile
    private var llmLoading = false

    private val importModel =
        registerForActivityResult(ActivityResultContracts.OpenDocument()) { uri: Uri? ->
            android.util.Log.i("LongevityLlm", "Импорт: выбран файл uri=$uri")
            uri ?: return@registerForActivityResult
            importModelFile(uri)
        }

    override fun onCreateView(
        inflater: LayoutInflater, container: ViewGroup?, savedInstanceState: Bundle?,
    ): View {
        _binding = FragmentGeneratorBinding.inflate(inflater, container, false)
        return binding.root
    }

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)
        val ready = app.state as? LongevityApp.State.Ready ?: return
        Ui.pageSubtitle(this, binding.tvPageSubtitle)

        binding.btnModelDownload.setOnClickListener { askDownloadUrl() }
        binding.btnModelImport.setOnClickListener {
            android.util.Log.i("LongevityLlm", "Импорт: открываю выбор файла")
            importModel.launch(arrayOf("*/*"))
        }
        binding.btnModelRemove.setOnClickListener {
            worker.execute { LlmSession.reset() }
            ModelManager.forget(requireContext())
            refreshModelStatus()
        }

        binding.btnMenuGenerate.setOnClickListener { generateMenu() }
        binding.btnWorkoutGenerate.setOnClickListener { generateWorkout() }
        binding.rgLevel.check(R.id.mb_level_mid)

        refreshModelStatus()
    }

    // ------------------------------------------------------------------ модель

    private fun refreshModelStatus() {
        if (_binding == null) return
        val ctx = requireContext()
        val path = ModelManager.modelPath(ctx)
        binding.tvModelStatus.text = if (path != null) {
            val name = File(path).name
            "Модель установлена: $name (${ModelManager.humanSize(File(path).length())}). " +
                "Генерация пойдёт через нейросеть."
        } else {
            "Модель не установлена — работает встроенный генератор."
        }
        binding.btnModelRemove.isEnabled = path != null
    }

    private fun askDownloadUrl() {
        val input = EditText(requireContext()).apply {
            hint = "https://…/model.litertlm"
            setText(lastModelUrl())
        }
        MaterialAlertDialogBuilder(requireContext())
            .setTitle("Скачать модель")
            .setMessage(
                "Укажите прямую ссылку на файл модели LiteRT-LM (.litertlm).\n" +
                    "Модель скачивается один раз и хранится локально; генерация после " +
                    "этого работает офлайн.\n\n" +
                    "Где взять файл: нажмите «Открыть страницу загрузки» — откроется " +
                    "репозиторий моделей LiteRT (Gemma 4 E2B)."
            )
            .setView(input)
            .setNegativeButton("Отмена", null)
            .setNeutralButton("Открыть страницу загрузки") { _, _ -> openModelPage() }
            .setPositiveButton("Скачать") { _, _ ->
                val url = input.text.toString().trim()
                if (url.isNotEmpty()) {
                    rememberModelUrl(url)
                    startDownload(url)
                }
            }
            .show()
    }

    /** Открыть в браузере страницу с моделями LiteRT (.litertlm). */
    private fun openModelPage() {
        try {
            val intent = Intent(Intent.ACTION_VIEW, Uri.parse(MODEL_PAGE_URL))
            startActivity(intent)
        } catch (e: Exception) {
            binding.tvModelStatus.text = "Не удалось открыть браузер."
        }
    }

    private fun startDownload(url: String) {
        val ctx = requireContext()
        val fileName = "model.litertlm"
        val target = ModelManager.modelFile(ctx, fileName)
        binding.progressModel.visibility = View.VISIBLE
        binding.progressModel.progress = 0
        binding.tvModelStatus.text = "Скачиваю модель… 0%"
        binding.btnModelDownload.isEnabled = false

        ModelDownloader.start(url, target,
            onProgress = { done, total ->
                val percent = if (total > 0) (done * 100 / total).toInt() else 0
                main.post {
                    binding.progressModel.progress = percent.coerceIn(0, 100)
                    val doneStr = ModelManager.humanSize(done)
                    val totalStr = if (total > 0) ModelManager.humanSize(total) else "?"
                    binding.tvModelStatus.text = "Скачиваю модель… $percent% ($doneStr/$totalStr)"
                }
            },
            onDone = { result ->
                main.post {
                    binding.progressModel.visibility = View.GONE
                    binding.btnModelDownload.isEnabled = true
                    result.onSuccess { file ->
                        ModelManager.remember(ctx, file)
                        LlmSession.reset()
                        binding.tvModelStatus.text = "Модель скачана. Генерация через нейросеть."
                    }.onFailure { e ->
                        binding.tvModelStatus.text =
                            "Не удалось скачать модель: ${e.message ?: "ошибка сети"}"
                    }
                    refreshModelStatus()
                }
            })
    }

    private fun importModelFile(uri: Uri) {
        val ctx = requireContext()
        val target = ModelManager.modelFile(ctx, "model-import.litertlm")
        target.parentFile?.mkdirs()
        binding.progressModel.visibility = View.VISIBLE
        binding.progressModel.progress = 0
        binding.tvModelStatus.text = "Импортирую модель…"
        binding.btnModelImport.isEnabled = false

        worker.execute {
            runCatching {
                val total = runCatching {
                    ctx.contentResolver.openAssetFileDescriptor(uri, "r")?.use { it.length }
                        ?: -1L
                }.getOrDefault(-1L)
                var done = 0L
                ctx.contentResolver.openInputStream(uri)?.use { input ->
                    target.outputStream().use { output ->
                        val buffer = ByteArray(256 * 1024)
                        while (true) {
                            val read = input.read(buffer)
                            if (read < 0) break
                            output.write(buffer, 0, read)
                            done += read
                            val doneNow = done
                            if (total > 0) {
                                val percent = (doneNow * 100 / total).toInt()
                                main.post {
                                    if (_binding == null) return@post
                                    binding.progressModel.progress = percent.coerceIn(0, 100)
                                    binding.tvModelStatus.text =
                                        "Импортирую модель… $percent% " +
                                            "(${ModelManager.humanSize(doneNow)} / " +
                                            "${ModelManager.humanSize(total)})"
                                }
                            } else {
                                main.post {
                                    if (_binding == null) return@post
                                    binding.tvModelStatus.text =
                                        "Импортирую модель… ${ModelManager.humanSize(doneNow)}"
                                }
                            }
                        }
                    }
                } ?: error("Не удалось открыть файл (нет доступа)")
                if (target.length() == 0L) error("Файл пустой")
                ModelManager.remember(ctx, target)
                LlmSession.reset()
            }.onSuccess {
                android.util.Log.i("LongevityLlm", "Модель импортирована: ${target.absolutePath}")
                main.post {
                    if (_binding == null) return@post
                    binding.progressModel.visibility = View.GONE
                    binding.btnModelImport.isEnabled = true
                    refreshModelStatus()
                }
            }.onFailure { e ->
                android.util.Log.e("LongevityLlm", "Импорт модели не удался", e)
                main.post {
                    if (_binding == null) return@post
                    binding.progressModel.visibility = View.GONE
                    binding.btnModelImport.isEnabled = true
                    binding.tvModelStatus.text =
                        "Не удалось импортировать модель: ${e.message ?: e.javaClass.simpleName}"
                }
            }
        }
    }

    private fun lastModelUrl(): String = requireContext()
        .getSharedPreferences("llm_download", android.content.Context.MODE_PRIVATE)
        .getString("url", "").orEmpty()

    private fun rememberModelUrl(url: String) {
        requireContext().getSharedPreferences(
            "llm_download", android.content.Context.MODE_PRIVATE
        ).edit().putString("url", url).apply()
    }

    /** Загрузить модель, если она установлена; вызвать [onResult]. */
    private fun ensureLlm(onResult: (LocalLlm?) -> Unit) {
        LlmSession.current()?.let { cached ->
            onResult(cached)
            return
        }
        if (llmLoading) {
            // Один поток загрузки модели за раз: следующая генерация дождётся.
            main.postDelayed({ ensureLlm(onResult) }, 500)
            return
        }
        if (ModelManager.modelPath(app) == null) {
            onResult(null)
            return
        }
        llmLoading = true
        main.post { if (_binding != null) binding.tvModelStatus.text = "Загружаю модель в память…" }
        worker.execute {
            val loaded = LlmSession.load(app)
            llmLoading = false
            main.post {
                if (!isAdded || _binding == null) return@post
                if (loaded == null) {
                    val reason = LlmSession.lastError ?: "неизвестная ошибка"
                    binding.tvModelStatus.text =
                        "Не удалось загрузить модель: $reason. Работает встроенный генератор."
                }
                onResult(loaded)
            }
        }
    }

    // ------------------------------------------------------------------ меню

    private fun generateMenu() {
        val ready = app.state as? LongevityApp.State.Ready ?: return
        val target = binding.llMenuResult
        target.removeAllViews()
        binding.tvMenuNote.visibility = View.VISIBLE
        binding.tvMenuNote.text = "Генерирую…"
        binding.btnMenuGenerate.isEnabled = false
        ensureLlm { model ->
            if (model != null) {
                binding.tvMenuNote.text = "Нейросеть думает (может занять минуту)…"
            }
            worker.execute {
                var note = "Сгенерировано встроенным генератором (MIND)."
                var menu: List<MenuDay>? = null
                if (model != null) {
                    try {
                        val prompt = GroundedPrompts.menuPrompt(
                            ready.content, ready.index, ready.bookSearch,
                        )
                        val text = model.generate(prompt)
                        menu = parseMenu(text)
                        if (menu != null) {
                            note = "Меню сгенерировано нейросетью по RAG-контексту (MIND + книги)."
                        } else {
                            note = "Нейросеть вернула не JSON — показано меню встроенного генератора."
                        }
                    } catch (e: Exception) {
                        note = "Нейросеть недоступна (${e.message ?: "ошибка"}) — " +
                            "встроенный генератор."
                    }
                }
                if (menu == null) menu = MealGenerator.generateMenu()
                val finalMenu = menu
                main.post {
                    binding.btnMenuGenerate.isEnabled = true
                    renderMenu(finalMenu)
                    binding.tvMenuNote.text = note
                }
            }
        }
    }

    private fun renderMenu(menu: List<MenuDay>) {
        val ctx = requireContext()
        binding.llMenuResult.removeAllViews()
        for (day in menu) {
            val head = TextView(ctx).apply {
                text = day.day
                textSize = 15f
                setTypeface(typeface, android.graphics.Typeface.BOLD)
                setTextColor(ContextCompat.getColor(ctx, R.color.primary))
            }
            binding.llMenuResult.addView(head, topMargin(8))

            fun line(label: String, value: String) {
                val row = TextView(ctx).apply {
                    text = "$label: $value"
                    textSize = 13f
                    setTextColor(ContextCompat.getColor(ctx, R.color.text_primary))
                }
                binding.llMenuResult.addView(row)
            }
            line("Завтрак", day.breakfast)
            line("Обед", day.lunch)
            line("Ужин", day.dinner)
            line("Перекус", day.snack)
        }
    }

    private fun parseMenu(text: String): List<MenuDay>? {
        val start = text.indexOf('[')
        val end = text.lastIndexOf(']')
        if (start < 0 || end <= start) return null
        val arr = runCatching { JSONArray(text.substring(start, end + 1)) }.getOrNull()
            ?: return null
        if (arr.length() != 7) return null
        val days = (0 until arr.length()).mapNotNull { i ->
            val obj = arr.optJSONObject(i) ?: return@mapNotNull null
            val b = obj.optString("breakfast").trim()
            val l = obj.optString("lunch").trim()
            val d = obj.optString("dinner").trim()
            val s = obj.optString("snack").trim()
            if (b.isEmpty() || l.isEmpty() || d.isEmpty() || s.isEmpty()) return@mapNotNull null
            MenuDay(day = "День", breakfast = b, lunch = l, dinner = d, snack = s)
        }
        return if (days.size == 7) days else null
    }

    // ------------------------------------------------------------------ тренировки

    private fun generateWorkout() {
        val ready = app.state as? LongevityApp.State.Ready ?: return
        val level = when (binding.rgLevel.checkedButtonId) {
            R.id.mb_level_easy -> WorkoutGenerator.LEVELS[0]
            R.id.mb_level_hard -> WorkoutGenerator.LEVELS[2]
            else -> WorkoutGenerator.LEVELS[1]
        }
        binding.llWorkoutResult.removeAllViews()
        binding.tvWorkoutNote.visibility = View.VISIBLE
        binding.tvWorkoutNote.text = "Генерирую…"
        binding.btnWorkoutGenerate.isEnabled = false

        ensureLlm { model ->
            if (model != null) {
                binding.tvWorkoutNote.text = "Нейросеть думает (может занять минуту)…"
            }
            worker.execute {
                var note = "Сгенерировано встроенным генератором (по книге Москалева)."
                var llmText: String? = null
                if (model != null) {
                    try {
                        val prompt = GroundedPrompts.workoutPrompt(
                            ready.content, ready.index, ready.bookSearch, level,
                        )
                        llmText = model.generate(prompt).trim()
                        if (llmText.isNullOrEmpty()) {
                            note = "Нейросеть вернула пустой ответ — встроенный генератор."
                            llmText = null
                        } else {
                            note = "Программа сгенерирована нейросетью " +
                                "по RAG-контексту (уровень: $level)."
                        }
                    } catch (e: Exception) {
                        note = "Нейросеть недоступна — встроенный генератор."
                    }
                }
                val program = if (llmText == null)
                    WorkoutGenerator.generate(level = level)
                else null
                main.post {
                    binding.btnWorkoutGenerate.isEnabled = true
                    if (llmText != null) {
                        renderLlmText(llmText)
                    } else if (program != null) {
                        renderProgram(program)
                    }
                    binding.tvWorkoutNote.text = note
                }
            }
        }
    }

    private fun renderProgram(program: WorkoutProgram) {
        val ctx = requireContext()
        binding.llWorkoutResult.removeAllViews()
        for ((dayName, rows) in program.rowsByDay) {
            val head = TextView(ctx).apply {
                text = dayName
                textSize = 15f
                setTypeface(typeface, android.graphics.Typeface.BOLD)
                setTextColor(ContextCompat.getColor(ctx, R.color.primary))
            }
            binding.llWorkoutResult.addView(head, topMargin(8))
            for (row in rows) {
                val prefix = if (row.time.isNotEmpty()) "${row.time} — " else ""
                val line = TextView(ctx).apply {
                    text = "• $prefix${row.title}"
                    textSize = 13f
                    setTextColor(ContextCompat.getColor(ctx, R.color.text_primary))
                    setTypeface(typeface, android.graphics.Typeface.BOLD)
                }
                binding.llWorkoutResult.addView(line)
                if (row.detail.isNotEmpty()) {
                    val detail = TextView(ctx).apply {
                        text = "   ${row.detail}"
                        textSize = 12f
                        setTextColor(ContextCompat.getColor(ctx, R.color.text_muted))
                    }
                    binding.llWorkoutResult.addView(detail)
                }
            }
        }
    }

    private fun renderLlmText(text: String) {
        val ctx = requireContext()
        binding.llWorkoutResult.removeAllViews()
        val tv = TextView(ctx).apply {
            setText(text)
            setTextSize(14f)
            setTextColor(ContextCompat.getColor(ctx, R.color.text_primary))
            setTextIsSelectable(true)
        }
        binding.llWorkoutResult.addView(tv)
    }

    private fun topMargin(value: Int): LinearLayout.LayoutParams =
        LinearLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT,
        ).apply { topMargin = Ui.dp(binding.root, value) }

    override fun onDestroyView() {
        super.onDestroyView()
        worker.shutdown()
        _binding = null
    }

    companion object {
        /**
         * Репозиторий моделей LiteRT-LM (.litertlm) на HuggingFace —
         * здесь опубликованы Gemma 4 E2B и другие on-device модели.
         */
        private const val MODEL_PAGE_URL =
            "https://huggingface.co/litert-community/gemma-4-E2B-it-litert-lm/tree/main"
    }
}
