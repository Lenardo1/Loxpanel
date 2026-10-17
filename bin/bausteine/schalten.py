"""Bausteine der Visu, Familie Schalten: Schalter, Zeitschalter, Schaltuhr, Taster, Auf/Ab digital, Radiotaste.

Kachel (@kachel) und Detailseite (@detail) je Typ, siehe bausteine/__init__.py.
Die Helfer (app._state, app._fmt_num ...) sind Mixins: die allgemeinen in helfer.py,
die dieser Familie in der Klasse unten; App erbt sie ueber bausteine.BausteinHelfer."""
from __future__ import annotations

import re

from bausteine import detail, kachel
from bausteine.gemeinsam import SWITCHY, _clean


@kachel(*SWITCHY)
def kachel_schalter(app, uuid, c, it):
    on = bool(app._state(c, "active"))
    it.update(on=on, sublabel="Ein" if on else "Aus", icon="switch",
              cmd={"uuid": c.get("uuidAction"), "cmd": "off" if on else "on"})
    # lockedOn (Strukturdoku): die Logik haelt ihn an, Aus wirkt nicht
    if on and app._state(c, "lockedOn"):
        it["sublabel"] = "Ein (von der Logik gehalten)"


@kachel("TimedSwitch")
def kachel_zeitschalter(app, uuid, c, it):
    # Treppenhaus-/Zeitschalter: kein 'active'-State, sondern
    # 'deactivationDelay' (>0 = laeuft noch N Sek, -1 = dauerhaft an,
    # 0 = aus). 'pulse' startet den Timer, 'off' schaltet aus.
    dd = app._state(c, "deactivationDelay")
    try:
        dd = float(dd if dd is not None else 0)
    except (TypeError, ValueError):
        dd = 0.0
    on = dd != 0
    if dd > 0:
        sub = "noch %d:%02d" % (int(dd) // 60, int(dd) % 60)
    elif dd < 0:
        sub = "Ein"
    else:
        sub = "Aus"
    it.update(on=on, sublabel=sub, icon="bulb",
              cmd={"uuid": c.get("uuidAction"), "cmd": "off" if on else "pulse"})


@kachel("Daytimer")
def kachel_schaltuhr(app, uuid, c, it):
    # Wochenschaltuhr: aktueller Wert + ob ein manueller Timer (override) laeuft.
    ov = bool(app._state(c, "override"))
    it.update(icon="info", on=bool(app._state(c, "value")),
              nav={"view": "control", "id": uuid},
              sublabel=app._daytimer_value(c) + (" · Timer läuft" if ov else ""))


@kachel("UpDownDigital")
def kachel_auf_ab_digital(app, uuid, c, it):
    # Auf/Ab-Taster (keine States) -> Detailseite mit Auf/Ab/Stop.
    it.update(icon="blind", nav={"view": "control", "id": uuid}, sublabel="Auf / Ab", subInfo=True)


@kachel("Pushbutton")
def kachel_taster(app, uuid, c, it):
    it.update(icon="switch", sublabel="Taster",
              cmd={"uuid": c.get("uuidAction"), "cmd": "pulse"})


@kachel("Radio")
def kachel_radiotaste(app, uuid, c, it):
    det = c.get("details") or {}
    outs = det.get("outputs") or {}
    aoi = int(app._state(c, "activeOutput") or 0)
    # Kein Ausgang aktiv: der Text, den Loxone dafuer vergibt (allOff,
    # etwa "Automatik"), wie in der Detailseite; ohne ihn ein Strich.
    ruhe = det.get("allOff") or "–"
    it.update(icon="switch", nav={"view": "control", "id": uuid},
              sublabel=(outs.get(str(aoi)) or (ruhe if aoi == 0 else f"Ausgang {aoi}")))


@detail("Radio")
def detail_radiotaste(app, uuid, c, route):
    ua = c.get("uuidAction")
    det = c.get("details") or {}
    outs = det.get("outputs") or {}
    ao = int(app._state(c, "activeOutput") or 0)
    items = []
    if det.get("allOff"):
        items.append({"id": f"{uuid}:0", "label": det["allOff"], "on": ao == 0,
                      "icon": "stop", "cmd": {"uuid": ua, "cmd": "reset"}})
    for k in sorted(outs, key=lambda x: int(x)):
        items.append({"id": f"{uuid}:{k}", "label": outs[k], "on": ao == int(k),
                      "icon": "mood", "cmd": {"uuid": ua, "cmd": str(k)}})
    return {"t": "view", "title": _clean(c.get("name")), "route": route,
            "layout": "list", "items": items}


@detail("Daytimer")
def detail_schaltuhr(app, uuid, c, route):
    ua = c.get("uuidAction")
    ov = bool(app._state(c, "override"))
    mode = app._daytimer_mode(c)
    sub = ("Timer läuft · " + mode) if (ov and mode) else ("Timer läuft" if ov else mode)
    hero = {"k": "hero", "icon": "info"}
    iu = app._control_icon_url(c)
    if iu:
        hero["iconUrl"] = iu
    blocks = [hero, {"k": "astat", "text": app._daytimer_value(c), "sub": sub}]
    # Laeuft ein manueller Timer (override), kann er beendet werden
    # (stopOverride). Sonst 4 feste Dauern zum Starten: startOverride/
    # {value}/{sekunden} — value=1 (einschalten) fuer die gewaehlte Zeit.
    if ov:
        blocks.append({"k": "row", "cells": [
            {"label": "Timer beenden", "cmd": {"uuid": ua, "cmd": "stopOverride"}}]})
    else:
        blocks.append({"k": "row", "wrap": True, "cells": [
            {"label": "15 min", "cmd": {"uuid": ua, "cmd": "startOverride/1/900"}},
            {"label": "30 min", "cmd": {"uuid": ua, "cmd": "startOverride/1/1800"}},
            {"label": "60 min", "cmd": {"uuid": ua, "cmd": "startOverride/1/3600"}},
            {"label": "90 min", "cmd": {"uuid": ua, "cmd": "startOverride/1/5400"}},
        ]})
    return {"t": "view", "title": _clean(c.get("name")), "route": route,
            "anchor": "bottom", "blocks": blocks}


@detail("UpDownDigital")
def detail_auf_ab_digital(app, uuid, c, route):
    # Auf/Ab-Taster ohne States: gedrueckt halten = fahren (UpOn), loslassen
    # = stoppen (UpOff). Push&hold ist die sichere Taster-Semantik.
    ua = c.get("uuidAction")
    return {"t": "view", "title": _clean(c.get("name")), "route": route,
            "anchor": "bottom", "blocks": [
        {"k": "hero", "icon": "blind"},
        {"k": "status", "text": "Zum Fahren gedrückt halten"},
        {"k": "row", "cells": [
            {"icon": "up", "hold": True, "cmd": {"uuid": ua, "cmd": "UpOn"},
             "release": {"uuid": ua, "cmd": "UpOff"}},
            {"icon": "down", "hold": True, "cmd": {"uuid": ua, "cmd": "DownOn"},
             "release": {"uuid": ua, "cmd": "DownOff"}}]},
    ]}


class SchaltenHelfer:
    """Helfer der Familie Schalten fuer Kachel, Detailseite und Unterseiten. Mixin: App erbt sie
    ueber bausteine.BausteinHelfer, gerufen wird ueber self bzw. app."""

    def _daytimer_mode(self, c: dict) -> str:
        """Aktiver Modus/Tag eines Daytimers als Name. `mode` (Zahl) wird ueber
        `modeList` aufgeloest, Format: '0:mode=0;name=\"Feiertag\",1:mode=3;
        name=\"Montag\",...' (Anfuehrungszeichen escaped)."""
        raw = str(self._state(c, "modeList") or "").replace('\\"', '"')
        modes = {int(m): n for m, n in re.findall(r'mode=(\d+);name="([^"]*)"', raw)}
        try:
            return modes.get(int(float(self._state(c, "mode"))), "")
        except (TypeError, ValueError):
            return ""

    def _daytimer_value(self, c: dict) -> str:
        """Aktueller Wert eines Daytimers als Text: 0/leer -> „Aus"; analog ->
        formatiert (details.format); digital -> „Ein"."""
        val = self._state(c, "value")
        if not val:
            return "Aus"
        det = c.get("details") or {}
        if det.get("analog"):
            return self._fmt_num(val, det.get("format") or "%.1f")
        return "Ein"
