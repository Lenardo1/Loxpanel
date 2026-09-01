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
