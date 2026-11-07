package com.loxpanel.spike

import android.annotation.SuppressLint
import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.bluetooth.BluetoothManager
import android.bluetooth.le.ScanCallback
import android.bluetooth.le.ScanResult
import android.bluetooth.le.ScanSettings
import android.content.Context
import android.content.Intent
import android.net.wifi.WifiManager
import android.os.Build
import android.os.IBinder
import android.os.ParcelUuid
import android.util.Log
import org.json.JSONArray
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.net.URLEncoder
import java.util.concurrent.Executors
import java.util.concurrent.ScheduledFuture
import java.util.concurrent.TimeUnit

/**
 * BLE-Presence-Scanner als Dienst (eigene Version, Marco): spricht mit dem
 * LoxBerry-Plugin ble_presence genau wie dessen Shelly-Skript (POST
 * /shelly/register, /shelly/scan, /shelly/heartbeat, /shelly/event,
 * /shelly/calibration, GET /shelly/devices auf Port 8099). Logik in BleLogik.
 *
 * Einrichten per adb (der Dienst verlangt android.permission.DUMP, die hat die
 * adb-Shell, gewoehnliche Apps nicht):
 *   adb shell am start-foreground-service -n com.loxpanel.spike/.BlePresenceService \
 *     --es host 192.168.1.10 --es name Flur --es key <api_key>
 * Abschalten: ... --ez aus true
 * Discovery („Geraete suchen“) des Plugins geht nicht: das ruft Script.Eval am Shelly.
 */
