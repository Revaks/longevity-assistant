package com.revaks.longevity.ui.assistant

import android.graphics.Color
import android.graphics.Typeface
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.FrameLayout
import android.view.Gravity
import androidx.core.content.ContextCompat
import androidx.fragment.app.Fragment
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.RecyclerView
import com.google.android.material.chip.Chip
import com.revaks.longevity.LongevityApp
import com.revaks.longevity.R
import com.revaks.longevity.core.AssistantEngine
import com.revaks.longevity.databinding.FragmentAssistantBinding
import com.revaks.longevity.databinding.ItemChatBinding
import com.revaks.longevity.llm.GroundedPrompts
import com.revaks.longevity.llm.LlmSession
import com.revaks.longevity.llm.ModelManager
import com.revaks.longevity.ui.Ui
import java.util.concurrent.ExecutorService
import java.util.concurrent.Executors

/** Сообщение чата. */
private data class ChatItem(val isUser: Boolean, val text: String, val thinking: Boolean = false)

/**
 * Вкладка «Умный ассистент»: ответы по базе знаний (расписание, советы, отрывки
 * книг через BM25). Если установлена модель нейросети (LiteRT-LM, .litertlm) —
 * ответ собирается нейросетью по RAG-контексту из данных приложения, а при сбое
 * автоматически включается офлайн-движок.
 */
class AssistantFragment : Fragment() {

    private var _binding: FragmentAssistantBinding? = null
    private val binding get() = _binding!!

    private val app get() = requireActivity().application as LongevityApp
    private val messages = ArrayList<ChatItem>()
    private lateinit var adapter: ChatAdapter
    private var busy = false
    private val worker: ExecutorService = Executors.newSingleThreadExecutor()
    private val mainHandler = Handler(Looper.getMainLooper())

    override fun onCreateView(
        inflater: LayoutInflater, container: ViewGroup?, savedInstanceState: Bundle?,
    ): View {
        _binding = FragmentAssistantBinding.inflate(inflater, container, false)
        return binding.root
    }

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)
        val ready = app.state as? LongevityApp.State.Ready ?: return

        Ui.pageSubtitle(this, binding.tvPageSubtitle)
        adapter = ChatAdapter(requireContext())
        binding.rvChat.layoutManager = LinearLayoutManager(requireContext())
        binding.rvChat.adapter = adapter

        buildQuickChips(ready.content.quickQuestions)

        binding.tvModelStatus.text = if (ModelManager.modelPath(app) != null)
            "Нейросеть: ответы по вашим данным (RAG: советы, книги, MIND). План дня/расписание — офлайн."
        else
            "Нейросеть не установлена — офлайн-ответы по базе знаний."

        binding.btnSend.setOnClickListener { sendFromInput() }
        binding.etInput.setOnEditorActionListener { _, _, _ ->
            sendFromInput()
            true
        }

        if (messages.isEmpty()) {
            append(ChatItem(isUser = false, text = AssistantEngine.greet()))
        }
        render()
    }

    private fun buildQuickChips(questions: List<String>) {
        val ctx = requireContext()
        for (q in questions) {
            val chip = Chip(ctx).apply {
                text = q
                textSize = 12f
            }
            val lp = FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT,
            ).apply { marginEnd = Ui.dp(chip, 6) }
            chip.setOnClickListener { sendQuestion(q) }
            binding.llQuick.addView(chip, lp)
        }
    }

    // ------------------------------------------------------------------ отправка

    private fun sendFromInput(): Boolean {
        val text = binding.etInput.text?.toString()?.trim().orEmpty()
        if (text.isEmpty() || busy) return false
        binding.etInput.setText("")
        sendQuestion(text)
        return true
    }

    private fun sendQuestion(text: String) {
        val ready = app.state as? LongevityApp.State.Ready ?: return
        if (busy) return
        busy = true
        setInputEnabled(false)

        append(ChatItem(isUser = true, text = text))
        append(ChatItem(isUser = false, text = "Думаю...", thinking = true))
        render()
        val streamIndex = messages.size - 1

        worker.execute {
            val streamed = StringBuilder()
            var lastPost = 0L
            val answer = try {
                answerQuestion(ready, text) { piece ->
                    streamed.append(piece)
                    val now = System.currentTimeMillis()
                    if (now - lastPost > 150) {
                        lastPost = now
                        val current = streamed.toString()
                        mainHandler.post {
                            if (!isAdded || _binding == null) return@post
                            if (streamIndex in messages.indices) {
                                messages[streamIndex] = ChatItem(isUser = false, text = current)
                                render()
                            }
                        }
                    }
                }
            } catch (e: Exception) {
                "Не удалось подготовить ответ: ${e.message ?: e.javaClass.simpleName}"
            }
            mainHandler.post {
                if (!isAdded || _binding == null) return@post
                // Заменяем «Думаю...»/поток готовым ответом.
                if (streamIndex in messages.indices) {
                    messages[streamIndex] = ChatItem(isUser = false, text = answer)
                } else {
                    messages.add(ChatItem(isUser = false, text = answer))
                }
                busy = false
                setInputEnabled(true)
                render()
            }
        }
    }

    /**
     * Ответ на вопрос: при установленной нейросети — RAG-промпт с реальными
     * данными приложения (советы/книги/MIND через BM25), при сбое или без
     * модели — офлайн-движок. Вопросы про план/расписание всегда офлайн,
     * т.к. в RAG-контекст книг расписание не попадает.
     */
    private fun answerQuestion(
        ready: LongevityApp.State.Ready,
        query: String,
        onPiece: (String) -> Unit,
    ): String {
        if (AssistantEngine.wantsSchedule(query)) {
            return AssistantEngine.answer(ready.content, ready.index, ready.bookSearch, query)
        }
        val model = LlmSession.current() ?: LlmSession.load(app)
        if (model != null) {
            try {
                val prompt = GroundedPrompts.chatPrompt(
                    ready.content, ready.index, ready.bookSearch, query,
                )
                val text = model.generate(prompt, onPiece)
                if (text.isNotEmpty()) return text
            } catch (e: Exception) {
                // модель недоступна — отвечает офлайн-движок
            }
        }
        return AssistantEngine.answer(ready.content, ready.index, ready.bookSearch, query)
    }

    private fun setInputEnabled(enabled: Boolean) {
        binding.etInput.isEnabled = enabled
        binding.btnSend.isEnabled = enabled
        binding.btnSend.alpha = if (enabled) 1f else 0.4f
        for (i in 0 until binding.llQuick.childCount) {
            binding.llQuick.getChildAt(i).isEnabled = enabled
        }
    }

    private fun append(item: ChatItem) {
        messages.add(item)
        render()
    }

    private fun render() {
        adapter.submit(messages)
        if (messages.isNotEmpty()) {
            binding.rvChat.smoothScrollToPosition(messages.size - 1)
        }
    }

    override fun onDestroyView() {
        super.onDestroyView()
        worker.shutdown()
        _binding = null
    }
}

