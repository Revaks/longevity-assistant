package com.revaks.longevity.core

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class ContentLoaderTest {

    @Test
    fun `builds content from valid fixture`() {
        val c = Fixtures.content()
        assertEquals("Ассистент долголетия", c.appTitle)
        assertEquals(1, c.tips.size)
        assertEquals("t1", c.tips[0].id)
        assertEquals(1, c.schedule.size)
        assertEquals(listOf(0, 2, 4), c.schedule[0].days)
        assertEquals("Есть рыбу дважды в неделю", c.tip("t1").title)
        assertEquals(1, c.books.size)
        assertEquals("Книга", c.book("b1").title)
        assertEquals(1, c.passages.size)
        assertEquals("Глава 1", c.passage("p1").section)
        assertNull(c.tip("t1").ageMin)
        assertEquals(0xFFE65100.toInt(), c.catColor("Питание"))
    }

    @Test(expected = ContentError::class)
    fun `rejects unknown tip category`() {
        Fixtures.content(
            tipsJson = Fixtures.tipsJson(Fixtures.tip(cat = "Нет такой")),
        )
    }

    @Test(expected = ContentError::class)
    fun `rejects duplicate tip ids`() {
        Fixtures.content(
            tipsJson = Fixtures.tipsJson(Fixtures.tip(), Fixtures.tip()),
        )
    }

    @Test(expected = ContentError::class)
    fun `rejects clock item without time`() {
        Fixtures.content(
            scheduleJson = Fixtures.scheduleJson(
                Fixtures.scheduleItem(anchor = "clock", time = null),
            ),
        )
    }

    @Test(expected = ContentError::class)
    fun `rejects time on non-clock item`() {
        Fixtures.content(
            scheduleJson = Fixtures.scheduleJson(
                Fixtures.scheduleItem(anchor = "morning", time = "07:00"),
            ),
        )
    }

    @Test(expected = ContentError::class)
    fun `rejects schedule link to missing tip`() {
        Fixtures.content(
            scheduleJson = Fixtures.scheduleJson(
                Fixtures.scheduleItem(tips = listOf("нет-такого")),
            ),
        )
    }

    @Test(expected = ContentError::class)
    fun `rejects passage link to missing book`() {
        val books = Fixtures.booksJson(
            passages = Fixtures.obj(
                "id" to "p9", "book" to "нет-книги",
                "section" to "Глава", "text" to "Какой-то текст",
            ),
        )
        Fixtures.content(booksJson = books)
    }

    @Test(expected = ContentError::class)
    fun `rejects duplicate passage id`() {
        val books = Fixtures.obj(
            "version" to 1,
            "books" to Fixtures.arr(
                Fixtures.obj("id" to "b1", "title" to "Книга", "subtitle" to "", "author" to "А"),
            ),
            "passages" to Fixtures.arr(
                Fixtures.obj("id" to "p1", "book" to "b1", "section" to "1", "text" to "Текст 1"),
                Fixtures.obj("id" to "p1", "book" to "b1", "section" to "2", "text" to "Текст 2"),
            ),
        )
        Fixtures.content(booksJson = books)
    }

    @Test
    fun `validates requires has alt alternative`() {
        // requires без alt отклоняется, с alt — проходит.
        try {
            val bad = Fixtures.obj(
                "id" to "x", "title" to "Т", "detail" to "", "cat" to "Питание",
                "days" to Fixtures.arr(0), "anchor" to "allday", "time" to null,
                "tips" to Fixtures.arr(), "requires" to Fixtures.jobj("user.diet" to "veg"),
            )
            Fixtures.content(scheduleJson = Fixtures.scheduleJson(bad))
            throw AssertionError("ожидался ContentError")
        } catch (expected: ContentError) {
            assertTrue(
                "Сообщение без «alt»: ${expected.message}",
                expected.message.orEmpty().contains("alt"),
            )
        }

        val ok = Fixtures.obj(
            "id" to "y", "title" to "Т", "detail" to "", "cat" to "Питание",
            "days" to Fixtures.arr(0), "anchor" to "allday", "time" to null,
            "tips" to Fixtures.arr(),
            "requires" to Fixtures.jobj("user.diet" to "veg"),
            "alt" to Fixtures.jobj("veg" to "Альтернатива"),
        )
        Fixtures.content(scheduleJson = Fixtures.scheduleJson(ok))
    }

    @Test
    fun `broken json reports file name`() {
        try {
            Fixtures.content(tipsJson = "{битый json")
            throw AssertionError("ожидался ContentError")
        } catch (e: ContentError) {
            assertTrue(e.message.orEmpty().contains("tips.json"))
        }
    }
}