class BlePresenceService : Service() {
    companion object {
        private const val TAG = "LPBLE"
        private const val PREFS = "blepresence"
        private const val PORT = 8099
        const val VERSION = "1.5.5-loxpanel"

        fun eingerichtet(ctx: Context): Boolean =
            ctx.getSharedPreferences(PREFS, Context.MODE_PRIVATE).let {
                !it.getString("host", "").isNullOrEmpty() && !it.getString("key", "").isNullOrEmpty()
            }

        fun starten(ctx: Context) {
            if (!eingerichtet(ctx)) return
            val i = Intent(ctx, BlePresenceService::class.java)
            try {
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) ctx.startForegroundService(i) else ctx.startService(i)
            } catch (e: Exception) { Log.w(TAG, "Start fehlgeschlagen: ${e.message}") }
        }
    }

    private val logik = BleLogik()
    private val arbeit = Executors.newSingleThreadScheduledExecutor { r -> Thread(r, "loxpanel-ble").apply { isDaemon = true } }
    private val zeitplaene = ArrayList<ScheduledFuture<*>>()
    private var host = ""; private var name = ""; private var key = ""
    @Volatile private var bereit = false
    private var scannt = false
    private var start = 0L

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        startForeground(2, notification())
        val p = getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        intent?.let {
            if (it.getBooleanExtra("aus", false)) {
                p.edit().clear().apply(); stopSelf(); return START_NOT_STICKY
            }
            val e = p.edit()
            it.getStringExtra("host")?.let { v -> e.putString("host", v.trim()) }
            it.getStringExtra("name")?.let { v -> e.putString("name", v.trim()) }
            it.getStringExtra("key")?.let { v -> e.putString("key", v.trim()) }
            e.apply()
        }
        host = p.getString("host", "") ?: ""; name = p.getString("name", "") ?: ""; key = p.getString("key", "") ?: ""
        if (host.isEmpty() || key.isEmpty() || name.isEmpty()) { stopSelf(); return START_NOT_STICKY }
        if (start == 0L) {
            start = jetzt()
            Log.i(TAG, "BLE Presence Scanner $VERSION: $name -> $host")
            arbeit.execute { registrieren() }
        }
        return START_STICKY
    }

    override fun onDestroy() {
        scanStoppen()
        zeitplaene.forEach { it.cancel(false) }
        arbeit.shutdownNow()
        super.onDestroy()
    }

    private fun jetzt() = System.currentTimeMillis() / 1000

    // ---- Ablauf wie im Shelly-Skript ----

    private fun registrieren() {
        bereit = false
        val ip = eigeneIp()
        val d = post("/shelly/register", JSONObject().put("scanner", name).put("ip", ip)
            .put("model", "WallDisplay-" + Build.MODEL).put("firmware", Build.DISPLAY)
            .put("script_version", VERSION).put("scan_interval", logik.scanIntervall))
        if (d == null || !d.optBoolean("success")) {
            Log.w(TAG, "Registrierung fehlgeschlagen, neuer Versuch in 10 s")
            arbeit.schedule({ registrieren() }, 10, TimeUnit.SECONDS); return
        }
        logik.setzeBekannt(liste(d.optJSONArray("known_macs")))
        logik.setzeIrks(liste(d.optJSONArray("known_irks")))   // nur mit gepatchtem Plugin
        if (d.optInt("scan_interval", 0) > 0) logik.scanIntervall = d.optInt("scan_interval")
        Log.i(TAG, "Registriert: ${logik.anzahlBekannt()} bekannte Geraete")
        bereit = true
        if (zeitplaene.isEmpty()) {
            zeitplaene += arbeit.scheduleWithFixedDelay({ sicher { logik.pruefeOffline(jetzt()); senden() } },
                logik.scanIntervall.toLong(), logik.scanIntervall.toLong(), TimeUnit.SECONDS)
            zeitplaene += arbeit.scheduleWithFixedDelay({ sicher { lebenszeichen() } }, 10, 10, TimeUnit.SECONDS)
            zeitplaene += arbeit.scheduleWithFixedDelay({ sicher { geraeteHolen() } }, 60, 60, TimeUnit.SECONDS)
            zeitplaene += arbeit.scheduleWithFixedDelay({ sicher { zustandMelden() } }, 2, 30, TimeUnit.SECONDS)
            arbeit.schedule({ sicher { logik.meldeNieGesehene(); senden() } }, logik.offlineNach.toLong(), TimeUnit.SECONDS)
        }
        scanStarten()
    }

    private fun senden() {
        if (!bereit || logik.warteschlange.isEmpty()) return
        val scans = logik.nimmWarteschlange()
        if (post("/shelly/scan", JSONObject().put("scanner", name).put("scans", JSONArray(scans))
                .put("discovery", false)) == null) Log.w(TAG, "Senden fehlgeschlagen")
    }

    private fun lebenszeichen() {
        if (!bereit) return
        val kal = logik.nimmKalibrierung()
        if (kal.isNotEmpty()) post("/shelly/calibration", JSONObject().put("scanner", name).put("readings", JSONArray(kal)))
        val d = post("/shelly/heartbeat", JSONObject().put("scanner", name)
            .put("uptime", jetzt() - start).put("script_version", VERSION))
        if (d == null || !d.optBoolean("success")) {
            Log.w(TAG, "Lebenszeichen fehlgeschlagen, neu registrieren")
            bereit = false
            arbeit.schedule({ registrieren() }, 5, TimeUnit.SECONDS)
        }
    }

    private fun geraeteHolen() {
        val d = get("/shelly/devices?scanner=" + URLEncoder.encode(name, "UTF-8")) ?: return
        if (d.optBoolean("success") && d.has("known_macs")) logik.setzeBekannt(liste(d.optJSONArray("known_macs")))
        if (d.optBoolean("success") && d.has("known_irks")) logik.setzeIrks(liste(d.optJSONArray("known_irks")))
    }

    /** Zustand an den LoxPanel-Server, fuer die Karte des Geraets im Konfigurator. */
    private fun zustandMelden() {
        http("POST", Visu.basis(this) + "api/geraet/ble", JSONObject().put("scanner", name)
            .put("registriert", bereit).put("scannt", scannt).put("bekannt", logik.anzahlBekannt())
            .put("inReichweite", logik.anzahlOnline()).put("zuletztErkannt", logik.zuletztErkannt).toString())
    }

    // ---- Funk ----

    private val rueckruf = object : ScanCallback() {
        override fun onScanResult(callbackType: Int, r: ScanResult) { verarbeiten(r) }
        override fun onBatchScanResults(results: MutableList<ScanResult>) { results.forEach { verarbeiten(it) } }
        override fun onScanFailed(errorCode: Int) {
            Log.w(TAG, "Scan fehlgeschlagen: $errorCode, neuer Versuch in 30 s")
            scannt = false
            arbeit.schedule({ scanStarten() }, 30, TimeUnit.SECONDS)
        }
    }

    private val uuidBtHome = ParcelUuid.fromString("0000fcd2-0000-1000-8000-00805f9b34fb")
    private val uuidEddystone = ParcelUuid.fromString("0000feaa-0000-1000-8000-00805f9b34fb")

    private fun verarbeiten(r: ScanResult) {
        val rec = r.scanRecord
        val fund = BleLogik.Fund(r.device.address ?: return, r.rssi, rec?.deviceName ?: "",
            rec?.getServiceData(uuidBtHome), rec?.getServiceData(uuidEddystone),
            rec?.getManufacturerSpecificData(0x004C))
        arbeit.execute {
            sicher {
                val e = logik.fund(fund, jetzt())
                e.ereignis?.let { post("/shelly/event", it.put("scanner", name)) }
                if (e.sofortSenden) senden()
            }
        }
    }

    @SuppressLint("MissingPermission")
    private fun scanStarten() {
        if (scannt) return
        val scanner = (getSystemService(Context.BLUETOOTH_SERVICE) as BluetoothManager).adapter?.bluetoothLeScanner
        if (scanner == null) {
            Log.w(TAG, "Bluetooth aus oder nicht da, neuer Versuch in 30 s")
            arbeit.schedule({ scanStarten() }, 30, TimeUnit.SECONDS); return
        }
        try {
            scanner.startScan(null, ScanSettings.Builder().setScanMode(ScanSettings.SCAN_MODE_LOW_LATENCY).build(), rueckruf)
            scannt = true
            Log.i(TAG, "Scan laeuft")
        } catch (e: SecurityException) {
            Log.w(TAG, "Keine Berechtigung fuer Bluetooth-Scan (Standort): ${e.message}")
            arbeit.schedule({ scanStarten() }, 60, TimeUnit.SECONDS)
        }
    }

    @SuppressLint("MissingPermission")
    private fun scanStoppen() {
        try {
            (getSystemService(Context.BLUETOOTH_SERVICE) as BluetoothManager).adapter?.bluetoothLeScanner?.stopScan(rueckruf)
        } catch (_: Exception) { }
        scannt = false
    }

    // ---- HTTP ----

    private fun post(pfad: String, body: JSONObject): JSONObject? {
        body.put("api_key", key)
        return http("POST", "http://$host:$PORT$pfad", body.toString())
    }

    private fun get(pfad: String): JSONObject? =
        http("GET", "http://$host:$PORT$pfad" + (if ('?' in pfad) "&" else "?") + "api_key=" + URLEncoder.encode(key, "UTF-8"), null)

    private fun http(methode: String, adresse: String, body: String?): JSONObject? {
        val con = URL(adresse).openConnection() as HttpURLConnection
        return try {
            con.connectTimeout = 5000; con.readTimeout = 5000; con.requestMethod = methode; con.useCaches = false
            if (body != null) {
                con.doOutput = true
                con.setRequestProperty("Content-Type", "application/json")
                con.outputStream.use { it.write(body.toByteArray(Charsets.UTF_8)) }
            }
            val code = con.responseCode
            val text = (if (code in 200..299) con.inputStream else con.errorStream)
                ?.bufferedReader(Charsets.UTF_8)?.use { it.readText() } ?: return null
            if (code !in 200..299) { Log.w(TAG, "$methode ${adresse.substringBefore('?')} -> $code"); null }
            else JSONObject(text)
        } catch (e: Exception) { null } finally { con.disconnect() }
    }

    private fun liste(a: JSONArray?): List<String> =
        if (a == null) emptyList() else (0 until a.length()).map { a.optString(it) }

    private inline fun sicher(block: () -> Unit) {
        try { block() } catch (e: Exception) { Log.w(TAG, "Fehler: ${e.message}") }
    }

    @Suppress("DEPRECATION")
    private fun eigeneIp(): String {
        val ip = (applicationContext.getSystemService(Context.WIFI_SERVICE) as WifiManager).connectionInfo.ipAddress
        return if (ip == 0) "0.0.0.0" else "${ip and 0xff}.${ip shr 8 and 0xff}.${ip shr 16 and 0xff}.${ip shr 24 and 0xff}"
    }

    private fun notification(): Notification {
        val kanal = "loxpanel-ble"
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            (getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager).createNotificationChannel(
                NotificationChannel(kanal, "BLE Presence", NotificationManager.IMPORTANCE_LOW))
        }
        @Suppress("DEPRECATION")
        val b = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) Notification.Builder(this, kanal) else Notification.Builder(this)
        return b.setContentTitle("BLE Presence").setContentText("Scanner läuft")
            .setSmallIcon(android.R.drawable.stat_sys_data_bluetooth).setOngoing(true).build()
    }
}
