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
 * Если установлена модель нейросети (MediaPipe LLM), запрос уходит модели,
 * а при сбое автоматически включается встроенный генератор.
 */
class GeneratorFragment : Fragment() {

    private var _binding: FragmentGeneratorBinding? = null
    private val binding get() = _binding!!

    private val app get() = requireActivity().application as LongevityApp
    private val worker: ExecutorService = Executors.newSingleThreadExecutor()
    private val main = Handler(Looper.getMainLooper())

    /** Загруженный экземпляр нейросети (null, пока модель не используется). */
    @Volatile
    private var llm: LocalLlm? = null
    @Volatile
    private var llmLoading = false

    private val importModel =
        registerForActivityResult(ActivityResultContracts.OpenDocument()) { uri: Uri? ->
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
            importModel.launch(arrayOf("*/*"))
        }
        binding.btnModelRemove.setOnClickListener {
            worker.execute { llm?.close() }
            llm = null
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
            hint = "https://…/model.task"
            setText(lastModelUrl())
        }
        MaterialAlertDialogBuilder(requireContext())
            .setTitle("Скачать модель")
            .setMessage(
                "Укажите прямую ссылку на файл модели MediaPipe LLM (.task).\n" +
                    "Модель скачивается один раз и хранится локально; генерация после " +
                    "этого работает офлайн.\n\n" +
                    "Где взять файл: нажмите «Открыть страницу загрузки» — откроется " +
                    "официальная документация MediaPipe с разделом Models."
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

    /** Открыть в браузере официальную страницу с моделями MediaPipe LLM. */
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
        val fileName = "model.task"
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
        binding.tvModelStatus.text = "Импортирую модель…"
        worker.execute {
            val target = ModelManager.modelFile(ctx, "model-import.task")
            runCatching {
                ctx.contentResolver.openInputStream(uri)?.use { input ->
                    target.outputStream().use { output -> input.copyTo(output) }
                } ?: error("Не удалось открыть файл")
                ModelManager.remember(ctx, target)
            }.onFailure { e ->
                main.post {
                    binding.tvModelStatus.text =
                        "Не удалось импортировать модель: ${e.message ?: "ошибка"}"
                }
            }
            main.post { refreshModelStatus() }
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
        if (llm != null) {
            onResult(llm)
            return
        }
        if (llmLoading) {
            // Один поток загрузки модели за раз: следующая генерация дождётся.
            main.postDelayed({ ensureLlm(onResult) }, 500)
            return
        }
        val ctx = requireContext()
        val path = ModelManager.modelPath(ctx)
        if (path == null) {
            onResult(null)
            return
        }
        llmLoading = true
        main.post { binding.tvModelStatus.text = "Загружаю модель в память…" }
        worker.execute {
            val loaded = LocalLlm.load(ctx, path)
            llm = loaded
            llmLoading = false
            main.post {
                if (loaded == null) {
                    binding.tvModelStatus.text =
                        "Не удалось загрузить модель (возможно, файл не подходит). " +
                            "Работает встроенный генератор."
                }
                onResult(loaded)
            }
        }
    }

    // ------------------------------------------------------------------ меню

    private fun generateMenu() {
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
                        val text = model.generate(MENU_PROMPT)
                        menu = parseMenu(text)
                        if (menu != null) note = "Меню сгенерировано нейросетью."
                        else note = "Нейросеть вернула не JSON — показано меню встроенного генератора."
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
                        val prompt = WORKOUT_PROMPT.replace("{level}", level)
                        llmText = model.generate(prompt).trim()
                        if (llmText.isNullOrEmpty()) {
                            note = "Нейросеть вернула пустой ответ — встроенный генератор."
                            llmText = null
                        } else {
                            note = "Программа сгенерирована нейросетью (уровень: $level)."
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
         * Официальная страница MediaPipe LLM Inference: раздел «Models»,
         * где публикуются ссылки на файлы .task (Kaggle).
         */
        private const val MODEL_PAGE_URL =
            "https://ai.google.dev/edge/mediapipe/solutions/genai/llm_inference#models"

        private val MENU_PROMPT: String = """
            Ты — диетолог, специалист по средиземноморско-скандинавской диете MIND.
            Составь недельное меню (7 дней) по правилам MIND: цельные злаки ежедневно,
            ягоды 2+ раза, орехи, зелёные листовые овощи, оливковое масло, бобовые 3+ раз,
            птица вместо красного мяса, жирная рыба 2–3 раза в неделю, ужин за 3–4 часа до сна,
            минимум сахара и соли, без жарки (готовка до 120 °C).
            Ответь строго JSON-массивом из 7 объектов с ключами:
            day, breakfast, lunch, dinner, snack. Без текста вокруг.
        """.trimIndent()

        private val WORKOUT_PROMPT: String = """
            Ты — тренер по оздоровительной физкультуре, работаешь по принципам
            А. А. Москалева: аэробная нагрузка 30–60 минут 3–5 раз в неделю, силовые
            упражнения на основные группы мышц 2 раза в неделю, ежедневная умеренная
            активность. Составь программу тренировок на неделю для уровня: {level}.
            Для каждого дня недели (Понедельник..Воскресенье) напиши: день, время и
            конкретные упражнения/активность. Отвечай по-русски, кратко, списком дней.
        """.trimIndent()
    }
}
