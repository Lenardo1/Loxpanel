package com.loxpanel.spike

import org.junit.Assert.assertEquals
import org.junit.Test

class WetterTextTest {
    @Test fun codes() {
        assertEquals("Klar", WetterText.art(0, true).second)
        assertEquals("🌙", WetterText.art(0, false).first)
        assertEquals("Regen", WetterText.art(63, true).second)
        assertEquals("Gewitter", WetterText.art(95, true).second)
        assertEquals("", WetterText.art(42, true).second)
    }
    @Test fun grad() {
        assertEquals("4,8°", WetterText.grad(4.84))
        assertEquals("-3,0°", WetterText.grad(-2.96))
        assertEquals("0,0°", WetterText.grad(-0.04))
        assertEquals("5°", WetterText.ganz(5.4))
        assertEquals("-3°", WetterText.ganz(-2.6))
    }
}
