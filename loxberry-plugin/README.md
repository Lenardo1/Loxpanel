# LoxPanel – LoxBerry-Plugin (Docker)

Betreibt **LoxPanel** als Docker-Container auf einem LoxBerry – nach dem Vorbild
von *AudioServer4Home*. Das Plugin selbst ist schlank: Es installiert Docker
(falls nötig), startet den LoxPanel-Container aus der GitHub Container Registry
und hält ihn am Laufen. Die gesamte App (Server + Weboberfläche) steckt im Image.

## Was das Plugin macht

- installiert bei Bedarf **Docker** (offizielles Docker-Repo, Pakete via `dpkg/apt`)
- startet `ghcr.io/lenardo1/loxpanel:latest` per `docker compose` (Port **8099**)
- startet das Panel beim **Boot** (`daemon`) und prüft alle **5 Minuten**, ob der
  Container läuft (`cron.05min` → `loxpanel-ctl.sh check`)
- sichert die Nutzerdaten bei Updates (`pre-/postupgrade.sh`)
- entfernt Container + Image beim Deinstallieren

## Bedienung

Nach der Installation (und einem Reboot, falls Docker frisch installiert wurde):

- **Konfiguration:** `http://<LoxBerry-IP>:8099/config` (Panels, Räume, Kacheln)
- **Einstellungen:** `http://<LoxBerry-IP>:8099/settings` (Miniserver-Zugang, Intercom, Displays)
- Das LoxBerry-Plugin-Widget leitet direkt auf `/config` weiter.

Der Miniserver-Zugang wird **nicht** im Plugin gesetzt, sondern über die
Einstellungen-Seite und in `data/plugins/loxpanel/config/loxpanel.cfg`
(Docker-Volume) gespeichert.

## Voraussetzungen

- LoxBerry **3.0+** (Debian Bullseye oder neuer)
- Das Image `ghcr.io/lenardo1/loxpanel` muss **öffentlich** (public) sein, damit
  der LoxBerry es ohne Login pullen kann. Multi-Arch: `arm64`, `amd64`, `armv7`.

## Steuerung von Hand (SSH auf dem LoxBerry)

```bash
BIN=/opt/loxberry/bin/plugins/loxpanel
$BIN/loxpanel-ctl.sh start      # starten (mit Image-Pull)
$BIN/loxpanel-ctl.sh stop       # stoppen (bleibt gestoppt)
$BIN/loxpanel-ctl.sh restart    # neu starten / updaten
$BIN/loxpanel-ctl.sh check      # starten, falls nicht läuft (Cron/Boot)
```

## Update

Bei aktivem Auto-Update prüft LoxBerry `release.cfg`. Ein neues **App**-Release
(neues Image) kommt automatisch, weil `:latest` rollend ist und `start`/`restart`
vorher `docker compose pull` ausführt. Ein neues **Plugin**-Release (geänderte
compose/Skripte) erfordert einen Versions-Bump in `plugin.cfg` **und** `release.cfg`.
