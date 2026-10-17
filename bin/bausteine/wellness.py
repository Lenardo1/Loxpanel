"""Bausteine der Visu, Familie Wellness und Kueche: Sauna, Grillthermometer.

Kachel (@kachel) und Detailseite (@detail) je Typ, siehe bausteine/__init__.py.
Die Helfer (app._state, app._fmt_num ...) sind Mixins: die allgemeinen in helfer.py,
die dieser Familie in der Klasse unten; App erbt sie ueber bausteine.BausteinHelfer."""
from __future__ import annotations

from urllib.parse import quote

from bausteine import detail, kachel
from bausteine.gemeinsam import (
    _clean, DAUER_SCHRITT, _dauer_text, PROZENT_SCHRITT, SAUNA_MODES, SAUNA_STOERUNG, SAUNA_WASSER)

# Grillthermometer (SteakThermo, Strukturdoku): Fuehler von links (gelb) nach
# rechts (gruen), deviceState 0 laeuft (dann ohne Hinweis), powerMode 1 = am Netz
STEAK_FARBEN = ("Gelb", "Grün")
STEAK_GERAET = {1: "Gerät offline", 2: "Gerät ausgeschaltet", 3: "Gerätefehler", 4: "Gerät schläft"}
STEAK_NETZ = 1
STEAK_ZIEL_SCHRITT = 1
# Schalter am Geraet: (State, Befehl, Text, details-Schluessel "Logik haengt dran")
STEAK_SCHALTER = (("touchProtection", "setTouchProtection", "Tastensperre", "isTouchProtectConnected"),
                  ("displayAlwaysOnBat", "setDisplayAlwaysOnBat", "Display an (Akku)", None),
                  ("displayAlwaysOnDc", "setDisplayAlwaysOnDc", "Display an (Netz)", None))


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
    if app._state(c, "drying"):
        rows.append({"k": "status", "text": "Trocknung läuft"})
    timer = app._endlich(c, "timer") or 0
    if timer > 0:
        rows.append({"k": "status", "text": f"Sanduhr noch {_dauer_text(timer)}"})
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
    # Sollfeuchte (nur mit Verdampfer, humidity/<wert>)
    ht = app._endlich(c, "humidityTarget")
    if det.get("hasVaporizer") and ht is not None:
        ctrl.append({"k": "stepper", "label": "Feuchte", "value": ht, "fmt": "prozent",
                     "step": PROZENT_SCHRITT, "min": 0, "max": 100,
                     "cmd": {"uuid": ua, "tmpl": "humidity/{v}"}})
    # Betriebsart per Aufklapper (mode/<n>), aktive Art ist markiert.
    ctrl.append({"k": "row", "cells": [
        {"label": "Ein", "on": act, "cmd": {"uuid": ua, "cmd": "on"}},
        {"label": "Aus", "on": not act, "cmd": {"uuid": ua, "cmd": "off"}},
        {"label": "Programm", "menu": [
            {"label": nm, "on": isinstance(md, (int, float)) and int(md) == n,
             "cmd": {"uuid": ua, "cmd": f"mode/{n}"}}
            for n, nm in SAUNA_MODES.items()]},
    ]})
    # Luefter (fanon geht laut Strukturdoku nur bei aktiver Sauna) und die
    # Sanduhr (starttimer zaehlt von timerTotal herunter)
    extra = []
    luefter = bool(app._state(c, "fan"))
    if act or luefter:
        extra.append({"label": "Lüftung", "on": luefter,
                      "cmd": {"uuid": ua, "cmd": "fanoff" if luefter else "fanon"}})
    gesamt = app._endlich(c, "timerTotal") or 0
    if gesamt > 0 and timer <= 0:
        extra.append({"label": f"Sanduhr {_dauer_text(gesamt)}", "cmd": {"uuid": ua, "cmd": "starttimer"}})
    if extra:
        ctrl.append({"k": "row", "cells": extra})
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
    """Touch & Grill (Strukturdoku SteakThermo): je Fuehler Temperatur und
    Ziel (setSensor/{index}/{ziel}/{name}), der Timer (setTimerDuration,
    startTimer, stopTimer), Alarme quittieren (quitAlarm), Geraetezustand und
    Akku."""
    ua = c.get("uuidAction")
    act = bool(app._state(c, "isActive"))
    temps = app._steak_temps(c)
    fuehler = app._steak_fuehler(c)
    blocks = [{"k": "hero", "icon": "thermo"},
              {"k": "big", "text": (f"{app._fmt_num(temps[0][1], '%.0f')} °C" if temps
                                    else ("Aktiv" if act else "Aus"))}]
    geraet = STEAK_GERAET.get(int(app._endlich(c, "deviceState") or 0))
    if geraet:
        blocks.append({"k": "status", "text": geraet})
    alarm = (app._text(c, "activeAlarmText")
             or next((a.get("text") for a in app._steak_alarme(c) if a.get("ringing")), ""))
    if alarm:
        blocks.append({"k": "status", "text": _clean(alarm)})
    if any(app._state(c, n) for n in ("yellowAlarmActive", "greenAlarmActive", "timerAlarmActive")):
        blocks.append({"k": "row", "cells": [{"label": "Alarm quittieren", "cmd": {"uuid": ua, "cmd": "quitAlarm"}}]})
    for i, f in enumerate(fuehler):
        ist = temps[i][1] if i < len(temps) else None
        if f["connected"] is False:
            blocks.append({"k": "status", "text": f"{f['name']}: nicht eingesteckt"})
            continue
        if ist is not None:
            blocks.append({"k": "status", "text": f"{f['name']}: {app._fmt_num(ist, '%.0f')} °C"})
        if f["target"] is not None:
            blocks.append({"k": "stepper", "label": f"Ziel {f['name']}", "value": f["target"], "unit": "°C",
                           "step": STEAK_ZIEL_SCHRITT, "min": 0,
                           "cmd": {"uuid": ua, "tmpl": f"setSensor/{i}/{{v}}/{quote(f['name'], safe='')}"}})
    timer = app._json_state(c, "timerInfo")
    if isinstance(timer, dict) and timer.get("duration") is not None:
        laeuft = bool(timer.get("active"))
        rest = app._endlich(c, "timerRemaining") or 0
        blocks.append({"k": "head", "text": "Timer" + (f" · noch {_dauer_text(rest)}" if laeuft else "")})
        if not laeuft:
            blocks.append({"k": "stepper", "label": "Dauer", "value": timer.get("duration"), "fmt": "dauer",
                           "step": DAUER_SCHRITT, "min": DAUER_SCHRITT,
                           "cmd": {"uuid": ua, "tmpl": "setTimerDuration/{v}"}})
        blocks.append({"k": "row", "cells": [
            {"label": "Timer stoppen" if laeuft else "Timer starten",
             "cmd": {"uuid": ua, "cmd": "stopTimer" if laeuft else "startTimer"}}]})
    bat = app._endlich(c, "batteryStateOfCharge")
    if bat is not None and app._endlich(c, "powerMode") != STEAK_NETZ:
        blocks.append({"k": "status", "text": f"Akku {app._fmt_num(bat, '%.0f')} %"})
    blocks += app._steak_geraet(c)
    return {"t": "view", "title": _clean(c.get("name")), "route": route, "blocks": blocks}


