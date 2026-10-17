"""Bausteine der Visu, Familie Licht: Lichtsteuerung V2 und V1, Dimmer, Farbwahl.

Kachel (@kachel) und Detailseite (@detail) je Typ, siehe bausteine/__init__.py.
Die Helfer (app._state, app._fmt_num ...) sind Mixins: die allgemeinen in helfer.py,
die dieser Familie in der Klasse unten; App erbt sie ueber bausteine.BausteinHelfer."""
from __future__ import annotations

import re

from bausteine import detail, kachel
from bausteine.gemeinsam import LIGHT, _clean, _pos_pct

# Lichtkreise einer Lichtsteuerung nach Typ der Unterbausteine; ein
# Farb-Lichtkreis ohne bekannte Farbtemperatur bekommt diese (Kelvin), wie
# die Farbwahl-Seite (detail_farbwahl). Der alte ColorPicker (Strukturdoku:
# nur Kreis der Lichtsteuerung Generation 1, Farbtemperatur als lumitech(...))
# gehoert nicht dazu: deren Detailseite zeigt nur die Szenen.
LC_DIMMER_TYPEN = frozenset({"Dimmer", "EIBDimmer"})
LC_FARB_TYPEN = frozenset({"ColorPickerV2"})
LC_SCHALT_TYPEN = frozenset({"Switch"})
LC_KELVIN = 4000


@kachel("LightControllerV2")
def kachel_lichtsteuerung_v2(app, uuid, c, it):
    r = LIGHT.render(app._with_uuid(uuid), app.states)
    it.update(on=r["on"], sublabel=r["label"], icon="bulb",
              nav={"view": "control", "id": uuid})


@kachel("Dimmer", "EIBDimmer")
def kachel_dimmer(app, uuid, c, it):
    pos = app._state(c, "position") or 0
    it.update(icon="bulb", on=pos > 0, nav={"view": "control", "id": uuid},
              pos=_pos_pct(pos),
              sublabel=(f"{round(pos)} %" if pos > 0 else "Aus"))


@kachel("ColorPickerV2")
def kachel_farbwahl(app, uuid, c, it):
    mode, a, b, v = app._color_parse(app._state(c, "color"))
    bright = a if mode == "temp" else v
    on = bright > 0
    it.update(icon="bulb", on=on, nav={"view": "control", "id": uuid},
              sublabel=(f"{bright} %" if on else "Aus"))
    if mode == "rgb" and on:
        it["colorFixed"] = app._hsv_hex(a, b, v)   # Icon in aktueller Farbe


@kachel("LightController")
def kachel_lichtsteuerung_v1(app, uuid, c, it):
    scenes = app._lc_scenes(c)
    asc = int(app._state(c, "activeScene") or 0)
    it.update(icon="bulb", on=asc != 0, nav={"view": "control", "id": uuid},
              sublabel=(scenes.get(asc) or ("Aus" if asc == 0 else f"Szene {asc}")))


@detail("LightControllerV2")
def detail_lichtsteuerung_v2(app, uuid, c, route):
    """Lichtsteuerung (Strukturdoku LightControllerV2): die Stimmungen,
    Lieblingsstimmungen (favoriteMoods) zuerst, die weiteren
    (additionalMoods) darunter, je ein Tipp aktiviert sie (changeTo);
    vorige/naechste Stimmung (minus, plus); die Master-Helligkeit
    (details.masterValue) und jeder Lichtkreis (Unterbausteine) zum Stellen."""
    ua = c.get("uuidAction")
    cu = app._with_uuid(uuid)
    active = LIGHT.active_moods(cu, app.states)
    r = LIGHT.render(cu, app.states)

    def zelle(m):
        return {"label": _clean(m.get("name")) or str(m.get("id")), "on": m.get("id") in active,
                "cmd": {"uuid": ua, "cmd": f"changeTo/{m.get('id')}"}}
    favs, weitere = app._lc_stimmungen(c, LIGHT.moods(cu, app.states))
    blocks = [{"k": "hero", "icon": "bulb"}, {"k": "status", "text": r["label"]}]
    if favs:
        blocks.append({"k": "row", "wrap": True, "cells": [zelle(m) for m in favs]})
    blocks.append({"k": "row", "cells": [{"icon": "prev", "cmd": {"uuid": ua, "cmd": "minus"}},
                                         {"icon": "next", "cmd": {"uuid": ua, "cmd": "plus"}}]})
    master, kreise = app._lc_kreise(c)
    if master:
        blocks.append(master)
    if weitere:
        blocks += [{"k": "head", "text": "Weitere Stimmungen"},
                   {"k": "row", "wrap": True, "cells": [zelle(m) for m in weitere]}]
    if kreise:
        blocks += [{"k": "head", "text": "Lichtkreise"}, *kreise]
    return {"t": "view", "title": _clean(c.get("name")), "route": route, "blocks": blocks}


