package com.revaks.longevity.llm

import android.content.Context
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
        /**
         * Пытается загрузить модель на CPU-бэкенде (XNNPack, работает на любом
         * современном устройстве); при любой ошибке возвращает null.
         */
        fun load(context: Context, modelPath: String, maxTokens: Int = 1024): LocalLlm? =
            try {
                val cacheDir = runCatching { context.cacheDir.absolutePath }.getOrNull()
                val engine = Engine(
                    EngineConfig(
                        modelPath = modelPath,
                        backend = Backend.CPU(),
                        cacheDir = cacheDir,
                    )
                ).also { it.initialize() }
                LocalLlm(modelPath, engine, maxTokens)
            } catch (t: Throwable) {
                null
            }
    }
}
