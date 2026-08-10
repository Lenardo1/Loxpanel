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
sudo pip3 install --break-system-packages loxone-api    # zieht aiohttp mit
```

## 3) Miniserver-Zugang
```bash
cp /opt/loxpanel/config/loxpanel.cfg.example /opt/loxpanel/config/loxpanel.cfg
nano /opt/loxpanel/config/loxpanel.cfg      # host/user/pass/verify_tls eintragen
```

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
