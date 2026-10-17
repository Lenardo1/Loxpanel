"""Bausteine der Visu, Familie Klima: Raumregelung V2 und V1, Klimaanlage, Klimaregler, Lueftung.

Kachel (@kachel) und Detailseite (@detail) je Typ, siehe bausteine/__init__.py.
Die Helfer (app._state, app._fmt_num ...) sind Mixins: die allgemeinen in helfer.py,
die dieser Familie in der Klasse unten; App erbt sie ueber bausteine.BausteinHelfer."""
from __future__ import annotations

from adapters import json_aus_text
from bausteine import detail, kachel
from bausteine.gemeinsam import (
    _clean, IRC1_BETRIEBSARTEN, IRC1_ECO, IRC1_KOMFORT_HEIZEN, IRC1_KOMFORT_KUEHLEN,
    IRC1_KUEHL_MODI, IRC1_MANUELL, IRC1_MANUELL_MODI, IRC1_NUR_HEIZEN, IRC1_NUR_KUEHLEN, IRC1_TEMPS,
    IRC1_TIMER_S, IRC2_BETRIEBSARTEN, IRC2_MANUELL)

# Raumregelung V2 (Strukturdoku Intelligent Room Controller v2): die
# einstellbaren Temperaturen mit State, Befehl und Bit in
# details.connectedInputs (1 = niedrigstes Bit; gesetzt = von der Logik
# vorgegeben); faehigkeit = noetiges Bit in possibleCapabilities (4 =
# Beschattung moeglich). Die Toleranz liegt laut Doku zwischen 0,5 und 3,0.
IRC2_SCHRITT = 0.5
IRC2_EINSTELLUNGEN = (
    {"state": "comfortTemperature", "befehl": "setComfortTemperature", "bit": 1,
     "label": "Komfort Heizen", "einzeln": "Komforttemperatur"},
    {"state": "comfortTemperatureCool", "befehl": "setComfortTemperatureCool", "bit": 2, "label": "Komfort Kühlen"},
    {"state": "comfortTolerance", "befehl": "setComfortTolerance", "bit": 4, "label": "Komfort-Toleranz (±)",
     "min": 0.5, "max": 3.0},
    {"state": "absentMinOffset", "befehl": "setAbsentMinTemperature", "bit": 5, "label": "Eco nach unten",
     "einzeln": "Eco-Abweichung (±)"},
    {"state": "absentMaxOffset", "befehl": "setAbsentMaxTemperature", "bit": 6, "label": "Eco nach oben"},
    {"state": "shadingHeatTemp", "befehl": "setshadingtemperatureheat", "bit": 8, "label": "Beschatten ab (Heizen)",
     "faehigkeit": 4},
    {"state": "shadingCoolTemp", "befehl": "setshadingtemperaturecool", "bit": 9, "label": "Beschatten ab (Kühlen)",
     "faehigkeit": 4},
)
# Mit einer einzigen Komforttemperatur entfallen die getrennten Werte
IRC2_NUR_GETRENNT = frozenset({"comfortTemperatureCool", "absentMaxOffset"})
# actualOutdoorTemp -1000 = keine Aussentemperatur
IRC2_KEINE_AUSSENTEMP = -1000


@kachel("IRoomControllerV2", "IRoomController")
def kachel_raumregelung(app, uuid, c, it):
    t = c.get("type")
    ta = app._state(c, "tempActual"); tt = app._state(c, "tempTarget")
    # heizt/kuehlt: V2 meldet es in prepareState, die alte Raumregelung
    # ueber ihre Ventile (siehe _irc1)
    prep = app._state(c, "prepareState") if t == "IRoomControllerV2" else app._irc1(c)["prep"]
    fenster = app._state(c, "openWindow")
    bits = app._irc_activity(prep, fenster)
    if fenster:
        # Hinweis der Hausseite: dringend, solange der Raum dabei
        # heizt oder kuehlt
        taetig = app._irc_activity(prep, None)
        it["hinweis"] = {"stufe": "dringend" if taetig else "warnung", "text": "Fenster offen",
                         "symbol": "window", "zusatz": " · ".join(taetig)}
    sub = (f"{app._fmt_num(ta, '%.1f')}° → {app._fmt_num(tt, '%.1f')}°"
           if ta is not None else "Heizung")
    if bits:
        sub += " · " + " · ".join(bits)
    it.update(icon="thermo", nav={"view": "control", "id": uuid},
              on=bool(prep), sublabel=sub)
    if ta is None:
        it["subInfo"] = True
    else:
        # Neuer Kachel-Aufbau: Ist-Temperatur gross an Stelle des
        # Symbols, die Zeile darunter nennt nur noch Soll und Taetigkeit.
        it["big"] = f"{app._fmt_num(ta, '%.1f')}°"
        it["bigSub"] = " · ".join(([f"Soll {app._fmt_num(tt, '%.1f')}°"] if tt is not None else []) + bits)


