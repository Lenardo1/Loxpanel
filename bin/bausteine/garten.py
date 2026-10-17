"""Bausteine der Visu, Familie Garten: Bewaesserung.

Kachel (@kachel) und Detailseite (@detail) je Typ, siehe bausteine/__init__.py.
Die Helfer (app._state, app._fmt_num ...) sind Mixins: die allgemeinen in helfer.py,
die dieser Familie in der Klasse unten; App erbt sie ueber bausteine.BausteinHelfer."""
from __future__ import annotations

from bausteine import detail, kachel
from bausteine.gemeinsam import (
    _clean, DAUER_SCHRITT, _dauer_text, IRR_ALLE_AKTIV, IRR_AUS, IRR_SELECT_ALLE, IRR_SELECT_AUS)


@kachel("Irrigation")
def kachel_bewaesserung(app, uuid, c, it):
    act = app._irr_running(c)
    rain = bool(app._state(c, "rainActive"))
    sub = "Bewässert" if act else ("Regenpause" if rain else "Bereit")
    zone = app._irrigation_zone_name(c)
    if act and zone:
        sub += " · " + zone
    it.update(icon="info", on=act, nav={"view": "control", "id": uuid}, sublabel=sub)


@detail("Irrigation")
def detail_bewaesserung(app, uuid, c, route):
    ua = c.get("uuidAction")
    act = app._irr_running(c)
    cur = app._irr_current(c)
    rain = bool(app._state(c, "rainActive"))
    big = "Bewässert" if act else ("Regenpause" if rain else "Bereit")
    rows = []
    zone = app._irrigation_zone_name(c)
    if zone:
        rows.append({"k": "status", "text": "Aktive Zone: " + zone})
    ep = app._state(c, "expectedPrecipitation")
    if ep is not None:
        txt = f"Erwarteter Niederschlag {app._fmt_num(ep, '%.1f mm')}"
        grenze = app._state(c, "maxExpectedPrecipitation")
        if grenze is not None:
            txt += f" · Grenze {app._fmt_num(grenze, '%.1f mm')}"
        rows.append({"k": "status", "text": txt})
    regen = app._state(c, "rainTime")
    if isinstance(regen, (int, float)) and regen > 0:
        rows.append({"k": "status", "text": "Regen in den letzten 24 h: " + _dauer_text(regen)})
    # Zonen: Antippen oeffnet die Zone (starten/stoppen, Laufzeit).
    zones = app._irr_zones(c)
    if zones:
        rows.append({"k": "head", "text": "Zonen"})
        rows.append({"k": "row", "wrap": True, "cells": [
            {"label": z["name"] + (" · " + _dauer_text(z["duration"]) if z["duration"] is not None else ""),
             "on": cur in (z["id"], IRR_ALLE_AKTIV),
             "nav": {"view": "irrzone", "id": uuid, "zone": z["id"]}} for z in zones]})
    # Steuerung laut Loxone-Strukturdoku: start = nur wenn noetig,
    # startForce = erwarteten/vergangenen Regen ignorieren, stop, dazu
    # select fuer alle Zonen an/aus (Zahlen siehe IRR_SELECT_*).
    rows.append({"k": "row", "cells": [
        {"label": "Start", "on": act, "cmd": {"uuid": ua, "cmd": "start"}},
        {"label": "Erzwingen", "cmd": {"uuid": ua, "cmd": "startForce"}},
        {"label": "Stopp", "on": not act, "cmd": {"uuid": ua, "cmd": "stop"}},
    ]})
    rows.append({"k": "row", "cells": [
        {"label": "Alle Zonen", "cmd": {"uuid": ua, "cmd": f"select/{IRR_SELECT_ALLE}"}},
        {"label": "Alles aus", "cmd": {"uuid": ua, "cmd": f"select/{IRR_SELECT_AUS}"}},
    ]})
    return {"t": "view", "title": _clean(c.get("name")), "route": route,
            "anchor": "bottom", "blocks": [
        {"k": "hero", "icon": "info"},
        {"k": "big", "text": big, **({"tone": "good"} if act else {})},
        {"k": "status", "text": "Bewässerung"},
        *rows,
    ]}


