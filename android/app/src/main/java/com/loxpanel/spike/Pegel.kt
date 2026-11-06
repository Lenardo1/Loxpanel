package com.loxpanel.spike

/**
 * Verstaerkung beim Gegensprechen (eigene Version): das Shelly-X2i-Display und
 * die Tuerstation waren beide zu leise, auch mit voller Gespraechslautstaerke.
 * Werte ueber 1 heben den Pegel an; was ueber den 16-Bit-Bereich ginge, wird
 * weich begrenzt statt hart abgeschnitten (klingt weniger kratzig).
 */
object Pegel {
    /** Ton von der Tuerstation, bevor er zum Lautsprecher des Displays geht. */
    const val LAUTSPRECHER = 2.0f

    /** Mikrofon des Displays, bevor es zur Tuerstation geht. */
    const val MIKROFON = 3.0f

    fun verstaerken(samples: ShortArray, faktor: Float) {
        if (faktor == 1.0f) return
        for (i in samples.indices) samples[i] = begrenzen(samples[i] * faktor).toInt().toShort()
    }

    /** Linear bis 24000, darueber weich gegen 32767. */
    internal fun begrenzen(x: Float): Float {
        val knie = 24000f
        val rest = 32767f - knie
        val betrag = kotlin.math.abs(x)
        if (betrag <= knie) return x
        val weich = knie + rest * kotlin.math.tanh((betrag - knie) / rest)
        return if (x < 0) -weich else weich
    }
}
