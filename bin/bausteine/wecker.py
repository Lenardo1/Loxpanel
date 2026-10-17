"""Bausteine der Visu, Familie Wecker (AlarmClock).

Kachel (@kachel) und Detailseite (@detail) je Typ, siehe bausteine/__init__.py.
Die Helfer (app._state, app._fmt_num ...) sind Mixins: die allgemeinen in helfer.py,
die dieser Familie in der Klasse unten; App erbt sie ueber bausteine.BausteinHelfer."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from urllib.parse import quote, unquote

from bausteine import detail, kachel
from bausteine.gemeinsam import _clean, DAUER_SCHRITT, PROZENT_SCHRITT, STAT_WEEKDAYS

log = logging.getLogger("loxpanel.webvisu")   # derselbe Logger wie der Server: die Methoden gehoeren zu App


@kachel("AlarmClock")
def kachel_wecker(app, uuid, c, it):
    ringing = bool(app._state(c, "isAlarmActive"))
    nxt = app._alarm_next_text(c)
    has = bool(app._alarm_entries(uuid))
    rn = _clean((app.rooms.get(c.get("room")) or {}).get("name"))
    if rn:
        it["room"] = rn   # Raum auf der Kachel zeigen (mehrere Wecker unterscheidbar)
    it.update(icon="alarm", on=ringing, tone=("crit" if ringing else None),
              nav={"view": "control", "id": uuid},
              sublabel=("Weckt!" if ringing else
                        "Ausgeschaltet" if app._alarm_aus(c) else
                        (nxt or ("Keine Weckzeit aktiv" if has else "Kein Wecker"))))


@detail("AlarmClock")
def detail_wecker(app, uuid, c, route):
    ua = c.get("uuidAction")
    ringing = bool(app._state(c, "isAlarmActive"))
    nxt = app._alarm_next_text(c)
    entries = app._alarm_entries(uuid)
    room = _clean((app.rooms.get(c.get("room")) or {}).get("name"))
    # Layout wie IRR/Klima (anchor:bottom): Statuszeile mittig oben (Raum
    # als Unterzeile), die Weckzeit-Eintraege unten angedockt. Je Eintrag
    # ein Schalter (ein/aus), Antippen oeffnet ihn zum Bearbeiten. Klingelt
    # der Wecker, gibt es Schlummer (Loxone 'snooze') und Wecker aus
    # ('dismiss' -> isAlarmActive 0 -> Weckton stoppt).
    stat = {"k": "astat", "text": ("Weckt jetzt" if ringing else
                                   "Ausgeschaltet" if app._alarm_aus(c) else
                                   (nxt or "Keine Weckzeit aktiv"))}
    if ringing:
        stat["tone"] = "crit"
    if room:
        stat["sub"] = room
    blocks = [{"k": "hero", "icon": "alarm"}, stat, {"k": "alarmlist", "entries": entries}]
    if ringing:
        blocks.append({"k": "row", "cells": [
            {"label": "Schlummer", "cmd": {"uuid": ua, "cmd": "snooze"}},
            {"label": "Wecker aus", "cmd": {"uuid": ua, "cmd": "dismiss"}}]})
    if (app._alarm_raw(c) or ({}, False))[1]:
        blocks.append({"k": "row", "cells": [
            {"label": "Neue Weckzeit", "nav": {"view": "alarmentry", "id": uuid, "entry": ""}},
            {"label": "Einstellungen", "nav": {"view": "alarmsettings", "id": uuid}}]})
    return {"t": "view", "title": _clean(c.get("name")), "route": route,
            "anchor": "bottom", "blocks": blocks}


# Wecker (AlarmClock) laut Strukturdoku: die Betriebsarten 3..9 sind die
# Wochentage Montag bis Sonntag, 0..2 (Feiertag, Urlaub, freie Tage) haben
# Vorrang vor ihnen. Grenzen aus der Loxone-Wissensdatenbank (Baustein
# Wecker): Schlummerdauer 60..1800 s, Lautstaerke des Wecksounds 5..100 %.
# Wecksound, Lautstaerke und Helligkeit gibt es nur mit Touch Nightlight;
# deviceState meldet es (0 keins, 1 offline, 2 online).
WECKER_WOCHENTAGE = range(3, 10)

WECKER_VORRANG = range(0, 3)

WECKER_SCHLUMMER_MIN, WECKER_SCHLUMMER_MAX = 60, 1800

WECKER_LAUT_MIN = 5

NIGHTLIGHT_DA = (1, 2)


class WeckerHelfer:
    """Helfer der Familie Wecker fuer Kachel, Detailseite und Unterseiten. Mixin: App erbt sie ueber
    bausteine.BausteinHelfer, gerufen wird ueber self bzw. app."""

    def _alarm_next_text(self, c: dict) -> str:
        """Naechste Weckzeit eines Weckers (AlarmClock) als Text. Loxone liefert
        `nextEntryTime` in Sekunden seit dem 1.1.2009 (lokale Wanduhr); 0/leer =
        kein aktiver Eintrag. Ausgabe z.B. 'Heute 06:30', 'Morgen 06:30',
        'Mo 06:30' oder '24.12. 06:30'."""
        v = self._state(c, "nextEntryTime")
        try:
            ts = int(float(v))
        except (TypeError, ValueError):
            return ""
        if ts <= 0:
            return ""
        # Wert als Wanduhr behandeln (TZ-neutral): 2009-Basis + Sekunden.
        dt = datetime(2009, 1, 1) + timedelta(seconds=ts)
        today = datetime.now().date()
        d = (dt.date() - today).days
        hm = dt.strftime("%H:%M")
        if d == 0:
            return "Heute " + hm
        if d == 1:
            return "Morgen " + hm
        if 2 <= d <= 6:
            return ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"][dt.weekday()] + " " + hm
        return dt.strftime("%d.%m.") + " " + hm

    def _alarm_aus(self, c: dict) -> bool:
        """Wecker per Logik ausgeschaltet (State isEnabled 0). Fehlt der State
        (aeltere Firmware), gilt er als eingeschaltet."""
        v = self._state(c, "isEnabled")
        return v is not None and not v

    def _alarm_raw(self, c: dict) -> tuple[dict[str, dict], bool] | None:
        """State entryList eines Weckers -> ({entryID: Eintrag}, IDs echt).
        Laut Strukturdoku ein JSON-Objekt {entryID: {name, isActive, alarmTime
        (Sekunden ab Mitternacht), modes, nightLight, daily}}, ggf.
        prozentkodiert. Kommt eine Liste, steht die Position an Stelle der ID;
        dann wird nur angezeigt, nicht geschrieben (IDs echt = False), sonst
        traefe ein Befehl womoeglich einen anderen Eintrag. None, wenn der
        State fehlt oder nicht lesbar ist (dann wird der Rohwert geloggt)."""
        raw = self._state(c, "entryList")
        if raw in (None, ""):
            return None
        data = raw
        if isinstance(raw, str):
            txt = unquote(raw).strip()
            try:
                data = json.loads(txt)
            except ValueError:
                log.warning("Wecker entryList nicht als JSON parsebar: %r", txt[:200])
                return None
        if isinstance(data, dict):
            return {str(k): e for k, e in data.items() if isinstance(e, dict)}, True
        if isinstance(data, list):
            return {str(i): e for i, e in enumerate(data) if isinstance(e, dict)}, False
        return None

    @staticmethod
    def _alarm_secs(e: dict) -> int:
        try:
            return int(float(e.get("alarmTime") or 0)) % 86400
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _alarm_modes(e: dict) -> list[int]:
        out = []
        for m in e.get("modes") or []:
            try:
                out.append(int(m))
            except (TypeError, ValueError):
                continue
        return out

    def _alarm_put(self, eid: str, e: dict, aktiv: bool) -> str:
        """Befehl entryList/put/{entryID}/{name}/{alarmTime}/{isActive}/{modes|daily}
        laut Strukturdoku: schreibt den Eintrag mit neuem Aktiv-Stand zurueck.
        Name URL-kodiert, Zeit in Sekunden ab Mitternacht, zuletzt bei
        Eintraegen mit nightLight daily (0/1), sonst die Betriebsarten mit Komma."""
        letzter = (("1" if e.get("daily") else "0") if e.get("nightLight") is True
                   else ",".join(str(m) for m in self._alarm_modes(e)))
        return (f"entryList/put/{quote(eid, safe='')}/{quote(str(e.get('name') or ''), safe='')}"
                f"/{self._alarm_secs(e)}/{1 if aktiv else 0}/{letzter}")

    def _alarm_entries(self, uuid: str) -> list[dict]:
        """Weckzeit-Eintraege eines Weckers fuer die Liste der Detailseite:
        [{id, name, hm, active, repeat, cmd, nav}], aktive zuerst, dann nach
        Uhrzeit. cmd schaltet den Eintrag ein bzw. aus, nav oeffnet ihn zum
        Bearbeiten."""
        c = self.controls.get(uuid, {})
        roh, echt = self._alarm_raw(c) or ({}, False)
        ua = c.get("uuidAction")
        out = []
        for eid, e in roh.items():
            secs = self._alarm_secs(e)
            it = {"id": eid, "name": _clean(str(e.get("name") or "")) or "Weckzeit",
                  "hm": "%02d:%02d" % (secs // 3600, secs % 3600 // 60),
                  "active": bool(e.get("isActive")), "repeat": self._alarm_repeat(e)}
            if echt:
                it["cmd"] = {"uuid": ua, "cmd": self._alarm_put(eid, e, not e.get("isActive"))}
                it["nav"] = {"view": "alarmentry", "id": uuid, "entry": eid}
            out.append(it)
        out.sort(key=lambda x: (not x["active"], x["hm"]))
        return out

    def _alarm_repeat(self, e: dict) -> str:
        """Wiederholungs-Text eines Weckzeit-Eintrags. Eintraege mit nightLight
        kennen nur daily (taeglich oder einmalig). Sonst die Betriebsarten: 3..9
        sind laut Strukturdoku Montag bis Sonntag (Mo/Di/...), alle sieben
        heissen "Täglich"; andere (Feiertag, Urlaub ...) mit ihrem Namen aus den
        operatingModes der Anlage."""
        if e.get("nightLight") is True:
            return "Täglich" if e.get("daily") else "Einmalig"
        if e.get("daily"):
            return "Täglich"
        modes = self._alarm_modes(e)
        tage = [m for m in WECKER_WOCHENTAGE if m in modes]
        andere = [m for m in modes if m not in WECKER_WOCHENTAGE]
        namen = (["Täglich"] if len(tage) == len(WECKER_WOCHENTAGE)
                 else [STAT_WEEKDAYS[m - WECKER_WOCHENTAGE[0]] for m in tage])
        namen += [self._op_mode_name(m) for m in andere]
        return " ".join(namen)

    def _op_mode_name(self, m: int) -> str:
        """Name einer Betriebsart aus der Struktur, sonst "Betriebsart <Nr>"."""
        return _clean(str(self.op_modes.get(str(m)) or "")) or f"Betriebsart {m}"

    def _alarm_mode_items(self, modes: list[int]) -> list[dict]:
        """Waehlbare Tage einer Weckzeit: Mo..So (Betriebsarten 3..9), dazu die
        Vorrang-Betriebsarten 0..2, soweit die Anlage sie kennt (damit klingelt
        der Wecker auch an Feiertagen oder im Urlaub), und jede weitere, die der
        Eintrag schon hat. -> [{v, label, on}]"""
        gesetzt = set(modes)
        items = [{"v": m, "label": STAT_WEEKDAYS[i], "on": m in gesetzt}
                 for i, m in enumerate(WECKER_WOCHENTAGE)]
        weitere = [m for m in WECKER_VORRANG if str(m) in self.op_modes]
        weitere += sorted(m for m in gesetzt if m not in WECKER_WOCHENTAGE and m not in weitere)
        items += [{"v": m, "label": self._op_mode_name(m), "on": m in gesetzt} for m in weitere]
        return items

    def _view_alarm_entry(self, uuid: str, entry) -> dict:
        """Weckzeit bearbeiten oder (entry leer) anlegen: Name, Uhrzeit und
        Tage. Die Visu setzt die drei in die Befehlsvorlage von "Speichern"
        ein (form, entryList/put wie _alarm_put); der Aktiv-Stand bleibt, eine
        neue Weckzeit ist aktiv und beginnt mit der aktuellen Uhrzeit.
        Loeschen per entryList/delete/{entryID}, mit Rueckfrage."""
        c = self.controls.get(uuid or "", {})
        route = {"view": "alarmentry", "id": uuid, "entry": entry}
        roh = self._alarm_raw(c) if c.get("type") == "AlarmClock" else None
        if not roh or not roh[1]:
            return self._gone_view(route, _clean(c.get("name")), "Diese Weckzeit gibt es nicht mehr.")
        eintraege = roh[0]
        neu = entry in (None, "")
        if neu:
            n = 0
            while str(n) in eintraege:
                n += 1
            eid, jetzt = str(n), datetime.now()
            e = {"name": "Weckzeit", "isActive": True, "alarmTime": jetzt.hour * 3600 + jetzt.minute * 60}
        else:
            eid = str(entry)
            e = eintraege.get(eid)
            if e is None:
                return self._gone_view(route, _clean(c.get("name")), "Diese Weckzeit gibt es nicht mehr.")
        ua = c.get("uuidAction")
        name = _clean(str(e.get("name") or "")) or "Weckzeit"
        if e.get("nightLight") is True:
            tage = {"k": "chips", "name": "tage", "items": [
                {"v": 0, "label": "Einmalig", "on": not e.get("daily")},
                {"v": 1, "label": "Täglich", "on": bool(e.get("daily"))}]}
        else:
            tage = {"k": "chips", "name": "tage", "multi": True,
                    "items": self._alarm_mode_items(self._alarm_modes(e))}
        aktiv = 1 if e.get("isActive") else 0
        cells = []
        if not neu:
            cells.append({"label": "Löschen", "confirm": "Wirklich löschen?", "back": True,
                          "cmd": {"uuid": ua, "cmd": f"entryList/delete/{quote(eid, safe='')}"}})
        cells.append({"label": "Speichern", "back": True, "form": {
            "uuid": ua, "tmpl": f"entryList/put/{quote(eid, safe='')}/{{name}}/{{zeit}}/{aktiv}/{{tage}}"}})
        return {"t": "view", "title": name, "route": route, "blocks": [
            {"k": "title", "text": "Neue Weckzeit" if neu else name, "sub": _clean(c.get("name"))},
            {"k": "field", "name": "name", "label": "Name", "value": str(e.get("name") or name)},
            {"k": "timepick", "name": "zeit", "value": self._alarm_secs(e)},
            tage,
            {"k": "row", "cells": cells},
        ]}

    def _view_alarm_settings(self, uuid: str) -> dict:
        """Einstellungen eines Weckers laut Strukturdoku, jeweils fest, wenn
        die Logik sie vorgibt (details.*Connected): Schlummerdauer
        (setSnoozeDuration), maximale Weckdauer (setRingDuration), Vorweckzeit
        (setPrepDuration). Mit Touch Nightlight dazu Wecksound
        (setWakeAlarmSound, Auswahl aus details.wakeAlarmSounds), lauter
        werdend (setWakeAlarmSlopingOn), Signalton (setBeepOn), Lautstaerke
        (setWakeAlarmVolume) und Helligkeit (setBrightnessInactive/Active)."""
        c = self.controls.get(uuid or "", {})
        route = {"view": "alarmsettings", "id": uuid}
        if c.get("type") != "AlarmClock":
            return self._gone_view(route, "", "Diesen Wecker gibt es nicht mehr.")
        ua = c.get("uuidAction")
        det = c.get("details") or {}
        blocks = [{"k": "title", "text": "Einstellungen", "sub": _clean(c.get("name"))}]

        def stufe(label, wert, befehl, schritt, minimum, maximum, fmt, fest):
            if not isinstance(wert, (int, float)) or isinstance(wert, bool):
                return
            b = {"k": "stepper", "label": label, "value": int(wert), "fmt": fmt}
            if fest:
                b["sub"] = "von der Logik vorgegeben"
            else:
                b.update(step=schritt, min=minimum, cmd={"uuid": ua, "tmpl": befehl + "/{v}"})
                if maximum is not None:
                    b["max"] = maximum
            blocks.append(b)

        stufe("Schlummerdauer", self._state(c, "snoozeDuration"), "setSnoozeDuration", DAUER_SCHRITT,
              WECKER_SCHLUMMER_MIN, WECKER_SCHLUMMER_MAX, "dauer", bool(det.get("snoozeDurationConnected")))
        stufe("Maximale Weckdauer", self._state(c, "ringDuration"), "setRingDuration", DAUER_SCHRITT,
              DAUER_SCHRITT, None, "dauer", False)
        stufe("Vorweckzeit", self._state(c, "prepareDuration"), "setPrepDuration", DAUER_SCHRITT,
              0, None, "dauer", False)
        if self._state(c, "deviceState") in NIGHTLIGHT_DA:
            geraet = self._json_state(c, "deviceSettings")
            geraet = geraet if isinstance(geraet, dict) else {}
            ton = self._json_state(c, "wakeAlarmSoundSettings")
            ton = ton if isinstance(ton, dict) else {}
            blocks.append({"k": "head", "text": "Touch Nightlight"})
            sounds = [x for x in det.get("wakeAlarmSounds") or [] if isinstance(x, dict) and x.get("id") is not None]
            jetzt = next((x for x in sounds if str(x.get("id")) == str(ton.get("sound"))), None)
            name = _clean(str((jetzt or {}).get("name") or ""))
            zellen = []
            if sounds and not det.get("wakeAlarmSoundConnected"):
                zellen.append({"label": "Wecksound" + (": " + name if name else ""), "menu": [
                    {"label": _clean(str(x.get("name") or "")) or str(x.get("id")), "on": x is jetzt,
                     "cmd": {"uuid": ua, "cmd": f"setWakeAlarmSound/{x.get('id')}"}} for x in sounds]})
            elif name:
                blocks.append({"k": "status", "text": "Wecksound: " + name})
            if "isSloping" in ton and not det.get("wakeAlarmSlopingConnected"):
                an = bool(ton.get("isSloping"))
                zellen.append({"label": "Lauter werdend", "on": an,
                               "cmd": {"uuid": ua, "cmd": f"setWakeAlarmSlopingOn/{0 if an else 1}"}})
            if "beepUsed" in geraet:
                an = bool(geraet.get("beepUsed"))
                zellen.append({"label": "Signalton", "on": an,
                               "cmd": {"uuid": ua, "cmd": f"setBeepOn/{0 if an else 1}"}})
            if zellen:
                blocks.append({"k": "row", "wrap": True, "cells": zellen})
            stufe("Lautstärke", ton.get("volume"), "setWakeAlarmVolume", PROZENT_SCHRITT, WECKER_LAUT_MIN, 100,
                  "prozent", bool(det.get("wakeAlarmVolumeConnected")))
            stufe("Helligkeit inaktiv", geraet.get("brightInactive"), "setBrightnessInactive", PROZENT_SCHRITT,
                  0, 100, "prozent", bool(det.get("brightInactiveConnected")))
            stufe("Helligkeit aktiv", geraet.get("brightActive"), "setBrightnessActive", PROZENT_SCHRITT,
                  0, 100, "prozent", bool(det.get("brightActiveConnected")))
        return {"t": "view", "title": "Einstellungen", "route": route, "blocks": blocks}
