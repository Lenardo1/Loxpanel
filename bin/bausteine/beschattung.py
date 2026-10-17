"""Bausteine der Visu, Familie Beschattung und Antriebe: Jalousie, Tor, Fenster.

Kachel (@kachel) und Detailseite (@detail) je Typ, siehe bausteine/__init__.py.
Die Helfer (app._state, app._fmt_num ...) sind Mixins: die allgemeinen in helfer.py,
die dieser Familie in der Klasse unten; App erbt sie ueber bausteine.BausteinHelfer."""
from __future__ import annotations

from bausteine import detail, kachel
from bausteine.gemeinsam import JAL, _clean, _pos_pct

# Jalousie (Strukturdoku): details.animation 0 = Raffstore (nur er hat
# Lamellen), deviceState 1 = Geraet offline
JAL_RAFFSTORE = 0
JAL_OFFLINE = 1


@kachel("Jalousie")
def kachel_jalousie(app, uuid, c, it):
    r = JAL.render(app._with_uuid(uuid), app.states)
    # Fahrt auf der Kachel sichtbar machen: dieselben States, die die
    # Detailansicht schon liest (_view_control_inner). Ohne das steht die
    # Kachel waehrend einer halben Minute Fahrt reglos da.
    up_move, down_move, auf, ab = app._jal_fahrt(c)
    # „fährt …" vor der Stellung las sich widerspruechlich: „▲ fährt …
    # 62% zu" wirkt, als sei sie beim Auffahren trotzdem zu. Beides
    # stimmt zwar - sie faehrt auf UND steht gerade auf 62 % geschlossen
    # -, nur stand nichts dazwischen, das die zwei Angaben trennt. Ein
    # Verb benennt die Richtung eindeutig (wie beim Tor, :3219), der
    # Trenner macht die Stellung als zweite Angabe kenntlich.
    sub = r["label"]
    sperre = app._jal_sperre(c)
    if sperre:
        sub = sperre.split(":")[0] + " · " + sub
    if up_move:
        sub = "▲ öffnet · " + sub
    elif down_move:
        sub = "▼ schließt · " + sub
    # Auf/Ab auf der Kachel ueber die controls-Mechanik des Audioplayers,
    # mit den Befehlen der Detailansicht (_jal_fahrt). Die Tasten loesen
    # erst beim Tippen aus (panel.html, click auf .tctrls .tb): Ein
    # Wischer, der auf einer Taste beginnt, scrollt das Raster, statt
    # die Beschattung eine halbe Minute fahren zu lassen. Waehrend der
    # Fahrt zeigt die fahrende Richtung Stop; die Anzahl der Tasten
    # bleibt gleich, so tauscht die Visu nur Symbol und Befehl aus.
    # Ganz Auf/Ganz Ab und Beschatten bleiben in der Detailansicht.
    it.update(on=r["on"], sublabel=sub, icon="blind",
              nav={"view": "control", "id": uuid},
              controls=[{"icon": "stop" if up_move else "triup", "cmd": auf},
                        {"icon": "stop" if down_move else "tridown", "cmd": ab}])
    _p = _pos_pct(r.get("pct"))
    if _p is not None:
        it["pos"] = _p


@kachel("Gate")
def kachel_tor(app, uuid, c, it):
    pct = round((app._state(c, "position") or 0) * 100)
    it.update(on=pct > 0, icon="gate", nav={"view": "control", "id": uuid},
              pos=_pos_pct(pct),
              sublabel=("Offen" if pct >= 100 else
                        ("Geschlossen" if pct <= 0 else f"{pct}% offen")))


@kachel("Window")
def kachel_fenster(app, uuid, c, it):
    pct = round((app._state(c, "position") or 0) * 100)
    it.update(icon="blind", on=pct > 0, nav={"view": "control", "id": uuid},
              pos=_pos_pct(pct),
              sublabel=("Offen" if pct >= 100 else
                        ("Geschlossen" if pct <= 0 else f"{pct}% offen")))