class GartenHelfer:
    """Helfer der Familie Garten fuer Kachel, Detailseite und Unterseiten. Mixin: App erbt sie ueber
    bausteine.BausteinHelfer, gerufen wird ueber self bzw. app."""

    def _view_irr_zone(self, uuid: str, zone) -> dict:
        """Eine Zone der Bewaesserung: starten (select, Nummer siehe
        IRR_SELECT_*) bzw. stoppen (stop) und ihre Laufzeit
        (setDuration/{id}={Sekunden}). Gibt die Logik die Laufzeit vor
        (setByLogic), steht sie nur da."""
        c = self.controls.get(uuid or "", {})
        route = {"view": "irrzone", "id": uuid, "zone": zone}
        try:
            zid = int(zone)
        except (TypeError, ValueError):
            zid = None
        z = (next((z for z in self._irr_zones(c) if z["id"] == zid), None)
             if c.get("type") == "Irrigation" else None)
        if z is None:
            return self._gone_view(route, _clean(c.get("name")), "Diese Zone gibt es nicht mehr.")
        ua = c.get("uuidAction")
        cur = self._irr_current(c)
        an = cur in (zid, IRR_ALLE_AKTIV)
        blocks = [{"k": "title", "text": z["name"], "sub": _clean(c.get("name"))},
                  {"k": "big", "text": "Läuft" if an else "Aus", **({"tone": "good"} if an else {})}]
        if z["duration"] is not None:
            dauer = {"k": "stepper", "label": "Laufzeit", "value": z["duration"], "fmt": "dauer"}
            if z["logic"]:
                dauer["sub"] = "von der Logik vorgegeben"
            else:
                dauer.update(step=DAUER_SCHRITT, min=0,
                             cmd={"uuid": ua, "tmpl": f"setDuration/{zid}={{v}}"})
            blocks.append(dauer)
        if an:
            knopf = {"label": "Alle Zonen stoppen" if cur == IRR_ALLE_AKTIV else "Zone stoppen",
                     "cmd": {"uuid": ua, "cmd": "stop"}}
        else:
            knopf = {"label": "Zone starten", "cmd": {"uuid": ua, "cmd": f"select/{zid + 1}"}}
        blocks.append({"k": "row", "cells": [knopf]})
        return {"t": "view", "title": z["name"], "route": route, "anchor": "bottom", "blocks": blocks}

    def _irr_zones(self, c: dict) -> list[dict]:
        """Zonen der Bewaesserung aus dem State zones (JSON, laut Strukturdoku
        [{id, name, duration, setByLogic}], id ab 0), nach id sortiert ->
        [{id, name, duration (Sekunden oder None), logic}]. Eine Zone ohne
        Nummer faellt weg: ohne sie gaebe es keinen Befehl fuer sie."""
        data = self._json_state(c, "zones")
        seq = data.values() if isinstance(data, dict) else (data if isinstance(data, list) else [])
        out = []
        for z in seq:
            if not isinstance(z, dict):
                continue
            try:
                zid = int(z.get("id"))
            except (TypeError, ValueError):
                continue
            try:
                dauer = int(round(float(z.get("duration"))))
            except (TypeError, ValueError):
                dauer = None
            out.append({"id": zid, "name": _clean(str(z.get("name") or "")) or f"Zone {zid + 1}",
                        "duration": dauer, "logic": bool(z.get("setByLogic"))})
        return sorted(out, key=lambda z: z["id"])

    def _irr_current(self, c: dict) -> int | None:
        """currentZone als Zahl: id der laufenden Zone oder IRR_ALLE_AKTIV;
        None, wenn keine laeuft (IRR_AUS) oder der Wert fehlt."""
        try:
            cur = int(float(self._state(c, "currentZone")))
        except (TypeError, ValueError):
            return None
        return None if cur == IRR_AUS else cur

    def _irr_running(self, c: dict) -> bool:
        """Bewaesserung laeuft: State active (neuere Firmware) oder laut
        Strukturdoku currentZone ungleich -1."""
        return bool(self._state(c, "active")) or self._irr_current(c) is not None

    def _irrigation_zone_name(self, c: dict) -> str:
        """Name der laufenden Zone (currentZone = id aus zones), 'Alle Zonen'
        bei IRR_ALLE_AKTIV, sonst leer."""
        cur = self._irr_current(c)
        if cur is None:
            return ""
        if cur == IRR_ALLE_AKTIV:
            return "Alle Zonen"
        for z in self._irr_zones(c):
            if z["id"] == cur:
                return z["name"]
        return f"Zone {cur + 1}"