@detail("LightController")
def detail_lichtsteuerung_v1(app, uuid, c, route):
    ua = c.get("uuidAction")
    scenes = app._lc_scenes(c)
    asc = int(app._state(c, "activeScene") or 0)
    items = [{"id": f"{uuid}:0", "label": "Aus", "on": asc == 0, "icon": "stop",
              "cmd": {"uuid": ua, "cmd": "0"}}]
    for sid in sorted(scenes):
        items.append({"id": f"{uuid}:{sid}", "label": scenes[sid], "on": asc == sid,
                      "icon": "mood", "cmd": {"uuid": ua, "cmd": str(sid)}})
    return {"t": "view", "title": _clean(c.get("name")), "route": route,
            "layout": "list", "items": items}


@detail("Dimmer", "EIBDimmer")
def detail_dimmer(app, uuid, c, route):
    ua = c.get("uuidAction")
    pos = app._state(c, "position") or 0
    mn = app._state(c, "min"); mx = app._state(c, "max"); stp = app._state(c, "step")
    mn = 0 if mn is None else mn
    mx = 100 if mx is None else mx
    stp = stp if isinstance(stp, (int, float)) and stp else 1
    return {"t": "view", "title": _clean(c.get("name")), "route": route,
            "anchor": "bottom", "blocks": [
        {"k": "hero", "icon": "bulb"},
        {"k": "big", "text": f"{round(pos)} %"},
        {"k": "slider", "icon": "bulb", "value": round(pos), "min": round(mn),
         "max": round(mx), "step": stp, "cmd": {"uuid": ua, "tmpl": "{v}"}},
        {"k": "row", "cells": [
            {"label": "Aus", "cmd": {"uuid": ua, "cmd": "off"}},
            {"label": "Ein", "cmd": {"uuid": ua, "cmd": "on"}}]},
    ]}


@detail("ColorPickerV2")
def detail_farbwahl(app, uuid, c, route):
    ua = c.get("uuidAction")
    mode, a, b, v = app._color_parse(app._state(c, "color"))
    if mode == "temp":
        bright, kelvin = a, b
        bset = bright or 100
        blocks = [
            {"k": "hero", "icon": "bulb"},
            {"k": "big", "text": f"{bright} %"},
            {"k": "slider", "icon": "bulb", "value": bright, "min": 0, "max": 100,
             "step": 1, "cmd": {"uuid": ua, "tmpl": "temp({v}," + str(kelvin or LC_KELVIN) + ")"}},
            {"k": "row", "wrap": True, "cells": [
                {"label": nm, "cmd": {"uuid": ua, "cmd": f"temp({bset},{k})"}}
                for nm, k in (("Warm", 2700), ("Neutral", 4000), ("Kalt", 6500))]},
            {"k": "row", "cells": [
                {"label": "Aus", "cmd": {"uuid": ua, "cmd": f"temp(0,{kelvin or LC_KELVIN})"}}]},
        ]
    else:   # rgb (auch wenn noch kein Wert: als RGB behandeln)
        hue, sat, val = a, (b or 100), v
        bset = val or 100
        blocks = [
            {"k": "hero", "icon": "bulb"},
            {"k": "big", "text": f"{val} %"},
            {"k": "slider", "icon": "bulb", "value": val, "min": 0, "max": 100,
             "step": 1, "cmd": {"uuid": ua, "tmpl": f"hsv({hue},{sat}," + "{v})"}},
            {"k": "row", "wrap": True, "cells": [
                {"label": nm, "cmd": {"uuid": ua, "cmd": f"hsv({h},{s},{bset})"}}
                for nm, h, s in (("Rot", 0, 100), ("Gelb", 55, 100), ("Grün", 120, 100),
                                 ("Türkis", 180, 100), ("Blau", 225, 100),
                                 ("Violett", 285, 100), ("Weiß", 0, 0))]},
            {"k": "row", "cells": [
                {"label": "Aus", "cmd": {"uuid": ua, "cmd": f"hsv({hue},{sat},0)"}}]},
        ]
    return {"t": "view", "title": _clean(c.get("name")), "route": route,
            "anchor": "bottom", "blocks": blocks}


