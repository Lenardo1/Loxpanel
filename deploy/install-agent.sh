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
"""LoxPanel Panel-Agent — laeuft auf jedem Wandpanel (Linero/PX30).

Meldet das Panel beim LoxPanel-Server (Auto-Discovery) und nimmt Start-/Reload-/
Stop-Befehle entgegen, um den Chromium-Kiosk fernzusteuern. Nur Standardlib.

Config: dieselbe deploy/loxpanel-kiosk.conf wie kiosk.sh
  SERVER=host:port     LoxPanel-Server (Pflicht)
  PANEL=<id>           Panel-Profil / Startseite
  AGENT_PORT=8130      HTTP-Port des Agenten (Default 8130)
  AGENT_NAME=<name>    Anzeigename (Default: Hostname)

Start am Panel aus dem X-Autostart:  python3 loxpanel-agent.py &
(ersetzt den direkten kiosk.sh-Aufruf — der Agent startet den Kiosk selbst).
"""
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
    # Env (LOXPANEL_<KEY>) hat Vorrang vor der Conf-Datei.
    return os.environ.get("LOXPANEL_" + key) or CFG.get(key) or default


SERVER = _cfg("SERVER", "localhost:8099")
PORT = int(_cfg("AGENT_PORT", "8130"))
NAME = _cfg("AGENT_NAME") or socket.gethostname()
# AUTOSTART=0 -> Kiosk NICHT beim Start oeffnen, nur auf /start aus der
# Settings-Seite warten.
AUTOSTART = _cfg("AUTOSTART", "1").lower() not in ("0", "false", "no", "off")
# X = horizontaler Feinversatz der ganzen Visu in px (negativ = nach links),
# gegen Display-Overscan/Fensterposition. Wird als ?x= an die Kiosk-URL gehaengt
# und ueberlebt Reboots (im Gegensatz zum localStorage im fluechtigen /tmp-Profil).
NUDGE_X = _cfg("X", "").strip()
# DPMS_OFF = Sekunden bis das Display komplett abschaltet (Backlight aus), wenn
# nichts angetippt wird. 0 = nie abschalten. Antippen weckt es sofort wieder.
# Unsere schlanke .xsession bringt sonst kein Power-Management mit -> Display
# lief nach dem Autostart-Umbau durch.
DPMS_OFF = _cfg("DPMS_OFF", "180").strip()
# Chromium-Profilverzeichnis. Gedacht als fluechtig, ueberlebt aber Reboots,
# wenn /tmp kein tmpfs ist -> vor jedem Start von Crash-/Lock-Resten befreien,
# damit nach hartem Stromausfall kein "Wiederherstellen?"-Dialog den Kiosk
# blockiert, bis jemand aufs Panel tippt.
PROFILE_DIR = _cfg("PROFILE_DIR", "/tmp/kiosk_profile")
# Backlight-Device fuer die ECHTE Display-Abschaltung. Auf ARM-Panels (PX30)
# schaltet X-DPMS nur das Bildsignal ab, nicht die Hintergrundbeleuchtung ->
# das Panel bleibt hell und wird heiss. Wir ziehen das Backlight per sysfs am
# DPMS-Status nach. BL_DEVICE = Name unter /sys/class/backlight (leer =
# automatisch). Braucht Schreibrechte auf .../brightness (udev-Regel + Gruppe
# video), sonst bleibt nur das reine X-DPMS aktiv.
BL_DEVICE = _cfg("BL_DEVICE", "").strip()
# RELOAD_HOURS = Stunden bis zum automatischen Kiosk-Neustart (gegen Einfrieren
# des Panels/Chromium). 0 = aus. Der Server kann den Wert pro Panel per
# Announce-Antwort (reloadHours) ueberschreiben (Settings-Seite). Nur waehrend
# der Kiosk laeuft; ein bewusst gestoppter Kiosk wird NICHT neu gestartet.
RELOAD_HOURS = _cfg("RELOAD_HOURS", "0").strip()

_proc = None
_cur_panel = _cfg("PANEL", "")
_lock = threading.Lock()


def local_ip():
    """Eigene LAN-IP (die zum Server routet) — wichtig hinter Docker-NAT,
    wo der Server sonst nur das Docker-Gateway als Absender saehe."""
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
_last_reload = time.time()   # Zeitpunkt des letzten (Auto-)Kiosk-Starts


def _reload_default() -> float:
    try:
        return float(RELOAD_HOURS or "0")
    except ValueError:
        return 0.0


def _dpms_default():
    try:
        return int(float(DPMS_OFF or "0"))
    except ValueError:
        return 0


