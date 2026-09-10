package com.revaks.longevity.core

import org.junit.Assert.assertEquals
import org.junit.Test

/** Форматирование измерений биодневника. */
class MeasuresTest {

    @Test
    fun `format adds unit and trims zeros`() {
        assertEquals("72.5 кг", Measures.format("weight", 72.5))
        assertEquals("80 кг", Measures.format("weight", 80.0))
        assertEquals("120 мм рт.ст.", Measures.format("bp_sys", 120.0))
        assertEquals("72", Measures.format("unknown_kind", 72.0))
    }

    @Test
    fun `delta shows sign and unit`() {
        assertEquals("+0.4 кг", Measures.delta("weight", 72.9, 72.5))
        assertEquals("−1.2 кг", Measures.delta("weight", 71.3, 72.5))
        assertEquals("0.0 кг", Measures.delta("weight", 72.5, 72.5))
    }
}
