package com.revaks.longevity

import android.app.Application
import android.content.Context
import android.os.Handler
import android.os.Looper
import com.revaks.longevity.core.BookSearch
import com.revaks.longevity.core.Content
import com.revaks.longevity.core.ContentLoader
import com.revaks.longevity.core.JsonFiles
import com.revaks.longevity.core.SearchIndex
import com.revaks.longevity.data.Storage
import java.util.concurrent.Executors

/**
 * Приложение-контейнер: загружает данные (JSON из assets), строит индексы
 * поиска и открывает хранилище. Тяжёлая работа (книги — 2,5 МБ) выполняется
 * в фоне, чтобы стартовое окно не висело.
 */
class LongevityApp : Application() {

    sealed class State {
        object Loading : State()
        data class Ready(
            val content: Content,
            val index: SearchIndex,
            val bookSearch: BookSearch,
        ) : State()

        data class Failed(val reason: String) : State()
    }

    @Volatile
    var state: State = State.Loading
        private set

    @Volatile
    private var storage: Storage? = null

    private val executor = Executors.newSingleThreadExecutor()
    private val mainHandler = Handler(Looper.getMainLooper())
    private val listeners = ArrayList<() -> Unit>()

    override fun onCreate() {
        super.onCreate()
        startLoad()
    }

    /** Хранилище создаётся лениво на вызывающем потоке. */
    fun storage(): Storage = synchronized(this) {
        storage ?: Storage(this).also { storage = it }
    }

    fun addListener(listener: () -> Unit) {
        synchronized(listeners) { listeners.add(listener) }
        if (state is State.Ready || state is State.Failed) {
            // Контент уже готов — сообщаем сразу, но в главном потоке.
            mainHandler.post(listener)
        }
    }

    fun removeListener(listener: () -> Unit) {
        synchronized(listeners) { listeners.remove(listener) }
    }

    fun startLoad() {
        state = State.Loading
        notifyListeners()
        executor.execute {
            val next = try {
                val content = loadContent()
                State.Ready(
                    content = content,
                    index = SearchIndex(content),
                    bookSearch = BookSearch(content),
                )
            } catch (e: Exception) {
                State.Failed(e.message ?: e.javaClass.simpleName)
            }
            state = next
            mainHandler.post { notifyListeners() }
        }
    }

    private fun loadContent(): Content {
        val ctx: Context = this
        fun read(name: String): String =
            ctx.assets.open("longevity/$name").bufferedReader(Charsets.UTF_8).use { it.readText() }

        return ContentLoader.buildContent(
            JsonFiles(
                tips = read("tips.json"),
                schedule = read("schedule.json"),
                synonyms = read("synonyms.json"),
                mind = read("mind.json"),
                meta = read("meta.json"),
                books = read("books.json"),
                extras = read("extras.json"),
            )
        )
    }

    private fun notifyListeners() {
        val copy = synchronized(listeners) { listeners.toList() }
        copy.forEach { it() }
    }
}
