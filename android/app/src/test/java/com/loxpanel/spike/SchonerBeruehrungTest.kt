package com.loxpanel.spike

import com.loxpanel.spike.SchonerBeruehrung.Tun
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/** Berührung im Schoner: ein Finger weckt, zwei Finger gehen als Geste an die Visu. */
class SchonerBeruehrungTest {

    private val w = SchonerBeruehrung.WARTE_MS

    @Test
    fun einFingerWecktNachDerWartezeit() {
        val b = SchonerBeruehrung()
        assertEquals(Tun.HALTEN, b.runter(1000))
        assertTrue(b.laeuft)
        assertEquals(Tun.SCHLUCKEN, b.weiter())
        assertEquals(Tun.WECKEN, b.frist())
        // der Rest derselben Berührung geht nicht an die Kachel darunter
        assertEquals(Tun.SCHLUCKEN, b.weiter())
        assertEquals(Tun.SCHLUCKEN, b.weitererFinger(1000 + 2 * w))
        assertEquals(Tun.SCHLUCKEN, b.hoch())
        assertFalse(b.laeuft)
    }

    @Test
    fun kurzerTippWecktSofort() {
        val b = SchonerBeruehrung()
        b.runter(1000)
        assertEquals(Tun.WECKEN, b.hoch())
        assertEquals("die Frist danach weckt nicht noch einmal", Tun.SCHLUCKEN, b.frist())
    }

    @Test
    fun zweiFingerSindEineGeste() {
        val b = SchonerBeruehrung()
        b.runter(1000)
        assertEquals(Tun.NACHREICHEN, b.weitererFinger(1000 + w))
        assertEquals("die Frist weckt nicht mehr", Tun.SCHLUCKEN, b.frist())
        assertEquals(Tun.DURCHREICHEN, b.weiter())
        assertEquals(Tun.DURCHREICHEN, b.weitererFinger(1000 + 5 * w))
        assertEquals(Tun.DURCHREICHEN, b.hoch())
        assertFalse(b.laeuft)
        // die nächste Berührung beginnt von vorn
        assertEquals(Tun.HALTEN, b.runter(5000))
    }

    @Test
    fun zweiterFingerZuSpaetWeckt() {
        val b = SchonerBeruehrung()
        b.runter(1000)
        assertEquals(Tun.WECKEN, b.weitererFinger(1000 + w + 1))
        assertEquals(Tun.SCHLUCKEN, b.weiter())
        assertEquals(Tun.SCHLUCKEN, b.hoch())
    }

    @Test
    fun abbruchWecktNie() {
        val warten = SchonerBeruehrung()
        warten.runter(1000)
        assertEquals(Tun.SCHLUCKEN, warten.abbruch())
        assertFalse(warten.laeuft)
        val geste = SchonerBeruehrung()
        geste.runter(1000)
        geste.weitererFinger(1010)
        assertEquals("die Visu erfährt das Ende der Geste", Tun.DURCHREICHEN, geste.abbruch())
    }

    @Test
    fun wartezeitIstEinstellbar() {
        val b = SchonerBeruehrung(warteMs = 50)
        b.runter(0)
        assertEquals(Tun.WECKEN, b.weitererFinger(51))
    }
}
