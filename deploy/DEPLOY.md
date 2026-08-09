# LoxHASP auf dem PX30-Wandpanel

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
sudo mkdir -p /opt/loxhasp
# vom Entwicklungsrechner (Beispiel scp), oder per USB/git:
#   scp -r loxhasp/* root@<px30-ip>:/opt/loxhasp/
```

## 2) Python-Abhaengigkeiten
```bash
sudo apt update
sudo apt install -y python3-pip chromium unclutter fonts-inter fonts-roboto
sudo pip3 install --break-system-packages loxone-api    # zieht aiohttp mit
```

## 3) Miniserver-Zugang
```bash
cp /opt/loxhasp/config/loxhasp.cfg.example /opt/loxhasp/config/loxhasp.cfg
nano /opt/loxhasp/config/loxhasp.cfg      # host/user/pass/verify_tls eintragen
```

## 4) Server als Dienst
```bash
sudo cp /opt/loxhasp/deploy/loxhasp-webvisu.service /etc/systemd/system/
# ggf. User=/Pfade in der .service anpassen
sudo systemctl daemon-reload
sudo systemctl enable --now loxhasp-webvisu
systemctl status loxhasp-webvisu           # laeuft?
curl -s localhost:8099 | head -c 60        # liefert HTML?
```

## 5) Kiosk-Autostart
`deploy/kiosk.sh` in den vorhandenen X11-Autostart einhaengen und die alte
Loxone-App dort entfernen. Je nach Setup:
- **openbox:** in `~/.config/openbox/autostart` bzw. `/etc/xdg/openbox/autostart`
  die Loxone-Zeile durch `bash /opt/loxhasp/deploy/kiosk.sh &` ersetzen.
- **.xinitrc:** die `kerberos`/Loxone-Zeile durch `exec bash /opt/loxhasp/deploy/kiosk.sh` ersetzen.

Dann Panel neu starten:
```bash
sudo reboot
```

## Fehlersuche
- Server-Log: `journalctl -u loxhasp-webvisu -f`
- Weisse/leere Seite: URL/Server pruefen (`curl localhost:8099`).
- Kein Bild gedreht/skaliert: `--force-device-scale-factor` in kiosk.sh anpassen.
