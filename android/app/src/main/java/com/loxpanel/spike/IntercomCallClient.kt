package com.loxpanel.spike

import android.content.Context
import org.json.JSONObject
import java.io.IOException
import java.net.HttpURLConnection
import java.net.URL
import java.security.SecureRandom
import java.util.UUID

/** Nur der native Prozess kennt diesen kurzlebigen Zugang zum lokalen Server. */
object IntercomNative {
    val token: String = UUID.randomUUID().toString() + UUID.randomUUID().toString()
}

/**
 * Geräteschlüssel für Gegensprechen über einen Server im Netz: einmal zufällig
 * erzeugt, bleibt bis zur Neuinstallation. Der Server speichert nur seinen
 * Hash und lässt das Display erst sprechen, wenn es im Konfigurator
 * (Einstellungen → SIP → Displays im Netz) freigegeben ist.
 */
object IntercomGeraet {
    const val KOPF = "X-LoxPanel-Intercom-Geraet"
    private const val PREFS = "intercom"
    private const val SCHLUESSEL = "geraeteschluessel"

    @Synchronized
    fun schluessel(ctx: Context): String {
        val p = ctx.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        p.getString(SCHLUESSEL, null)?.let { return it }
        val bytes = ByteArray(32).also { SecureRandom().nextBytes(it) }
        val neu = bytes.joinToString("") { "%02x".format(it) }
        p.edit().putString(SCHLUESSEL, neu).apply()
        return neu
    }
}

/** Gespräche über den eingestellten Server: den eigenen auf dem Gerät
 *  (Prozess-Token) oder einen im Netz (Geräteschlüssel). */
class IntercomCallClient(private val ctx: Context) : IntercomCalls {
    override fun start(ticket: IntercomSession.Ticket, port: Int): IntercomReply = reply(request(
        "start", JSONObject().put("session", ticket.session).put("uuid", ticket.uuid).put("rtpPort", port)))

    override fun status(ticket: IntercomSession.Ticket): IntercomReply =
        reply(request("status?session=${ticket.session}"))

    override fun stop(ticket: IntercomSession.Ticket) {
        request("stop", JSONObject().put("session", ticket.session))
    }

    private fun reply(json: JSONObject): IntercomReply {
        val state = json.optString("state", "error")
        if (state !in listOf("idle", "connecting", "connected", "ending", "error")) {
            throw IOException("Ungültiger Gesprächsstatus")
        }
        val media = json.optJSONObject("media")?.let {
            val host = it.optString("remoteHost")
            val port = it.optInt("remotePort")
            val codec = it.optString("codec").uppercase()
            val payload = it.optInt("payloadType", -1)
            if (host.isBlank() || port !in 1..65535 || codec !in listOf("PCMA", "PCMU") ||
                payload !in 0..127 || it.optInt("sampleRate") != 8000 || it.optInt("ptime") != 20) {
                throw IOException("Die Türstation nennt kein unterstütztes Audioformat")
            }
            IntercomMedia(host, port, codec, payload)
        }
        if (state == "connected" && media == null) throw IOException("Die Audioadresse der Türstation fehlt")
        return IntercomReply(state, json.optString("message"), media)
    }

    private fun request(path: String, body: JSONObject? = null): JSONObject {
        // Eigener Server: Prozess-Token, nur er kennt es. Server im Netz:
        // Geräteschlüssel, der Server prüft die Freigabe und schickt den Ton
        // der Türstation an dieses Gerät.
        val eigener = Visu.eigenerServer(ctx)
        val con = URL(Visu.basis(ctx) + "api/intercom/talk/" + path).openConnection() as HttpURLConnection
        try {
            con.connectTimeout = 3000
            con.readTimeout = 5000
            con.useCaches = false
            con.instanceFollowRedirects = false
            if (eigener) con.setRequestProperty("X-LoxPanel-Intercom", IntercomNative.token)
            else con.setRequestProperty(IntercomGeraet.KOPF, IntercomGeraet.schluessel(ctx))
            if (body != null) {
                con.requestMethod = "POST"
                con.doOutput = true
                con.setRequestProperty("Content-Type", "application/json; charset=utf-8")
                con.outputStream.use { it.write(body.toString().toByteArray(Charsets.UTF_8)) }
            }
            val code = con.responseCode
            val input = if (code in 200..299) con.inputStream else con.errorStream
            val text = input?.bufferedReader(Charsets.UTF_8)?.use { it.readText() } ?: ""
            val json = try { JSONObject(text) } catch (e: Exception) {
                throw IOException(if (eigener) "Der lokale Gesprächsdienst antwortet nicht"
                    else "Der Server im Netz kennt kein Gegensprechen für Displays (LoxPanel aktualisieren)")
            }
            if (code !in 200..299 || !json.optBoolean("ok")) {
                throw IOException(json.optString("message").ifBlank {
                    json.optString("error").ifBlank { "Der lokale Gesprächsdienst ist nicht verfügbar" }
                })
            }
            return json
        } finally {
            con.disconnect()
        }
    }
}
