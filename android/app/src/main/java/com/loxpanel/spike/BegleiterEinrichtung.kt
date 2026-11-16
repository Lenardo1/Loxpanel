package com.loxpanel.spike

import android.Manifest
import android.app.Activity
import android.app.admin.DevicePolicyManager
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.graphics.Color
import android.graphics.Typeface
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.os.PowerManager
import android.provider.Settings
import android.text.InputType
import android.util.TypedValue
import android.view.Gravity
import android.widget.Button
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView

/**
 * Einrichtung als Begleit-Tablet (eigene Version, Marco) – ohne adb: Server und Name
 * eintragen, dann Schritt für Schritt die Android-Berechtigungen erteilen. Danach läuft
 * die App nur im Hintergrund; vorn bleibt die andere App (Loxone). Alles Weitere stellt
 * man im LoxPanel-Konfigurator unter Geräte → „Begleit-Tablets“ ein.
 *
 * Erreichbar über die Ersteinrichtung („Nur im Hintergrund“) und danach jederzeit über
 * das App-Symbol von LoxPanel.
 */
class BegleiterEinrichtung : Activity() {

    private lateinit var server: EditText
    private lateinit var name: EditText
    private lateinit var schritte: LinearLayout
    private lateinit var stand: TextView

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val pr = getSharedPreferences("begleiter", Context.MODE_PRIVATE)
        val spalte = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; setPadding(dp(24), dp(24), dp(24), dp(24)) }
        spalte.addView(text("Begleit-Tablet", 22f, true))
        spalte.addView(text("LoxPanel läuft auf diesem Tablet nur im Hintergrund, vorn bleibt eine andere App " +
            "(z. B. die Loxone-App). LoxPanel blendet dort das Wetter ein, schaltet das Display über den " +
            "Bewegungsmelder und arbeitet als BLE-Scanner. Eingestellt wird das im LoxPanel-Konfigurator " +
            "unter Geräte → „Begleit-Tablets“.", 15f, false))

        spalte.addView(text("Adresse des LoxPanel-Servers", 15f, true))
        server = feld(pr.getString("server", "") ?: "", "z. B. 192.168.1.10:${Visu.PORT}")
        spalte.addView(server)
        spalte.addView(text("Name dieses Tablets (so erscheint es im Konfigurator)", 15f, true))
        name = feld(pr.getString("name", "") ?: "", "z. B. Flur")
        spalte.addView(name)

        spalte.addView(text("Berechtigungen", 18f, true))
        schritte = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }
        spalte.addView(schritte)

        stand = text("", 14f, false)
        spalte.addView(stand)
        val knoepfe = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL; gravity = Gravity.END }
        knoepfe.addView(Button(this).apply {
            text = "Begleit-Modus beenden"
            setOnClickListener { beenden() }
        })
        knoepfe.addView(Button(this).apply {
            text = "Speichern und starten"
            setOnClickListener { starten() }
        })
        spalte.addView(knoepfe)
        setContentView(ScrollView(this).apply { addView(spalte) })
    }

    override fun onResume() {
        super.onResume()
        schritteZeichnen()
    }

    // ---- Schritte: Status und Knopf, der die passende Android-Seite öffnet ----

    private class Schritt(val titel: String, val wozu: String, val erledigt: Boolean, val knopf: String, val tun: () -> Unit)

    private fun schritteListe(): List<Schritt> {
        val l = ArrayList<Schritt>()
        l += Schritt("Über anderen Apps einblenden", "für das Wetterfeld über der Loxone-App",
            Build.VERSION.SDK_INT < 23 || Settings.canDrawOverlays(this), "Erlauben") {
            startActivity(Intent(Settings.ACTION_MANAGE_OVERLAY_PERMISSION, Uri.parse("package:$packageName")))
        }
        val vorne = mutableListOf(Manifest.permission.ACCESS_FINE_LOCATION)
        if (Build.VERSION.SDK_INT >= 31) vorne += Manifest.permission.BLUETOOTH_SCAN
        if (Build.VERSION.SDK_INT >= 33) vorne += Manifest.permission.POST_NOTIFICATIONS
        l += Schritt("Standort, Bluetooth, Benachrichtigungen", "für den BLE-Scanner (Android verlangt dafür den Standort)",
            vorne.all { erlaubt(it) }, "Erlauben") { requestPermissions(vorne.toTypedArray(), 1) }
        if (Build.VERSION.SDK_INT >= 29) {
            l += Schritt("Standort „Immer erlauben“", "damit der Scanner auch nach einem Neustart im Hintergrund startet",
                erlaubt(Manifest.permission.ACCESS_BACKGROUND_LOCATION), "Erlauben") {
                if (!erlaubt(Manifest.permission.ACCESS_FINE_LOCATION)) stand.text = "Zuerst „Standort, Bluetooth …“ erlauben."
                else requestPermissions(arrayOf(Manifest.permission.ACCESS_BACKGROUND_LOCATION), 2)
            }
        }
        val pm = getSystemService(POWER_SERVICE) as PowerManager
        l += Schritt("Akku-Optimierung aus", "damit Android LoxPanel nicht schlafen legt",
            Build.VERSION.SDK_INT < 23 || pm.isIgnoringBatteryOptimizations(packageName), "Ausnehmen") {
            startActivity(Intent(Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS, Uri.parse("package:$packageName")))
        }
        val dpm = getSystemService(DEVICE_POLICY_SERVICE) as DevicePolicyManager
        val admin = ComponentName(this, LockAdmin::class.java)
        l += Schritt("Display ausschalten dürfen", "Geräteadministrator, nur „Bildschirm sperren“ – für Display aus per Bewegungsmelder",
            dpm.isAdminActive(admin), "Aktivieren") {
            startActivity(Intent(DevicePolicyManager.ACTION_ADD_DEVICE_ADMIN)
                .putExtra(DevicePolicyManager.EXTRA_DEVICE_ADMIN, admin)
                .putExtra(DevicePolicyManager.EXTRA_ADD_EXPLANATION, "LoxPanel schaltet das Display aus, wenn der Bewegungsmelder niemanden sieht."))
        }
        val dienste = Settings.Secure.getString(contentResolver, Settings.Secure.ENABLED_ACCESSIBILITY_SERVICES) ?: ""
        l += Schritt("Bedienungshilfe „LoxPanel“ (optional)", "blendet das Wetter aus, wenn das Menü der Loxone-App offen ist. " +
            "Dort unter „Installierte Apps“ → LoxPanel einschalten.",
            dienste.contains("$packageName/"), "Öffnen") { startActivity(Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS)) }
        return l
    }

    private fun schritteZeichnen() {
        schritte.removeAllViews()
        for (s in schritteListe()) {
            val zeile = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL; gravity = Gravity.CENTER_VERTICAL; setPadding(0, dp(6), 0, dp(6)) }
            val t = TextView(this).apply {
                text = (if (s.erledigt) "✓  " else "○  ") + s.titel + "\n" + s.wozu
                setTextSize(TypedValue.COMPLEX_UNIT_SP, 15f)
                setTextColor(if (s.erledigt) Color.rgb(46, 160, 67) else Color.DKGRAY)
            }
            zeile.addView(t, LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f))
            if (!s.erledigt) zeile.addView(Button(this).apply { text = s.knopf; setOnClickListener { s.tun() } })
            schritte.addView(zeile)
        }
    }

    override fun onRequestPermissionsResult(requestCode: Int, permissions: Array<out String>, grantResults: IntArray) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        schritteZeichnen()
    }

    private fun erlaubt(p: String) = checkSelfPermission(p) == PackageManager.PERMISSION_GRANTED

    // ---- Speichern ----

    private fun starten() {
        val s = Visu.serverEingabe(server.text.toString())
        val n = name.text.toString().trim()
        if (s == null) { stand.text = "Bitte die Adresse des LoxPanel-Servers eintragen, z. B. 192.168.1.10:${Visu.PORT}."; return }
        if (!Regex("^[\\wäöüÄÖÜß .\\-]{1,40}$").matches(n)) { stand.text = "Bitte einen Namen eintragen (Buchstaben, Zahlen, Leerzeichen)."; return }
        // Voreinstellungen beim ersten Mal: Loxone-App nach dem Hochfahren öffnen, Weckdienst an
        val sa = getSharedPreferences("startapp", Context.MODE_PRIVATE)
        if (sa.getString("paket", "").isNullOrEmpty() && installiert("com.loxone.kerberos"))
            sa.edit().putString("paket", "com.loxone.kerberos").apply()
        if (!WachDienst.an(this)) WachDienst.setzen(this, true)
        BegleiterDienst.setzen(this, Intent().putExtra("begleiterServer", s).putExtra("begleiterName", n))
        stand.text = "Gespeichert. „$n“ meldet sich gleich im LoxPanel-Konfigurator unter Geräte → „Begleit-Tablets“. " +
            "Dort Wetter, Farbe und BLE-Scanner einstellen."
        // die eingestellte App nach vorn
        StartApp.oeffnen(this)
    }

    private fun beenden() {
        BegleiterDienst.setzen(this, Intent().putExtra("begleiterServer", "").putExtra("begleiterName", ""))
        WetterOverlay.setzen(this, Intent().putExtra("wetter", ""))
        startActivity(Intent(this, ServerActivity::class.java))
        finish()
    }

    private fun installiert(paket: String) = try { packageManager.getPackageInfo(paket, 0); true } catch (_: Exception) { false }

    private fun feld(wert: String, hinweis: String) = EditText(this).apply {
        setText(wert); hint = hinweis; isSingleLine = true
        inputType = InputType.TYPE_CLASS_TEXT
        setTextSize(TypedValue.COMPLEX_UNIT_SP, 16f)
    }

    private fun text(inhalt: String, sp: Float, fett: Boolean) = TextView(this).apply {
        text = inhalt; setTextSize(TypedValue.COMPLEX_UNIT_SP, sp)
        if (fett) setTypeface(typeface, Typeface.BOLD)
        setPadding(0, dp(8), 0, dp(4))
    }

    private fun dp(w: Int) = TypedValue.applyDimension(TypedValue.COMPLEX_UNIT_DIP, w.toFloat(), resources.displayMetrics).toInt()
}
