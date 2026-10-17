"""Bausteine der Visu, Familie Audio: Audiozone (Gen 1) und Audiozone V2.

Kachel (@kachel) und Detailseite (@detail) je Typ, siehe bausteine/__init__.py.
Die Helfer (app._state, app._fmt_num ...) sind Mixins: die allgemeinen in helfer.py,
die dieser Familie in der Klasse unten; App erbt sie ueber bausteine.BausteinHelfer."""
from __future__ import annotations

import logging
from urllib.parse import quote

from bausteine import detail, kachel
from bausteine.gemeinsam import _clean

log = logging.getLogger("loxpanel.webvisu")   # derselbe Logger wie der Server: die Methoden gehoeren zu App


# Audio-Zone Gen. 2 (Strukturdoku AudioZoneV2): serverState/clientState
# 2 = online, sonst der Hinweis; details.disableFeature Bit 2 = Bluetooth an
# der Zone abgeschaltet, details.parameterConnections Bit 10 = Bluetooth von
# der Logik vorgegeben
ZONE_ONLINE = 2
ZONE_SERVER = {-5: "Audioserver startet neu", -2: "Audioserver nicht erreichbar", 0: "Audioserver offline",
               1: "Audioserver startet", None: "Audioserver nicht bereit"}
ZONE_CLIENT = {-5: "Lautsprecher startet neu", 0: "Lautsprecher offline", 1: "Lautsprecher startet",
               None: "Lautsprecher nicht bereit"}
ZONE_BT_ABGESCHALTET = 1 << 2
ZONE_BT_LOGIK = 1 << 9


@kachel("AudioZone")
def kachel_audiozone(app, uuid, c, it):
    playing = app._state(c, "playState") == 2
    ua = c.get("uuidAction")
    it.update(on=playing, sublabel=(app._song(c) or ("An" if playing else "Aus")),
              icon="music", nav={"view": "control", "id": uuid},
              controls=[
                  {"icon": "prev", "cmd": {"uuid": ua, "cmd": "queueminus"}},
                  {"icon": "pause" if playing else "play",
                   "cmd": {"uuid": ua, "cmd": "pause" if playing else "play"}},
                  {"icon": "next", "cmd": {"uuid": ua, "cmd": "queueplus"}},
              ])
    # Sender-Logo bzw. Cover: die breite Kachel zeigt es neben den Tasten
    cover = app._audio_cover(c)
    if cover:
        it["cover"] = cover


@kachel("AudioZoneV2")
def kachel_audiozone_v2(app, uuid, c, it):
    # Audioserver Gen 2: wird ueber den Miniserver gesteuert (play/pause/
    # prev/next/volume) — nicht ueber das Gen-1-Audio-Backend (kein playerid).
    playing = app._state(c, "playState") == 2
    song = app._song(c)
    sm = app._sonn_for(c)          # Sonn liefert Titel/Status, wo Loxone leer ist
    if sm:
        playing = playing or bool(sm.get("playing"))
        song = song or sm.get("title") or ""
    ua = c.get("uuidAction")
    it.update(on=playing, sublabel=(song or ("Spielt" if playing else "Aus")),
              icon="music", nav={"view": "control", "id": uuid},
              controls=[
                  {"icon": "prev", "cmd": {"uuid": ua, "cmd": "prev"}},
                  {"icon": "pause" if playing else "play",
                   "cmd": {"uuid": ua, "cmd": "pause" if playing else "play"}},
                  {"icon": "next", "cmd": {"uuid": ua, "cmd": "next"}},
              ])
    cover = app._audio_cover(c)
    if cover:
        it["cover"] = cover


