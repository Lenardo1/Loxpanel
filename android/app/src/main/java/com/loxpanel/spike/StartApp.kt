package com.loxpanel.spike

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.util.Log

/**
 * Fremde App nach dem Hochfahren öffnen (eigene Version, Marco): auf einem Tablet,
 * das die Loxone-App zeigt und LoxPanel nur als BLE-Scanner nutzt, soll nach einem
 * Stromausfall wieder die Loxone-App vorn sein. Gilt nur, wenn die LoxPanel-Anzeige
 * NICHT eingerichtet ist (sonst startet BootReceiver die eigene Anzeige).
 *
 * Einstellen nur per adb (DUMP hat die adb-Shell, gewöhnliche Apps nicht):
 *   adb shell am broadcast -n com.loxpanel.spike/.StartApp --es paket com.loxone.kerberos
 * Aus: --es paket ""
 * Weckdienst (Port 2971, Display an/aus per HTTP) ohne Anzeige: --ez standby true
 * Aus dem Hintergrund darf die App nur mit SYSTEM_ALERT_WINDOW starten:
 *   adb shell appops set com.loxpanel.spike SYSTEM_ALERT_WINDOW allow
 */
class StartApp : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        // Weckdienst (Display an/aus per HTTP, z. B. vom Loxone-Bewegungsmelder) ohne die
        // Anzeige ein-/ausschalten: --ez standby true|false
        if (intent.hasExtra("standby")) {
            val an = intent.getBooleanExtra("standby", false)
            WachDienst.setzen(context, an)
            Log.i(TAG, "Weckdienst ${if (an) "an" else "aus"}")
        }
        // Wetter-Einblendung über der Loxone-App: --es wetter <Weather4Lox-URL> --es wetterIcons <Miniserver-URL> [--ei wetterX/Y/B/H]
        if (listOf("wetter", "wetterIcons", "wetterX", "wetterY", "wetterB", "wetterH").any { intent.hasExtra(it) })
            WetterOverlay.setzen(context, intent)
        // Begleit-Tablet: Server und Name für die Einstellungen aus dem Konfigurator
        if (intent.hasExtra("begleiterServer") || intent.hasExtra("begleiterName")) BegleiterDienst.setzen(context, intent)
        val paket = intent.getStringExtra("paket")?.trim() ?: return
        prefs(context).edit().putString(PAKET, paket).apply()
        Log.i(TAG, if (paket.isEmpty()) "Start-App aus" else "Start-App nach dem Hochfahren: $paket")
    }

    companion object {
        private const val TAG = "LPSTART"
        private const val PAKET = "paket"
        private fun prefs(ctx: Context) = ctx.getSharedPreferences("startapp", Context.MODE_PRIVATE)

        /** Eingestellte App öffnen; false, wenn keine eingestellt oder nicht installiert. */
        fun oeffnen(ctx: Context): Boolean {
            val paket = prefs(ctx).getString(PAKET, "")?.takeIf { it.isNotEmpty() } ?: return false
            val start = ctx.packageManager.getLaunchIntentForPackage(paket)
            if (start == null) { Log.w(TAG, "$paket nicht installiert"); return false }
            return try {
                ctx.startActivity(start.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
                Log.i(TAG, "$paket geöffnet"); true
            } catch (e: Exception) { Log.w(TAG, "$paket nicht geöffnet: ${e.message}"); false }
        }
    }
}
