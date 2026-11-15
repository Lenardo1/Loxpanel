package com.loxpanel.spike

import android.annotation.SuppressLint
import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.content.Context
import android.content.Intent
import android.graphics.Color
import android.graphics.PixelFormat
import android.os.Build
import android.os.Handler
import android.os.IBinder
import android.os.Looper
import android.provider.Settings
import android.util.Log
import android.view.Gravity
import android.view.WindowManager
import android.webkit.JavascriptInterface
import android.webkit.WebView
import org.json.JSONArray
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.util.concurrent.Executors
import java.util.concurrent.TimeUnit

/**
 * Wetter-Einblendung über einer fremden App (eigene Version, Marco): auf dem Tablet
 * mit Loxone-App ein Feld in der Kopfzeile (deckt dort den Miniserver-Namen ab, im
 * Schwarz der Loxone-Kopfzeile). Antippen öffnet die Vorhersage für heute und die
 * nächsten drei Tage, erneut antippen oder nach 20 s schließt sie.
 *
 * Daten: Plugin Weather4Lox auf dem LoxBerry (current.json, dailyforecast.json, alle
 * 10 min). Symbole: die Loxone-Wettersymbole vom Miniserver
 * (resources/Images/new/aurora/weather-NN[-d|-n].svg, NN = Loxone-Wettercode - 1),
 * werden nur geladen, nicht mitgeliefert; fehlen sie, bleibt das Feld ohne Symbol.
 *
 * Mit dem Bedienungshilfe-Dienst LoxSicht blendet es sich aus, solange in der
 * Loxone-App das Menü, eine Detailansicht oder der Ambientmodus zu sehen ist.
 *
 * Einstellen nur per adb über den StartApp-Empfänger:
 *   --es wetter "http://<loxberry>/plugins/weather4lox/"   (aus: "")
 *   --es wetterIcons "http://<miniserver>/"
 *   --ei wetterX <px> --ei wetterY <px> --ei wetterB <px> --ei wetterH <px>  (Lage/Größe des Feldes)
 * Braucht SYSTEM_ALERT_WINDOW (appops set … SYSTEM_ALERT_WINDOW allow).
 */
class WetterOverlay : Service() {