@detail("AudioZone")
def detail_audiozone(app, uuid, c, route):
    ua = c.get("uuidAction")
    playing = app._state(c, "playState") == 2
    title = app._song(c) or "Radio"
    sub = app._text(c, "artist") or app._text(c, "album")
    vol = int(app._state(c, "volume") or 0)
    cover = app._audio_cover(c)
    blocks = [{"k": "cover", "src": cover}] if cover else []
    blocks += [{"k": "title", "text": title, "sub": sub}, *app._sender_bloecke(uuid)]
    blocks += [
        {"k": "row", "cells": [
            {"icon": "prev", "cmd": {"uuid": ua, "cmd": "queueminus"}},
            {"icon": "pause" if playing else "play", "big": True,
             "cmd": {"uuid": ua, "cmd": "pause" if playing else "play"}},
            {"icon": "next", "cmd": {"uuid": ua, "cmd": "queueplus"}},
        ]},
        {"k": "slider", "icon": "vol", "value": vol, "min": 0, "max": 100,
         "cmd": {"uuid": ua, "tmpl": "volume/{v}"}},
    ]
    # Die Musikauswahl (alle Favoriten umbrechend) bleibt ueber die drei Punkte
    # erreichbar; angefordert werden die Favoriten beim Oeffnen (prime_favs).
    blocks.append({"k": "more", "route": {"view": "sources", "id": uuid}})
    # Bedienleiste (Transport + Lautstaerke) unten andocken; Cover/Titel
    # oben zentriert. Ohne laufende Musik rutscht so nichts nach oben.
    return {"t": "view", "title": _clean(c.get("name")), "route": route,
            "anchor": "bottom", "blocks": blocks}


@detail("AudioZoneV2")
def detail_audiozone_v2(app, uuid, c, route):
    ua = c.get("uuidAction")
    playing = app._state(c, "playState") == 2
    title = app._song(c)
    sub = app._text(c, "artist") or app._text(c, "album")
    vol = int(app._state(c, "volume") or 0)
    # Sonn/Audioserver4Home reicht Track-Metadaten NICHT ueber das
    # Loxone-Protokoll durch -> per Namensabgleich aus der Sonn-API
    # ergaenzen (nur wo Loxone leer ist). Das Bild: _audio_cover().
    sm = app._sonn_for(c)
    if sm:
        playing = playing or bool(sm.get("playing"))
        title = title or sm.get("title") or ""
        sub = sub or sm.get("artist") or sm.get("album") or ""
        if not vol and sm.get("volume") is not None:
            try:
                vol = int(sm.get("volume"))
            except (TypeError, ValueError):
                pass
    cover = app._audio_cover(c)
    if not title:
        title = "Spielt" if playing else "Aus"
    blocks = [{"k": "cover", "src": cover} if cover else {"k": "hero", "icon": "music"}]
    blocks += [{"k": "title", "text": title, "sub": sub},
               *({"k": "status", "text": t} for t in app._zone_hinweise(c)),
               *app._sender_bloecke(uuid)]
    blocks += [
        {"k": "row", "cells": [
            {"icon": "prev", "cmd": {"uuid": ua, "cmd": "prev"}},
            {"icon": "pause" if playing else "play", "big": True,
             "cmd": {"uuid": ua, "cmd": "pause" if playing else "play"}},
            {"icon": "next", "cmd": {"uuid": ua, "cmd": "next"}},
        ]},
        {"k": "slider", "icon": "vol", "value": vol, "min": 0, "max": 100,
         "cmd": {"uuid": ua, "tmpl": "volume/{v}"}},
    ]
    # Bluetooth (bluetooth/1|0, ab 15.0) und Durchsage (tts, Unterseite)
    extra = [{"label": "Durchsage", "nav": {"view": "durchsage", "id": uuid}}]
    bt = app._zone_bluetooth(c)
    if bt:
        extra.insert(0, bt)
    blocks.append({"k": "row", "cells": extra})
    # 3-Punkte -> Musikauswahl (Sonn via API, sonst Loxone-roomfav)
    blocks.append({"k": "more", "route": {"view": "sources", "id": uuid}})
    return {"t": "view", "title": _clean(c.get("name")), "route": route,
            "anchor": "bottom", "blocks": blocks}


