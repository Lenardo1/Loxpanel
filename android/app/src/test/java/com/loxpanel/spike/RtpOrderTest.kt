package com.loxpanel.spike

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class RtpOrderTest {
    @Test fun duplicateAndLatePacketsDoNotPlayAgain() {
        val order = RtpOrder()
        assertTrue(order.accept(10, 1))
        assertFalse(order.accept(10, 1))
        assertTrue(order.accept(12, 1))
        assertFalse(order.accept(11, 1))
        assertFalse(order.accept(12, 1))
        assertTrue(order.accept(13, 1))
    }

    @Test fun rolloverAndNewSourceRestart() {
        val order = RtpOrder()
        assertTrue(order.accept(65535, 1))
        assertTrue(order.accept(0, 1))
        assertFalse(order.accept(65535, 1))
        assertTrue(order.accept(300, 2))
        assertTrue(order.accept(301, 2))
    }
}
