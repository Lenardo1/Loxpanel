# LoxPanel

**Eine konfigurierbare Touch-Visu für Loxone** – verwandelt jedes Display
(Wandpanel, Tablet oder Handy) in eine aufgeräumte, frei gestaltbare
Bedienoberfläche für den Loxone Miniserver. LoxPanel läuft als **Docker-Container
auf dem LoxBerry** (Plug&Play-Plugin); eingerichtet und gestaltet wird alles im
Browser – ganz ohne Programmierung und ohne die Loxone-App.

> Status: **lauffähig & produktiv einsetzbar.** Verbindet sich per WebSocket mit
> dem Miniserver (Token-Auth), liest die Struktur automatisch ein und steuert live.

## Inhalt

- [Funktionen](#funktionen)
- [Unterstützte Bausteine](#unterstützte-bausteine)
- [Der Panel-Agent (Wandpanel-Kiosk)](#der-panel-agent-wandpanel-kiosk)
- [Voraussetzungen](#voraussetzungen)
- [Installation als LoxBerry-Plugin](#installation-als-loxberry-plugin)
- [Konfiguration](#konfiguration)
- [Updates](#updates)
- [Sicherung (Backup & Wiederherstellung)](#sicherung-backup--wiederherstellung)
- [Datenschutz](#datenschutz)
- [Weitere Installationsarten](#weitere-installationsarten-ohne-loxberry)
- [Architektur](#architektur)
- [Roadmap](#roadmap)
- [Changelog](#changelog)

## Screenshots

**Visu am Panel** — Favoriten mit Status, Musik-Player, Musikauswahl, PIN-geschützte Tür, Intercom-Livebild, Räume:

![Visu](docs/screenshots/kiosk1.png)

**Am Wandpanel** (Linux-Panel im Chromium-Kiosk):

![Wandpanel](docs/screenshots/kiosk2.png)

**Konfiguration im Browser** — Panel-Profile: pro Gerät Räume, Kategorien und Tabs an-/abwählen:

![Panel-Profile](docs/screenshots/panel.png)

**Pro Kachel gestalten** — Hintergrund, Rahmen, Icon- und Textfarbe, Schrift und Icon (eingebaut / Loxone) je Kachel:

![Kachel-Editor](docs/screenshots/kacheln.png)

**Einstellungen** — Miniserver und Intercom eintragen, **Panels automatisch finden und den Kiosk fernstarten**:

![Einstellungen](docs/screenshots/intercom.png)

**Layout-Varianten** je Detailseite (einzeln / gestapelt / 2×2 / Liste):

![Layouts](docs/screenshots/kacheln2.png)

## Funktionen

- **Automatische Struktur-Erkennung:** verbindet sich mit dem Miniserver und liest
  Räume, Kategorien und Bausteine automatisch ein – kein manuelles Anlegen von
  Bedienelementen.
- **Navigation wie die Loxone-App:** untere Tab-Leiste **Favoriten / Zentral /
  Räume / Kategorien**, scrollbare Kachelseiten, Detailseiten je Baustein.
- **Übersicht mit Farben & Werten:** aktive Kacheln farbig hervorgehoben, Alarm
  grün „Ok", Zentral-Bausteine mit Zähltext („Licht in X Räumen", „Musik in X
  Räumen"), Energie/Temperatur/Statustexte mit Einheiten-Skalierung.
- **Frei gestaltbare Panels (Profile):** beliebig viele Ansichten – z. B.
  „Wohnzimmer", „Poolhaus", „Handy". Pro Panel wählbar, **welche** Räume,
  Kategorien und Tabs sichtbar sind; einzelne Kacheln gezielt ausblenden.
- **Pro-Kachel-Styling:** je Kachel Hintergrund, Rahmen, Icon- und Textfarbe,
  Schrift und Icon (eingebaute Icons, Loxone-Icons, eigene). Konfigurierbares
  Aktiv-Overlay (Farbe/Transparenz von Füllung und Rahmen), global oder pro Kachel.
- **Ein Design für alle Geräte:** dieselbe Oberfläche skaliert auf Wandpanel,
  Tablet und Smartphone.
- **Musik** (Loxone AudioZone): Zonen-Liste mit Mini-Player (◀ ⏯ ▶) und voller
  Raum-Player mit Cover (über den Miniserver).
- **Intercom** (z. B. Mobotix T25): Live-Bild (MJPEG mit Auth), Tür öffnen &
  Außenlicht, Klingel-Popup (der Server erkennt den `bell`-State und schiebt die
  Ansicht aufs Panel). Gegensprechen (SIP) folgt.
- **Theming:** Kategorie-Farben, Zustandsfarben, Icon-/Schriftgrößen, sichtbare
  Tabs und Schrift zentral einstellbar.
- **Sicherung an Bord:** Backup & Wiederherstellung der kompletten Konfiguration
  direkt im Plugin – überlebt auch Updates.

## Unterstützte Bausteine

Aktuell rund **40 Loxone-Bausteine**, u. a.: Licht (LightControllerV2 mit
Stimmungen), Jalousie/Rollladen, Tor/Gate, Taster/Schalter (Switch/Pushbutton),
Heizung (IRoomControllerV2 – Ist/Soll, Betriebsmodi), Klima (AcControl),
Zentralsteuerung (ClimateControllerUS), Wetter, Wecker (AlarmClock), Wochenschaltuhr
(Daytimer), Tracker/Ereignisliste, Meter/Slider/Text, Alarmanlage, sowie diverse
Zentralfunktionen (Central­Light/-Audio/-Gate/-Window …).

Noch offen: u. a. Remote, AudioZoneV2 – siehe [Roadmap](#roadmap).

## Der Panel-Agent (Wandpanel-Kiosk)

Für ein **dediziertes Linux-Wandpanel** (z. B. ein 4-Zoll-PX30-Panel im
Chromium-Kiosk) gibt es einen kleinen, **optionalen** Helfer: den **Panel-Agent**.

> **Wichtig zum Verständnis:** Der Agent ist **nicht** Teil des LoxBerry-Containers.
> Er läuft **direkt auf dem Wandpanel**. Tablets, Handys oder ein normaler Browser
> brauchen ihn **nicht** – die rufen einfach die Visu-URL des LoxBerry auf. Der
> Agent lohnt sich nur, wenn ein Panel als fest verbauter Kiosk laufen soll.

**Warum getrennt?** Der LoxPanel-Server (im LoxBerry-Container) liefert die Visu.
Die **lokale Hardware des Panels** – Bildschirm, Hintergrundbeleuchtung, der
Chromium-Kiosk – kann ein Container auf dem LoxBerry aber nicht steuern. Genau das
übernimmt der Agent auf dem Gerät.

**Was der Agent macht:**

- **Kiosk-Autostart:** startet Chromium im Vollbild mit der richtigen Panel-URL
  (`?panel=<id>`) automatisch beim Booten.
- **Auto-Discovery:** meldet das Panel selbstständig beim Server – es erscheint in
  **Einstellungen → Panels**. Von dort lässt sich die Ansicht wählen und der Kiosk
  **fernstarten / neu laden**.
- **Echte Display-Abschaltung:** schaltet nach Inaktivität nicht nur das Bildsignal,
  sondern die **Hintergrundbeleuchtung** ab (alle Backlight-Devices) → das Panel
  wird wirklich dunkel **und kühl**. Antippen weckt es sofort.
- **Stromspar-Pause:** friert den Chromium-Kiosk bei dunklem Display ein und setzt
  ihn beim Aufwachen fort → deutlich weniger CPU-Last und Wärme im Ruhezustand.
- **Auto-Neustart gegen Einfrieren:** startet den Kiosk optional periodisch neu,
  falls der Browser mal hängt.
- **Robuster Neustart:** bereinigt nach einem Stromausfall den „Wiederherstellen?"-
  Dialog von Chromium, damit der Kiosk ohne Eingriff wieder hochkommt.

**Installation (per SSH auf dem Panel):** ein Skript richtet Agent + Autostart ein:

```bash
SERVER=<loxberry-ip>:8099 bash deploy/install-agent.sh
```

Einstellungen danach in `/etc/loxpanel/kiosk.conf` – u. a.:

| Schlüssel | Bedeutung |
|---|---|
| `SERVER` | IP:Port des LoxPanel-Servers (LoxBerry) |
| `PANEL` | Panel-Profil / Startansicht (leer = Standard) |
| `DPMS_OFF` | Sekunden bis zur Display-Abschaltung (0 = nie) |
| `BL_ON` | Helligkeit im Ein-Zustand (0…max; leer = voll) |
| `PAUSE_ON_BLANK` | Chromium bei dunklem Display pausieren (1 = an) |
| `AUTOSTART` | Kiosk beim Booten starten (1) oder nur auf Fernstart warten (0) |

Details: [`deploy/DEPLOY.md`](deploy/DEPLOY.md).

## Voraussetzungen

- **LoxBerry 3.0** oder neuer.
- Architektur **aarch64 / x86_64 / armhf** (Raspberry Pi 3/4/5 und x86).
- **Docker** – wird vom Plugin bei Bedarf automatisch installiert.
- Erreichbarer **Loxone Miniserver** (Gen1 oder Gen2).

## Installation als LoxBerry-Plugin

1. LoxBerry → **Plugin-Verwaltung**.
2. Plugin per ZIP-URL installieren:
   `https://github.com/Lenardo1/Loxpanel/releases/latest/download/loxpanel-plugin.zip`
3. Das Plugin installiert bei Bedarf Docker und startet den LoxPanel-Container
   automatisch. Danach erreichst du alles über das Plugin-Widget in LoxBerry.

## Konfiguration

**1. Miniserver verbinden** – im Plugin-Widget IP, Benutzer, Passwort und Port
eintragen, oder mit einem Klick **„Aus LoxBerry übernehmen"**: LoxPanel holt sich
den Zugang aus der **zentralen LoxBerry-Miniserver-Konfiguration**. Anschließend
lädt es die Struktur automatisch.

**2. Panels & Kacheln gestalten** – über **„Panels & Kacheln öffnen"** landest du
im Konfigurator: Ansichten anlegen, Räume/Kategorien/Tabs je Panel wählen, Kacheln
ein-/ausblenden, Farben, Icons und Schrift pro Kachel einstellen.

**3. Panels verwalten** – unter **„Settings öffnen"** siehst du alle Wandpanels mit
[installiertem Agent](#der-panel-agent-wandpanel-kiosk), wählst deren Ansicht und
startest/aktualisierst den Kiosk aus der Ferne.

**Panel-Profile im Detail:** Ein Server versorgt beliebig viele Panels; jedes Gerät
kann eine eigene Visu zeigen. Der Kiosk ruft die Seite mit `?panel=<id>` auf; der
Server lädt das passende Profil. Pro Profil einstellbar: sichtbare Tabs, Whitelist
der Räume/Kategorien (UUID oder Name, Teilstring genügt), Theme-Override und
Zustandsfarben. Ohne Profil verhält sich ein Panel wie `default` (alles sichtbar).

## Updates

- **App-Updates** (neue LoxPanel-Version) holst du im Plugin-Widget per Button
  **„Jetzt updaten / Neu starten"** – zieht das aktuelle Image und startet neu.
- Der Fortschritt wird live im **Log-Fenster** angezeigt.
- Deine Panels und Einstellungen bleiben dabei **immer erhalten** (eigenes
  Daten-Volume; zusätzlich werden sie bei Plugin-Updates gesichert).

## Sicherung (Backup & Wiederherstellung)

Im Plugin-Widget unter **„Panels sichern & wiederherstellen"** legst du jederzeit
ein Backup der kompletten Konfiguration (Panels, Kacheln, Theme, Miniserver-Zugang)
an. Die Archive liegen auf dem LoxBerry unter
`data/plugins/loxpanel/backups/` und **überleben Plugin-Updates**. Aus der Liste
lässt sich ein Stand mit einem Klick wiederherstellen (der aktuelle Stand wird
vorher automatisch gesichert).

## Datenschutz

LoxPanel läuft **vollständig lokal**: Die Verbindung besteht nur zwischen LoxBerry
und dem Miniserver in deinem Netz. Es gibt **keine Cloud**, kein Konto und keine
Telemetrie. Zugangsdaten liegen ausschließlich lokal im Daten-Volume.

## Weitere Installationsarten (ohne LoxBerry)

LoxPanel ist ein normaler Docker-Dienst und läuft auch ohne LoxBerry – gleiche
Server-Basis, gleiches Image `ghcr.io/lenardo1/loxpanel:latest` (multi-arch:
amd64 / arm64 / **armv7**).

**Portainer / docker compose:**

```yaml
services:
  loxpanel:
    image: ghcr.io/lenardo1/loxpanel:latest
    container_name: loxpanel
    restart: unless-stopped
    ports:
      - "8099:8099"
    environment:
      LOXPANEL_MS_HOST: "192.168.1.50"     # Miniserver-IP
      LOXPANEL_MS_USER: "LoxoneUser"
      LOXPANEL_MS_PASS: "dein-passwort"
      LOXPANEL_MS_PORT: "443"
      LOXPANEL_MS_VERIFY_TLS: "false"       # Gen2 selbstsigniert -> false
    volumes:
      - loxpanel_config:/app/config          # panels.json / theme.json / loxpanel.cfg persistent
volumes:
  loxpanel_config:
```

Danach: Visu `http://<host>:8099`, Konfig `…/config`, Einstellungen `…/settings`.
Zugangsdaten per Env **oder** leer lassen und in `/settings` eintragen.

**Für Entwickler (Standalone):**

```bash
pip install loxone-api            # zieht aiohttp mit
cp config/loxpanel.cfg.example config/loxpanel.cfg   # Miniserver eintragen (gitignored)
python bin/webvisu.py             # -> http://localhost:8099
```

Details: [`deploy/DOCKER.md`](deploy/DOCKER.md) / [`deploy/DEPLOY.md`](deploy/DEPLOY.md).

## Architektur

```
Loxone Miniserver ──WebSocket(Token)──►  webvisu.py (aiohttp)   ─┐
        ▲  (Befehle via loxone-api / jdev)      │  WebSocket+HTTP │ Docker-Container
        └───────────────────────────────────────┘                │ (LoxBerry-Plugin)
                                                 ▼               ─┘
                                       Browser-Panel (Kacheln, Tabs, Detailseiten)
                                       ├─ Wandpanel: Chromium-Kiosk + Panel-Agent
                                       └─ Tablet / Handy: einfach die URL öffnen
```

- **loxone-api** (PyPI): Token-Auth (getkey2/getjwt), Struktur, Befehle.
- **loxone_ws.py**: WebSocket-Client für Live-Werte (binäre State-Tabellen).
- **adapters.py**: pro Control-Typ ein Adapter (Zustand → Kachel, Aktion → Befehl).
- **webvisu.py**: Server – baut Views/Blocks, streamt sie per WebSocket, proxyt
  Icons/Cover/MJPEG, sendet das Theme.
- **panel.html**: die Single-Page-Visu (Kacheln, Detail-Panels, Tabs, Theme).
- **agent/loxpanel-agent.py**: der [Panel-Agent](#der-panel-agent-wandpanel-kiosk)
  auf dem Wandpanel.

## Roadmap

- Intercom Teil 2: **Gegensprechen** (SIP-Client auf dem Panel).
- Weitere Bausteine (u. a. Remote, AudioZoneV2) und Heizung-Modus-Umschaltung.
- Musiksteuerung mit austauschbarem Audio-Backend (MS4H/LMS).
- Optionaler openHASP-Renderer (ESP32) als kuratierter Satellit.

## Changelog

- **0.2.6** – Miniserver-Felder nebeneinander (mehr Platz); Button „Aus LoxBerry übernehmen".
- **0.2.5** – Backup & Wiederherstellung der Konfiguration im Plugin-Widget.
- **0.2.4** – Container-Aktionen laufen im Hintergrund + Live-Statuslog (kein Timeout mehr).
- **0.2.x** – erstes öffentliches LoxBerry-Plugin (Docker, automatische Installation).

## Support & Quellcode

Fragen, Ideen und Fehlerberichte gerne als GitHub-Issue:
<https://github.com/Lenardo1/Loxpanel>
