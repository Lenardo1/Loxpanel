package com.loxpanel.spike

import android.accessibilityservice.AccessibilityService
import android.graphics.Rect
import android.os.Handler
import android.os.Looper
import android.view.accessibility.AccessibilityEvent
import android.view.accessibility.AccessibilityNodeInfo

/**
 * Bedienungshilfe-Dienst (eigene Version, Marco): beobachtet nur die Loxone-App
 * (res/xml/lox_sicht.xml) und sagt der Wetter-Einblendung, ob sie gerade passt.
 * Sie erscheint nur, wenn oben links der Miniserver-Name steht (Startansicht) und
 * das Menü zu ist; im Menü, in Detailansichten und im Ambientmodus verschwindet sie.
 *
 * Einschalten per adb (ohne diesen Dienst ist das Wetter immer sichtbar):
 *   adb shell settings put secure enabled_accessibility_services com.loxpanel.spike/com.loxpanel.spike.LoxSicht
 *   adb shell settings put secure accessibility_enabled 1
 */
class LoxSicht : AccessibilityService() {

    private val haupt = Handler(Looper.getMainLooper())
    private var geplant = false
    private val pruefen = Runnable { geplant = false; auswerten() }

    override fun onAccessibilityEvent(event: AccessibilityEvent?) {
        // Viele Ereignisse hintereinander (Werte ändern sich laufend) -> höchstens alle 250 ms prüfen
        if (!geplant) { geplant = true; haupt.postDelayed(pruefen, 250) }
    }

    override fun onInterrupt() {}

    private fun auswerten() {
        val wurzel = try { rootInActiveWindow } catch (_: Exception) { null } ?: return
        if (wurzel.packageName?.toString() != "com.loxone.kerberos") return
        var name = false; var menue = false
        val r = Rect()
        fun gehen(n: AccessibilityNodeInfo?, tiefe: Int) {
            if (n == null || tiefe > 40 || (name && menue)) return
            val t = n.text?.toString()
            if (!t.isNullOrBlank() && n.isVisibleToUser) {
                n.getBoundsInScreen(r)
                if (WetterText.istMenue(t)) menue = true
                if (r.top < 80 && r.left in 60..140 && r.height() in 20..100) name = true
            }
            for (i in 0 until n.childCount) gehen(n.getChild(i), tiefe + 1)
        }
        gehen(wurzel, 0)
        WetterOverlay.sichtbar(name && !menue)
    }
}
