package com.loxpanel.spike

import java.util.UUID

/** Zustand einer nativen Sitzung; ohne Android fuer die Abbruchtests. */
class IntercomSession {
    data class Ticket(val session: String, val uuid: String)
    data class Status(val state: String, val uuid: String = "", val message: String = "")

    private var ticket: Ticket? = null
    private var stand = Status("idle")

    @Synchronized fun status(): Status = stand

    /** Die Sitzung existiert bereits vor Berechtigungsdialog und HTTP-Anfrage. */
    @Synchronized fun begin(uuid: String): Ticket? {
        if (uuid.isBlank() || stand.state !in listOf("idle", "error")) return null
        val neu = Ticket(UUID.randomUUID().toString(), uuid)
        ticket = neu
        stand = Status("connecting", uuid)
        return neu
    }

    @Synchronized fun wanted(t: Ticket): Boolean =
        ticket == t && stand.state in listOf("connecting", "connected")

    @Synchronized fun current(): Ticket? = ticket

    @Synchronized fun ending(): Ticket? {
        val t = ticket ?: return null
        if (stand.state == "ending") return null
        stand = Status("ending", t.uuid)
        return t
    }

    @Synchronized fun accept(t: Ticket, state: String, message: String = ""): Boolean {
        if (!wanted(t)) return false
        stand = Status(state, t.uuid, message)
        if (state in listOf("idle", "error")) ticket = null
        return true
    }

    @Synchronized fun finished(t: Ticket) {
        if (ticket == t) {
            ticket = null
            stand = Status("idle")
        }
    }

    /** Ein spaet beantworteter Start darf eine aufgelegte Sitzung nie wecken. */
    fun connect(t: Ticket, port: Int, client: IntercomCalls): IntercomReply? {
        if (!wanted(t)) return null
        val reply = client.start(t, port)
        if (!wanted(t)) {
            client.stop(t)
            return null
        }
        return reply
    }
}

data class IntercomMedia(val remoteHost: String, val remotePort: Int,
                        val codec: String, val payloadType: Int)
data class IntercomReply(val state: String, val message: String = "", val media: IntercomMedia? = null)

interface IntercomCalls {
    fun start(ticket: IntercomSession.Ticket, port: Int): IntercomReply
    fun status(ticket: IntercomSession.Ticket): IntercomReply
    fun stop(ticket: IntercomSession.Ticket)
}
