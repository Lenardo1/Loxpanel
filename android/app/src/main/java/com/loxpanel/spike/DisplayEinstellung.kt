package com.loxpanel.spike

import android.content.Context
import android.provider.Settings
import android.view.Gravity
import android.widget.LinearLayout
import android.widget.SeekBar
import android.widget.TextView

/**
 * Display-Helligkeit direkt am Geraet einstellen (eigene Version, Marco):
 * Grundhelligkeit (Android-Systemhelligkeit) und Helligkeit nach Annaeherung
 * (Annaeherung.kt). Steht als Abschnitt auf der Einrichtungsseite
 * (langer Druck auf die Uhr). Werte in SharedPreferences "annaeherung", die
 * KioskActivity liest sie beim Zurueckkehren (onResume).
 */
object DisplayEinstellung {
    const val PREFS = "annaeherung"

    fun abschnitt(ctx: Context, text: (String, Float, Boolean) -> TextView, dp: (Int) -> Int): LinearLayout {
        val p = ctx.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        val box = LinearLayout(ctx).apply { orientation = LinearLayout.VERTICAL; setPadding(0, dp(24), 0, 0) }
        box.addView(text("Display-Helligkeit", 20f, true))

        // Grundhelligkeit = Android-Systemhelligkeit (braucht „Systemeinstellungen aendern“)
        val darf = Settings.System.canWrite(ctx)
        val sys = try { Settings.System.getInt(ctx.contentResolver, Settings.System.SCREEN_BRIGHTNESS) } catch (_: Exception) { 230 }
        box.addView(regler(ctx, text, dp, "Grundhelligkeit", 10, 100, Math.round(sys * 100f / 255), "%",
            if (darf) "So hell ist das Display, wenn jemand davorsteht." else
                "Nur lesbar: der App fehlt die Erlaubnis „Systemeinstellungen ändern“.", darf) { v ->
            try {
                Settings.System.putInt(ctx.contentResolver, Settings.System.SCREEN_BRIGHTNESS_MODE,
                    Settings.System.SCREEN_BRIGHTNESS_MODE_MANUAL)
                Settings.System.putInt(ctx.contentResolver, Settings.System.SCREEN_BRIGHTNESS, Math.round(v * 255f / 100))
            } catch (_: Exception) { }
        })
        box.addView(regler(ctx, text, dp, "Ruhe-Helligkeit", 5, 100, p.getInt("ruhe", 100), "%",
            "Anteil der Grundhelligkeit, wenn niemand in der Nähe ist. 100 % = aus (immer voll hell).", true) { v ->
            p.edit().putInt("ruhe", v).apply()
        })
        box.addView(regler(ctx, text, dp, "Voll hell nach Annäherung", 5, 300, p.getInt("halten", 30), "s",
            "So lange bleibt es nach Annäherung oder Berührung voll hell, dann dimmt es weich ab.", true) { v ->
            p.edit().putInt("halten", v).apply()
        })
        box.addView(text("Nachts abdunkeln stellst du im LoxPanel-Konfigurator ein (Vorgaben → Verhalten → Nacht); " +
            "es wirkt zusätzlich.", 13f, false))
        return box
    }

    private fun regler(ctx: Context, text: (String, Float, Boolean) -> TextView, dp: (Int) -> Int,
                       titel: String, min: Int, max: Int, wert: Int, einheit: String, hinweis: String,
                       aktiv: Boolean, aendern: (Int) -> Unit): LinearLayout {
        val zeile = LinearLayout(ctx).apply { orientation = LinearLayout.VERTICAL; setPadding(0, dp(12), 0, 0) }
        val kopf = LinearLayout(ctx).apply { orientation = LinearLayout.HORIZONTAL }
        val name = text(titel, 16f, true)
        val anzeige = text("$wert $einheit", 16f, false).apply { gravity = Gravity.END }
        kopf.addView(name, LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f))
        kopf.addView(anzeige)
        zeile.addView(kopf)
        val bar = SeekBar(ctx).apply {
            this.max = max - min
            progress = (wert.coerceIn(min, max) - min)
            isEnabled = aktiv
            setOnSeekBarChangeListener(object : SeekBar.OnSeekBarChangeListener {
                override fun onProgressChanged(s: SeekBar?, v: Int, vomNutzer: Boolean) {
                    anzeige.text = "${v + min} $einheit"
                    if (vomNutzer) aendern(v + min)
                }
                override fun onStartTrackingTouch(s: SeekBar?) {}
                override fun onStopTrackingTouch(s: SeekBar?) {}
            })
        }
        zeile.addView(bar)
        zeile.addView(text(hinweis, 13f, false))
        return zeile
    }
}
