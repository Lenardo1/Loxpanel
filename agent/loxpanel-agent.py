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
SERVER = CFG.get("SERVER", "localhost:8099")
PORT = int(CFG.get("AGENT_PORT", "8130"))
NAME = CFG.get("AGENT_NAME") or socket.gethostname()

_proc = None
_cur_panel = CFG.get("PANEL", "")
_lock = threading.Lock()


def kiosk_url(panel):
    return "http://%s/" % SERVER + ("?panel=%s" % panel if panel else "")


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
           kiosk_url(_cur_panel)]
    with _lock:
        _proc = subprocess.Popen(cmd, env=env)
    print("Kiosk gestartet:", kiosk_url(_cur_panel))
    return True


def running():
    return _proc is not None and _proc.poll() is None


def announce_loop():
    url = "http://%s/api/agent/announce" % SERVER
    while True:
        try:
            data = json.dumps({"name": NAME, "panel": _cur_panel,
                               "port": PORT, "kiosk": running()}).encode()
            req = urlreq.Request(url, data=data, headers={"Content-Type": "application/json"})
            urlreq.urlopen(req, timeout=6).read()
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
    if os.environ.get("DISPLAY") or os.path.exists("/tmp/.X11-unix/X0"):
        start_kiosk(_cur_panel)
    threading.Thread(target=announce_loop, daemon=True).start()
    srv = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print("LoxPanel-Agent auf :%d, Server=%s, Panel=%s" % (PORT, SERVER, _cur_panel or "(default)"))
    srv.serve_forever()


if __name__ == "__main__":
    main()