class LichtHelfer:
    """Helfer der Familie Licht fuer Kachel, Detailseite und Unterseiten. Mixin: App erbt sie ueber
    bausteine.BausteinHelfer, gerufen wird ueber self bzw. app."""

    def _lc_stimmungen(self, c: dict, moods: list[dict]) -> tuple[list[dict], list[dict]]:
        """Stimmungen einer Lichtsteuerung -> (Lieblingsstimmungen in der
        Reihenfolge von favoriteMoods, die uebrigen in der von
        additionalMoods). Ohne diese States (aeltere Anlagen) alle als
        Lieblingsstimmungen in der Reihenfolge von moodList."""
        nach_id = {m.get("id"): m for m in moods if isinstance(m, dict)}
        fav = self._json_state(c, "favoriteMoods")
        if not isinstance(fav, list):
            return list(nach_id.values()), []
        favs = [nach_id[i] for i in fav if i in nach_id]
        rest = self._json_state(c, "additionalMoods")
        reihe = [i for i in (rest if isinstance(rest, list) else []) if i in nach_id and i not in fav]
        reihe += [i for i in nach_id if i not in fav and i not in reihe]
        return favs, [nach_id[i] for i in reihe]

    def _lc_kreise(self, c: dict) -> tuple[dict | None, list[dict]]:
        """Master-Helligkeit (details.masterValue) und Lichtkreise einer
        Lichtsteuerung als Bloecke: Dimmer als Regler mit ihren Grenzen
        (min, max, step), Farb-Lichtkreise als Helligkeitsregler, der Farbe
        bzw. Farbtemperatur behaelt, Schalter als Zelle an/aus. Befehle gehen
        an den Lichtkreis selbst (seine uuidAction)."""
        det = c.get("details") or {}
        master_u, farbe_u = det.get("masterValue"), det.get("masterColor")
        master, kreise, schalter = None, [], []
        for su, s in (c.get("subControls") or {}).items():
            if not isinstance(s, dict) or su == farbe_u:
                continue
            sua, name, t = s.get("uuidAction") or su, _clean(s.get("name")), s.get("type")
            if t in LC_DIMMER_TYPEN:
                pos = self._endlich(s, "position")
                if pos is None:
                    continue
                mn, mx, st = (self._endlich(s, n) for n in ("min", "max", "step"))
                b = {"k": "slider", "icon": "bulb", "value": round(pos), "min": round(mn or 0),
                     "max": round(mx) if mx and mx > (mn or 0) else 100, "step": st or 1,
                     "cmd": {"uuid": sua, "tmpl": "{v}"}}
                if su == master_u:
                    master = {**b, "label": "Helligkeit"}
                else:
                    kreise.append({**b, "label": name})
            elif t in LC_FARB_TYPEN:
                mode, a, bb, v = self._color_parse(self._state(s, "color"))
                tmpl = (f"temp({{v}},{bb or LC_KELVIN})" if mode == "temp" else f"hsv({a},{bb or 100},{{v}})")
                kreise.append({"k": "slider", "icon": "bulb", "label": name, "value": a if mode == "temp" else v,
                               "min": 0, "max": 100, "step": 1, "cmd": {"uuid": sua, "tmpl": tmpl}})
            elif t in LC_SCHALT_TYPEN:
                an = bool(self._state(s, "active"))
                schalter.append({"label": name, "on": an, "cmd": {"uuid": sua, "cmd": "off" if an else "on"}})
        if schalter:
            kreise.append({"k": "row", "wrap": True, "cells": schalter})
        return master, kreise

    def _lc_scenes(self, c: dict) -> dict:
        """LightController-V1 sceneList (Loxone-Format id=\"name\") -> {id:name}."""
        raw = str(self._state(c, "sceneList") or "")
        return {int(m.group(1)): m.group(2) for m in re.finditer(r'(\d+)="([^"]*)"', raw)}