class WellnessHelfer:
    """Helfer der Familie Wellness fuer Kachel, Detailseite und Unterseiten. Mixin: App erbt sie
    ueber bausteine.BausteinHelfer, gerufen wird ueber self bzw. app."""

    def _steak_fuehler(self, c: dict) -> list[dict]:
        """Fuehler des Grillthermometers aus sensorInfo (Strukturdoku: Liste
        [{name, connected, target}], Index 0 links/gelb, 1 rechts/gruen) ->
        [{name, connected (None wenn unbekannt), target}]. Ohne sensorInfo die
        Ziele aus targetYellow/targetGreen."""
        data = self._json_state(c, "sensorInfo")
        if isinstance(data, list) and data:
            out = []
            for i, e in enumerate(data):
                e = e if isinstance(e, dict) else {}
                try:
                    ziel = float(e.get("target"))
                except (TypeError, ValueError):
                    ziel = None
                out.append({"name": _clean(e.get("name")) or STEAK_FARBEN[i % len(STEAK_FARBEN)],
                            "connected": e.get("connected") if isinstance(e.get("connected"), bool) else None,
                            "target": ziel})
            return out
        return [{"name": farbe, "connected": None, "target": self._endlich(c, state)}
                for farbe, state in zip(STEAK_FARBEN, ("targetYellow", "targetGreen"))
                if state in (c.get("states") or {})]

    def _steak_geraet(self, c: dict) -> list[dict]:
        """Einstellungen am Touch & Grill (Strukturdoku SteakThermo):
        Display-Helligkeit (setDisplayBrightness, ab 10.3), Tastensperre
        (setTouchProtection) und Display immer an im Akku- bzw. Netzbetrieb
        (setDisplayAlwaysOnBat, setDisplayAlwaysOnDc). Haengt Logik am
        Eingang (details.isBrightnessConnected, isTouchProtectConnected), nur
        Anzeige. Nur, was die Anlage als State liefert."""
        det, ua, st = c.get("details") or {}, c.get("uuidAction"), c.get("states") or {}
        out, zellen = [], []
        hell = self._endlich(c, "displayBrightness")
        if hell is not None:
            b = {"k": "stepper", "label": "Display-Helligkeit", "value": hell, "fmt": "prozent"}
            if det.get("isBrightnessConnected"):
                b["sub"] = "von der Logik vorgegeben"
            else:
                b.update(step=PROZENT_SCHRITT, min=0, max=100, cmd={"uuid": ua, "tmpl": "setDisplayBrightness/{v}"})
            out.append(b)
        for state, befehl, text, logik in STEAK_SCHALTER:
            if state not in st:
                continue
            an = bool(self._state(c, state))
            z = {"label": text, "on": an}
            if not (logik and det.get(logik)):
                z["cmd"] = {"uuid": ua, "cmd": f"{befehl}/{0 if an else 1}"}
            zellen.append(z)
        if zellen:
            out += [{"k": "head", "text": "Gerät"}, {"k": "row", "wrap": True, "cells": zellen}]
        return out

    def _steak_alarme(self, c: dict) -> list[dict]:
        """Alarme der Fuehler (sensorAlarms, Liste [{text, time, ringing}])."""
        data = self._json_state(c, "sensorAlarms")
        return [a for a in data if isinstance(a, dict)] if isinstance(data, list) else []

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
