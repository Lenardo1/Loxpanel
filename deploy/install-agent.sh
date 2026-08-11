#!/bin/bash
# LoxPanel Panel-Agent — Installer fuer das Anzeige-Geraet (Linero/PX30/Debian).
# Legt Agent + Config an und haengt ihn in den X-Autostart ein.
#
# Benutzung (auf dem Panel per SSH, als dessen Login-Benutzer, NICHT root):
#   1) SERVER unten anpassen (IP:Port deines LoxPanel-Servers)
#   2) bash install-agent.sh
#
# Der eingebettete Agent ist ein Spiegel von agent/loxpanel-agent.py.
set -e

# ===== ANPASSEN (oder per Env uebergeben: SERVER=... bash install-agent.sh) =====
SERVER="${SERVER:-192.168.1.10:8099}"    # IP:Port deines LoxPanel-Servers (Docker-Host/Pi)
AGENT_NAME="${AGENT_NAME:-$(hostname)}"  # Anzeigename in /settings
PANEL="${PANEL:-}"                       # Panel-Profil-ID (leer = Standardansicht)
AUTOSTART="${AUTOSTART:-1}"              # 1 = Kiosk beim Booten; 0 = nur Agent, Start aus /settings
TIMEZONE="${TIMEZONE:-Europe/Vienna}"   # Systemzeitzone (Screensaver-Uhr); leer = unveraendert lassen
NUDGE_X="${NUDGE_X:-}"                   # horiz. Feinversatz der Visu in px (z.B. -8 = 8px nach links); leer = 0
DPMS_OFF="${DPMS_OFF:-180}"              # Sek. bis Display abschaltet (Backlight aus); 0 = nie
# ================================================================================

AGENT_DIR="/opt/loxpanel/agent"
AGENT="$AGENT_DIR/loxpanel-agent.py"
CONF="/etc/loxpanel/kiosk.conf"

if [ "$(id -u)" = "0" ] && [ -n "$SUDO_USER" ]; then
  echo "Bitte NICHT mit sudo starten — als Panel-Login-Benutzer ausfuehren (das Skript ruft sudo selbst)."
  exit 1
fi

echo "==> 1/5 Verzeichnisse"
sudo mkdir -p "$AGENT_DIR" /etc/loxpanel

echo "==> 2/5 Agent schreiben ($AGENT)"
sudo tee "$AGENT" >/dev/null <<'PYEOF'
#!/usr/bin/env python3
"""LoxPanel Panel-Agent — meldet das Panel und steuert den Chromium-Kiosk."""
import json
import os
import shutil
import socket
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib import request as urlreq

_HERE = os.path.dirname(os.path.abspath(__file__))
CONF_PATHS = [os.environ.get("LOXPANEL_KIOSK_CONF", ""),
              os.path.join(_HERE, "..", "deploy", "loxpanel-kiosk.conf"),
              "/etc/loxpanel/kiosk.conf"]


