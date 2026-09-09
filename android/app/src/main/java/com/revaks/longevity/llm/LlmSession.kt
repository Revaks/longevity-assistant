package com.revaks.longevity.llm

import android.content.Context

/**
 * Процессный кэш загруженной модели: одна загруженная модель на приложение,
 * чтобы «Генератор» и «Ассистент» не грузили файл в память по отдельности.
 */
object LlmSession {

    @Volatile
    private var instance: LocalLlm? = null

    @Volatile
    private var loadedPath: String? = null

    private val lock = Any()

    /** Уже загруженный экземпляр (без попытки загрузки). */
    fun current(): LocalLlm? = instance

    /** Загрузить модель, если она установлена (вызывать из фонового потока). */
    fun load(context: Context): LocalLlm? {
        val path = ModelManager.modelPath(context) ?: return null
        val existing = instance
        if (existing != null && loadedPath == path) return existing
        synchronized(lock) {
            val again = instance
            if (again != null && loadedPath == path) return again
            instance?.close()
            instance = null
            val loaded = LocalLlm.load(context, path)
            instance = loaded
            loadedPath = path
            return loaded
        }
    }

    /** Закрыть и забыть модель (при её удалении/замене). */
    fun reset() {
        synchronized(lock) {
            instance?.close()
            instance = null
            loadedPath = null
        }
    }
}
