package com.loxpanel.spike

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/** Welche Adressen sich die Kiosk-Anzeige als Start-Adresse merkt und was das
 *  Server-Feld der Einrichtung annimmt. */
class VisuTest {

    private val eigener = Visu.EIGENER
    private val netz = Visu.basisFuer("192.168.1.10:8099")

    @Test
    fun visuMitUndOhneProfil() {
        assertTrue(Visu.istVisu(eigener, eigener))
        assertTrue(Visu.istVisu(eigener, eigener + "?panel=wohnen"))
        assertTrue(Visu.istVisu(eigener, eigener + "?panel=wohnen&device=k%C3%BCche"))
        assertTrue(Visu.istVisu(eigener, eigener + "#oben"))
    }

    @Test
    fun andereSeitenDesServersNicht() {
        assertFalse(Visu.istVisu(eigener, eigener + "config"))
        assertFalse(Visu.istVisu(eigener, eigener + "settings?x=1"))
        assertFalse(Visu.istVisu(eigener, eigener + "api/meta"))
    }

    @Test
    fun fremdeAdressenNicht() {
        assertFalse(Visu.istVisu(eigener, "http://10.0.0.5:${Visu.PORT}/?panel=wohnen"))
        assertFalse(Visu.istVisu(eigener, "http://127.0.0.1:${Visu.PORT + 1}/"))
        assertFalse(Visu.istVisu(eigener, "http://127.0.0.1:${Visu.PORT}0/"))
        assertFalse(Visu.istVisu(eigener, "about:blank"))
        assertFalse(Visu.istVisu(eigener, ""))
    }

    @Test
    fun kaputteAdresseNicht() {
        assertFalse(Visu.istVisu(eigener, eigener + "?panel=a b"))
    }

    /** Mit einem Server im Netz gilt dessen Visu, nicht mehr die des eigenen
     *  Servers: Eine gemerkte Adresse des alten Servers zählt nicht. */
    @Test
    fun serverImNetzHatSeineEigeneVisu() {
        assertEquals("http://192.168.1.10:8099/", netz)
        assertTrue(Visu.istVisu(netz, netz))
        assertTrue(Visu.istVisu(netz, netz + "?panel=flur"))
        assertFalse(Visu.istVisu(netz, netz + "config"))
        assertFalse(Visu.istVisu(netz, eigener + "?panel=flur"))
        assertFalse(Visu.istVisu(eigener, netz))
    }

    @Test
    fun serverFeldNimmtHostMitUndOhnePort() {
        assertEquals("192.168.1.10:8099", Visu.serverEingabe("192.168.1.10:8099"))
        assertEquals("192.168.1.10:${Visu.PORT}", Visu.serverEingabe("192.168.1.10"))
        assertEquals("192.168.1.10:8100", Visu.serverEingabe("  192.168.1.10:8100 "))
        assertEquals("loxberry:${Visu.PORT}", Visu.serverEingabe("LoxBerry"))
        assertEquals("loxpanel.fritz.box:8099", Visu.serverEingabe("loxpanel.fritz.box:8099"))
        assertEquals("[fd00::10]:8099", Visu.serverEingabe("[fd00::10]:8099"))
    }

    /** Die Zeile aus „Gerät verbinden“ im Konfigurator darf man samt http://
     *  und Schrägstrich einfügen. */
    @Test
    fun serverFeldNimmtDieZeileAusDemKonfigurator() {
        assertEquals("192.168.1.10:8099", Visu.serverEingabe("http://192.168.1.10:8099/"))
        assertEquals("192.168.1.10:8099", Visu.serverEingabe("http://192.168.1.10:8099"))
        assertEquals("192.168.1.10:${Visu.PORT}", Visu.serverEingabe("http://192.168.1.10/"))
    }

    @Test
    fun serverFeldLehntAbWasKeinServerIst() {
        assertNull(Visu.serverEingabe(""))
        assertNull(Visu.serverEingabe("   "))
        assertNull(Visu.serverEingabe("192.168.1.10:8099/config"))
        assertNull(Visu.serverEingabe("http://192.168.1.10:8099/?panel=flur"))
        assertNull(Visu.serverEingabe("https://192.168.1.10:8099/"))
        assertNull(Visu.serverEingabe("ftp://192.168.1.10/"))
        assertNull(Visu.serverEingabe("admin:geheim@192.168.1.10"))
        assertNull(Visu.serverEingabe("192.168.1.10:abc"))
        assertNull(Visu.serverEingabe("a b"))
    }
}
