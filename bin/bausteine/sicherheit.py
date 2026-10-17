"""Bausteine der Visu, Familie Sicherheit und Melder: Alarmanlage, Rauchmelder, Praesenzmelder, Fensterueberwachung, Postkasten.

Kachel (@kachel) und Detailseite (@detail) je Typ, siehe bausteine/__init__.py.
Die Helfer (app._state, app._fmt_num ...) sind Mixins in helfer.py und den Familien, App erbt sie ueber bausteine.BausteinHelfer."""
from __future__ import annotations

from bausteine import detail, kachel
from bausteine.gemeinsam import _clean


@kachel("SmokeAlarm")
def kachel_rauchmelder(app, uuid, c, it):
    ok = (app._state(c, "level") or 0) == 0
    it.update(icon="alarm", sublabel=("Alles ok" if ok else "Alarm!"),
              tone=("good" if ok else "crit"))


@kachel("PresenceDetector")
def kachel_praesenzmelder(app, uuid, c, it):
    on = bool(app._state(c, "active"))
    itxt = app._text(c, "infoText")
    it.update(icon="info", on=on,
              sublabel=(itxt if itxt and itxt.lower() not in ("on", "off")
                        else ("Anwesend" if on else "Abwesend")))


@kachel("WindowMonitor")
def kachel_fensterueberwachung(app, uuid, c, it):
    op = int(app._state(c, "numOpen") or 0) + int(app._state(c, "numTilted") or 0)
    it.update(icon="blind", on=op > 0, nav={"view": "control", "id": uuid},
              sublabel=(f"{op} offen" if op else "Alle geschlossen"))


@kachel("Alarm")
def kachel_alarmanlage(app, uuid, c, it):
    armed = bool(app._state(c, "armed"))
    lvl = app._state(c, "level") or 0
    it.update(icon="alarm", on=armed, tone=("crit" if lvl else None),
              nav={"view": "control", "id": uuid},
              sublabel=("Alarm!" if lvl else ("Scharf" if armed else "Unscharf")))


@kachel("MailBox")
def kachel_postkasten(app, uuid, c, it):
    mail = bool(app._state(c, "mailReceived"))
    pk = bool(app._state(c, "packetReceived"))
    sub = " · ".join(x for x, f in (("Post da", mail), ("Paket da", pk)) if f) or "Leer"
    it.update(icon="info", on=(mail or pk), nav={"view": "control", "id": uuid}, sublabel=sub)
    if mail or pk:
        it["hinweis"] = {"stufe": "an", "symbol": "mail"}


@detail("WindowMonitor")
def detail_fensterueberwachung(app, uuid, c, route):
    windows = (c.get("details") or {}).get("windows") or []
    codes = [x for x in str(app._state(c, "windowStates") or "").split(",") if x != ""]

    def wtext(b):
        parts = []
        if b & 1:
            parts.append("geschlossen")
        if b & 2:
            parts.append("gekippt")
        if b & 4:
            parts.append("offen")
        if b & 8:
            parts.append("verriegelt")
        if b & 32:
            parts.append("offline")
        return ", ".join(parts) or "–"

    items = []
    for i, w in enumerate(windows):
        try:
            b = int(float(codes[i])) if i < len(codes) else 0
        except (ValueError, TypeError):
            b = 0
        items.append({"id": f"{uuid}:{i}", "icon": "blind", "on": bool(b & 6),
                      "label": _clean(w.get("name") or f"Fenster {i + 1}"),
                      "sublabel": wtext(b)})
    return {"t": "view", "title": _clean(c.get("name")), "route": route,
            "layout": "list", "items": items}


@detail("SmokeAlarm")
def detail_rauchmelder(app, uuid, c, route):
    ok = (app._state(c, "level") or 0) == 0
    return app._big_view(uuid, "alarm", "Alles ok" if ok else "Alarm!",
                          tone=("good" if ok else "crit"))


@detail("PresenceDetector")
def detail_praesenzmelder(app, uuid, c, route):
    on = bool(app._state(c, "active"))
    itxt = app._text(c, "infoText")
    big = itxt if (itxt and itxt.lower() not in ("on", "off")) else ("Anwesend" if on else "Abwesend")
    return app._big_view(uuid, "info", big)


@detail("Alarm")
def detail_alarmanlage(app, uuid, c, route):
    ua = c.get("uuidAction")
    armed = bool(app._state(c, "armed"))
    lvl = app._state(c, "level") or 0
    big = {"k": "big", "text": ("Alarm!" if lvl else ("Scharf" if armed else "Unscharf"))}
    if lvl:
        big["tone"] = "crit"
    elif not armed:
        big["tone"] = "good"
    if lvl:                                   # Alarm ausgeloest
        sub = "Alarm ausgelöst"
        cells = [{"label": "Quittieren", "cmd": {"uuid": ua, "cmd": "quit"}},
                 {"label": "Unscharf", "cmd": {"uuid": ua, "cmd": "off"}}]
    elif armed:                               # scharf -> nur entschaerfen
        sub = "Anlage ist scharf"
        cells = [{"label": "Unscharf", "cmd": {"uuid": ua, "cmd": "off"}}]
    else:                                     # unscharf -> scharfschalten
        sub = "Bereit zum Scharfschalten"
        cells = [{"label": "Scharf", "cmd": {"uuid": ua, "cmd": "on"}},
                 {"label": "Verzögert", "cmd": {"uuid": ua, "cmd": "delayedon"}}]
    return {"t": "view", "title": _clean(c.get("name")), "route": route,
            "anchor": "bottom", "blocks": [
        {"k": "hero", "icon": "alarm"},
        big,
        {"k": "status", "text": sub},
        {"k": "row", "cells": cells},
    ]}


@detail("MailBox")
def detail_postkasten(app, uuid, c, route):
    mail = bool(app._state(c, "mailReceived"))
    pk = bool(app._state(c, "packetReceived"))
    big = "Post und Paket" if (mail and pk) else ("Post da" if mail else ("Paket da" if pk else "Leer"))
    return app._big_view(uuid, "info", big, "Postkasten", tone=("good" if (mail or pk) else None))
