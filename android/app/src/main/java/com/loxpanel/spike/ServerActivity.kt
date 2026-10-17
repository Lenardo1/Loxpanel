package com.loxpanel.spike

import android.app.Activity
import android.graphics.Color
import android.graphics.Typeface
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.text.InputType
import android.util.TypedValue
import android.view.Gravity
import android.view.View
import android.view.inputmethod.EditorInfo
import android.widget.Button
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.RadioButton
import android.widget.RadioGroup
import android.widget.ScrollView
import android.widget.TextView
import java.net.Inet4Address
import java.net.NetworkInterface
import java.net.SocketException
import java.util.concurrent.Executors

/**
 * Einrichtung der App: „Wo läuft der Server?“ Beim ersten Start, bevor die
 * Anzeige etwas lädt, und später über „Server ändern“ (langer Druck auf der
 * Uhr-Seite, Knopf auf der Fehlerseite). Zwei Wege:
 *
 * - **Auf diesem Gerät:** Die App startet den eingebetteten Server
 *   (ServerService), der Konfigurator ist im Heimnetz unter der Adresse des
 *   Geräts erreichbar.
 * - **Im Netz:** Die App zeigt die Visu eines anderen LoxPanel-Servers (Docker,
 *   LoxBerry, anderes Panel) und verhält sich wie jedes Gerät mit
 *   Kiosk-Browser: Der Konfigurator meldet es mit Code, vergibt Namen und
 *   Ansicht. „Weiter“ fragt /api/health des Servers; antwortet er nicht,
 *   lässt sich die Adresse trotzdem übernehmen (der Server läuft vielleicht
 *   gerade nicht).
 *
 * Wechselt die App vom eigenen Server auf einen im Netz, startet die Anzeige
 * den Prozess neu, damit der eingebettete Server endet (KioskActivity).
 */
class ServerActivity : Activity() {

    private lateinit var hier: RadioButton
    private lateinit var netz: RadioButton
    private lateinit var adresse: EditText
    private lateinit var meldung: TextView
    private lateinit var weiter: Button
    private lateinit var trotzdem: Button
    private val ui = Handler(Looper.getMainLooper())
    private val pruefer = Executors.newSingleThreadExecutor { r ->
        Thread(r, "loxpanel-serverpruefung").apply { isDaemon = true }
    }

    /** Ob die App vor dieser Seite schon eingerichtet war: dann lässt sie sich
     *  mit Zurück oder „Abbrechen“ verlassen, beim ersten Start nicht. */
    private var warEingerichtet = false

    /** host:port, dessen Prüfung scheiterte; „Trotzdem übernehmen“ nimmt es. */
    private var ungeprueft: String? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        warEingerichtet = Visu.eingerichtet(this)
        val server = Visu.server(this)

