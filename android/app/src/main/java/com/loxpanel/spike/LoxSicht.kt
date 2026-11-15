package com.loxpanel.spike

import android.accessibilityservice.AccessibilityService
import android.graphics.Rect
import android.os.Handler
import android.os.Looper
import android.util.Log
import android.view.accessibility.AccessibilityEvent
import android.view.accessibility.AccessibilityNodeInfo

/**
 * Bedienungshilfe-Dienst (eigene Version, Marco): beobachtet nur die Loxone-App
 * (res/xml/lox_sicht.xml) und sagt der Wetter-Einblendung, ob sie gerade passt.
 * Sie erscheint nur, wenn oben links der Miniserver-Name steht (Startansicht) und
 * das Menü zu ist; im Menü, in Detailansichten und im Ambientmodus verschwindet sie.
 *
 * Einschalten am Gerät (ohne diesen Dienst ist das Wetter immer sichtbar): Einstellungen →
 * Eingabehilfe → Installierte Apps → LoxPanel. Per adb setzt Android 14 das wieder zurück
 * (eingeschränkte Einstellung) – nicht umgehen.
 */
class LoxSicht : AccessibilityService() {

    private val haupt = Handler(Looper.getMainLooper())
    // Die Loxone-App (React Native) meldet Änderungen ihrer Oberfläche kaum als Ereignis
    // (nur beim Fensterwechsel). Darum regelmäßig nachsehen - nur bei eingeschaltetem Display.
    private val takt = object : Runnable {
        override fun run() {
            val pm = getSystemService(POWER_SERVICE) as android.os.PowerManager
            if (pm.isInteractive) auswerten()
            haupt.postDelayed(this, if (pm.isInteractive) 600 else 3000)
        }
    }

    override fun onServiceConnected() { super.onServiceConnected(); instanz = this; haupt.removeCallbacks(takt); haupt.post(takt) }

    override fun onDestroy() { haupt.removeCallbacks(takt); haupt.removeCallbacks(nachsehen); if (instanz === this) instanz = null; super.onDestroy() }

    private val nachsehen = Runnable { auswerten() }

    companion object {
        @Volatile private var instanz: LoxSicht? = null

        /** Nach einer Berührung irgendwo (meldet die Wetter-Einblendung): gleich mehrmals hintereinander
         *  nachsehen, damit das Wetter mit dem Aufklappen des Menüs verschwindet, nicht erst im nächsten Takt. */
        fun schnell() {
            val s = instanz ?: return
            s.haupt.post {
                s.haupt.removeCallbacks(s.nachsehen)
                for (ms in longArrayOf(60, 150, 260, 400, 600, 900, 1300)) s.haupt.postDelayed(s.nachsehen, ms)
            }
        }
    }

    override fun onAccessibilityEvent(event: AccessibilityEvent?) {}

    override fun onInterrupt() {}

    private var zuletzt = ""

    private fun auswerten() {
        // Ohne Ereignisse der App veraltet der Accessibility-Zwischenspeicher: vor jedem Blick leeren
        // (ab Android 14), sonst die besuchten Knoten einzeln auffrischen.
        val leeren = android.os.Build.VERSION.SDK_INT >= 34
        if (leeren) try { clearCache() } catch (_: Exception) {}
        // Alle Fenster der Loxone-App (das Menü kann ein eigenes Fenster sein)
        val wurzeln = try {
            windows.mapNotNull { it.root }.filter { it.packageName?.toString() == "com.loxone.kerberos" }
        } catch (_: Exception) { emptyList() }
        if (wurzeln.isEmpty()) return
        // Ein Durchgang über den oberen Rand: Miniserver-Name in der Kopfzeile (links ab ~84 px)
        // und der Kopf des offenen Menüs („INTERN VERBUNDEN“ o. ä., darüber der Name ganz links).
        // Der Baum der Loxone-App ist tief (~47 Ebenen); Zweige unterhalb des Randes fallen weg.
        var name = false; var menue = false
        val r = Rect()
        // Grenzen in dp (gemessen am A8: Name bei 84..273 px, 21..75 px Höhe, Dichte 1,5),
        // damit es auf Tablets mit anderer Auflösung genauso greift
        val d = resources.displayMetrics.density
        val rand = (93 * d).toInt(); val oben = (53 * d).toInt()
        val links = (40 * d).toInt()..(93 * d).toInt(); val hoehe = (13 * d).toInt()..(67 * d).toInt()
        fun gehen(n: AccessibilityNodeInfo?, tiefe: Int) {
            if (n == null || (name && menue) || tiefe > 120) return
            if (!leeren) try { n.refresh() } catch (_: Exception) {}
            n.getBoundsInScreen(r)
            if (r.top >= rand || r.bottom <= 0) return
            val t = n.text?.toString()
            if (!t.isNullOrBlank()) {
                if (WetterText.istMenue(t)) menue = true
                else if (r.top < oben && r.left in links && r.height() in hoehe) name = true
            }
            for (i in 0 until n.childCount) gehen(n.getChild(i), tiefe + 1)
        }
        wurzeln.forEach { gehen(it, 0) }
        val stand = "name=$name menue=$menue fenster=${wurzeln.size}"
        if (stand != zuletzt) { zuletzt = stand; Log.i("LPSICHT", stand) }
        WetterOverlay.sichtbar(name && !menue)
    }
}
