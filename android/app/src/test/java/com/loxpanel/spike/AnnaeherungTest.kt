package com.loxpanel.spike

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class AnnaeherungTest {
    @Test fun ausHeisstImmerVoll() {
        val a = Annaeherung(ruheProzent = 100)
        assertEquals(1f, a.faktor(1_000_000), 0f)
        assertNull(a.naechsteAenderungMs(0))
    }

    @Test fun vollHaltenDannWeichAufRuhe() {
        val a = Annaeherung(ruheProzent = 30, haltenSek = 30, blendeSek = 2f)
        a.nah(0)
        assertEquals(1f, a.faktor(30_000), 0f)
        assertEquals(0.65f, a.faktor(31_000), 0.001f)      // halb geblendet
        assertEquals(0.3f, a.faktor(32_000), 0.001f)
        assertEquals(0.3f, a.faktor(600_000), 0.001f)
        a.nah(600_000)
        assertEquals(1f, a.faktor(600_001), 0f)
    }

    @Test fun ohneAnnaeherungSofortRuhe() {
        assertEquals(0.4f, Annaeherung(ruheProzent = 40).faktor(0), 0.001f)
    }

    @Test fun naechsteAenderung() {
        val a = Annaeherung(ruheProzent = 30, haltenSek = 30, blendeSek = 2f)
        a.nah(0)
        assertEquals(20_000L, a.naechsteAenderungMs(10_000))
        assertEquals(50L, a.naechsteAenderungMs(31_000))
        assertNull(a.naechsteAenderungMs(40_000))
    }
}
