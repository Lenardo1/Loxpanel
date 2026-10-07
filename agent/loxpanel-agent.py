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
import math
import os
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib import request as urlreq
from urllib.parse import quote

_HERE = os.path.dirname(os.path.abspath(__file__))
CONF_PATHS = [os.environ.get("LOXPANEL_KIOSK_CONF", ""),
              os.path.join(_HERE, "..", "deploy", "loxpanel-kiosk.conf"),
              "/etc/loxpanel/kiosk.conf"]


CONF_FILE = ""


def load_conf():
    global CONF_FILE
    cfg = {}
    for p in CONF_PATHS:
        if p and os.path.isfile(p):
            CONF_FILE = p
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
# BL_ON = feste Helligkeit im Ein-Zustand (0..max_brightness). Leer = volles
# max_brightness des Geraets. Wird NICHT aus dem Ist-Wert gelernt, damit ein zu
# dunkler Boot-Default das Panel nicht dauerhaft dunkel laesst.
BL_ON = _cfg("BL_ON", "").strip()
# PAUSE_ON_BLANK = Chromium-Kiosk pausieren (SIGSTOP), solange das Display aus
# ist (Monitor Off), und beim Aufwachen fortsetzen (SIGCONT). Spart zwar
# CPU/Waerme, hat aber einen gravierenden Nebeneffekt: waehrend des Einfrierens
# stirbt die WebSocket-Verbindung zum Server, sodass das Panel nach dem
# Aufwachen erst ein eingefrorenes altes Bild zeigt und ~30 s fuer den
# WS-Reconnect braucht, bevor es wieder auf Aenderungen reagiert. Daher
# standardmaessig AUS. Nur bei Bedarf per PAUSE_ON_BLANK=1 in der kiosk.conf
# wieder aktivieren. Das echte Display-Aus (Backlight/DPMS) laeuft unabhaengig
# davon weiter.
PAUSE_ON_BLANK = _cfg("PAUSE_ON_BLANK", "0").lower() not in ("0", "false", "no", "off")
# RELOAD_HOURS = Stunden bis zum automatischen Kiosk-Neustart (gegen Einfrieren
# des Panels/Chromium). 0 = aus. Der Server kann den Wert pro Panel per
# Announce-Antwort (reloadHours) ueberschreiben (Settings-Seite). Nur waehrend
# der Kiosk laeuft; ein bewusst gestoppter Kiosk wird NICHT neu gestartet.
RELOAD_HOURS = _cfg("RELOAD_HOURS", "0").strip()


def _sekunden(key, standard):
    """Sekundenwert aus Env/Conf; leer, ungueltig, negativ oder nicht endlich
    (inf, nan: time.sleep im Waechter braeche ab) -> Standard."""
    try:
        v = float(_cfg(key, str(standard)))
    except ValueError:
        return standard
    return v if math.isfinite(v) and v >= 0 else standard


# KIOSK_RESTART_SECS = Pause, bevor der Agent ein unerwartet beendetes Chromium
# neu startet (Absturz, OOM-Kill, Alt+F4 - jedes Ende ausser /stop). 0 = aus.
# Standard 5 s wie RestartSec=5 der Dienstdateien (agent/loxpanel-agent.service):
# das Panel bleibt kaum dunkel, ein Absturz flutet die CPU nicht mit Neustarts.
KIOSK_RESTART_SECS = _sekunden("KIOSK_RESTART_SECS", 5)
# KIOSK_RESTART_MAX_SECS = Obergrenze, bis zu der sich die Pause verdoppelt,
# wenn Chromium immer wieder abstuerzt (kaputtes Profil, Speicher voll). Standard
# 300 s wie Kubernetes bei CrashLoopBackOff: Das Panel erholt sich spaetestens
# 5 min, nachdem die Ursache weg ist. Muss ueber DPMS_OFF liegen: jeder
# Kiosk-Start setzt per xset den Leerlaufzaehler zurueck, eine Schleife mit
# kuerzeren Abstaenden hielte das Display dauerhaft an.
KIOSK_RESTART_MAX_SECS = max(KIOSK_RESTART_SECS, _sekunden("KIOSK_RESTART_MAX_SECS", 300))


def _state_standard():
    """Ablage nach XDG Base Directory: $XDG_STATE_HOME, wenn gesetzt und absolut,
    sonst ~/.local/state. Gehoert dem Benutzer, unter dem der Agent laeuft
    (Login-Benutzer aus ~/.xsession); /etc/loxpanel legt der Installer als
    root an, dort scheiterte das Speichern."""
    basis = os.environ.get("XDG_STATE_HOME", "")
    if not os.path.isabs(basis):
        basis = os.path.join(os.path.expanduser("~"), ".local", "state")
    return os.path.join(basis, "loxpanel", "agent-state.json")


