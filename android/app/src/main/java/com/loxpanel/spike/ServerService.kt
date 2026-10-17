package com.loxpanel.spike

import android.annotation.SuppressLint
import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.content.Context
import android.content.Intent
import android.os.Build
import android.os.IBinder
import android.os.Process
import android.os.SystemClock
import android.util.Log
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import java.io.File
import java.io.IOException
import java.net.HttpURLConnection
import java.net.URL
import java.util.concurrent.Executors
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicBoolean

/**
 * Foreground-Service, der den eingebetteten LoxPanel-Server (webvisu.py) startet
 * und am Leben hält. Der echte LoxPanel-Code liegt in den App-Assets und wird
 * beim ersten Start nach filesDir/loxpanel kopiert, dann aus Python importiert.
 *
 * Wächter: Der Dienst fragt den Server in festem Abstand nach /api/health.
 * Antwortet er nicht mehr (Server-Thread beendet, Ereignisschleife hängt) oder
 * meldet er eine beendete Hintergrund-Aufgabe, beendet der Dienst den Prozess
 * der App. Android startet ihn neu: den Dienst, weil er START_STICKY ist, die
 * Anzeige, wenn sie vorn war (stateNotNeeded im Manifest). Wann und wie oft,
 * regelt [Waechter].
 */
class ServerService : Service() {

    companion object {
        /** Server und Wächter laufen je Prozess einmal. Anzeige, BootReceiver
         *  und der Neustart durch Android starten den Dienst, jeder Start ruft
         *  onStartCommand. */
        private val gestartet = AtomicBoolean(false)

        /** Einstellungen des Wächters: die Zeitpunkte seiner Neustarts für die
         *  Bremse. Sie müssen den Neustart überdauern. */
        private const val WAECHTER = "waechter"
        private const val NEUSTARTS = "neustarts"
    }

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        startForeground(1, buildNotification())
        // Die Anzeige startet der BootReceiver bzw. der Nutzer (KioskActivity);
        // der Dienst kümmert sich nur um den Server.
        if (!gestartet.compareAndSet(false, true)) return START_STICKY
        val start = SystemClock.elapsedRealtime()
        waechterStarten(start)
        Thread {
            try {
                val appDir = File(filesDir, "loxpanel")
                deployAssets(appDir)

                if (!Python.isStarted()) {
                    Python.start(AndroidPlatform(this))
                }
                val res = Python.getInstance().getModule("boot")
                    .callAttr("start_bg", appDir.absolutePath, Visu.PORT, IntercomNative.token)
                Log.i("LPSERVER", "boot.start_bg -> $res")
            } catch (e: Throwable) {
                Log.e("LPSERVER", "Serverstart fehlgeschlagen", e)
            }
        }.start()

