package com.revaks.longevity.core

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class TextTest {

    @Test
    fun `normalize lowercases and replaces yo`() {
        assertEquals("елка тест2", Text.normalize("Ёлка!  Тест2"))
        assertEquals("тест драйв 123", Text.normalize("Тест-Драйв, 123"))
    }

    @Test
    fun `stem unifies word forms`() {
        // Ожидания сверены с Python-оригиналом (longevity/text.py).
        assertEquals("активност", Text.stem("активность"))
        assertEquals("активност", Text.stem("активности"))
        assertEquals("памят", Text.stem("память"))
        assertEquals("памят", Text.stem("памяти"))
        assertEquals("бег", Text.stem("бегом"))
        assertEquals("бег", Text.stem("бега"))
    }

    @Test
    fun `fleeting vowel family maps to same stem`() {
        for (form in listOf("сон", "сна", "сну", "сном", "сне")) {
            assertEquals("сон", Text.stem(form))
        }
    }

    @Test
    fun `analyze drops stopwords and stems`() {
        assertEquals(listOf("спат"), Text.analyze("как спать"))
        assertEquals(listOf("план", "сегодн"), Text.analyze("План на сегодня"))
        assertEquals(listOf("расписан"), Text.analyze("расписание"))
        assertEquals(listOf("анализ"), Text.analyze("какие анализы сдавать?"))
        assertEquals(listOf("ест"), Text.analyze("есть"))
        assertEquals(listOf("рыб"), Text.analyze("рыба")) // -а отсекается, длина 3+1 > 3
    }

    @Test
    fun `analyze handles normalize plus tokenize edge cases`() {
        // Короткие токены остаются без изменений: основа короче 3 не отсекается.
        assertEquals("сн", Text.stem("сн"))
        assertEquals("ия", Text.stem("ия"))
        // Дефис и пунктуация — разделители, а «сна» из словаря даёт «сон».
        assertEquals(listOf("а", "б"), Text.tokenize("а-б"))
        assertEquals(listOf("сон"), Text.analyze("сон сна сну сном сне").distinct())
    }

    @Test
    fun `normalize handles unicode letters and digits`() {
        assertTrue(Text.normalize("аБвГд12").isNotBlank())
        assertFalse(Text.STOPWORDS.isEmpty())
        assertTrue(Text.STOPWORDS.contains("и"))
        assertTrue(Text.STOPWORDS.contains("го"))
    }
}
