package com.loxpanel.spike

import org.junit.Assert.*
import org.junit.Test
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicReference

/** Rennen zwischen Start, Auflegen und einer spaeten Serverantwort. */
class IntercomSessionTest {
    private class FakeCalls : IntercomCalls {
        val entered = CountDownLatch(1)
        val answer = CountDownLatch(1)
        val stopped = mutableListOf<IntercomSession.Ticket>()
        override fun start(ticket: IntercomSession.Ticket, port: Int): IntercomReply {
            entered.countDown()
            check(answer.await(2, TimeUnit.SECONDS))
            return IntercomReply("connected", media = IntercomMedia("192.0.2.1", port, "PCMA", 8))
        }
        override fun status(ticket: IntercomSession.Ticket) = IntercomReply("connected")
        override fun stop(ticket: IntercomSession.Ticket) { synchronized(stopped) { stopped.add(ticket) } }
    }

    @Test fun connectingExistsBeforeHttpAndOnlyOneCallStarts() {
        val session = IntercomSession()
        val ticket = session.begin("door")!!
        assertEquals(IntercomSession.Status("connecting", "door"), session.status())
        assertTrue(session.wanted(ticket))
        assertNull(session.begin("other"))
        assertEquals(ticket, session.ending())
        assertEquals("ending", session.status().state)
        assertFalse(session.wanted(ticket))
        assertNull(session.ending())
    }

    @Test fun stoppingBeforeHttpNeverCreatesACall() {
        val session = IntercomSession()
        val calls = FakeCalls()
        val ticket = session.begin("door")!!
        session.ending()
        assertNull(session.connect(ticket, 6000, calls))
        assertEquals(1L, calls.entered.count)
    }

    @Test fun lateStartIsHungUpAndCannotChangeNewCall() {
        val session = IntercomSession()
        val calls = FakeCalls()
        val old = session.begin("door")!!
        val result = AtomicReference<IntercomReply?>()
        val worker = Thread { result.set(session.connect(old, 6000, calls)) }
        worker.start()
        assertTrue(calls.entered.await(2, TimeUnit.SECONDS))
        session.ending()
        calls.stop(old)
        session.finished(old)
        val fresh = session.begin("other")!!
        calls.answer.countDown()
        worker.join(2000)
        assertFalse(worker.isAlive)
        assertNull(result.get())
        assertEquals(listOf(old, old), calls.stopped)
        assertFalse(session.accept(old, "connected"))
        session.finished(old)
        assertEquals(fresh, session.current())
        assertEquals(IntercomSession.Status("connecting", "other"), session.status())
    }

    @Test fun errorKeepsExplanationAndAllowsRetry() {
        val session = IntercomSession()
        val ticket = session.begin("door")!!
        assertTrue(session.accept(ticket, "error", "Mikrofon fehlt"))
        assertEquals(IntercomSession.Status("error", "door", "Mikrofon fehlt"), session.status())
        assertNotNull(session.begin("door"))
    }
}