@detail("Jalousie")
def detail_jalousie(app, uuid, c, route):
    ua = c.get("uuidAction")
    cu = app._with_uuid(uuid)
    up_move, down_move, auf_cmd, ab_cmd = app._jal_fahrt(c)
    pct = JAL.render(cu, app.states).get("pct")
    base = "–" if pct is None else ("Offen" if pct <= 0 else
                                    ("Geschlossen" if pct >= 100 else f"{pct}% geschlossen"))
    # Gleiche Formulierung wie auf der Kachel (_control_item), damit
    # Kachel und Detailansicht dasselbe sagen.
    val = ("▲ öffnet · " + base) if up_move else (("▼ schließt · " + base) if down_move else base)
    # Wie Original-Visu: kein Stop-Button. Tipp auf die Richtung waehrend der
    # Fahrt sendet Stop (haelt an); im Stand startet er die Fahrt.
    auf = {"label": "Auf", "on": up_move, "cmd": auf_cmd}
    ab = {"label": "Ab", "on": down_move, "cmd": ab_cmd}
    det = c.get("details") or {}
    blocks = [{"k": "hero", "icon": "blind"}, {"k": "status", "text": app._jal_status(cu)}]
    sperre = app._jal_sperre(c)
    if sperre:
        blocks.append({"k": "status", "text": sperre})
    blocks.append({"k": "value", "text": val})
    # Position und Lamellen frei waehlen (Strukturdoku: manualPosition und
    # manualLamelle, 0..100; 0 = offen bzw. Lamellen waagrecht). Lamellen
    # nur beim Raffstore (details.animation JAL_RAFFSTORE).
    if pct is not None:
        blocks.append({"k": "slider", "icon": "blind", "value": pct, "min": 0, "max": 100,
                       "cmd": {"uuid": ua, "tmpl": "manualPosition/{v}"}})
    lam = app._endlich(c, "shadePosition")
    if lam is not None and det.get("animation", JAL_RAFFSTORE) == JAL_RAFFSTORE:
        blocks.append({"k": "slider", "icon": "lamelle", "value": round(lam * 100), "min": 0, "max": 100,
                       "cmd": {"uuid": ua, "tmpl": "manualLamelle/{v}"}})
    zusatz = [{"label": "Beschatten", "cmd": {"uuid": ua, "cmd": "shade"}}]
    if det.get("isAutomatic"):
        auto = bool(app._state(c, "autoActive"))
        zusatz.append({"label": "Automatik", "on": auto, "cmd": {"uuid": ua, "cmd": "NoAuto" if auto else "auto"}})
    blocks += [
        {"k": "row", "cells": [auf, ab]},
        {"k": "row", "cells": [
            {"label": "Ganz Auf", "cmd": {"uuid": ua, "cmd": "FullUp"}},
            {"label": "Ganz Ab", "cmd": {"uuid": ua, "cmd": "FullDown"}},
        ]},
        {"k": "row", "cells": zusatz},
    ]
    return {"t": "view", "title": _clean(c.get("name")), "route": route,
            "anchor": "bottom", "blocks": blocks}


@detail("CentralJalousie")
def detail_zentral_jalousie(app, uuid, c, route):
    """Zentral-Jalousie (Strukturdoku Central Objects): alle Jalousien auf, ab,
    stoppen, beschatten, Automatik an und aus, darunter die einzelnen zum
    Oeffnen."""
    ua = c.get("uuidAction")
    blocks = [{"k": "hero", "icon": "blind"}, {"k": "status", "text": "Alle Jalousien"},
              {"k": "row", "cells": [{"label": "Ganz Auf", "cmd": {"uuid": ua, "cmd": "FullUp"}},
                                     {"label": "Stopp", "cmd": {"uuid": ua, "cmd": "stop"}},
                                     {"label": "Ganz Ab", "cmd": {"uuid": ua, "cmd": "FullDown"}}]},
              {"k": "row", "cells": [{"label": "Beschatten", "cmd": {"uuid": ua, "cmd": "shade"}},
                                     {"label": "Automatik an", "cmd": {"uuid": ua, "cmd": "auto"}},
                                     {"label": "Automatik aus", "cmd": {"uuid": ua, "cmd": "NoAuto"}}]}]
    mitglieder = [m.get("uuid") for m in ((c.get("details") or {}).get("controls") or [])
                  if m.get("uuid") in app.controls]
    if mitglieder:
        blocks += [{"k": "head", "text": "Einzeln"},
                   {"k": "row", "wrap": True, "cells": [app._jal_zelle(mu) for mu in mitglieder]}]
    return {"t": "view", "title": _clean(c.get("name")), "route": route, "anchor": "bottom", "blocks": blocks}


