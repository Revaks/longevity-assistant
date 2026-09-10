package com.revaks.longevity.llm

import android.content.Context
import android.util.Log
import com.google.ai.edge.litertlm.Backend
import com.google.ai.edge.litertlm.Content
import com.google.ai.edge.litertlm.ConversationConfig
import com.google.ai.edge.litertlm.Engine
import com.google.ai.edge.litertlm.EngineConfig
import com.google.ai.edge.litertlm.ExperimentalApi
import com.google.ai.edge.litertlm.ExperimentalFlags
import com.google.ai.edge.litertlm.Message
import com.google.ai.edge.litertlm.MessageCallback
import com.google.ai.edge.litertlm.SamplerConfig
import java.util.concurrent.CountDownLatch

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
    /** Имя бэкенда, на котором удалось поднять движок ("CPU"/"GPU"). */
    val backendName: String,
) {
    /**
     * Ответ на промпт (отдельная короткоживущая беседа, история не копится).
     * Токены по мере генерации отдаются в [onToken] — можно показывать ответ
     * сразу. Не вызывать из главного потока.
     */
    @Synchronized
    fun generate(prompt: String, onToken: (String) -> Unit = {}): String {
        val config = ConversationConfig(
            samplerConfig = SamplerConfig(topK = 40, topP = 0.95, temperature = 0.4),
            maxOutputToken = maxOutputTokens,
        )
        engine.createConversation(config).use { conversation ->
            val full = StringBuilder()
            val latch = CountDownLatch(1)
            val failure = java.util.concurrent.atomic.AtomicReference<Throwable?>(null)

            conversation.sendMessageAsync(prompt, object : MessageCallback {
                override fun onMessage(message: Message) {
                    val chunk = textOf(message)
                    if (chunk.isEmpty()) return
                    // Обработка обоих вариантов потока: пофрагментно и «накопительно».
                    val delta = if (chunk.startsWith(full)) chunk.substring(full.length) else chunk
                    if (delta.isEmpty()) return
                    full.append(delta)
                    onToken(delta)
                }

                override fun onDone() {
                    latch.countDown()
                }

                override fun onError(t: Throwable) {
                    failure.set(t)
                    latch.countDown()
                }
            })
            latch.await()
            failure.get()?.let { throw it }
            return full.toString().trim()
        }
    }

    fun close() {
        runCatching { engine.close() }
    }

    private fun textOf(message: Message): String = message.contents.contents
        .filterIsInstance<Content.Text>()
        .joinToString("") { it.text }

    companion object {
        private const val TAG = "LongevityLlm"

        /** Текст последней ошибки загрузки — показывается в интерфейсе. */
        @Volatile
        var lastError: String? = null
            private set

        /** Бэкенд загруженной модели (для строки состояния). */
        @Volatile
        var lastBackend: String? = null
            private set

        /**
         * Пытается загрузить модель. Сначала GPU (заметно быстрее на телефоне),
         * затем CPU (XNNPack — работает везде). При любой ошибке возвращает null,
         * а причину кладёт в [lastError].
         */
        fun load(context: Context, modelPath: String, maxTokens: Int = 768): LocalLlm? {
            lastError = null
            lastBackend = null
            enableFastDecoding()
            val cacheDir = runCatching { context.cacheDir.absolutePath }.getOrNull()
            val errors = ArrayList<String>()
            for ((name, backend) in listOf("GPU" to Backend.GPU(), "CPU" to Backend.CPU())) {
                try {
                    val engine = Engine(
                        EngineConfig(
                            modelPath = modelPath,
                            backend = backend,
                            cacheDir = cacheDir,
                        )
                    ).also { it.initialize() }
                    Log.i(TAG, "Модель загружена ($name): $modelPath")
                    lastBackend = name
                    return LocalLlm(modelPath, engine, maxTokens, name)
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

        /** Ускорение декодирования: спекулятивное декодирование (MTP). */
        @OptIn(ExperimentalApi::class)
        private fun enableFastDecoding() {
            runCatching { ExperimentalFlags.enableSpeculativeDecoding = true }
                .onFailure { Log.w(TAG, "MTP недоступен: ${it.message}") }
        }
    }
}