        val spalte = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(24), dp(24), dp(24), dp(24))
        }
        spalte.addView(text("Wo läuft der LoxPanel-Server?", 22f, true))
        spalte.addView(text(
            "Die App zeigt die Visu eines LoxPanel-Servers. Er kann auf diesem Gerät laufen " +
                "oder irgendwo im Heimnetz, etwa in Docker oder auf einem LoxBerry.", 15f, false))

        val gruppe = RadioGroup(this).apply { orientation = RadioGroup.VERTICAL }
        hier = wahl(
            "Auf diesem Gerät",
            "Die App startet den Server selbst. Der Konfigurator ist dann im Heimnetz unter " +
                konfiguratorAdresse() + " erreichbar."
        )
        netz = wahl(
            "Im Netz",
            "Die App zeigt die Visu des Servers unter dieser Adresse. Der Konfigurator meldet " +
                "das Gerät dort unter „Neues Gerät gefunden“ und vergibt Namen und Ansicht."
        )
        gruppe.addView(hier)
        gruppe.addView(netz)
        spalte.addView(gruppe)

        adresse = EditText(this).apply {
            hint = "Adresse des Servers, z. B. 192.168.1.10:${Visu.PORT}"
            inputType = InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_URI
            imeOptions = EditorInfo.IME_ACTION_DONE
            isSingleLine = true
            setTextSize(TypedValue.COMPLEX_UNIT_SP, 16f)
            setText(server ?: "")
            setOnEditorActionListener { _, aktion, _ ->
                if (aktion == EditorInfo.IME_ACTION_DONE) { weiter(); true } else false
            }
        }
        spalte.addView(adresse, LinearLayout.LayoutParams(
            LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT
        ).apply { leftMargin = dp(32); topMargin = dp(4) })

        meldung = text("", 14f, false)
        spalte.addView(meldung)

        val knoepfe = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.END
        }
        trotzdem = Button(this).apply {
            text = "Trotzdem übernehmen"
            visibility = View.GONE
            setOnClickListener { ungeprueft?.let { uebernehmen(it) } }
        }
        weiter = Button(this).apply {
            text = if (warEingerichtet) "Übernehmen" else "Weiter"
            setOnClickListener { weiter() }
        }
        if (warEingerichtet) {
            knoepfe.addView(Button(this).apply {
                text = "Abbrechen"
                setOnClickListener { finish() }
            })
        }
        knoepfe.addView(trotzdem)
        knoepfe.addView(weiter)
        spalte.addView(knoepfe)

        setContentView(ScrollView(this).apply { addView(spalte) })

        gruppe.setOnCheckedChangeListener { _, _ -> wahlZeigen() }
        if (server != null) netz.isChecked = true else hier.isChecked = true
        wahlZeigen()
    }

    override fun onDestroy() {
        pruefer.shutdownNow()
        ui.removeCallbacksAndMessages(null)
        super.onDestroy()
    }

    /** Beim ersten Start gibt es nichts, wohin Zurück führen könnte. */
    @Suppress("OVERRIDE_DEPRECATION")
    override fun onBackPressed() {
        if (warEingerichtet) finish()
    }

    private fun wahlZeigen() {
        adresse.isEnabled = netz.isChecked
        adresse.alpha = if (netz.isChecked) 1f else 0.5f
        meldung.text = ""
        trotzdem.visibility = View.GONE
        ungeprueft = null
        if (netz.isChecked) adresse.requestFocus()
    }

    /** „Weiter“: eigener Server sofort, Server im Netz erst nach einer Prüfung. */
    private fun weiter() {
        meldung.text = ""
        trotzdem.visibility = View.GONE
        ungeprueft = null
        if (hier.isChecked) {
            uebernehmen(null)
            return
        }
        val s = Visu.serverEingabe(adresse.text.toString())
        if (s == null) {
            meldung.text = "Bitte die Adresse des Servers eintragen, zum Beispiel 192.168.1.10:${Visu.PORT} " +
                "(ohne Port gilt ${Visu.PORT}). Die Zeile steht im Konfigurator unter Geräte → „Gerät verbinden“."
            return
        }
        weiter.isEnabled = false
        meldung.text = "Prüfe $s …"
        pruefer.execute {
            val ergebnis = ServerPruefung.pruefen(Visu.basisFuer(s))
            ui.post { if (!isFinishing && !isDestroyed) ergebnis(s, ergebnis) }
        }
    }

    private fun ergebnis(s: String, ergebnis: ServerPruefung.Ergebnis) {
        weiter.isEnabled = true
        when (ergebnis) {
            is ServerPruefung.Ergebnis.Gefunden -> uebernehmen(s)
            is ServerPruefung.Ergebnis.KeinServer -> {
                meldung.text = "Unter $s antwortet kein LoxPanel-Server: ${ergebnis.grund}. " +
                    "Läuft der Server, und ist das Gerät im selben Netz?"
                ungeprueft = s
                trotzdem.visibility = View.VISIBLE
            }
        }
    }

    /** Speichert die Wahl und übergibt an die Anzeige; den Dienst startet oder
     *  beendet sie passend zur Wahl. */
    private fun uebernehmen(server: String?) {
        Visu.serverSetzen(this, server)
        ServerService.anpassen(this)
        finish()
    }

    /** Adresse des Konfigurators, wenn der Server auf diesem Gerät läuft: mit
     *  der IPv4-Adresse des Geräts im Heimnetz, sonst mit dem Platz dafür. */
    private fun konfiguratorAdresse(): String {
        val ip = try {
            NetworkInterface.getNetworkInterfaces()?.toList().orEmpty()
                .filter { it.isUp && !it.isLoopback }
                .flatMap { it.inetAddresses.toList() }
                .filterIsInstance<Inet4Address>()
                .firstOrNull { it.isSiteLocalAddress }
                ?.hostAddress
        } catch (e: SocketException) {
            null
        }
        return "http://${ip ?: "<IP dieses Geräts>"}:${Visu.PORT}/config"
    }

    private fun wahl(titel: String, erklaerung: String): RadioButton = RadioButton(this).apply {
        text = android.text.SpannableStringBuilder().apply {
            append(titel)
            setSpan(android.text.style.StyleSpan(Typeface.BOLD), 0, length, 0)
            append("\n")
            val ab = length
            append(erklaerung)
            setSpan(android.text.style.RelativeSizeSpan(0.85f), ab, length, 0)
            setSpan(android.text.style.ForegroundColorSpan(Color.GRAY), ab, length, 0)
        }
        setTextSize(TypedValue.COMPLEX_UNIT_SP, 17f)
        setPadding(dp(8), dp(12), dp(8), dp(12))
    }

    private fun text(inhalt: String, sp: Float, fett: Boolean): TextView = TextView(this).apply {
        text = inhalt
        setTextSize(TypedValue.COMPLEX_UNIT_SP, sp)
        if (fett) setTypeface(typeface, Typeface.BOLD)
        setPadding(0, dp(8), 0, dp(8))
    }

    private fun dp(wert: Int): Int =
        TypedValue.applyDimension(TypedValue.COMPLEX_UNIT_DIP, wert.toFloat(), resources.displayMetrics).toInt()
}