@kachel("Ventilation")
def kachel_lueftung(app, uuid, c, it):
    spd = app._state(c, "speed") or 0
    it.update(icon="fan", on=spd > 0, nav={"view": "control", "id": uuid},
              sublabel=(f"{round(spd)} %" if spd > 0 else "Aus"))


@kachel("AcControl")
def kachel_klimaanlage(app, uuid, c, it):
    modes = app._json_list_map(c, "operatingModes")
    tt = app._fmt_num(app._state(c, "targetTemperature"), "%.1f")
    ac_sub = " · ".join(x for x in (modes.get(int(app._state(c, "mode") or 0)),
                                    (tt + " °C" if tt else "")) if x)
    it.update(icon="thermo", on=(app._state(c, "status") or 0) != 0,
              nav={"view": "control", "id": uuid}, sublabel=(ac_sub or "Klima"))
    if not ac_sub:
        it["subInfo"] = True


@kachel("ClimateControllerUS")
def kachel_klimaregler(app, uuid, c, it):
    dh = app._state(c, "demandHeat") or 0
    dc = app._state(c, "demandCool") or 0
    it.update(icon="thermo", on=bool(dh or dc),
              nav={"view": "control", "id": uuid},
              sublabel=("Heizt" if dh else ("Kühlt" if dc else "Bereit")))


@detail("IRoomControllerV2")
def detail_raumregelung_v2(app, uuid, c, route):
    ua = c.get("uuidAction")
    ta = app._fmt_num(app._state(c, "tempActual"), "%.1f")
    tt = app._fmt_num(app._state(c, "tempTarget"), "%.1f")
    # -/+ verstellt die Komforttemperatur - nur mit bekanntem Wert (das
    # Soll kann gerade Eco sein, ein angenommener Wert verstellt die Regelung)
    try:
        comfort = float(app._state(c, "comfortTemperature"))
    except (TypeError, ValueError):
        comfort = None
    modes = app._irc_modes(c)
    am = app._state(c, "activeMode")
    try:
        am = int(am) if am is not None else None
    except (TypeError, ValueError):
        am = None
    art, manuell = app._irc_betriebsart(c)
    # Status: Soll-Temp + aktiver Modus + manuelle Betriebsart + heizt/kuehlt/Fenster
    sbits = []
    if am is not None and am in modes:
        sbits.append(modes[am])
    if manuell:
        sbits.append(manuell)
    sbits += app._irc_activity(app._state(c, "prepareState"),
                                app._state(c, "openWindow"))
    status = f"Soll {tt} °C" + (" · " + " · ".join(sbits) if sbits else "")
    blocks = [
        {"k": "big", "text": f"{ta} °C"},          # grosse Ist-Temp statt Icon
        {"k": "status", "text": status},
    ]
    reihe = [art] if art else []
    if comfort is not None:
        reihe = [{"label": "−", "cmd": {"uuid": ua, "cmd": f"setComfortTemperature/{comfort - 0.5:.1f}"}},
                 *reihe,
                 {"label": "+", "cmd": {"uuid": ua, "cmd": f"setComfortTemperature/{comfort + 0.5:.1f}"}}]
    if reihe:
        blocks.append({"k": "row", "cells": reihe})
    # Betriebsmodi in EINER Zeile: Temperatur-Modi (Eco/Komfort) als
    # 1-h-Override + Automatik (zurueck zur Zeitschaltung). Namen aus MS
    # (details.timerModes). Gebaeudeschutz wird ausgelassen (aufgeraeumt).
    if modes:
        cells = [{"label": nm, "on": (mid == am),
                  "cmd": {"uuid": ua, "cmd": f"override/{mid}"}}
                 for mid, nm in sorted(modes.items())
                 if "schutz" not in (nm or "").lower()]
        cells.append({"label": "Automatik",
                      "cmd": {"uuid": ua, "cmd": "stopOverride"}})
        blocks.append({"k": "row", "cells": cells})
    # Raumklima, soweit die Anlage es liefert (Strukturdoku: -1000 = keine
    # Aussentemperatur, co2 und humidityActual ab 15.1)
    klima = []
    aussen = app._endlich(c, "actualOutdoorTemp")
    if aussen is not None and aussen > IRC2_KEINE_AUSSENTEMP:
        klima.append(f"Außen {app._fmt_num(aussen, '%.1f')} °C")
    feuchte = app._endlich(c, "humidityActual")
    if feuchte is not None:
        klima.append(f"Feuchte {app._fmt_num(feuchte, '%.0f')} %")
    co2 = app._endlich(c, "co2")
    if co2 is not None:
        klima.append(f"CO₂ {app._fmt_num(co2, '%.0f')} ppm")
    if klima:
        blocks.insert(2, {"k": "status", "text": " · ".join(klima)})
    if app._irc2_einstellungen(c):
        blocks.append({"k": "row", "cells": [{"label": "Einstellungen", "nav": {"view": "ircset", "id": uuid}}]})
    return {"t": "view", "title": _clean(c.get("name")), "route": route,
            "anchor": "bottom", "blocks": blocks}


