package com.loxpanel.spike

import android.annotation.SuppressLint
import android.annotation.TargetApi
import android.app.Activity
import android.content.pm.PackageManager
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
import android.os.Process
import android.provider.Settings
import android.util.Log
import android.util.TypedValue
import android.view.Gravity
import android.view.MotionEvent
import android.view.View
import android.view.WindowManager
import android.webkit.JavascriptInterface
import android.webkit.RenderProcessGoneDetail
import android.webkit.WebResourceError
import android.webkit.WebResourceRequest
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import android.webkit.WebViewRenderProcess
import android.webkit.WebViewRenderProcessClient
import android.widget.Button
import android.widget.FrameLayout
import android.widget.LinearLayout
import android.widget.TextView
import org.json.JSONObject

/**
 * Eingebauter Kiosk: Vollbild-WebView auf den eingestellten LoxPanel-Server
 * (Visu.basis: der eigene auf dem Gerät oder einer im Netz). Ersetzt Fully
 * Kiosk — die App kontrolliert die Anzeige selbst. Lädt die Panel-URL und lädt
 * bei jedem Fehler (Server noch nicht bereit / neu gestartet) alle 2 s neu;
 * solange steht eine eigene Fehlerseite mit „Server ändern“ über der WebView.
 *
 * Einrichtung: Solange nicht feststeht, wo der Server läuft, zeigt die Anzeige
 * statt der Visu die ServerActivity. Später erreicht man sie mit einem langen
 * Druck (LANGER_DRUCK_MS) auf der Uhr-Seite oder über die Fehlerseite.
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
 *
 * Absturz der Anzeige: Stürzt der Renderer der WebView ab oder beendet Android
 * ihn, baut die Anzeige eine neue WebView auf, statt die App mitzureißen. Hängt
 * er (ab Android 10 gemeldet), beendet sie ihn nach einer halben Minute selbst.
 */
class KioskActivity : Activity(), SensorEventListener {

    private lateinit var web: WebView
    private lateinit var root: FrameLayout
    private lateinit var saver: View
    private lateinit var fehler: View
    private lateinit var fehlerText: TextView
    private val ui = Handler(Looper.getMainLooper())
    private var errored = false
    private var reloadPending = false
    // Basis-Adresse des Servers, für den show() zuletzt geladen hat: Nach
    // „Server ändern“ lädt die Anzeige beim Zurückkommen den neuen.
    private var geladenFuer: String? = null
    // Langer Druck auf der Uhr-Seite öffnet die Einrichtung (Server ändern).
    private val langerDruck = Runnable { einrichtungOeffnen() }
    private val intercom by lazy { IntercomAudio(this, ui) }
    private val intercomCapability = IntercomCapability()
    private var intercomPageCapability: String? = null
    @Volatile private var intercomPage = false
    private var destroyed = false

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
    // Berührung im Schoner: ein Finger weckt, zwei Finger gehen als Geste an die
    // Visu (Gesten im Dunkeln). Das erste Ereignis hält die Anzeige zurück, bis
    // feststeht, ob ein zweiter Finger kommt (SchonerBeruehrung).
    private val beruehrung = SchonerBeruehrung()
    private var gehalten: MotionEvent? = null
    private val fristAb = Runnable { if (beruehrung.frist() == SchonerBeruehrung.Tun.WECKEN) schonerWecken() }

    private val sensorManager by lazy { getSystemService(Context.SENSOR_SERVICE) as? SensorManager }
    // Näherungssensor (falls vorhanden). Am Shelly ist er ein Wake-up-Sensor, den
    // getDefaultSensor() nicht liefert -> zuerst über getSensorList suchen.
    private val proximity: Sensor? by lazy {
        sensorManager?.let {
            it.getSensorList(Sensor.TYPE_PROXIMITY).firstOrNull()
                ?: it.getDefaultSensor(Sensor.TYPE_PROXIMITY)
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        // Bildschirm anlassen: Wir dimmen im Screensaver selbst, damit die App
        // aktiv bleibt und den Näherungssensor auswerten kann (sofortiges Wecken).
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)

        web = neueWebView()

        // Dunkel-Overlay: NUR schwarz (echtes Schwarz beim Backlight-Aus), KEINE
        // eigene Uhr — die Uhr zeigt die Visu. Zunächst versteckt.
        saver = FrameLayout(this).apply {
            setBackgroundColor(Color.BLACK)
            visibility = View.GONE
        }

        fehler = fehlerSeite()

        root = FrameLayout(this)
        root.addView(web, vollbild())
        root.addView(fehler, vollbild())
        root.addView(saver, vollbild())
        setContentView(root)

        wake()
        // Laden erst in onResume: Ohne Einrichtung kommt zuerst die ServerActivity.
    }

