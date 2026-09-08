package com.revaks.longevity.ui.knowledge

import android.content.Intent
import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.AdapterView
import android.widget.ArrayAdapter
import android.widget.EditText
import androidx.fragment.app.Fragment
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.RecyclerView
import com.revaks.longevity.LongevityApp
import com.revaks.longevity.R
import com.revaks.longevity.core.BookSearch
import com.revaks.longevity.core.Content
import com.revaks.longevity.core.Passage
import com.revaks.longevity.core.Tip
import com.revaks.longevity.databinding.FragmentKnowledgeBinding
import com.revaks.longevity.databinding.ItemBookBinding
import com.revaks.longevity.databinding.ItemTipBinding
import com.revaks.longevity.ui.DetailActivity
import com.revaks.longevity.ui.Ui

/** Число отрывков в выдаче поиска по книгам (как BOOKS_PAGE_LIMIT в десктопе). */
private const val BOOKS_PAGE_LIMIT = 50

/**
 * Вкладка «База знаний»: советы (поиск по категориям) и отрывки книг
 * (поиск BM25). «Смысловой поиск» через Ollama на Android не переносится.
 */
class KnowledgeFragment : Fragment() {

    private var _binding: FragmentKnowledgeBinding? = null
    private val binding get() = _binding!!

    private val app get() = requireActivity().application as LongevityApp
    private var bookSearch: BookSearch? = null
    private var tipsAdapter: TipsAdapter? = null
    private var booksAdapter: BooksAdapter? = null

    override fun onCreateView(
        inflater: LayoutInflater, container: ViewGroup?, savedInstanceState: Bundle?,
    ): View {
        _binding = FragmentKnowledgeBinding.inflate(inflater, container, false)
        return binding.root
    }

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)
        val ready = app.state as? LongevityApp.State.Ready ?: return
        val content = ready.content
        bookSearch = ready.bookSearch

        Ui.pageSubtitle(this, binding.tvPageSubtitle)

        // Советы
        tipsAdapter = TipsAdapter(content) { tip -> openTip(content, tip) }
        binding.rvTips.layoutManager = LinearLayoutManager(requireContext())
        binding.rvTips.adapter = tipsAdapter

        val options = listOf("Все категории") + content.categories
        binding.spinnerCat.adapter = ArrayAdapter(
            requireContext(), android.R.layout.simple_spinner_dropdown_item, options,
        )
        binding.spinnerCat.onItemSelectedListener = object : AdapterView.OnItemSelectedListener {
            override fun onItemSelected(parent: AdapterView<*>?, view: View?, position: Int, id: Long) {
                refreshTips()
            }

            override fun onNothingSelected(parent: AdapterView<*>?) = Unit
        }
        binding.etTipsSearch.addTextChangedListener(debounce { refreshTips() })
        binding.btnTipsReset.setOnClickListener {
            binding.etTipsSearch.setText("")
            binding.spinnerCat.setSelection(0)
            refreshTips()
        }

        // Книги
        booksAdapter = BooksAdapter(content) { passage -> openPassage(content, passage) }
        binding.rvBooks.layoutManager = LinearLayoutManager(requireContext())
        binding.rvBooks.adapter = booksAdapter
        binding.etBooksSearch.addTextChangedListener(debounce { refreshBooks() })
        binding.btnBooksReset.setOnClickListener {
            binding.etBooksSearch.setText("")
            refreshBooks()
        }

        binding.toggleGroup.check(R.id.chip_tips)
        binding.toggleGroup.addOnButtonCheckedListener { _, checkedId, isChecked ->
            if (!isChecked) return@addOnButtonCheckedListener
            val showBooks = checkedId == R.id.chip_books
            binding.panelTips.visibility = if (showBooks) View.GONE else View.VISIBLE
            binding.panelBooks.visibility = if (showBooks) View.VISIBLE else View.GONE
        }

        refreshTips()
        refreshBooks()
    }

    // ------------------------------------------------------------------ данные

    private fun refreshTips() {
        val ready = app.state as? LongevityApp.State.Ready ?: return
        val content = ready.content
        val query = binding.etTipsSearch.text?.toString()?.trim().orEmpty()
        val selectedCat = binding.spinnerCat.selectedItem as? String
            ?: "Все категории"

        val all: List<Tip> = if (query.isNotEmpty()) {
            ready.index.search(query).map { it.tip }
        } else {
            content.tips
        }
        val filtered = if (selectedCat == "Все категории") all
        else all.filter { it.cat == selectedCat }
        tipsAdapter?.submit(filtered)
        binding.tvTipsCount.text = "Найдено: ${filtered.size}"
    }

    private fun refreshBooks() {
        val ready = app.state as? LongevityApp.State.Ready ?: return
        val content = ready.content
        val query = binding.etBooksSearch.text?.toString()?.trim().orEmpty()
        if (query.isEmpty()) {
            booksAdapter?.submit(content.passages)
            binding.tvBooksCount.text = "Отрывков: ${content.passages.size}"
            return
        }
        val hits = bookSearch?.search(query, BOOKS_PAGE_LIMIT).orEmpty()
        booksAdapter?.submit(hits.map { it.passage })
        binding.tvBooksCount.text = "Найдено: ${hits.size} (BM25)"
    }

    // ------------------------------------------------------------------ детали

    private fun openTip(content: Content, tip: Tip) {
        val caption = buildString {
            append("[${tip.cat}]\n")
            append("Когда / как часто: ${tip.sched}\n")
            append("Источник: ${tip.source}")
        }
        startDetail(content.appTitle, tip.title, caption, tip.text, binding.etTipsSearch.text.toString())
    }

    private fun openPassage(content: Content, passage: Passage) {
        val book = content.books.firstOrNull { it.id == passage.book }
        val title = if (book != null) "«${book.title}»" else passage.book
        val caption = if (passage.section.isNotEmpty())
            "$title, раздел «${passage.section}»" else title
        startDetail(content.appTitle, "Отрывок из книги", caption, passage.text,
            binding.etBooksSearch.text.toString())
    }

    private fun startDetail(pageTitle: String, title: String, caption: String, body: String, query: String) {
        val intent = Intent(requireContext(), DetailActivity::class.java).apply {
            putExtra(DetailActivity.EXTRA_TITLE, title)
            putExtra(DetailActivity.EXTRA_CAPTION, caption)
            putExtra(DetailActivity.EXTRA_BODY, body)
            putExtra(DetailActivity.EXTRA_QUERY, query)
        }
        startActivity(intent)
    }

    // ------------------------------------------------------------------ хелперы

    private fun debounce(action: () -> Unit): android.text.TextWatcher =
        object : android.text.TextWatcher {
            private var runnable: Runnable? = null
            override fun beforeTextChanged(s: CharSequence?, a: Int, b: Int, c: Int) = Unit
            override fun onTextChanged(s: CharSequence?, a: Int, b: Int, c: Int) = Unit
            override fun afterTextChanged(s: android.text.Editable?) {
                runnable?.let { binding.root.removeCallbacks(it) }
                val r = Runnable { action() }
                runnable = r
                binding.root.postDelayed(r, 200)
            }
        }

    override fun onDestroyView() {
        super.onDestroyView()
        _binding = null
    }
}

