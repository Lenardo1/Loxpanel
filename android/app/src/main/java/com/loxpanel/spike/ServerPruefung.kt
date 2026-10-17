package com.loxpanel.spike

import java.io.IOException
import java.net.HttpURLConnection
import java.net.URL

/**
 * Prüft, ob unter einer Adresse ein LoxPanel-Server antwortet: /api/health
 * liefert JSON mit "version", 200 wenn alle Hintergrund-Aufgaben laufen, 503
 * wenn eine beendet ist. Beides ist ein LoxPanel-Server; alles andere nicht.
 * Die Auswertung der Antwort steht ohne Android (auch ohne org.json, das in
 * JVM-Tests nur ein Stummel ist), damit sie sich auf dem PC prüfen lässt.
 */
object ServerPruefung {

    sealed class Ergebnis {
        /** Ein LoxPanel-Server mit dieser Version; [gesund] = /api/health 200. */
        data class Gefunden(val version: String, val gesund: Boolean) : Ergebnis()

        /** Kein LoxPanel-Server, [grund] in Worten für die Einrichtung. */
        data class KeinServer(val grund: String) : Ergebnis()
    }

    /** Wertet Statuscode und Antwort von /api/health aus. */
    fun auswerten(code: Int, body: String): Ergebnis {
        if (code != HttpURLConnection.HTTP_OK && code != HttpURLConnection.HTTP_UNAVAILABLE) {
            return Ergebnis.KeinServer("antwortet mit Status $code statt mit /api/health")
        }
        // /api/health ist ein flaches JSON-Objekt; "version" ist dort eine
        // Zeichenkette. Mehr Lesen braucht die Prüfung nicht.
        if (!body.trimStart().startsWith("{")) return Ergebnis.KeinServer("antwortet, aber nicht wie LoxPanel")
        val version = VERSION.find(body)?.groupValues?.get(1)?.replace("\\\"", "\"")?.takeIf { it.isNotEmpty() }
            ?: return Ergebnis.KeinServer("antwortet, aber nicht wie LoxPanel")
        return Ergebnis.Gefunden(version, code == HttpURLConnection.HTTP_OK)
    }

    private val VERSION = Regex(""""version"\s*:\s*"((?:[^"\\]|\\.)*)"""")

    /** Fragt /api/health der Basis-Adresse (mit "/" am Ende) ab, blockierend. */
    fun pruefen(basis: String): Ergebnis {
        val con = try {
            URL(basis + "api/health").openConnection() as HttpURLConnection
        } catch (e: IOException) {
            return Ergebnis.KeinServer("Adresse nicht lesbar ($e)")
        }
        return try {
            con.connectTimeout = Waechter.VERBINDEN_MS
            con.readTimeout = Waechter.ANTWORT_MS
            con.useCaches = false
            val code = con.responseCode
            val strom = if (code >= HttpURLConnection.HTTP_BAD_REQUEST) con.errorStream else con.inputStream
            val body = strom?.bufferedReader()?.use { it.readText() } ?: ""
            auswerten(code, body)
        } catch (e: IOException) {
            Ergebnis.KeinServer(e.localizedMessage ?: e.javaClass.simpleName)
        } finally {
            con.disconnect()
        }
    }
}
