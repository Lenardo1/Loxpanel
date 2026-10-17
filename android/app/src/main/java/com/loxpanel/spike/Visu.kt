package com.loxpanel.spike

import android.annotation.SuppressLint
import android.content.Context
import java.io.File
import java.net.URI
import java.net.URISyntaxException

/**
 * Wo der LoxPanel-Server läuft und welche Adresse die Anzeige lädt. Port und
 * Adressen stehen nur hier; Server-Dienst, Kiosk-Anzeige, Einrichtung und
 * Statusseite lesen sie von hier.
 *
 * Server-Einstellung (Umbau der Einrichtung, Schritt 6): Beim ersten Start
 * fragt die App, ob der Server auf diesem Gerät laufen soll (eingebetteter
 * Server, Chaquopy) oder ob sie einen Server im Netz zeigt (Docker, LoxBerry,
 * ein anderes Panel). Mit einem Server im Netz verhält sich die App wie Fully
 * Kiosk: Sie lädt dessen Visu ohne Parameter, der Konfigurator meldet das Gerät
 * mit Code, und der eigene Server startet gar nicht erst.
 *
 * Die Kiosk-Anzeige merkt sich die zuletzt geladene Visu-Adresse. Die Visu
 * wechselt eine Ansicht, indem sie sich selbst mit neuem ?panel= lädt (Geräte
 * -> Ansicht wechseln, Betriebsmodus-Automatik). Nach einem Neustart der App
 * steht so wieder dieselbe Ansicht da, statt immer das Standardprofil. Wechselt
 * der Server, fällt die gemerkte Adresse weg: Sie gehört zum alten Server.
 */
object Visu {
    const val PORT = 8099

    /** Adresse des eingebetteten Servers auf dem Gerät. */
    const val EIGENER = "http://127.0.0.1:$PORT/"

    private const val PREFS = "visu"
    private const val LETZTE = "letzteAdresse"

    /** host:port des Servers im Netz; leer = der eigene Server auf dem Gerät.
     *  Fehlt der Eintrag, ist die App noch nicht eingerichtet. */
    private const val SERVER = "server"

    /** Ob schon entschieden ist, wo der Server läuft. Vorher zeigt die Anzeige
     *  die Einrichtung ([ServerActivity]). Eine App, die vor dieser Einstellung
     *  installiert war, hat ihren eigenen Server schon ausgerollt
     *  (filesDir/loxpanel/config); sie läuft damit weiter, ohne zu fragen. */
    fun eingerichtet(ctx: Context): Boolean {
        if (prefs(ctx).contains(SERVER)) return true
        if (File(ctx.filesDir, "loxpanel/config").isDirectory) {
            serverSetzen(ctx, null)
            return true
        }
        return false
    }

    /** host:port des Servers im Netz, null = der eigene Server auf dem Gerät. */
    fun server(ctx: Context): String? =
        prefs(ctx).getString(SERVER, null)?.takeIf { it.isNotEmpty() }

    fun eigenerServer(ctx: Context): Boolean = server(ctx) == null

    /** Basis-Adresse des eingestellten Servers, mit "/" am Ende. */
    fun basis(ctx: Context): String = server(ctx)?.let { basisFuer(it) } ?: EIGENER

    /** Speichert, wo der Server läuft: null = dieses Gerät, sonst host:port
     *  aus [serverEingabe]. Ändert sich damit die Basis-Adresse, fällt die
     *  gemerkte Visu-Adresse weg. commit statt apply: Nach einem Wechsel vom
     *  eigenen Server weg startet die App gleich neu, der Eintrag muss stehen. */
    @SuppressLint("ApplySharedPref")
    fun serverSetzen(ctx: Context, server: String?) {
        val neu = server?.let { basisFuer(it) } ?: EIGENER
        val e = prefs(ctx).edit().putString(SERVER, server ?: "")
        if (neu != basis(ctx)) e.remove(LETZTE)
        e.commit()
    }

    /** Zuletzt angezeigte Visu-Adresse dieses Servers, sonst seine Visu mit
     *  dem Standardprofil. */
    fun startAdresse(ctx: Context): String {
        val b = basis(ctx)
        return prefs(ctx).getString(LETZTE, null)?.takeIf { istVisu(b, it) } ?: b
    }

    /** Merkt sich eine geladene Adresse, wenn sie die Visu des eingestellten
     *  Servers ist, nicht /config oder eine andere Seite. */
    fun merken(ctx: Context, adresse: String?) {
        if (adresse != null && istVisu(basis(ctx), adresse)) {
            prefs(ctx).edit().putString(LETZTE, adresse).apply()
        }
    }

    /** Ob die Adresse die Visu des Servers mit dieser Basis ist: dessen Host
     *  und Port, Pfad "/". */
    internal fun istVisu(basis: String, adresse: String): Boolean {
        if (!adresse.startsWith(basis)) return false
        val pfad = try {
            URI(adresse).path
        } catch (e: URISyntaxException) {
            return false
        }
        return pfad.isNullOrEmpty() || pfad == "/"
    }

    /** Basis-Adresse eines Servers im Netz aus host:port. */
    fun basisFuer(server: String): String = "http://$server/"

    /** Liest das Server-Feld der Einrichtung: "192.168.1.10", "192.168.1.10:8099"
     *  oder die Zeile aus dem Konfigurator ("http://192.168.1.10:8099/"). Ohne
     *  Port gilt [PORT]. Liefert host:port oder null, wenn das keine Adresse
     *  eines LoxPanel-Servers ist (Pfad, Abfrage, Zugangsdaten, https). */
    fun serverEingabe(text: String): String? {
        var t = text.trim()
        if (t.isEmpty()) return null
        if (!t.contains("://")) t = "http://$t"
        val uri = try {
            URI(t)
        } catch (e: URISyntaxException) {
            return null
        }
        if (uri.scheme != "http") return null
        val host = uri.host?.takeIf { it.isNotEmpty() } ?: return null
        if (uri.rawUserInfo != null || uri.rawQuery != null || uri.rawFragment != null) return null
        if (!(uri.rawPath.isNullOrEmpty() || uri.rawPath == "/")) return null
        val port = if (uri.port == -1) PORT else uri.port
        return "${host.lowercase()}:$port"
    }

    private fun prefs(ctx: Context) = ctx.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
}
