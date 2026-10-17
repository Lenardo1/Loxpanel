package com.loxpanel.spike

import android.Manifest
import android.app.Activity
import android.content.pm.PackageManager
import android.os.Handler
import android.util.Log
import org.json.JSONObject
import java.net.DatagramSocket
import java.util.concurrent.Executors
import java.util.concurrent.RejectedExecutionException
import java.util.concurrent.TimeUnit

/** Die Anzeige besitzt Mikrofon und RTP; Python uebernimmt ausschliesslich SIP. */
class IntercomAudio(private val activity: Activity, private val ui: Handler) {
    companion object { const val MICROPHONE_REQUEST = 1701 }

    private val session = IntercomSession()
    private val calls = IntercomCallClient()
    private val jobs = Executors.newScheduledThreadPool(2) { r ->
        Thread(r, "loxpanel-intercom").apply { isDaemon = true }
    }
    private val mediaLock = Any()
    private var socketTicket: IntercomSession.Ticket? = null
    private var socket: DatagramSocket? = null
    private var audio: IntercomRtpDevice? = null
    private var permissionTicket: IntercomSession.Ticket? = null
    @Volatile private var awaitingPermission = false
    @Volatile private var resumed = false
    @Volatile private var closed = false

    fun status(): String {
        val s = session.status()
        return JSONObject().put("state", s.state).put("uuid", s.uuid).put("message", s.message).toString()
    }

