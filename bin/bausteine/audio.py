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
    blocks += [
        {"k": "title", "text": title, "sub": sub},
        {"k": "row", "cells": [
            {"icon": "prev", "cmd": {"uuid": ua, "cmd": "queueminus"}},
            {"icon": "pause" if playing else "play", "big": True,
             "cmd": {"uuid": ua, "cmd": "pause" if playing else "play"}},
            {"icon": "next", "cmd": {"uuid": ua, "cmd": "queueplus"}},
        ]},
        {"k": "slider", "icon": "vol", "value": vol, "min": 0, "max": 100,
         "cmd": {"uuid": ua, "tmpl": "volume/{v}"}},
    ]
    # Quellen (Radio/Playlist/Spotify) immer auf Unterseite erreichbar
    # (Favoriten werden dort per prime_favs frisch angefordert).
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
    blocks += [
        {"k": "title", "text": title, "sub": sub},
        {"k": "row", "cells": [
            {"icon": "prev", "cmd": {"uuid": ua, "cmd": "prev"}},
            {"icon": "pause" if playing else "play", "big": True,
             "cmd": {"uuid": ua, "cmd": "pause" if playing else "play"}},
            {"icon": "next", "cmd": {"uuid": ua, "cmd": "next"}},
        ]},
        {"k": "slider", "icon": "vol", "value": vol, "min": 0, "max": 100,
         "cmd": {"uuid": ua, "tmpl": "volume/{v}"}},
    ]
    # 3-Punkte -> Quellen/Favoriten (Sonn via API, sonst Loxone-roomfav)
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

    def _view_sources(self, uuid: str) -> dict:
        """Musikauswahl einer AudioZone: feste Rubriken (immer sichtbar, auch leer).

        'Favoriten' = die Zonen-Favoriten (_zonen_favoriten). 'Playlisten' ist
        vorerst ein Platzhalter (Bibliothek/Playlisten liegen im Audioserver
        und werden noch nicht abgefragt).
        """
        c = self.controls.get(uuid, {})
        items, vom_kanal = self._zonen_favoriten(uuid)
        if vom_kanal:
            body = ({"k": "favs", "wrap": True, "items": items} if items else
                    {"k": "status", "text": "noch keine – in der App/am Tablet anlegen"})
            return {"t": "view", "title": _clean(c.get("name")),
                    "route": {"view": "sources", "id": uuid},
                    "blocks": [{"k": "title", "text": _clean(c.get("name")), "sub": "Musikauswahl"},
                               {"k": "head", "text": "Favoriten"}, body]}

        empty = {"k": "status", "text": "noch keine – im Tablet / der App anlegen"}
        blocks = [{"k": "title", "text": _clean(c.get("name")), "sub": "Musikauswahl"},
                  {"k": "head", "text": "Favoriten"},
                  {"k": "favs", "wrap": True, "items": items} if items else dict(empty),
                  {"k": "head", "text": "Playlisten"},
                  dict(empty)]
        return {"t": "view", "title": _clean(c.get("name")),
                "route": {"view": "sources", "id": uuid}, "blocks": blocks}

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