def apply_dpms(secs, force=False):
    """Display-Power-Management setzen: nach `secs` Sekunden Inaktivitaet
    schaltet X das Display ab (Backlight aus); Antippen weckt es (Input-Event).
    secs=0 -> nie abschalten. None -> ignorieren (kein Wert vom Server).
    Wird sowohl beim Kiosk-Start (kiosk.conf-Default) als auch live aus der
    Announce-Antwort des Servers aufgerufen; redundante Aufrufe werden verworfen."""
    global _dpms_cur
    if secs is None:
        return
    if secs == _dpms_cur and not force:
        return
    changed = secs != _dpms_cur   # nur bei echter Aenderung loggen (force laeuft alle 15s)
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
            # standby/suspend/off-Timer: nur "off" nutzen (echtes Abschalten)
            subprocess.run([xset, "dpms", "0", "0", str(secs)], env=env, check=False)
            if changed:
                print("DPMS: Display aus nach %ss Inaktivitaet" % secs)
        else:
            subprocess.run([xset, "-dpms"], env=env, check=False)
            if changed:
                print("DPMS: Abschaltung deaktiviert (0)")
        _dpms_cur = secs
    except Exception as e:
        print("DPMS-Setup fehlgeschlagen:", e)


def _read_dpms_off():
    """Aktuellen DPMS-'Off'-Timeout (Sekunden) aus `xset q` lesen; 0 wenn DPMS
    deaktiviert; None bei Fehler. Nur Query -> setzt den X-Inaktivitaets-Zaehler
    NICHT zurueck (im Gegensatz zu 'xset dpms ...' / 'xset s off'), darf also
    beliebig oft im announce_loop aufgerufen werden."""
    xset = shutil.which("xset")
    if not xset:
        return None
    env = dict(os.environ)
    env.setdefault("DISPLAY", ":0")
    try:
        out = subprocess.run([xset, "q"], env=env, capture_output=True,
                             text=True, timeout=5).stdout
    except Exception:
        return None
    off = None
    for line in out.splitlines():
        s = line.strip()
        if s.startswith("Standby:") and "Off:" in s:  # "Standby: 0  Suspend: 0  Off: 60"
            try:
                off = int(s.split("Off:")[1].split()[0])
            except (ValueError, IndexError):
                off = None
    if off is None:
        return None
    return off if "DPMS is Enabled" in out else 0


def _find_backlight():
    """Pfad zur brightness-Datei des Panel-Backlights (oder None). Bevorzugt das
    Device namens 'backlight', sonst das erste unter /sys/class/backlight."""
    base = "/sys/class/backlight"
    if BL_DEVICE:
        cand = [BL_DEVICE]
    else:
        try:
            names = sorted(os.listdir(base))
        except OSError:
            return None
        cand = (["backlight"] if "backlight" in names else []) + \
               [n for n in names if n != "backlight"]
    for name in cand:
        p = os.path.join(base, name, "brightness")
        if os.path.exists(p):
            return p
    return None


_BL_PATH = _find_backlight()
_bl_on_value = None     # zuletzt bekannte "helle" Helligkeit
_bl_off = False         # True = wir haben das Backlight abgeschaltet


def _bl_read():
    try:
        with open(_BL_PATH, encoding="ascii") as fh:
            return int(fh.read().strip())
    except Exception:
        return None


def _bl_write(val):
    try:
        with open(_BL_PATH, "w", encoding="ascii") as fh:
            fh.write(str(int(val)))
        return True
    except Exception as e:
        print("Backlight schreiben fehlgeschlagen:", e)
        return False


def _monitor_on():
    """DPMS-Monitorstatus aus `xset q`: True=an, False=aus/standby/suspend,
    None=unbekannt (xset fehlt oder Fehler)."""
    xset = shutil.which("xset")
    if not xset:
        return None
    env = dict(os.environ)
    env.setdefault("DISPLAY", ":0")
    try:
        out = subprocess.run([xset, "q"], env=env, capture_output=True,
                             text=True, timeout=5).stdout
    except Exception:
        return None
    for line in out.splitlines():
        if "Monitor is" in line:
            return "On" in line
    return None


def backlight_loop():
    """Koppelt die Hintergrundbeleuchtung an den X-DPMS-Status: schaltet X das
    Bild nach Inaktivitaet ab (Monitor Off), ziehen wir das Backlight per sysfs
    auf 0 nach (Panel wirklich aus, kein Aufheizen); beim Aufwachen zurueck auf
    den letzten hellen Wert. Eine externe Helligkeitsaenderung (waehrend Monitor
    On) wird als neuer Normalwert uebernommen."""
    global _bl_on_value, _bl_off
    _bl_on_value = _bl_read() or 255
    while True:
        try:
            on = _monitor_on()
            if on is True:
                if _bl_off:
                    _bl_write(_bl_on_value)
                    _bl_off = False
                else:
                    cur = _bl_read()
                    if cur and cur > 0:
                        _bl_on_value = cur
            elif on is False:
                if not _bl_off:
                    cur = _bl_read()
                    if cur and cur > 0:
                        _bl_on_value = cur
                    _bl_write(0)
                    _bl_off = True
        except Exception:
            pass
        time.sleep(1)