    /** Auch im JS-Thread sofort sichtbar, bevor der UI-Thread den Dialog zeigt. */
    @Synchronized fun start(uuid: String, allowed: () -> Boolean = { true }): Boolean {
        if (closed || !resumed || !allowed()) return false
        val ticket = session.begin(uuid) ?: return false
        ui.post {
            if (!session.wanted(ticket)) return@post
            if (closed || !resumed || !allowed()) { stop(); return@post }
            if (activity.checkSelfPermission(Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED) {
                prepare(ticket)
            } else {
                permissionTicket = ticket
                awaitingPermission = true
                activity.requestPermissions(arrayOf(Manifest.permission.RECORD_AUDIO), MICROPHONE_REQUEST)
            }
        }
        return true
    }

    /** Auflegen sperrt zuerst den Zustand; ein spaeter HTTP-Start wird abgeraeumt. */
    fun stop(): Boolean {
        val ticket = session.ending() ?: return true
        ui.post { if (permissionTicket == ticket) permissionTicket = null }
        closeMedia(ticket)
        runJob { endServer(ticket) }
        return true
    }

    fun onResume() {
        if (closed) return
        resumed = true
        val ticket = permissionTicket
        if (!awaitingPermission && ticket != null && session.wanted(ticket)) {
            permissionTicket = null
            prepare(ticket)
        }
    }

    fun onPause() {
        resumed = false
        // Der eigene Berechtigungsdialog pausiert die Activity ebenfalls.
        if (!awaitingPermission) stop()
    }

    fun onStop() { resumed = false; stop() }

    fun permissionResult(granted: Boolean) {
        awaitingPermission = false
        val ticket = permissionTicket ?: return
        if (!session.wanted(ticket)) { permissionTicket = null; return }
        if (!granted) {
            permissionTicket = null
            failed(ticket, "Mikrofonzugriff nicht erlaubt. In den Android-Einstellungen freigeben.")
        } else if (resumed) {
            permissionTicket = null
            prepare(ticket)
        }
    }

    @Synchronized fun destroy() {
        if (closed) return
        closed = true
        resumed = false
        stop()
        // Bereits gestartete HTTP-Anfragen duerfen ihre spaeten Sitzungen noch auflegen.
        jobs.shutdown()
    }

    private fun prepare(ticket: IntercomSession.Ticket) {
        runJob {
            try {
                val port = synchronized(mediaLock) {
                    if (!session.wanted(ticket)) return@runJob
                    val bound = DatagramSocket(0)
                    socket = bound
                    socketTicket = ticket
                    bound.localPort
                }
                val reply = session.connect(ticket, port, calls) ?: return@runJob
                apply(ticket, reply)
                if (session.wanted(ticket)) poll(ticket)
            } catch (e: Exception) {
                failed(ticket, e.message ?: "Das Gespräch konnte nicht gestartet werden")
            }
        }
    }

    /** Jede Abfrage verlaengert zugleich die serverseitige Lebensfrist. */
    private fun poll(ticket: IntercomSession.Ticket) {
        if (closed || !session.wanted(ticket)) return
        try {
            jobs.schedule({
                if (!session.wanted(ticket)) return@schedule
                try {
                    apply(ticket, calls.status(ticket))
                    poll(ticket)
                } catch (e: Exception) {
                    failed(ticket, e.message ?: "Die Verbindung zur Türstation ist abgebrochen")
                }
            }, 500, TimeUnit.MILLISECONDS)
        } catch (_: RejectedExecutionException) { /* Activity bereits beendet */ }
    }

    private fun apply(ticket: IntercomSession.Ticket, reply: IntercomReply) {
        if (!session.wanted(ticket)) return
        if (reply.state == "connected") {
            synchronized(mediaLock) {
                if (!session.wanted(ticket)) return
                if (audio == null) {
                    val bound = socket?.takeIf { socketTicket == ticket }
                        ?: throw IllegalStateException("Der Audioport ist geschlossen")
                    audio = IntercomRtpDevice(activity, ui, bound, requireNotNull(reply.media)) {
                        message -> runJob { failed(ticket, message) }
                    }.also { it.start() }
                }
            }
        } else if (reply.state in listOf("idle", "error", "ending")) {
            closeMedia(ticket)
        }
        session.accept(ticket, reply.state, reply.message)
        if (reply.state == "ending") {
            // Der Server legt bereits auf; das native Ticket endet ebenfalls.
            runJob { endServer(ticket) }
        }
    }

    private fun failed(ticket: IntercomSession.Ticket, message: String) {
        closeMedia(ticket)
        if (session.accept(ticket, "error", message)) {
            Log.w("LPINTERCOM", "Gespräch beendet: $message")
            runJob { try { calls.stop(ticket) } catch (_: Exception) { /* Lebensfrist greift */ } }
        }
    }

    private fun closeMedia(ticket: IntercomSession.Ticket) {
        synchronized(mediaLock) {
            if (socketTicket != ticket) return
            audio?.close()
            audio = null
            socket?.close()
            socket = null
            socketTicket = null
        }
    }

    private fun endServer(ticket: IntercomSession.Ticket) {
        try {
            calls.stop(ticket)
            waitForEnd(ticket)
        } catch (_: Exception) {
            Log.w("LPINTERCOM", "Auflegen: lokaler Gesprächsdienst nicht erreichbar")
            session.finished(ticket)
        }
    }

    private fun waitForEnd(ticket: IntercomSession.Ticket) {
        if (closed) { session.finished(ticket); return }
        if (session.current() != ticket || session.status().state != "ending") return
        // Die Stop-Antwort bestaetigt nur den Auftrag. Erst nach SIP-CANCEL/BYE
        // wieder freigeben, sonst waere der naechste Start am Server noch belegt.
        try {
            jobs.schedule({
                if (closed) { session.finished(ticket); return@schedule }
                if (session.current() != ticket) return@schedule
                try {
                    val reply = calls.status(ticket)
                    if (reply.state in listOf("idle", "error")) session.finished(ticket)
                    else waitForEnd(ticket)
                } catch (_: Exception) { session.finished(ticket) }
            }, 500, TimeUnit.MILLISECONDS)
        } catch (_: RejectedExecutionException) { session.finished(ticket) }
    }

    private fun runJob(action: () -> Unit) {
        // Bereits laufende Startanfragen beenden sich selbst (connect legt spaet auf).
        // Rueckrufe von Audio/UI nach destroy duerfen keine neue Arbeit starten.
        try { jobs.execute(action) } catch (_: RejectedExecutionException) { /* geschlossen */ }
    }
}