def load_conf():
    cfg = {}
    for p in CONF_PATHS:
        if p and os.path.isfile(p):
            with open(p, encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    k, v = line.split("=", 1)
                    cfg[k.strip()] = v.strip().strip('"').strip("'")
            break
    return cfg


CFG = load_conf()


def _cfg(key, default=""):
    return os.environ.get("LOXPANEL_" + key) or CFG.get(key) or default


SERVER = _cfg("SERVER", "localhost:8099")
PORT = int(_cfg("AGENT_PORT", "8130"))
NAME = _cfg("AGENT_NAME") or socket.gethostname()
AUTOSTART = _cfg("AUTOSTART", "1").lower() not in ("0", "false", "no", "off")
# X = horizontaler Feinversatz der ganzen Visu in px (negativ = nach links).
NUDGE_X = _cfg("X", "").strip()
# DPMS_OFF = Sekunden bis das Display abschaltet (Backlight aus); 0 = nie.
DPMS_OFF = _cfg("DPMS_OFF", "180").strip()

_proc = None
_cur_panel = _cfg("PANEL", "")
_lock = threading.Lock()


def local_ip():
    host = SERVER.split("//")[-1].split(":")[0]
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect((host, 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return ""


MY_IP = local_ip()


def kiosk_url(panel):
    q = []
    if panel:
        q.append("panel=%s" % panel)
    if NUDGE_X:
        q.append("x=%s" % NUDGE_X)
    return "http://%s/" % SERVER + ("?" + "&".join(q) if q else "")


_dpms_cur = None


def _dpms_default():
    try:
        return int(float(DPMS_OFF or "0"))
    except ValueError:
        return 0


def apply_dpms(secs):
    """Display-Abschaltung setzen: nach `secs` Sek. Inaktivitaet schaltet X das
    Display ab; Antippen weckt es. 0=nie, None=ignorieren. Wird beim Kiosk-Start
    (kiosk.conf-Default) und live aus der Announce-Antwort des Servers gesetzt."""
    global _dpms_cur
    if secs is None or secs == _dpms_cur:
        return
    xset = shutil.which("xset")
    if not xset:
        print("xset fehlt (Paket x11-xserver-utils) — Display-Abschaltung inaktiv")
        return
    env = dict(os.environ)
    env.setdefault("DISPLAY", ":0")
    try:
        subprocess.run([xset, "s", "off"], env=env, check=False)
        if secs > 0:
            subprocess.run([xset, "+dpms"], env=env, check=False)
            subprocess.run([xset, "dpms", "0", "0", str(secs)], env=env, check=False)
            print("DPMS: Display aus nach %ss Inaktivitaet" % secs)
        else:
            subprocess.run([xset, "-dpms"], env=env, check=False)
            print("DPMS: Abschaltung deaktiviert (0)")
        _dpms_cur = secs
    except Exception as e:
        print("DPMS-Setup fehlgeschlagen:", e)


def stop_kiosk():
    global _proc
    with _lock:
        if _proc and _proc.poll() is None:
            _proc.terminate()
            try:
                _proc.wait(timeout=5)
            except Exception:
                _proc.kill()
        _proc = None


def start_kiosk(panel=None):
    global _proc, _cur_panel
    if panel is not None:
        _cur_panel = panel
    stop_kiosk()
    chrome = shutil.which("chromium") or shutil.which("chromium-browser")
    if not chrome:
        print("Chromium nicht gefunden")
        return False
    env = dict(os.environ)
    env.setdefault("DISPLAY", ":0")
    cmd = [chrome, "--kiosk", "--user-data-dir=/tmp/kiosk_profile", "--noerrdialogs",
           "--disable-infobars", "--disable-session-crashed-bubble", "--disable-pinch",
           "--overscroll-history-navigation=0", "--check-for-update-interval=31536000",
           "--force-device-scale-factor=1", "--autoplay-policy=no-user-gesture-required",
           "--disable-features=HttpsUpgrades,HttpsFirstBalancedMode,HttpsFirstModeV2,Translate,TranslateUI",
           "--no-first-run",
           kiosk_url(_cur_panel)]
    with _lock:
        _proc = subprocess.Popen(cmd, env=env)
    apply_dpms(_dpms_default())
    print("Kiosk gestartet:", kiosk_url(_cur_panel))
    return True


def running():
    return _proc is not None and _proc.poll() is None


def announce_loop():
    url = "http://%s/api/agent/announce" % SERVER
    while True:
        try:
            data = json.dumps({"name": NAME, "panel": _cur_panel, "ip": MY_IP,
                               "port": PORT, "kiosk": running()}).encode()
            req = urlreq.Request(url, data=data, headers={"Content-Type": "application/json"})
            resp = urlreq.urlopen(req, timeout=6).read()
            try:
                r = json.loads(resp or b"{}")
                if running():
                    apply_dpms(r.get("dpmsOff"))
            except Exception:
                pass
        except Exception:
            pass
        time.sleep(15)


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, obj):
        b = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def log_message(self, *a):
        pass

    def do_GET(self):
        if self.path.startswith("/status"):
            self._send(200, {"running": running(), "panel": _cur_panel,
                             "url": kiosk_url(_cur_panel), "name": NAME})
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        try:
            body = json.loads(self.rfile.read(n) or b"{}")
        except Exception:
            body = {}
        p = self.path.rstrip("/") or "/"
        if p == "/start":
            ok = start_kiosk(body.get("panel") if body.get("panel") is not None else _cur_panel)
            self._send(200 if ok else 500, {"ok": ok})
        elif p == "/reload":
            ok = start_kiosk()
            self._send(200 if ok else 500, {"ok": ok})
        elif p == "/stop":
            stop_kiosk()
            self._send(200, {"ok": True})
        else:
            self._send(404, {"error": "not found"})


def main():
    if AUTOSTART and (os.environ.get("DISPLAY") or os.path.exists("/tmp/.X11-unix/X0")):
        start_kiosk(_cur_panel)
    threading.Thread(target=announce_loop, daemon=True).start()
    srv = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print("LoxPanel-Agent auf :%d, Server=%s, Panel=%s, Autostart=%s"
          % (PORT, SERVER, _cur_panel or "(default)", "an" if AUTOSTART else "aus"))
    srv.serve_forever()


if __name__ == "__main__":
    main()
PYEOF
sudo chmod 644 "$AGENT"

echo "==> 3/5 Config ($CONF)"
sudo tee "$CONF" >/dev/null <<EOF
SERVER=$SERVER
PANEL=$PANEL
AGENT_NAME=$AGENT_NAME
AGENT_PORT=8130
AUTOSTART=$AUTOSTART
X=$NUDGE_X
DPMS_OFF=$DPMS_OFF
EOF

if [ -n "$TIMEZONE" ]; then
  echo "==> Zeitzone -> $TIMEZONE (fuer die Screensaver-Uhr)"
  sudo timedatectl set-timezone "$TIMEZONE" 2>/dev/null \
    || echo "   WARN: Zeitzone nicht gesetzt (timedatectl fehlt?) — manuell: sudo timedatectl set-timezone $TIMEZONE"
fi

echo "==> 4/5 Voraussetzungen"
command -v python3 >/dev/null || echo "   WARN: python3 fehlt  -> sudo apt install -y python3"
command -v chromium >/dev/null || command -v chromium-browser >/dev/null \
  || echo "   WARN: chromium fehlt -> sudo apt install -y chromium"
# xset (fuer Display-Abschaltung/DPMS) — bei Bedarf nachinstallieren
if ! command -v xset >/dev/null; then
  echo "   xset fehlt -> installiere x11-xserver-utils"
  sudo apt-get install -y x11-xserver-utils 2>/dev/null \
    || echo "   WARN: x11-xserver-utils nicht installiert -> Display-Abschaltung inaktiv"
fi

echo "==> Chromium-Policies (kein Sign-in / Sync / Promo)"
for pol in /etc/chromium/policies/managed /etc/chromium-browser/policies/managed; do
  sudo mkdir -p "$pol"
  sudo tee "$pol/loxpanel.json" >/dev/null <<'JSONEOF'
{
  "BrowserSignin": 0,
  "SyncDisabled": true,
  "MetricsReportingEnabled": false,
  "PromotionalTabsEnabled": false,
  "DefaultBrowserSettingEnabled": false
}
JSONEOF
done

echo "==> 5/5 Autostart via ~/.xsession"
# Robust fuer LightDM/GDM (Default-Xsession fuehrt ~/.xsession aus) und startx.
# Der Kiosk laeuft ohne extra Fenstermanager (wie eine dedizierte Kiosk-Session).
XS="$HOME/.xsession"
if [ -f "$XS" ] && ! grep -qF "loxpanel-agent" "$XS"; then
  cp "$XS" "$XS.loxpanel.bak"
  echo "   vorhandene ~/.xsession gesichert: $XS.loxpanel.bak"
fi
cat > "$XS" <<EOF
#!/bin/sh
# LoxPanel Panel-Agent -> startet den Chromium-Kiosk und meldet das Panel.
# Screensaver-Blank aus; DPMS (Display-Abschaltung) richtet der Agent selbst
# gemaess DPMS_OFF ein — daher hier NICHT mehr -dpms setzen.
xset s off 2>/dev/null || true
exec python3 $AGENT
EOF
chmod +x "$XS"
echo "   $XS angelegt (LightDM fuehrt es nach dem Auto-Login aus)"
# alte openbox-Zeile aus frueheren Versuchen aufraeumen (schadet sonst nicht)
OB="$HOME/.config/openbox/autostart"
[ -f "$OB" ] && sed -i '/loxpanel-agent/d' "$OB" 2>/dev/null || true

echo
echo "=== Fertig ==="
echo "Test von Hand:   DISPLAY=:0 python3 $AGENT"
echo "Dann neu booten: sudo reboot"
echo "Panel erscheint unter  http://$SERVER/settings  -> Displays"