# STATE_FILE = persistente Merkdatei fuer die zuletzt (per Settings-Seite/Agent)
# gewaehlte Panel-ID. Liegt bewusst NICHT im fluechtigen PROFILE_DIR (/tmp),
# damit die Wahl einen Reboot ueberlebt. Ueber die conf per STATE_FILE=<pfad>
# ueberschreibbar. Bis hierher lag sie neben der kiosk.conf (_STATE_ALT); eine
# Datei von dort wird beim Start einmal uebernommen.
STATE_FILE = _cfg("STATE_FILE", "") or _state_standard()
_STATE_ALT = os.path.join(os.path.dirname(CONF_FILE) if CONF_FILE else _HERE,
                          "loxpanel-agent-state.json")


def _read_state(pfad):
    """State-Datei lesen -> dict mit "panel" (str) oder None (fehlt/ungueltig)."""
    try:
        with open(pfad, encoding="utf-8") as fh:
            d = json.load(fh)
    except Exception:
        return None
    return d if isinstance(d, dict) and isinstance(d.get("panel"), str) else None


def _load_panel_state():
    """Gemerkte Panel-ID: "" ist die Standardansicht, None heisst nichts gemerkt.
    Die Datei haelt auch PANEL der kiosk.conf beim Merken ("conf"): Steht dort
    inzwischen etwas anderes (Installer neu gelaufen, von Hand geaendert), gilt
    die kiosk.conf und die alte Wahl wird verworfen."""
    d = _read_state(STATE_FILE)
    if d is None and not _cfg("STATE_FILE") and _STATE_ALT != STATE_FILE:
        d = _read_state(_STATE_ALT)
        if d is not None:
            print("Panel-Wahl uebernommen: %s -> %s" % (_STATE_ALT, STATE_FILE))
            if _save_panel_state(d["panel"]):
                # Nur einmal: bliebe die alte Datei liegen, kaeme ihre Wahl
                # zurueck, sobald jemand die neue loescht (Weg zurueck auf PANEL).
                try:
                    os.remove(_STATE_ALT)
                except OSError as e:
                    print("Alte Panel-Wahl nicht geloescht, bitte von Hand entfernen: %s" % e)
    if d is None:
        return None
    conf = CFG.get("PANEL", "")
    if d.get("conf", conf) != conf:
        print("PANEL in der kiosk.conf geaendert (%r -> %r): gilt statt der gemerkten Wahl %r"
              % (d["conf"], conf, d["panel"]))
        _save_panel_state(conf)
        return None
    return d["panel"]


def _save_panel_state(panel):
    """Gewaehlte Panel-ID persistieren, damit sie einen Reboot ueberlebt
    (atomar: tmp-Datei + rename). Schlaegt das fehl, laut melden. True = gespeichert."""
    try:
        if os.path.dirname(STATE_FILE):   # ohne Ordner: im Arbeitsordner
            os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
        tmp = STATE_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump({"panel": panel, "conf": CFG.get("PANEL", "")}, fh)
        os.replace(tmp, STATE_FILE)
        return True
    except Exception as e:
        print("FEHLER: Panel-Wahl NICHT gespeichert, gilt nur bis zum Neustart des Agenten: %s"
              " (Agent laeuft als uid %d; anderen Ort per STATE_FILE=<pfad> in %s setzen)"
              % (e, os.getuid(), CONF_FILE or "der kiosk.conf"))
        return False


_proc = None
# Panel-Auswahl mit Prioritaet: Env-Override > gemerkte Laufzeit-Wahl (State-
# Datei, auch "" = Standardansicht) > kiosk.conf > leer (=Default-Visu). Die
# gemerkte Wahl entsteht, sobald das Panel per Settings-Seite/Agent auf ein
# Profil (z.B. "pool") gestellt wird, und ueberlebt so Reboots.
_gemerkt = _load_panel_state()
if os.environ.get("LOXPANEL_PANEL"):
    _cur_panel, _PANEL_QUELLE = os.environ["LOXPANEL_PANEL"], "LOXPANEL_PANEL"
elif _gemerkt is not None:
    _cur_panel, _PANEL_QUELLE = _gemerkt, STATE_FILE
else:
    _cur_panel, _PANEL_QUELLE = CFG.get("PANEL", ""), CONF_FILE or "Standard"
