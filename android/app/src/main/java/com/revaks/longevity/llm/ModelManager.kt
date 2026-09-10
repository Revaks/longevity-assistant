package com.revaks.longevity.llm

import android.content.Context
import java.io.File

/**
 * Состояние скачанной/импортированной модели нейросети.
 *
 * Модель лежит вне APK (в каталоге приложения на внешнем хранилище),
 * путь запоминается в SharedPreferences. Модели, как правило, большие
 * (сотни МБ — несколько ГБ), поэтому в assets их не кладём.
 */
object ModelManager {

    private const val PREFS = "llm_model"
    private const val KEY_PATH = "model_path"

    fun modelDir(context: Context): File =
        File(context.getExternalFilesDir(null) ?: context.filesDir, "models")

    fun modelFile(context: Context, fileName: String): File =
        File(modelDir(context), fileName)

    /** Путь к установленной модели или null. */
    fun modelPath(context: Context): String? {
        val prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        val path = prefs.getString(KEY_PATH, null) ?: return null
        return if (File(path).isFile) path else null
    }

    /** Запомнить установленную модель. */
    fun remember(context: Context, file: File) {
        modelDir(context).mkdirs()
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .edit().putString(KEY_PATH, file.absolutePath).apply()
    }

    fun forget(context: Context) {
        modelPath(context)?.let { File(it).delete() }
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .edit().remove(KEY_PATH).apply()
    }

    fun humanSize(bytes: Long): String = when {
        bytes >= 1024L * 1024 * 1024 -> "%.2f ГБ".format(bytes / 1024.0 / 1024 / 1024)
        bytes >= 1024L * 1024 -> "%.0f МБ".format(bytes / 1024.0 / 1024)
        else -> "%.0f КБ".format(bytes / 1024.0)
    }
}
