package com.revaks.longevity.core

import kotlin.math.ln

/**
 * Поисковый движок приложения: BM25F по советам и по книгам —
 * перенос longevity/search.py.
 *
 * Единственный класс [BM25F] делает статистику и скоринг для любого набора
 * документов; [SearchIndex] индексирует советы (title/tags/text/cat),
 * [BookSearch] — отрывки книг (section/book/text, где «book» — название книги).
 */

object SearchWeights {
    const val K1 = 1.2
    const val B = 0.75
    const val SYNONYM_WEIGHT = 0.4
    const val DEFAULT_LIMIT = Int.MAX_VALUE // «без ограничения»

    val FIELD_WEIGHTS: Map<String, Double> = mapOf(
        "title" to 3.0, "tags" to 2.0, "text" to 1.0, "cat" to 0.5,
    )
    val BOOK_FIELD_WEIGHTS: Map<String, Double> = mapOf(
        "section" to 3.0, "book" to 2.0, "text" to 1.0,
    )
}

class TipHit(val tip: Tip, val score: Double)

class BookHit(val passage: Passage, val score: Double)

private class FieldIndex(val counters: Map<String, MutableMap<String, Int>>,
                         val lengths: Map<String, Int>)

/** Общая механика BM25F над списком документов. */
class BM25F<T>(
    docs: List<T>,
    weights: Map<String, Double>,
    fieldText: (field: String, doc: T) -> String,
    synonyms: Map<String, String>,
) {
    private val docs: List<T> = docs
    private val weights: Map<String, Double> = weights
    private val syn: Map<String, List<String>> =
        synonyms.mapValues { (_, value) -> Text.analyze(value) }

    private val fields: List<FieldIndex>
    private val n: Int
    private val avgLen: Map<String, Double>
    private val df: MutableMap<String, Int> = HashMap()

    init {
        val built = ArrayList<FieldIndex>(docs.size)
        for (doc in docs) {
            val counters = HashMap<String, MutableMap<String, Int>>()
            val lengths = HashMap<String, Int>()
            for (field in weights.keys) {
                val terms = Text.analyze(fieldText(field, doc))
                val counter = HashMap<String, Int>()
                for (t in terms) counter[t] = (counter[t] ?: 0) + 1
                counters[field] = counter
                lengths[field] = terms.size
            }
            built.add(FieldIndex(counters, lengths))
        }
        fields = built
        n = docs.size
        val sums = HashMap<String, Double>()
        for (f in weights.keys) {
            var sum = 0.0
            for (fi in built) sum += fi.lengths[f] ?: 0
            val avg = if (n > 0) sum / n else 1.0
            // как в Python: нулевая средняя длина приравнивается к 1.0
            sums[f] = if (avg == 0.0) 1.0 else avg
        }
        avgLen = sums
        for (fi in built) {
            val seen = HashSet<String>()
            for (counter in fi.counters.values) seen.addAll(counter.keys)
            for (term in seen) df[term] = (df[term] ?: 0) + 1
        }
    }

    /** Основы запроса с весами: прямые слова тяжелее синонимов. */
    private fun weightedTerms(query: String): Map<String, Double> {
        val terms = LinkedHashMap<String, Double>()
        for (term in Text.analyze(query)) terms[term] = 1.0
        // Словарь синонимов ключуется словами до стемминга — нужен сырой tokenize.
        for (word in Text.tokenize(query).toSet()) {
            for (term in syn[word] ?: emptyList()) {
                if (!terms.containsKey(term)) terms[term] = SearchWeights.SYNONYM_WEIGHT
            }
        }
        return terms
    }

    private fun idf(term: String): Double {
        val dfT = df[term] ?: 0
        return ln((n - dfT + 0.5) / (dfT + 0.5) + 1.0)
    }

    private fun tf(index: Int, term: String): Double {
        val fi = fields[index]
        var total = 0.0
        for ((field, weight) in weights) {
            val count = fi.counters[field]?.get(term) ?: 0
            if (count == 0) continue
            val len = fi.lengths[field] ?: 0
            val norm = 1 - SearchWeights.B + SearchWeights.B * (len / avgLen[field]!!)
            total += weight * count / norm
        }
        return total
    }

    /**
     * Пары (документ, оценка), отсортированные по (-score, id).
     * limit <= 0 означает «ничего не показывать»; DEFAULT_LIMIT — без ограничения.
     */
    fun search(query: String, limit: Int = SearchWeights.DEFAULT_LIMIT): List<Pair<T, Double>> {
        val terms = weightedTerms(query)
        if (terms.isEmpty()) return emptyList()
        val hits = ArrayList<Pair<T, Double>>()
        for (i in docs.indices) {
            var score = 0.0
            for ((term, termWeight) in terms) {
                val tfValue = tf(i, term)
                if (tfValue == 0.0) continue
                score += termWeight * idf(term) * (tfValue * (SearchWeights.K1 + 1)) /
                    (tfValue + SearchWeights.K1)
            }
            if (score > 0) hits.add(Pair(docs[i], score))
        }
        val sorted = hits.sortedWith { a, b ->
            val byScore = b.second.compareTo(a.second)
            if (byScore != 0) byScore
            else {
                val idA = idOf(a.first)
                val idB = idOf(b.first)
                idA.compareTo(idB)
            }
        }
        return if (limit < 0 || limit == Int.MAX_VALUE) sorted else sorted.take(limit)
    }

    private fun idOf(doc: T): String = when (doc) {
        is Tip -> doc.id
        is Passage -> doc.id
        is ScheduleItem -> doc.id
        else -> doc.toString()
    }
}

/** Индекс советов: четыре поля (title/tags/text/cat). */
class SearchIndex(content: Content) {
    private val engine = BM25F(
        docs = content.tips,
        weights = SearchWeights.FIELD_WEIGHTS,
        fieldText = { field, tip ->
            when (field) {
                "title" -> tip.title
                "tags" -> tip.tags
                "cat" -> tip.cat
                else -> tip.text
            }
        },
        synonyms = content.synonyms,
    )

    fun search(query: String, limit: Int = SearchWeights.DEFAULT_LIMIT): List<TipHit> =
        engine.search(query, limit).map { TipHit(it.first as Tip, it.second) }
}

/** Индекс отрывков книг. Название книги подмешивается в «book»-поле. */
class BookSearch(content: Content) {
    private val titles = content.books.associate {
        it.id to "${it.title} ${it.subtitle}".trim()
    }

    private val engine = BM25F(
        docs = content.passages,
        weights = SearchWeights.BOOK_FIELD_WEIGHTS,
        fieldText = { field, passage ->
            when (field) {
                "book" -> titles[passage.book] ?: passage.book
                "section" -> passage.section
                else -> passage.text
            }
        },
        synonyms = content.synonyms,
    )

    fun search(query: String, limit: Int = SearchWeights.DEFAULT_LIMIT): List<BookHit> =
        engine.search(query, limit).map { BookHit(it.first as Passage, it.second) }
}
