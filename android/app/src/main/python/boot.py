"""
Launcher fuer den eingebetteten LoxPanel-Server auf Android.

Startet webvisu.py aus <app_dir>/bin. Problem: webvisu.main() ruft am Ende
aiohttp.web.run_app(), das Signal-Handler setzt — die crashen in einem
Hintergrund-Thread auf Android. Loesung: web.run_app durch eine signal-freie
Variante (AppRunner/TCPSite + run_forever) ersetzen, dann webvisu.main() rufen.
"""
import os
import sys
import asyncio
import threading
import traceback

_started = False


def _start_server(app_dir, port):
    binp = os.path.join(app_dir, "bin")
    if binp not in sys.path:
        sys.path.insert(0, binp)
    os.environ["LOXPANEL_PORT"] = str(port)

    # Optionale lokale Icon-Bibliothek (falls spaeter mitgeliefert)
    icons = os.path.join(app_dir, "loxone-icons", "filled")
    if os.path.isdir(icons):
        os.environ["LOXPANEL_LOXLIB_DIR"] = icons

    from aiohttp import web

    def _run_app_no_signals(app, host="0.0.0.0", port=8099, **kwargs):
        # Ersatz fuer web.run_app OHNE loop.add_signal_handler (Android-Thread).
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        runner = web.AppRunner(app)
        loop.run_until_complete(runner.setup())     # triggert on_startup (Tasks)
        site = web.TCPSite(runner, host, port)
        loop.run_until_complete(site.start())
        print("LoxPanel-Server laeuft auf %s:%s" % (host, port), flush=True)
        loop.run_forever()

    web.run_app = _run_app_no_signals               # global patchen
    sys.argv = ["webvisu"]                          # argparse: keine Android-Args

    import webvisu
    webvisu.main()                                  # baut App+Routen -> (gepatchtes) run_app


def start_bg(app_dir, port, intercom_token=""):
    """Startet den Server in einem Daemon-Thread. Idempotent."""
    global _started
    if _started:
        return "already-running"
    # Nur die native Bruecke kennt dieses Prozess-Token, nie die WebView.
    if intercom_token:
        os.environ["LOXPANEL_INTERCOM_TOKEN"] = str(intercom_token)
    _started = True

    def _run():
        try:
            _start_server(app_dir, int(port))
        except Exception:
            traceback.print_exc()

    threading.Thread(target=_run, name="loxpanel-server", daemon=True).start()
    return "started"
