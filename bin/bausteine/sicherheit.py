"""Bausteine der Visu, Familie Sicherheit und Melder: Alarmanlage, Rauchmelder, Praesenzmelder, Fensterueberwachung, Postkasten.

Kachel (@kachel) und Detailseite (@detail) je Typ, siehe bausteine/__init__.py.
Die Helfer (app._state, app._fmt_num ...) sind Mixins in helfer.py und den Familien, App erbt sie ueber bausteine.BausteinHelfer."""
from __future__ import annotations

import time
from datetime import datetime

from bausteine import detail, kachel
from bausteine.gemeinsam import _clean, DAUER_SCHRITT, _dauer_text, LOX_EPOCH_UTC

# Briefkasten (MailBox, Strukturdoku): so lange setzen die Tasten die
# Benachrichtigungen aus (disableNotifications/{Sekunden}); 0 hebt die Pause auf.
# disableEndTime zaehlt laut Strukturdoku Sekunden seit 1.1.2009 in UTC (LOX_EPOCH_UTC).
BRIEFKASTEN_PAUSEN = (3600, 4 * 3600, 24 * 3600)

# Rauchmelder (SmokeAlarm, Strukturdoku): Bits von availableAlarms (details)
# und alarmCause (State)
RAUCH_ARTEN = ((0x01, "Rauch"), (0x02, "Wasser"), (0x04, "Temperatur"), (0x08, "Fehlerlichtbogen"))
# State level: 1 Voralarm, 2 Hauptalarm
RAUCH_STUFEN = {1: "Voralarm", 2: "Hauptalarm"}
# Revisionsmodus: servicemode/0 aus, /1 ohne Ende (timeServiceMode meldet dann
# RAUCH_REVISION_ENDLOS), sonst Sekunden
RAUCH_REVISION_AUS, RAUCH_REVISION_DAUERHAFT, RAUCH_REVISION_ENDLOS = 0, 1, 99999
RAUCH_REVISION_DAUERN = (3600, 4 * 3600)
# Alarmstufen (State nextLevel bei Alarmanlage und Rauchmelder)
ALARM_STUFEN = {1: "Still", 2: "Akustisch", 3: "Optisch", 4: "Intern", 5: "Extern", 6: "Fernalarm"}
# Praesenzmelder: parameterConnections Bit 0 = Nachlaufzeit von der Logik
PRAESENZ_ZEIT_GESPERRT = 1


def _bits_text(maske, arten=RAUCH_ARTEN) -> str:
    """Bitmaske (availableAlarms, alarmCause) als Liste der Namen."""
    try:
        m = int(float(maske or 0))
    except (TypeError, ValueError):
        return ""
    return ", ".join(name for bit, name in arten if m & bit)


def _rauch_zustand(app, c: dict) -> tuple[str, str | None]:
    """(Text, Ton) eines Rauchmelders: Alarm mit Stufe und Ursache,
    Probealarm, Revisionsmodus oder alles ok."""
    lvl = int(app._endlich(c, "level") or 0)
    if lvl:
        ursache = _bits_text(app._state(c, "alarmCause"))
        return (RAUCH_STUFEN.get(lvl, "Alarm") + (f": {ursache}" if ursache else ""), "crit")
    if app._state(c, "testAlarm"):
        return "Probealarm", None
    if (app._endlich(c, "timeServiceMode") or 0) > 0:
        return "Revisionsmodus", None
    return "Alles ok", "good"