@detail("IRoomController")
def detail_raumregelung_v1(app, uuid, c, route):
    # Alte Raumregelung (v1), Befehle laut Loxone-Strukturdoku:
    # settemp/<Nr>/<Wert>, starttimer/<Nr>/<Sekunden>, stoptimer.
    ua = c.get("uuidAction")
    z = app._irc1(c)
    art, manuell = app._irc_betriebsart(c)
    ta = app._fmt_num(app._state(c, "tempActual"), "%.1f")
    tt = app._fmt_num(app._state(c, "tempTarget"), "%.1f")
    # manuell: die Betriebsart ("Manuell Heizen") statt der Temperatur "Manuell"
    sbits = [z["name"]] if z["name"] and not (manuell and z["ix"] == IRC1_MANUELL) else []
    if manuell:
        sbits.append(manuell)
    sbits += app._irc_activity(z["prep"], app._state(c, "openWindow"))
    status = f"Soll {tt} °C" + (" · " + " · ".join(sbits) if sbits else "")
    blocks = [
        {"k": "big", "text": f"{ta} °C"},
        {"k": "status", "text": status},
    ]
    # -/+ verstellt Komfort der Periode (manuell: die manuelle
    # Temperatur) - nur mit bekanntem, absolutem Wert. Dazwischen
    # die Betriebsart (mode/<Nr>).
    reihe = [art] if art else []
    if z["stell"] is not None:
        ix, v = z["stell_ix"], z["stell"]
        reihe = [{"label": "−", "cmd": {"uuid": ua, "cmd": f"settemp/{ix}/{v - 0.5:.1f}"}},
                 *reihe,
                 {"label": "+", "cmd": {"uuid": ua, "cmd": f"settemp/{ix}/{v + 0.5:.1f}"}}]
    if reihe:
        blocks.append({"k": "row", "cells": reihe})
    # Eco/Komfort fuer eine Stunde halten, Automatik beendet den Timer.
    blocks.append({"k": "row", "cells": [
        {"label": IRC1_TEMPS[IRC1_ECO], "on": z["ix"] == IRC1_ECO,
         "cmd": {"uuid": ua, "cmd": f"starttimer/{IRC1_ECO}/{IRC1_TIMER_S}"}},
        {"label": "Komfort", "on": z["ix"] == z["komfort_ix"],
         "cmd": {"uuid": ua, "cmd": f"starttimer/{z['komfort_ix']}/{IRC1_TIMER_S}"}},
        {"label": "Automatik", "cmd": {"uuid": ua, "cmd": "stoptimer"}},
    ]})
    return {"t": "view", "title": _clean(c.get("name")), "route": route,
            "anchor": "bottom", "blocks": blocks}


@detail("Ventilation")
def detail_lueftung(app, uuid, c, route):
    spd = app._state(c, "speed") or 0
    return app._big_view(uuid, "fan", (f"{round(spd)} %" if spd else "Aus"),
                          sub="Lüftung")


