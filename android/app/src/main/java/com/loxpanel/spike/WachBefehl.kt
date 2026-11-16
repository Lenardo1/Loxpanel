package com.loxpanel.spike

/** Weck-Anfragen an den Weckdienst (WachDienst), ohne Android: testbar. */
object WachBefehl {
    /** Was eine HTTP-Anfrage verlangt: true = wecken, false = schlafen, null = nichts.
     *  WallPanel-Format POST /api/command {"wake": true|false}, dazu GET /wecken. */
    fun befehl(anfrage: String): Boolean? {
        val zeile = anfrage.lineSequence().firstOrNull()?.trim() ?: return null
        val teile = zeile.split(" ")
        if (teile.size < 2) return null
        val pfad = teile[1].substringBefore("?")
        if (pfad == "/wecken") return true
        if (pfad != "/api/command") return null
        val koerper = anfrage.substringAfter("\r\n\r\n", anfrage.substringAfter("\n\n", ""))
        val m = Regex("\"wake\"\\s*:\\s*(true|false)").find(koerper) ?: return null
        return m.groupValues[1] == "true"
    }
}
