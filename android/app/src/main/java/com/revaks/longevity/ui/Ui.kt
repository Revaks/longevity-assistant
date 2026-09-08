package com.revaks.longevity.ui

import android.graphics.Color
import android.text.Spannable
import android.text.SpannableString
import android.text.style.BackgroundColorSpan
import android.view.View
import android.widget.TextView
import androidx.fragment.app.Fragment
import com.revaks.longevity.LongevityApp
import java.time.OffsetDateTime
import java.time.ZoneId
import java.time.format.DateTimeFormatter

/** Общие помощники страниц. */
object Ui {

    /** «12:34» из ISO-времени создания записи (UTC -> локальное время). */
    fun localTime(iso: String): String = try {
        val parsed = OffsetDateTime.parse(iso)
        parsed.atZoneSameInstant(ZoneId.systemDefault())
            .format(DateTimeFormatter.ofPattern("HH:mm"))
    } catch (e: Exception) {
        if (iso.length >= 16) iso.substring(11, 16) else iso
    }

    /** Подсветить вхождения слов запроса (длиной 3+ символа), как в десктопе. */
    fun highlight(text: String, query: String, hlColor: Int = 0xFFFDE68A.toInt()): CharSequence {
        if (query.isBlank()) return text
        val tokens = Regex("[\\p{L}\\p{N}]{3,}").findAll(query).map { it.value }.toList()
        if (tokens.isEmpty()) return text

        val sp = SpannableString(text)
        val lower = text.lowercase()
        for (token in tokens) {
            val needle = token.lowercase()
            var start = 0
            while (true) {
                val pos = lower.indexOf(needle, start)
                if (pos < 0) break
                sp.setSpan(BackgroundColorSpan(hlColor), pos, pos + needle.length,
                    Spannable.SPAN_EXCLUSIVE_EXCLUSIVE)
                start = pos + needle.length
            }
        }
        return sp
    }

    fun pageSubtitle(fragment: Fragment, tv: TextView) {
        val app = fragment.requireActivity().application as LongevityApp
        val content = (app.state as? LongevityApp.State.Ready)?.content
        tv.text = content?.appSubtitle.orEmpty()
    }

    fun dp(view: View, value: Int): Int =
        (value * view.resources.displayMetrics.density).toInt()

    val SELECTED_HEADER_TEXT = Color.parseColor("#134E4A")
}