@kachel("SmokeAlarm")
def kachel_rauchmelder(app, uuid, c, it):
    text, ton = _rauch_zustand(app, c)
    it.update(icon="alarm", sublabel=text, tone=ton, nav={"view": "control", "id": uuid})


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
    it.update(icon="mail", on=(mail or pk), nav={"view": "control", "id": uuid}, sublabel=sub)
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
    """Rauchmelder (Strukturdoku SmokeAlarm): Zustand mit Ursache, im Alarm
    Sirene aus (mute) und Quittieren (confirm), Revisionsmodus
    (servicemode/{n}) und Probealarm (startDrill), beide mit Rueckfrage."""
    ua = c.get("uuidAction")
    text, ton = _rauch_zustand(app, c)
    blocks = [{"k": "hero", "icon": "alarm"}, {"k": "big", "text": text, **({"tone": ton} if ton else {})}]
    ueberwacht = _bits_text((c.get("details") or {}).get("availableAlarms"))
    if ueberwacht:
        blocks.append({"k": "status", "text": f"Überwacht: {ueberwacht}"})
    rest = app._endlich(c, "timeServiceMode") or 0
    if rest >= RAUCH_REVISION_ENDLOS:
        blocks.append({"k": "status", "text": "Revisionsmodus ohne Ende"})
    elif rest > 0:
        blocks.append({"k": "status", "text": f"Revisionsmodus noch {_dauer_text(rest)}"})
    if app._state(c, "areAlarmSignalsOff"):
        blocks.append({"k": "status", "text": "Alarmsignale aus"})
    # naechste Stufe: nextLevelDelay zaehlt bis nextLevelDelayTotal hoch
    stufe = ALARM_STUFEN.get(int(app._endlich(c, "nextLevel") or 0))
    gesamt, bisher = app._endlich(c, "nextLevelDelayTotal") or 0, app._endlich(c, "nextLevelDelay") or 0
    if int(app._endlich(c, "level") or 0) and stufe and gesamt > bisher:
        blocks.append({"k": "status", "text": f"Nächste Stufe ({stufe}) in {_dauer_text(gesamt - bisher)}"})
    if int(app._endlich(c, "level") or 0) or app._state(c, "testAlarm"):
        cells = [{"label": "Quittieren", "cmd": {"uuid": ua, "cmd": "confirm"}}]
        if app._state(c, "acousticAlarm"):
            cells.insert(0, {"label": "Sirene aus", "cmd": {"uuid": ua, "cmd": "mute"}})
        blocks.append({"k": "row", "cells": cells})
    blocks.append({"k": "head", "text": "Revisionsmodus"})
    if rest > 0:
        blocks.append({"k": "row", "cells": [
            {"label": "Beenden", "cmd": {"uuid": ua, "cmd": f"servicemode/{RAUCH_REVISION_AUS}"}}]})
    else:
        blocks.append({"k": "row", "cells": [
            *({"label": _dauer_text(sek), "confirm": "Melder aussetzen?",
               "cmd": {"uuid": ua, "cmd": f"servicemode/{sek}"}} for sek in RAUCH_REVISION_DAUERN),
            {"label": "Ohne Ende", "confirm": "Melder aussetzen?",
             "cmd": {"uuid": ua, "cmd": f"servicemode/{RAUCH_REVISION_DAUERHAFT}"}}]})
        blocks.append({"k": "row", "cells": [
            {"label": "Probealarm", "confirm": "Alarm auslösen?", "cmd": {"uuid": ua, "cmd": "startDrill"}}]})
    return {"t": "view", "title": _clean(c.get("name")), "route": route,
            "anchor": "bottom", "blocks": blocks}


@detail("PresenceDetector")
def detail_praesenzmelder(app, uuid, c, route):
    """Praesenzmelder (Strukturdoku PresenceDetector): anwesend seit
    (activeSince), gesperrt mit Grund (locked, infoText), die Nachlaufzeit
    (time, Befehl time/{Sekunden}, gesperrt mit parameterConnections Bit 0)
    und der Verlauf aus dem Tracker."""
    ua = c.get("uuidAction")
    on = bool(app._state(c, "active"))
    itxt = app._text(c, "infoText")
    gesperrt = bool(app._state(c, "locked"))
    big = itxt if (itxt and not gesperrt and itxt.lower() not in ("on", "off")) else \
        ("Anwesend" if on else "Abwesend")
    v = app._big_view(uuid, "info", big, tone="good" if on else None)
    blocks = v["blocks"]
    seit = app._endlich(c, "activeSince") or 0
    if on and seit > 0:
        blocks.append({"k": "status", "text": "seit " + _uhrzeit_text(datetime.fromtimestamp(LOX_EPOCH_UTC + seit))})
    if gesperrt:
        blocks.append({"k": "status", "text": "Gesperrt" + (f": {itxt}" if itxt else "")})
    zeit = app._endlich(c, "time")
    if zeit is not None:
        b = {"k": "stepper", "label": "Nachlaufzeit", "value": zeit, "fmt": "dauer"}
        try:
            logik = int((c.get("details") or {}).get("parameterConnections") or 0) & PRAESENZ_ZEIT_GESPERRT
        except (TypeError, ValueError):
            logik = 0
        if logik:
            b["sub"] = "von der Logik vorgegeben"
        else:
            b.update(step=DAUER_SCHRITT, min=0, cmd={"uuid": ua, "tmpl": "time/{v}"})
        blocks.append(b)
    if app._verlauf_sub(c)[1] is not None:
        blocks.append({"k": "row", "cells": [{"label": "Verlauf", "nav": {"view": "verlauf", "id": uuid}}]})
    v.update(route=route, anchor="bottom")
    return v


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
    ab = app._endlich(c, "armedAt") or 0
    if not armed and ab > time.time():        # verzoegert: armedAt ist ein Unix-Zeitstempel
        sub = f"Wird scharf um {datetime.fromtimestamp(ab).strftime('%H:%M:%S')}"
    stufe = ALARM_STUFEN.get(int(app._endlich(c, "nextLevel") or 0))
    na = app._endlich(c, "nextLevelAt") or 0       # Unix-Zeitstempel, 0 = keine
    if lvl and stufe and na > time.time():
        sub += f" · nächste Stufe ({stufe}) um {datetime.fromtimestamp(na).strftime('%H:%M:%S')}"
    blocks = [{"k": "hero", "icon": "alarm"}, big, {"k": "status", "text": sub},
              {"k": "row", "cells": cells}]
    # Bewegungsmelder (dismv/1 ein, dismv/0 aus; State disabledMove)
    if "disabledMove" in (c.get("states") or {}):
        bewegung = not app._state(c, "disabledMove")
        blocks.append({"k": "row", "cells": [
            {"label": "Bewegungsmelder", "on": bewegung,
             "cmd": {"uuid": ua, "cmd": f"dismv/{0 if bewegung else 1}"}}]})
    return {"t": "view", "title": _clean(c.get("name")), "route": route,
            "anchor": "bottom", "blocks": blocks}


