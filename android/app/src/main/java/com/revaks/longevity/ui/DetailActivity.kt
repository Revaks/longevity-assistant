package com.revaks.longevity.ui

import android.os.Bundle
import androidx.appcompat.app.AppCompatActivity
import com.revaks.longevity.databinding.ActivityDetailBinding

/**
 * Экран деталей совета или отрывка книги. Текст передаётся интентами,
 * слова запроса подсвечиваются.
 */
class DetailActivity : AppCompatActivity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val binding = ActivityDetailBinding.inflate(layoutInflater)
        setContentView(binding.root)

        binding.toolbar.setNavigationOnClickListener { finish() }
        binding.toolbar.title = intent.getStringExtra(EXTRA_TITLE).orEmpty()

        val caption = intent.getStringExtra(EXTRA_CAPTION).orEmpty()
        val body = intent.getStringExtra(EXTRA_BODY).orEmpty()
        val query = intent.getStringExtra(EXTRA_QUERY).orEmpty()

        binding.tvCaption.visibility =
            if (caption.isBlank()) android.view.View.GONE else android.view.View.VISIBLE
        binding.tvCaption.text = caption
        binding.tvBody.text = Ui.highlight(body, query)
    }

    companion object {
        const val EXTRA_TITLE = "title"
        const val EXTRA_CAPTION = "caption"
        const val EXTRA_BODY = "body"
        const val EXTRA_QUERY = "query"
    }
}
