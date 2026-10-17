"""Zustand des Servers: /api/health (Docker-HEALTHCHECK und Waechter der App;
503, sobald eine Hintergrundaufgabe endet) und das Diagnosepaket
(/api/diagnose, gebaut von diagnose.py).

Die Handler holen die App aus request.app["app"]; main() in webvisu.py traegt
sie in die Routentabelle ein. Importiert webvisu nicht (App nur als Typangabe)."""
from __future__ import annotations

import json
import logging
import re
import time
from datetime import datetime
from typing import TYPE_CHECKING

from aiohttp import web

import diagnose
from diagnosedaten import VERSION
from konfig import _CFGDIR
from routen.gemeinsam import _NOCACHE
from sicherung import BACKUP_FILES

if TYPE_CHECKING:   # nur fuer die Typangabe, kein Import zur Laufzeit (webvisu importiert hierher)
    from webvisu import App

log = logging.getLogger("loxpanel.webvisu")   # derselbe Logger wie der Server


def _aufgaben_stand(a: web.Application) -> tuple[dict, bool]:
    """Hintergrundaufgaben (on_startup) -> ({Name: "läuft" | "beendet[: Fehler]"},
    alle laufen). Fuer /api/health und das Diagnosepaket."""
    tasks, ok = {}, True
    for name, t in (a.get("tasks") or {}).items():
        if not t.done():
            tasks[name] = "läuft"
            continue
        ok = False
        err = None if t.cancelled() else t.exception()
        tasks[name] = f"beendet: {err!r}" if err else "beendet"
    return tasks, ok


async def api_health(request: web.Request) -> web.Response:
    """Zustand fuer den Docker-HEALTHCHECK (Unraid zeigt ihn im Docker-Tab) und
    den Waechter der LoxPanel-App, der die App bei 503 neu startet.

    503, sobald eine Hintergrund-Aufgabe beendet ist: dann bekommen die Panels
    keine Werte oder Ansichten mehr, und ein Neustart des Containers hilft. Die
    Miniserver-Verbindung wird nur gemeldet - ist der Miniserver weg, hilft ein
    Neustart nicht, stream_task verbindet von selbst neu."""
    app: App = request.app["app"]
    tasks, ok = _aufgaben_stand(request.app)
    started = request.app.get("started")
    return web.json_response({
        "ok": ok, "tasks": tasks,
        "miniserver": bool(app.client and app.ws),
        "panels": len(app.conn_route),
        "uptime": round(time.monotonic() - started) if started is not None else None,
        "version": VERSION,
    }, status=200 if ok else 503, headers=_NOCACHE)


# Dateiname des Diagnosepakets: nur, was jeder Browser und jedes Dateisystem nimmt
_DATEINAME_RE = re.compile(r"[^A-Za-z0-9_-]+")


async def api_diagnose(request: web.Request) -> web.Response:
    """Diagnosepaket als ZIP (bin/diagnose.py): ?device= fuer ein Geraet
    (Konfigurator: Geraete -> Diagnose), sonst der Server mit allen Geraeten
    (Einstellungen -> Sicherung). 404 fuer ein unbekanntes Geraet. Die
    Einstellungsdateien wie in der Sicherung; eine unlesbare bleibt draussen,
    ungeprueft koennte sie ein Kennwort enthalten."""
    app: App = request.app["app"]
    geraet = (request.query.get("device") or "").strip()
    aufgaben, _ok = _aufgaben_stand(request.app)
    try:
        daten, geheim = app.diagnose_daten(geraet, aufgaben, request.app.get("started"))
    except KeyError:
        return web.json_response({"ok": False, "error": f"Gerät {geraet!r} unbekannt"}, status=404)
    einstellungen, fehlen = {}, []
    for name in BACKUP_FILES:
        f = _CFGDIR / name
        if not f.is_file():
            continue
        try:
            einstellungen[name] = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError) as err:
            log.warning("Diagnose: %s nicht lesbar (%s) - nicht enthalten", name, err)
            fehlen.append(name)
    if fehlen:
        daten["einstellungen_unlesbar"] = fehlen
    body = diagnose.paket(daten, einstellungen, diagnose.LOG.zeilen(), geheim)
    teil = _DATEINAME_RE.sub("_", geraet).strip("_") or "server"
    name = f"loxpanel-diagnose-{teil}-{datetime.now():%Y-%m-%d_%H%M}.zip"
    return web.Response(body=body, content_type="application/zip",
                        headers={**_NOCACHE, "Content-Disposition": f'attachment; filename="{name}"'})