def _clear_chrome_crash_state():
    """Nach hartem Stromausfall bleibt im Profil `exited_cleanly:false` bzw. ein
    verwaistes Singleton-Lock zurueck -> Chromium zeigt beim Start einen
    "Wiederherstellen?"-/"Profil in Benutzung"-Dialog, der den Kiosk blockiert,
    bis jemand tippt. Vor jedem Start bereinigen (wie zuvor kiosk.sh per sed)."""
    prefs = os.path.join(PROFILE_DIR, "Default", "Preferences")
    try:
        with open(prefs, encoding="utf-8") as fh:
            data = fh.read()
        fixed = (data.replace('"exited_cleanly":false', '"exited_cleanly":true')
                     .replace('"exit_type":"Crashed"', '"exit_type":"Normal"'))
        if fixed != data:
            with open(prefs, "w", encoding="utf-8") as fh:
                fh.write(fixed)
    except FileNotFoundError:
        pass
    except Exception as e:
        print("Crash-Flags bereinigen fehlgeschlagen:", e)
    for n in ("SingletonLock", "SingletonSocket", "SingletonCookie"):
        try:
            os.unlink(os.path.join(PROFILE_DIR, n))
        except OSError:
            pass


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
    global _proc, _cur_panel, _last_reload
    if panel is not None:
        _cur_panel = panel
    stop_kiosk()
    chrome = shutil.which("chromium") or shutil.which("chromium-browser")
    if not chrome:
        print("Chromium nicht gefunden")
        return False
    env = dict(os.environ)
    env.setdefault("DISPLAY", ":0")
    os.makedirs(os.path.join(PROFILE_DIR, "Default"), exist_ok=True)
    _clear_chrome_crash_state()
    cmd = [chrome, "--kiosk", "--user-data-dir=" + PROFILE_DIR, "--noerrdialogs",
           "--disable-infobars", "--disable-session-crashed-bubble", "--disable-pinch",
           "--overscroll-history-navigation=0", "--check-for-update-interval=31536000",
           "--force-device-scale-factor=1", "--autoplay-policy=no-user-gesture-required",
           # kein http->https-Upgrade (unser Server ist http) + keine Uebersetzen-Leiste:
           "--disable-features=HttpsUpgrades,HttpsFirstBalancedMode,HttpsFirstModeV2,Translate,TranslateUI",
           "--no-first-run",
           kiosk_url(_cur_panel)]
    with _lock:
        _proc = subprocess.Popen(cmd, env=env)
    _last_reload = time.time()   # Auto-Reload-Timer bei jedem Start zuruecksetzen
    # force: Chromium-(Neu)Start setzt DPMS auf den X-Default (600) zurueck —
    # deshalb hier immer neu erzwingen (kiosk.conf-Default; Server ueberschreibt).
    apply_dpms(_dpms_default(), force=True)
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
            # Server kann Geraeteeinstellungen zurueckgeben (z.B. Display-Abschaltung)
            try:
                r = json.loads(resp or b"{}")
                if running():
                    # DPMS nur korrigieren, wenn der aktuelle X-Wert abweicht
                    # (z.B. weil Chromium den Timer beim Start auf den X-Default
                    # zurueckgesetzt hat). NICHT bei jedem Tick neu setzen: jeder
                    # 'xset dpms'-Aufruf setzt den Inaktivitaets-Zaehler zurueck,
                    # dann erreicht er nie den Off-Wert und das Display bleibt an.
                    # Kein Server-Wert -> kiosk.conf-Default.
                    target = r.get("dpmsOff")
                    try:
                        want = _dpms_default() if target is None else int(float(target))
                    except (TypeError, ValueError):
                        want = _dpms_default()
                    if _read_dpms_off() != want:
                        apply_dpms(want, force=True)
                # Periodischer Kiosk-Neustart gegen Einfrieren. reloadHours vom
                # Server (Settings) oder kiosk.conf-Default. 0 = aus. Nur wenn der
                # Kiosk laeuft (bewusst gestoppten NICHT wieder starten).
                rh = r.get("reloadHours")
                try:
                    hours = _reload_default() if rh is None else float(rh)
                except (TypeError, ValueError):
                    hours = _reload_default()
                if hours > 0 and running() and (time.time() - _last_reload) >= hours * 3600:
                    print("Auto-Reload nach %gh (gegen Einfrieren)" % hours)
                    start_kiosk()
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
    if _BL_PATH:
        threading.Thread(target=backlight_loop, daemon=True).start()
        print("Backlight-Steuerung aktiv:", _BL_PATH)
    else:
        print("Kein Backlight-Device gefunden — nur X-DPMS (Bildsignal) aktiv")
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