def _pause_bis(app, c: dict) -> datetime | None:
    """Bis wann die Benachrichtigungen des Briefkastens pausiert sind (State
    disableEndTime, Ortszeit), None ohne laufende Pause."""
    try:
        ts = float(app._state(c, "disableEndTime") or 0)
    except (TypeError, ValueError):
        return None
    ende = LOX_EPOCH_UTC + ts
    return datetime.fromtimestamp(ende) if ts > 0 and ende > time.time() else None


def _uhrzeit_text(dt: datetime) -> str:
    """Zeitpunkt kurz: heute nur die Uhrzeit, morgen mit "morgen", sonst mit Datum."""
    tage = (dt.date() - datetime.now().date()).days
    if tage == 0:
        return dt.strftime("%H:%M")
    if tage == 1:
        return "morgen " + dt.strftime("%H:%M")
    return dt.strftime("%d.%m. %H:%M")


@detail("MailBox")
def detail_postkasten(app, uuid, c, route):
    """Briefkasten (Strukturdoku MailBox): was drin ist, Post bzw. Paket als
    entnommen bestaetigen (confirmMail, confirmPacket), die Benachrichtigungen
    pausieren (disableNotifications) und der Verlauf aus dem Unterbaustein
    Tracker."""
    ua = c.get("uuidAction")
    mail = bool(app._state(c, "mailReceived"))
    pk = bool(app._state(c, "packetReceived"))
    big = {"k": "big", "text": "Post und Paket" if (mail and pk) else
           ("Post da" if mail else ("Paket da" if pk else "Leer"))}
    if mail or pk:
        big["tone"] = "good"
    blocks = [{"k": "hero", "icon": "mail"}, big]
    bis = _pause_bis(app, c)
    if app._state(c, "notificationsDisabledInput"):
        blocks.append({"k": "status", "text": "Benachrichtigungen über die Logik ausgesetzt"})
    elif bis:
        blocks.append({"k": "status", "text": f"Benachrichtigungen pausiert bis {_uhrzeit_text(bis)}"})
    su, tracker = app._verlauf_sub(c)
    zeilen = app._tracker_lines(tracker) if tracker is not None else []
    if zeilen:
        ts, txt = app._split_ts(zeilen[0])
        blocks.append({"k": "status", "text": f"Zuletzt: {txt}" + (f" ({ts})" if ts else "")})
    entnommen = [{"label": text, "cmd": {"uuid": ua, "cmd": cmd}}
                 for da, text, cmd in ((mail, "Post entnommen", "confirmMail"),
                                       (pk, "Paket entnommen", "confirmPacket")) if da]
    if entnommen:
        blocks.append({"k": "row", "cells": entnommen})
    if bis:
        blocks += [{"k": "head", "text": "Benachrichtigungen"},
                   {"k": "row", "cells": [{"label": "Wieder an",
                                           "cmd": {"uuid": ua, "cmd": "disableNotifications/0"}}]}]
    else:
        blocks += [{"k": "head", "text": "Benachrichtigungen pausieren"},
                   {"k": "row", "cells": [{"label": _dauer_text(s),
                                           "cmd": {"uuid": ua, "cmd": f"disableNotifications/{s}"}}
                                          for s in BRIEFKASTEN_PAUSEN]}]
    if tracker is not None:
        blocks.append({"k": "row", "cells": [{"label": "Verlauf", "nav": {"view": "verlauf", "id": uuid}}]})
    return {"t": "view", "title": _clean(c.get("name")), "route": route,
            "anchor": "bottom", "blocks": blocks}
