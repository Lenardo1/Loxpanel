package com.loxpanel.spike

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/** Wann der Wächter die App neu startet und wann die Bremse das verhindert. */
class WaechterTest {

    private val abstand = Waechter.PRUEF_ABSTAND_MS

    /** Spielt Prüfungen im Abstand PRUEF_ABSTAND_MS ab dem Serverstart durch,
     *  wie der Server-Dienst. [gesund] sagt je Zeitpunkt (ms seit Start), ob
     *  der Server antwortet. Liefert den Zeitpunkt des ersten Neustarts, null
     *  wenn keiner nötig war. */
    private fun ersterNeustart(bisMs: Long, gesund: (Long) -> Boolean): Long? {
        val start = 1_000_000L
        val stand = Waechter.Stand(start)
        var t = abstand
        while (t <= bisMs) {
            if (stand.pruefung(gesund(t), start + t)) return t
            t += abstand
        }
        return null
    }

    @Test
    fun gesunderServerNie() {
        assertNull(ersterNeustart(24 * 3_600_000L) { true })
    }

    @Test
    fun langsamerStartInnerhalbDerAnlaufzeit() {
        val bereit = Waechter.ANLAUF_MS - abstand
        assertNull(ersterNeustart(24 * 3_600_000L) { it >= bereit })
    }

    @Test
    fun serverKommtNieHoch() {
        val t = ersterNeustart(3_600_000L) { false }!!
        assertTrue("nicht vor der Anlaufzeit: $t", t >= Waechter.ANLAUF_MS)
        assertTrue("gleich danach: $t", t < Waechter.ANLAUF_MS + abstand)
    }

    @Test
    fun ausfallImBetrieb() {
        val aus = 2 * 3_600_000L
        val t = ersterNeustart(24 * 3_600_000L) { it < aus }!!
        assertEquals(aus + (Waechter.FEHLER_BIS_NEUSTART - 1) * abstand, t)
    }

    @Test
    fun ausfallKurzNachDemStartWartetNichtAufDieAnlaufzeit() {
        val t = ersterNeustart(3_600_000L) { it == abstand }!!
        assertEquals((1 + Waechter.FEHLER_BIS_NEUSTART) * abstand, t)
        assertTrue(t < Waechter.ANLAUF_MS)
    }

    @Test
    fun einzelneAussetzerReichenNicht() {
        val luecken = Waechter.FEHLER_BIS_NEUSTART - 1
        // Jede Antwort setzt die Fehlschläge zurück, auch nach einer Lücke.
        assertNull(ersterNeustart(24 * 3_600_000L) { (it / abstand) % (luecken + 1) == 0L })
    }

    @Test
    fun standZaehltUndSetztZurueck() {
        val stand = Waechter.Stand(0)
        stand.pruefung(false, abstand)
        stand.pruefung(false, 2 * abstand)
        assertEquals(2, stand.fehler)
        assertFalse(stand.warGesund)
        stand.pruefung(true, 3 * abstand)
        assertEquals(0, stand.fehler)
        assertTrue(stand.warGesund)
    }

    @Test
    fun bremseNachHoechstensNeustarts() {
        val jetzt = 50 * 3_600_000L
        val neustarts = mutableListOf<Long>()
        repeat(Waechter.NEUSTARTS_HOECHSTENS) {
            assertTrue(Waechter.neustartErlaubt(neustarts, jetzt))
            neustarts += jetzt - 600_000L * (it + 1)
        }
        assertFalse(Waechter.neustartErlaubt(neustarts, jetzt))
        // Fällt der älteste aus dem Zeitraum, darf der nächste.
        val aeltester = neustarts.min()
        assertTrue(Waechter.neustartErlaubt(neustarts, aeltester + Waechter.BREMSE_MS))
        assertFalse(Waechter.neustartErlaubt(neustarts, aeltester + Waechter.BREMSE_MS - 1))
    }

    @Test
    fun bremseUeberEinenTagHoechstensDreiJeStunde() {
        // Ein Server, der nach jedem Neustart gleich wieder ausfällt: Die App
        // versucht es bei jeder fälligen Prüfung, die Bremse lässt je Stunde
        // nur NEUSTARTS_HOECHSTENS durch.
        val neustarts = mutableListOf<Long>()
        var t = 0L
        while (t < 24 * 3_600_000L) {
            if (Waechter.neustartErlaubt(neustarts, t)) neustarts += t
            t += abstand
        }
        for (ende in neustarts) {
            assertTrue(neustarts.count { it in (ende - Waechter.BREMSE_MS + 1)..ende } <= Waechter.NEUSTARTS_HOECHSTENS)
        }
        assertEquals(24 * Waechter.NEUSTARTS_HOECHSTENS, neustarts.size)
    }

    @Test
    fun alteUndKuenftigeNeustarteZaehlenNicht() {
        val jetzt = 10 * 3_600_000L
        val alt = jetzt - Waechter.BREMSE_MS
        val kuenftig = jetzt + 60_000L
        assertEquals(listOf(jetzt - 1, jetzt), Waechter.zaehlende(listOf(alt, kuenftig, jetzt - 1, jetzt), jetzt))
        assertTrue(Waechter.neustartErlaubt(List(10) { alt - it } + List(10) { kuenftig + it }, jetzt))
    }

    @Test
    fun neustarteAlsText() {
        val liste = listOf(1_759_400_000_000L, 1_759_400_600_000L)
        assertEquals(liste, Waechter.ausText(Waechter.alsText(liste)))
        assertEquals(emptyList<Long>(), Waechter.ausText(null))
        assertEquals(emptyList<Long>(), Waechter.ausText(""))
        assertEquals(listOf(5L, 7L), Waechter.ausText("5, x,, 7"))
    }

    @Test
    fun haengenderRendererErstNachMehrerenMeldungen() {
        assertFalse(Waechter.rendererBeenden(0))
        assertFalse(Waechter.rendererBeenden(Waechter.ANZEIGE_HAENGT_MELDUNGEN - 1))
        assertTrue(Waechter.rendererBeenden(Waechter.ANZEIGE_HAENGT_MELDUNGEN))
        assertFalse("einmal je Hänger", Waechter.rendererBeenden(Waechter.ANZEIGE_HAENGT_MELDUNGEN + 1))
        assertTrue("Android meldet frühestens alle 5 s: mindestens eine halbe Minute",
            Waechter.ANZEIGE_HAENGT_MELDUNGEN * 5 >= 30)
    }
}
