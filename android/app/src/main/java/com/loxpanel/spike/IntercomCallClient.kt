package com.loxpanel.spike

import org.json.JSONObject
import java.io.IOException
import java.net.HttpURLConnection
import java.net.URL
import java.util.UUID

/** Nur der native Prozess kennt diesen kurzlebigen Zugang zum lokalen Server. */
object IntercomNative {
    val token: String = UUID.randomUUID().toString() + UUID.randomUUID().toString()
}

class IntercomCallClient : IntercomCalls {
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
        val con = URL(Visu.BASIS + "api/intercom/talk/" + path).openConnection() as HttpURLConnection
        try {
            con.connectTimeout = 3000
            con.readTimeout = 5000
            con.useCaches = false
            con.instanceFollowRedirects = false
            con.setRequestProperty("X-LoxPanel-Intercom", IntercomNative.token)
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
                throw IOException("Der lokale Gesprächsdienst antwortet nicht")
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
