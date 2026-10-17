"""Bausteine der Visu, Familie Tuersprechstellen: Intercom und IntercomV2.

Kachel (@kachel) und Detailseite (@detail) je Typ, siehe bausteine/__init__.py.
Die Helfer (app._state, app._fmt_num ...) sind Mixins: die allgemeinen in helfer.py,
die dieser Familie in der Klasse unten; App erbt sie ueber bausteine.BausteinHelfer."""
from __future__ import annotations

import logging
import re
from datetime import date, datetime
from urllib.parse import quote, unquote

from bausteine import detail, kachel
from bausteine.gemeinsam import INTERCOM_TYPES, _clean, STAT_WEEKDAYS

log = logging.getLogger("loxpanel.webvisu")   # derselbe Logger wie der Server: die Methoden gehoeren zu App


@kachel(*INTERCOM_TYPES)
def kachel_tuersprechstelle(app, uuid, c, it):
    ring = bool(app._state(c, "bell"))
    # v2: Geraetezustand und Stumm sind Zustaende, keine Beschreibung
    sub = "Es klingelt" if ring else (app._intercom_zustand(c) or
                                      ("Stummgeschaltet" if app._state(c, "muted") else ""))
    it.update(icon="cam", on=ring, sublabel=sub or "Türsprechanlage",
              nav={"view": "control", "id": uuid})
    if not sub:
        it["subInfo"] = True
    if ring:
        it["tone"] = "crit"


@detail(*INTERCOM_TYPES)
def detail_tuersprechstelle(app, uuid, c, route):
    t = c.get("type")
    ua = c.get("uuidAction")
    subs = c.get("subControls") or {}
    cells = [{"label": _clean(sc.get("name")),
              "cmd": {"uuid": sc.get("uuidAction"), "cmd": "pulse"}}
             for sc in subs.values()]
    blocks = []
    if app._state(c, "bell"):
        blocks.append({"k": "astat", "text": "Es klingelt", "tone": "crit"})
    zustand = app._intercom_zustand(c)
    if zustand:
        blocks.append({"k": "status", "id": "zustand", "text": zustand})
    blocks.append(app._intercom_video_block(uuid, c))
    if cells:
        blocks.append({"k": "row", "cells": cells})
    # Die native Bruecke fuehrt Audio; Browser/Fully filtern diesen Block.
    # deviceType ist keine Generation: auch eine Gen-1 kann 0 melden.
    if t == "Intercom":
        blocks.append({"k": "intercom-talk", "uuid": uuid, "nativeOnly": True})
    # Laut Strukturdoku: 'answer' stellt die Klingel ab; lastBellEvents
    # sind die Klingeln, auf die niemand reagiert hat. Eigene Zeile
    # hinter den Ausgaengen - die Kamera-Pane zeigt sie nicht
    # (intercom_blocks).
    extra = []
    if app._state(c, "bell"):
        extra.append({"label": "Klingel abstellen", "cmd": {"uuid": ua, "cmd": "answer"}})
    n = len(app._bell_events(c))
    if n:
        extra.append({"label": f"{n} verpasste Klingel" + ("" if n == 1 else "n"),
                      "nav": {"view": "bells", "id": uuid}})
    if extra:
        blocks.append({"k": "row", "id": "klingel", "cells": extra})
    # Nur v2 (Strukturdoku 17.0, IntercomV2): Antworten spielt die Intercom
    # an der Tuer ab (playTts/{idx}); muted ist der Ausgang Qb des
    # Bausteins, mute/{0/1} schaltet ihn stumm bzw. wieder laut.
    antworten = [{"label": a, "cmd": {"uuid": ua, "cmd": f"playTts/{i}"}}
                 for i, a in app._intercom_antworten(c)] if t == "IntercomV2" else []
    if antworten:
        blocks += [{"k": "head", "id": "antworten", "text": "Antwort abspielen"},
                   {"k": "row", "id": "antworten", "wrap": True, "cells": antworten}]
    if t == "IntercomV2" and "muted" in (c.get("states") or {}):
        stumm = bool(app._state(c, "muted"))
        blocks.append({"k": "row", "id": "stumm", "cells": [
            {"label": "Stumm", "on": stumm, "cmd": {"uuid": ua, "cmd": "mute/0" if stumm else "mute/1"}}]})
    return {"t": "view", "title": _clean(c.get("name")), "route": route, "blocks": blocks}


# IntercomV2 deviceState: 1 = StateOk; 0 = StateUnknown sagt nichts Sicheres
# und bleibt ohne Hinweis.
INTERCOM_V2_ZUSTAND = {2: "Startet neu", 3: "Startet"}

# Zeitstempel einer Klingel (lastBellEvents, camimage): JJJJMMTTHHMMSS
_BELL_TS = re.compile(r"\d{14}")

KEIN_VIDEO = "Kein Video eingerichtet"


