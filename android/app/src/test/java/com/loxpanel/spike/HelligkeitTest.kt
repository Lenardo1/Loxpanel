package com.loxpanel.spike

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/** Welche Fensterhelligkeit die Anzeige im Nachtmodus der Visu setzt. */
class HelligkeitTest {

    @Test
    fun teilDerSystemhelligkeit() {
        assertEquals(0.4f, Helligkeit.fensterwert(50, 0.8f)!!, 1e-6f)
        assertEquals(0.08f, Helligkeit.fensterwert(10, 0.8f)!!, 1e-6f)
        assertEquals(0.01f, Helligkeit.fensterwert(1, 1f)!!, 1e-6f)
    }

    @Test
    fun nieHellerAlsDieSystemhelligkeit() {
        for (prozent in 0..99) {
            for (system in listOf(0f, 0.05f, 0.5f, 1f)) {
                val wert = Helligkeit.fensterwert(prozent, system)!!
                assertTrue("$prozent % von $system ergab $wert", wert in 0f..system)
            }
        }
        assertEquals(0f, Helligkeit.fensterwert(-5, 0.5f)!!, 0f)
    }

    @Test
    fun hundertProzentIstDieSystemhelligkeit() {
        assertEquals(Helligkeit.SYSTEM, Helligkeit.fensterwert(100, 0.5f))
        assertEquals(Helligkeit.SYSTEM, Helligkeit.fensterwert(250, 0.5f))
        assertEquals("auch bei automatischer Helligkeit", Helligkeit.SYSTEM, Helligkeit.fensterwert(100, null))
    }

    @Test
    fun automatischeHelligkeitLehntAb() {
        assertNull(Helligkeit.fensterwert(50, null))
        assertNull(Helligkeit.fensterwert(1, null))
    }

    @Test
    fun anteilDerEinstellung() {
        assertEquals(1f, Helligkeit.anteil(255, 255), 0f)
        assertEquals(0.5f, Helligkeit.anteil(1024, 2048), 1e-6f)
        assertEquals("Hersteller-Bereich ohne bekannten Höchstwert", 1f, Helligkeit.anteil(2047, 0), 0f)
        assertEquals(0f, Helligkeit.anteil(-3, 255), 0f)
    }
}
