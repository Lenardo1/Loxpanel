package com.loxpanel.spike

import android.annotation.SuppressLint
import android.app.Activity
import android.content.Context
import android.content.Intent
import android.content.res.Resources
import android.graphics.Color
import android.hardware.Sensor
import android.hardware.SensorEvent
import android.hardware.SensorEventListener
import android.hardware.SensorManager
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.provider.Settings
import android.view.MotionEvent
import android.view.View
import android.view.WindowManager
import android.webkit.JavascriptInterface
import android.webkit.WebResourceError
import android.webkit.WebResourceRequest
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.FrameLayout

/**
 * Eingebauter Kiosk: Vollbild-WebView auf den lokalen LoxPanel-Server. Ersetzt
 * Fully Kiosk — die App kontrolliert die Anzeige selbst. Lädt die Panel-URL und
 * lädt bei jedem Fehler (Server noch nicht bereit / neu gestartet) alle 2 s neu.
 *
 * Bildschirmschoner: Nach Inaktivität zeigt die App selbst einen schwarzen
 * Screen mit großer Uhr und dimmt das Backlight auf Minimum. Aufwecken per
 * Berührung ODER — falls ein Näherungssensor vorhanden ist (Shelly Wall Display,
 * Sonoff NSPanel Pro) — per Annäherung. Bewusst NICHT über die Firmware/den
 * Geräteadmin, weil deren Annäherungs-Weckung greift nur, wenn der Hersteller-
 * Launcher im Vordergrund ist — hier ist es unsere Visu.
 *
 * Die Visu schaltet den Schoner zusätzlich selbst: Die JS-Brücke LoxKiosk hat
 * dieselben Display-Funktionen wie Fully Kiosk (turnScreenOn/turnScreenOff/
 * isScreenOn). Damit wecken Klingel, Wecker, Notify und Goto das Display, und
 * der Server kann es schalten (Displays-Seite, /api/display).
 *
 * Nachtmodus: Die Visu senkt nachts über setDisplayBrightness die echte
 * Helligkeit des Fensters auf einen Teil der eingestellten Systemhelligkeit,
 * statt eine dunkle Fläche über sich zu legen. Bei automatischer Helligkeit
 * lehnt die App ab, dann dunkelt die Visu wie bisher selbst ab.
 */
class KioskActivity : Activity(), SensorEventListener {

    private lateinit var web: WebView
    private lateinit var root: FrameLayout
    private lateinit var saver: View
    private val ui = Handler(Looper.getMainLooper())
    private var errored = false
    private var reloadPending = false

    // Bildschirmschoner nach Inaktivität. Die Zeit kommt aus /config ("Display aus
    // nach (Sek.)", Feld dpmsOff) über die JS-Brücke LoxKiosk; bis dahin 90 s als
    // Vorgabe. dpmsOff=0 schaltet den Schoner ab.
    private var idleMs = 90_000L
    private var saverEnabled = true
    // Volatile: isScreenOn() liest den Wert im Thread der JS-Brücke.
    @Volatile private var saverOn = false
    // Die Visu meldet über setSaver(), ob ihr eigener Screensaver (Uhr) läuft. Es
    // gibt nur EINEN sichtbaren Screensaver (den der Visu mit Uhr/Wetter/Kalender);
    // nativ wird nur das Backlight gedunkelt (nach idleMs) und auf Annäherung/
    // Berührung geweckt.
    private var visuSaver = false
    // Helligkeit des Fensters außerhalb des Schoners: die Systemhelligkeit oder,
    // im Nachtmodus der Visu, ein Teil davon (setDisplayBrightness).
    private var helligkeit = Helligkeit.SYSTEM
    private val goDark = Runnable { enterScreensaver() }

