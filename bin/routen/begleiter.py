"""Routen der Begleit-Tablets (eigene Version): Meldung der App, Uebersicht und
Speichern fuer den Konfigurator. Logik und Datei in bin/begleiter.py."""
from __future__ import annotations

import aiohttp
from aiohttp import web

import begleiter


async def _json(request: web.Request) -> dict | None:
    try:
        d = await request.json()
    except (ValueError, aiohttp.ContentTypeError):
        return None
    return d if isinstance(d, dict) else None


async def api_begleiter_melden(request: web.Request) -> web.Response:
    """App -> Server, jede Minute: {name, version, android, modell, bedienungshilfe, ist:{...}}.
    Antwort {ok, soll}: soll = gespeicherte Einstellungen oder null (dann behaelt die App ihre)."""
    d = await _json(request)
    if d is None or not begleiter.name_ok(d.get("name")):
        return web.json_response({"ok": False, "error": "name fehlt"}, status=400)
    soll = begleiter.melden(d["name"].strip(), request.remote or "", d)
    return web.json_response({"ok": True, "soll": soll})


async def api_begleiter(request: web.Request) -> web.Response:
    """GET: Uebersicht fuer den Konfigurator. POST {name, soll}: speichern; soll null = loeschen."""
    if request.method == "GET":
        return web.json_response({"ok": True, "begleiter": begleiter.uebersicht(),
                                  "standard": begleiter.STANDARD, "farben": begleiter.FARBEN})
    d = await _json(request)
    if d is None or not begleiter.name_ok(d.get("name")):
        return web.json_response({"ok": False, "error": "name fehlt"}, status=400)
    name = d["name"].strip()
    alle = begleiter.laden()
    if d.get("soll") is None:
        alle.pop(name, None)
        begleiter.GESEHEN.pop(name, None)
    else:
        alle[name] = begleiter.zusammenfuehren(alle.get(name), begleiter.bereinigen(d.get("soll")))
    try:
        begleiter.speichern(alle)
    except OSError as err:
        return web.json_response({"ok": False, "error": str(err)}, status=500)
    return web.json_response({"ok": True, "soll": begleiter.ohne_schluessel(alle.get(name))})
