package com.loxpanel.spike

import android.app.Activity
import android.os.Bundle
import android.view.Gravity
import android.widget.ScrollView
import android.widget.TextView

/**
 * Startet den LoxPanel-Server-Service und zeigt einen kurzen Status.
 * Die eigentliche Anzeige des Panels macht die KioskActivity (Visu.basis).
 */
class MainActivity : Activity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        val eingerichtet = Visu.eingerichtet(this)
        val eigener = eingerichtet && Visu.eigenerServer(this)
        if (eigener) ServerService.starten(this)
        val basis = Visu.basis(this)

        val tv = TextView(this).apply {
            textSize = 14f
            setPadding(32, 32, 32, 32)
            gravity = Gravity.TOP or Gravity.START
            text = buildString {
                appendLine(when {
                    !eingerichtet -> "Noch nicht eingerichtet: Die Anzeige fragt beim Start, wo der Server läuft."
                    eigener -> "LoxPanel-Server auf diesem Gerät wird gestartet …"
                    else -> "Server im Netz: ${Visu.server(this@MainActivity)}"
                })
                appendLine()
                appendLine("Visu:")
                appendLine("    $basis")
                appendLine()
                appendLine("Konfiguration:")
                appendLine("    ${basis}config")
                appendLine()
                appendLine("Log ansehen:")
                appendLine("    adb logcat -s LPSERVER LPANZEIGE python.stdout python.stderr")
            }
        }
        setContentView(ScrollView(this).apply { addView(tv) })
    }
}
