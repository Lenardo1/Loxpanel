package com.loxpanel.spike

import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class IntercomCapabilityTest {
    @Test fun framesWithoutPageAccessAreRejected() {
        val gate = IntercomCapability()
        assertFalse(gate.accepts(null))
        assertFalse(gate.accepts(""))
        val topDocument = gate.rotate()
        assertTrue(gate.accepts(topDocument))
        assertFalse(gate.accepts(null))
        assertFalse(gate.accepts("undefined"))
        assertFalse(gate.accepts("foreign-frame"))
    }

    @Test fun reloadingInvalidatesPreviousDocument() {
        val gate = IntercomCapability()
        val previous = gate.rotate()
        val current = gate.rotate()
        assertNotEquals(previous, current)
        assertFalse(gate.accepts(previous))
        assertTrue(gate.accepts(current))
        gate.clear()
        assertFalse(gate.accepts(current))
    }
}
