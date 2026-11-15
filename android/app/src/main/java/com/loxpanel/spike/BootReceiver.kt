package com.loxpanel.spike

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent

/**
 * Startet den Server-Service automatisch nach dem Booten — damit das Panel nach
 * Stromausfall von selbst wieder läuft (Appliance-Verhalten).
 */
class BootReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action == Intent.ACTION_BOOT_COMPLETED ||
            intent.action == Intent.ACTION_LOCKED_BOOT_COMPLETED ||
            intent.action == Intent.ACTION_MY_PACKAGE_REPLACED   // nach App-Update: Dienste wieder starten
        ) {
            // Den eigenen Server nur, wenn er auf diesem Gerät laufen soll; mit
            // einem Server im Netz gibt es nichts zu starten (Visu.eigenerServer).
            ServerService.starten(context)
            BlePresenceService.starten(context)   // nur wenn eingerichtet (eigene Version)
            WachDienst.starten(context)           // Standby-Weckdienst, nur wenn eingeschaltet (eigene Version)
            WetterOverlay.starten(context)        // Wetter über einer fremden App, nur wenn eingestellt (eigene Version)
            BegleiterDienst.starten(context)      // Einstellungen aus dem Konfigurator holen, nur wenn eingerichtet (eigene Version)
            // Eingebauten Kiosk (unsere Vollbild-WebView) in den Vordergrund holen –
            // nur wenn die Anzeige eingerichtet ist. Ein Gerät, auf dem nur der
            // BLE-Scanner läuft (z. B. Tablet mit Loxone-App), öffnet stattdessen die
            // per adb eingestellte App (StartApp), sonst nichts.
            if (!Visu.eingerichtet(context)) { StartApp.oeffnen(context); return }
            try {
                context.startActivity(
                    Intent(context, KioskActivity::class.java)
                        .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                )
            } catch (e: Exception) { /* ignoriert */ }
        }
    }
}
