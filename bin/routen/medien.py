"""Bilder fuer Visu und Konfigurator: Loxone-Icons (/icon), die Liste der Icons
(/api/loxicons), eigene Symbole (/loxlib), Klingelbilder (/bellimg) und
Cover ueber den Proxy (/cover). Holen und Zwischenspeichern macht das
Mixin Medien (medien.py).

Die Handler holen die App aus request.app["app"]; main() in webvisu.py traegt
sie in die Routentabelle ein. Importiert webvisu nicht (App nur als Typangabe)."""
from __future__ import annotations

import os
from typing import TYPE_CHECKING

from aiohttp import web

from bausteine.intercom import _BELL_TS
from konfig import _LOXLIB_NAME, _loxlib_names, LOXLIB_DIR

if TYPE_CHECKING:   # nur fuer die Typangabe, kein Import zur Laufzeit (webvisu importiert hierher)
    from webvisu import App


async def icon_handler(request: web.Request) -> web.Response:
    app: App = request.app["app"]
    p = request.query.get("p", "")
    if not p or ".." in p or not (p.endswith(".svg") or p.endswith(".png")):
        return web.Response(status=400, text="bad icon")
    res = await app.fetch_icon(p)
    if not res:
        return web.Response(status=404)
    body, ctype = res
    return web.Response(body=body, content_type=ctype.split(";")[0],
                        headers={"Cache-Control": "max-age=86400"})


async def loxicons_handler(request: web.Request) -> web.Response:
    """Namen der Loxone-Bibliothek (fuer den Kachel-Editor, lazy geladen)."""
    return web.json_response({"icons": _loxlib_names()})


async def loxlib_handler(request: web.Request) -> web.Response:
    """Ein SVG der Loxone-Bibliothek aus dem gemounteten Ordner ausliefern.
    Nur flache, validierte Dateinamen - kein Pfad-Ausbruch."""
    n = request.query.get("n", "")
    if not _LOXLIB_NAME.match(n) or ".." in n:
        return web.Response(status=400, text="bad")
    path = os.path.join(LOXLIB_DIR, n)
    if os.path.dirname(os.path.abspath(path)) != os.path.abspath(LOXLIB_DIR):
        return web.Response(status=400, text="bad")
    try:
        with open(path, "rb") as f:
            body = f.read()
    except OSError:
        return web.Response(status=404)
    return web.Response(body=body, content_type="image/svg+xml",
                        headers={"Cache-Control": "max-age=86400"})


async def bellimg_handler(request: web.Request) -> web.Response:
    """Bild einer verpassten Klingel (/bellimg?id=<Intercom>&ts=JJJJMMTTHHMMSS),
    vom Miniserver geholt (fetch_bell_image)."""
    app: App = request.app["app"]
    c = app.controls.get(request.query.get("id", ""))
    ts = request.query.get("ts", "")
    if not c or c.get("type") != "Intercom" or not _BELL_TS.fullmatch(ts):
        return web.Response(status=400, text="bad bell image")
    res = await app.fetch_bell_image(c.get("uuidAction") or "", ts)
    if not res:
        return web.Response(status=404)
    body, ctype = res
    return web.Response(body=body, content_type=ctype.split(";")[0],
                        headers={"Cache-Control": "max-age=86400"})


async def cover_handler(request: web.Request) -> web.Response:
    app: App = request.app["app"]
    u = request.query.get("u", "")
    if not (u.startswith("http://") or u.startswith("https://")):
        return web.Response(status=400, text="bad cover")
    res = await app.fetch_cover(u)
    if not res:
        return web.Response(status=404)
    body, ctype = res
    return web.Response(body=body, content_type=ctype.split(";")[0],
                        headers={"Cache-Control": "max-age=60"})


