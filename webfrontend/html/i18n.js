/* LoxPanel Admin-UI Uebersetzung (i18n) fuer /settings und /config.
 *
 * Ansatz: Schluessel = deutscher Quelltext (de ist die Referenz, kein Eintrag
 * noetig). Zusatzsprachen liefern eine Map deutsch->uebersetzt; fehlt ein
 * Eintrag, bleibt der deutsche Text stehen (sichtbarer, aber unschaedlicher
 * Fallback). Gebaeude-/Geraete-/Raum-/Kategorienamen kommen aus dem Miniserver
 * und werden NICHT uebersetzt -> nur explizit markierte Elemente
 * ([data-i18n]) bzw. per T() erzeugte Texte werden angefasst.
 */
(function () {
  var LANGS = [['de', 'Deutsch'], ['en', 'English']];

  var CAT = {
    en: {
      // --- /config: Uebersicht / unterstuetzte Geraete / Assistent (EN, 2026-10-05) ---
      'LoxPanel baut auf einem quadratischen <b>480×480-Pane</b> auf – der Größe eines 4″-Wandpanels. Das 4″-Panel zeigt eines, das Tablet zwei – quer nebeneinander (Visu links, Widget rechts), hochkant übereinander (Visu oben, Widget unten). Hier ein Überblick, darunter die einstellbaren Bereiche.': 'LoxPanel is built on a square <b>480×480 pane</b> — the size of a 4″ wall panel. The 4″ panel shows one, the tablet two — side by side (view left, widget right), stacked in portrait (view top, widget bottom). Here is an overview, with the configurable areas below.',
      'Ein <b>Widget</b> ist eine fertige Inhaltsfläche — kein Kachelraster aus <b>Bausteinen</b>, sondern eine eigene Ansicht: <b>Wetter</b>, <b>Kalender</b>, <b>Energiefluss</b>, <b>Kamera</b> (Türstation), <b>Verlauf</b> (Aufzeichnung eines Bausteins), <b>Werte</b> (frei gewählte Bausteine als Liste) oder <b>Audio</b> (Now Playing der Musikzone).': 'A <b>widget</b> is a ready-made content area — not a tile grid of <b>blocks</b>, but a view of its own: <b>weather</b>, <b>calendar</b>, <b>energy flow</b>, <b>camera</b> (door station), <b>history</b> (recording of a block), <b>values</b> (freely chosen blocks as a list) or <b>audio</b> (now playing of the music zone).',
      'Dasselbe Widget lässt sich an <b>drei Stellen</b> einsetzen: im <b>Pane 2</b> eines 2-Pane-Panels (quer rechts neben der Visu, hochkant darunter, je Tab), in der <b>zweiten Spalte des Screensavers</b> (Uhr-Seite quer rechts, hochkant unten) und — <b>bald</b> — als <b>eigener Vollbild-Tab</b> in der unteren Leiste (auch am 1-Pane-Panel). Welche Widgets erscheinen, hängt von der Anlage ab: <b>Werte</b> braucht ausgewählte Bausteine, <b>Audio/Energiefluss/Kamera/Verlauf</b> je einen passenden Baustein.': 'The same widget can be placed in <b>three spots</b>: in <b>pane 2</b> of a 2-pane panel (landscape to the right of the view, portrait below it, per tab), in the <b>second column of the screensaver</b> (clock page: landscape right, portrait bottom) and — <b>soon</b> — as its <b>own full-screen tab</b> in the bottom bar (on a 1-pane panel too). Which widgets appear depends on the system: <b>values</b> needs selected blocks, <b>audio/energy flow/camera/history</b> each need a matching block.',
      'Ohne Widget: <b>„Screen füllen"</b> verdoppelt die Kacheln bei gleicher Kachelgröße – quer nach rechts (aus 2×2 wird 2×2 | 2×2 = 4×2), hochkant nach unten (aus 2×2 wird 2×4; das Hochformat-Raster 2×3 bleibt). <b>„Bildschirm füllen"</b> zoomt zusätzlich auf die echte Tablet-Auflösung.': 'Without a widget: <b>“Fill screen”</b> doubles the tiles at the same tile size — to the right in landscape (2×2 becomes 2×2 | 2×2 = 4×2), downward in portrait (2×2 becomes 2×4; the 2×3 portrait grid stays). <b>“Fill display”</b> additionally zooms to the real tablet resolution.',
      '<span class="n">A</span>Geräteklassen': '<span class="n">A</span>Device classes',
      '<span class="n">B</span>Aufteilung im Pane': '<span class="n">B</span>Layout within the pane',
      '<span class="n">C</span>Widget (Pane 2, Screensaver oder eigener Tab)': '<span class="n">C</span>Widget (pane 2, screensaver or own tab)',
      '<b>4″-Wandpanel</b>1 Pane – nur Visu': '<b>4″ wall panel</b>1 pane – view only',
      '<b>Tablet quer</b>2 Panes, gleiche Größe': '<b>Tablet landscape</b>2 panes, same size',
      '<b>Tablet hochkant</b>2 Panes übereinander': '<b>Tablet portrait</b>2 panes stacked',
      '<b>2×2</b>4 Kacheln': '<b>2×2</b>4 tiles',
      '<b>3×2</b>6 Kacheln': '<b>3×2</b>6 tiles',
      '<b>2×3</b>6 Kacheln': '<b>2×3</b>6 tiles',
      '<b>3×3</b>9 Kacheln': '<b>3×3</b>9 tiles',
      '<b>Liste</b>4 × 120': '<b>List</b>4 × 120',
      '<b>Vollbild</b>Status': '<b>Full screen</b>Status',
      '<b>Audio</b>Musikzone je Tab': '<b>Audio</b>Music zone per tab',
      '<b>Wetter</b>Kurve &amp; Vorschau': '<b>Weather</b>Curve &amp; forecast',
      '<b>Kalender</b>Monat + Termine': '<b>Calendar</b>Month + events',
      '<b>Energiefluss</b>Radial, live': '<b>Energy flow</b>Radial, live',
      '<b>Kamera</b>Türstation live': '<b>Camera</b>Door station live',
      '<b>Verlauf</b>Aufzeichnung eines Bausteins': '<b>History</b>Recording of a block',
      '<b>Werte</b>Frei gewählte Bausteine': '<b>Values</b>Freely chosen blocks',
      '<b>Pool</b><span class="badge">Bald</span>': '<b>Pool</b><span class="badge">Soon</span>',
      '<b>Ofensteuerung</b><span class="badge">Bald</span>': '<b>Stove control</b><span class="badge">Soon</span>',
      'LoxPanel läuft auf <b>Android-Wandpanels</b> (Fully Kiosk per <code>adb</code>) im Zielformat <b>480×480</b>. Diese Geräte sind erprobt – 4″-Panels 1:1, höher aufgelöste oder größere per Zoom, breite Geräte als zwei Panes.': 'LoxPanel runs on <b>Android wall panels</b> (Fully Kiosk via <code>adb</code>) in the target format <b>480×480</b>. These devices are proven — 4″ panels 1:1, higher-resolution or larger ones via zoom, wide devices as two panes.',
      '4″-Standardpanel <span class="badge ref">Referenz</span>': '4″ standard panel <span class="badge ref">Reference</span>',
      'Sonoff NSPanel Pro 86 <span class="badge">1 Pane · Fix</span>': 'Sonoff NSPanel Pro 86 <span class="badge">1 pane · fixed</span>',
      'Shelly Wall Display X1i <span class="badge">1 Pane · Zoom</span>': 'Shelly Wall Display X1i <span class="badge">1 pane · zoom</span>',
      'Sonoff NSPanel Pro 120 <span class="badge">1 Pane · Zoom</span>': 'Sonoff NSPanel Pro 120 <span class="badge">1 pane · zoom</span>',
      'Shelly Wall Display X2 / X2i <span class="badge">2 Panes</span>': 'Shelly Wall Display X2 / X2i <span class="badge">2 panes</span>',
      'YC-SM55P (Portworld) <span class="badge">2 Panes · LAN/PoE</span>': 'YC-SM55P (Portworld) <span class="badge">2 panes · LAN/PoE</span>',
      '7–8″-Tablet <span class="badge">2 Panes / Zoom</span>': '7–8″ tablet <span class="badge">2 panes / zoom</span>',
      'YC-SM41P / YC-SM41xx (Portworld) &amp; baugleiche – die <b>xx</b>-Varianten auch mit <b>LAN/PoE</b> (Strom + Netzwerk über ein Kabel). 1 Pane, fix – native Auflösung. Debian + Chromium-Kiosk = primäres Ziel.': 'YC-SM41P / YC-SM41xx (Portworld) &amp; equivalents – the <b>xx</b> variants also with <b>LAN/PoE</b> (power + network over one cable). 1 pane, fixed – native resolution. Debian + Chromium kiosk = primary target.',
      '5,5″-Gerät in der Klasse des Shelly X2 – zwei 480×480-Panes nebeneinander, zusätzlich mit <b>LAN/PoE</b> (Strom + Netzwerk über ein Kabel). Hoch- und Querformat möglich; hochkant liegen die beiden Panes übereinander.': '5.5″ device in the class of the Shelly X2 – two 480×480 panes side by side, additionally with <b>LAN/PoE</b> (power + network over one cable). Portrait and landscape possible; in portrait the two panes sit one above the other.',
      'In acht Schritten vom leeren Panel zur fertigen Visu — geführt, mit Sofort-Vorschau. Danach lässt sich jedes Detail unter <b>Panel Configuration</b> nachjustieren.': 'In eight steps from an empty panel to a finished view — guided, with instant preview. Afterwards every detail can be adjusted under <b>Panel Configuration</b>.',
      'Anzeigename und Panel-ID. Die ID ist der Aufruf am Gerät: <code>?panel=wohnzimmer</code>.': 'Display name and panel ID. The ID is the call on the device: <code>?panel=wohnzimmer</code>.',
      'Bei <strong>Freier Auswahl</strong>: bis zu 4 Seiten sind offen — ungenutzte mit <strong>✕</strong> entfernen. Je Seite Name, Icon und der Inhalt:': 'With <strong>Free selection</strong>: up to 4 pages are open — remove unused ones with <strong>✕</strong>. Per page a name, icon and the content:',
      '<strong>Kacheln:</strong> links Raum, rechts die Bausteine — mit Suche. <em>Nächsten Tab befüllen</em> führt weiter.<br><strong>Widget:</strong> gleich daneben der konkrete Baustein — <em>welcher</em> Verlauf, <em>welche</em> Kamera, <em>welche</em> Zone.': '<strong>Tiles:</strong> room on the left, the blocks on the right — with search. <em>Fill next tab</em> continues.<br><strong>Widget:</strong> right beside it the concrete block — <em>which</em> history, <em>which</em> camera, <em>which</em> zone.',
      'Wie eine <strong>aktive</strong> Kachel hervorgehoben wird — Rahmen, Füllung, Deckkraft — und der Rahmen der inaktiven Kacheln und rechten Panes.': 'How an <strong>active</strong> tile is highlighted — border, fill, opacity — and the border of the inactive tiles and right-hand panes.',
      'Alle Einstellungen auf einen Blick, dann <strong>„Panel anlegen ✓"</strong>. Danach im Editor für den Feinschliff und jederzeit über <em>„Visu öffnen"</em> testbar.': 'All settings at a glance, then <strong>“Create panel ✓”</strong>. Afterwards test in the editor for fine-tuning and anytime via <em>“Open view”</em>.',
      '<span class="pin">2 Panes</span> Was am Breitbild anders ist': '<span class="pin">2 panes</span> What is different on the wide display',
      'Licht, Beschattung, Taster, Sensoren … als einzelne <strong>Kacheln</strong> im Raster.': 'Lights, shading, buttons, sensors … as individual <strong>tiles</strong> in the grid.',
      'Panel-Konfiguration': 'Panel configuration',
      'Grundeinstellungen': 'Basic settings',
      'Aussehen & Verhalten': 'Appearance & behavior',
      'Panel-Farbe & Schrift, Kachel-Layout, Widget (Pane 2), Display & Nacht (Abdunkeln, Auto-Neustart), Feinjustierung.': 'Panel color & font, tile layout, widget (pane 2), display & night (dimming, auto-restart), fine-tuning.',
      'Untere Leiste: bis 4 Buttons – Standard-Tabs und/oder einzelne Kategorien bzw. Räume als Abkürzung. Der erste ist die Startseite.': 'Bottom bar: up to 4 buttons – standard tabs and/or individual categories or rooms as shortcuts. The first is the start page.',
      'Welche Räume dieses Panel zeigt. Nichts angehakt = alle.': 'Which rooms this panel shows. Nothing ticked = all.',
      'Welche Kategorien im Tab „Kategorien" erscheinen.': 'Which categories appear in the “Categories” tab.',
      'Einzelne Kacheln umbenennen, färben, Icon setzen oder ausblenden.': 'Rename, color, set an icon for or hide individual tiles.',
      'Name/Fenstertitel dieses Panel-Profils.': 'Name/window title of this panel profile.',
      'Wie eine aktive Kachel hervorgehoben wird (Rahmen, Füllung, Deckkraft).': 'How an active tile is highlighted (border, fill, opacity).',
      'Zugang zum Loxone Miniserver (Host, Benutzer, Passwort). HTTPS/443.': 'Access to the Loxone Miniserver (host, user, password). HTTPS/443.',
      'iCal-Abo + Feiertags-iCal, Wetter (Loxone-Wetterserver, sonst Open-Meteo mit dem Standort des Miniservers).': 'iCal subscription + holiday iCal, weather (Loxone weather server, otherwise Open-Meteo with the Miniserver location).',
      'Audioserver-Live-Daten (Cover/Titel/Favoriten), Direktkanal-Option.': 'Audio server live data (cover/title/favorites), direct-channel option.',
      'Kamerabilder und Klingel-Popup je Intercom-Baustein.': 'Camera images and doorbell popup per intercom block.',
      'Welche Visu welches Gerät zeigt: Online-Status, Ansicht wechseln, Betriebsmodus-Automatik.': 'Which view each device shows: online status, switch view, operating-mode automation.',
      'Start-URL für ein Android/Tablet erzeugen oder Agent per SSH aufs Linux-Panel.': 'Generate a start URL for an Android/tablet or deploy the agent via SSH onto the Linux panel.',
      'Wandpanels · ein Pane': 'Wall panels · one pane',
      'Breite Wandpanels · zwei Panes': 'Wide wall panels · two panes',
      'Tablets · zwei Panes': 'Tablets · two panes',
      '480×480 · Android 11 / Debian 11 · WLAN oder LAN/PoE': '480×480 · Android 11 / Debian 11 · Wi-Fi or LAN/PoE',
      '4,7″ · Hochformat 76×120 mm': '4.7″ · portrait 76×120 mm',
      '~1024×600 / 1280×800 · Android · quer oder hochkant': '~1024×600 / 1280×800 · Android · landscape or portrait',
      'Natives Format, 1:1. Android gesperrt → Fully Kiosk per adb. 2 Relais onboard.': 'Native format, 1:1. Android locked → Fully Kiosk via adb. 2 relays onboard.',
      'Quadratisch, höher aufgelöst – das 480×480-Pane wird sauber auf 720² gezoomt.': 'Square, higher resolution – the 480×480 pane is cleanly zoomed to 720².',
      'Anderer Formfaktor als die quadratischen 4″-Panels: höher als breit. Ein Pane, gezoomt.': 'A different form factor than the square 4″ panels: taller than wide. One pane, zoomed.',
      'Breites Gerät (~2:1): ein Gerät mit zwei 480×480-Panes nebeneinander. Wie zwei 4″-Displays in einem Rahmen.': 'Wide device (~2:1): one device with two 480×480 panes side by side. Like two 4″ displays in one frame.',
      'Zwei Panes (Visu + Widget) – quer nebeneinander, hochkant übereinander – oder Zoom auf den ganzen Schirm.': 'Two panes (view + widget) – side by side in landscape, stacked in portrait – or zoom to the whole screen.',
      'Referenz': 'Reference',
      '1 Pane · Fix': '1 pane · fixed',
      '1 Pane · Zoom': '1 pane · zoom',
      '2 Panes · LAN/PoE': '2 panes · LAN/PoE',
      '2 Panes / Zoom': '2 panes / zoom',
      'Zuerst die Bauform: ein einzelnes 4″-Panel oder ein breites 2-Pane-Gerät. Darunter das Kachel-Raster (2×2 · 3×2 · 2×3 · 3×3) — es bestimmt nur, wie viele Kacheln je Seite passen.': 'First the form: a single 4″ panel or a wide 2-pane device. Below it the tile grid (2×2 · 3×2 · 2×3 · 3×3) — it only determines how many tiles fit per page.',
      'Wie das Panel befüllt wird.': 'How the panel is filled.',
      'Aussehen für das ganze Panel — später je Kachel übersteuerbar.': 'Appearance for the whole panel — overridable per tile later.',
      'Auf dem Tablet steht neben bzw. unter der Uhr Platz für ein Widget (die zweite Spalte): quer rechts, hochkant unter Uhr und Wetter.': 'On the tablet there is room beside or below the clock for a widget (the second column): landscape right, portrait below clock and weather.',
      'Anzeige & Kachel-Raster': 'Display & tile grid',
      'Seiten befüllen': 'Fill pages',
      'Screensaver — Uhr-Seite': 'Screensaver — clock page',
      'Der Widget-Katalog': 'The widget catalog',
      'Schritt 1 / 8': 'Step 1 / 8',
      'Schritt 2 / 8': 'Step 2 / 8',
      'Schritt 3 / 8': 'Step 3 / 8',
      'Schritt 4 / 8': 'Step 4 / 8',
      'Schritt 5 / 8': 'Step 5 / 8',
      'Schritt 6 / 8': 'Step 6 / 8',
      'Schritt 7 / 8': 'Step 7 / 8',
      'Schritt 8 / 8': 'Step 8 / 8',
      'Freie Auswahl — bis 4 Seiten': 'Free selection — up to 4 pages',
      'Deckkraft': 'Opacity',
      'Positionsring': 'Position ring',
      'Deine Loxone-Controls': 'Your Loxone controls',
      'Fertige Inhaltsfläche': 'Ready-made content area',
      'Wetter, Kalender, Audio, Energiefluss, Kamera, Verlauf oder Werte — eine ganze Ansicht statt einzelner Kacheln.': 'Weather, calendar, audio, energy flow, camera, history or values — a whole view instead of individual tiles.',
      '＋ Neues Panel einrichten starten': '＋ Start setting up a new panel',
      'Einrichtungsassistent': 'Setup assistant',
      'unterstützte Geräte': 'Supported devices',
      // --- Widget-Terminologie (Pane 2 / Screensaver / eigener Tab) ---
      'Widget (Pane 2)': 'Widget (Pane 2)',
      'Widget je Tab': 'Widget per tab',
      'Visu + Widget je Tab.': 'View + widget per tab.',
      'Widget': 'Widget',
      'Widget (Vollbild)': 'Widget (full screen)',
      'Kein Widget (Screen füllen)': 'No widget (fill screen)',
      'Seiteninhalt': 'Page content',
      'Freie Seiten — bis 4, je Name, Icon & Inhalt (Kacheln oder Widget)':
        'Free pages — up to 4, each with name, icon & content (tiles or widget)',
      'Bausteine (Kacheln)': 'Blocks (tiles)',
      'Baustein': 'Block',
      'Musikzone': 'Music zone',
      'Keine Musikzone in der Anlage.': 'No music zone in the system.',
      'Diese Seite zeigt das Widget über die ganze Fläche (Vollbild-Tab) — auch am 1-Pane-Gerät. Baustein/Zone wählst du oben direkt.':
        'This page shows the widget across the whole area (full-screen tab) — on a 1-pane display too. You pick the block/zone directly above.',
      'Audio/Energiefluss/Kamera/Verlauf erscheinen hier nur, wenn ein passender Baustein vorhanden ist.':
        'Audio/energy flow/camera/history only appear here if a matching block exists.',
      'Kein passender Baustein': 'No matching block',
      'Werte': 'Values',
      'Über den Kacheln': 'Above the tiles',
      'Kopfzeile': 'Header row',
      'Kopfzeile (Uhr, Wetter, Werte)': 'Header row (clock, weather, values)',
      'Ohne Werte zeigt die Kopfzeile Uhr und Wetter.': 'Without values the header row shows clock and weather.',
      'Werte als Leiste über den Kacheln': 'Values as a strip above the tiles',
      'Mehr passt nicht in die Zeile.': 'No more fit in the row.',
      'Kopfzeile je Tab': 'Header row per tab',
      'Keine': 'None',
      'Am 1-Pane-Gerät gibt es kein Widget daneben, aber die Kopfzeile über den Kacheln: Uhr, Wetter und nach Wahl Werte (Werte wählst du im Editor).': 'A 1-pane device has no widget beside the tiles, but it can have the header row above them: clock, weather and optional values (pick the values in the editor).',
      'Split ist aus: ein Widget daneben gibt es nicht, die Kopfzeile über den Kacheln schon.': 'Split is off: there is no widget beside the tiles, but the header row above them is available.',
      'Audio': 'Audio',
      'Miniserver': 'Miniserver',
      '„Automatisch" vergrößert die Visu auf jedem Gerät so weit, wie es ohne Rand geht. „Wie Vorgabe" erbt den Wert aus den Vorgaben.':
        '“Automatic” enlarges the visu on each device as far as it goes without a border. “Same as default” inherits the value from the defaults.',
      // --- Nachgezogen: Assistent, Displays, Betriebsmodus, restliche Admin-UI ---
      "Standard-Farbschema": "Default color scheme",
      "Eine Farbe wählen — Hintergrund, Kacheln, Leiste, Schrift, Icons und Zustandsfarben werden daraus berechnet. Eigene Zustandsfarben behalten Vorrang.": "Pick a color — background, tiles, bar, text, icons and state colors are derived from it. Custom state colors keep priority.",
      "Eigene Farbe": "Custom color",
      "Keine": "None",
      "Standard-Aussehen für alle Ansichten. Einzelne Ansichten überschreiben es unter „Aussehen\".": "Default look for all views. Individual views override it under „Appearance“.",
      "Du bearbeitest": "You are editing",
      "Raum-Ansicht": "Room view",
      "Klassisch": "Classic",
      "Eigene Auswahl": "Custom selection",
      "Ein Raum ist die Startseite — das Gerät wacht direkt in diesem Raum auf (Licht &amp; Beschattung sofort bedienbar), ohne vorher zu wählen. Ideal für kleine 4″-Wandpanels. Die untere Leiste zeigt automatisch die im Raum vorkommenden Kategorien — ein Tipp scrollt zu den passenden Bausteinen oder zeigt nur sie (Einstellung unten).": "A room is the start page — the device wakes up directly in this room (light &amp; shading usable at once), without choosing first. Ideal for small 4″ wall panels. The bottom bar automatically shows the categories present in the room — a tap scrolls to the matching blocks or shows only them (setting below).",
      "Dieser Raum": "This room",
      "Kategorie-Tabs (unten)": "Category tabs (bottom)",
      "Automatisch": "Automatic",
      "Bis zu 4 Kategorien als untere Tabs. Vorausgewählt sind die ersten im Raum — du kannst sie ändern. „Automatisch\" folgt wieder dem Rauminhalt.": "Up to 4 categories as bottom tabs. The first ones in the room are preselected — you can change them. „Automatic“ follows the room content again.",
      "Bis zu <b>4 Buttons</b> — die 4 Standard-Tabs, die <b>eigene Auswahl</b> und/oder einzelne Kategorien (gestrichelt) bzw. Räume (gepunktet). <b>Die Reihenfolge des Anklickens ist die Reihenfolge in der Leiste</b> (1., 2., …), der erste ist die Startseite (★). ": "Up to <b>4 buttons</b> — the 4 standard tabs, the <b>custom selection</b> and/or individual categories (dashed) or rooms (dotted). <b>The click order is the order in the bar</b> (1., 2., …), the first one is the start page (★). ",
      "Aussehen": "Appearance",
      "Layout": "Layout",
      "Split / Pane 2": "Split / Pane 2",
      "Screensaver (Uhr-Seite)": "Screensaver (clock page)",
      "Display &amp; Nacht": "Display &amp; night",
      "Feinjustierung": "Fine-tuning",
      "In der LoxPanel-App senkt „Nachts abdunkeln“ die echte Display-Helligkeit, statt das Bild abzudunkeln – mit derselben Wirkung, aber ohne grau leuchtendes Schwarz. Ist am Gerät die automatische Helligkeit an, dunkelt die Visu wie im Browser ab.": "In the LoxPanel app, “Dim at night” lowers the real display brightness instead of darkening the picture – with the same effect, but without black glowing grey. If automatic brightness is on in the device, the view dims as in a browser.",
      "Wie eine Kachel im <b>aktiven Zustand</b> hervorgehoben wird (an = Akzent, ok = grün, kritisch = rot): Rahmen, Füllung und Deckkraft. Die <b>Farbe</b> kommt je Zustand aus dem Theme, hier stellst du das <b>Aussehen</b> ein. Darunter der Rahmen der <b>inaktiven</b> Kacheln <b>und der rechten Panes</b> (Pane 2, z. B. Energieflussmonitor, Wetter, Kalender) – Deckkraft und Breite hochdrehen, falls er auf hellen Displays (z. B. Shelly) kaum sichtbar ist. Gilt für diese Ansicht — einzelne Kacheln können unten abweichen.": "How a tile is highlighted in the <b>active state</b> (on = accent, ok = green, critical = red): border, fill and opacity. The <b>color</b> comes from the theme per state, here you set the <b>look</b>. Below, the border of the <b>inactive</b> tiles <b>and the right panes</b> (pane 2, e.g. energy flow monitor, weather, calendar) – turn opacity and width up if it is barely visible on bright displays (e.g. Shelly). Applies to this view — individual tiles can differ below.",
      "Inhalt": "Content",
      "Kein Energieflussmonitor in der Anlage.": "No energy flow monitor in the system.",
      "Kein Intercom-Baustein in der Anlage.": "No intercom block in the system.",
      "Kein Baustein mit Aufzeichnung in der Anlage.": "No block with logging in the system.",
      "Bausteine": "Blocks",
      "＋ hinzufügen …": "＋ add …",
      "Mehr passt nicht auf die Seite.": "No more fit on the page.",
      "Werte unter dem Bild": "Values below the image",
      "Keine – das Bild steht allein.": "None – the image stands alone.",
      "Noch nichts gewählt – oben hinzufügen.": "Nothing selected yet – add above.",
      "Keine Räume verfügbar.": "No rooms available.",
      "Die zusammengestellte Tab-Leiste geht dabei verloren. Fortfahren?": "The assembled tab bar will be lost. Continue?",
      "Keine Räume": "No rooms",
      "Keine Kategorien im Raum": "No categories in the room",
      "Seite": "Page",
      "Seite hinzufügen": "Add page",
      "kein": "none",
      "Icon suchen…": "Search icon…",
      "Raum": "Room",
      "Alle Räume": "All rooms",
      "Suche": "Search",
      "Baustein suchen…": "Search block…",
      "Alle Bausteine liegen im selben Raum – die untere Leiste bleibt darum ohne Sprungmarken.": "All blocks are in the same room – the bottom bar therefore stays without jump marks.",
      "Untere Leiste in der Visu – ein Tipp scrollt zur Gruppe:": "Bottom bar in the visu – a tap scrolls to the group:",
      "Tipp auf eine Sprungmarke": "Tapping a jump mark",
      "Springen – zur Gruppe scrollen": "Jump – scroll to the group",
      "Filtern – nur diese Gruppe zeigen": "Filter – show only this group",
      "Springen: die Kacheln der Gruppe leuchten kurz auf. Filtern: ein zweiter Tipp auf dieselbe Marke zeigt wieder alle, ebenso eine Minute ohne Bedienung.": "Jump: the group's tiles light up briefly. Filter: a second tap on the same mark shows everything again, as does a minute without use.",
      "Untere Leiste in der Visu – ein Tipp zeigt nur diese Gruppe:": "Bottom bar in the visu – a tap shows only this group:",
      "Springen": "Jump",
      "Filtern": "Filter",
      "Zur Gruppe scrollen, die Kacheln leuchten kurz auf.": "Scroll to the group, its tiles light up briefly.",
      "Nur die Kacheln dieser Gruppe zeigen, ein zweiter Tipp zeigt wieder alle.": "Show only this group's tiles, a second tap shows everything again.",
      "Sprungmarken": "Jump marks",
      "In die Leiste passen 4 Sprungmarken – die Bausteine der weiteren Räume stehen trotzdem auf der Seite.": "The bar holds 4 jump marks – the blocks of the other rooms are still on the page.",
      "Fertig": "Done",
      "Name der Seite": "Page name",
      "Auswahl": "Selection",
      "Weiter": "Next",
      "Zurück": "Back",
      "Die Seite": "The page",
      "zeigt": "shows",
      "aus": "from",
      "Räumen": "rooms",
      "gewählter Baustein ist in dieser Ansicht ausgeblendet und erscheint nicht.": "selected block is hidden in this view and does not appear.",
      "gewählte Bausteine sind in dieser Ansicht ausgeblendet und erscheinen nicht.": "selected blocks are hidden in this view and do not appear.",
      "Icon der Seite": "Page icon",
      "ausgeblendet": "hidden",
      "Bibliothek": "Library",
      "Suchen… z. B. light, blind, alarm": "Search… e.g. light, blind, alarm",
      "Keine Loxone-Bibliothek gefunden — LoxoneIcons-Plugin installiert und gemountet?": "No Loxone library found — is the LoxoneIcons plugin installed and mounted?",
      "weitere — Suche eingrenzen": "more — narrow the search",
      "Nichts gefunden.": "Nothing found.",
      "Audio/Energie/Kamera/Verlauf nehmen automatisch den ersten passenden Baustein — den genauen wählst du bei Bedarf im Editor.": "Audio/energy/camera/history automatically take the first matching block — you pick the exact one in the editor if needed.",
      "Keine Räume gefunden": "No rooms found",
      "Sprungtabs — Kategorien des Raums": "Jump tabs — categories of the room",
      "max 4, leer = automatisch": "max 4, empty = automatic",
      "Für diesen Raum sind keine Kategorien hinterlegt.": "No categories are defined for this room.",
      "Standard-Tabs — an/aus": "Standard tabs — on/off",
      "Freie Seiten — bis 4, je Name, Icon & Kacheln": "Free pages — up to 4, each with name, icon & tiles",
      "Seitenname": "Page name",
      "Kacheln": "Tiles",
      "Noch keine Kacheln — links Raum wählen, dann rechts Bausteine.": "No tiles yet — pick a room on the left, then blocks on the right.",
      "Ohne Raum": "No room",
      "Keine Bausteine gefunden.": "No blocks found.",
      "Nächsten Tab befüllen": "Fill next tab",
      "Übersicht": "Overview",
      "Baustein suchen (alle Räume)…": "Search block (all rooms)…",
      "Grundfarbe": "Base color",
      "Eine Farbe wählen — Hintergrund, Kacheln, Leiste, Schrift und Icons werden daraus berechnet. Leer = Standard.": "Pick a color — background, tiles, bar, text and icons are derived from it. Empty = default.",
      "Größen & Schrift": "Sizes & font",
      "Klassische Visu": "Classic view",
      "Freie Auswahl": "Custom selection",
      "2 Panes": "2 panes",
      "1 Pane · 4″": "1 pane · 4″",
      "Raster": "Grid",
      "Design": "Design",
      "Einheitlich": "Uniform",
      "Individuell": "Individual",
      "Seiten": "Pages",
      "Angepasst": "Customized",
      "Automatik": "Automatic",
      "Energiefluss": "Energy flow",
      "Kamera": "Camera",
      "Screensaver": "Screensaver",
      "Schritt": "Step",
      "Anzahl Panes": "Number of panes",
      "1 Pane — 4″ Wandpanel": "1 pane — 4″ wall panel",
      "Ein Pane, nur die Visu.": "One pane, just the view.",
      "2 Panes — Tablet / Breitbild": "2 panes — tablet / widescreen",
      "Visu + Widget je Tab – quer rechts, hochkant darunter.": "View + widget per tab – to the right in landscape, below in portrait.",
      "Kachel-Raster — frei wählbar": "Tile grid — freely selectable",
      "Wie möchtest du befüllen?": "How do you want to fill it?",
      "Ein Raum aus Loxone + Kategorien als Sprungtabs.": "One room from Loxone + categories as jump tabs.",
      "Standard-Tabs (Favoriten/Zentral/Räume/Kategorien).": "Standard tabs (Favorites/Central/Rooms/Categories).",
      "Eigene Seiten mit handverlesenen Kacheln (bis 4).": "Custom pages with hand-picked tiles (up to 4).",
      "Wie sollen die Kacheln aussehen?": "How should the tiles look?",
      "Einheitliches Design": "Uniform design",
      "Kachelgrößen und Schrift aus den Vorgaben. Später einzeln übersteuerbar.": "Tile sizes and font from the defaults. Overridable individually later.",
      "Individuell je Kachel": "Individual per tile",
      "Farbe, Schrift & Icon je Kachel — im Editor.": "Color, font & icon per tile — in the editor.",
      "Aktiv-Overlay — wie eine aktive Kachel hervorgehoben wird": "Active overlay — how an active tile is highlighted",
      "Gilt für die ganze Ansicht; einzelne Kacheln kannst du später im Editor abweichend einstellen.": "Applies to the whole view; individual tiles can differ later in the editor.",
      "z. B. Wohnzimmer": "e.g. Living room",
      "Kennung": "Identifier",
      "Aufruf am Gerät:": "Open on the device:",
      "Am 4″-Wandpanel ist die Uhr-Seite einspaltig (Uhr + automatisch Termine/Wetter) — keine zweite Spalte.": "On the 4″ wall panel the clock page is single-column (clock + automatic events/weather) — no second column.",
      "Uhr-Seite — zweite Fläche (quer rechts, hochkant unten)": "Clock page — second area (right in landscape, below in portrait)",
      "Automatik (Termine/Wetter)": "Automatic (events/weather)",
      "Aus — nur Uhr": "Off — clock only",
      "Statuswerte (mehrere Bausteine) für diese Fläche legst du danach im Editor fest.": "Status values (multiple blocks) for this area are set afterwards in the editor.",
      "Energiefluss/Kamera/Verlauf erscheinen hier nur, wenn ein passender Baustein vorhanden ist.": "Energy flow/camera/history appear here only if a matching block exists.",
      "Zusammenfassung": "Summary",
      "Nach „Ansicht anlegen\" bist du im Editor zum Feinschliff (Kacheln, Pane 2, Icons) und kannst die Ansicht über „Visu öffnen\" testen.": "After „Create view“ you are in the editor for fine-tuning (tiles, pane 2, icons) and can test the view via „Open view“.",
      "Ansicht anlegen ✓": "Create view ✓",
      "Weiter →": "Next →",
      "gibt es schon.": "already exists.",
      "Erkannte Audioserver:": "Detected audio servers:",
      "Kein Audioserver in der Loxone-Struktur gefunden.": "No audio server found in the Loxone structure.",
      "— kein Auslöser (Sonnenuntergang) —": "— no trigger (sunset) —",
      "Kein Kalender konfiguriert.": "No calendar configured.",
      "Termine": "Events",
      "Fehler:": "Error:",
      "Kalender geladen": "Calendar loaded",
      "Automatisch vom Miniserver:": "Automatically from the Miniserver:",
      "Wetter vom Loxone-Wetterserver": "Weather from the Loxone weather server",
      "Open-Meteo wird nicht abgefragt.": "Open-Meteo is not queried.",
      "Wetter geladen": "Weather loaded",
      "Standort vom Miniserver wird verwendet.": "The Miniserver location is used.",
      "Kein Standort konfiguriert.": "No location configured.",
      "Visu offen": "View open",
      "Ansicht wechseln": "Switch view",
      "Neu laden": "Reload",
      "Display aus": "Display off",
      "Display an": "Display on",
      "Browser": "Browser",
      "Ansicht": "View",
      "Ohne Kennung": "No identifier",
      "Gerätename": "Device name",
      "Namen vergeben": "Assign name",
      "Noch kein Gerät gefunden. Ein Gerät erscheint, sobald es die Visu mit ?device=<name> öffnet oder der Agent darauf läuft.": "No device found yet. A device appears as soon as it opens the view with ?device=<name> or the agent runs on it.",
      "Geräte ohne Kennung. Das Gerät zeigt seinen Code unter „Dieses Gerät einrichten“ – hier daneben den Namen vergeben, damit das Gerät dauerhaft gelistet und per Betriebsmodus umgeschaltet werden kann.": "Devices without an identifier. The device shows its code under \"Set up this device\" – enter the name next to it here so the device is listed permanently and can be switched by operating mode.",
      "Code": "Code",
      "Gerät nicht erreicht": "Device not reached",
      "Bitte einen Namen eingeben": "Please enter a name",
      "Schließen": "Close",
      "Verbunden, aber noch ohne Namen – erst benennen, dann auswählen:": "Connected but not named yet – name it first, then select it:",
      "✓ Name vergeben – das Gerät verbindet sich neu und erscheint gleich oben:": "✓ Name assigned – the device reconnects and will appear above shortly:",
      "Display-Steuerung": "Display control",
      "keine (nur über die Seite)": "none (only via the page)",
      "Passwort (Fully)": "Password (Fully)",
      "Display-Kennwort nicht übernommen, weil Host oder Treiber geändert:": "Display password not kept because host or driver changed:",
      "Noch kein Gerät bekannt. Sobald ein Gerät die Visu mit Kennung öffnet oder ein Agent läuft, erscheint es hier.": "No device known yet. As soon as a device opens the view with an identifier or an agent runs, it appears here.",
      "Für welche Geräte?": "For which devices?",
      "Noch kein Gerät bekannt. Ein Gerät muss die Visu einmal mit ?device=<name> öffnen oder einen Agent haben.": "No device known yet. A device must open the visu once with ?device=<name> or have an agent.",
      "Die Modus-Zuordnung gilt für alle gewählten Geräte gleich. Feinabstimmung je Gerät danach in der Detail-Tabelle.": "The mode assignment applies equally to all selected devices. Fine-tune per device afterwards in the detail table.",
      "Welche Betriebsmodi?": "Which operating modes?",
      "Loxone sendet": "Loxone sends",
      "Eigener Modus": "Custom mode",
      "z. B. Kino": "e.g. Cinema",
      "Hinzufügen": "Add",
      "Welche Ansicht bei welchem Modus?": "Which view for which mode?",
      "„Unverändert lassen\" heißt: dieser Modus schaltet das Gerät nicht um.": "„Leave unchanged“ means: this mode does not switch the device.",
      "Keine Zuordnung gewählt — es würde nichts umgeschaltet.": "No assignment chosen — nothing would be switched.",
      "Fertig — in Loxone einrichten": "Done — set up in Loxone",
      "Lege in Loxone Config je Betriebsart einen virtuellen HTTP-Ausgang mit dieser Adresse an (der Modusname am Ende zählt):": "In Loxone Config, create a virtual HTTP output per operating mode with this address (the mode name at the end matters):",
      "Adressen kopieren": "Copy addresses",
      "Zuordnung": "Assignment",
      "Geräte:": "Devices:",
      "„Übernehmen\" speichert das für alle gewählten Geräte.": "„Apply“ saves this for all selected devices.",
      "Übernehmen ✓": "Apply ✓",
      "✓ Betriebsmodus gespeichert": "✓ Operating mode saved",
      "Gerätename und Server-Adresse nötig": "Device name and server address required",
      "Welche Ansicht welches Gerät zeigt. Linux-Geräte mit Agent melden sich automatisch; Android-Wandpanels und Tablets erscheinen, sobald sie die Visu mit einer Gerätekennung öffnen (?panel=<start>&device=<name>). Ein neues Gerät verbindet und bestückt ＋ Gerät einrichten.": "Which view each device shows. Linux devices with an agent register automatically; Android wall panels and tablets appear as soon as they open the view with a device ID (?panel=<start>&device=<name>). ＋ Set up device connects and fills a new device.",
      "Geräte & Ansicht": "Devices & view",
      "Je Gerät die Ansicht wählen und live umschalten. Geräte ohne Kennung stehen unten und bekommen hier einen Namen.": "Pick the view per device and switch live. Devices without an identifier are listed below and get a name here.",
      "🧭 Betriebsmodus-Assistent": "🧭 Operating-mode assistant",
      "Geführt: Modi → Ansicht je Gerät, mit fertiger Loxone-Adresse.": "Guided: modes → view per device, with a ready Loxone address.",
      "Betriebsmodus-Automatik & Display-Steuerung": "Operating-mode automation & display control",
      "Ansicht je Loxone-Betriebsmodus automatisch wechseln; Fully/WallPanel-Display schalten.": "Automatically switch view per Loxone operating mode; control Fully/WallPanel display.",
      "Display-Steuerung je Gerät: Bei Fully Kiosk die Remote-Admin-Schnittstelle einschalten (Port 2323, Passwort), bei WallPanel den HTTP-Server (Port 2971). Der Server schaltet das Display dann auch bei Klingel, Wecker, Notify und Goto ein und nach der Abschaltzeit aus, unabhängig von der Seite.": "Display control per device: for Fully Kiosk enable the remote admin interface (port 2323, password), for WallPanel the HTTP server (port 2971). The server then also turns the display on for doorbell, alarm, notify and goto, and off after the timeout, regardless of the page.",
      "Präsenzmelder": "Presence sensor",
      "— keiner (Display nach der Leerlaufzeit aus) —": "— none (display off after the idle time) —",
      "nicht in der Struktur": "not in the structure",
      "gerade: jemand da": "now: someone present",
      "gerade: Raum leer": "now: room empty",
      "Präsenzmelder je Gerät: Solange der gewählte Baustein jemanden meldet (z.B. der Präsenzmelder des Raums), bleibt das Display hell und die Leerlaufzeit ist ausgesetzt; wird der Raum leer, geht es aus. Wirkt mit der LoxPanel-App, mit Fully Kiosk (JavaScript-Schnittstelle oder Remote Admin) und WallPanel, nicht bei Linux-Geräten mit Agent.": "Presence sensor per device: while the chosen block reports someone (e.g. the room's presence sensor), the display stays bright and the idle timeout is suspended; when the room is empty, it turns off. Works with the LoxPanel app, Fully Kiosk (JavaScript interface or Remote Admin) and WallPanel, not on Linux devices with an agent.",
      "Nachtmodus": "Night mode",
      "Wann die Geräte abdunkeln. Ohne Auslöser entscheidet der Sonnenuntergang — die Zeiten kommen vom Miniserver, ersatzweise vom Wetterdienst. Als Auslöser lässt sich jeder Baustein mit Ein/Aus-Zustand wählen; sein Ein-Zustand bedeutet Nacht. Damit auch ein Loxone-Betriebsmodus, sobald er in Loxone Config auf einen Status-Baustein mit Raum und Kategorie gelegt ist — der Modus selbst steht nicht in der Visu.": "When the devices dim. Without a trigger, sunset decides — the times come from the Miniserver, or from the weather service as a fallback. Any block with an on/off state can be a trigger; its on state means night. That includes a Loxone operating mode, once it is mapped in Loxone Config to a status block with room and category — the mode itself is not in the view.",
      "Auslöser (optional)": "Trigger (optional)",
      "Port": "Port",
      "Weckton-Test und Audioserver-Live-Daten (Cover/Titel/Favoriten).": "Alarm-tone test and audio-server live data (cover/title/favorites).",
      "Audioserver (Cover / Titel / Favoriten)": "Audio server (cover / title / favorites)",
      "Loxone-Audioserver (Gen 2) liefern Cover/Titel/Interpret und Favoriten über einen eigenen Live-Kanal (Audioprotokoll, Port 7091) — genau wie die Loxone-App. LoxPanel abonniert diesen Kanal und legt die Infos über die passende Zone. Die Audioserver-Adresse wird automatisch aus der Loxone-Struktur erkannt — keine IP-Eingabe nötig. Funktioniert mit dem originalen Loxone-Audioserver ebenso wie mit Nachbauten (Sonn/Audioserver4Home). Musikserver-/MS4H-Zonen bleiben unberührt (die liefern es ohnehin).": "Loxone audio servers (Gen 2) deliver cover/title/artist and favorites over their own live channel (audio protocol, port 7091) — just like the Loxone app. LoxPanel subscribes to this channel and overlays the info onto the matching zone. The audio-server address is detected automatically from the Loxone structure — no IP entry needed. Works with the original Loxone audio server as well as with clones (Sonn/Audioserver4Home). Music-server/MS4H zones stay untouched (they deliver it anyway).",
      "Audioserver-Live-Daten abonnieren (automatisch)": "Subscribe to audio-server live data (automatic)",
      "Zwei Wege: ein Android-Wandpanel oder Tablet mit Kiosk-App bekommt nur eine Start-URL; ein Linux-Gerät bekommt den Agenten per SSH.": "Two ways: an Android wall panel or tablet with a kiosk app only gets a start URL; a Linux device gets the agent via SSH.",
      "Android-Wandpanel oder Tablet (Kiosk-App)": "Android wall panel or tablet (kiosk app)",
      "Start-URL in Fully Kiosk Browser oder WallPanel eintragen. Der Gerätename sorgt dafür, dass das Gerät unter Geräte erscheint und per Betriebsmodus umgeschaltet werden kann. Display-Abschaltung: bei Fully die JavaScript-Schnittstelle einschalten oder oben einen Display-Treiber eintragen. Details in deploy/ANDROID.md.": "Enter the start URL in Fully Kiosk Browser or WallPanel. The device name ensures the device appears under Devices and can be switched by operating mode. Display shutoff: with Fully enable the JavaScript interface or enter a display driver above. Details in deploy/ANDROID.md.",
      "Start-URL erzeugen": "Generate start URL",
      "Linux-Gerät mit Agent (SSH)": "Linux device with agent (SSH)",
      // Rahmen / Navigation
      'Einstellungen': 'Settings',
      // Rubriken und Seitenleiste: Ansicht = was ein Geraet zeigt, Geraet = das Geraet selbst
      'Ansichten': 'Views',
      'Geräte': 'Devices',
      'Erprobte Hardware': 'Tested hardware',
      'Einrichtungsassistent': 'Setup assistant',
      'Vorgaben': 'Defaults',
      // Eine Speicherleiste fuer alles (Schritt 2)
      'Nicht gespeichert:': 'Not saved:',
      'Alles gespeichert': 'Everything saved',
      'Gespeichert:': 'Saved:',
      'Gelöscht:': 'Deleted:',
      'Ansicht löschen:': 'Delete view:',
      'Gilt sofort, ohne „Speichern“. Andere offene Änderungen bleiben offen.':
        'Takes effect at once, without “Save”. Other open changes stay open.',
      'Seine Einstellungen (Betriebsmodi, Display-Steuerung, Skalierung, Zielkachel, Präsenzmelder) gehen verloren. Gilt sofort, ohne „Speichern“; andere offene Änderungen bleiben offen.':
        'Its settings (operating modes, display control, scaling, target tile, presence sensor) will be lost. Takes effect at once, without “Save”; other open changes stay open.',
      'Ungespeicherte Änderungen gehen dabei verloren.': 'Unsaved changes will be lost.',
      // Reiter einer Ansicht (Schritt 3)
      'Allgemein': 'General',
      'Verhalten': 'Behaviour',
      'Untere Leiste': 'Bottom bar',
      'Kachel-Layout': 'Tile layout',
      'Mit dieser Kennung öffnet ein Gerät die Ansicht:': 'A device opens the view with this identifier:',
      'Widget, Kopfzeile, Werteleiste': 'Widget, header row, value strip',
      'Widget, Kopfzeile, Werteleiste dieser Seite': 'Widget, header row and value strip of this page',
      'Widget je Standard-Seite': 'Widget per standard page',
      'Freie Seiten (Eigene Auswahl) stellst du im Seiten-Editor ein.': 'Free pages (own selection) are set up in the page editor.',
      'Keine Standard-Seite in der Leiste. Freie Seiten stellst du im Seiten-Editor ein.': 'No standard page in the bar. Free pages are set up in the page editor.',
      'Zu Inhalt': 'To Content',
      // Geraetekarte (Schritt 4)
      'Eine Karte je Gerät: oben Zustand, Ansicht und Steuerung, aufgeklappt Betriebsmodi, Skalierung, Zielkachel, Präsenzmelder und Display-Steuerung. Änderungen speichert die Leiste unten.':
        'One card per device: state, view and controls at the top, expanded the operating modes, scaling, target tile, presence sensor and display control. The bar at the bottom saves changes.',
      'Geräte ohne Kennung': 'Devices without an identifier',
      'Start-Adresse oder Agent': 'Start address or agent',
      'Start-Adresse für App oder Tablet, Agent per SSH für Linux.': 'Start address for app or tablet, agent via SSH for Linux.',
      'So schaltet Loxone die Ansicht um': 'How Loxone switches the view',
      'Betriebsmodus, Display-Steuerung und Präsenzmelder erklärt.': 'Operating mode, display control and presence sensor explained.',
      'Wandpanels und Tablets, auf denen LoxPanel läuft.': 'Wall panels and tablets LoxPanel runs on.',
      'Betriebsmodi': 'Operating modes',
      'Am Gerät': 'On the device',
      'noch nicht gemeldet': 'not reported yet',
      'Konfiguration': 'Configuration',
      'Kamera / Türstation': 'Camera / Door station',
      'bald': 'soon',
      'Neues Gerät': 'New device',
      'Sicherung': 'Backup',
      'Einstellungen herunterladen': 'Download settings',
      'Alle Einstellungen dieses Servers als ZIP-Datei: Miniserver-Zugang, Kamera, Kalender, Ansichten, Geräte und Design.':
        'All settings of this server as a ZIP file: Miniserver access, camera, calendar, views, devices and design.',
      'Kennwörter (Miniserver, Kamera, Display-Treiber) sind nicht enthalten, weil der Download ohne Anmeldung möglich ist.':
        'Passwords (Miniserver, camera, display driver) are not included because the download needs no login.',
      'Sicherung einspielen': 'Restore backup',
      'Eine ZIP-Datei aus „Einstellungen herunterladen" wählen, auch von einem anderen LoxPanel. Sie ersetzt die Einstellungen dieses Servers; was nicht in der Sicherung steckt, bleibt. Eingetragene Kennwörter bleiben, solange ihr Ziel gleich bleibt (Miniserver: Host und Benutzer, Kamera: Adresse und Benutzer, Display: Host und Treiber); fehlende nennt das Ergebnis.':
        'Choose a ZIP file from “Download settings”, also from another LoxPanel. It replaces the settings of this server; whatever is not in the backup stays. Passwords already entered stay as long as their target stays the same (Miniserver: host and user, camera: address and user, display: host and driver); missing ones are listed in the result.',
      'ZIP-Datei wählen und einspielen': 'Choose ZIP file and restore',
      'Diagnose': 'Diagnostics',
      'Diagnose herunterladen': 'Download diagnostics',
      'Für die Fehlersuche: Version, Verbindungen zu Miniserver und Audioserver, alle Geräte, die Einstellungen und die letzten Log-Zeilen als ZIP-Datei, mit einer lesbaren Zusammenfassung (diagnose.md). Je Gerät gibt es das Paket auch unter Geräte.':
        'For troubleshooting: version, connections to Miniserver and Audio Server, all devices, the settings and the latest log lines as a ZIP file, with a readable summary (diagnose.md). Per device the package is also available under Devices.',
      'Kennwörter, Tokens, Kalender-Abos (bis auf den Host), Zugangsdaten in Adressen und der Standort sind entfernt.':
        'Passwords, tokens, calendar subscriptions (except the host), credentials in addresses and the location are removed.',
      'Die Sicherung ersetzt die Einstellungen dieses Servers. Am besten vorher „Einstellungen herunterladen“. Fortfahren?':
        'The backup replaces the settings of this server. Best “Download settings” first. Continue?',
      'Ungespeicherte Änderungen an Ansichten gehen dabei verloren.': 'Unsaved changes to views will be lost.',
      '✓ Eingespielt:': '✓ Restored:',
      'Nur teilweise eingespielt:': 'Only partly restored:',
      'Nicht eingespielt': 'Not restored',
      'Nicht eingespielt:': 'Not restored:',
      'Das ist keine ZIP-Datei.': 'This is not a ZIP file.',
      'Keine Datei erhalten.': 'No file received.',
      'Die Datei ist zu groß für eine LoxPanel-Sicherung.': 'The file is too large for a LoxPanel backup.',
      'Keine LoxPanel-Sicherung: In der ZIP-Datei steckt weder loxpanel.cfg noch panels.json noch theme.json.':
        'Not a LoxPanel backup: the ZIP file contains neither loxpanel.cfg nor panels.json nor theme.json.',
      'Miniserver: mit dem eingespielten Zugang neu verbunden.': 'Miniserver: reconnected with the restored access.',
      'Miniserver: Zugang unverändert, die Verbindung bleibt.': 'Miniserver: access unchanged, the connection stays.',
      'Miniserver: Kennwort fehlt – unter Einstellungen → Miniserver eintragen.': 'Miniserver: password missing – enter it under Settings → Miniserver.',
      'Miniserver: Die Sicherung enthält keinen Zugang, der bisherige bleibt.': 'Miniserver: the backup holds no access, the current one stays.',
      'Miniserver: Der Zugang kommt hier aus den Umgebungsvariablen und bleibt.': 'Miniserver: access comes from the environment variables here and stays.',
      'Miniserver: Verbindung mit dem eingespielten Zugang fehlgeschlagen:': 'Miniserver: connecting with the restored access failed:',
      'Miniserver: weder in der Sicherung noch hier eingetragen – unter Einstellungen → Miniserver eintragen.':
        'Miniserver: neither in the backup nor set up here – enter it under Settings → Miniserver.',
      'Miniserver: Für {ziel} aus der Sicherung fehlt das Kennwort, der bisherige Zugang bleibt. Zum Wechseln unter Einstellungen → Miniserver mit Kennwort eintragen.':
        'Miniserver: the password for {ziel} from the backup is missing, the current access stays. To switch, enter it with its password under Settings → Miniserver.',
      'Miniserver: Verbindung mit dem eingespielten Zugang fehlgeschlagen, der bisherige Zugang bleibt:':
        'Miniserver: connecting with the restored access failed, the current access stays:',
      'Miniserver: Benutzer fehlt – unter Einstellungen → Miniserver eintragen.': 'Miniserver: user missing – enter it under Settings → Miniserver.',
      'Miniserver: Für {ziel} aus der Sicherung fehlt der Benutzer, der bisherige Zugang bleibt. Zum Wechseln unter Einstellungen → Miniserver vollständig eintragen.':
        'Miniserver: the user for {ziel} from the backup is missing, the current access stays. To switch, enter the complete access under Settings → Miniserver.',
      'Kennwort fehlt, bitte unter Einstellungen eintragen:': 'Password missing, please enter it under Settings:',
      'Kennwort von diesem Server übernommen:': 'Password kept from this server:',
      'Nicht in der Sicherung, unverändert:': 'Not in the backup, unchanged:',
      'Bitte die Seite neu laden, damit der Konfigurator den eingespielten Stand zeigt.': 'Please reload the page so the configurator shows the restored settings.',
      'Kamera': 'Camera',
      'Display-Treiber': 'Display driver',
      '＋ Neue Ansicht': '＋ New view',
      'Panels & Kacheln': 'Panels & tiles',
      'Ansichten gestalten': 'Design views',
      'Panels · Miniserver · Intercom': 'Panels · Miniserver · Intercom',
      'Visu öffnen': 'Open visu',
      'Visu im Browser anzeigen': 'Show the visu in the browser',
      // Miniserver
      'Zugang zum Loxone Miniserver. Nach dem Speichern verbindet der Server sofort neu.':
        'Access to the Loxone Miniserver. Reconnects immediately after saving.',
      'Host / IP': 'Host / IP',
      'Benutzer': 'User',
      'Passwort': 'Password',
      'unverändert lassen': 'leave unchanged',
      'Zertifikat prüfen (Gen2 mit selbstsigniertem Zertifikat: aus)':
        'Verify certificate (Gen2 with self-signed cert: off)',
      'Verbinden & Speichern': 'Connect & save',
      // --- Ersteinrichtung: ohne Struktur zuerst der Miniserver ---
      'Zuerst den Miniserver verbinden': 'Connect the Miniserver first',
      'Ohne Verbindung kennt LoxPanel weder Räume noch Bausteine. Adresse, Benutzer und Passwort eintragen, dann „Verbinden & Speichern“. Danach sind alle Bereiche offen.':
        'Without a connection LoxPanel knows neither rooms nor blocks. Enter address, user and password, then “Connect & save”. After that all sections are open.',
      'Erst den Miniserver verbinden': 'Connect the Miniserver first',
      'Noch kein Miniserver eingetragen.': 'No Miniserver entered yet.',
      'Der gespeicherte Zugang ist nicht verbunden. Angaben prüfen und erneut „Verbinden & Speichern“.':
        'The saved access is not connected. Check the entries and “Connect & save” again.',
      'Verbindung zu {host} wird aufgebaut …': 'Connecting to {host} …',
      'Keine Verbindung zu {host}:': 'No connection to {host}:',
      'Host fehlt': 'Host missing',
      'Passwort fehlt': 'Password missing',
      'Benutzer fehlt': 'User missing',
      'Port ungültig': 'Invalid port',
      'Neuer Host oder Benutzer: bitte das Passwort eingeben.': 'New host or user: please enter the password.',
      'Anmeldung am Miniserver gescheitert. Der Zugang wurde nicht gespeichert.':
        'Login to the Miniserver failed. The access was not saved.',
      'Miniserver nicht erreichbar. Der Zugang ist trotzdem gespeichert: Die bestehende Verbindung bleibt, der neue Zugang gilt ab dem nächsten Verbindungsaufbau.':
        'Miniserver not reachable. The access was saved anyway: the existing connection stays, the new access applies from the next time the connection is set up.',
      'Miniserver nicht erreichbar. Der Zugang ist trotzdem gespeichert, LoxPanel versucht es damit weiter.':
        'Miniserver not reachable. The access was saved anyway, LoxPanel keeps trying with it.',
      'Miniserver nicht erreichbar, und der Zugang ließ sich nicht speichern. Es bleibt beim bisherigen.':
        'Miniserver not reachable, and the access could not be saved. Everything stays as before.',
      'Verbunden, aber der Zugang ließ sich nicht speichern. Nach einem Neustart gilt er nicht mehr.':
        'Connected, but the access could not be saved. After a restart it no longer applies.',
      'Mit dem Miniserver verbunden': 'Connected to the Miniserver',
      'Bausteine geladen: {n}. Alle Bereiche sind jetzt offen.': 'Blocks loaded: {n}. All sections are open now.',
      'Gerät einrichten': 'Set up device',
      // Kamera / Tuerstation
      'Video-URL (MJPEG) und Login der Türstation(en) für das Kamerabild. Leer lassen, dann nimmt LoxPanel die Kamera, die der Miniserver nennt (in Loxone Config am Baustein der Intercom eingetragen). Die Liste kommt aus dem Miniserver.':
        'Video URL (MJPEG) and login of the door station(s) for the camera image. Leave empty to use the camera the Miniserver provides (set in Loxone Config at the intercom block). The list comes from the Miniserver.',
      'Speichern': 'Save',
      'Bausteintypen der Anlage anzeigen': 'Show control types of the installation',
      '(welche Typen vorkommen und welche LoxPanel noch nicht unterstützt; als JSON unter /api/types)':
        '(which types exist and which LoxPanel does not support yet; JSON at /api/types)',
      // SIP
      'SIP-Zugang der Türstation(en), wie ihn der Miniserver für das Gegensprechen nennt. LoxPanel liest ihn verschlüsselt, das Passwort bleibt im Server. „Verbindung prüfen“ fragt die Türstation, ob sie antwortet und die Anmeldung annimmt; ein Anruf entsteht dabei nicht.':
        'SIP access of the door station(s) as the Miniserver provides it for two-way audio. LoxPanel reads it encrypted, the password stays on the server. “Check connection” asks the door station whether it answers and accepts the login; no call is placed.',
      'Frage den Miniserver …': 'Asking the Miniserver …',
      'Andere oder unbekannte Türstation': 'Other or unknown door station',
      'SIP-Adresse': 'SIP address',
      'vorhanden': 'present',
      'keins': 'none',
      'Verbindung prüfen': 'Check connection',
      'Prüfe …': 'Checking …',
      'Die Türstation antwortet und nimmt die Anmeldung an.': 'The door station answers and accepts the login.',
      'Die Türstation antwortet und verlangt keine Anmeldung.': 'The door station answers and requires no login.',
      'Die Türstation lehnt die Anmeldung ab.': 'The door station rejects the login.',
      'Die Türstation verlangt eine Anmeldung, der Miniserver nennt aber kein Passwort.':
        'The door station requires a login, but the Miniserver provides no password.',
      'Die Türstation verlangt ein Anmeldeverfahren, das LoxPanel nicht kennt.':
        'The door station requires a login method LoxPanel does not know.',
      'Antwort:': 'Response:',
      'Gegenstelle:': 'Remote side:',
      'Codecs:': 'Codecs:',
      'Methoden:': 'Methods:',
      'Gesicherte Details vom Miniserver:': 'Secured details from the Miniserver:',
      'Ohne SIP-Adresse gibt es nichts zu prüfen. Die Adresse für Audio steht in Loxone Config am Baustein der Intercom (bei einer benutzerdefinierten Intercom „Host für Audio (intern)“); nach dem Speichern in den Miniserver diesen Reiter neu öffnen. Steht sie dort und fehlt hier trotzdem, gibt der Miniserver sie für diesen Baustein nicht heraus.':
        'Without a SIP address there is nothing to check. The audio address is set in Loxone Config at the intercom block (for a custom intercom “Host for audio (internal)”); after saving to the Miniserver, reopen this tab. If it is set there and still missing here, the Miniserver does not hand it out for this block.',
      'Für die Loxone Intercom am Baustein Intercom beschreibt die Strukturdoku von Loxone keinen SIP-Zugang.':
        'For the Loxone Intercom on the Intercom block, the Loxone structure file documentation describes no SIP access.',
      'Baustein Türsteuerung': 'Door Controller block',
      'Baustein Intercom': 'Intercom block',
      'leer': 'empty',
      // SIP: feste Meldungen des Servers (/api/sip, /api/sip/pruefen)
      'Keine Verbindung zum Miniserver': 'No connection to the Miniserver',
      'Die Intercom nennt keinen SIP-Zugang': 'The intercom provides no SIP access',
      'Unbekannte Intercom': 'Unknown intercom',
      'Der Benutzer von LoxPanel darf diese Zugangsdaten nicht lesen (Rechte in Loxone Config)':
        'The LoxPanel user may not read these credentials (permissions in Loxone Config)',
      'Der Miniserver lehnt die Anmeldung von LoxPanel ab (Code 401)': 'The Miniserver rejects the LoxPanel login (code 401)',
      'Der Miniserver lehnt die verschlüsselte Anfrage ab': 'The Miniserver rejects the encrypted request',
      'Die Antwort des Miniservers lässt sich nicht entschlüsseln': 'The response of the Miniserver cannot be decrypted',
      'Die gesicherten Details sind kein JSON': 'The secured details are not JSON',
      'Der Baustein hat keine gesicherten Details': 'The block has no secured details',
      "Paket 'cryptography' fehlt": "Package 'cryptography' is missing",
      'Keine Antwort: an dieser Adresse meldet sich kein SIP-Dienst': 'No response: no SIP service answers at this address',
      'Port geschlossen: an dieser Adresse läuft kein SIP-Dienst': 'Port closed: no SIP service runs at this address',
      'Keine Antwort auf die Anmeldung': 'No response to the login',
      // Panels
      'Suche Geräte…': 'Searching for devices…',
      '(Standard)': '(Default)',
      'Start': 'Start',
      'Reload': 'Reload',
      'Stop': 'Stop',
      'Kiosk läuft': 'Kiosk running',
      'Status:': 'Status:',
      'Video-URL (MJPEG)': 'Video URL (MJPEG)',
      // Audio
      'Der Weckton (Loxone-Wecker) wird direkt im Kiosk-Browser des Geräts erzeugt. Mit dem Test-Ton prüfst du, ob am Gerät wirklich etwas zu hören ist — falls nicht, liegt es meist an der Lautstärke/Ausgabe am Gerät (ALSA/PulseAudio), nicht am Browser.':
        'The alarm tone (Loxone alarm clock) is generated directly in the device’s kiosk browser. Use the test tone to check whether the device actually plays sound — if not, it is usually the volume/output on the device (ALSA/PulseAudio), not the browser.',
      'Test-Ton': 'Test tone',
      'Sendet 3 kurze Pieptöne an das/die gewählte(n) Gerät(e). Es müssen dafür geöffnet sein (Kiosk läuft und zeigt die Visu).':
        'Sends 3 short beeps to the selected device(s). They must be open (kiosk running and showing the visu).',
      'Zielgerät': 'Target device',
      '🔊 Test-Ton senden': '🔊 Send test tone',
      'Alle Geräte': 'All devices',
      // Kalender & Wetter (Front / Screensaver)
      'Kalender & Wetter': 'Calendar & weather',
      'Zeigt Termine aus deinen iCal-Abos und das Wetter auf der Uhr-Startseite (Screensaver) aller Geräte. Serverweit — der Server holt die Daten und schickt sie an die Geräte.':
        'Shows events from your iCal subscriptions and the weather on the clock start page (screensaver) of all devices. Server-wide — the server fetches the data and pushes it to the devices.',
      'iCal-Kalender': 'iCal calendars',
      'Abo-Link aus Apple/iCloud (Kalender → Teilen → Öffentlicher Kalender), Google oder anderen Diensten. webcal:// oder https://. Nur Lesen, kein Login. Mehrere Kalender möglich — Geburtstage, Müllabfuhr, Ferien und die Familientermine landen gemeinsam auf einer Liste.':
        'Subscription link from Apple/iCloud (Calendar → Share → Public calendar), Google or other services. webcal:// or https://. Read-only, no login. Several calendars are possible — birthdays, waste collection, school holidays and family appointments all end up in one list.',
      'Überschrift in der Visu': 'Heading in the visu',
      '＋ Kalender hinzufügen': '＋ Add calendar',
      'Feiertags-iCal (optional)': 'Holiday iCal (optional)',
      'z.B. österr. Feiertage aus Google Kalender (basic.ics)':
        'e.g. Austrian public holidays from Google Calendar (basic.ics)',
      'Optionaler zweiter iCal nur für Feiertage — deren Tage werden im Monatsraster rot markiert (wie Sonntage). Z.B. der Feiertagskalender deines Landes aus Google.':
        'An optional second iCal for public holidays only — those days are marked red in the month grid (like Sundays). For example your country’s holiday calendar from Google.',
      // Kalenderzeile
      'Kalender': 'Calendar',
      // Hausuebersicht als Seite (Seiten-Editor, Assistent)
      'Hausübersicht': 'House overview',
      'Hausübersicht als Seite hinzufügen': 'Add the house overview as a page',
      'Haus': 'House',
      'Diese Seite zeigt die Hausübersicht: Räume, was gerade an ist, Audio, Uhr, Wetter und Energie. Sie stellt sich aus der Anlage selbst zusammen, hier gibt es nichts anzuordnen.':
        'This page shows the house overview: rooms, what is on right now, audio, clock, weather and energy. It builds itself from your installation, there is nothing to arrange here.',
      'Name': 'Name',
      'Farbe': 'Color',
      'Entfernen': 'Remove',
      'iCal-Abo-URL': 'iCal subscription URL',
      'z.B. Müllabfuhr': 'e.g. waste collection',
      'Noch kein Kalender. Mit „＋ Kalender hinzufügen" den ersten Abo-Link eintragen.':
        'No calendar yet. Use “＋ Add calendar” to enter the first subscription link.',
      'Mehr als {max} Kalender gehen nicht.': 'More than {max} calendars are not possible.',
      // Status der Kalender
      'noch nicht geladen': 'not loaded yet',
      'geladen': 'loaded',
      'aus {n} Kalendern': 'from {n} calendars',
      '{n} von {gesamt} Kalendern nicht geladen': '{n} of {gesamt} calendars not loaded',
      'Grund steht oben beim jeweiligen Kalender.':
        'The reason is shown above, at the calendar concerned.',
      'Die Visu zeigt weiter den Stand von {zeit} Uhr.':
        'The visu still shows the data from {zeit}.',
      'Visu zeigt den Stand von {zeit} Uhr.': 'Visu is showing the data from {zeit}.',
      // Wetter
      'Wetter': 'Weather',
      'Hat die Anlage den Loxone-Wetterdienst, kommt das Wetter von dort — die Koordinaten bleiben dann unbenutzt. Sonst von Open-Meteo: kostenlos, ohne API-Schlüssel und ohne Konto, nur die Koordinaten deines Standorts eintragen (Dezimalgrad, z.B. 47.071 / 15.439). Leer lassen schaltet das Wetter aus, solange kein Wetterserver liefert.':
        'If the installation has the Loxone weather service, the weather comes from there — the coordinates then stay unused. Otherwise from Open-Meteo: free, no API key and no account, just enter the coordinates of your location (decimal degrees, e.g. 47.071 / 15.439). Leaving them empty switches the weather off, as long as no weather server delivers.',
      'Breitengrad': 'Latitude',
      'Längengrad': 'Longitude',
      // Anzeige am Panel
      'Anzeige': 'Display',
      'Termine der nächsten … Tage': 'Events for the next … days',
      'Wetter-Vorschau (Tage)': 'Weather forecast (days)',
      'Termine auf der Uhr-Seite (max.)': 'Events on the clock page (max.)',
      'Kalenderfarben in der Visu zeigen': 'Show calendar colors in the visu',
      'Aus = schlicht: alle Termine einfarbig, nur der Kalendername steht daneben. An = jeder Kalender bekommt seinen Farbpunkt, auch im Monatsraster.':
        'Off = plain: all events in a single color, only the calendar name beside them. On = every calendar gets its color dot, in the month grid too.',
      '„Termine auf der Uhr-Seite" ist eine Obergrenze — was neben Wetter und Uhr nicht mehr auf den Schirm passt, bleibt weg (auf einem 480×480-Gerät sind das etwa drei). Die vollständige Liste steht im Kalender-Pane.':
        '“Events on the clock page” is an upper limit — whatever no longer fits on the screen next to the weather and the clock is left out (on a 480×480 device that is about three). The full list is in the calendar pane.',
      // Verlaufs-Diagramme (Detailseite, Split-Haelfte, Kachel)
      'Verlauf': 'History',
      'Zeitraum': 'Period',
      'Trend': 'Trend',
      'Tagesmuster': 'Daily pattern',
      'Tagesspanne': 'Daily range',
      'Kurve mit Tief, Hoch und Änderung': 'Curve with low, high and change',
      'Verbrauch als Balken, dazu die Summe': 'Consumption as bars, plus the total',
      'Ein/Aus als Stufen, dazu die Einschaltdauer': 'On/off as steps, plus the time switched on',
      '7 Tage × 24 Stunden als Farbraster': '7 days × 24 hours as a color grid',
      'Tief bis Hoch je Tag, 7 Tage': 'Low to high per day, 7 days',
      '7 Tage': '7 days',
      '30 Tage': '30 days',
      // Neues Panel
      '＋ Gerät einrichten': '＋ Set up device',
      'Erzeugt den Befehl, der Agent + Config aufs Gerät überträgt, den Autostart einrichtet und Chromium still stellt (keine Übersetzen-Leiste / Anmeldung). Einmal im Terminal ausführen — fragt nach dem SSH-/sudo-Passwort des Geräts.':
        'Generates the command that copies agent + config to the device, sets up autostart and quiets Chromium (no translate bar / sign-in). Run once in a terminal — it asks for the device’s SSH/sudo password.',
      'Geräte-IP': 'Device IP',
      'SSH-Benutzer': 'SSH user',
      'Anzeigename': 'Display name',
      'Startansicht': 'Start view',
      'Server-Adresse (dieser Server)': 'Server address (this server)',
      'Befehl erzeugen': 'Generate command',
      'In Zwischenablage kopieren': 'Copy to clipboard',
      'Geräte-IP und Server-Adresse nötig': 'Device IP and server address required',
      '✓ kopiert': '✓ copied',
      'Kopieren nicht möglich – bitte manuell markieren': 'Copy failed – please select manually',
      'Fehler': 'Error',
      'Keine Intercom-Bausteine gefunden (Miniserver verbunden?).':
        'No intercom blocks found (Miniserver connected?).',
      '✓ Gespeichert': '✓ Saved',
      'Nicht übernommen:': 'Not kept by the server:',
      'verbunden': 'connected',
      'nicht verbunden': 'not connected',
      // Version in der Seitenleiste
      'Version unbekannt': 'Version unknown',
      'gebaut': 'built',

      // ---- Betriebsmodus-Automatik (/settings) ----
      'Betriebsmodus-Automatik': 'Operating-mode automation',
      'Loxone schaltet die Ansicht automatisch um: in Loxone Config einen virtuellen HTTP-Ausgang anlegen, der pro Betriebsart einen Modusnamen an diesen Server schickt. Hier legst du je Gerät fest, welche Ansicht bei welchem Modus erscheint. Ein Gerät ohne Eintrag für einen Modus bleibt unverändert.':
        'Loxone switches the view automatically: in Loxone Config create a virtual HTTP output that sends a mode name to this server per operating mode. Here you define, per device, which view appears for which mode. A device without an entry for a mode stays unchanged.',
      'Geräte mit Agent (Linux) erscheinen automatisch. Ein Gerät ohne Agent (z.B. NSPanel Pro, Tablet) muss nur die Visu mit einer Geräte-Kennung öffnen: ?panel=<start>&device=<name> — dann wird es hier gelistet und live umgeschaltet (Browser lädt sich mit neuer Ansicht neu, kein Agent nötig).':
        'Devices with an agent (Linux) appear automatically. A device without an agent (e.g. NSPanel Pro, tablet) just opens the visu with a device id: ?panel=<start>&device=<name> — then it is listed here and switched live (the browser reloads with the new view, no agent needed).',
      // Skalierung / Bildschirmgroesse
      'Kachel-Aufbau': 'Tile layout',
      'Neu (wie die Loxone-App)': 'New (like the Loxone app)',
      'Kachel-Set': 'Tile set',
      'Eigene Farben': 'Own colours',
      'Neuer Stand auf dem Server – nach dem Speichern lädt die Seite neu.':
        'New version on the server – the page reloads after saving.',
      'Jetzt neu laden': 'Reload now',
      'Ohne Set: Farben aus der Grundfarbe, Kachel-Aufbau frei wählbar.':
        'Without a set: colours from the base colour, tile layout freely selectable.',
      'Loxone-App (dunkel)': 'Loxone app (dark)',
      'Eigene Zustandsfarben und Farben aus „Kacheln gestalten“ gelten weiter.':
        'Your own state colours and colours from “Style tiles” still apply.',
      'Flache dunkle Kacheln, weiße Symbole, dunkle Tasten, die Tab-Leiste als Pille.':
        'Flat dark tiles, white icons, dark buttons, the tab bar as a pill.',
      'Touch (Farbton wählbar)': 'Touch (choose a hue)',
      'Kacheln in einem Farbton, Symbol mittig, die aktive Kachel kippt ganz um; die Tab-Leiste steht nur mit Symbolen oben.':
        'Tiles in one hue, icon centred, the active tile flips completely; the tab bar sits at the top with icons only.',
      'Kreide (hell)': 'Chalk (light)',
      'Weiße Kacheln auf hellem Grund, das Symbol im Kreis, die Tabs als Seitenleiste links.':
        'White tiles on a light background, the icon in a circle, the tabs as a sidebar on the left.',
      'Farbton': 'Hue',
      'Aktive Kachel': 'Active tile',
      'Hell': 'Light',
      'Dunkel': 'Dark',
      'Schnellwahl': 'Quick pick',
      'Nachgerechnet': 'Checked',
      'Ziel': 'target',
      'Schrift auf Kachel': 'Text on tile',
      'Schrift auf aktiver Kachel': 'Text on active tile',
      'Symbol auf Taste': 'Icon on button',
      'Salbei': 'Sage',
      'Mint': 'Mint',
      'Himmel': 'Sky',
      'Lavendel': 'Lavender',
      'Rosé': 'Rosé',
      'Sand': 'Sand',
      'Grundfarbe und Kachel-Aufbau kommen aus dem gewählten Set.': 'Base colour and tile layout come from the chosen set.',
      'Farbe und Aufbau': 'Colour and layout',
      'Größen': 'Sizes',
      'Was bedeuten die Größen?': 'What do the sizes mean?',
      'Automatisch (Tablet)': 'Automatic (tablet)',
      'Kachelgröße': 'Tile size',
      'Klein (mehr Kacheln)': 'Small (more tiles)',
      'Mittel': 'Medium',
      'Groß (weniger Kacheln)': 'Large (fewer tiles)',
      'Zielkachel (px)': 'Target tile (px)',
      'Widget-Breite': 'Widget width',
      // --- Ansicht duplizieren mit Raumtausch (Punkt 14) ---
      'Duplizieren': 'Duplicate',
      'Ansicht duplizieren': 'Duplicate view',
      'Vorlage': 'Template',
      'Neue ID': 'New ID',
      'Raum tauschen: von': 'Swap room: from',
      'nach': 'to',
      '(kein Raumtausch – reine Kopie)': '(no room swap – plain copy)',
      '(Kopie)': '(copy)',
      'Reine Kopie: alle Tabs, Bausteine und Einstellungen bleiben, wie sie sind.': 'Plain copy: all tabs, blocks and settings stay as they are.',
      'Quell- und Zielraum sind gleich – nichts zu tauschen.': 'Source and target room are the same – nothing to swap.',
      'Bausteine aus': 'blocks from',
      'werden durch die gleichnamigen in': 'are replaced by the ones of the same name in',
      'ersetzt.': '.',
      'Ohne Gegenstück dort (fallen weg):': 'Without a counterpart there (dropped):',
      'angelegt – Speichern nicht vergessen.': 'created – remember to save.',
      'Weggefallen:': 'Dropped:',
      // --- Zielgeraet eines Profils (Punkt 15) ---
      'Zielgerät': 'Target device',
      '(keines)': '(none)',
      'Für welches Gerät diese Ansicht gemacht ist. Unter Geräte steht eine Warnung, wenn ein anderes Gerät oder eines mit deutlich anderer Bildschirmgröße es nutzt.': 'Which device this view is made for. Devices shows a warning when another device, or one with a clearly different screen size, uses it.',
      'Ansicht ist für': 'View is made for',
      'gemacht': '',
      'gemacht, hier': ', here',
      // --- Vorschlag statt leerer Seite (Punkt 13) ---
      'Vorschlag für ein Gerät': 'Suggestion for a device',
      'für': 'for',
      'Übernimmt Anzeige, Inhalt und Name und trägt das Gerät als Zielgerät ein – danach gleich prüfen und anlegen oder zurück und verfeinern.': 'Fills in display, content and name and sets the device as target device – then check and create right away, or go back and refine.',
      'Oder selbst wählen': 'Or choose yourself',
      'Favoriten': 'Favourites',
      'Weiter zu Prüfen →': 'On to check →',
      'Das Aussehen behält die Vorgaben': 'The appearance keeps the defaults',
      'Automatisch': 'Automatic',
      'rund': 'about',
      'der Spalten': 'of the columns',
      'Kachelspalte': 'tile column',
      'Kachelspalten': 'tile columns',
      'Wie viele Kachelspalten das Widget rechts neben den Kacheln belegt, hochkant Kachelzeilen darunter – die Kacheln bleiben gleich groß. „Automatisch“ nimmt den Anteil, den das Gerät aus seinem Raster rechnet. Mit fester Breite wachsen wenige Kacheln auch neben dem Widget, es wächst dann mit. Nur im Kachel-Layout „Automatisch“.':
        'How many tile columns the widget takes to the right of the tiles, in portrait tile rows below them – the tiles stay the same size. "Automatic" takes the share the device works out from its grid. With a fixed width, a few tiles grow next to the widget too, and it grows with them. Only in the "Automatic" tile layout.',
      'Breite': 'Width',
      'breit': 'wide',
      'schmal': 'narrow',
      '1 Spalte': '1 column',
      '2 Spalten (breit)': '2 columns (wide)',
      'Zielkachel: Breite einer Kachel in CSS-Pixeln, aus der das Tablet Spalten und Zeilen rechnet. Leer = Standard': 'Target tile: width of a tile in CSS pixels, from which the tablet works out columns and rows. Empty = default',
      'die bisherigen Stufen Klein, Mittel und Groß entsprechen': 'the former steps small, medium and large correspond to',
      'Passen alle Kacheln einer Seite auf den Schirm, wachsen sie (ohne Widget daneben oder mit fester Widget-Breite) bis zum': 'If all tiles of a page fit on the screen, they grow (without a widget beside them, or with a fixed widget width) up to',
      'Fachen': 'times the target',
      'Für welches Gerät?': 'For which device?',
      'Dieser Browser': 'This browser',
      'gemeldet': 'reported',
      'Aus dem Katalog …': 'From the catalogue …',
      'Vorgerechnet für': 'Precalculated for',
      'Zielkachel': 'Target tile',
      'angeboten wird nur, was zu diesem Schirm passt.': 'only what suits this screen is offered.',
      'Mit einem Gerät rechnet der Assistent jede Anzeige vor und bietet nur passende an.': 'With a device, the wizard precalculates every layout and only offers those that fit.',
      'Kachel-Raster — vorgerechnet': 'Tile grid — precalculated',
      'Danach auf': 'Afterwards show on',
      'anzeigen – speichert und schaltet das Gerät um': '– saves and switches the device',
      'am Gerät merken': 'remember on the device',
      'Danach': 'Afterwards',
      'Gerät umschalten': 'switch device',
      'nur anlegen': 'create only',
      'gespeichert,': 'saved,',
      'schaltet um.': 'is switching.',
      'Spalten': 'columns',
      'Zeilen': 'rows',
      'ist nicht online – die Ansicht ist gespeichert, umschalten unter Geräte.': 'is not online – the view is saved, switch it under Devices.',
      'Vorschau': 'Preview',
      'Zeigt diese Ansicht mit allen Änderungen in der echten Visu, auch ungespeichert. Das Fenster zieht Änderungen nach.': 'Shows this view with all changes in the real visu, even unsaved. The window follows your changes.',
      'Das Vorschaufenster hat der Browser blockiert.': 'The browser blocked the preview window.',
      'Vorschau nicht möglich:': 'Preview not possible:',
      'Am Gerät ansehen': 'View on device',
      'Am Gerät beenden': 'End on device',
      'Zeigt diese Ansicht mit allen Änderungen auf dem Gerät (Vorschaugerät im Seiten-Editor, sonst das Zielgerät) und zieht Änderungen nach. Ohne Änderungen kehrt das Gerät nach 15 Minuten zur vorigen Ansicht zurück.': 'Shows this view with all changes on the device (preview device in the page editor, otherwise the target device) and follows your changes. Without changes the device returns to its previous view after 15 minutes.',
      'Für die Vorschau am Gerät im Seiten-Editor ein Gerät wählen, das verbunden ist.': 'For the preview on a device choose a connected device in the page editor.',
      'hat keine verbundene Visu – eine Vorschau braucht sie.': 'has no connected visu – a preview needs one.',
      'Vorschau läuft auf': 'Preview running on',
      'Vorschau am Gerät beendet.': 'Preview on the device ended.',
      'Stand': 'Build',
      'Vorschau am Gerät nicht beendet:': 'Preview on the device not ended:',
      'Auf dem Gerät ansehen': 'View on the device',
      'Auf': 'On',
      'ansehen': 'view',
      'Vorschau beenden': 'End preview',
      'Zeigt die Ansicht mit diesen Einstellungen auf dem Gerät, bevor sie angelegt wird. Ohne Änderungen kehrt das Gerät nach 15 Minuten zur vorigen Ansicht zurück.': 'Shows the view with these settings on the device before it is created. Without changes the device returns to its previous view after 15 minutes.',
      'Die Zielkachel am Gerät wird erst beim Anlegen gemerkt; die Vorschau rechnet mit der bisherigen.': 'The target tile on the device is only remembered when the view is created; the preview uses the previous one.',
      'Im Seiten-Editor bearbeiten': 'Edit in the page editor',
      'Name, Icon, Inhalt und Anordnung der Seite stellst du im Seiten-Editor ein.': 'Set the name, icon, content and layout of the page in the page editor.',
      'Seite entfernen': 'Remove page',
      'Gerät entfernen:': 'Remove device:',
      'Entfernt:': 'Removed:',
      'Es ist gerade verbunden und erscheint danach wieder, ohne Einstellungen.': 'It is connected right now and will reappear afterwards, without settings.',
      'Seine Einstellungen (Betriebsmodi, Display-Steuerung, Skalierung, Zielkachel, Präsenzmelder) gehen verloren. Ungespeicherte Änderungen an den übrigen Geräten werden dabei mitgespeichert.': 'Its settings (operating modes, display control, scaling, target tile, presence sensor) will be lost. Unsaved changes to the other devices are saved along with it.',
      'Werte der Kopfzeile': 'Header values',
      'ist noch leer.': 'is still empty.',
      'zeigt das Widget': 'shows the widget',
      'über die ganze Fläche.': 'across the whole screen.',
      '„Vorschau“ unten zeigt die Seite in der echten Visu, auch ungespeichert, und zieht Änderungen nach.': 'The “Preview” button below shows the page in the real visu, even unsaved, and follows your changes.',
      'Seiten-Editor': 'Page editor',
      'Ordnet die freien Seiten (Eigene Auswahl) so an, wie das gewählte Gerät sie zeigt: Bausteine aus der Liste auf die Fläche ziehen, Kacheln verschieben, Größe 1 × 1, 2 × 1 oder 2 × 2 wählen, ein Widget daneben setzen.': 'Arranges the free pages (own selection) the way the chosen device shows them: drag blocks from the list onto the area, move tiles, choose size 1 × 1, 2 × 1 or 2 × 2, put a widget next to them.',
      'Freie Seiten zeigt die Visu erst, wenn sie in der Leiste stehen: unter Inhalt „Eigene Auswahl“ wählen oder die Auswahl als Button in die klassische Leiste nehmen.': 'The visu only shows free pages once they are in the bar: choose “Own selection” under Content or add the selection as a button to the classic bar.',
      'Vorschau für': 'Preview for',
      'Nach Räumen gruppieren': 'Group by room',
      'Die Visu ordnet die Kacheln nach Räumen, ein Raum steht dort, wo sein erster Baustein steht; Verschieben ordnet innerhalb eines Raums oder rückt einen ganzen Raum nach vorn. Ohne Gruppierung gilt genau diese Anordnung, ohne Sprungmarken.': 'The visu orders the tiles by room, a room stands where its first block stands; moving reorders within a room or moves a whole room forward. Without grouping exactly this arrangement applies, without jump marks.',
      'Die Visu zeigt genau diese Anordnung, ohne Sprungmarken.': 'The visu shows exactly this arrangement, without jump marks.',
      'Bausteine aus der Liste hierher ziehen oder antippen': 'Drag blocks from the list here or tap them',
      'Uhr, Wetter': 'clock, weather',
      'Raster am': 'Grid on',
      'Festes Raster am': 'Fixed grid on',
      'neben dem Widget': 'next to the widget',
      'über dem Widget': 'above the widget',
      'von': 'of',
      'Seite zurück': 'Previous page',
      'Seite vor': 'Next page',
      'Diese Seite zeigt ein Widget über die ganze Fläche statt Kacheln. Für Kacheln den Seiteninhalt auf „Bausteine (Kacheln)“ stellen.': 'This page shows a widget across the whole area instead of tiles. For tiles set the page content to “Blocks (tiles)”.',
      'Feste Raster: die Kachelgröße hängt am Kasten der Visu und an der Skalierung, die Fläche zeigt Spalten, Zeilen und Lage.': 'Fixed grids: the tile size depends on the visu box and the scaling, the area shows columns, rows and position.',
      'Ziehen mit Maus oder Finger, in der Liste am Griff. Ohne Ziehen: Kachel antippen, dann mit den Pfeiltasten verschieben, Entf nimmt sie von der Seite.': 'Drag with mouse or finger, in the list by the handle. Without dragging: tap a tile, then move it with the arrow keys, Delete takes it off the page.',
      'Ausgewählt': 'Selected',
      'Kachel antippen, um Größe und Reihenfolge zu ändern.': 'Tap a tile to change its size and order.',
      'Größe': 'Size',
      'Auf diesem Gerät zeigt die Visu sie': 'On this device the visu shows it as',
      'dafür fehlen Spalten oder Zeilen.': 'there are not enough columns or rows for more.',
      'Reihenfolge': 'Order',
      'nach vorn': 'forward',
      'nach hinten': 'backward',
      'Von der Seite nehmen': 'Remove from page',
      'Kachel gestalten': 'Style tile',
      'auf dieser Seite': 'on this page',
      'abgeblendet = schon platziert': 'dimmed = already placed',
      'Widgets': 'Widgets',
      'Ein Widget steht quer rechts neben den Kacheln, hochkant darunter; die Kopfzeile liegt über ihnen. Antippen oder auf die Fläche ziehen, noch einmal antippen nimmt es weg.': 'A widget stands to the right of the tiles in landscape, below them in portrait; the header row lies above them. Tap or drag onto the area, tap again to remove it.',
      'Mehr als 60 Bausteine passen nicht auf eine Seite.': 'More than 60 blocks do not fit on one page.',
      'Die Seite ist nicht nach Räumen gruppiert (Seiten-Editor) – die untere Leiste bleibt darum ohne Sprungmarken.': 'The page is not grouped by room (page editor) – so the bottom bar has no jump marks.',
      '4″-Wandpanel': '4″ wall panel',
      'Galaxy Tab A9 quer': 'Galaxy Tab A9 landscape',
      'Galaxy Tab A9 hochkant': 'Galaxy Tab A9 portrait',
      'iPad quer': 'iPad landscape',
      'iPad hochkant': 'iPad portrait',
      '10″-Tablet quer': '10″ tablet landscape',
      '10″-Tablet hochkant': '10″ tablet portrait',
      'Bliebe bei mehreren Seiten die letzte mehr als ein Drittel leer, werden sie kleiner, wenn das eine Seite spart, höchstens bis zur Zielkachel geteilt durch': 'If, with several pages, the last one would stay more than a third empty, they shrink when that saves a page, at most down to the target tile divided by',
      'Ein Gerät kann unter Geräte einen eigenen Wert bekommen, mit Vorschlag aus seiner gemeldeten Größe.': 'A device can get its own value under Devices, with a suggestion from its reported size.',
      'Zielkachel (Automatik)': 'Target tile (automatic grid)',
      'wie in der Ansicht': 'as in the view',
      'Vorschlag': 'Suggestion',
      'Pixeldichte': 'pixel density',
      'übernehmen': 'apply',
      'kein Vorschlag: das Gerät hat noch keine Größe gemeldet': 'no suggestion: the device has not reported a size yet',
      'Kachel-Layout „Automatisch“ (Tablet): Das Gerät rechnet Spalten und Zeilen selbst aus seiner Bildschirmgröße – ein größerer Schirm zeigt mehr Kacheln, nicht größere. Ein Widget belegt ganze Kachelspalten, hochkant ganze Zeilen; die Kacheln bleiben dabei gleich groß. „Bildschirm füllen“ und Skalierung braucht es dann nicht. Was ein Gerät daraus macht, steht unter Geräte.':
        'Tile grid “Automatic” (tablet): the device works out columns and rows from its screen size itself – a larger screen shows more tiles, not larger ones. A widget takes whole tile columns, in portrait whole rows; the tiles keep their size. “Fill screen” and scaling are not needed then. What a device makes of it is shown under Devices.',
      '„Automatisch“ rechnet das Raster aus der Bildschirmgröße des Tablets: ein größerer Schirm zeigt mehr Kacheln, nicht größere.':
        '“Automatic” works out the grid from the tablet’s screen size: a larger screen shows more tiles, not larger ones.',
      'Kachel-Aufbau „Neu“: Raum klein oben rechts, der Zustand groß und der Name darunter, Temperaturen groß an Stelle des Symbols, Tasten als Leiste unten. „Klassisch“ ist der bisherige Aufbau. Das Kachel-Layout bleibt in beiden gleich.':
        'Tile layout “New”: room small at the top right, the state large with the name below, temperatures large in place of the symbol, buttons as a bar at the bottom. “Classic” is the previous layout. The tile grid stays the same in both.',
      'Skalierung': 'Scaling',
      'Wie in der Ansicht': 'Same as the view',
      'Aus (feste Größe)': 'Off (fixed size)',
      'Automatisch (Bildschirm ausnutzen)': 'Automatic (use the screen)',
      'Fest': 'Fixed',
      'quer': 'landscape',
      'hoch': 'portrait',
      'quadratisch': 'square',
      'physisch': 'physical',
      'Visu': 'visu',
      'nutzt': 'uses',
      'Skalierung „Automatisch": Jedes Gerät vergrößert die Visu so weit, wie es ohne Rand und ohne Verzerrung geht – Schrift, Icons, Uhr-Seite und Panes wachsen mit. Ein fester Faktor wird nie größer, als der Bildschirm hergibt. Wirkt nicht zusammen mit „Bildschirm füllen", das den Schirm schon ausfüllt. „Wie Vorgabe" übernimmt die Einstellung unter Vorgaben → Darstellung; pro Gerät übersteuerbar auf seiner Karte unter Geräte → Am Gerät.':
        'Scaling "Automatic": each device enlarges the visu as far as it can without borders or distortion – text, icons, clock page and panes grow along. A fixed factor never exceeds what the screen allows. Has no effect together with "Fill screen", which already fills the screen. "Same as default" takes the setting under Defaults → Appearance; can be overridden per device on its card under Devices → On the device.',
      'Wie Vorgabe': 'Same as default',
      'Standard für alle Ansichten': 'Default for all views',
      'Aus': 'Off',
      'Gilt für alle Ansichten, die „Wie Vorgabe" eingestellt haben. „Automatisch" vergrößert die Visu auf jedem Gerät so weit, wie es ohne Rand und ohne Verzerrung geht. Eine Ansicht kann das unter Raster übersteuern, ein einzelnes Gerät auf seiner Karte unter Geräte → Am Gerät.':
        'Applies to all views set to "Same as default". "Automatic" enlarges the visu on every device as far as it can without borders or distortion. A view can override this under Grid, a single device on its card under Devices → On the device.',
      'Werte für alle Ansichten, die sie nicht selbst setzen. Eine Ansicht überschreibt sie unter Raster, Aussehen und Verhalten.':
        'Values for all views that do not set them themselves. A view overrides them under Grid, Appearance and Behaviour.',
      'Nacht': 'Night',
      'Kategorie-Farben': 'Category colors',
      'Abdunkelung': 'Dimming',
      'Nachts abdunkeln (%)': 'Dim at night (%)',
      'Aufhellen bei Berührung (Sek.)': 'Brighten on touch (s)',
      '0 = aus': '0 = off',
      'Gilt für alle Ansichten, die unter Verhalten nichts eintragen.': 'Applies to all views that leave it empty under Behaviour.',
      'Baustein nicht mehr in der Anlage': 'Block no longer in the installation',
      'aus den Vorgaben': 'from the defaults',
      'aus der Ansicht {a}': 'from the view {a}',
      'Ansicht {a}': 'view {a}',
      'gilt für {n} von {m} Ansichten': 'applies to {n} of {m} views',
      'eigener Wert in {liste}': 'own value in {liste}',
      'am Gerät {g}: {w}': 'on device {g}: {w}',
      'Dann gilt: {w}': 'Then applies: {w}',
      '× zurücksetzen': '× reset',
      'zeigt gerade keine Ansicht': 'shows no view right now',
      'wirkt nur bei Kachel-Layout „Automatisch“ (Ansicht {a})': 'only takes effect with tile layout “Automatic” (view {a})',
      'Fett': 'Bold',
      'Normal': 'Normal',
      'Display &amp; Neustart': 'Display &amp; restart',
      'nie': 'never',
      'Linux-Agent nach seiner kiosk.conf, sonst nie': 'Linux agent per its kiosk.conf, otherwise never',
      'Vom Gerät bis zur fertigen Ansicht in sechs Schritten: Miniserver, Gerät, Ansicht, Inhalt und Seiten, Aussehen und Verhalten, Prüfen.': 'From the device to a finished view in six steps: Miniserver, device, view, content and pages, appearance and behaviour, check.',
      'Gerät': 'Device',
      'Miniserver verbunden': 'Miniserver connected',
      'entfällt hier': 'not needed here',
      'Ohne Gerät': 'Without device',
      'nur eine Ansicht anlegen, ohne Vorrechnung': 'just create a view, without pre-calculation',
      'Neues Gerät verbinden': 'Connect a new device',
      'Ein Gerät, das die Visu schon zeigt, aber noch keinen Namen hat, steht mit seinem Code darunter. Ein neues bekommt die Start-Adresse oder den Agenten; sobald es sich meldet, steht es oben zur Wahl.': 'A device that already shows the view but has no name yet is listed below with its code. A new one gets the start address or the agent; as soon as it reports in, it can be chosen above.',
      'Was soll {g} zeigen?': 'What should {g} show?',
      'Welche Ansicht?': 'Which view?',
      'Neue Ansicht anlegen': 'Create a new view',
      'Inhalt, Seiten und Aussehen in den nächsten Schritten.': 'Content, pages and appearance in the next steps.',
      'Vorhandene Ansicht zeigen': 'Show an existing view',
      'Das Gerät schaltet auf eine Ansicht, die es schon gibt.': 'The device switches to a view that already exists.',
      'Braucht ein Gerät aus Schritt 2.': 'Needs a device from step 2.',
      'Vorhandene duplizieren': 'Duplicate an existing view',
      'Mit Raumtausch: die Bausteine eines Raums durch die gleichnamigen eines anderen ersetzen.': 'With room swap: replace the blocks of one room with the same-named ones of another.',
      'Inhalt und Aussehen entfallen hier: Die Ansicht hat sie schon, den Feinschliff machst du danach unter Ansichten.': 'Content and appearance are not needed here: the view already has them; fine-tune it afterwards under Views.',
      'Vorschlag aus dem Gerätenamen: Raum-Ansicht {r}': 'Suggested from the device name: room view {r}',
      'Leere Felder nehmen die Vorgaben; einzelne Kacheln stellst du danach im Editor ein.': 'Empty fields take the defaults; adjust single tiles afterwards in the editor.',
      'Leer gilt:': 'Empty means:',
      'Display aus nach': 'Display off after',
      'Zeigt künftig': 'Will show',
      'Raumtausch': 'Room swap',
      'Zuweisen ✓': 'Assign ✓',
      '„Zuweisen" schaltet das Gerät gleich um; Betriebsmodi unter Geräte gelten weiter.': '“Assign” switches the device right away; operating modes under Devices still apply.',
      '— Ansicht wählen —': '— choose view —',
      'Modus (z.B. gaeste)': 'Mode (e.g. guests)',
      'Automatik aktiv': 'Automation active',
      '+ Modus': '+ Mode',
      'Zeile entfernen': 'Remove row',

      // ---- /config (Panel-Editor) ----
      'Titel': 'Title',
      'Fenstertitel der Ansicht.': 'Window title of the view.',
      'Kiosk-URL:': 'Kiosk URL:',
      'Standard-Aussehen für <b>alle</b> Panels. Einzelne Panels können es unter „Darstellung" überschreiben (leer = erbt global).':
        'Default look for <b>all</b> panels. Individual panels can override it under "Appearance" (empty = inherits global).',
      'Untere Leiste (Tabs)': 'Bottom bar (tabs)',
      'Bis zu <b>4 Buttons</b> — die 4 Standard-Tabs und/oder einzelne Kategorien als Abkürzung. Der <b>erste aktive</b> ist die Startseite (★). ':
        'Up to <b>4 buttons</b> — the 4 standard tabs and/or individual categories as shortcuts. The <b>first active</b> one is the start page (★). ',
      'Räume': 'Rooms',
      'Welche Räume diese Ansicht zeigt. <b>Nichts angehakt = alle Räume.</b>':
        'Which rooms this view shows. <b>Nothing checked = all rooms.</b>',
      'Alle abwählen': 'Deselect all',
      'Kategorien': 'Categories',
      'Welche Kategorien im Tab „Kategorien" erscheinen. <b>Nichts angehakt = alle.</b> Bei gesetzter Raum-Auswahl werden Kategorien zusätzlich auf diese Räume gefiltert.':
        'Which categories appear in the "Categories" tab. <b>Nothing checked = all.</b> If a room selection is set, categories are additionally filtered to those rooms.',
      'Kacheln gestalten': 'Style tiles',
      'Klicke eine Kachel an und ändere <b>Farben, Schrift und Icon nur für diese Kachel</b> (in dieser Ansicht). Farbiger Punkt = schon angepasst. Mit dem <b>Auge</b> rechts blendest du eine Kachel in dieser Ansicht ganz aus. ':
        'Click a tile and change <b>colors, font and icon for this tile only</b> (in this view). Colored dot = already customized. Use the <b>eye</b> on the right to hide a tile entirely in this view. ',
      'Kachel suchen…': 'Search tile…',
      'Darstellung (optional)': 'Appearance (optional)',
      'Überschreibt die Vorgaben nur für diese Ansicht. Leer = Vorgabe.':
        'Overrides the defaults for this view only. Empty = default.',
      'Aktiv-Overlay': 'Active overlay',
      'Wie eine Kachel im <b>aktiven Zustand</b> hervorgehoben wird (an = Akzent, ok = grün, kritisch = rot): Rahmen, Füllung und Deckkraft. Die <b>Farbe</b> kommt je Zustand aus dem Theme, hier stellst du das <b>Aussehen</b> ein. Gilt für diese Ansicht — einzelne Kacheln können unten abweichen.':
        'How a tile is highlighted in its <b>active state</b> (on = accent, ok = green, critical = red): border, fill and opacity. The <b>color</b> per state comes from the theme; here you set the <b>look</b>. Applies to this view — individual tiles can differ below.',
      'Ansicht löschen': 'Delete view',
      'Keine Ansicht gewählt.': 'No view selected.',
      'keine Kacheln im gewählten Raum-/Kategorie-Filter': 'no tiles in the selected room/category filter',
      'nichts gefunden': 'nothing found',
      // Labels
      'Icon-Größe': 'Icon size',
      'Haupttext-Größe': 'Main text size',
      'Zweittext-Größe': 'Second line size',
      'Raum-Größe': 'Room size',
      'Messwert-Größe': 'Value size',
      'Haupttext': 'Main text',
      'Zweittext': 'Second line',
      'Haupttext ist die große Zeile der Kachel, Zweittext die kleine darunter. Im klassischen Aufbau ist das der Name und darunter der Zustand, im neuen steht meist der Zustand groß und der Name klein. Raum ist die Raumangabe, Messwert die große Temperatur an Stelle des Symbols.':
        'Main text is the large line of a tile, the second line the small one below it. In the classic layout that is the name with the state below; in the new one the state is mostly large and the name small. Room is the room label, value the large temperature in place of the symbol.',
      'Ein leeres Feld nimmt den Standard des Kachel-Aufbaus; grau steht der des neuen Aufbaus.':
        'An empty field takes the default of the tile layout; shown in grey is the one of the new layout.',
      'Ein leeres Feld übernimmt die Vorgabe, sonst den Standard des Kachel-Aufbaus; grau steht, was dann gilt.':
        'An empty field takes the default, otherwise the default of the tile layout; shown in grey is what then applies.',
      'Schriftart': 'Font',
      'Schriftfarbe (Haupttext)': 'Text color (main text)',
      'Sprache': 'Language',
      'Steuert vorerst Datum & Uhr in der Visu. Gerätenamen kommen aus dem Miniserver.':
        'For now controls date & clock in the visu. Device names come from the Miniserver.',
      'Horiz. Versatz (px)': 'Horiz. offset (px)',
      'Display aus nach (Sek.)': 'Display off after (sec.)',
      'Gesicherte Bausteine': 'Secured blocks',
      'PIN merken (Sek.)': 'Remember PIN (sec.)',
      'Nach der richtigen Visu-PIN fragt die Visu bei gesicherten Bausteinen so lange nicht erneut – nur auf derselben Seite. Uhr-Seite, Display aus und Seitenwechsel vergessen die PIN sofort. 0 = jedes Mal fragen.':
        'After the correct visu PIN the visu does not ask again for secured blocks for this long – only on the same page. Clock page, display off and changing the page forget the PIN at once. 0 = ask every time.',
      'Auto-Neustart alle (Std.)': 'Auto-restart every (hrs.)',
      'nachts um {h} Uhr': 'at night at {h}:00',
      'Auto-Neustart gegen Einfrieren: Leer lädt die Visu jede Nacht um {h} Uhr neu, eine Zahl alle so viele Stunden, 0 nie. Neu geladen wird nur, während die Uhr-Seite steht; ein dunkles Display bleibt dabei dunkel. Linux-Geräte mit Agent starten stattdessen den Browser neu: nach der Zahl hier, ohne Eintrag nach RELOAD_HOURS in ihrer kiosk.conf.':
        'Auto-restart against freezing: empty reloads the visu every night at {h}:00, a number every that many hours, 0 never. It only reloads while the clock page is showing; a dark display stays dark. Linux devices with the agent restart the browser instead: per the number here, without an entry per RELOAD_HOURS in their kiosk.conf.',
      'Kacheln pro Zeile': 'Tiles per row',
      'Füllung': 'Fill',
      'Rahmen': 'Border',
      'Rahmenbreite': 'Border width',
      'Darstellung': 'Appearance',
      'Hintergrund': 'Background',
      'Icon-Farbe': 'Icon color',
      'Textfarbe': 'Text color',
      'Schrift': 'Font',
      // Optionen
      'Standard (Vorgabe)': 'Default (preset)',
      'System (Sans)': 'System (Sans)',
      'Eigene…': 'Custom…',
      'Rahmen + Füllung': 'Border + fill',
      'Nur Rahmen': 'Border only',
      'Nur Füllung': 'Fill only',
      '2 × 2 (4″-Wandpanel)': '2 × 2 (4″ wall panel)',
      '3 × 2 (Tablet)': '3 × 2 (tablet)',
      'Standard (Deutsch)': 'Default (German)',
      // Icon-Reiter / Kachel-Editor
      'Eingebaut': 'Built-in',
      'Google · Upload': 'Google · Upload',
      'Kachel zurücksetzen': 'Reset tile',
      'Standard': 'Default',
      'Alle einblenden': 'Show all',
      'Auf Standard zurücksetzen': 'Reset to default',
      'neutral': 'neutral',
      'Aktiv': 'Active',
      // Global-Editor
      '🌐 Vorgaben': '🌐 Defaults',
      'Schrift, Größe, Farbe und Stärke der Kachel-Beschriftung — gilt für alle Ansichten.':
        'Font, size, color and weight of the tile labels — applies to all views.',
      'Kategorie-Farben (Ampel)': 'Category colors (traffic light)',
      'Pro Kategorie eine <b>Aktiv-</b> und <b>OK-Farbe</b> für Kachel-Hintergrund und Rahmen — gilt auf allen Geräten (Wiedererkennung). ◐ einschalten = Zustands-Ampel (z. B. Alarm rot/grün, Tor gelb/grün). Aus = neutral. Analoge Messwerte bleiben immer neutral.':
        'Per category an <b>active</b> and an <b>OK</b> color for tile background and border — applies on all devices (recognizability). Turn on ◐ = state traffic light (e.g. alarm red/green, gate yellow/green). Off = neutral. Analog readings always stay neutral.',
      // Dialoge
      'Kennung der neuen Ansicht (klein, ohne Leerzeichen), z. B. wohnzimmer:':
        'Identifier of the new view (lowercase, no spaces), e.g. livingroom:',
      'Ungültige ID.': 'Invalid ID.'
    }
  };

  function detect() {
    try { var s = localStorage.getItem('lp_ui_lang'); if (s && (s === 'de' || CAT[s])) return s; } catch (e) {}
    var n = (navigator.language || 'de').toLowerCase().split('-')[0];
    return (n === 'de' || CAT[n]) ? n : 'de';
  }

  var LANG = detect();

  function T(s) {
    if (s == null) return s;
    if (LANG === 'de') return s;
    var m = CAT[LANG];
    return (m && m[s] != null) ? m[s] : s;
  }

  function apply(root) {
    root = root || document;
    root.querySelectorAll('[data-i18n]').forEach(function (el) {
      var k = el.getAttribute('data-i18n') || el.textContent.trim();
      if (k) el.textContent = T(k);
    });
    root.querySelectorAll('[data-i18n-ph]').forEach(function (el) {
      var k = el.getAttribute('data-i18n-ph') || el.getAttribute('placeholder') || '';
      if (k) el.setAttribute('placeholder', T(k));
    });
    root.querySelectorAll('[data-i18n-title]').forEach(function (el) {
      var k = el.getAttribute('data-i18n-title'); if (k) el.setAttribute('title', T(k));
    });
  }

  function mountSwitcher() {
    var host = document.querySelector('[data-langsel]');
    if (!host) return;
    var sel = document.createElement('select');
    sel.className = 'langsel';
    LANGS.forEach(function (l) {
      var o = document.createElement('option');
      o.value = l[0]; o.textContent = l[1];
      if (l[0] === LANG) o.selected = true;
      sel.appendChild(o);
    });
    sel.onchange = function () {
      try { localStorage.setItem('lp_ui_lang', sel.value); } catch (e) {}
      location.reload();
    };
    host.appendChild(sel);
  }

  // ---- Auto-Uebersetzer fuer JS-generierte Seiten (z.B. /config) ----
  // Uebersetzt nur BLATT-Elemente (reiner Text, keine Kind-Elemente) der
  // angegebenen Chrome-Selektoren und nur, wenn es eine Uebersetzung gibt
  // (sonst bleibt der deutsche Text). Miniserver-Namen sind nicht im Katalog
  // -> bleiben unangetastet. Reagiert per MutationObserver auf Neu-Rendern.
  var _sel = null, _pending = false;

  function applyChrome(root) {
    if (!_sel) return;
    (root || document).querySelectorAll(_sel).forEach(function (el) {
      if (el.children.length) {                   // formatierter Text (b/code/span): ueber innerHTML
        var h = (el.innerHTML || '').trim();
        if (!h) return;
        var th = T(h);
        if (th !== h) el.innerHTML = th;          // nur bei echter Uebersetzung schreiben
        return;
      }
      var k = (el.textContent || '').trim();
      if (!k) return;
      var t = T(k);
      if (t !== k) el.textContent = t;            // nur bei echter Uebersetzung schreiben
    });
  }

  function _schedule() {
    if (_pending) return;
    _pending = true;
    var raf = window.requestAnimationFrame || function (f) { setTimeout(f, 16); };
    raf(function () { _pending = false; applyChrome(document); });
  }

  function autoChrome(selectors) {
    _sel = selectors;
    applyChrome(document);
    try {
      new MutationObserver(_schedule).observe(document.body,
        { childList: true, subtree: true, characterData: true });
    } catch (e) {}
  }

  // Global verfuegbar fuer die Seiten-Skripte (T fuer dynamisch erzeugte Texte).
  window.I18N = { lang: LANG, t: T, apply: apply, applyChrome: applyChrome,
                  autoChrome: autoChrome, langs: LANGS };
  window.T = T;

  document.addEventListener('DOMContentLoaded', function () {
    document.documentElement.setAttribute('lang', LANG);
    mountSwitcher();
    apply(document);
  });
})();
