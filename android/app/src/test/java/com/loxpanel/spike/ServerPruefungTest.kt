package com.loxpanel.spike

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/** Woran die Einrichtung einen LoxPanel-Server erkennt: /api/health mit
 *  "version", 200 gesund, 503 mit beendeter Hintergrund-Aufgabe. */
class ServerPruefungTest {

    private val health = """{"ok": true, "tasks": {"stream_task": true}, "miniserver": true,
        "panels": 2, "uptime": 120, "version": "0.9.1"}"""

    @Test
    fun gesunderServer() {
        assertEquals(ServerPruefung.Ergebnis.Gefunden("0.9.1", true), ServerPruefung.auswerten(200, health))
    }

    /** 503 heißt: LoxPanel läuft, aber eine Aufgabe ist beendet. Für die
     *  Einrichtung ist das ein Server, nur kein gesunder. */
    @Test
    fun gestoerterServerIstTrotzdemLoxPanel() {
        val erg = ServerPruefung.auswerten(503, health.replace("\"ok\": true", "\"ok\": false"))
        assertEquals(ServerPruefung.Ergebnis.Gefunden("0.9.1", false), erg)
    }

    @Test
    fun fremderWebserver() {
        val erg = ServerPruefung.auswerten(404, "<html>Not Found</html>")
        assertTrue(erg is ServerPruefung.Ergebnis.KeinServer)
        assertTrue((erg as ServerPruefung.Ergebnis.KeinServer).grund.contains("404"))
    }

    @Test
    fun antwortOhneVersionOderKeinJson() {
        assertTrue(ServerPruefung.auswerten(200, "<html>ok</html>") is ServerPruefung.Ergebnis.KeinServer)
        assertTrue(ServerPruefung.auswerten(200, """{"ok": true}""") is ServerPruefung.Ergebnis.KeinServer)
        assertTrue(ServerPruefung.auswerten(200, "") is ServerPruefung.Ergebnis.KeinServer)
    }
}
