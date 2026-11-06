# LoxPanel – LoxBerry-Plugin (Docker)

Betreibt **LoxPanel** als Docker-Container auf einem LoxBerry – nach dem Vorbild
von *AudioServer4Home*. Das Plugin selbst ist schlank: Es installiert Docker
(falls nötig), startet den LoxPanel-Container aus der GitHub Container Registry
und hält ihn am Laufen. Die gesamte App (Server + Weboberfläche) steckt im Image.

## Was das Plugin macht

- installiert bei Bedarf **Docker** (offizielles Docker-Repo, Pakete via `dpkg/apt`)
- startet `ghcr.io/lenardo1/loxpanel:latest` per `docker compose` (Port
  **8099**, im Widget einstellbar, siehe „Port am LoxBerry“)
- startet das Panel beim **Boot** (`daemon` → `loxpanel-ctl.sh boot`) und prüft
  alle **5 Minuten**, ob der Container läuft (`cron.05min` → `loxpanel-ctl.sh check`)
- nimmt Konfiguration und Sicherungen über Plugin-Updates mit (`preroot.sh`/`postroot.sh`);
  lässt sich die Konfiguration nicht sichern, bricht das Update ab, bevor LoxBerry
  etwas löscht, fehlen nur die Sicherungen, warnt es und läuft weiter
- entfernt Container + Image beim Deinstallieren

## Bedienung

Nach der Installation (und einem Reboot, falls LoxBerry danach einen anfordert –
nur wenn Docker frisch installiert wurde und noch nicht bereit ist; Updates
kommen ohne Neustart aus):

- **Konfiguration:** `http://<LoxBerry-IP>:<Port>/config` (Panels, Räume, Kacheln)
- **Einstellungen:** `http://<LoxBerry-IP>:<Port>/settings` (Miniserver-Zugang, Intercom, Displays)
- Das LoxBerry-Plugin-Widget verlinkt beide mit dem eingestellten Port.

Der Miniserver-Zugang wird **nicht** im Plugin gesetzt, sondern über die
Einstellungen-Seite und in `data/plugins/loxpanel/config/loxpanel.cfg`
(Docker-Volume) gespeichert. Das Widget reicht ihn nur weiter, wenn unter dem
Port wirklich LoxPanel antwortet. **„Aus LoxBerry übernehmen“** nimmt den
ersten Miniserver aus LoxBerry; ist dort „HTTPS bevorzugen“ an, dessen
HTTPS-Port, sonst den HTTP-Port (LoxPanel wählt das Schema am Port: 80 = HTTP,
sonst HTTPS).

## Port am LoxBerry

Standard ist **8099**, derselbe Port wie im Container. Belegt ein anderes Plugin
ihn, im Widget unter **„Port am LoxBerry“** einen freien eintragen und
übernehmen: Ein laufendes LoxPanel startet dann damit neu. Panels und die App
brauchen danach die neue Adresse. Der Port steht in
`config/plugins/loxpanel/loxpanel_plugin.cfg` (`PORT=…`), Plugin-Updates nehmen
ihn mit (`preroot.sh`/`postroot.sh`). `loxpanel-ctl.sh start` schreibt daraus
`docker-compose.port.env` und startet Compose mit `--env-file`.

Ist der Port schon belegt, startet LoxPanel nicht erst (Docker scheiterte am
Port, und unter ihm antwortete das andere Programm). Das Widget zeigt dann,
wer ihn belegt: einen Docker-Container mit Namen oder „ein anderes Programm“.

## Stoppen

**„Stoppen“** hält LoxPanel an, bis **„Starten“** oder bis zum nächsten
Neustart des LoxBerry; so lange startet die 5-Minuten-Prüfung es nicht. Das
Widget zeigt, seit wann es gestoppt ist.

## Zeitzone

Der Container übernimmt die Zeitzone des LoxBerry: `loxpanel-ctl.sh start` legt
`docker-compose.zeitzone.yml` neben die Compose-Datei. Sie bindet
`/etc/localtime` des LoxBerry nur lesend als `/run/loxberry-localtime` ein und
setzt `TZ=":/run/loxberry-localtime"`; eine Zone steht nirgends fest. Fehlt
`/etc/localtime` oder zeigt der Symlink ins Leere, startet LoxPanel ohne sie in
UTC und schreibt eine Warnung in den Verlauf.

Nach einer Änderung der Zeitzone im LoxBerry LoxPanel neu starten (Widget:
**„Jetzt updaten / Neu starten"**); ein Neustart des LoxBerry übernimmt sie
ebenfalls.

## Voraussetzungen

- LoxBerry **3.0+** (Debian Bullseye oder neuer)
- Das Image `ghcr.io/lenardo1/loxpanel` muss **öffentlich** (public) sein, damit
  der LoxBerry es ohne Login pullen kann. Multi-Arch: `arm64`, `amd64`, `armv7`.

## Steuerung von Hand (SSH auf dem LoxBerry)

```bash
BIN=/opt/loxberry/bin/plugins/loxpanel
$BIN/loxpanel-ctl.sh start      # starten (mit Image-Pull)
$BIN/loxpanel-ctl.sh stop       # stoppen (bis „start“ oder Neustart des LoxBerry)
$BIN/loxpanel-ctl.sh restart    # neu starten / updaten
$BIN/loxpanel-ctl.sh check      # starten, falls nicht läuft und nicht gestoppt (Cron)
$BIN/loxpanel-ctl.sh boot       # wie check, hebt „stop“ auf (Boot)
$BIN/loxpanel-ctl.sh port       # Port am LoxBerry ausgeben
$BIN/loxpanel-ctl.sh port 8098  # Port einstellen (startet LoxPanel damit neu)
$BIN/loxpanel-ctl.sh zustand    # Port, läuft, gestoppt seit, wer den Port belegt
```

## Update

Bei aktivem Auto-Update prüft LoxBerry `release.cfg`. Ein neues **App**-Release
(neues Image) kommt automatisch, weil `:latest` rollend ist und `start`/`restart`
vorher `docker compose pull` ausführt. Ein neues **Plugin**-Release (geänderte
compose/Skripte) erfordert einen Versions-Bump in `plugin.cfg` **und** `release.cfg`.