@detail("Gate")
def detail_tor(app, uuid, c, route):
    ua = c.get("uuidAction")
    pct = round((app._state(c, "position") or 0) * 100)
    active = app._state(c, "active") or 0
    postext = "Offen" if pct >= 100 else ("Geschlossen" if pct <= 0 else f"{pct}% offen")
    status = "öffnet …" if active > 0 else ("schließt …" if active < 0 else postext)
    return {"t": "view", "title": _clean(c.get("name")), "route": route,
            "anchor": "bottom", "blocks": [
        {"k": "hero", "icon": "gate"},
        {"k": "status", "text": status},
        {"k": "value", "text": postext},
        {"k": "row", "cells": [
            {"label": "Öffnen", "cmd": {"uuid": ua, "cmd": "open"}},
            {"label": "Stop", "cmd": {"uuid": ua, "cmd": "stop"}},
            {"label": "Schließen", "cmd": {"uuid": ua, "cmd": "close"}},
        ]},
    ]}


@detail("Window")
def detail_fenster(app, uuid, c, route):
    ua = c.get("uuidAction")
    pct = round((app._state(c, "position") or 0) * 100)
    return {"t": "view", "title": _clean(c.get("name")), "route": route,
            "anchor": "bottom", "blocks": [
        {"k": "hero", "icon": "blind"},
        {"k": "big", "text": f"{pct}%"},
        {"k": "slider", "icon": "blind", "value": pct, "min": 0, "max": 100, "step": 1,
         "cmd": {"uuid": ua, "tmpl": "moveToPosition/{v}"}},
        {"k": "row", "cells": [
            {"label": "Zu", "cmd": {"uuid": ua, "cmd": "fullclose"}},
            {"label": "Auf", "cmd": {"uuid": ua, "cmd": "fullopen"}}]},
    ]}


class BeschattungHelfer:
    """Helfer der Familie Beschattung fuer Kachel, Detailseite und Unterseiten. Mixin: App erbt sie
    ueber bausteine.BausteinHelfer, gerufen wird ueber self bzw. app."""

    def _jal_status(self, c: dict) -> str:
        s = c.get("states") or {}
        ai = s.get("autoInfoText")
        if ai and self.states.get(ai):
            return str(self.states.get(ai))
        aa = s.get("autoActive")
        if aa:
            return "Automatik aktiv" if self.states.get(aa) else "Sonnenstandsautomatik inaktiv"
        return "Manuell"

    def _jal_sperre(self, c: dict) -> str:
        """Warum eine Jalousie nicht faehrt (Strukturdoku): gesperrt (locked,
        Ausgang QI, geht vor) oder Sicherheitsabschaltung (safetyActive), mit
        dem Grund aus infoText; dazu ein Geraet, das offline ist."""
        grund = self._text(c, "infoText")
        for state, text in (("locked", "Gesperrt"), ("safetyActive", "Sicherheitsabschaltung")):
            if self._state(c, state):
                return text + (f": {grund}" if grund else "")
        if self._endlich(c, "deviceState") == JAL_OFFLINE:
            return "Gerät offline"
        return ""

    def _jal_zelle(self, uuid: str) -> dict:
        """Zelle einer Jalousie in der Zentral-Jalousie: Name und Stellung wie
        auf ihrer Kachel, ein Tipp oeffnet sie."""
        it = self._control_item(uuid)
        return {"label": " · ".join(x for x in (it.get("label"), it.get("sublabel")) if x),
                "on": bool(it.get("on")), "nav": {"view": "control", "id": uuid}}

    def _jal_fahrt(self, c: dict) -> tuple[bool, bool, dict, dict]:
        """(faehrt auf, faehrt ab, Befehl Auf, Befehl Ab) einer Jalousie, wie in
        der Original-Visu: Im Stand startet die Richtung die Fahrt, waehrend
        der Fahrt haelt jede der beiden an. Kachel und Detailansicht nehmen
        beide dies, damit sie sich gleich bedienen."""
        s = c.get("states") or {}
        auf = bool(self.states.get(s.get("up")))
        ab = bool(self.states.get(s.get("down")))
        ua = c.get("uuidAction")
        return (auf, ab, {"uuid": ua, "cmd": "Stop" if auf or ab else "Up"},
                {"uuid": ua, "cmd": "Stop" if auf or ab else "Down"})