class IntercomHelfer:
    """Helfer der Familie Intercom fuer Kachel, Detailseite und Unterseiten. Mixin: App erbt sie
    ueber bausteine.BausteinHelfer, gerufen wird ueber self bzw. app."""

    def _bell_events(self, c: dict) -> list[str]:
        """Zeitstempel der verpassten Klingeln, neueste zuerst. Laut
        Strukturdoku State lastBellEvents: JJJJMMTTHHMMSS, mit | getrennt."""
        txt = unquote(str(self._state(c, "lastBellEvents") or ""))
        return sorted({t.strip() for t in txt.split("|") if _BELL_TS.fullmatch(t.strip())}, reverse=True)

    def _intercom_video_block(self, uuid: str, c: dict) -> dict:
        """Video der Intercom-Seite: eine in LoxPanel eingetragene Kamera oder
        die des Miniservers (intercom_video). Solange offen ist, ob er eine
        nennt, steht das Video schon da: /mjpeg fragt ihn, und die Seite zeigt
        danach Bild oder Grund."""
        ent = self.intercom_cfg.get(uuid)
        eigene = ent.get("url") if isinstance(ent, dict) else ent
        cam = self.ms_video.get(uuid)
        if (isinstance(eigene, str) and eigene.strip()) or \
                (c.get("securedDetails") and (cam is None or cam.get("url"))):
            return {"k": "video", "src": f"/mjpeg?id={quote(uuid)}"}
        return {"k": "status", "text": (cam or {}).get("grund") or KEIN_VIDEO}

    def _intercom_zustand(self, c: dict) -> str:
        """Hinweis zum Geraetezustand einer IntercomV2 (deviceState, Strukturdoku
        17.0) wie "Startet neu"; leer, wenn sie bereit ist, ohne State und bei v1."""
        if c.get("type") != "IntercomV2":
            return ""
        try:
            return INTERCOM_V2_ZUSTAND.get(int(float(self._state(c, "deviceState"))), "")
        except (TypeError, ValueError):
            return ""

    def _intercom_antworten(self, c: dict) -> list[tuple[int, str]]:
        """Antworten einer IntercomV2 als (Index, Text). Laut Strukturdoku 17.0
        ist der State answers eine Liste, playTts/{idx} spielt die mit dem Index
        an der Tuer ab, setAnswers/{answer0}/{answer1}/... setzt sie als Texte.
        Der Index bleibt der in der Liste, auch wenn ein Eintrag leer ist."""
        liste = self._json_state(c, "answers")
        if not isinstance(liste, list):
            return []
        return [(i, a.strip()) for i, a in enumerate(liste) if isinstance(a, str) and a.strip()]

    @staticmethod
    def _bell_text(ts: str, heute: date | None = None) -> str:
        """Zeitpunkt einer Klingel: 'Heute 07:49', 'Gestern 07:49', 'Mo 07:49'
        (die letzte Woche), sonst mit Datum ('01.10. 07:49', aus einem anderen
        Jahr '01.10.2025 07:49'). Wanduhr des Miniservers, wie geliefert."""
        try:
            dt = datetime.strptime(ts, "%Y%m%d%H%M%S")
        except ValueError:
            return ts
        heute = heute or datetime.now().date()
        tage = (heute - dt.date()).days
        hm = dt.strftime("%H:%M")
        if tage == 0:
            return "Heute " + hm
        if tage == 1:
            return "Gestern " + hm
        if 2 <= tage <= 6:
            return STAT_WEEKDAYS[dt.weekday()] + " " + hm
        return dt.strftime("%d.%m. " if dt.year == heute.year else "%d.%m.%Y ") + hm

    def _view_bells(self, uuid: str) -> dict:
        """Verpasste Klingeln einer Tuersprechstelle, neueste zuerst. Mit
        details.lastBellEventImages speichert der Miniserver ein Bild je
        Klingel; die Visu holt es ueber /bellimg (camimage)."""
        c = self.controls.get(uuid or "", {})
        route = {"view": "bells", "id": uuid}
        if c.get("type") not in INTERCOM_TYPES:
            return self._gone_view(route, "", "Diese Türsprechstelle gibt es nicht mehr.")
        evs = self._bell_events(c)
        blocks = [{"k": "title", "text": "Verpasste Klingeln", "sub": _clean(c.get("name"))}]
        if not evs:
            blocks.append({"k": "status", "text": "Keine verpassten Klingeln"})
        elif (c.get("details") or {}).get("lastBellEventImages"):
            blocks.append({"k": "gallery", "items": [
                {"src": f"/bellimg?id={quote(uuid, safe='')}&ts={ts}", "label": self._bell_text(ts)}
                for ts in evs]})
        else:
            blocks += [{"k": "status", "text": self._bell_text(ts)} for ts in evs]
        return {"t": "view", "title": "Verpasste Klingeln", "route": route, "blocks": blocks}
