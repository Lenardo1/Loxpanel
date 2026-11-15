package com.loxpanel.spike

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.content.Context
import android.content.Intent
import android.os.Build
import android.os.IBinder
import android.provider.Settings
import android.util.Log
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.util.concurrent.Executors
import java.util.concurrent.TimeUnit

/**
 * Begleit-Tablet (eigene Version, Marco): Die LoxPanel-App läuft nur im Hintergrund,
 * vorn eine andere App (Loxone). Dieser Dienst meldet sich jede Minute beim LoxPanel-
 * Server (POST /api/begleiter/melden) mit dem eigenen Stand und übernimmt die dort im
 * Konfigurator gespeicherten Einstellungen (Wetter, Start-App, Weckdienst, BLE-Scanner).
 * Ohne gespeicherte Einstellungen ("soll" null) bleibt alles, wie es ist.
 *
 * Einrichten nur per adb über den StartApp-Empfänger:
 *   --es begleiterServer <loxberry>:8098 --es begleiterName "<Name>"   (aus: --es begleiterName "")
 */
class BegleiterDienst : Service() {

    companion object {
        private const val TAG = "LPBEGLEITER"
        private const val PREFS = "begleiter"

        private fun p(ctx: Context) = ctx.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        /** Begleit-Modus gewählt (Server eingetragen), auch wenn der Name noch fehlt. */
        fun gewaehlt(ctx: Context) = !p(ctx).getString("server", "").isNullOrBlank()
        fun an(ctx: Context) = !p(ctx).getString("name", "").isNullOrBlank() && !p(ctx).getString("server", "").isNullOrBlank()
        /** BLE-Scanner im Konfigurator ausgeschaltet (Einrichtung bleibt erhalten). */
        fun bleAus(ctx: Context) = p(ctx).getBoolean("bleAus", false)
        /** Wetter auch bei offenem Menü zeigen (Ausblenden im Konfigurator aus). */
        fun menueEgal(ctx: Context) = !p(ctx).getBoolean("menueAusblenden", true)

        fun setzen(ctx: Context, intent: Intent) {
            val e = p(ctx).edit()
            intent.getStringExtra("begleiterServer")?.let { e.putString("server", it.trim()) }
            intent.getStringExtra("begleiterName")?.let { e.putString("name", it.trim()) }
            e.apply()
            ctx.stopService(Intent(ctx, BegleiterDienst::class.java))
            if (an(ctx)) starten(ctx)
            Log.i(TAG, if (an(ctx)) "Begleiter an" else "Begleiter aus")
        }

        fun starten(ctx: Context) {
            if (!an(ctx)) return
            try {
                val i = Intent(ctx, BegleiterDienst::class.java)
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) ctx.startForegroundService(i) else ctx.startService(i)
            } catch (e: Exception) { Log.w(TAG, "Start fehlgeschlagen: ${e.message}") }
        }
    }

    private val arbeit = Executors.newSingleThreadScheduledExecutor { r -> Thread(r, "loxpanel-begleiter").apply { isDaemon = true } }
    private var laeuft = false

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        startForeground(5, notification())
        if (!an(this)) { stopSelf(); return START_NOT_STICKY }
        if (!laeuft) {
            laeuft = true
            arbeit.scheduleWithFixedDelay({ try { runde() } catch (e: Exception) { Log.w(TAG, "Fehler: ${e.message}") } },
                3, 60, TimeUnit.SECONDS)
        }
        return START_STICKY
    }

    override fun onDestroy() { arbeit.shutdownNow(); super.onDestroy() }

    private fun runde() {
        val pr = p(this)
        val antwort = senden("http://${pr.getString("server", "")}/api/begleiter/melden", meldung(pr.getString("name", "")!!))
            ?: return
        val soll = antwort.optJSONObject("soll") ?: return
        // Nur anwenden, wenn sich etwas geändert hat (sonst Wetterfeld jede Minute neu)
        val neu = soll.toString()
        if (neu == pr.getString("zuletzt", "")) return
        anwenden(soll)
        pr.edit().putString("zuletzt", neu).apply()
        Log.i(TAG, "Einstellungen aus dem Konfigurator übernommen")
    }

    private fun meldung(name: String): JSONObject {
        val w = getSharedPreferences("wetter", Context.MODE_PRIVATE)
        val sa = getSharedPreferences("startapp", Context.MODE_PRIVATE)
        val paket = sa.getString("paket", "") ?: ""
        val ist = JSONObject()
            .put("wetter", WetterOverlay.an(this))
            .put("wetterQuelle", w.getString("ort", "") ?: "")
            .put("wetterSymbole", w.getString("icons", "") ?: "")
            .put("farbe", w.getString("farbe", "schwarz") ?: "schwarz")
            .put("x", w.getInt("wetterX", -1)).put("y", w.getInt("wetterY", -1))
            .put("menueAusblenden", !menueEgal(this))
            .put("startApp", paket.isNotEmpty())
            .put("startPaket", paket.ifEmpty { "com.loxone.kerberos" })
            .put("weckdienst", WachDienst.an(this))
            .put("ble", BlePresenceService.eingerichtet(this) && !bleAus(this))
            .put("bleName", getSharedPreferences(BlePresenceService.PREFS, Context.MODE_PRIVATE).getString("name", "") ?: "")
        val version = try { packageManager.getPackageInfo(packageName, 0).versionName } catch (_: Exception) { "" }
        val dienste = Settings.Secure.getString(contentResolver, Settings.Secure.ENABLED_ACCESSIBILITY_SERVICES) ?: ""
        return JSONObject().put("name", name).put("version", version).put("android", Build.VERSION.RELEASE)
            .put("modell", Build.MODEL).put("bedienungshilfe", dienste.contains("$packageName/"))
            .put("ist", ist)
    }

    private fun anwenden(s: JSONObject) {
        val pr = p(this)
        // Wetter: Einstellungen wie per adb, danach Einblendung neu starten
        val w = Intent()
        w.putExtra("wetter", if (s.optBoolean("wetter", true)) s.optString("wetterQuelle", "") else "")
        s.optString("wetterSymbole", "").takeIf { it.isNotEmpty() }?.let { w.putExtra("wetterIcons", it) }
        w.putExtra("wetterFarbe", s.optString("farbeHex", "#0e0e0e"))
        w.putExtra("wetterFarbeName", s.optString("farbe", "schwarz"))
        w.putExtra("wetterX", s.optInt("x", -1)); w.putExtra("wetterY", s.optInt("y", -1))
        pr.edit().putBoolean("menueAusblenden", s.optBoolean("menueAusblenden", true))
            .putBoolean("bleAus", !s.optBoolean("ble", true)).apply()
        WetterOverlay.setzen(this, w)
        // Start-App
        getSharedPreferences("startapp", Context.MODE_PRIVATE).edit()
            .putString("paket", if (s.optBoolean("startApp", true)) s.optString("startPaket", "") else "").apply()
        // Weckdienst
        if (s.optBoolean("weckdienst", true) != WachDienst.an(this)) WachDienst.setzen(this, s.optBoolean("weckdienst", true))
        // BLE-Scanner: neu einrichten, wenn im Konfigurator ein Schlüssel steht; sonst wie bisher.
        // Aus = nur anhalten, die Einrichtung bleibt.
        val schluessel = s.optString("bleSchluessel", "")
        if (!bleAus(this) && schluessel.isNotEmpty()) {
            val ble = getSharedPreferences(BlePresenceService.PREFS, Context.MODE_PRIVATE)
            val host = pr.getString("server", "")!!.substringBefore(":")
            val name = s.optString("bleName", "").ifEmpty { pr.getString("name", "")!! }
            if (ble.getString("key", "") != schluessel || ble.getString("name", "") != name || ble.getString("host", "") != host) {
                stopService(Intent(this, BlePresenceService::class.java))
                val i = Intent(this, BlePresenceService::class.java).putExtra("host", host).putExtra("name", name).putExtra("key", schluessel)
                try { if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) startForegroundService(i) else startService(i) }
                catch (e: Exception) { Log.w(TAG, "BLE-Scanner nicht gestartet: ${e.message}") }
                Log.i(TAG, "BLE-Scanner aus dem Konfigurator eingerichtet: $name")
                return
            }
        }
        if (bleAus(this)) stopService(Intent(this, BlePresenceService::class.java)) else BlePresenceService.starten(this)
    }

    private fun senden(adresse: String, body: JSONObject): JSONObject? = try {
        val con = URL(adresse).openConnection() as HttpURLConnection
        con.connectTimeout = 8000; con.readTimeout = 8000; con.requestMethod = "POST"; con.doOutput = true
        con.setRequestProperty("Content-Type", "application/json")
        con.outputStream.use { it.write(body.toString().toByteArray(Charsets.UTF_8)) }
        try { JSONObject(con.inputStream.bufferedReader().use { it.readText() }) } finally { con.disconnect() }
    } catch (e: Exception) { Log.w(TAG, "Melden fehlgeschlagen: ${e.message}"); null }

    private fun notification(): Notification {
        val kanal = "loxpanel-begleiter"
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            (getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager).createNotificationChannel(
                NotificationChannel(kanal, "Begleit-Tablet", NotificationManager.IMPORTANCE_MIN))
        }
        val b = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) Notification.Builder(this, kanal)
        else @Suppress("DEPRECATION") Notification.Builder(this)
        return b.setSmallIcon(android.R.drawable.ic_menu_manage).setContentTitle("Begleit-Tablet").setOngoing(true).build()
    }
}
