"""Anbindung an den Audioserver: Ereignis-Clients (Gen2, Port 7091) je
Audioserver, Backends fuer Befehle, Cover der laufenden Titel, Favoriten der
Zonen. Die Backends selbst stehen in audioserver.py und audioserver_events.py.

Die Methoden sind ein Mixin (Audiodienst): App erbt sie und arbeitet mit ihnen auf ihrem
Zustand (self ist die App). Importiert webvisu nicht."""
from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from urllib.parse import quote, unquote, urlencode

import aiohttp

from audioserver import AudioBackend, make_backend
from audioserver_events import AudioEventClient
from konfig import _audiometa_sekunden

log = logging.getLogger("loxpanel.webvisu")   # derselbe Logger wie der Server: die Methoden gehoeren zu App


class Audiodienst:
    """Audioserver, Cover und Favoriten; Mixin der App (self ist die App)."""

    def _song_cover(self, artist: str, title: str) -> str | None:
        """Album-Cover (ueber /cover-Proxy) zu Interpret+Titel, gecacht.

        Cache-Treffer -> URL bzw. None (kein Album, z.B. Wortbeitrag). Bei einem
        Miss wird der Lookup einmalig im Hintergrund angestossen; das Ergebnis
        erscheint beim naechsten Render (der Lookup setzt _dirty)."""
        artist = (artist or "").strip()
        title = (title or "").strip()
        if not artist or not title:
            return None
        key = f"{artist}\n{title}".lower()
        hit = self._cover_cache.get(key)
        if hit and hit[1] > time.time():
            return ("/cover?u=" + quote(hit[0], safe="")) if hit[0] else None
        if key not in self._cover_pending:
            self._cover_pending.add(key)
            self._spawn(self._lookup_cover(artist, title, key))
        return None

    async def _lookup_cover(self, artist: str, title: str, key: str) -> None:
        """iTunes-Suche nach Interpret+Titel -> Album-Cover-URL (600px)."""
        url = None
        try:
            sess = self.icon_session
            if sess is not None:
                api = "https://itunes.apple.com/search?" + urlencode(
                    {"term": f"{artist} {title}", "media": "music",
                     "entity": "song", "limit": 1})
                async with sess.get(api, timeout=aiohttp.ClientTimeout(total=6)) as r:
                    if r.status == 200:
                        data = await r.json(content_type=None)
                        res = data.get("results") or []
                        if res:
                            art = res[0].get("artworkUrl100") or ""
                            url = art.replace("100x100bb", "600x600bb") or None
        except Exception as err:
            log.debug("Cover-Lookup (%s): %s", key, err)
        # Treffer lange cachen (gleicher Song -> gleiches Cover), Fehlschlag kurz
        # (aus Wortbeitrag wird spaeter wieder ein Titel).
        self._cover_cache[key] = (url, time.time() + (24 * 3600 if url else 900))
        self._cover_pending.discard(key)
        if url:
            self._dirty = True

    def _audio_favs(self, c: dict) -> list:
        """Raum-Favoriten (Radio/Playlist/Spotify) aus dem sourceList-State.

        Loxone legt das Ergebnis von `roomfav/get` in den sourceList-Textstate.
        Die Struktur variiert je nach Firmware:
          {"getroomfavs_result":[{...,"items":[...]}]}  (Gruppe(n) mit items)
          {"getroomfavs_result":[{...item...}]}          (flache Item-Liste)
          {"items":[...]}                                 (direktes Listing)
        Der State ist ausserdem ein transienter Browse-Puffer: er ist nur
        verlaesslich befuellt, nachdem wir `roomfav/get` angefordert haben
        (siehe prime_favs). Wir sammeln alle Items mit gueltigem 'slot' ein.
        """
        raw = self._state(c, "sourceList")
        if not raw:
            return []
        try:
            data = json.loads(raw)
        except (ValueError, TypeError):
            return []
        buckets = []
        res = data.get("getroomfavs_result")
        if isinstance(res, list):
            for grp in res:
                if isinstance(grp, dict) and isinstance(grp.get("items"), list):
                    buckets.append(grp["items"])
                elif isinstance(grp, dict) and "slot" in grp:
                    buckets.append([grp])
        if isinstance(data.get("items"), list):
            buckets.append(data["items"])
        out, seen = [], set()
        for items in buckets:
            for it in items:
                if not isinstance(it, dict):
                    continue
                slot = it.get("slot")
                if slot is None or slot in seen:
                    continue
                seen.add(slot)
                out.append({"slot": slot, "cover": it.get("coverurl") or "",
                            "type": (it.get("type") or "").lower(),
                            "name": unquote(str(it.get("name") or it.get("title") or f"Favorit {slot}"))})
        out.sort(key=lambda f: f["slot"])
        return out

    async def prime_favs(self, uuid: str) -> None:
        """Fordert die Zonen-Favoriten aktiv an (`roomfav/get`), damit der
        sourceList-State frisch befuellt wird. Das Ergebnis kommt asynchron
        per WS -> _on_value setzt _dirty -> broadcaster re-rendert die offene
        Ansicht (Musikauswahl) mit den nun vorhandenen Favoriten."""
        c = self.controls.get(uuid, {})
        t = c.get("type")
        if t not in ("AudioZone", "AudioZoneV2"):
            return
        # Zone mit laufendem Audioserver-Event-Client (Gen1 Musikserver ODER
        # Gen2 Audioserver): Raumfavoriten direkt ueber den 7091-Kanal anfordern
        # (Ergebnis kommt async -> _dirty). Der Loxone-sourceList-State ist bei
        # vielen Setups leer, deshalb ist das der zuverlaessige Weg.
        cl, pid = self._audio_client_for(c)
        if cl is not None and pid is not None and (cl.paired is False or cl.authed):
            await cl.request_favs(pid)
            return
        # Fallback ohne Event-Client (z.B. MS4H ohne 7091), bei gekoppeltem
        # Audioserver ohne Anmeldung oder unklarer Kopplung (paired None):
        # Favoriten ueber den Miniserver holen.
        ua = c.get("uuidAction")
        if ua:
            await self.command(ua, "roomfav/get/0/20")

    async def audio_events_task(self) -> None:
        """Verwaltet je Audioserver (aus /mediaServer der Struktur) einen
        Gen-2-Event-Client (WS 7091). Startet neue Server, stoppt verschwundene;
        reagiert so auf Struktur-/Config-Aenderungen. `enabled` (audiometa) ist
        der Master-Schalter. Adressen kommen automatisch aus der Struktur —
        keine IP-Eingabe noetig."""
        while True:
            enabled = (self.audiometa_cfg or {}).get("enabled", True)
            want = set()
            if enabled:
                for hp in self.mediaservers.values():
                    host = (hp or "").split(":")[0].strip()
                    if host:
                        want.add(host)
            for host in want:
                if host not in self.audio_clients:
                    am = self.audiometa_cfg or {}
                    cl = AudioEventClient(host, 7091, user=self.user,
                                          token_provider=lambda: self.jwt,
                                          neu_versuch_s=_audiometa_sekunden(
                                              am, "retry_interval", AudioEventClient.NEU_VERSUCH_S),
                                          pruef_zeitlimit_s=_audiometa_sekunden(
                                              am, "response_timeout", AudioEventClient.PRUEF_ZEITLIMIT_S))
                    self.audio_clients[host] = cl
                    asyncio.create_task(self._run_audio_client(host, cl))
                    log.info("Audioserver-Event-Client gestartet: %s", host)
            for host in list(self.audio_clients):
                if host not in want:
                    cl = self.audio_clients.pop(host, None)
                    if cl:
                        await cl.close()
                        log.info("Audioserver-Event-Client gestoppt: %s", host)
            await asyncio.sleep(10)

    async def _run_audio_client(self, host: str, cl: AudioEventClient) -> None:
        try:
            await cl.run(self._mark_dirty)
        except Exception as err:
            log.debug("audio client %s: %s", host, err)
        finally:
            if self.audio_clients.get(host) is cl:
                self.audio_clients.pop(host, None)

    def _audio_client_for(self, c: dict):
        """(Event-Client, playerid) zur AudioZoneV2-Zone `c` — via
        details.server -> mediaServer-Host und details.playerid. (None, None),
        wenn kein passender Client laeuft."""
        det = c.get("details") or {}
        pid = det.get("playerid")
        hp = self.mediaservers.get(det.get("server"))
        if pid is None or not hp:
            return None, None
        host = hp.split(":")[0].strip()
        return self.audio_clients.get(host), pid

    def _sonn_for(self, c: dict) -> dict | None:
        """Now-Playing zur Zone `c` aus dem passenden Audioserver-Event-Client."""
        cl, pid = self._audio_client_for(c)
        return cl.now.get(pid) if cl else None

    def _sonn_zone_id(self, c: dict):
        """playerid der Zone `c`, nur wenn ein Event-Client dafuer laeuft."""
        cl, pid = self._audio_client_for(c)
        return pid if cl else None

    def _detect_audio_host(self) -> str | None:
        """Audioserver-Host aus einer AudioZone-Cover/sourceList-URL ableiten.

        Loxone-Musik-Cover werden ueber den Audioserver-Proxy ausgeliefert
        (z.B. http://10.0.2.2:7092/...), die Host-IP ist also dort ablesbar.
        """
        for c in self.controls.values():
            if c.get("type") != "AudioZone":
                continue
            s = c.get("states") or {}
            for key in ("cover", "sourceList"):
                v = self.states.get(s.get(key))
                if isinstance(v, str):
                    m = re.search(r"https?://(\d{1,3}(?:\.\d{1,3}){3}):\d+/", v)
                    if m:
                        return m.group(1)
        return None

    def _audio_backend_for(self, uuid: str) -> AudioBackend | None:
        """Liefert das Steuer-Backend fuer eine AudioZone (uuidAction).

        Host-Reihenfolge: manuell konfiguriert (audio_cfg) -> mediaServer-Host
        aus der Struktur (steht IMMER fest, auch wenn nichts spielt) -> als
        letzter Ausweg aus einer Cover-URL abgeleitet. Pro Host ein Backend.
        """
        if self.audio is not None:               # explizit konfiguriert
            return self.audio
        host = self.audiohost_by_action.get(uuid) or self._detect_audio_host()
        if not host:
            return None
        be = self.audio_backends.get(host)
        if be is None:
            be = make_backend({"host": host, "port": self.audio_cfg.get("port", 7091)})
            if be is not None:
                self.audio_backends[host] = be
                log.info("Audioserver-Backend fuer %s", host)
        return be
