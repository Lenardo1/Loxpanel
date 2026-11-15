package com.loxpanel.spike

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.content.Context
import android.content.Intent
import android.graphics.Color
import android.graphics.PixelFormat
import android.graphics.drawable.GradientDrawable
import android.os.Build
import android.os.Handler
import android.os.IBinder
import android.os.Looper
import android.provider.Settings
import android.util.Log
import android.util.TypedValue
import android.view.Gravity
import android.view.WindowManager
import android.widget.LinearLayout
import android.widget.TextView
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.util.concurrent.Executors
import java.util.concurrent.TimeUnit

/**
 * Wetter-Einblendung über einer fremden App (eigene Version, Marco): auf dem Tablet
 * mit Loxone-App ein kleines Fenster mit aktuellem Wetter, das über der App schwebt.
 * Berührungen gehen hindurch (FLAG_NOT_TOUCHABLE), die App bleibt bedienbar.
 * Daten von Open-Meteo (wie der LoxPanel-Server als Ersatzquelle), alle 10 min.
 *
 * Einstellen nur per adb über den StartApp-Empfänger:
 *   --es wetter "<breite> <länge>"  (Standort, z. B. der des Miniservers; aus: "")
 *   --ei wetterX <px> --ei wetterY <px>   (Abstand von oben links, Standard 300/12)
 * Braucht SYSTEM_ALERT_WINDOW (appops set … SYSTEM_ALERT_WINDOW allow).
 */
class WetterOverlay : Service() {

    companion object {
        private const val TAG = "LPWETTER"
        private const val PREFS = "wetter"

        fun an(ctx: Context): Boolean = ort(ctx) != null

        private fun ort(ctx: Context): Pair<Double, Double>? {
            val t = ctx.getSharedPreferences(PREFS, Context.MODE_PRIVATE).getString("ort", "") ?: ""
            val z = t.trim().split(Regex("[\\s,;]+")).mapNotNull { it.toDoubleOrNull() }
            return if (z.size == 2) z[0] to z[1] else null
        }

        /** Einstellung aus dem adb-Broadcast übernehmen und Dienst passend starten/beenden. */
        fun setzen(ctx: Context, intent: Intent) {
            val e = ctx.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit()
            intent.getStringExtra("wetter")?.let { e.putString("ort", it.trim()) }
            if (intent.hasExtra("wetterX")) e.putInt("x", intent.getIntExtra("wetterX", 300))
            if (intent.hasExtra("wetterY")) e.putInt("y", intent.getIntExtra("wetterY", 12))
            e.apply()
            ctx.stopService(Intent(ctx, WetterOverlay::class.java))
            if (an(ctx)) starten(ctx)
            Log.i(TAG, if (an(ctx)) "Wetter-Einblendung an" else "Wetter-Einblendung aus")
        }

        fun starten(ctx: Context) {
            if (!an(ctx)) return
            try {
                val i = Intent(ctx, WetterOverlay::class.java)
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) ctx.startForegroundService(i) else ctx.startService(i)
            } catch (e: Exception) { Log.w(TAG, "Start fehlgeschlagen: ${e.message}") }
        }
    }

    private val haupt = Handler(Looper.getMainLooper())
    private val arbeit = Executors.newSingleThreadScheduledExecutor { r -> Thread(r, "loxpanel-wetter").apply { isDaemon = true } }
    private var fenster: LinearLayout? = null
    private var gross: TextView? = null
    private var klein: TextView? = null

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        startForeground(4, notification())
        val o = ort(this)
        if (o == null) { stopSelf(); return START_NOT_STICKY }
        if (fenster == null) {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M && !Settings.canDrawOverlays(this)) {
                Log.w(TAG, "Keine Erlaubnis für Einblendungen (SYSTEM_ALERT_WINDOW)"); stopSelf(); return START_NOT_STICKY
            }
            zeigen()
            arbeit.scheduleWithFixedDelay({ holen(o.first, o.second) }, 0, 10, TimeUnit.MINUTES)
        }
        return START_STICKY
    }

    override fun onDestroy() {
        arbeit.shutdownNow()
        fenster?.let { try { (getSystemService(WINDOW_SERVICE) as WindowManager).removeView(it) } catch (_: Exception) {} }
        fenster = null
        super.onDestroy()
    }

    private fun dp(v: Float) = TypedValue.applyDimension(TypedValue.COMPLEX_UNIT_DIP, v, resources.displayMetrics)

    private fun zeigen() {
        val p = getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        gross = TextView(this).apply {
            setTextColor(Color.WHITE); setTextSize(TypedValue.COMPLEX_UNIT_SP, 22f); text = "…"
        }
        klein = TextView(this).apply {
            setTextColor(Color.argb(200, 255, 255, 255)); setTextSize(TypedValue.COMPLEX_UNIT_SP, 13f)
            setPadding(dp(10f).toInt(), 0, 0, 0)
        }
        val v = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
            val r = dp(14f)
            background = GradientDrawable().apply { setColor(Color.argb(170, 30, 30, 30)); cornerRadius = r }
            setPadding(dp(14f).toInt(), dp(6f).toInt(), dp(14f).toInt(), dp(6f).toInt())
            addView(gross); addView(klein)
        }
        val typ = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O)
            WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY
        else @Suppress("DEPRECATION") WindowManager.LayoutParams.TYPE_PHONE
        val lp = WindowManager.LayoutParams(
            WindowManager.LayoutParams.WRAP_CONTENT, WindowManager.LayoutParams.WRAP_CONTENT, typ,
            WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE or WindowManager.LayoutParams.FLAG_NOT_TOUCHABLE or
                WindowManager.LayoutParams.FLAG_LAYOUT_IN_SCREEN,
            PixelFormat.TRANSLUCENT
        ).apply {
            gravity = Gravity.TOP or Gravity.START
            x = p.getInt("x", 300); y = p.getInt("y", 12)
        }
        (getSystemService(WINDOW_SERVICE) as WindowManager).addView(v, lp)
        fenster = v
        Log.i(TAG, "Einblendung gezeigt bei ${lp.x}/${lp.y}")
    }

    private fun holen(breite: Double, laenge: Double) {
        val adresse = "https://api.open-meteo.com/v1/forecast?latitude=$breite&longitude=$laenge" +
            "&current=temperature_2m,weather_code,is_day&daily=temperature_2m_max,temperature_2m_min" +
            "&timezone=auto&forecast_days=1"
        try {
            val con = URL(adresse).openConnection() as HttpURLConnection
            con.connectTimeout = 10000; con.readTimeout = 10000
            val text = try { con.inputStream.bufferedReader().use { it.readText() } } finally { con.disconnect() }
            val j = JSONObject(text)
            val c = j.getJSONObject("current"); val d = j.getJSONObject("daily")
            val (symbol, art) = WetterText.art(c.optInt("weather_code", -1), c.optInt("is_day", 1) == 1)
            val oben = "$symbol ${WetterText.grad(c.getDouble("temperature_2m"))}"
            val unten = listOf(art, "${WetterText.ganz(d.getJSONArray("temperature_2m_max").getDouble(0))} / " +
                WetterText.ganz(d.getJSONArray("temperature_2m_min").getDouble(0))).filter { it.isNotEmpty() }.joinToString(" · ")
            haupt.post { gross?.text = oben; klein?.text = unten }
        } catch (e: Exception) {
            Log.w(TAG, "Wetter nicht geholt: ${e.message}")
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