/** Список советов. */
private class TipsAdapter(
    private val content: Content,
    private val onClick: (Tip) -> Unit,
) : RecyclerView.Adapter<TipsAdapter.Holder>() {

    private val items = ArrayList<Tip>()

    fun submit(newItems: List<Tip>) {
        items.clear()
        items.addAll(newItems)
        notifyDataSetChanged()
    }

    class Holder(val binding: ItemTipBinding) : RecyclerView.ViewHolder(binding.root)

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): Holder {
        val binding = ItemTipBinding.inflate(LayoutInflater.from(parent.context), parent, false)
        return Holder(binding)
    }

    override fun getItemCount(): Int = items.size

    override fun onBindViewHolder(holder: Holder, position: Int) {
        val tip = items[position]
        holder.binding.tvCat.text = tip.cat
        holder.binding.tvCat.setTextColor(content.catColor(tip.cat))
        holder.binding.tvTitle.text = tip.title
        holder.binding.tvSched.text = tip.sched
        holder.binding.root.setOnClickListener { onClick(tip) }
    }
}

/** Список отрывков книг. */
private class BooksAdapter(
    private val content: Content,
    private val onClick: (Passage) -> Unit,
) : RecyclerView.Adapter<BooksAdapter.Holder>() {

    private val items = ArrayList<Passage>()

    fun submit(newItems: List<Passage>) {
        items.clear()
        items.addAll(newItems)
        notifyDataSetChanged()
    }

    class Holder(val binding: ItemBookBinding) : RecyclerView.ViewHolder(binding.root)

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): Holder {
        val binding = ItemBookBinding.inflate(LayoutInflater.from(parent.context), parent, false)
        return Holder(binding)
    }

    override fun getItemCount(): Int = items.size

    override fun onBindViewHolder(holder: Holder, position: Int) {
        val passage = items[position]
        val book = content.books.firstOrNull { it.id == passage.book }
        holder.binding.tvBook.text = book?.title ?: passage.book
        holder.binding.tvSection.text = passage.section.ifEmpty { "—" }
        holder.binding.tvText.text = passage.text.take(220)
        holder.binding.root.setOnClickListener { onClick(passage) }
    }
}
