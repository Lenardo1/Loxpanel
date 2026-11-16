package com.loxpanel.spike

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class WachBefehlTest {
    @Test
    fun wallpanelWecken() {
        val a = "POST /api/command HTTP/1.1\r\nHost: x\r\nContent-Type: application/json\r\n\r\n{\"wake\": true}"
        assertEquals(true, WachBefehl.befehl(a))
    }

    @Test
    fun wallpanelSchlafen() {
        assertEquals(false, WachBefehl.befehl("POST /api/command HTTP/1.1\r\n\r\n{\"wake\":false}"))
    }

    @Test
    fun einfachesWecken() {
        assertEquals(true, WachBefehl.befehl("GET /wecken?x=1 HTTP/1.1\r\n\r\n"))
    }

    @Test
    fun anderesNichts() {
        assertNull(WachBefehl.befehl("GET / HTTP/1.1\r\n\r\n"))
        assertNull(WachBefehl.befehl("POST /api/command HTTP/1.1\r\n\r\n{}"))
        assertNull(WachBefehl.befehl(""))
    }
}
