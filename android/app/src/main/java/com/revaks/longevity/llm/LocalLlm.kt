package com.revaks.longevity.llm

import android.content.Context
import android.util.Log
import com.google.ai.edge.litertlm.Backend
import com.google.ai.edge.litertlm.Content
import com.google.ai.edge.litertlm.ConversationConfig
import com.google.ai.edge.litertlm.Engine
import com.google.ai.edge.litertlm.EngineConfig
import com.google.ai.edge.litertlm.Message
import com.google.ai.edge.litertlm.SamplerConfig

/**
 * Лёгкая обёртка над LiteRT-LM — on-device нейросеть в формате .litertlm
 * (например, Gemma 4 E2B из HuggingFace litert-community).
 *
 * Создание [Engine] загружает модель в память (десятки секунд) — делать это
 * нужно в фоне. Через [LlmSession] инстанс один на процесс, поэтому вызовы
 * generate() сериализуются на самом инстансе.
 */
class LocalLlm private constructor(
    val modelPath: String,
    private val engine: Engine,
    private val maxOutputTokens: Int,
) {
    /**
     * Полный текстовый ответ на промпт (отдельная короткоживущая беседа,
     * история не накапливается). Не вызывать из главного потока.
     */
    @Synchronized
    fun generate(prompt: String): String {
        val config = ConversationConfig(
            samplerConfig = SamplerConfig(topK = 40, topP = 0.95, temperature = 0.4),
            maxOutputToken = maxOutputTokens,
        )
        engine.createConversation(config).use { conversation ->
            val message = conversation.sendMessage(prompt)
            return textOf(message)
        }
    }

    fun close() {
        runCatching { engine.close() }
    }

    private fun textOf(message: Message): String {
        val text = message.contents.contents
            .filterIsInstance<Content.Text>()
            .joinToString("") { it.text }
        return text.trim().ifEmpty { message.toString() }
    }

    companion object {
        private const val TAG = "LongevityLlm"

        /** Текст последней ошибки загрузки — показывается в интерфейсе. */
        @Volatile
        var lastError: String? = null
            private set

        /**
         * Пытается загрузить модель. Бэкенды перебираются по очереди:
         * сначала CPU (XNNPack — работает везде), затем GPU.
         * При любой ошибке возвращает null, а причину кладёт в [lastError].
         */
        fun load(context: Context, modelPath: String, maxTokens: Int = 1024): LocalLlm? {
            lastError = null
            val cacheDir = runCatching { context.cacheDir.absolutePath }.getOrNull()
            val errors = ArrayList<String>()
            for ((name, backend) in listOf("CPU" to Backend.CPU(), "GPU" to Backend.GPU())) {
                try {
                    val engine = Engine(
                        EngineConfig(
                            modelPath = modelPath,
                            backend = backend,
                            cacheDir = cacheDir,
                        )
                    ).also { it.initialize() }
                    Log.i(TAG, "Модель загружена ($name): $modelPath")
                    return LocalLlm(modelPath, engine, maxTokens)
                } catch (t: Throwable) {
                    val reason = t.message?.takeIf { it.isNotBlank() }
                        ?: t.javaClass.simpleName
                    Log.e(TAG, "Не удалось загрузить модель на $name: $reason", t)
                    errors.add("$name: $reason")
                }
            }
            lastError = errors.joinToString("; ")
            return null
        }
    }
}
