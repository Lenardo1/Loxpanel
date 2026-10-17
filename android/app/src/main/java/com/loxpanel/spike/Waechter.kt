package com.loxpanel.spike

/**
 * Wächter der App: Der Server-Dienst fragt in festem Abstand /api/health des
 * eingebetteten Servers. Antwortet er mehrmals hintereinander nicht oder meldet
 * er eine beendete Hintergrund-Aufgabe (503), startet die App neu: Den
 * Python-Server kann sie im laufenden Prozess nicht neu starten. Eine Bremse
 * verhindert, dass ein dauerhaft kaputter Server die App in eine
 * Neustart-Schleife schickt. Dazu die Regel, wann die Anzeige einen hängenden
 * Renderer der WebView beendet. Hier stehen die Regeln, ohne Android, damit sie
 * sich auf dem PC prüfen lassen.
 */
object Waechter {
    /** Abstand der Prüfungen. */
    const val PRUEF_ABSTAND_MS = 30_000L

    /** Wartezeit auf den Verbindungsaufbau und auf die Antwort einer Prüfung. */
    const val VERBINDEN_MS = 5_000
    const val ANTWORT_MS = 10_000

    /** So lange darf der Server nach dem Start brauchen, bis er zum ersten Mal
     *  antwortet. Der erste Start nach einem Update kopiert den Code und
     *  entpackt Python, das dauert auf schwachen Geräten. */
    const val ANLAUF_MS = 300_000L

    /** Fehlschläge in Folge bis zum Neustart, mit PRUEF_ABSTAND_MS gut
     *  anderthalb Minuten ohne Antwort. Ein einzelner Aussetzer reicht nicht. */
    const val FEHLER_BIS_NEUSTART = 3

    /** Bremse: höchstens so viele Neustarts innerhalb von BREMSE_MS. Danach
     *  wartet der Wächter, bis der älteste herausfällt. */
    const val NEUSTARTS_HOECHSTENS = 3
    const val BREMSE_MS = 3_600_000L

    /** Meldungen "Anzeige reagiert nicht" (Android meldet frühestens alle 5 s)
     *  bis die Anzeige ihren Renderer beendet und sich neu aufbaut, also gut
     *  eine halbe Minute ohne Reaktion. */
    const val ANZEIGE_HAENGT_MELDUNGEN = 6

    /** Was der Wächter zwischen zwei Prüfungen weiß. [startMs] ist der
     *  Serverstart, auf derselben Uhr wie die Zeitpunkte der Prüfungen. */
    class Stand(private val startMs: Long) {
        /** Fehlschläge in Folge, eine Antwort setzt zurück. */
        var fehler = 0
            private set

        /** Ob der Server seit dem Start schon einmal geantwortet hat. */
        var warGesund = false
            private set

        /** Wertet eine Prüfung aus: true, wenn der Server neu gestartet werden
         *  muss. Hat er seit dem Start noch nie geantwortet, frühestens nach der
         *  Anlaufzeit. */
        fun pruefung(gesund: Boolean, jetztMs: Long): Boolean {
            fehler = if (gesund) 0 else fehler + 1
            warGesund = warGesund || gesund
            return fehler >= FEHLER_BIS_NEUSTART && (warGesund || jetztMs - startMs >= ANLAUF_MS)
        }
    }

    /** Die Neustarts, die für die Bremse zählen: die der letzten BREMSE_MS.
     *  Zeitpunkte nach [jetzt] stammen von einer verstellten Uhr und zählen nicht. */
    fun zaehlende(neustarts: List<Long>, jetzt: Long): List<Long> =
        neustarts.filter { it <= jetzt && jetzt - it < BREMSE_MS }

    /** Ob die Bremse einen weiteren Neustart erlaubt. */
    fun neustartErlaubt(neustarts: List<Long>, jetzt: Long): Boolean =
        zaehlende(neustarts, jetzt).size < NEUSTARTS_HOECHSTENS

    /** Ob die Anzeige ihren Renderer bei dieser Meldung in Folge beendet: bei
     *  der ANZEIGE_HAENGT_MELDUNGEN-ten, einmal je Hänger. */
    fun rendererBeenden(meldungen: Int): Boolean = meldungen == ANZEIGE_HAENGT_MELDUNGEN

    /** Neustart-Zeitpunkte (ms seit 1970) als Text für die Einstellungen der App
     *  und zurück. Unlesbares fällt weg. */
    fun alsText(neustarts: List<Long>): String = neustarts.joinToString(",")

    fun ausText(text: String?): List<Long> =
        text.orEmpty().split(',').mapNotNull { it.trim().toLongOrNull() }
}