private class ChatAdapter(private val ctx: android.content.Context) :
    RecyclerView.Adapter<ChatAdapter.Holder>() {

    private val items = ArrayList<ChatItem>()

    fun submit(newItems: List<ChatItem>) {
        items.clear()
        items.addAll(newItems)
        notifyDataSetChanged()
    }

    class Holder(val binding: ItemChatBinding) : RecyclerView.ViewHolder(binding.root)

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): Holder {
        val binding = ItemChatBinding.inflate(LayoutInflater.from(parent.context), parent, false)
        return Holder(binding)
    }

    override fun getItemCount(): Int = items.size

    override fun onBindViewHolder(holder: Holder, position: Int) {
        val item = items[position]
        val b = holder.binding
        val density = ctx.resources.displayMetrics.density

        val params = b.card.layoutParams as FrameLayout.LayoutParams
        params.gravity = if (item.isUser) Gravity.END else Gravity.START
        b.card.layoutParams = params

        // Ограничиваем ширину пузыря шириной текста: текст переносится по
        // maxWidth, а карточка оборачивает его целиком.
        b.tvText.maxWidth = (ctx.resources.displayMetrics.widthPixels * 0.8f).toInt()

        b.tvWho.text = if (item.isUser) "Вы" else "Ассистент"

        val textColor: Int
        val whoColor: Int
        if (item.thinking) {
            b.card.setCardBackgroundColor(ContextCompat.getColor(ctx, R.color.header_default))
            textColor = Color.parseColor("#6B7280")
            whoColor = Color.parseColor("#6B7280")
            b.tvText.setTypeface(b.tvText.typeface, Typeface.ITALIC)
        } else if (item.isUser) {
            b.card.setCardBackgroundColor(ContextCompat.getColor(ctx, R.color.primary))
            textColor = Color.WHITE
            whoColor = Color.parseColor("#CCFFFFFF")
            b.tvText.setTypeface(b.tvText.typeface, Typeface.NORMAL)
        } else {
            b.card.setCardBackgroundColor(ContextCompat.getColor(ctx, R.color.card))
            textColor = Color.parseColor("#111827")
            whoColor = Color.parseColor("#0F766E")
            b.tvText.setTypeface(b.tvText.typeface, Typeface.NORMAL)
        }
        // Сбрасываем возможный «унаследованный» от предыдущего сообщения сток.
        b.card.strokeColor = if (item.isUser || item.thinking) Color.TRANSPARENT
        else Color.parseColor("#E2E8F0")
        b.card.strokeWidth = if (item.isUser || item.thinking) 0
        else (density * 1f).toInt()

        b.tvText.setTextColor(textColor)
        b.tvWho.setTextColor(whoColor)
        b.tvText.text = item.text
    }
}