@detail("AcControl")
def detail_klimaanlage(app, uuid, c, route):
    ua = c.get("uuidAction")
    # An die IRR-Detailseite angeglichen: grosse Ist-Temp oben, Status-
    # zeile, dann 2 Bedienzeilen. Modus/Fan klappen ihre Auswahl inline
    # auf (viele Optionen passen nicht in eine feste Zeile).
    modes = app._json_list_map(c, "operatingModes")   # {id: name}
    fans = app._json_list_map(c, "fanspeeds")          # {id: name}
    on = (app._state(c, "status") or 0) != 0
    def _as_int(v, d=0):
        try:
            return int(float(v))
        except (TypeError, ValueError):
            return d
    cur_mode = _as_int(app._state(c, "mode"))
    cur_fan = _as_int(app._state(c, "fan"))
    tgt = app._state(c, "targetTemperature")
    ist = app._state(c, "temperature")
    try:
        cur_t = float(tgt)
    except (TypeError, ValueError):
        cur_t = 22.0
    try:
        lo = float(app._state(c, "minTemp"))
    except (TypeError, ValueError):
        lo = 5.0
    try:
        hi = float(app._state(c, "maxTemp"))
    except (TypeError, ValueError):
        hi = 40.0
    dn = max(lo, cur_t - 0.5); up = min(hi, cur_t + 0.5)
    # grosse Anzeige = Ist-Temp (wie IRR); Fallback Soll, wenn kein Ist
    try:
        ist_ok = ist is not None and float(ist) > -50
    except (TypeError, ValueError):
        ist_ok = False
    big = (app._fmt_num(ist, "%.1f") + " °C") if ist_ok else \
          ((app._fmt_num(tgt, "%.1f") + " °C") if tgt is not None else "–")
    sbits = []
    if tgt is not None:
        sbits.append(f"Soll {app._fmt_num(tgt, '%.1f')} °C")
    if cur_mode in modes:
        sbits.append(modes[cur_mode])
    sbits.append("Ein" if on else "Aus")
    status = " · ".join(x for x in sbits if x)
    # Zeile 2: Auto (Schnellzugriff Auto-Modus) + Modus/Fan-Aufklapper
    auto_id = next((mid for mid, nm in modes.items()
                    if (nm or "").strip().lower() == "auto"), None)
    row2 = []
    if auto_id is not None:
        row2.append({"label": modes[auto_id], "on": cur_mode == auto_id,
                     "cmd": {"uuid": ua, "cmd": f"setMode/{auto_id}"}})
    # Modus/Fan oeffnen ein Popup mit der Auswahl (statt Inline-Zeilen)
    if modes:
        row2.append({"label": "Modus", "menu": [
            {"label": nm, "on": mid == cur_mode, "cmd": {"uuid": ua, "cmd": f"setMode/{mid}"}}
            for mid, nm in sorted(modes.items())]})
    if fans:
        row2.append({"label": "Fan", "menu": [
            {"label": nm, "on": fid == cur_fan, "cmd": {"uuid": ua, "cmd": f"setFan/{fid}"}}
            for fid, nm in sorted(fans.items())]})
    blocks = [
        {"k": "big", "text": big},
        {"k": "status", "text": status},
        {"k": "row", "cells": [
            {"label": "−", "cmd": {"uuid": ua, "cmd": f"setTarget/{dn:.1f}"}},
            {"label": "Aus", "on": not on, "cmd": {"uuid": ua, "cmd": "off"}},
            {"label": "Ein", "on": on, "cmd": {"uuid": ua, "cmd": "on"}},
            {"label": "+", "cmd": {"uuid": ua, "cmd": f"setTarget/{up:.1f}"}},
        ]},
        {"k": "row", "cells": row2},
    ]
    return {"t": "view", "title": _clean(c.get("name")), "route": route,
            "anchor": "bottom", "blocks": blocks}


@detail("ClimateControllerUS")
def detail_klimaregler(app, uuid, c, route):
    dh = app._state(c, "demandHeat") or 0
    dc = app._state(c, "demandCool") or 0
    big = "Heizt" if dh else ("Kühlt" if dc else "Bereit")
    # verwaltete AC-Einheiten + wie viele gerade Bedarf anmelden
    roh = app._state(c, "controls")
    units = json_aus_text(roh)[1] if isinstance(roh, str) else None
    units = units if isinstance(units, list) else []
    active = sum(1 for u in units if isinstance(u, dict) and u.get("demand"))
    sbits = [f"{active}/{len(units)} Anlagen aktiv"] if units else []
    hum = app._state(c, "humidity") or 0
    if hum:
        sbits.append(f"Feuchte {app._fmt_num(hum, '%.0f')} %")
    out = app._state(c, "actualOutdoorTemp")
    try:
        if out is not None and float(out) > -100:
            sbits.append(f"Außen {app._fmt_num(out, '%.1f')} °C")
    except (TypeError, ValueError):
        pass
    return app._big_view(uuid, "thermo", big, " · ".join(sbits),
                          tone=("crit" if dc else None))


