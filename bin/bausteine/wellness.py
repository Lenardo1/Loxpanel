"""Bausteine der Visu, Familie Wellness und Kueche: Sauna, Grillthermometer.

Kachel (@kachel) und Detailseite (@detail) je Typ, siehe bausteine/__init__.py.
Die Helfer (app._state, app._fmt_num ...) sind Mixins: die allgemeinen in helfer.py,
die dieser Familie in der Klasse unten; App erbt sie ueber bausteine.BausteinHelfer."""
from __future__ import annotations

from bausteine import detail, kachel
from bausteine.gemeinsam import SAUNA_MODES, SAUNA_STOERUNG, SAUNA_WASSER, _clean


@kachel("Sauna")
def kachel_sauna(app, uuid, c, it):
    act = bool(app._state(c, "active"))
    ta = app._state(c, "tempActual")
    zustand = "Ein" if act else "Aus"
    ist = f" · {app._fmt_num(ta, '%.0f')} °C" if ta is not None else ""
    rest = ""
    if act:
        tt = app._state(c, "tempTarget")
        if tt is not None:
            rest += f" → {app._fmt_num(tt, '%.0f')} °C"
        md = app._state(c, "mode")
        if isinstance(md, (int, float)) and int(md) in SAUNA_MODES:
            rest += f" · {SAUNA_MODES[int(md)]}"
    sub = zustand + ist + rest
    if ta is not None:
        # Neuer Kachel-Aufbau: Ist-Temperatur gross an Stelle des Symbols
        it["big"] = f"{app._fmt_num(ta, '%.1f')}°"
        it["bigSub"] = zustand + rest
    if (c.get("details") or {}).get("hasVaporizer") and app._state(c, "lessWater"):
        it["tone"] = "warn"
        it["hinweis"] = {"text": SAUNA_WASSER}
    if app._state(c, "error") or app._state(c, "saunaError"):
        it["tone"] = "crit"
        it["hinweis"] = {"text": SAUNA_STOERUNG}
    it.update(icon="thermo", on=act, nav={"view": "control", "id": uuid}, sublabel=sub)


@kachel("SteakThermo")
def kachel_grillthermometer(app, uuid, c, it):
    act = bool(app._state(c, "isActive"))
    temps = app._steak_temps(c)
    sub = " · ".join(f"{app._fmt_num(v, '%.0f')} °C" for _, v in temps[:2]) if temps else ("Aktiv" if act else "Aus")
    if app._state(c, "greenAlarmActive") or app._state(c, "yellowAlarmActive") or app._state(c, "timerAlarmActive"):
        it["tone"] = "good"
    it.update(icon="thermo", on=act, nav={"view": "control", "id": uuid}, sublabel=sub)


