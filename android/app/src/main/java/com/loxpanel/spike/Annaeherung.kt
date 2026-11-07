package com.loxpanel.spike

/**
 * Helligkeit nach Annaeherung (eigene Version, Marco): Kommt jemand nah an das
 * Display (Naeherungssensor) oder beruehrt es, ist es voll hell; nach
 * [haltenSek] ohne Annaeherung dimmt es in [blendeSek] weich auf [ruheProzent]
 * herunter. Ohne Android, damit sich die Rechnung auf dem PC pruefen laesst.
 */
class Annaeherung(var ruheProzent: Int = 100, var haltenSek: Int = 30, var blendeSek: Float = 2f) {
    private var letzteMs = Long.MIN_VALUE / 2

    val aktiv get() = ruheProzent in 0..99

    /** Annaeherung oder Beruehrung zur Zeit [jetztMs]. */
    fun nah(jetztMs: Long) { letzteMs = jetztMs }

    /** Anteil 0..1 der vollen Helligkeit zur Zeit [jetztMs]. */
    fun faktor(jetztMs: Long): Float {
        if (!aktiv) return 1f
        val ruhe = ruheProzent.coerceIn(0, 100) / 100f
        val seit = (jetztMs - letzteMs) / 1000f
        if (seit <= haltenSek) return 1f
        val blende = blendeSek.coerceAtLeast(0.01f)
        val t = ((seit - haltenSek) / blende).coerceIn(0f, 1f)
        return 1f - (1f - ruhe) * t
    }

    /** Millisekunden bis sich der Faktor das naechste Mal aendert, null = bleibt. */
    fun naechsteAenderungMs(jetztMs: Long): Long? {
        if (!aktiv) return null
        val ende = letzteMs + ((haltenSek + blendeSek) * 1000).toLong()
        if (jetztMs >= ende) return null
        val haltenEnde = letzteMs + haltenSek * 1000L
        return if (jetztMs < haltenEnde) haltenEnde - jetztMs else 50L
    }
}
