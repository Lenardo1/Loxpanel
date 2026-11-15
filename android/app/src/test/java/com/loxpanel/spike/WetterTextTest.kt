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
    @Test fun weather4lox() {
        assertEquals("⛅", WetterText.symbolW4l("partly-cloudy-day"))
        assertEquals("🌧️", WetterText.symbolW4l("cloudy_shower_1"))
        assertEquals("☁️", WetterText.symbolW4l("overcast"))
        assertEquals("🌙", WetterText.symbolW4l("clear-night"))
        assertEquals("🌡️", WetterText.symbolW4l(null))
    }
    @Test fun loxone() {
        assertEquals("weather-00-d.svg", WetterText.loxoneSymbol(1, false))
        assertEquals("weather-03-n.svg", WetterText.loxoneSymbol(4, true))
        assertEquals("weather-04.svg", WetterText.loxoneSymbol(5, true))
        assertEquals("weather-10.svg", WetterText.loxoneSymbol(WetterText.zahl("11"), false))
        assertEquals(null, WetterText.loxoneSymbol(0, false))
        assertEquals(null, WetterText.loxoneSymbol(null, false))
    }
    @Test fun nacht() {
        val c = java.util.Calendar.getInstance()
        c.set(java.util.Calendar.HOUR_OF_DAY, 6); c.set(java.util.Calendar.MINUTE, 0)
        assertEquals(true, WetterText.istNacht("07:29", "16:33", c))
        c.set(java.util.Calendar.HOUR_OF_DAY, 12)
        assertEquals(false, WetterText.istNacht("07:29", "16:33", c))
        c.set(java.util.Calendar.HOUR_OF_DAY, 17)
        assertEquals(true, WetterText.istNacht("07:29", "16:33", c))
        assertEquals(false, WetterText.istNacht(null, "16:33", c))
    }
    @Test fun tage() {
        assertEquals("Heute", WetterText.tagName(0, 0))
        assertEquals("Morgen", WetterText.tagName(1, 0))
        assertEquals("Di 17.11.", WetterText.tagName(2, 1794873600L))   // 2026-11-17 01:00 MEZ
        assertEquals("7° / -2°", WetterText.maxMin(org.json.JSONObject("{\"temperature\":{\"max\":{\"air\":7},\"min\":{\"air\":-2}}}")))
    }
    @Test fun menue() {
        assertEquals(true, WetterText.istMenue("Automatik Designer"))
        assertEquals(true, WetterText.istMenue(" INTERN VERBUNDEN "))
        assertEquals(false, WetterText.istMenue("Miniserver OG"))
    }
}