# RLock: start_kiosk haelt sie ganz und ruft darin stop_kiosk, das sie auch nimmt.
_lock = threading.RLock()


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
        q.append("panel=%s" % quote(panel))
    if NUDGE_X:
        q.append("x=%s" % NUDGE_X)
    # Geraetekennung mitgeben: so ordnet der Server die WebSocket-Verbindung
    # diesem Agenten zu (Betriebsmodus-Wechsel per Push statt Chromium-Neustart,
    # Display-Abschaltung bleibt Sache des Agenten).
    q.append("device=%s" % quote(NAME))
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


def _find_backlights():
    """Alle brightness-Dateien unter /sys/class/backlight (Liste, leer wenn
    keins). Manche Panels (z.B. PX30) haben MEHRERE Devices — 'backlight' UND
    'backlight1' — die gemeinsam die LED speisen: schalten wir nur eines ab,
    bleibt das Panel hell und wird warm. Darum ALLE steuern. BL_DEVICE (falls
    gesetzt) beschraenkt bewusst auf ein einzelnes."""
    base = "/sys/class/backlight"
    if BL_DEVICE:
        names = [BL_DEVICE]
    else:
        try:
            names = sorted(os.listdir(base))
        except OSError:
            return []
    paths = []
    for name in names:
        p = os.path.join(base, name, "brightness")
        if os.path.exists(p):
            paths.append(p)
    return paths


_BL_PATHS = _find_backlights()
_bl_on_values = {}      # pro Device der zuletzt bekannte "helle" Wert
_bl_off = False         # True = wir haben die Backlights abgeschaltet


def _bl_read(path):
    try:
        with open(path, encoding="ascii") as fh:
            return int(fh.read().strip())
    except Exception:
        return None


def _bl_write(path, val):
    try:
        with open(path, "w", encoding="ascii") as fh:
            fh.write(str(int(val)))
        return True
    except Exception as e:
        print("Backlight schreiben fehlgeschlagen (%s):" % path, e)
        return False


def _bl_max(path):
    try:
        with open(os.path.join(os.path.dirname(path), "max_brightness"),
                  encoding="ascii") as fh:
            return max(1, int(fh.read().strip()))
    except Exception:
        return 255


def _bl_on_target(path):
    """Feste Ziel-Helligkeit im Ein-Zustand: BL_ON (auf gueltigen Bereich
    begrenzt) sonst max_brightness des Devices."""
    mx = _bl_max(path)
    if BL_ON:
        try:
            return max(1, min(mx, int(BL_ON)))
        except ValueError:
            pass
    return mx


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


_kiosk_paused = False   # True = Chromium ist per SIGSTOP eingefroren


def _chromium_pids():
    try:
        out = subprocess.run(["pgrep", "-f", "chromium"], capture_output=True,
                             text=True, timeout=5).stdout
        return [int(x) for x in out.split()]
    except Exception:
        return []


def _kiosk_signal(sig):
    n = 0
    for pid in _chromium_pids():
        try:
            os.kill(pid, sig)
            n += 1
        except Exception:
            pass
    return n


def _kiosk_pause():
    """Chromium einfrieren (SIGSTOP) -> CPU/Waerme fast auf Leerlauf, solange das
    Display aus ist. Idempotent."""
    global _kiosk_paused
    if not PAUSE_ON_BLANK or _kiosk_paused:
        return
    if _kiosk_signal(signal.SIGSTOP):
        _kiosk_paused = True
        print("Kiosk pausiert (Display aus)")


def _kiosk_resume():
    """Chromium fortsetzen (SIGCONT). Idempotent; laeuft auch, wenn die Pause
    inzwischen abgeschaltet wurde."""
    global _kiosk_paused
    if not _kiosk_paused:
        return
    _kiosk_signal(signal.SIGCONT)
    _kiosk_paused = False
    print("Kiosk fortgesetzt (Display an)")


