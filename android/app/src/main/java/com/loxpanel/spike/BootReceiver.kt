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
            intent.action == Intent.ACTION_LOCKED_BOOT_COMPLETED
        ) {
            // Den eigenen Server nur, wenn er auf diesem Gerät laufen soll; mit
            // einem Server im Netz gibt es nichts zu starten (Visu.eigenerServer).
            ServerService.starten(context)
            BlePresenceService.starten(context)   // nur wenn eingerichtet (eigene Version)
            WachDienst.starten(context)           // Standby-Weckdienst, nur wenn eingeschaltet (eigene Version)
            // Eingebauten Kiosk (unsere Vollbild-WebView) in den Vordergrund holen –
            // nur wenn die Anzeige eingerichtet ist. Ein Gerät, auf dem nur der
            // BLE-Scanner läuft (z. B. Tablet mit Loxone-App), bleibt so unberührt.
            if (!Visu.eingerichtet(context)) return
            try {
                context.startActivity(
                    Intent(context, KioskActivity::class.java)
                        .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                )
            } catch (e: Exception) { /* ignoriert */ }
        }
    }
}
