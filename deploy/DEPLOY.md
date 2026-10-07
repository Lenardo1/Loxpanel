# LoxPanel auf dem PX30-Wandpanel

Ziel: Die Web-Visu laeuft als Dienst und startet beim Booten im Chromium-Kiosk.
Zwei Varianten fuer den Server:

- **A (einfach, self-contained):** Server + Kiosk laufen beide auf dem PX30.
  Kiosk-URL = `http://localhost:8099`.
- **B (sauber, skalierbar):** Server laeuft auf LoxBerry (24/7), PX30 zeigt nur.
  Kiosk-URL = `http://<loxberry-ip>:8099`. (Spaeter als LoxBerry-Plugin.)

Unten Variante A. Alle Befehle auf dem PX30 (per SSH).

## 0) Discovery (einmal ausfuehren, Ausgabe zuruecksenden)
```bash
cat /etc/os-release | head -3
python3 --version
echo "session: $XDG_SESSION_TYPE"          # x11 oder wayland?
command -v chromium chromium-browser        # welcher Browser da?
ls ~/.xinitrc /etc/xdg/openbox/autostart 2>/dev/null   # aktueller Autostart?
pgrep -a kerberos || pgrep -a -i loxone     # womit startet die alte Loxone-App?
```

## 1) Dateien aufs Panel
```bash
sudo mkdir -p /opt/loxpanel
# vom Entwicklungsrechner (Beispiel scp), oder per USB/git:
#   scp -r loxpanel/* root@<px30-ip>:/opt/loxpanel/
```

## 2) Python-Abhaengigkeiten
```bash
sudo apt update
sudo apt install -y python3-pip chromium unclutter fonts-inter fonts-roboto
# nur 32-bit-ARM-System (dpkg --print-architecture: armhf, auch wenn uname -m
# bei 64-bit-Kernel aarch64 zeigt): fuer cffi gibt es dort kein fertiges Paket,
# pip baut es (wie im Dockerfile) und braucht dazu:
sudo apt install -y gcc libc6-dev libffi-dev python3-dev
sudo pip3 install --break-system-packages -r /opt/loxpanel/requirements.txt
```
Die Paketliste steht nur in `requirements.txt`: Kalender und die Anmeldung am
Audioserver brauchen mehr als `loxone-api`. Fehlt eins der Pakete dafuer, startet
der Server trotzdem und nennt es beim Start im Log; ohne `loxone-api` (und das
damit installierte `aiohttp`) startet er nicht.

`--break-system-packages` kennt pip erst ab Version 23 (Debian 12); auf
aelteren Systemen die Option weglassen. Auf 32-bit-ARM bekommt pip
`cryptography` nur fertig, wenn glibc (`ldd --version`) und pip neu genug sind;
die Grenze kann sich mit jeder neuen cryptography-Version verschieben. Baut pip
es selbst (Meldung `Building wheel for cryptography`), braucht es zusaetzlich
`libssl-dev`, `pkg-config` und Rust in der Mindestversion aus der
[Installationsanleitung von cryptography](https://cryptography.io/en/latest/installation/);
das `cargo` aus apt ist dafuer auf aelteren Systemen zu alt, dann Rust ueber
rustup installieren (dessen `cargo` muss auch fuer `sudo pip3` im `PATH` liegen).

## 3) Miniserver-Zugang
Nach Schritt 4 im Browser `http://<px30-ip>:8099/config` oeffnen und den Zugang
unter **Settings → Miniserver** eintragen. Der Server legt `config/loxpanel.cfg`
selbst an und verbindet sich; bis dahin wartet er und zeigt jedem Panel, wo der
Konfigurator zu oeffnen ist. Alternativ in der `.service` unter `[Service]` je
eine Zeile `Environment=LOXPANEL_MS_HOST=<ip>` (ebenso `_USER`, `_PASS`, `_PORT`,
`_VERIFY_TLS`); ein unter Settings gespeicherter Zugang hat Vorrang vor diesen
Variablen.

## 4) Server als Dienst
```bash
sudo cp /opt/loxpanel/deploy/loxpanel-webvisu.service /etc/systemd/system/
# ggf. User=/Pfade in der .service anpassen
sudo systemctl daemon-reload
sudo systemctl enable --now loxpanel-webvisu
systemctl status loxpanel-webvisu           # laeuft?
curl -s localhost:8099 | head -c 60        # liefert HTML?
```

## 5) Kiosk-Autostart

Erst Server-Adresse + Panel-ID in die panel-lokale Konfig (keine IP im Startbefehl):
```bash
cp /opt/loxpanel/deploy/loxpanel-kiosk.conf.example /opt/loxpanel/deploy/loxpanel-kiosk.conf
nano /opt/loxpanel/deploy/loxpanel-kiosk.conf   # SERVER=<ip:port>, PANEL=<profil-id>
```
`kiosk.sh` liest daraus die URL (`http://<SERVER>/?panel=<PANEL>`). Server-IP
aendern = nur diese Datei anpassen, Autostart bleibt unveraendert. Test von Hand:
```bash
DISPLAY=:0 bash /opt/loxpanel/deploy/kiosk.sh
```

Dann `deploy/kiosk.sh` in den vorhandenen X11-Autostart einhaengen und die alte
Loxone-App dort entfernen. Je nach Setup:
- **openbox:** in `~/.config/openbox/autostart` bzw. `/etc/xdg/openbox/autostart`
  die Loxone-Zeile durch `bash /opt/loxpanel/deploy/kiosk.sh &` ersetzen.
- **.xinitrc:** die `kerberos`/Loxone-Zeile durch `exec bash /opt/loxpanel/deploy/kiosk.sh` ersetzen.

Dann Panel neu starten:
```bash
sudo reboot
```

## 6) Panel-Agent (empfohlen: Fernstart aus der Settings-Seite)

Statt `kiosk.sh` direkt zu starten, den **Agenten** starten — er startet den
Kiosk selbst UND meldet das Panel beim Server, sodass du es unter
`http://<SERVER>/settings` findest und dort **Start / Reload / Ansicht wechseln**
kannst. Nutzt dieselbe `loxpanel-kiosk.conf` (zusaetzlich optional `AGENT_PORT`,
`AGENT_NAME`); nur Python-Standardlib, keine Extra-Pakete.

Im X11-Autostart die `kiosk.sh`-Zeile ersetzen durch:
```bash
python3 /opt/loxpanel/agent/loxpanel-agent.py &
```
Oder als systemd-Dienst (User/XAUTHORITY an die Autologin-Session anpassen):
```bash
sudo cp /opt/loxpanel/agent/loxpanel-agent.service /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now loxpanel-agent
```
Der Agent hoert auf Port **8130** (Server steuert darueber). Test von Hand:
```bash
DISPLAY=:0 python3 /opt/loxpanel/agent/loxpanel-agent.py
```

> Docker-Hinweis: Der Agent meldet sich **per HTTP** beim Server (kein UDP-
> Broadcast) — funktioniert daher auch mit dem Server im Docker-Bridge-Netz.

## Fehlersuche
- Server-Log: `journalctl -u loxpanel-webvisu -f`
- Weisse/leere Seite: URL/Server pruefen (`curl localhost:8099`).
- Kein Bild gedreht/skaliert: `--force-device-scale-factor` in kiosk.sh anpassen.