        return START_STICKY
    }

    /** Prüft den Server ab [start] (elapsedRealtime) in festem Abstand und
     *  startet die App neu, wenn er gestört ist. */
    private fun waechterStarten(start: Long) {
        val ctx = applicationContext
        val stand = Waechter.Stand(start)
        var gebremst = false
        Executors.newSingleThreadScheduledExecutor { r -> Thread(r, "loxpanel-waechter").apply { isDaemon = true } }
            .scheduleWithFixedDelay({
                // Ein Fehler darf den Wächter nicht beenden: Der Executor führte
                // die Prüfung danach nie wieder aus.
                try {
                    val gesund = gesund()
                    if (gesund && !stand.warGesund) {
                        Log.i("LPSERVER", "Wächter: Server antwortet, ${(SystemClock.elapsedRealtime() - start) / 1000} s nach dem Start")
                    }
                    if (gesund) gebremst = false
                    if (stand.pruefung(gesund, SystemClock.elapsedRealtime()) && !neuStarten(ctx) && !gebremst) {
                        gebremst = true
                        Log.w("LPSERVER", "Wächter: Server gestört, die Bremse lässt keinen Neustart zu " +
                            "(höchstens ${Waechter.NEUSTARTS_HOECHSTENS} in ${Waechter.BREMSE_MS / 60_000} min)")
                    }
                } catch (e: Throwable) {
                    Log.e("LPSERVER", "Wächter: Prüfung fehlgeschlagen", e)
                }
            }, Waechter.PRUEF_ABSTAND_MS, Waechter.PRUEF_ABSTAND_MS, TimeUnit.MILLISECONDS)
    }

    /** Ob der Server antwortet und alle seine Hintergrund-Aufgaben laufen:
     *  /api/health meldet dann 200, sonst 503. */
    private fun gesund(): Boolean {
        val con = URL(Visu.BASIS + "api/health").openConnection() as HttpURLConnection
        return try {
            con.connectTimeout = Waechter.VERBINDEN_MS
            con.readTimeout = Waechter.ANTWORT_MS
            con.useCaches = false
            val code = con.responseCode
            if (code != HttpURLConnection.HTTP_OK) Log.w("LPSERVER", "Wächter: /api/health meldet $code")
            code == HttpURLConnection.HTTP_OK
        } catch (e: IOException) {
            Log.w("LPSERVER", "Wächter: Server antwortet nicht ($e)")
            false
        } finally {
            con.disconnect()
        }
    }

    /** Beendet den Prozess der App, damit Android Server und Anzeige frisch
     *  startet. false, wenn die Bremse das nicht erlaubt. */
    @SuppressLint("ApplySharedPref")
    private fun neuStarten(ctx: Context): Boolean {
        val prefs = ctx.getSharedPreferences(WAECHTER, Context.MODE_PRIVATE)
        val jetzt = System.currentTimeMillis()
        val bisher = Waechter.zaehlende(Waechter.ausText(prefs.getString(NEUSTARTS, null)), jetzt)
        if (!Waechter.neustartErlaubt(bisher, jetzt)) return false
        // commit statt apply: Der Prozess endet gleich, der Eintrag muss vorher stehen.
        prefs.edit().putString(NEUSTARTS, Waechter.alsText(bisher + jetzt)).commit()
        Log.w("LPSERVER", "Wächter: Server gestört, App startet neu")
        Process.killProcess(Process.myPid())
        return true
    }

    /**
     * Kopiert den LoxPanel-Code aus den Assets nach filesDir/loxpanel.
     * bin/ und webfrontend/ werden bei jedem Start aufgefrischt (Code-Update),
     * config/ nur beim ersten Mal — damit über /settings gespeicherte Änderungen
     * (Miniserver-Zugang etc.) erhalten bleiben.
     */
    private fun deployAssets(appDir: File) {
        appDir.mkdirs()
        // Nur bei App-Update neu ausrollen: Stempel = Installationszeit der App.
        // Normale Reboots ueberspringen das Kopieren -> schneller Start.
        val stamp = File(appDir, ".assets_version")
        val current = try {
            packageManager.getPackageInfo(packageName, 0).lastUpdateTime.toString()
        } catch (e: Exception) { "" }
        val previous = try { if (stamp.exists()) stamp.readText().trim() else "" } catch (e: Exception) { "" }

        if (current != previous || !File(appDir, "bin/webvisu.py").exists()) {
            copyAsset("loxpanel/bin", File(appDir, "bin"))
            copyAsset("loxpanel/webfrontend", File(appDir, "webfrontend"))
            copyAsset("loxpanel/deploy", File(appDir, "deploy"))
            try { stamp.writeText(current) } catch (e: Exception) {}
            Log.i("LPSERVER", "Assets neu ausgerollt (App-Update) unter ${appDir.absolutePath}")
        } else {
            Log.i("LPSERVER", "Assets aktuell - kein Neukopieren (schneller Start)")
        }

        // config nur beim ersten Mal (ueber /settings gespeicherte Zugangsdaten bleiben)
        val cfg = File(appDir, "config")
        if (!cfg.exists()) {
            copyAsset("loxpanel/config", cfg)
        }
    }

    private fun copyAsset(path: String, out: File) {
        val list = try { assets.list(path) } catch (e: Exception) { null }
        if (list == null || list.isEmpty()) {
            // Datei (oder leeres Verzeichnis)
            out.parentFile?.mkdirs()
            try {
                assets.open(path).use { input ->
                    out.outputStream().use { output -> input.copyTo(output) }
                }
            } catch (e: Exception) {
                // war ein (leeres) Verzeichnis — ignorieren
            }
        } else {
            out.mkdirs()
            for (name in list) {
                copyAsset("$path/$name", File(out, name))
            }
        }
    }

    private fun buildNotification(): Notification {
        val channelId = "loxpanel"
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val ch = NotificationChannel(
                channelId, "LoxPanel Server", NotificationManager.IMPORTANCE_LOW
            )
            (getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager)
                .createNotificationChannel(ch)
        }
        @Suppress("DEPRECATION")
        val builder = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O)
            Notification.Builder(this, channelId) else Notification.Builder(this)
        return builder
            .setContentTitle("LoxPanel Server")
            .setContentText("läuft auf Port ${Visu.PORT}")
            .setSmallIcon(android.R.drawable.ic_dialog_info)
            .setOngoing(true)
            .build()
    }
}