@detail("Sauna")
def detail_sauna(app, uuid, c, route):
    ua = c.get("uuidAction")
    det = c.get("details") or {}
    act = bool(app._state(c, "active"))
    ta = app._state(c, "tempActual")
    err = app._state(c, "error") or app._state(c, "saunaError")
    sbits = ["Ein" if act else "Aus"]
    md = app._state(c, "mode")
    if isinstance(md, (int, float)) and int(md) in SAUNA_MODES:
        sbits.append(SAUNA_MODES[int(md)])
    tt = app._state(c, "tempTarget")
    if tt is not None:
        sbits.append(f"Soll {app._fmt_num(tt, '%.0f')} °C")
    tb = app._state(c, "tempBench")
    if tb is not None:
        sbits.append(f"Bank {app._fmt_num(tb, '%.0f')} °C")
    hum = app._state(c, "humidityActual")
    if hum is not None and det.get("hasVaporizer"):
        fbit = f"Feuchte {app._fmt_num(hum, '%.0f')} %"
        ht = app._state(c, "humidityTarget")
        if isinstance(ht, (int, float)) and ht > 0:
            fbit += f" → {app._fmt_num(ht, '%.0f')} %"
        sbits.append(fbit)
    rows = []
    if det.get("hasDoorSensor") and app._state(c, "doorClosed") == 0:
        rows.append({"k": "status", "text": "Tür offen"})
    if app._state(c, "ready"):
        rows.append({"k": "status", "text": "Betriebstemperatur erreicht"})
    if app._state(c, "fan"):
        rows.append({"k": "status", "text": "Lüftung läuft"})
    if app._state(c, "drying"):
        rows.append({"k": "status", "text": "Trocknung läuft"})
    if app._state(c, "timer"):
        rows.append({"k": "status", "text": "Timer läuft"})
    if det.get("hasVaporizer") and app._state(c, "lessWater"):
        rows.append({"k": "status", "text": SAUNA_WASSER})
    if err:
        rows.append({"k": "status", "text": SAUNA_STOERUNG})
    # Steuerung. Befehle an der Anlage verifiziert (bin/sauna_probe.py):
    # Solltemperatur temp/<wert>, Betriebsart mode/<0..6>, Ein/Aus on/off.
    # Solltemperatur relativ (der Miniserver begrenzt auf die Sauna-Grenzen);
    # die Buttons rechnen bei jedem Rendering vom aktuellen Sollwert weiter.
    ctrl = []
    if tt is not None:
        base = int(round(tt))
        ctrl.append({"k": "row", "cells": [
            {"label": "−5°", "cmd": {"uuid": ua, "cmd": f"temp/{base - 5}"}},
            {"label": "−1°", "cmd": {"uuid": ua, "cmd": f"temp/{base - 1}"}},
            {"label": "+1°", "cmd": {"uuid": ua, "cmd": f"temp/{base + 1}"}},
            {"label": "+5°", "cmd": {"uuid": ua, "cmd": f"temp/{base + 5}"}},
        ]})
    # Betriebsart per Aufklapper (mode/<n>), aktive Art ist markiert.
    ctrl.append({"k": "row", "cells": [
        {"label": "Ein", "on": act, "cmd": {"uuid": ua, "cmd": "on"}},
        {"label": "Aus", "on": not act, "cmd": {"uuid": ua, "cmd": "off"}},
        {"label": "Programm", "menu": [
            {"label": nm, "on": isinstance(md, (int, float)) and int(md) == n,
             "cmd": {"uuid": ua, "cmd": f"mode/{n}"}}
            for n, nm in SAUNA_MODES.items()]},
    ]})
    blocks = [
        {"k": "hero", "icon": "thermo"},
        {"k": "big", "text": (f"{app._fmt_num(ta, '%.0f')} °C" if ta is not None else "–"),
         **({"tone": "crit"} if err else {})},
        {"k": "status", "text": " · ".join(sbits)},
        *rows,
        *ctrl,
    ]
    return {"t": "view", "title": _clean(c.get("name")), "route": route,
            "anchor": "bottom", "blocks": blocks}


@detail("SteakThermo")
def detail_grillthermometer(app, uuid, c, route):
    act = bool(app._state(c, "isActive"))
    temps = app._steak_temps(c)
    rows = [{"k": "status", "text": f"{label}: {app._fmt_num(v, '%.0f')} °C"} for label, v in temps]
    for nm, lbl in (("targetGreen", "Ziel grün"), ("targetYellow", "Ziel gelb")):
        v = app._state(c, nm)
        if v is not None:
            rows.append({"k": "status", "text": f"{lbl}: {app._fmt_num(v, '%.0f')} °C"})
    al = app._text(c, "activeAlarmText")
    if al:
        rows.append({"k": "status", "text": al})
    if app._state(c, "timerAlarmActive") or app._state(c, "timerRemaining"):
        rows.append({"k": "status", "text": "Timer läuft"})
    bat = app._state(c, "batteryStateOfCharge")
    if bat is not None:
        rows.append({"k": "status", "text": f"Akku {app._fmt_num(bat, '%.0f')} %"})
    big = (f"{app._fmt_num(temps[0][1], '%.0f')} °C" if temps else ("Aktiv" if act else "Aus"))
    return {"t": "view", "title": _clean(c.get("name")), "route": route, "blocks": [
        {"k": "hero", "icon": "thermo"},
        {"k": "big", "text": big},
        {"k": "status", "text": "Grillthermometer" + ("" if act else " · aus")},
        *rows,
    ]}


class WellnessHelfer:
    """Helfer der Familie Wellness fuer Kachel, Detailseite und Unterseiten. Mixin: App erbt sie
    ueber bausteine.BausteinHelfer, gerufen wird ueber self bzw. app."""

    def _steak_temps(self, c: dict) -> list[tuple[str, float]]:
        """Fuehler-Temperaturen des Grillthermometers aus currentTemperatures
        (Liste von Zahlen oder Objekten mit name/value)."""
        data = self._json_state(c, "currentTemperatures")
        out = []
        for label, e in self._named_items(data):
            v = e.get("value", e.get("temperature", e.get("temp")))
            try:
                out.append((label if not label.isdigit() else f"Fühler {label}", float(v)))
            except (TypeError, ValueError):
                continue
        return out