    private val sensorManager by lazy { getSystemService(Context.SENSOR_SERVICE) as? SensorManager }
    // Näherungssensor (falls vorhanden). Am Shelly ist er ein Wake-up-Sensor, den
    // getDefaultSensor() nicht liefert -> zuerst über getSensorList suchen.
    private val proximity: Sensor? by lazy {
        sensorManager?.let {
            it.getSensorList(Sensor.TYPE_PROXIMITY).firstOrNull()
                ?: it.getDefaultSensor(Sensor.TYPE_PROXIMITY)
        }
    }

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        // Server sicherstellen (idempotent — läuft als Foreground-Service)
        val svc = Intent(this, ServerService::class.java)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) startForegroundService(svc) else startService(svc)

        // Bildschirm anlassen: Wir dimmen im Screensaver selbst, damit die App
        // aktiv bleibt und den Näherungssensor auswerten kann (sofortiges Wecken).
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)

        web = WebView(this)
        web.setBackgroundColor(Color.parseColor("#0b1020"))
        web.overScrollMode = View.OVER_SCROLL_NEVER
        web.isVerticalScrollBarEnabled = false
        web.isHorizontalScrollBarEnabled = false

        with(web.settings) {
            javaScriptEnabled = true
            domStorageEnabled = true
            mediaPlaybackRequiresUserGesture = false   // Wecker-Ton ohne Nutzergeste
            useWideViewPort = true
            loadWithOverviewMode = true
            builtInZoomControls = false
            displayZoomControls = false
            @Suppress("DEPRECATION")
            textZoom = 100
            cacheMode = WebSettings.LOAD_DEFAULT
        }

        web.webViewClient = object : WebViewClient() {
            override fun shouldOverrideUrlLoading(v: WebView, r: WebResourceRequest): Boolean = false
            override fun onReceivedError(v: WebView, req: WebResourceRequest?, err: WebResourceError?) {
                if (req == null || req.isForMainFrame) { errored = true; scheduleReload() }
            }
            // Jede geladene Visu-Adresse merken (auch nach einem Ansichtswechsel
            // per ?panel=), damit die App nach einem Neustart dort weitermacht.
            override fun onPageFinished(v: WebView, adresse: String?) {
                Visu.merken(this@KioskActivity, adresse)
            }
        }
        // Brücke für die Visu: übergibt die konfigurierte Display-aus-Zeit (dpmsOff
        // aus /config) an den nativen Screensaver.
        web.addJavascriptInterface(KioskBridge(), "LoxKiosk")

        // Dunkel-Overlay: NUR schwarz (echtes Schwarz beim Backlight-Aus), KEINE
        // eigene Uhr — die Uhr zeigt die Visu. Zunächst versteckt.
        saver = FrameLayout(this).apply {
            setBackgroundColor(Color.BLACK)
            visibility = View.GONE
        }

        root = FrameLayout(this)
        root.addView(web, FrameLayout.LayoutParams(
            FrameLayout.LayoutParams.MATCH_PARENT, FrameLayout.LayoutParams.MATCH_PARENT))
        root.addView(saver, FrameLayout.LayoutParams(
            FrameLayout.LayoutParams.MATCH_PARENT, FrameLayout.LayoutParams.MATCH_PARENT))
        setContentView(root)

        show()
        wake()
    }

    /** Lädt die Visu: die zuletzt angezeigte Adresse, sonst das Standardprofil. */
    private fun show() { errored = false; web.loadUrl(Visu.startAdresse(this)) }

    /** Nach 2 s erneut laden (entprellt, wiederholt sich bei anhaltendem Fehler). */
    private fun scheduleReload() {
        if (reloadPending) return
        reloadPending = true
        ui.postDelayed({ reloadPending = false; show() }, 2000)
    }

    override fun onResume() {
        super.onResume()
        enterImmersive()
        // Näherungssensor abonnieren (falls vorhanden) -> weckt aus dem Screensaver.
        // FASTEST für flottes Aufwecken bei Annäherung (Proximity ist on-change +
        // sparsam, daher unkritisch für den Verbrauch).
        proximity?.let { sensorManager?.registerListener(this, it, SensorManager.SENSOR_DELAY_FASTEST) }
        wake()
        if (errored) show()   // beim Zurückkommen sicher neu laden, falls Fehlerzustand
    }

    override fun onPause() {
        super.onPause()
        sensorManager?.unregisterListener(this)
    }

    // Berührung: im dunklen Screensaver weckt sie nur (Tap wird geschluckt, löst
    // keine Kachel aus) und holt den 1. Tab; sonst normal an die Visu weiterreichen.
    override fun dispatchTouchEvent(ev: MotionEvent): Boolean {
        // Wecken, solange IRGENDEIN Saver läuft — der native Dunkel-Modus ODER
        // der Visu-Uhr-Saver (visuSaver). So weckt Tippen auch in der Uhr-Phase,
        // in der das Display noch hell ist, auf den 1. Tab (statt nur aus dem
        // Dunkeln). Der Tap wird dabei geschluckt (löst keine Kachel aus).
        if (saverOn || visuSaver) { userWake(); return true }
        wake()
        return super.dispatchTouchEvent(ev)
    }

    // Annäherung weckt aus jedem Saver (nativ dunkel ODER Visu-Uhr) und holt den 1. Tab.
    override fun onSensorChanged(event: SensorEvent) {
        if (event.sensor.type != Sensor.TYPE_PROXIMITY) return
        val near = event.values.isNotEmpty() &&
            event.values[0] < (proximity?.maximumRange ?: 5f)
        if (near && (saverOn || visuSaver)) userWake()
    }

    override fun onAccuracyChanged(sensor: Sensor?, accuracy: Int) { /* egal */ }

    /** Backlight wieder an (Dunkel-Overlay weg). Den Backlight-aus-Timer armt nur
     *  der Visu-Saver (setSaver), nicht jedes Wecken. */
    private fun wake() {
        exitScreensaver()
    }

    /** Aufwecken durch den Nutzer (Berührung/Annäherung) aus dem dunklen Screensaver:
     *  Display an und der Visu sagen, ihre Uhr-Startseite zu schließen -> es steht
     *  der 1. Tab da (den nachRuhe() beim Einschlafen schon gesetzt hat). */
    private fun userWake() {
        wake()
        web.evaluateJavascript("try{ if(typeof wake==='function') wake(); }catch(e){}", null)
    }

    /** Backlight-aus-Timer: dunkelt idleMs nachdem der Visu-Saver angegangen ist.
     *  Nur während der Visu-Saver läuft — sonst greift die App nie von sich aus
     *  ins Display ein. */
    private fun rearmIdle() {
        ui.removeCallbacks(goDark)
        if (saverEnabled && visuSaver && !saverOn) ui.postDelayed(goDark, idleMs)
    }

    /** JS-Brücke der Visu. */
    inner class KioskBridge {
        /** Die konfigurierte Display-aus-Zeit (dpmsOff aus /config). >0 = Backlight
         *  aus so viele Sekunden nach Saver-Start; 0 = nie (Uhr bleibt hell). */
        @JavascriptInterface
        fun setDisplayOff(seconds: Int) {
            ui.post {
                if (seconds > 0) {
                    idleMs = seconds * 1000L
                    saverEnabled = true
                    rearmIdle()
                } else {
                    saverEnabled = false
                    ui.removeCallbacks(goDark)
                    if (saverOn) exitScreensaver()
                }
            }
        }

        /** Die Visu meldet ihren eigenen Screensaver (Uhr) an/aus. Nativ gibt es
         *  dann KEINE zweite Uhr — nur Backlight-aus nach idleMs und Wecken per
         *  Annäherung/Berührung. on=false weckt sofort (Backlight zurück). */
        @JavascriptInterface
        fun setSaver(on: Boolean) {
            ui.post {
                visuSaver = on
                if (on) {
                    rearmIdle()
                } else {
                    ui.removeCallbacks(goDark)
                    if (saverOn) exitScreensaver()
                }
            }
        }

        /** Wie Fully Kiosk: Display einschalten. Die Visu ruft das bei Klingel,
         *  Wecker, Notify und Goto sowie wenn der Server das Display einschaltet.
         *  Nimmt den Schoner weg und startet die Leerlaufzeit neu. */
        @JavascriptInterface
        fun turnScreenOn() {
            ui.post { wake() }
        }

        /** Wie Fully Kiosk: Display ausschalten, also den Schoner zeigen. Die Visu
         *  ruft das, wenn der Server das Display abschaltet. */
        @JavascriptInterface
        fun turnScreenOff() {
            ui.post { enterScreensaver() }
        }

        /** Wie Fully Kiosk: ob das Display gerade an ist (kein Schoner). */
        @JavascriptInterface
        fun isScreenOn(): Boolean = !saverOn

        /** Nachtmodus der Visu: Helligkeit in Prozent der eingestellten
         *  Systemhelligkeit, 100 = unverändert. Gilt nur für dieses Fenster, die
         *  Einstellung des Geräts bleibt. Im Schoner bleibt es dunkel, der Wert
         *  gilt ab dem Aufwecken. false, wenn die App das nicht übernimmt
         *  (automatische Helligkeit am Gerät): dann dunkelt die Visu selbst ab. */
        @JavascriptInterface
        fun setDisplayBrightness(prozent: Int): Boolean {
            val wert = Helligkeit.fensterwert(prozent, systemHelligkeit())
            ui.post {
                helligkeit = wert ?: Helligkeit.SYSTEM
                if (!saverOn) setBrightness(helligkeit)
            }
            return wert != null
        }
    }

    /** Backlight aus: schwarzes Overlay (echtes Schwarz) + Helligkeit 0. KEINE
     *  Uhr — die zeigt die Visu. */
    private fun enterScreensaver() {
        if (saverOn) return
        saverOn = true
        saver.visibility = View.VISIBLE
        saver.bringToFront()
        setBrightness(0f)      // praktisch dunkel (LCD -> kein Einbrennen)
    }

    /** Backlight zurück (Systemhelligkeit oder Nachtmodus), Overlay weg. */
    private fun exitScreensaver() {
        if (saverOn) {
            saverOn = false
            saver.visibility = View.GONE
        }
        setBrightness(helligkeit)
    }

    private fun setBrightness(b: Float) {
        val lp = window.attributes
        lp.screenBrightness = b
        window.attributes = lp
    }

    /** Eingestellte Systemhelligkeit als Anteil 0..1, null bei automatischer
     *  Helligkeit (dann ist die tatsächliche Helligkeit unbekannt). Lesen
     *  braucht keine Berechtigung. */
    private fun systemHelligkeit(): Float? = try {
        val cr = contentResolver
        if (Settings.System.getInt(cr, Settings.System.SCREEN_BRIGHTNESS_MODE) ==
            Settings.System.SCREEN_BRIGHTNESS_MODE_AUTOMATIC
        ) null
        else Helligkeit.anteil(Settings.System.getInt(cr, Settings.System.SCREEN_BRIGHTNESS), helligkeitMax())
    } catch (e: Settings.SettingNotFoundException) {
        null
    }

    /** Höchstwert der Helligkeitseinstellung des Geräts (AOSP: 255). */
    @SuppressLint("DiscouragedApi")
    private fun helligkeitMax(): Int {
        val res = Resources.getSystem()
        val id = res.getIdentifier("config_screenBrightnessSettingMaximum", "integer", "android")
        return try {
            if (id != 0) res.getInteger(id) else Helligkeit.MAX_STANDARD
        } catch (e: Resources.NotFoundException) {
            Helligkeit.MAX_STANDARD
        }
    }

    @Suppress("DEPRECATION")
    private fun enterImmersive() {
        window.decorView.systemUiVisibility = (
            View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY
                or View.SYSTEM_UI_FLAG_FULLSCREEN
                or View.SYSTEM_UI_FLAG_HIDE_NAVIGATION
                or View.SYSTEM_UI_FLAG_LAYOUT_STABLE
                or View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN
                or View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION)
    }

    // Kiosk: Zurück-Taste ignorieren, damit man die Anzeige nicht verlässt.
    @Suppress("OVERRIDE_DEPRECATION")
    override fun onBackPressed() { /* bewusst leer */ }
}
