package com.loxpanel.spike

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class PegelTest {
    @Test fun leiseWerteWerdenLinearVerstaerkt() {
        val s = shortArrayOf(1000, -1000, 0)
        Pegel.verstaerken(s, 2.0f)
        assertEquals(listOf<Short>(2000, -2000, 0), s.toList())
    }

    @Test fun lauteWerteBleibenImBereich() {
        val s = shortArrayOf(Short.MAX_VALUE, Short.MIN_VALUE, 20000, -20000)
        Pegel.verstaerken(s, 2.0f)
        s.forEach { assertTrue(it in -32767..32767) }
        assertTrue(s[2] > 24000 && s[0] >= s[2])
        assertTrue(s[3] < -24000 && s[1] <= s[3])
    }

    @Test fun faktorEinsAendertNichts() {
        val s = shortArrayOf(123, -456)
        Pegel.verstaerken(s, 1.0f)
        assertEquals(listOf<Short>(123, -456), s.toList())
    }
}
