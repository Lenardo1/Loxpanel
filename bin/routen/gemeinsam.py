"""Was die Routen mehrerer Themen brauchen: den Kopf gegen Zwischenspeichern
(_NOCACHE), Push an ausgewaehlte Browser (_push mit _push_filter), einen
JSON-Body, der auch fehlen darf (_json_or_empty), und die Kennung des
laufenden Stands (server_stand).

Die Handler holen die App aus request.app["app"]; main() in webvisu.py traegt
sie in die Routentabelle ein. Importiert webvisu nicht (App nur als Typangabe)."""
from __future__ import annotations

from typing import TYPE_CHECKING

import aiohttp
from aiohttp import web

from diagnosedaten import VERSION

if TYPE_CHECKING:   # nur fuer die Typangabe, kein Import zur Laufzeit (webvisu importiert hierher)
    from webvisu import App


def server_stand() -> str:
    """Kennung des laufenden Stands fuer Visu und Konfigurator (theme-Nachricht,
    /api/devices): der Commit, ohne ihn die Kennung des Inhalts (lokaler Build
    ohne Git), sonst leer. Meldet ein neu gestarteter Server einen anderen,
    laden offene Seiten neu, statt altes HTML/JS gegen den neuen Server laufen
    zu lassen."""
    return VERSION.get("commit") or VERSION.get("inhalt") or ""


# Panel-/Config-/Settings-HTML immer frisch ausliefern: der Kiosk-Chromium
# cachte die Seite sonst heuristisch und zeigte nach einem Update die alte
# Version (aufklappende Auswahl etc. griff nicht) bis der Profil-Cache geleert
# wurde. no-cache erzwingt Revalidierung -> Updates greifen sofort.
_NOCACHE = {"Cache-Control": "no-cache, no-store, must-revalidate"}


async def _push(app: "App", msg: dict, panel: str = "", device: str = "") -> int:
    """Push an offene Visu-Verbindungen, siehe App.push(); die Routen rufen
    weiter diese Huelle."""
    return await app.push(msg, panel, device)


def _push_filter(request: web.Request, d: dict) -> tuple:
    """panel/device-Filter aus Query ODER JSON lesen."""
    return (str(d.get("panel") or request.query.get("panel") or ""),
            str(d.get("device") or request.query.get("device") or ""))


async def _json_or_empty(request: web.Request) -> dict:
    if request.method == "POST":
        try:
            return await request.json()
        except (ValueError, aiohttp.ContentTypeError):
            return {}
    return {}


