package com.revaks.longevity.llm

import android.content.Context
import com.google.mediapipe.tasks.genai.llminference.LlmInference

/**
 * Лёгкая обёртка над MediaPipe LLM Inference (on-device нейросеть).
 *
 * Создание инстанса загружает модель в память — делать это нужно в фоне.
 * Через [LlmSession] инстанс один на процесс, поэтому вызовы generate()
 * сериализуются на самом инстансе.
 */
class LocalLlm private constructor(
    val modelPath: String,
    private val inference: LlmInference,
) {
    /** Синхронная генерация. Не вызывать из главного потока. */
    @Synchronized
    fun generate(prompt: String): String = inference.generateResponse(prompt)

    fun close() {
        runCatching { inference.close() }
    }

    companion object {
        /** Пытается загрузить модель; при любой ошибке возвращает null. */
        fun load(context: Context, modelPath: String, maxTokens: Int = 1024): LocalLlm? =
            try {
                val options = LlmInference.LlmInferenceOptions.builder()
                    .setModelPath(modelPath)
                    .setMaxTokens(maxTokens)
                    .setTemperature(0.4f)
                    .setTopK(40)
                    .build()
                val inference = LlmInference.createFromOptions(context, options)
                LocalLlm(modelPath, inference)
            } catch (t: Throwable) {
                null
            }
    }
}
