package com.loxpanel.spike

import org.json.JSONObject
import java.util.Calendar
import java.util.Locale
import java.util.TimeZone

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

    /** Symbol aus dem Bildnamen von Weather4Lox (weatherCode.image, z. B. "partly-cloudy-day",
     *  ersatzweise weatherCode.weather4lox, z. B. "cloudy_shower_1"). */
    fun symbolW4l(bild: String?): String {
        val b = (bild ?: "").lowercase()
        return when {
            "thunder" in b || "storm" in b -> "⛈️"
            "sleet" in b -> "🌨️"
            "snow" in b -> "❄️"
            "rain" in b || "shower" in b || "drizzle" in b -> "🌧️"
            "fog" in b || "mist" in b || "haze" in b -> "🌫️"
            "partly" in b && "night" in b -> "☁️"
            "partly" in b || "mostly" in b -> "⛅"
            "cloud" in b || "overcast" in b -> "☁️"
            "wind" in b -> "💨"
            "clear" in b && "night" in b -> "🌙"
            "clear" in b || "sun" in b -> "☀️"
            else -> "🌡️"
        }
    }

    /** 4.84 -> "4,8°", -0.04 -> "0,0°" */
    fun grad(t: Double): String {
        val r = Math.round(t * 10) / 10.0
        return String.format(Locale.GERMANY, "%.1f°", if (r == 0.0) 0.0 else r)
    }

    /** Ganze Grad für Höchst/Tiefst: 5.4 -> "5°" */
    fun ganz(t: Double): String = "${Math.round(t)}°"

    /** Loxone-Wettercode (1-29, wie Weather4Lox ihn als weatherCode.loxone liefert) ->
     *  Dateiname des Loxone-Symbols auf dem Miniserver (aurora/weather-NN, NN = Code - 1;
     *  die Codes 1-4 gibt es als Tag- und Nachtvariante). */
    fun loxoneSymbol(code: Int?, nacht: Boolean): String? {
        if (code == null || code < 1 || code > 29) return null
        val nn = String.format(Locale.ROOT, "%02d", code - 1)
        return if (code <= 4) "weather-$nn-${if (nacht) "n" else "d"}.svg" else "weather-$nn.svg"
    }

    /** Zahl aus JSON-Wert (Weather4Lox liefert Codes mal als Zahl, mal als Text). */
    fun zahl(v: Any?): Int? = when (v) {
        is Number -> v.toInt()
        is String -> v.trim().toDoubleOrNull()?.toInt()
        else -> null
    }

    /** Nacht, wenn die Uhrzeit vor Sonnenaufgang oder nach Sonnenuntergang liegt ("07:29"/"16:33"). */
    fun istNacht(auf: String?, unter: String?, jetzt: Calendar): Boolean {
        fun min(t: String?) = t?.split(":")?.takeIf { it.size >= 2 }?.let { (it[0].toIntOrNull() ?: return null) * 60 + (it[1].toIntOrNull() ?: return null) }
        val a = min(auf) ?: return false; val u = min(unter) ?: return false
        val m = jetzt.get(Calendar.HOUR_OF_DAY) * 60 + jetzt.get(Calendar.MINUTE)
        return m < a || m >= u
    }

    /** "7° / -2°" aus einem Tag von dailyforecast.json. */
    fun maxMin(tag: JSONObject): String {
        val t = tag.optJSONObject("temperature") ?: return ""
        val max = t.optJSONObject("max")?.optDouble("air"); val min = t.optJSONObject("min")?.optDouble("air")
        if (max == null || min == null || max.isNaN() || min.isNaN()) return ""
        return "${ganz(max)} / ${ganz(min)}"
    }

    /** 0 -> "Heute", 1 -> "Morgen", sonst "Di 17.11." (Zeitzone Europe/Berlin). */
    fun tagName(index: Int, epochSek: Long): String {
        if (index == 0) return "Heute"
        if (index == 1) return "Morgen"
        val c = Calendar.getInstance(TimeZone.getTimeZone("Europe/Berlin")).apply { timeInMillis = epochSek * 1000 }
        val wt = arrayOf("So", "Mo", "Di", "Mi", "Do", "Fr", "Sa")[c.get(Calendar.DAY_OF_WEEK) - 1]
        return String.format(Locale.GERMANY, "%s %d.%d.", wt, c.get(Calendar.DAY_OF_MONTH), c.get(Calendar.MONTH) + 1)
    }

    /** Einträge, die nur im geöffneten Menü der Loxone-App stehen (LoxSicht). */
    val MENUE_MARKER = listOf("Automatik Designer", "Hilfe und Feedback", "Zur Standard-Ansicht gehen")
    fun istMenue(text: String): Boolean = text.trim() in setOf(
        "Automatik Designer", "Zur Standard-Ansicht gehen", "Hilfe und Feedback", "Batteriestatus Geräte",
        "INTERN VERBUNDEN", "EXTERN VERBUNDEN")
}