def backlight_loop():
    """Reagiert im Sekundentakt auf den X-DPMS-Status (Monitor On/Off):
    - setzt ALLE Backlight-Devices bei Aus auf 0 (Panel wirklich aus) und beim
      Aufwachen auf die FESTE Ziel-Helligkeit (BL_ON bzw. max_brightness) — der
      Ist-Wert wird bewusst nicht "gelernt", sonst laesst ein zu dunkler
      Boot-Default das Panel dauerhaft dunkel;
    - pausiert optional den Chromium-Kiosk waehrend Display-Aus (SIGSTOP) und
      setzt ihn beim Aufwachen fort (SIGCONT) -> spart CPU/Waerme."""
    global _bl_off
    for p in _BL_PATHS:
        _bl_on_values[p] = _bl_on_target(p)
    # Beim Start Helligkeit sofort korrekt setzen, wenn der Monitor an ist
    # (behebt einen zu dunklen Boot-Default direkt).
    if _monitor_on() is not False:
        for p in _BL_PATHS:
            _bl_write(p, _bl_on_values[p])
        _bl_off = False
    while True:
        try:
            on = _monitor_on()
            if on is True:
                _kiosk_resume()
                if _bl_off:
                    for p in _BL_PATHS:
                        _bl_write(p, _bl_on_values[p])
                    _bl_off = False
            elif on is False:
                if not _bl_off:
                    for p in _BL_PATHS:
                        _bl_write(p, 0)
                    _bl_off = True
                _kiosk_pause()
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
    _kiosk_resume()   # falls eingefroren: erst fortsetzen, sonst greift SIGTERM nicht
    with _lock:
        if _proc and _proc.poll() is None:
            _proc.terminate()
            try:
                _proc.wait(timeout=5)
            except Exception:
                _proc.kill()
        _proc = None   # ab hier gilt das Ende des alten Prozesses nicht als Absturz


def start_kiosk(panel=None):
    # Ganz unter der Sperre: Absturz-Waechter, Auto-Reload und HTTP-/start
    # duerfen nicht gleichzeitig zwei Chromium starten.
    with _lock:
        return _start_kiosk(panel)


def _panel_merken(panel):
    """Ansicht fuer alle kuenftigen Kiosk-Starts setzen und speichern."""
    global _cur_panel
    with _lock:
        if panel != _cur_panel:
            _cur_panel = panel
            _save_panel_state(panel)   # Wahl merken -> ueberlebt Reboot


def _start_kiosk(panel):
    global _proc, _last_reload, _kiosk_paused
    if panel is not None:
        _panel_merken(panel)
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
        if KIOSK_RESTART_SECS > 0:
            threading.Thread(target=_kiosk_waechter, args=(_proc, time.monotonic()), daemon=True).start()
    _kiosk_paused = False        # frisch gestarteter Kiosk laeuft (nicht eingefroren)
    _last_reload = time.time()   # Auto-Reload-Timer bei jedem Start zuruecksetzen
    # force: Chromium-(Neu)Start setzt DPMS auf den X-Default (600) zurueck —
    # deshalb hier immer neu erzwingen (kiosk.conf-Default; Server ueberschreibt).
    apply_dpms(_dpms_default(), force=True)
    print("Kiosk gestartet:", kiosk_url(_cur_panel))
    return True


def running():
    return _proc is not None and _proc.poll() is None


_absturz_pause = 0.0   # zuletzt gewartete Pause nach einem Absturz (0 = keine Schleife)


def _pause_nach_absturz(laufzeit):
    """Pause bis zum Neustart nach einem Absturz nach `laufzeit` Sekunden Lauf.
    Stuerzt Chromium wieder ab, bevor es stabil lief, verdoppelt sie sich bis
    KIOSK_RESTART_MAX_SECS, sonst gilt wieder KIOSK_RESTART_SECS. Stabil heisst:
    laenger gelaufen als die doppelte Obergrenze. In einer Schleife liegen
    zwischen zwei Abstuerzen hoechstens Pause plus kurzer Lauf; wer doppelt so
    lange durchhaelt wie die laengste Pause, ist aus ihr heraus (dieselbe Regel
    wie Kubernetes: Obergrenze 5 min, zurueckgesetzt nach 10 min Lauf)."""
    global _absturz_pause
    if _absturz_pause and laufzeit < 2 * KIOSK_RESTART_MAX_SECS:
        _absturz_pause = min(_absturz_pause * 2, KIOSK_RESTART_MAX_SECS)
    else:
        _absturz_pause = KIOSK_RESTART_SECS
    return _absturz_pause


def _absturz_vergessen():
    """Befehl von Hand (/start, /reload, /stop): Eine fruehere Absturzschleife
    zaehlt nicht mehr, der naechste Absturz wartet wieder KIOSK_RESTART_SECS
    statt bis zu KIOSK_RESTART_MAX_SECS. Ebenso der Auto-Reload: Der Kiosk lief
    bis dahin RELOAD_HOURS ohne Absturz. Nur der Waechter laesst sie stehen."""
    global _absturz_pause
    with _lock:
        _absturz_pause = 0.0


