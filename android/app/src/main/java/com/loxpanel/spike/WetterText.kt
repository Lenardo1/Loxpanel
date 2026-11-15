package com.loxpanel.spike

import java.util.Locale

/** Wetter für die Einblendung (WetterOverlay), ohne Android: testbar. */
object WetterText {
    /** WMO-Wettercode (Open-Meteo) -> Symbol und Text. */
    fun art(code: Int, tag: Boolean): Pair<String, String> = when (code) {
        0 -> (if (tag) "☀️" else "🌙") to "Klar"
        1 -> (if (tag) "🌤️" else "🌙") to "Überwiegend klar"
        2 -> "⛅" to "Teils bewölkt"
        3 -> "☁️" to "Bewölkt"
        45, 48 -> "🌫️" to "Nebel"
        51, 53, 55, 56, 57 -> "🌦️" to "Nieselregen"
        61, 63, 65, 66, 67, 80, 81, 82 -> "🌧️" to "Regen"
        71, 73, 75, 77 -> "❄️" to "Schnee"
        85, 86 -> "🌨️" to "Schneeschauer"
        95, 96, 99 -> "⛈️" to "Gewitter"
        else -> "🌡️" to ""
    }

    /** 4.84 -> "4,8°", -0.04 -> "0,0°" */
    fun grad(t: Double): String {
        val r = Math.round(t * 10) / 10.0
        return String.format(Locale.GERMANY, "%.1f°", if (r == 0.0) 0.0 else r)
    }

    /** Ganze Grad für Höchst/Tiefst: 5.4 -> "5°" */
    fun ganz(t: Double): String = "${Math.round(t)}°"
}