class AudioHelfer:
    """Helfer der Familie Audio fuer Kachel, Detailseite und Unterseiten, dazu die Bloecke des
    Spielers (Pane und Hausuebersicht). Mixin: App erbt sie ueber bausteine.BausteinHelfer,
    gerufen wird ueber self bzw. app."""

    def _song(self, control: dict) -> str:
        """songName, aber rohe Stream-URLs (Radio) ausblenden."""
        s = self._text(control, "songName")
        return "" if s.startswith(("http://", "https://")) else s

    def _zonen_favoriten(self, uuid: str) -> tuple[list, bool]:
        """Favoriten einer Audio-Zone fuer die Musikauswahl und den Spieler der
        Hausseite: ([{label, cmd, cover}], ob sie vom Audioserver-Kanal kommen).

        Zuerst aus dem Audioserver-Event-Kanal (Port 7091) - fuer Gen1
        (Musikserver) UND Gen2 (Audioserver/Sonn). Der Loxone-sourceList-State
        ist bei vielen Setups leer, dies ist der zuverlaessige Weg. Der
        Abspiel-Index (`play`) beruecksichtigt, dass Musikserver per `slot` und
        Sonn per Item-`id` adressiert (siehe AudioEventClient._apply_favs).
        Nur wenn der Kanal die Favoriten auch liefern darf: ein gekoppelter
        Audioserver ohne geglueckte Anmeldung (oder unklare Kopplung) schickt
        keine (dieselbe Bedingung wie beim Anfordern in prime_favs) -> dann
        die des Miniservers (_audio_favs)."""
        c = self.controls.get(uuid, {})
        ua = c.get("uuidAction")

        def cover(url):
            return ("/cover?u=" + quote(url, safe="")) if url else ""
        cl, pid = self._audio_client_for(c) if c.get("type") in ("AudioZone", "AudioZoneV2") else (None, None)
        if cl is not None and pid is not None and (cl.paired is False or cl.authed):
            return ([{"label": f["name"], "cmd": {"uuid": ua, "cmd": f"roomfav/play/{f.get('play', f['slot'])}"},
                      "cover": cover(f["cover"])}
                     for f in cl.favs.get(pid, []) if f.get("slot") is not None], True)
        return ([{"label": f["name"], "cmd": {"uuid": ua, "cmd": f"roomfav/play/{f['slot']}"},
                  "cover": cover(f["cover"])} for f in self._audio_favs(c)], False)

    def _zone_hinweise(self, c: dict) -> list[str]:
        """Was eine Gen-2-Zone am Spielen hindert (Strukturdoku AudioZoneV2):
        Audioserver nicht online (serverState), Lautsprecher nicht online
        (clientState), gesperrt (isLocked, Reset-Eingang). Nur, wenn die
        Anlage den State liefert."""
        out = []
        for state, texte in (("serverState", ZONE_SERVER), ("clientState", ZONE_CLIENT)):
            v = self._endlich(c, state)
            if v is not None and int(v) != ZONE_ONLINE:
                out.append(texte.get(int(v), texte[None]))
        if self._state(c, "isLocked"):
            out.append("Zone gesperrt")
        return out

    def _zone_bluetooth(self, c: dict) -> dict | None:
        """Zelle Bluetooth an/aus einer Gen-2-Zone (State bluetooth, Befehl
        bluetooth/1|0); nur Anzeige, wenn die Logik den Parameter vorgibt
        (details.parameterConnections Bit 10), keine, wenn Bluetooth an der
        Zone abgeschaltet ist (details.disableFeature Bit 2) oder der State
        fehlt."""
        if "bluetooth" not in (c.get("states") or {}):
            return None
        det = c.get("details") or {}
        try:
            aus = int(det.get("disableFeature") or 0) & ZONE_BT_ABGESCHALTET
            logik = int(det.get("parameterConnections") or 0) & ZONE_BT_LOGIK
        except (TypeError, ValueError):
            aus, logik = 0, 0
        if aus:
            return None
        an = bool(self._state(c, "bluetooth"))
        zelle = {"label": "Bluetooth", "on": an}
        if not logik:
            zelle["cmd"] = {"uuid": c.get("uuidAction"), "cmd": f"bluetooth/{0 if an else 1}"}
        return zelle

    def _view_durchsage(self, uuid: str) -> dict:
        """Unterseite Durchsage einer Gen-2-Zone (Route view=durchsage): Text
        eingeben, die Zone spricht ihn (Strukturdoku: tts/{text})."""
        c = self.controls.get(uuid or "") or {}
        route = {"view": "durchsage", "id": uuid}
        if c.get("type") != "AudioZoneV2":
            return self._gone_view(route, "Durchsage", "Diese Zone gibt es nicht mehr.")
        return {"t": "view", "title": f"{_clean(c.get('name'))} · Durchsage", "route": route, "blocks": [
            {"k": "title", "text": _clean(c.get("name")), "sub": "Durchsage"},
            {"k": "field", "name": "text", "label": "Text", "value": ""},
            {"k": "row", "cells": [{"label": "Sprechen", "back": True,
                                    "form": {"uuid": c.get("uuidAction"), "tmpl": "tts/{text}"}}]}]}

    def _favoriten_grund(self, uuid: str) -> str:
        """Warum eine Zone keine Favoriten liefern kann, als Satz fuer die
        Visu; leer, wenn kein Grund bekannt ist (noch nicht geladen, oder es
        sind wirklich keine angelegt). Bei einer Gen-2-Zone kommen sie nur
        ueber den Audioserver-Kanal: ohne Verbindung keine, und ein
        gekoppelter Audioserver gibt sie erst nach der Anmeldung heraus
        (der Ausweg ueber den Miniserver, sourceList, fehlt dieser Zone)."""
        c = self.controls.get(uuid) or {}
        if c.get("type") not in ("AudioZone", "AudioZoneV2"):
            return ""
        cl, pid = self._audio_client_for(c)
        if cl is None or pid is None:
            return ""
        if not cl.verbunden:
            return "Keine Verbindung zum Audioserver"
        if cl.paired and not cl.authed and cl.anmeldung:
            return f"Anmeldung am Audioserver gescheitert: {cl.anmeldung}"
        return ""

    def _sender_bloecke(self, uuid: str) -> list:
        """Favoriten einer Zone fuer ihre Detailseite: eine Reihe Cover zum
        Abspielen, die Seite bleibt dabei stehen (bleiben); ohne Favoriten der
        Grund (_favoriten_grund) oder nichts."""
        items, _ = self._zonen_favoriten(uuid)
        if items:
            return [{"k": "favs", "items": items, "bleiben": True}]
        grund = self._favoriten_grund(uuid)
        return [{"k": "status", "text": grund}] if grund else []

    def _view_sources(self, uuid: str) -> dict:
        """Musikauswahl einer AudioZone: alle Favoriten der Zone
        (_zonen_favoriten), umbrechend. Ohne Favoriten der Grund
        (_favoriten_grund), sonst der Hinweis, wo sie angelegt werden."""
        c = self.controls.get(uuid, {})
        items, _ = self._zonen_favoriten(uuid)
        body = ({"k": "favs", "wrap": True, "items": items} if items else
                {"k": "status", "text": self._favoriten_grund(uuid) or "noch keine – in der Loxone-App anlegen"})
        return {"t": "view", "title": _clean(c.get("name")),
                "route": {"view": "sources", "id": uuid},
                "blocks": [{"k": "title", "text": _clean(c.get("name")), "sub": "Musikauswahl"},
                           {"k": "head", "text": "Favoriten"}, body]}

    def _audio_cover(self, c: dict) -> str | None:
        """Bild einer Audiozone als fertige /cover-URL, None ohne Bild - fuer
        Detailseite und breite Kachel dasselbe. AudioZone (Gen1): der State
        "cover". AudioZoneV2: der Audioserver (oder Sonn, wo Loxone leer ist)
        liefert bei Radio oft nur das Sender-Logo; laeuft ein echter Titel,
        gilt das passende Album-Cover (_song_cover), sonst das Logo."""
        t = c.get("type")
        cover = self._state(c, "cover")
        if t == "AudioZoneV2":
            sm = self._sonn_for(c)
            playing = self._state(c, "playState") == 2 or bool(sm and sm.get("playing"))
            title = self._song(c) or (sm.get("title") if sm else "") or ""
            cover = cover or (sm.get("cover") if sm else None)
            art = (self._text(c, "artist") or (sm.get("artist") if sm else "") or "").strip()
            if playing and title and art:
                dyn = self._song_cover(art, title)
                if dyn:
                    return dyn   # schon eine fertige /cover-URL
        elif t != "AudioZone":
            return None
        return ("/cover?u=" + quote(str(cover), safe="")) if cover else None

    def player_blocks(self, uuid: str, mehr: bool = False):
        """Player-Bloecke (Cover/Titel/Transport/Lautstaerke) einer festen
        AudioZone fuer die linke Split-Player-Region. None, wenn keine gueltige
        Audio-Zone. Der `more`-Block (schwebender ⋮-Button) wird entfernt,
        ausser mit mehr=True (Spieler der Hausseite: ⋮ zur Musikauswahl)."""
        c = self.controls.get(uuid or "")
        if not c or c.get("type") not in ("AudioZone", "AudioZoneV2"):
            return None
        try:
            v = self._view_control_inner(uuid)
        except Exception:
            log.exception("player_blocks fehlgeschlagen (%s)", uuid)
            return None
        return [b for b in (v.get("blocks") or []) if mehr or b.get("k") != "more"]
