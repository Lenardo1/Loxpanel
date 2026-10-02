package com.loxpanel.spike

/**
 * Nachtmodus der Visu in der Anzeige: Nachts dunkelt die Visu um einen
 * eingestellten Prozentsatz ab ("Nachts abdunkeln"). In der App geschieht das
 * über die echte Helligkeit des Fensters statt über eine dunkle Fläche über der
 * Visu. Hier steht die Rechnung, ohne Android, damit sie sich auf dem PC prüfen
 * lässt.
 */
object Helligkeit {
    /** Fensterwert, bei dem die Systemhelligkeit gilt
     *  (WindowManager.LayoutParams.BRIGHTNESS_OVERRIDE_NONE). */
    const val SYSTEM = -1f

    /** Höchstwert der Helligkeitseinstellung, wenn das Gerät keinen nennt (AOSP). */
    const val MAX_STANDARD = 255

    /** Eingestellte Systemhelligkeit als Anteil 0..1. Die Einstellung reicht bei
     *  AOSP bis 255, bei manchen Herstellern weiter (z. B. 2047). */
    fun anteil(einstellung: Int, max: Int): Float =
        (einstellung.toFloat() / (if (max > 0) max else MAX_STANDARD)).coerceIn(0f, 1f)

    /** Fensterhelligkeit für [prozent] der Systemhelligkeit, deren Anteil 0..1
     *  [system] ist; ab 100 die Systemhelligkeit selbst. null, wenn die App nicht
     *  absenken kann, weil die Systemhelligkeit unbekannt ist (automatische
     *  Helligkeit): Ein fester Wert könnte heller sein als die Automatik. */
    fun fensterwert(prozent: Int, system: Float?): Float? = when {
        prozent >= 100 -> SYSTEM
        system == null -> null
        else -> system * prozent.coerceAtLeast(0) / 100f
    }
}