class KlimaHelfer:
    """Helfer der Familie Klima fuer Kachel, Detailseite und Unterseiten. Mixin: App erbt sie ueber
    bausteine.BausteinHelfer, gerufen wird ueber self bzw. app."""

    def _irc2_einstellungen(self, c: dict) -> list[dict]:
        """Einstellbare Temperaturen einer Raumregelung V2 (IRC2_EINSTELLUNGEN)
        als stepper, nur die, deren State die Anlage liefert. Gibt die Logik
        einen Wert vor (details.connectedInputs), steht er nur da. Mit einer
        einzigen Komforttemperatur (SingleComfortTemperature, ab 15.1) gilt
        comfortTemperature fuer Heizen und Kuehlen und absentMinOffset als
        Abweichung in Eco (±), die Werte fuer Kuehlen entfallen."""
        det = c.get("details") or {}
        try:
            gesperrt = int(det.get("connectedInputs") or 0)
        except (TypeError, ValueError):
            gesperrt = 0
        einzeln = bool(det.get("SingleComfortTemperature"))
        try:
            kann = int(det.get("possibleCapabilities"))
        except (TypeError, ValueError):
            kann = None
        ua = c.get("uuidAction")
        out = []
        for e in IRC2_EINSTELLUNGEN:
            if einzeln and e["state"] in IRC2_NUR_GETRENNT:
                continue
            if e.get("faehigkeit") and kann is not None and not kann & e["faehigkeit"]:
                continue
            wert = self._endlich(c, e["state"])
            if wert is None:
                continue
            label = e["einzeln"] if einzeln and e.get("einzeln") else e["label"]
            b = {"k": "stepper", "label": label, "value": wert, "unit": "°C"}
            if gesperrt & (1 << (e["bit"] - 1)):
                b["sub"] = "von der Logik vorgegeben"
            else:
                b.update(step=IRC2_SCHRITT, cmd={"uuid": ua, "tmpl": e["befehl"] + "/{v}"},
                         **{k: e[k] for k in ("min", "max") if k in e})
            out.append(b)
        return out

    def _view_irc_einstellungen(self, uuid: str) -> dict:
        """Unterseite Einstellungen einer Raumregelung V2 (Route view=ircset):
        die Temperaturen aus _irc2_einstellungen, dazu der Gebaeudeschutz
        (laut Strukturdoku V2 ohne Befehl, nur Anzeige)."""
        c = self.controls.get(uuid or "") or {}
        route = {"view": "ircset", "id": uuid}
        titel = f"{_clean(c.get('name'))} · Einstellungen"
        if c.get("type") != "IRoomControllerV2":
            return self._gone_view(route, titel, "Diesen Baustein gibt es nicht mehr.")
        blocks = [{"k": "title", "text": _clean(c.get("name")), "sub": "Einstellungen"},
                  *self._irc2_einstellungen(c)]
        frost, hitze = self._endlich(c, "frostProtectTemperature"), self._endlich(c, "heatProtectTemperature")
        if frost is not None or hitze is not None:
            teile = [f"{t} {self._fmt_num(v, '%.1f')} °C" for t, v in (("Frost", frost), ("Hitze", hitze))
                     if v is not None]
            blocks.append({"k": "status", "text": "Gebäudeschutz: " + " · ".join(teile)})
        return {"t": "view", "title": titel, "route": route, "blocks": blocks}

    def _irc_modes(self, c: dict) -> dict:
        """IRoomControllerV2: Temperatur-/Timer-Modi aus details.timerModes ->
        {id: Name} (z. B. 0=Eco, 1=Komfort, 2=Gebaeudeschutz)."""
        tm = (c.get("details") or {}).get("timerModes") or []
        return {int(m["id"]): _clean(m.get("name"))
                for m in tm if isinstance(m, dict) and m.get("id") is not None}

    @staticmethod
    def _irc_activity(prep, win) -> list:
        """Aktivitaets-Hinweise fuer die Raumregelung: heizt/kuehlt + Fenster."""
        bits = []
        try:
            p = float(prep)
        except (TypeError, ValueError):
            p = 0.0
        if p > 0:
            bits.append("heizt")
        elif p < 0:
            bits.append("kühlt")
        if win:
            bits.append("Fenster")
        return bits

    def _irc1(self, c: dict) -> dict:
        """Zustand der alten Raumregelung (IRoomController, v1):
          kuehlen   laeuft die Kuehlperiode (State mode, IRC1_KUEHL_MODI)
          ix/name   aktive Temperatur (currCoolTempIx bzw. currHeatTempIx)
          stell_ix  Temperatur, die -/+ verstellt: manuell die manuelle, sonst
                    Komfort der Periode
          stell     ihr aktueller Wert; None, wenn unbekannt oder relativ zu
                    Komfort (dann gibt es kein -/+, statt einen Wert zu raten)
          komfort_ix Komfort der Periode (fuer den Komfort-Knopf)
          prep      fuer _irc_activity: Ventil Heizen > 0 = 1, Kuehlen > 0 = -1"""
        def num(name):
            try:
                return float(self._state(c, name))
            except (TypeError, ValueError):
                return None

        mode = num("mode")
        mode = int(mode) if mode is not None else None
        kuehlen = mode in IRC1_KUEHL_MODI
        ix = num("currCoolTempIx" if kuehlen else "currHeatTempIx")
        ix = int(ix) if ix is not None else None
        komfort_ix = IRC1_KOMFORT_KUEHLEN if kuehlen else IRC1_KOMFORT_HEIZEN
        if mode in IRC1_MANUELL_MODI:
            stell_ix, stell = IRC1_MANUELL, num("tempTarget")
        else:
            stell_ix = komfort_ix
            stell = self._irc1_temp(c, komfort_ix) if self._irc1_absolut(c, komfort_ix) else None
        prep = 1 if (num("valveHeat") or 0) > 0 else (-1 if (num("valveCool") or 0) > 0 else 0)
        return {"kuehlen": kuehlen, "ix": ix, "name": IRC1_TEMPS.get(ix), "stell_ix": stell_ix,
                "stell": stell, "komfort_ix": komfort_ix, "prep": prep}

    def _irc_betriebsart(self, c: dict) -> tuple[dict | None, str | None]:
        """Aufklapper "Betriebsart" einer Raumregelung und der Name fuer die
        Statuszeile, wenn manuell geregelt wird (dann laeuft kein Zeitplan).
        V2: State operatingMode, setOperatingMode/<Nr>. Alt: State mode,
        mode/<Nr>; "Automatik, heizt/kuehlt gerade" (1/2) gilt als Automatik,
        details.restrictedToMode blendet Heizen bzw. Kuehlen aus.
        (None, None), wenn der Baustein den State nicht hat."""
        v2 = c.get("type") == "IRoomControllerV2"
        name = "operatingMode" if v2 else "mode"
        ua = c.get("uuidAction")
        if not ua or name not in (c.get("states") or {}):
            return None, None
        try:
            cur = int(float(self._state(c, name)))
        except (TypeError, ValueError):
            cur = None
        if v2:
            arten, befehl, manuell = IRC2_BETRIEBSARTEN, "setOperatingMode", IRC2_MANUELL
            markiert = cur
        else:
            nur = (c.get("details") or {}).get("restrictedToMode")
            weg = {IRC1_NUR_KUEHLEN: {3, 5}, IRC1_NUR_HEIZEN: {4, 6}}.get(nur, set())
            arten = {n: nm for n, nm in IRC1_BETRIEBSARTEN.items() if n not in weg}
            befehl, manuell = "mode", IRC1_MANUELL_MODI
            markiert = 0 if cur in (1, 2) else cur
        zelle = {"label": "Betriebsart", "menu": [
            {"label": nm, "on": n == markiert, "cmd": {"uuid": ua, "cmd": f"{befehl}/{n}"}}
            for n, nm in arten.items()]}
        return zelle, (arten.get(cur) if cur in manuell else None)

    def _irc1_temp(self, c: dict, ix: int):
        """Wert der Temperatur Nr. ix: der State "temperatures" ist bei der
        alten Raumregelung eine Liste mit einer UUID je Nummer."""
        lst = (c.get("states") or {}).get("temperatures")
        if not isinstance(lst, list) or not 0 <= ix < len(lst):
            return None
        try:
            return float(self.states.get(lst[ix]))
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _irc1_absolut(c: dict, ix: int) -> bool:
        """details.temperatures[ix].isAbsolute: True = fester Wert, False =
        haengt von Komfort ab. Nummern als Schluessel ("0".."6") oder Liste."""
        tt = (c.get("details") or {}).get("temperatures")
        if isinstance(tt, dict):
            e = tt.get(str(ix), tt.get(ix))
        elif isinstance(tt, list) and 0 <= ix < len(tt):
            e = tt[ix]
        else:
            e = None
        return bool(isinstance(e, dict) and e.get("isAbsolute"))