    companion object {
        private const val TAG = "LPWETTER"
        private const val PREFS = "wetter"

        fun an(ctx: Context): Boolean = w4l(ctx) != null

        private fun p(ctx: Context) = ctx.getSharedPreferences(PREFS, Context.MODE_PRIVATE)

        /** Basisadresse von Weather4Lox. */
        private fun w4l(ctx: Context): String? = mitSchraegstrich(p(ctx).getString("ort", ""))

        private fun icons(ctx: Context): String? = mitSchraegstrich(p(ctx).getString("icons", ""))

        private fun mitSchraegstrich(v: String?): String? =
            v?.trim()?.takeIf { it.startsWith("http") }?.let { if (it.endsWith("/")) it else "$it/" }

        /** Einstellung aus dem adb-Broadcast übernehmen und Dienst neu starten. */
        fun setzen(ctx: Context, intent: Intent) {
            val e = p(ctx).edit()
            intent.getStringExtra("wetter")?.let { e.putString("ort", it.trim()) }
            intent.getStringExtra("wetterIcons")?.let { e.putString("icons", it.trim()) }
            for (k in listOf("wetterX", "wetterY", "wetterB", "wetterH"))
                if (intent.hasExtra(k)) e.putInt(k, intent.getIntExtra(k, 0))
            e.apply()
            ctx.stopService(Intent(ctx, WetterOverlay::class.java))
            if (an(ctx)) starten(ctx)
            Log.i(TAG, if (an(ctx)) "Wetter-Einblendung an" else "Wetter-Einblendung aus")
        }

        @Volatile private var instanz: WetterOverlay? = null
        @Volatile private var zuletztSichtbar = true

        /** Von LoxSicht: passt die Einblendung gerade (Startansicht, Menü zu)? */
        fun sichtbar(v: Boolean) {
            if (v == zuletztSichtbar) return
            zuletztSichtbar = v
            instanz?.let { o -> o.haupt.post { o.anzeigen(v) } }
        }

        fun starten(ctx: Context) {
            if (!an(ctx)) return
            try {
                val i = Intent(ctx, WetterOverlay::class.java)
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) ctx.startForegroundService(i) else ctx.startService(i)
            } catch (e: Exception) { Log.w(TAG, "Start fehlgeschlagen: ${e.message}") }
        }
    }

    val haupt = Handler(Looper.getMainLooper())
    private val arbeit = Executors.newSingleThreadScheduledExecutor { r -> Thread(r, "loxpanel-wetter").apply { isDaemon = true } }
    private var web: WebView? = null
    private var lp: WindowManager.LayoutParams? = null
    private var offen = false
    @Volatile private var anzahlTage = 4
    @Volatile private var geladen = false
    @Volatile private var letzteDaten: String? = null
    private var kompaktBreite = 0   // gemessene Breite des Feldes (px), 0 = noch nicht gemessen
    private val symbole = HashMap<String, String>()   // Dateiname -> SVG (eingefärbt)
    private val schliessen = Runnable { umschalten(false) }

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        startForeground(4, notification())
        val basis = w4l(this)
        if (basis == null) { stopSelf(); return START_NOT_STICKY }
        if (web == null) {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M && !Settings.canDrawOverlays(this)) {
                Log.w(TAG, "Keine Erlaubnis für Einblendungen (SYSTEM_ALERT_WINDOW)"); stopSelf(); return START_NOT_STICKY
            }
            zeigen()
            arbeit.scheduleWithFixedDelay({ holen(basis) }, 0, 10, TimeUnit.MINUTES)
        }
        return START_STICKY
    }

    override fun onDestroy() {
        arbeit.shutdownNow()
        haupt.removeCallbacks(schliessen)
        web?.let { try { (getSystemService(WINDOW_SERVICE) as WindowManager).removeView(it) } catch (_: Exception) {}; it.destroy() }
        web = null
        if (instanz === this) instanz = null
        super.onDestroy()
    }

    private fun groesse(offen: Boolean) {
        val l = lp ?: return
        val pr = p(this)
        val dm = resources.displayMetrics
        if (offen) {
            // Breite nach Zahl der Tage (Weather4Lox liefert je nach Dienst 3 oder mehr)
            l.width = ((40 + anzahlTage.coerceIn(2, 4) * 190) * dm.density).toInt().coerceAtMost(dm.widthPixels - l.x)
            l.height = (300 * dm.density).toInt()
        } else {
            l.width = pr.getInt("wetterB", if (kompaktBreite > 0) kompaktBreite else (430 * dm.density).toInt())
            l.height = pr.getInt("wetterH", (64 * dm.density).toInt())
        }
    }

    @SuppressLint("SetJavaScriptEnabled")
    private fun zeigen() {
        val pr = p(this)
        val w = WebView(this).apply {
            setBackgroundColor(Color.rgb(14, 14, 14))
            settings.javaScriptEnabled = true
            isVerticalScrollBarEnabled = false; isHorizontalScrollBarEnabled = false
            addJavascriptInterface(Bruecke(), "LoxWetter")
            // Daten, die vor dem Laden der Seite kamen, danach nachreichen
            webViewClient = object : android.webkit.WebViewClient() {
                override fun onPageFinished(view: WebView?, url: String?) {
                    geladen = true
                    letzteDaten?.let { d -> view?.evaluateJavascript("zeigen($d)", null) }
                }
            }
            loadUrl("file:///android_asset/wetter/wetter.html")
            // Berührung außerhalb des Feldes (ohne Lage, die gibt Android nicht heraus): LoxSicht
            // sieht sofort nach, ob das Loxone-Menü aufgeht.
            setOnTouchListener { _, ev ->
                if (ev.actionMasked == android.view.MotionEvent.ACTION_OUTSIDE) LoxSicht.schnell()
                false
            }
        }
        val typ = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O)
            WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY
        else @Suppress("DEPRECATION") WindowManager.LayoutParams.TYPE_PHONE
        // Nur das eigene Feld nimmt Berührungen an (NOT_TOUCH_MODAL), alles daneben geht an die App.
        lp = WindowManager.LayoutParams(0, 0, typ,
            WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE or WindowManager.LayoutParams.FLAG_NOT_TOUCH_MODAL or
                WindowManager.LayoutParams.FLAG_LAYOUT_IN_SCREEN or WindowManager.LayoutParams.FLAG_WATCH_OUTSIDE_TOUCH,
            PixelFormat.OPAQUE
        ).apply {
            gravity = Gravity.TOP or Gravity.START
            x = pr.getInt("wetterX", (50 * resources.displayMetrics.density).toInt())
            y = pr.getInt("wetterY", 0)
        }
        groesse(false)
        (getSystemService(WINDOW_SERVICE) as WindowManager).addView(w, lp)
        web = w
        instanz = this
        if (!zuletztSichtbar) anzeigen(false)
        Log.i(TAG, "Einblendung gezeigt bei ${lp?.x}/${lp?.y}")
    }

    private fun umschalten(auf: Boolean) {
        val w = web ?: return
        offen = auf
        groesse(auf)
        try { (getSystemService(WINDOW_SERVICE) as WindowManager).updateViewLayout(w, lp) } catch (_: Exception) {}
        w.evaluateJavascript("offen($auf)", null)
        haupt.removeCallbacks(schliessen)
        if (auf) haupt.postDelayed(schliessen, 20000)
    }

    inner class Bruecke {
        @JavascriptInterface fun umschalten() { haupt.post { umschalten(!offen) } }
        /** Breite des kleinen Feldes in CSS-Pixeln (= dp), gemessen nach jedem Neuzeichnen. */
        @JavascriptInterface fun breite(css: Int) {
            haupt.post {
                val px = ((css + 4) * resources.displayMetrics.density).toInt()
                if (px != kompaktBreite && px > 0) {
                    kompaktBreite = px
                    if (!offen && web?.visibility == android.view.View.VISIBLE) { groesse(false); web?.let { w -> try { (getSystemService(WINDOW_SERVICE) as WindowManager).updateViewLayout(w, lp) } catch (_: Exception) {} } }
                }
            }
        }
    }

    /** Ein-/Ausblenden (LoxSicht). Ausgeblendet nimmt das Feld keine Berührungen an. */
    fun anzeigen(v: Boolean) {
        val w = web ?: return; val l = lp ?: return
        if (!v && offen) umschalten(false)
        w.visibility = if (v) android.view.View.VISIBLE else android.view.View.INVISIBLE
        // Ausgeblendet auf 1×1 px schrumpfen (statt NOT_TOUCHABLE): so meldet Android weiter jede
        // Berührung draußen, und LoxSicht merkt sofort, wenn das Menü wieder zugeht.
        if (v) groesse(offen) else { l.width = 1; l.height = 1 }
        try { (getSystemService(WINDOW_SERVICE) as WindowManager).updateViewLayout(w, l) } catch (_: Exception) {}
    }

    // ---- Daten ----

    private fun text(adresse: String): String {
        val con = URL(adresse).openConnection() as HttpURLConnection
        con.connectTimeout = 10000; con.readTimeout = 10000
        return try { con.inputStream.bufferedReader().use { it.readText() } } finally { con.disconnect() }
    }

    /** Loxone-Symbol laden (einmal je Datei) und auf currentColor umfärben. */
    private fun symbol(datei: String): String? {
        symbole[datei]?.let { return it }
        val basis = icons(this) ?: return null
        return try {
            val svg = text(basis + "resources/Images/new/aurora/" + datei)
                .replace(Regex("(stroke|fill)=\"#(?:[0-9a-fA-F]{3}){1,2}\"")) { "${it.groupValues[1]}=\"currentColor\"" }
            symbole[datei] = svg; svg
        } catch (e: Exception) { Log.w(TAG, "Symbol $datei: ${e.message}"); null }
    }

    private fun holen(basis: String) {
        try {
            val c = JSONObject(text(basis + "current.json")).getJSONObject("current")
            val tage = try { JSONObject(text(basis + "dailyforecast.json")).getJSONArray("dailyforecast") } catch (_: Exception) { JSONArray() }
            val code = c.optJSONObject("weatherCode")
            val nacht = WetterText.istNacht(c.optString("sunrise"), c.optString("sunset"), java.util.Calendar.getInstance())
            val iconsJ = JSONObject()
            fun ico(lox: Int?, n: Boolean): String {
                val d = WetterText.loxoneSymbol(lox, n) ?: return ""
                symbol(d)?.let { iconsJ.put(d, it) }
                return d
            }
            val heute = tage.optJSONObject(0)
            val mm = heute?.let { WetterText.maxMin(it) } ?: ""
            val cur = JSONObject()
                .put("t", WetterText.grad(c.getJSONObject("temperature").getDouble("air")))
                .put("desc", code?.optString("description")?.takeIf { it != "null" } ?: "")
                .put("mm", mm)
                .put("icon", ico(WetterText.zahl(code?.opt("loxone")), nacht))
                .put("extra", listOf(mm.takeIf { it.isNotEmpty() }?.let { "Heute $it" },
                    c.optJSONObject("wind")?.let { w -> w.optDouble("speed").takeIf { !it.isNaN() }?.let { "Wind ${Math.round(it * 3.6)} km/h" } },
                    c.optInt("humidity", -1).takeIf { it >= 0 }?.let { "Luftfeuchte $it %" }).filterNotNull().joinToString(" · "))
            val days = JSONArray()
            for (i in 0 until minOf(4, tage.length())) {
                val t = tage.getJSONObject(i)
                val tc = t.optJSONObject("weatherCode")
                val temp = t.optJSONObject("temperature")
                days.put(JSONObject()
                    .put("name", WetterText.tagName(i, t.optJSONObject("time")?.optLong("epoch") ?: 0L))
                    .put("icon", ico(WetterText.zahl(tc?.opt("loxone")), false))
                    .put("max", temp?.optJSONObject("max")?.optDouble("air")?.takeIf { !it.isNaN() }?.let { WetterText.ganz(it) } ?: "")
                    .put("min", temp?.optJSONObject("min")?.optDouble("air")?.takeIf { !it.isNaN() }?.let { WetterText.ganz(it) } ?: "")
                    .put("desc", tc?.optString("description")?.takeIf { it != "null" } ?: "")
                    .put("pop", t.optJSONObject("precipitation")?.opt("probability")?.let { WetterText.zahl(it) } ?: JSONObject.NULL))
            }
            anzahlTage = days.length()
            val daten = JSONObject().put("cur", cur).put("days", days).put("icons", iconsJ)
            val text = daten.toString()
            letzteDaten = text
            haupt.post { if (geladen) web?.evaluateJavascript("zeigen($text)", null) }
        } catch (e: Exception) {
            Log.w(TAG, "Weather4Lox nicht geholt: ${e.message}")
        }
    }

    private fun notification(): Notification {
        val kanal = "loxpanel-wetter"
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            (getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager).createNotificationChannel(
                NotificationChannel(kanal, "Wetter-Einblendung", NotificationManager.IMPORTANCE_MIN))
        }
        val b = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) Notification.Builder(this, kanal)
        else @Suppress("DEPRECATION") Notification.Builder(this)
        return b.setSmallIcon(android.R.drawable.ic_menu_day).setContentTitle("Wetter-Einblendung").setOngoing(true).build()
    }
}
