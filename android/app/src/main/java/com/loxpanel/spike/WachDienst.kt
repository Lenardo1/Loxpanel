package com.loxpanel.spike

import android.annotation.SuppressLint
import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.content.Context
import android.content.Intent
import android.hardware.Sensor
import android.hardware.SensorEvent
import android.hardware.SensorEventListener
import android.hardware.SensorManager
import android.os.Build
import android.os.IBinder
import android.os.PowerManager
import android.util.Log
import java.net.ServerSocket
import java.net.Socket
import kotlin.concurrent.thread

/**
 * Echtes Standby (eigene Version): Die Anzeige schaltet das Display im Schoner
 * wirklich aus (DevicePolicyManager.lockNow, siehe LockAdmin). Dann laeuft keine
 * Anzeige mehr, darum weckt dieser Dienst:
 *  - per HTTP im Format von WallPanel: POST /api/command {"wake": true}. Der
 *    LoxPanel-Server ruft das als Display-Treiber "wallpanel" auf, z. B. ueber
 *    /api/display?device=…&on=1 aus einem virtuellen Ausgang in Loxone.
 *  - ueber den Naeherungssensor (Weck-Sensor, meldet auch bei Display aus).
 * Einschalten per adb: am start -n com.loxpanel.spike/.KioskActivity --ez standby true
 */
class WachDienst : Service(), SensorEventListener {

    companion object {
        private const val TAG = "LPSTANDBY"
        const val PORT = 2971
        const val PREFS = "standby"

        fun an(ctx: Context): Boolean =
            ctx.getSharedPreferences(PREFS, Context.MODE_PRIVATE).getBoolean("an", false)

        fun setzen(ctx: Context, an: Boolean) {
            ctx.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit().putBoolean("an", an).apply()
            if (an) starten(ctx) else ctx.stopService(Intent(ctx, WachDienst::class.java))
        }

        fun starten(ctx: Context) {
            if (!an(ctx)) return
            val i = Intent(ctx, WachDienst::class.java)
            try {
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) ctx.startForegroundService(i) else ctx.startService(i)
            } catch (e: Exception) { Log.w(TAG, "Start fehlgeschlagen: ${e.message}") }
        }
    }

    @Volatile private var laeuft = false
    private var server: ServerSocket? = null
    private var sensoren: SensorManager? = null

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        startForeground(3, notification())
        if (!laeuft) {
            laeuft = true
            thread(name = "loxpanel-wach", isDaemon = true) { horchen() }
            sensoren = getSystemService(Context.SENSOR_SERVICE) as SensorManager
            val nah = sensoren?.getDefaultSensor(Sensor.TYPE_PROXIMITY, true)
                ?: sensoren?.getDefaultSensor(Sensor.TYPE_PROXIMITY)
            nah?.let { sensoren?.registerListener(this, it, SensorManager.SENSOR_DELAY_NORMAL) }
            Log.i(TAG, "Weckdienst laeuft (Port $PORT, Naeherung ${if (nah != null) "ja" else "nein"})")
        }
        return START_STICKY
    }

    override fun onDestroy() {
        laeuft = false
        sensoren?.unregisterListener(this)
        try { server?.close() } catch (_: Exception) {}
        super.onDestroy()
    }

    private fun horchen() {
        try {
            ServerSocket(PORT).use { s ->
                server = s
                while (laeuft) {
                    val c = try { s.accept() } catch (e: Exception) { if (laeuft) continue else break }
                    thread(isDaemon = true) { antworten(c) }
                }
            }
        } catch (e: Exception) {
            Log.w(TAG, "HTTP-Port $PORT: ${e.message}")
        }
    }

    private fun antworten(c: Socket) {
        c.use {
            it.soTimeout = 3000
            val puffer = ByteArray(4096)
            val n = try { it.getInputStream().read(puffer) } catch (_: Exception) { -1 }
            val anfrage = if (n > 0) String(puffer, 0, n, Charsets.UTF_8) else ""
            when (WachBefehl.befehl(anfrage)) {
                true -> wecken("HTTP", visu = false)   // nur Display an; was die Visu zeigt (Uhr), bestimmt der Server
                false -> Unit   // Schlafen regelt die Anzeige (Schoner nach Leerlauf)
                null -> Unit
            }
            val body = "{\"ok\":true}"
            it.getOutputStream().write(("HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n" +
                "Content-Length: ${body.length}\r\nConnection: close\r\n\r\n$body").toByteArray())
        }
    }

    override fun onSensorChanged(event: SensorEvent) {
        if (event.sensor.type != Sensor.TYPE_PROXIMITY) return
        val nah = event.values.isNotEmpty() && event.values[0] < event.sensor.maximumRange
        val pm = getSystemService(Context.POWER_SERVICE) as PowerManager
        if (nah && !pm.isInteractive) wecken("Naeherung", visu = true)   // wer davor steht, will bedienen
    }

    override fun onAccuracyChanged(sensor: Sensor?, accuracy: Int) {}

    /** Display einschalten und die Anzeige nach vorn holen; sie weckt die Visu. */
    @SuppressLint("WakelockTimeout")
    private fun wecken(grund: String, visu: Boolean) {
        Log.i(TAG, "Wecken ($grund)")
        val pm = getSystemService(Context.POWER_SERVICE) as PowerManager
        @Suppress("DEPRECATION")
        pm.newWakeLock(PowerManager.SCREEN_BRIGHT_WAKE_LOCK or PowerManager.ACQUIRE_CAUSES_WAKEUP,
            "loxpanel:wecken").acquire(5000)
        try {
            startActivity(Intent(this, KioskActivity::class.java)
                .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_SINGLE_TOP)
                .putExtra(if (visu) "wecken" else "anzeigen", true))
        } catch (e: Exception) { Log.w(TAG, "Anzeige nicht geholt: ${e.message}") }
    }

    private fun notification(): Notification {
        val kanal = "loxpanel-standby"
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            (getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager).createNotificationChannel(
                NotificationChannel(kanal, "Display-Standby", NotificationManager.IMPORTANCE_LOW))
        }
        @Suppress("DEPRECATION")
        val b = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) Notification.Builder(this, kanal) else Notification.Builder(this)
        return b.setContentTitle("LoxPanel").setContentText("Display-Standby bereit")
            .setSmallIcon(android.R.drawable.ic_lock_idle_lock).setOngoing(true).build()
    }
}
