package com.loxpanel.spike

/**
 * Berührung, solange ein Schoner läuft (die Uhr der Visu oder das dunkle
 * Display): Ein Finger weckt wie bisher und wird geschluckt, löst also keine
 * Kachel aus. Zwei Finger sind eine Geste wie auf den Loxone-Tastern (Licht
 * dimmen, Stimmung, Beschattung, Raum verlassen …): Die ganze Berührung geht an
 * die Visu, das Display bleibt dunkel (docs/TODO.md §9, Stufe 5).
 *
 * Ob ein zweiter Finger kommt, steht erst kurz nach dem ersten fest. So lange
 * hält die Anzeige das erste Ereignis zurück ([Tun.HALTEN]); wird der Finger
 * vorher losgelassen, weckt sie sofort. Ob die Visu Gesten überhaupt erlaubt,
 * entscheidet sie selbst: Ohne Gesten weckt sie bei der weitergereichten
 * Berührung wie bei jedem Tipp auf die Uhr.
 *
 * Hier steht die Entscheidung ohne Android, damit sie sich auf dem PC prüfen
 * lässt. Die Activity reicht die MotionEvents nach [Tun] weiter.
 */
class SchonerBeruehrung(private val warteMs: Long = WARTE_MS) {

    /** Was die Anzeige mit dem Ereignis tun soll. */
    enum class Tun {
        /** Erstes Ereignis zurückhalten, bis feststeht, ob ein zweiter Finger kommt. */
        HALTEN,
        /** Das zurückgehaltene Ereignis und dieses an die Visu geben (Geste beginnt). */
        NACHREICHEN,
        /** Dieses Ereignis an die Visu geben (Geste läuft). */
        DURCHREICHEN,
        /** Display wecken, das zurückgehaltene Ereignis verwerfen. */
        WECKEN,
        /** Ereignis verwerfen. */
        SCHLUCKEN,
    }

    private enum class Lage { RUHE, WARTET, GESTE, GEWECKT }

    private var lage = Lage.RUHE
    private var seit = 0L

    /** Gehört die laufende Berührung noch hierher (auch wenn der Schoner
     *  inzwischen aus ist)? Sonst bekäme die Visu Ereignisse ohne Anfang. */
    val laeuft: Boolean get() = lage != Lage.RUHE

    /** Erster Finger auf ([zeit] in ms, etwa MotionEvent.eventTime). */
    fun runter(zeit: Long): Tun {
        lage = Lage.WARTET
        seit = zeit
        return Tun.HALTEN
    }

    /** Ein weiterer Finger auf. */
    fun weitererFinger(zeit: Long): Tun = when (lage) {
        Lage.WARTET -> if (zeit - seit <= warteMs) {
            lage = Lage.GESTE
            Tun.NACHREICHEN
        } else {
            lage = Lage.GEWECKT
            Tun.WECKEN
        }
        Lage.GESTE -> Tun.DURCHREICHEN
        else -> Tun.SCHLUCKEN
    }

    /** Bewegung oder ein Finger von mehreren hoch, mitten in der Berührung. */
    fun weiter(): Tun = if (lage == Lage.GESTE) Tun.DURCHREICHEN else Tun.SCHLUCKEN

    /** Letzter Finger hoch: ein einzelner, kurzer Tipp weckt sofort. */
    fun hoch(): Tun {
        val tun = when (lage) {
            Lage.WARTET -> Tun.WECKEN
            Lage.GESTE -> Tun.DURCHREICHEN
            else -> Tun.SCHLUCKEN
        }
        lage = Lage.RUHE
        return tun
    }

    /** Das System bricht die Berührung ab: Eine Geste erfährt es, geweckt wird nicht. */
    fun abbruch(): Tun {
        val tun = if (lage == Lage.GESTE) Tun.DURCHREICHEN else Tun.SCHLUCKEN
        lage = Lage.RUHE
        return tun
    }

    /** Die Wartezeit ist um: Kam kein zweiter Finger, weckt der eine. */
    fun frist(): Tun = if (lage == Lage.WARTET) {
        lage = Lage.GEWECKT
        Tun.WECKEN
    } else {
        Tun.SCHLUCKEN
    }

    companion object {
        /** So lange wartet ein Finger auf den zweiten. Zwei Finger, die zugleich
         *  aufsetzen sollen, treffen innerhalb weniger Zehntelsekunden auf;
         *  länger soll das Wecken mit einem Finger nicht warten. Dieselbe Zahl
         *  nimmt die Visu (GESTE_ZWEITER_FINGER_MS in panel.html). */
        const val WARTE_MS = 120L
    }
}