    /** Eigene Fehlerseite statt der des Browsers, solange der Server nicht
     *  antwortet: sagt, welcher Server fehlt, und führt zur Einrichtung. */
    private fun fehlerSeite(): View {
        val spalte = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            gravity = Gravity.CENTER
            setBackgroundColor(Color.parseColor("#0b1020"))
            setPadding(dp(24), dp(24), dp(24), dp(24))
            visibility = View.GONE
        }
        fehlerText = TextView(this).apply {
            setTextColor(Color.parseColor("#c9d1e4"))
            setTextSize(TypedValue.COMPLEX_UNIT_SP, 16f)
            gravity = Gravity.CENTER
        }
        spalte.addView(fehlerText)
        spalte.addView(Button(this).apply {
            text = "Server ändern"
            setOnClickListener { einrichtungOeffnen() }
        }, LinearLayout.LayoutParams(
            LinearLayout.LayoutParams.WRAP_CONTENT, LinearLayout.LayoutParams.WRAP_CONTENT
        ).apply { topMargin = dp(16) })
        return spalte
    }

    /** Text der Fehlerseite: Der eigene Server braucht nach einem Update
     *  Minuten, ein Server im Netz fehlt oder ist nicht erreichbar. */
    private fun fehlerZeigen() {
        fehlerText.text = if (Visu.eigenerServer(this)) {
            "Der LoxPanel-Server auf diesem Gerät antwortet noch nicht.\n\n" +
                "Nach dem ersten Start oder einem Update kann das einige Minuten dauern; " +
                "die Anzeige versucht es weiter."
        } else {
            "Der LoxPanel-Server unter ${Visu.server(this)} antwortet nicht.\n\n" +
                "Läuft er, und ist dieses Gerät im selben Netz? Die Anzeige versucht es weiter."
        }
        fehler.visibility = View.VISIBLE
    }

    private fun einrichtungOeffnen() {
        startActivity(Intent(this, ServerActivity::class.java))
    }

    private fun dp(wert: Int): Int =
        TypedValue.applyDimension(TypedValue.COMPLEX_UNIT_DIP, wert.toFloat(), resources.displayMetrics).toInt()

    /** Die WebView der Anzeige mit Einstellungen und JS-Brücke: beim Start und
     *  wenn sie neu aufgebaut wird, weil ihr Renderer beendet ist. */
    @SuppressLint("SetJavaScriptEnabled")
    private fun neueWebView(): WebView {
        val w = WebView(this)
        w.setBackgroundColor(Color.parseColor("#0b1020"))
        w.overScrollMode = View.OVER_SCROLL_NEVER
        w.isVerticalScrollBarEnabled = false
        w.isHorizontalScrollBarEnabled = false

        with(w.settings) {
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

        w.webViewClient = object : WebViewClient() {
            override fun shouldOverrideUrlLoading(v: WebView, r: WebResourceRequest): Boolean = false
            override fun onPageStarted(v: WebView, adresse: String?, favicon: android.graphics.Bitmap?) {
                intercomPage = adresse?.let { Visu.istVisu(Visu.basis(this@KioskActivity), it) } == true
                intercomPageCapability = if (intercomPage) intercomCapability.rotate() else {
                    intercomCapability.clear()
                    null
                }
                intercom.stop()
            }
            override fun onReceivedError(v: WebView, req: WebResourceRequest?, err: WebResourceError?) {
                if (req == null || req.isForMainFrame) {
                    intercomPage = false
                    intercomCapability.clear()
                    intercomPageCapability = null
                    intercom.stop()
                    // Die Seite ist weg, mit ihr ihr Schoner: Berührungen gehören
                    // jetzt der Fehlerseite.
                    visuSaver = false
                    ui.removeCallbacks(goDark)
                    errored = true
                    fehlerZeigen()
                    scheduleReload()
                }
            }
            // Jede geladene Visu-Adresse merken (auch nach einem Ansichtswechsel
            // per ?panel=), damit die App nach einem Neustart dort weitermacht.
            override fun onPageFinished(v: WebView, adresse: String?) {
                Visu.merken(this@KioskActivity, adresse)
                if (!errored) fehler.visibility = View.GONE
                if (v === web && adresse == v.url && adresse?.let { Visu.istVisu(Visu.basis(this@KioskActivity), it) } == true) {
                    intercomBruecke(v)
                }
            }
            // Der Renderer ist abgestürzt oder von Android beendet (Speicher,
            // HaengerWaechter). Ohne diese Behandlung beendet Android die ganze
            // App; so baut sich nur die Anzeige neu auf.
            @TargetApi(Build.VERSION_CODES.O)
            override fun onRenderProcessGone(v: WebView, detail: RenderProcessGoneDetail): Boolean {
                Log.w("LPANZEIGE", if (detail.didCrash()) "Renderer abgestürzt, Anzeige wird neu aufgebaut"
                    else "Renderer beendet, Anzeige wird neu aufgebaut")
                anzeigeNeuAufbauen(v)
                return true
            }
        }
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) w.setWebViewRenderProcessClient(HaengerWaechter())
        // Brücke für die Visu: übergibt die konfigurierte Display-aus-Zeit (dpmsOff
        // aus /config) an den nativen Screensaver.
        val bridge = KioskBridge()
        w.addJavascriptInterface(bridge, "LoxKiosk")
        // Stabile rohe Referenz fuer erneute Seiten-Rueckrufe; die Fassade darf
        // LoxKiosk ersetzen, ohne beim zweiten onPageFinished den Zugang zu verlieren.
        w.addJavascriptInterface(bridge, "LoxKioskNative")
        return w
    }

    /** Ersetzt die WebView, deren Renderer beendet ist, durch eine neue unter dem
     *  Dunkel-Overlay und lädt die Visu nach der Pause von scheduleReload: Stürzt
     *  der neue Renderer gleich wieder ab, baut die Anzeige nicht in einer
     *  Schleife auf. */
    private fun anzeigeNeuAufbauen(alt: WebView) {
        if (alt !== web) return
        intercomPage = false
        intercomCapability.clear()
        intercomPageCapability = null
        intercom.stop()
        root.removeView(alt)
        alt.destroy()
        web = neueWebView()
        root.addView(web, 0, vollbild())
        scheduleReload()
    }

    /** Ab Android 10 meldet die WebView, wenn ihr Renderer nicht reagiert
     *  (Endlosschleife im Skript), frühestens alle 5 s. Nach mehreren Meldungen
     *  in Folge beendet die Anzeige ihn, onRenderProcessGone baut sie neu auf. */
    @TargetApi(Build.VERSION_CODES.Q)
    private class HaengerWaechter : WebViewRenderProcessClient() {
        private var meldungen = 0

        override fun onRenderProcessUnresponsive(view: WebView, renderer: WebViewRenderProcess?) {
            meldungen++
            if (Waechter.rendererBeenden(meldungen)) {
                Log.w("LPANZEIGE", "Renderer reagiert nicht ($meldungen Meldungen), wird beendet")
                renderer?.terminate()
            }
        }

        override fun onRenderProcessResponsive(view: WebView, renderer: WebViewRenderProcess?) {
            meldungen = 0
        }
    }

    private fun vollbild() = FrameLayout.LayoutParams(
        FrameLayout.LayoutParams.MATCH_PARENT, FrameLayout.LayoutParams.MATCH_PARENT)

    /** addJavascriptInterface ist auch in fremden Frames sichtbar. Deshalb
     *  bekommt nur das lokale Hauptdokument eine Fassade mit privatem Zugang;
     *  die rohen Methoden verlangen ihn und verraten ihn niemals. */
    private fun intercomBruecke(v: WebView) {
        val capability = JSONObject.quote(intercomPageCapability ?: return)
        val origin = JSONObject.quote(Visu.basis(this).removeSuffix("/"))
        // Gegensprechen läuft über den Gesprächsdienst des eigenen Servers
        // (IntercomCallClient, Prozess-Token). Mit einem Server im Netz fehlt
        // er, dann bekommt die Visu die Sprechfunktionen nicht und zeigt
        // keine Sprechbedienung (intercomNative() in panel.html).
        val sprechen = Visu.eigenerServer(this)
        v.evaluateJavascript("""
            (function(n, key, sprechen) {
              if (window !== window.top || location.origin !== $origin || location.pathname !== '/') return;
              if (!n || typeof n.startIntercomNative !== 'function') return;
              window.LoxKiosk = {
                setDisplayOff: function(s) { return n.setDisplayOff(s); },
                setSaver: function(on) { return n.setSaver(on); },
                turnScreenOn: function() { return n.turnScreenOn(); },
                turnScreenOff: function() { return n.turnScreenOff(); },
                isScreenOn: function() { return n.isScreenOn(); },
                setDisplayBrightness: function(p) { return n.setDisplayBrightness(p); }
              };
              if (sprechen) {
                window.LoxKiosk.startIntercom = function(uuid) { return n.startIntercomNative(uuid, key); };
                window.LoxKiosk.stopIntercom = function() { return n.stopIntercomNative(key); };
                window.LoxKiosk.intercomStatus = function() { return n.intercomStatusNative(key); };
              }
              window.dispatchEvent(new Event('loxpanel-intercom-ready'));
            })(window.LoxKioskNative, $capability, $sprechen);
        """.trimIndent(), null)
    }

    /** Lädt die Visu des eingestellten Servers: die zuletzt angezeigte
     *  Adresse, sonst das Standardprofil. */
    private fun show() {
        errored = false
        geladenFuer = Visu.basis(this)
        web.loadUrl(Visu.startAdresse(this))
    }

    /** Beim Vorkommen: ohne Einrichtung erst fragen, wo der Server läuft; mit
     *  einem Server im Netz, während der eigene noch läuft, den Prozess neu
     *  starten (Android holt die Anzeige zurück, stateNotNeeded); sonst den
     *  eigenen Server sicherstellen und laden, wenn der Server gewechselt hat
     *  oder die Seite im Fehler steht. */
    private fun serverUndSeite() {
        if (!Visu.eingerichtet(this)) {
            einrichtungOeffnen()
            return
        }
        if (!Visu.eigenerServer(this) && ServerService.serverLaeuft) {
            Log.i("LPANZEIGE", "Server jetzt im Netz (${Visu.server(this)}), App startet neu, damit der eigene Server endet")
            Process.killProcess(Process.myPid())
            return
        }
        ServerService.starten(this)
        if (geladenFuer != Visu.basis(this) || errored) show()
    }

    /** Nach 2 s erneut laden (entprellt, wiederholt sich bei anhaltendem Fehler). */
    private fun scheduleReload() {
        if (reloadPending || destroyed) return
        reloadPending = true
        ui.postDelayed({ reloadPending = false; if (!destroyed) show() }, 2000)
    }

    override fun onResume() {
        super.onResume()
        intercom.onResume()
        enterImmersive()
        // Näherungssensor abonnieren (falls vorhanden) -> weckt aus dem Screensaver.
        // FASTEST für flottes Aufwecken bei Annäherung (Proximity ist on-change +
        // sparsam, daher unkritisch für den Verbrauch).
        proximity?.let { sensorManager?.registerListener(this, it, SensorManager.SENSOR_DELAY_FASTEST) }
        wake()
        serverUndSeite()
    }

    override fun onPause() {
        intercom.onPause()
        super.onPause()
        sensorManager?.unregisterListener(this)
    }

    override fun onStop() {
        intercom.onStop()
        super.onStop()
    }

    override fun onDestroy() {
        destroyed = true
        intercomPage = false
        intercomCapability.clear()
        intercomPageCapability = null
        intercom.destroy()
        ui.removeCallbacksAndMessages(null)
        gehalten?.recycle()
        gehalten = null
        web.removeJavascriptInterface("LoxKiosk")
        web.removeJavascriptInterface("LoxKioskNative")
        web.destroy()
        super.onDestroy()
    }

    override fun onRequestPermissionsResult(requestCode: Int, permissions: Array<out String>, grantResults: IntArray) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        if (requestCode == IntercomAudio.MICROPHONE_REQUEST) {
            intercom.permissionResult(grantResults.firstOrNull() == PackageManager.PERMISSION_GRANTED)
        }
    }

    // Berührung: im Screensaver weckt ein Finger nur (Tap wird geschluckt, löst
    // keine Kachel aus) und holt den 1. Tab; zwei Finger gehen als Geste an die
    // Visu und lassen das Display dunkel. Sonst normal an die Visu weiterreichen.
    override fun dispatchTouchEvent(ev: MotionEvent): Boolean {
        // Im Schoner, solange IRGENDEIN Saver läuft — der native Dunkel-Modus ODER
        // der Visu-Uhr-Saver (visuSaver). So weckt Tippen auch in der Uhr-Phase,
        // in der das Display noch hell ist, auf den 1. Tab (statt nur aus dem
        // Dunkeln). Eine Berührung, die im Schoner begann, endet auch dort, sonst
        // bekäme die Visu Ereignisse ohne Anfang.
        if (saverOn || visuSaver || beruehrung.laeuft) return imSchoner(ev)
        wake()
        return super.dispatchTouchEvent(ev)
    }

    /** Berührung im Schoner nach [SchonerBeruehrung]: Ein Finger weckt nach
     *  WARTE_MS oder beim Loslassen, zwei Finger reichen die ganze Berührung samt
     *  dem zurückgehaltenen ersten Ereignis an die Visu weiter. Ob sie Gesten
     *  erlaubt, entscheidet die Visu; ohne Gesten weckt sie selbst. */
    private fun imSchoner(ev: MotionEvent): Boolean {
        when (ev.actionMasked) {
            MotionEvent.ACTION_DOWN -> {
                gehalten?.recycle()
                gehalten = MotionEvent.obtain(ev)
                beruehrung.runter(ev.eventTime)
                ui.removeCallbacks(fristAb)
                ui.postDelayed(fristAb, SchonerBeruehrung.WARTE_MS)
                // Bleibt der eine Finger liegen, öffnet sich die Einrichtung;
                // das Wecken nach WARTE_MS läuft davon unberührt.
                ui.removeCallbacks(langerDruck)
                ui.postDelayed(langerDruck, LANGER_DRUCK_MS)
            }
            MotionEvent.ACTION_POINTER_DOWN -> {
                ui.removeCallbacks(langerDruck)
                nachTun(beruehrung.weitererFinger(ev.eventTime), ev)
            }
            MotionEvent.ACTION_UP -> {
                ui.removeCallbacks(langerDruck)
                nachTun(beruehrung.hoch(), ev)
            }
            MotionEvent.ACTION_CANCEL -> {
                ui.removeCallbacks(langerDruck)
                nachTun(beruehrung.abbruch(), ev)
            }
            else -> nachTun(beruehrung.weiter(), ev)
        }
        return true
    }

    companion object {
        /** So lange muss ein Finger auf der Uhr-Seite liegen bleiben, bis die
         *  Einrichtung („Wo läuft der Server?“) aufgeht. Deutlich länger als
         *  jedes Tippen zum Wecken, das nach SchonerBeruehrung.WARTE_MS greift. */
        const val LANGER_DRUCK_MS = 3_000L
    }

    private fun nachTun(tun: SchonerBeruehrung.Tun, ev: MotionEvent) {
        when (tun) {
            SchonerBeruehrung.Tun.NACHREICHEN -> {
                ui.removeCallbacks(fristAb)
                val erstes = gehalten
                gehalten = null
                if (erstes != null) {
                    super.dispatchTouchEvent(erstes)
                    erstes.recycle()
                }
                super.dispatchTouchEvent(ev)
            }
            SchonerBeruehrung.Tun.DURCHREICHEN -> super.dispatchTouchEvent(ev)
            SchonerBeruehrung.Tun.WECKEN -> schonerWecken()
            SchonerBeruehrung.Tun.HALTEN, SchonerBeruehrung.Tun.SCHLUCKEN -> Unit
        }
        if (!beruehrung.laeuft) {
            ui.removeCallbacks(fristAb)
            gehalten?.recycle()
            gehalten = null
        }
    }

    /** Ein Finger im Schoner: zurückgehaltenes Ereignis verwerfen, wecken. */
    private fun schonerWecken() {
        ui.removeCallbacks(fristAb)
        gehalten?.recycle()
        gehalten = null
        userWake()
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
        /** Nur die lokale Visu kann eine native Gegensprech-Sitzung beginnen. */
        @JavascriptInterface
        fun startIntercomNative(uuid: String, capability: String?): Boolean =
            intercomPage && intercomCapability.accepts(capability) && intercom.start(uuid) {
                intercomPage && intercomCapability.accepts(capability)
            }

        @JavascriptInterface
        fun stopIntercomNative(capability: String?): Boolean =
            intercomCapability.accepts(capability) && intercom.stop()

        @JavascriptInterface
        fun intercomStatusNative(capability: String?): String =
            if (intercomCapability.accepts(capability)) intercom.status()
            else """{"state":"idle","uuid":"","message":""}"""

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