def _kiosk_waechter(p, gestartet):
    """Absturz-Waechter fuer genau einen Chromium-Prozess `p` (eigener Thread je
    Start). Endet p, ohne dass stop_kiosk() es beendet hat (dann waere _proc
    nicht mehr p), startet er den Kiosk nach der Pause mit derselben Ansicht
    neu. Gebunden an p: Hat in der Pause jemand neu gestartet oder gestoppt,
    bleibt es dabei. Die Pause laeuft ohne Sperre, /start und /stop warten
    nicht auf sie. Braucht keinen Server (anders als der Auto-Reload)."""
    code = p.wait()
    with _lock:
        if _proc is not p:
            return
        # monotonic: Panels ohne RTC stellen die Uhr beim Booten per NTP
        laufzeit = time.monotonic() - gestartet
        pause = _pause_nach_absturz(laufzeit)
    print("Kiosk unerwartet beendet (Code %s nach %ds), Neustart in %gs" % (code, laufzeit, pause))
    time.sleep(pause)
    with _lock:
        if _proc is p:
            try:
                start_kiosk()
            except Exception as e:
                print("Kiosk-Neustart fehlgeschlagen:", e)


def announce_loop():
    url = "http://%s/api/agent/announce" % SERVER
    while True:
        try:
            # features: "panel" = kann eine Ansicht aus der Antwort uebernehmen
            data = json.dumps({"name": NAME, "panel": _cur_panel, "ip": MY_IP,
                               "port": PORT, "kiosk": running(), "features": ["panel"]}).encode()
            req = urlreq.Request(url, data=data, headers={"Content-Type": "application/json"})
            resp = urlreq.urlopen(req, timeout=6).read()
            # Server kann Geraeteeinstellungen zurueckgeben (z.B. Display-Abschaltung)
            try:
                r = json.loads(resp or b"{}")
                # Ansicht, die der Server fuer dieses Panel vorsieht (Displays
                # "Ansicht wechseln", Betriebsmodus): Die Visu hat schon per
                # WebSocket gewechselt, also ohne Chromium-Neustart uebernehmen.
                # Gilt fuer jeden weiteren Kiosk-Start und ab der naechsten
                # Meldung; dpmsOff/reloadHours dieser Antwort gehoeren schon dazu.
                neu = r.get("panel")
                if isinstance(neu, str) and neu != _cur_panel:
                    _panel_merken(neu)
                    print("Ansicht vom Server uebernommen:", neu or "(default)")
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
                # Kiosk laeuft (bewusst gestoppten NICHT wieder starten; einen
                # abgestuerzten startet _kiosk_waechter). Bewusst nur mit Antwort
                # des Servers: ohne ihn zeigte der neue Kiosk nur eine Fehlerseite.
                rh = r.get("reloadHours")
                try:
                    hours = _reload_default() if rh is None else float(rh)
                except (TypeError, ValueError):
                    hours = _reload_default()
                if hours > 0 and running() and (time.time() - _last_reload) >= hours * 3600:
                    print("Auto-Reload nach %gh (gegen Einfrieren)" % hours)
                    _absturz_vergessen()
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
        if p in ("/start", "/reload", "/stop"):
            _absturz_vergessen()
        if p == "/start":
            ok = start_kiosk(body.get("panel") if isinstance(body.get("panel"), str) else _cur_panel)
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
    # Zeilenweise ausgeben: ~/.xsession-errors bekommt Meldungen (Absturz,
    # Speicherfehler) sofort und nicht erst blockweise.
    try:
        sys.stdout.reconfigure(line_buffering=True)
    except Exception:
        pass
    if _BL_PATHS or PAUSE_ON_BLANK:
        threading.Thread(target=backlight_loop, daemon=True).start()
    if _BL_PATHS:
        print("Backlight-Steuerung aktiv:", ", ".join(_BL_PATHS))
    else:
        print("Kein Backlight-Device gefunden — nur X-DPMS (Bildsignal) aktiv")
    if PAUSE_ON_BLANK:
        print("Kiosk-Pause bei Display-Aus: aktiv")
    if AUTOSTART and (os.environ.get("DISPLAY") or os.path.exists("/tmp/.X11-unix/X0")):
        start_kiosk(_cur_panel)
    threading.Thread(target=announce_loop, daemon=True).start()
    srv = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print("LoxPanel-Agent auf :%d, Server=%s, Panel=%s (aus %s), Autostart=%s"
          % (PORT, SERVER, _cur_panel or "(default)", _PANEL_QUELLE, "an" if AUTOSTART else "aus"))
    srv.serve_forever()


if __name__ == "__main__":
    main()
