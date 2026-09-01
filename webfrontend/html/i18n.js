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
      'nicht verbunden': 'not connected'
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

  // Global verfuegbar fuer die Seiten-Skripte (T fuer dynamisch erzeugte Texte).
  window.I18N = { lang: LANG, t: T, apply: apply, langs: LANGS };
  window.T = T;

  document.addEventListener('DOMContentLoaded', function () {
    document.documentElement.setAttribute('lang', LANG);
    mountSwitcher();
    apply(document);
  });
})();
