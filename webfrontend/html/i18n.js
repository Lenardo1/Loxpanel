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
      // --- Nachgezogen: Assistent, Displays, Betriebsmodus, restliche Admin-UI ---
      "Standard-Farbschema": "Default color scheme",
      "Eine Farbe wählen — Hintergrund, Kacheln, Leiste, Schrift, Icons und Zustandsfarben werden daraus berechnet. Eigene Zustandsfarben behalten Vorrang.": "Pick a color — background, tiles, bar, text, icons and state colors are derived from it. Custom state colors keep priority.",
      "Eigene Farbe": "Custom color",
      "Keine": "None",
      "Standard-Aussehen für alle Panels. Einzelne Panels überschreiben es unter „Darstellung\".": "Default look for all panels. Individual panels override it under „Appearance“.",
      "Du bearbeitest": "You are editing",
      "Raum-Panel": "Room panel",
      "Klassisch": "Classic",
      "Eigene Auswahl": "Custom selection",
      "Ein Raum ist die Startseite — das Panel wacht direkt in diesem Raum auf (Licht &amp; Beschattung sofort bedienbar), ohne vorher zu wählen. Ideal für kleine 4″-Panels. Die untere Leiste zeigt automatisch die im Raum vorkommenden Kategorien — ein Tipp scrollt zu den passenden Bausteinen.": "A room is the start page — the panel wakes up directly in this room (light &amp; shading usable at once), without choosing first. Ideal for small 4″ panels. The bottom bar automatically shows the categories present in the room — a tap scrolls to the matching blocks.",
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
      "Wie eine Kachel im <b>aktiven Zustand</b> hervorgehoben wird (an = Akzent, ok = grün, kritisch = rot): Rahmen, Füllung und Deckkraft. Die <b>Farbe</b> kommt je Zustand aus dem Theme, hier stellst du das <b>Aussehen</b> ein. Darunter der Rahmen der <b>inaktiven</b> Kacheln <b>und der rechten Panes</b> (Pane 2, z. B. Energieflussmonitor, Wetter, Kalender) – Deckkraft und Breite hochdrehen, falls er auf hellen Displays (z. B. Shelly) kaum sichtbar ist. Gilt für dieses Panel — einzelne Kacheln können unten abweichen.": "How a tile is highlighted in the <b>active state</b> (on = accent, ok = green, critical = red): border, fill and opacity. The <b>color</b> comes from the theme per state, here you set the <b>look</b>. Below, the border of the <b>inactive</b> tiles <b>and the right panes</b> (pane 2, e.g. energy flow monitor, weather, calendar) – turn opacity and width up if it is barely visible on bright displays (e.g. Shelly). Applies to this panel — individual tiles can differ below.",
      "Inhalt": "Content",
      "Kein Energieflussmonitor in der Anlage.": "No energy flow monitor in the system.",
      "Kein Intercom-Baustein in der Anlage.": "No intercom block in the system.",
      "Kein Baustein mit Aufzeichnung in der Anlage.": "No block with logging in the system.",
      "Bausteine": "Blocks",
      "＋ hinzufügen …": "＋ add …",
      "Mehr passt nicht auf die Seite.": "No more fit on the page.",
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
      "Gewählt": "Selected",
      "Alle entfernen": "Remove all",
      "Alle Bausteine liegen im selben Raum – die untere Leiste bleibt darum ohne Sprungmarken.": "All blocks are in the same room – the bottom bar therefore stays without jump marks.",
      "Untere Leiste am Panel – ein Tipp scrollt zur Gruppe:": "Bottom bar on the panel – a tap scrolls to the group:",
      "In die Leiste passen 4 Sprungmarken – die Bausteine der weiteren Räume stehen trotzdem auf der Seite.": "The bar holds 4 jump marks – the blocks of the other rooms are still on the page.",
      "Fertig": "Done",
      "Eigene Auswahl einrichten": "Set up custom selection",
      "Diese Seite stellt Bausteine aus <b>beliebigen Räumen und Kategorien</b> zusammen – etwa alles, was du morgens brauchst. Die untere Leiste am Panel wird dabei zu <b>Sprungmarken auf die Räume</b> deiner Auswahl.": "This page combines blocks from <b>any rooms and categories</b> – e.g. everything you need in the morning. The bottom bar on the panel becomes <b>jump marks to the rooms</b> of your selection.",
      "Name der Seite": "Page name",
      "Auswahl": "Selection",
      "Ohne Namen heißt die Seite „Auswahl“.": "Without a name the page is called „Selection“.",
      "Weiter": "Next",
      "Tippe die Bausteine an, die auf die Seite sollen. Am Panel stehen sie <b>nach Räumen gruppiert</b> – ein Raum kommt dorthin, wo du seinen ersten Baustein angeklickt hast, innerhalb des Raums gilt die Klickreihenfolge. Genau diese Gruppen werden unten zu den Sprungmarken.": "Tap the blocks that should go on the page. On the panel they are <b>grouped by room</b> – a room appears where you clicked its first block, within the room the click order applies. Exactly these groups become the jump marks below.",
      "Zurück": "Back",
      "Die Seite": "The page",
      "zeigt": "shows",
      "Baustein": "block",
      "aus": "from",
      "Räumen": "rooms",
      "gewählter Baustein ist auf diesem Panel ausgeblendet und erscheint nicht.": "selected block is hidden on this panel and does not appear.",
      "gewählte Bausteine sind auf diesem Panel ausgeblendet und erscheinen nicht.": "selected blocks are hidden on this panel and do not appear.",
      "Schritt für Schritt": "Step by step",
      "Icon der Seite": "Page icon",
      "Tippen auf <b>×</b> nimmt einen Baustein wieder heraus; die Nummern rutschen nach.": "Tapping <b>×</b> removes a block again; the numbers shift up.",
      "Die Liste zeigt <b>alle</b> Bausteine der Anlage – der Raum- und Kategoriefilter dieses Panels gilt hier bewusst nicht, sonst könntest du nicht über ihn hinausgreifen. Ein auf diesem Panel <b>ausgeblendeter</b> Baustein bleibt ausgeblendet, auch wenn du ihn hier wählst.": "The list shows <b>all</b> blocks of the system – the room and category filter of this panel deliberately does not apply here, otherwise you couldn't reach beyond it. A block <b>hidden</b> on this panel stays hidden even if you select it here.",
      "Noch nichts gewählt – unten antippen.": "Nothing selected yet – tap below.",
      "ausgeblendet": "hidden",
      "Bibliothek": "Library",
      "Suchen… z. B. light, blind, alarm": "Search… e.g. light, blind, alarm",
      "Keine Loxone-Bibliothek gefunden — LoxoneIcons-Plugin installiert und gemountet?": "No Loxone library found — is the LoxoneIcons plugin installed and mounted?",
      "weitere — Suche eingrenzen": "more — narrow the search",
      "Nichts gefunden.": "Nothing found.",
      "Rechtes Pane je Ansicht": "Right pane per view",
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
      "Panel-Farbe": "Panel color",
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
      "Visu + rechte Fläche (je Tab wählbar).": "View + right area (selectable per tab).",
      "Kachel-Raster — frei wählbar": "Tile grid — freely selectable",
      "Wie möchtest du befüllen?": "How do you want to fill it?",
      "Ein Raum aus Loxone + Kategorien als Sprungtabs.": "One room from Loxone + categories as jump tabs.",
      "Standard-Tabs (Favoriten/Zentral/Räume/Kategorien).": "Standard tabs (Favorites/Central/Rooms/Categories).",
      "Eigene Seiten mit handverlesenen Kacheln (bis 4).": "Custom pages with hand-picked tiles (up to 4).",
      "Wie sollen die Kacheln aussehen?": "How should the tiles look?",
      "Einheitliches Design": "Uniform design",
      "Globale Kachelgrößen/Schrift. Später einzeln übersteuerbar.": "Global tile sizes/font. Overridable individually later.",
      "Individuell je Kachel": "Individual per tile",
      "Farbe, Schrift & Icon je Kachel — im Editor.": "Color, font & icon per tile — in the editor.",
      "Aktiv-Overlay — wie eine aktive Kachel hervorgehoben wird": "Active overlay — how an active tile is highlighted",
      "Gilt für das ganze Panel; einzelne Kacheln kannst du später im Editor abweichend einstellen.": "Applies to the whole panel; individual tiles can differ later in the editor.",
      "z. B. Wohnzimmer": "e.g. Living room",
      "Panel-ID": "Panel ID",
      "Aufruf am Panel:": "Open on the panel:",
      "Am 4″-Panel ist die Uhr-Seite einspaltig (Uhr + automatisch Termine/Wetter) — keine zweite Spalte.": "On the 4″ panel the clock page is single-column (clock + automatic events/weather) — no second column.",
      "Uhr-Seite — zweite Spalte": "Clock page — second column",
      "Automatik (Termine/Wetter)": "Automatic (events/weather)",
      "Aus — nur Uhr": "Off — clock only",
      "Statuswerte (mehrere Bausteine) in der Spalte legst du danach im Editor fest.": "Status values (multiple blocks) in the column are set afterwards in the editor.",
      "Energiefluss/Kamera/Verlauf erscheinen hier nur, wenn ein passender Baustein vorhanden ist.": "Energy flow/camera/history appear here only if a matching block exists.",
      "Zusammenfassung": "Summary",
      "Nach „Panel anlegen\" bist du im Editor zum Feinschliff (Kacheln, Pane 2, Icons) und kannst das Panel über „Visu öffnen\" testen.": "After „Create panel“ you are in the editor for fine-tuning (tiles, pane 2, icons) and can test the panel via „Open view“.",
      "Panel anlegen ✓": "Create panel ✓",
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
      "Noch kein Panel gefunden. Ein Panel erscheint, sobald es die Visu mit ?device=<name> öffnet oder der Agent darauf läuft.": "No panel found yet. A panel appears as soon as it opens the view with ?device=<name> or the agent runs on it.",
      "Geräte ohne Kennung (nach IP). Einen Namen vergeben, damit das Gerät dauerhaft gelistet und per Betriebsmodus umgeschaltet werden kann.": "Devices without an identifier (by IP). Assign a name so the device is listed permanently and can be switched by operating mode.",
      "Panel nicht erreicht": "Panel not reached",
      "Bitte einen Namen eingeben": "Please enter a name",
      "Display-Steuerung": "Display control",
      "keine (nur über die Seite)": "none (only via the page)",
      "Passwort (Fully)": "Password (Fully)",
      "Noch kein Panel bekannt. Sobald ein Panel die Visu mit Kennung öffnet oder ein Agent läuft, erscheint es hier.": "No panel known yet. As soon as a panel opens the view with an identifier or an agent runs, it appears here.",
      "Für welche Geräte?": "For which devices?",
      "Noch kein Gerät bekannt. Ein Panel muss die Visu einmal mit ?device=<name> öffnen oder einen Agent haben.": "No device known yet. A panel must open the view once with ?device=<name> or have an agent.",
      "Die Modus-Zuordnung gilt für alle gewählten Geräte gleich. Feinabstimmung je Gerät danach in der Detail-Tabelle.": "The mode assignment applies equally to all selected devices. Fine-tune per device afterwards in the detail table.",
      "Welche Betriebsmodi?": "Which operating modes?",
      "Loxone sendet": "Loxone sends",
      "Eigener Modus": "Custom mode",
      "z. B. Kino": "e.g. Cinema",
      "Hinzufügen": "Add",
      "Welche Ansicht bei welchem Modus?": "Which view for which mode?",
      "„Unverändert lassen\" heißt: dieser Modus schaltet das Panel nicht um.": "„Leave unchanged“ means: this mode does not switch the panel.",
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
      "Welche Visu welches Gerät zeigt. Linux-Panels mit Agent melden sich automatisch; Android-Panels und Tablets erscheinen, sobald sie die Visu mit einer Gerätekennung öffnen (?panel=<start>&device=<name>). Ein neues Gerät einrichten: Settings → Neues Panel.": "Which view each device shows. Linux panels with an agent register automatically; Android panels and tablets appear as soon as they open the view with a device identifier (?panel=<start>&device=<name>). Set up a new device: Settings → New panel.",
      "Geräte & Ansicht": "Devices & view",
      "Je Gerät die Ansicht (Profil) wählen und live umschalten. Geräte ohne Kennung stehen unten und bekommen hier einen Namen.": "Pick the view (profile) per device and switch live. Devices without an identifier are listed below and get a name here.",
      "🧭 Betriebsmodus-Assistent": "🧭 Operating-mode assistant",
      "Geführt: Modi → Ansicht je Gerät, mit fertiger Loxone-Adresse.": "Guided: modes → view per device, with a ready Loxone address.",
      "Betriebsmodus-Automatik & Display-Steuerung": "Operating-mode automation & display control",
      "Ansicht je Loxone-Betriebsmodus automatisch wechseln; Fully/WallPanel-Display schalten.": "Automatically switch view per Loxone operating mode; control Fully/WallPanel display.",
      "Display-Steuerung je Gerät: Bei Fully Kiosk die Remote-Admin-Schnittstelle einschalten (Port 2323, Passwort), bei WallPanel den HTTP-Server (Port 2971). Der Server schaltet das Display dann auch bei Klingel, Wecker, Notify und Goto ein und nach der Abschaltzeit aus, unabhängig von der Seite.": "Display control per device: for Fully Kiosk enable the remote admin interface (port 2323, password), for WallPanel the HTTP server (port 2971). The server then also turns the display on for doorbell, alarm, notify and goto, and off after the timeout, regardless of the page.",
      "Nachtmodus": "Night mode",
      "Wann die Panels abdunkeln (Auslöser oder Sonnenuntergang).": "When the panels dim (trigger or sunset).",
      "Wann die Panels abdunkeln. Ohne Auslöser entscheidet der Sonnenuntergang — die Zeiten kommen vom Miniserver, ersatzweise vom Wetterdienst. Als Auslöser lässt sich jeder Baustein mit Ein/Aus-Zustand wählen; sein Ein-Zustand bedeutet Nacht. Damit auch ein Loxone-Betriebsmodus, sobald er in Loxone Config auf einen Status-Baustein mit Raum und Kategorie gelegt ist — der Modus selbst steht nicht in der Visu.": "When the panels dim. Without a trigger, sunset decides — the times come from the Miniserver, or from the weather service as a fallback. Any block with an on/off state can be a trigger; its on state means night. That includes a Loxone operating mode, once it is mapped in Loxone Config to a status block with room and category — the mode itself is not in the view.",
      "Auslöser (optional)": "Trigger (optional)",
      "Wie stark abgedunkelt wird und ob eine Berührung kurz aufhellt, stellst du je Panel unter Panel Configuration → Darstellung ein.": "How much it dims and whether a touch briefly brightens is set per panel under Panel Configuration → Appearance.",
      "Port": "Port",
      "Weckton-Test und Audioserver-Live-Daten (Cover/Titel/Favoriten).": "Alarm-tone test and audio-server live data (cover/title/favorites).",
      "Audioserver (Cover / Titel / Favoriten)": "Audio server (cover / title / favorites)",
      "Loxone-Audioserver (Gen 2) liefern Cover/Titel/Interpret und Favoriten über einen eigenen Live-Kanal (Audioprotokoll, Port 7091) — genau wie die Loxone-App. LoxPanel abonniert diesen Kanal und legt die Infos über die passende Zone. Die Audioserver-Adresse wird automatisch aus der Loxone-Struktur erkannt — keine IP-Eingabe nötig. Funktioniert mit dem originalen Loxone-Audioserver ebenso wie mit Nachbauten (Sonn/Audioserver4Home). Musikserver-/MS4H-Zonen bleiben unberührt (die liefern es ohnehin).": "Loxone audio servers (Gen 2) deliver cover/title/artist and favorites over their own live channel (audio protocol, port 7091) — just like the Loxone app. LoxPanel subscribes to this channel and overlays the info onto the matching zone. The audio-server address is detected automatically from the Loxone structure — no IP entry needed. Works with the original Loxone audio server as well as with clones (Sonn/Audioserver4Home). Music-server/MS4H zones stay untouched (they deliver it anyway).",
      "Audioserver-Live-Daten abonnieren (automatisch)": "Subscribe to audio-server live data (automatic)",
      "Zwei Wege: ein Android-Panel oder Tablet mit Kiosk-App bekommt nur eine Start-URL; ein Linux-Panel bekommt den Agenten per SSH.": "Two ways: an Android panel or tablet with a kiosk app only gets a start URL; a Linux panel gets the agent via SSH.",
      "Android-Panel oder Tablet (Kiosk-App)": "Android panel or tablet (kiosk app)",
      "Start-URL in Fully Kiosk Browser oder WallPanel eintragen. Der Gerätename sorgt dafür, dass das Gerät unter Panels erscheint und per Betriebsmodus umgeschaltet werden kann. Display-Abschaltung: bei Fully die JavaScript-Schnittstelle einschalten oder oben einen Display-Treiber eintragen. Details in deploy/ANDROID.md.": "Enter the start URL in Fully Kiosk Browser or WallPanel. The device name ensures the device appears under Panels and can be switched by operating mode. Display shutoff: with Fully enable the JavaScript interface or enter a display driver above. Details in deploy/ANDROID.md.",
      "Start-URL erzeugen": "Generate start URL",
      "Linux-Panel mit Agent (SSH)": "Linux panel with agent (SSH)",
      // Rahmen / Navigation
      'Einstellungen': 'Settings',
      'Konfiguration': 'Configuration',
      'Kamera / Türstation': 'Camera / Door station',
      'bald': 'soon',
      'Neues Panel': 'New panel',
      '＋ Neues Panel': '＋ New panel',
      'Panels & Kacheln': 'Panels & tiles',
      'Ansichten gestalten': 'Design views',
      'Panels · Miniserver · Intercom': 'Panels · Miniserver · Intercom',
      'Visu öffnen': 'Open visu',
      'Panel-Ansicht anzeigen': 'Show panel view',
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
      // Kamera / Tuerstation
      'Video-URL (MJPEG) und Login der Türstation(en). Wird für das Kamerabild im Intercom-Popup gebraucht. Die Liste kommt aus dem Miniserver.':
        'Video URL (MJPEG) and login of the door station(s). Needed for the camera image in the intercom popup. The list comes from the Miniserver.',
      'Speichern': 'Save',
      // SIP
      'Gegensprechen über die Türstation direkt am Panel (SIP-Audio/-Video statt nur Kamerabild).':
        'Two-way audio via the door station directly on the panel (SIP audio/video instead of just the camera image).',
      'SIP-Anbindung ist in Arbeit.': 'SIP integration is in progress.',
      'Coming soon': 'Coming soon',
      // Panels
      'Panels mit installiertem Agent melden sich automatisch. Ansicht wählen und den Kiosk starten / aktualisieren.':
        'Panels with the agent installed register automatically. Pick a view and start / refresh the kiosk.',
      'Suche Panels…': 'Searching for panels…',
      'Noch kein Panel gefunden. Agent auf dem Panel starten (agent/loxpanel-agent.py).':
        'No panel found yet. Start the agent on the panel (agent/loxpanel-agent.py).',
      '(Standard)': '(Default)',
      'Start': 'Start',
      'Reload': 'Reload',
      'Stop': 'Stop',
      'Kiosk läuft': 'Kiosk running',
      'Status:': 'Status:',
      'Video-URL (MJPEG)': 'Video URL (MJPEG)',
      // Audio
      'Der Weckton (Loxone-Wecker) wird direkt im Kiosk-Browser des Panels erzeugt. Mit dem Test-Ton prüfst du, ob am Panel wirklich etwas zu hören ist — falls nicht, liegt es meist an der Lautstärke/Ausgabe am Gerät (ALSA/PulseAudio), nicht am Browser.':
        'The alarm tone (Loxone alarm clock) is generated directly in the panel’s kiosk browser. Use the test tone to check whether the panel actually plays sound — if not, it is usually the volume/output on the device (ALSA/PulseAudio), not the browser.',
      'Test-Ton': 'Test tone',
      'Sendet 3 kurze Pieptöne an das/die gewählte(n) Panel(s). Es müssen dafür geöffnet sein (Kiosk läuft und zeigt die Visu).':
        'Sends 3 short beeps to the selected panel(s). They must be open (kiosk running and showing the visu).',
      'Ziel-Panel': 'Target panel',
      '🔊 Test-Ton senden': '🔊 Send test tone',
      'Alle Panels': 'All panels',
      // Kalender & Wetter (Front / Screensaver)
      'Kalender & Wetter': 'Calendar & weather',
      'Zeigt Termine aus deinen iCal-Abos und das Wetter auf der Uhr-Startseite (Screensaver) aller Panels. Serverweit — der Server holt die Daten und schickt sie an die Panels.':
        'Shows events from your iCal subscriptions and the weather on the clock start page (screensaver) of all panels. Server-wide — the server fetches the data and pushes it to the panels.',
      'iCal-Kalender': 'iCal calendars',
      'Abo-Link aus Apple/iCloud (Kalender → Teilen → Öffentlicher Kalender), Google oder anderen Diensten. webcal:// oder https://. Nur Lesen, kein Login. Mehrere Kalender möglich — Geburtstage, Müllabfuhr, Ferien und die Familientermine landen gemeinsam auf einer Liste.':
        'Subscription link from Apple/iCloud (Calendar → Share → Public calendar), Google or other services. webcal:// or https://. Read-only, no login. Several calendars are possible — birthdays, waste collection, school holidays and family appointments all end up in one list.',
      'Überschrift am Panel': 'Heading on the panel',
      '＋ Kalender hinzufügen': '＋ Add calendar',
      'Feiertags-iCal (optional)': 'Holiday iCal (optional)',
      'z.B. österr. Feiertage aus Google Kalender (basic.ics)':
        'e.g. Austrian public holidays from Google Calendar (basic.ics)',
      'Optionaler zweiter iCal nur für Feiertage — deren Tage werden im Monatsraster rot markiert (wie Sonntage). Z.B. der Feiertagskalender deines Landes aus Google.':
        'An optional second iCal for public holidays only — those days are marked red in the month grid (like Sundays). For example your country’s holiday calendar from Google.',
      // Kalenderzeile
      'Kalender': 'Calendar',
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
      'Das Panel zeigt weiter den Stand von {zeit} Uhr.':
        'The panel still shows the data from {zeit}.',
      'Panel zeigt den Stand von {zeit} Uhr.': 'Panel is showing the data from {zeit}.',
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
      'Kalenderfarben am Panel zeigen': 'Show calendar colors on the panel',
      'Aus = schlicht: alle Termine einfarbig, nur der Kalendername steht daneben. An = jeder Kalender bekommt seinen Farbpunkt, auch im Monatsraster.':
        'Off = plain: all events in a single color, only the calendar name beside them. On = every calendar gets its color dot, in the month grid too.',
      '„Termine auf der Uhr-Seite" ist eine Obergrenze — was neben Wetter und Uhr nicht mehr auf den Schirm passt, bleibt weg (auf einem 480×480-Panel sind das etwa drei). Die vollständige Liste steht im Kalender-Pane.':
        '“Events on the clock page” is an upper limit — whatever no longer fits on the screen next to the weather and the clock is left out (on a 480×480 panel that is about three). The full list is in the calendar pane.',
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
      'Neues Panel einrichten': 'Set up a new panel',
      'Erzeugt den Befehl, der Agent + Config aufs Panel überträgt, den Autostart einrichtet und Chromium still stellt (keine Übersetzen-Leiste / Anmeldung). Einmal im Terminal ausführen — fragt nach dem SSH-/sudo-Passwort des Panels.':
        'Generates the command that copies agent + config to the panel, sets up autostart and quiets Chromium (no translate bar / sign-in). Run once in a terminal — it asks for the panel’s SSH/sudo password.',
      'Panel-IP': 'Panel IP',
      'SSH-Benutzer': 'SSH user',
      'Anzeigename': 'Display name',
      'Startansicht (Profil)': 'Start view (profile)',
      'Server-Adresse (dieser Server)': 'Server address (this server)',
      'Befehl erzeugen': 'Generate command',
      'In Zwischenablage kopieren': 'Copy to clipboard',
      'Panel-IP und Server-Adresse nötig': 'Panel IP and server address required',
      '✓ kopiert': '✓ copied',
      'Kopieren nicht möglich – bitte manuell markieren': 'Copy failed – please select manually',
      'Fehler': 'Error',
      'Keine Intercom-Bausteine gefunden (Miniserver verbunden?).':
        'No intercom blocks found (Miniserver connected?).',
      '✓ Gespeichert': '✓ Saved',
      'verbunden': 'connected',
      'nicht verbunden': 'not connected',

      // ---- Betriebsmodus-Automatik (/settings) ----
      'Betriebsmodus-Automatik': 'Operating-mode automation',
      'Loxone schaltet die Ansicht automatisch um: in Loxone Config einen virtuellen HTTP-Ausgang anlegen, der pro Betriebsart einen Modusnamen an diesen Server schickt. Hier legst du je Panel fest, welche Ansicht bei welchem Modus erscheint. Panel ohne Eintrag für einen Modus bleibt unverändert.':
        'Loxone switches the view automatically: in Loxone Config create a virtual HTTP output that sends a mode name to this server per operating mode. Here you define, per panel, which view appears for which mode. A panel without an entry for a mode stays unchanged.',
      'Panels mit Agent (Linux) erscheinen automatisch. Ein Panel ohne Agent (z.B. NSPanel Pro, Tablet) muss nur die Visu mit einer Geräte-Kennung öffnen: ?panel=<start>&device=<name> — dann wird es hier gelistet und live umgeschaltet (Browser lädt sich mit neuem Profil neu, kein Agent nötig).':
        'Panels with an agent (Linux) appear automatically. A panel without an agent (e.g. NSPanel Pro, tablet) just opens the visu with a device id: ?panel=<start>&device=<name> — then it is listed here and switched live (the browser reloads with the new profile, no agent needed).',
      'Noch kein Panel bekannt. Ein Panel muss sich einmal gemeldet haben (Agent läuft), dann erscheint es hier.':
        'No panel known yet. A panel must have reported in once (agent running), then it appears here.',
      'Automatik speichern': 'Save automation',
      '— Ansicht wählen —': '— choose view —',
      'Modus (z.B. gaeste)': 'Mode (e.g. guests)',
      'Automatik aktiv': 'Automation active',
      '+ Modus': '+ Mode',
      'Zeile entfernen': 'Remove row',

      // ---- /config (Panel-Editor) ----
      'Konfiguration': 'Configuration',
      '＋ Neues Panel': '＋ New panel',
      'Titel': 'Title',
      'Fenstertitel des Panels.': 'Window title of the panel.',
      'Kiosk-URL:': 'Kiosk URL:',
      'Standard-Aussehen für <b>alle</b> Panels. Einzelne Panels können es unter „Darstellung" überschreiben (leer = erbt global).':
        'Default look for <b>all</b> panels. Individual panels can override it under "Appearance" (empty = inherits global).',
      'Untere Leiste (Tabs)': 'Bottom bar (tabs)',
      'Bis zu <b>4 Buttons</b> — die 4 Standard-Tabs und/oder einzelne Kategorien als Abkürzung. Der <b>erste aktive</b> ist die Startseite (★). ':
        'Up to <b>4 buttons</b> — the 4 standard tabs and/or individual categories as shortcuts. The <b>first active</b> one is the start page (★). ',
      'Räume': 'Rooms',
      'Welche Räume dieses Panel zeigt. <b>Nichts angehakt = alle Räume.</b>':
        'Which rooms this panel shows. <b>Nothing checked = all rooms.</b>',
      'Alle abwählen': 'Deselect all',
      'Kategorien': 'Categories',
      'Welche Kategorien im Tab „Kategorien" erscheinen. <b>Nichts angehakt = alle.</b> Bei gesetzter Raum-Auswahl werden Kategorien zusätzlich auf diese Räume gefiltert.':
        'Which categories appear in the "Categories" tab. <b>Nothing checked = all.</b> If a room selection is set, categories are additionally filtered to those rooms.',
      'Kacheln gestalten': 'Style tiles',
      'Klicke eine Kachel an und ändere <b>Farben, Schrift und Icon nur für diese Kachel</b> (auf diesem Panel). Farbiger Punkt = schon angepasst. Mit dem <b>Auge</b> rechts blendest du eine Kachel auf diesem Panel ganz aus. ':
        'Click a tile and change <b>colors, font and icon for this tile only</b> (on this panel). Colored dot = already customized. Use the <b>eye</b> on the right to hide a tile entirely on this panel. ',
      'Kachel suchen…': 'Search tile…',
      'Darstellung (optional)': 'Appearance (optional)',
      'Überschreibt das globale Theme nur für dieses Panel. Leer = global.':
        'Overrides the global theme for this panel only. Empty = global.',
      'Aktiv-Overlay': 'Active overlay',
      'Wie eine Kachel im <b>aktiven Zustand</b> hervorgehoben wird (an = Akzent, ok = grün, kritisch = rot): Rahmen, Füllung und Deckkraft. Die <b>Farbe</b> kommt je Zustand aus dem Theme, hier stellst du das <b>Aussehen</b> ein. Gilt für dieses Panel — einzelne Kacheln können unten abweichen.':
        'How a tile is highlighted in its <b>active state</b> (on = accent, ok = green, critical = red): border, fill and opacity. The <b>color</b> per state comes from the theme; here you set the <b>look</b>. Applies to this panel — individual tiles can differ below.',
      'Panel löschen': 'Delete panel',
      'Kein Panel gewählt.': 'No panel selected.',
      'keine Kacheln im gewählten Raum-/Kategorie-Filter': 'no tiles in the selected room/category filter',
      'nichts gefunden': 'nothing found',
      // Labels
      'Icon-Größe': 'Icon size',
      'Name-Größe': 'Name size',
      'Sub-Größe': 'Sub size',
      'Schriftart': 'Font',
      'Schriftfarbe (Name)': 'Text color (name)',
      'Sprache': 'Language',
      'Steuert vorerst Datum & Uhr am Panel. Gerätenamen kommen aus dem Miniserver.':
        'For now controls date & clock on the panel. Device names come from the Miniserver.',
      'Horiz. Versatz (px)': 'Horiz. offset (px)',
      'Display aus nach (Sek.)': 'Display off after (sec.)',
      'Auto-Neustart alle (Std.)': 'Auto-restart every (hrs.)',
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
      'Standard (global)': 'Default (global)',
      'System (Sans)': 'System (Sans)',
      'Eigene…': 'Custom…',
      'Rahmen + Füllung': 'Border + fill',
      'Nur Rahmen': 'Border only',
      'Nur Füllung': 'Fill only',
      '2 × 2 (4″-Panel)': '2 × 2 (4″ panel)',
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
      '🌐 Globale Darstellung': '🌐 Global appearance',
      'Schrift, Größe, Farbe und Stärke der Kachel-Beschriftung — gilt global für alle Panels.':
        'Font, size, color and weight of the tile labels — applies globally to all panels.',
      'Kategorie-Farben (Ampel)': 'Category colors (traffic light)',
      'Pro Kategorie eine <b>Aktiv-</b> und <b>OK-Farbe</b> für Kachel-Hintergrund und Rahmen — gilt systemweit auf allen Panels (Wiedererkennung). ◐ einschalten = Zustands-Ampel (z. B. Alarm rot/grün, Tor gelb/grün). Aus = neutral. Analoge Messwerte bleiben immer neutral.':
        'Per category an <b>active</b> and an <b>OK</b> color for tile background and border — applies system-wide on all panels (recognizability). Turn on ◐ = state traffic light (e.g. alarm red/green, gate yellow/green). Off = neutral. Analog readings always stay neutral.',
      // Skalierung / Bildschirmgroesse
      'Skalierung': 'Scaling',
      'Wie im Profil': 'Same as profile',
      'Aus (feste Größe)': 'Off (fixed size)',
      'Automatisch (Bildschirm ausnutzen)': 'Automatic (use the screen)',
      'Fest': 'Fixed',
      'quer': 'landscape',
      'hoch': 'portrait',
      'quadratisch': 'square',
      'physisch': 'physical',
      'Visu': 'visu',
      'nutzt': 'uses',
      'Skalierung „Automatisch": Jedes Display vergrößert die Visu so weit, wie es ohne Rand und ohne Verzerrung geht – Schrift, Icons, Uhr-Seite und Panes wachsen mit. Ein fester Faktor wird nie größer, als der Bildschirm hergibt. Wirkt nicht zusammen mit „Bildschirm füllen", das den Schirm schon ausfüllt. „Wie global" übernimmt die Einstellung unter Global → Darstellung; pro Gerät übersteuerbar unter Settings → Panels.':
        'Scaling "Automatic": each display enlarges the visu as far as it can without borders or distortion – text, icons, clock page and panes grow along. A fixed factor never exceeds what the screen allows. Has no effect together with "Fill screen", which already fills the screen. "Same as global" takes the setting under Global → Appearance; can be overridden per device under Settings → Panels.',
      'Wie global': 'Same as global',
      'Standard für alle Panels': 'Default for all panels',
      'Aus': 'Off',
      'Gilt für alle Panels, deren Profil „Wie global" eingestellt hat. „Automatisch" vergrößert die Visu auf jedem Display so weit, wie es ohne Rand und ohne Verzerrung geht. Ein Profil kann das unter Aussehen übersteuern, ein einzelnes Gerät unter Settings → Panels.':
        'Applies to all panels whose profile is set to "Same as global". "Automatic" enlarges the visu on every display as far as it can without borders or distortion. A profile can override this under Appearance, a single device under Settings → Panels.',
      // Dialoge
      'ID des neuen Panels (klein, ohne Leerzeichen), z. B. wohnzimmer:':
        'ID of the new panel (lowercase, no spaces), e.g. livingroom:',
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
      if (el.children.length) return;             // nur reine Textknoten
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
