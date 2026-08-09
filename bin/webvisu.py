#!/usr/bin/env python3
"""LoxHASP Live-Web-Visu (Phase 3) — Navigations-Shell.

Baut die Loxone-App-Navigation nach, aber aufgeraeumt fuers 480x480-Panel:
kompakter Kopf (Titel + Uhr), 2x2-Kacheln, unten 4 Tabs
(Favoriten / Zentral / Raeume / Kategorien). Licht ist voll ausgebaut:
Kategorie/Raum/Zentral -> Raum-Lichtcontroller -> Stimmungen.

Client<->Server (WebSocket, JSON):
  Client: {t:'nav', route:{...}}     Server: {t:'view', ...}
  Client: {t:'cmd', uuid, cmd}

Start:  python webvisu.py   ->  http://localhost:8099
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import re
import sys
from pathlib import Path

import ssl as _ssl
from urllib.parse import quote, unquote

import aiohttp
from aiohttp import WSMsgType, web

sys.path.insert(0, str(Path(__file__).resolve().parent))
from loxone_api import LoxoneClient  # noqa: E402
from loxone_ws import LoxoneWS  # noqa: E402
from adapters import JalousieAdapter, LightControllerV2Adapter  # noqa: E402

log = logging.getLogger("loxhasp.webvisu")
HTML = Path(__file__).resolve().parent.parent / "webfrontend" / "html" / "panel.html"
LIGHT = LightControllerV2Adapter()
JAL = JalousieAdapter()

SWITCHY = {"Switch", "TimedSwitch"}
_NUMFMT = re.compile(r"^(%[-+ 0-9.]*[dfeg])(.*)$")
_PREFIX = ["k", "M", "G", "T"]


def _clean(name: str) -> str:
    return re.sub(r"^[^0-9A-Za-zÄÖÜäöü]+", "", name or "").strip() or (name or "")


def _config() -> dict:
    base = Path(__file__).resolve().parent.parent / "config"
    f = base / "loxhasp.cfg"
    if not f.is_file():
        f = base / "loxhasp.cfg.example"
    return json.loads(f.read_text(encoding="utf-8")).get("miniserver", {})


def _intercom_config() -> dict:
    base = Path(__file__).resolve().parent.parent / "config"
    f = base / "loxhasp.cfg"
    if not f.is_file():
        f = base / "loxhasp.cfg.example"
    try:
        cfg = json.loads(f.read_text(encoding="utf-8")).get("intercom", {})
    except ValueError:
        return {}
    for k, v in cfg.items():
        if isinstance(v, dict) and isinstance(v.get("url"), str):
            v["url"] = v["url"].strip()
        elif isinstance(v, str):
            cfg[k] = v.strip()
    return cfg


DEFAULT_THEME = {"states": {"active": "#e0a24d", "good": "#52b881",
                            "warn": "#d6a24a", "crit": "#e2695f"}}


def load_theme() -> dict:
    theme = {"states": dict(DEFAULT_THEME["states"]), "categories": {},
             "ui": {"tabs": ["favoriten", "zentral", "raeume", "kategorien"],
                    "iconSize": 38, "nameSize": 18, "subSize": 15, "font": ""}}
    f = Path(__file__).resolve().parent.parent / "config" / "theme.json"
    if f.is_file():
        try:
            user = json.loads(f.read_text(encoding="utf-8"))
            for k in ("states", "categories", "ui"):
                v = user.get(k)
                if isinstance(v, dict):
                    theme[k].update({kk: vv for kk, vv in v.items() if not kk.startswith("_")})
        except ValueError:
            pass
    return theme


class App:
    def __init__(self, ms: dict):
        self.host, self.port = ms["host"], ms.get("port", 443)
        self.user, self.password = ms["user"], ms["pass"]
        self.verify_tls = ms.get("verify_tls", False)

        self.client: LoxoneClient | None = None
        self.ws: LoxoneWS | None = None
        self.states: dict[str, object] = {}
        self.controls: dict = {}
        self.rooms: dict = {}
        self.cats: dict = {}
        self.rooms_with: list[str] = []
        self.cats_with: list[str] = []
        self.conn_route: dict[web.WebSocketResponse, dict] = {}
        self._dirty = True
        self.jwt: str | None = None
        self.alg: str = "SHA1"
        self.icon_session: aiohttp.ClientSession | None = None
        self.icon_cache: dict[str, tuple[bytes, str]] = {}
        self.theme = load_theme()
        self.intercom_cfg = _intercom_config()
        self.bell_map: dict[str, str] = {}
        self._bell_prev: dict[str, object] = {}
        self._pending_ring: str | None = None

    async def start(self) -> None:
        self.client = LoxoneClient(host=self.host, user=self.user, password=self.password,
                                   port=self.port, verify_tls=self.verify_tls)
        await self.client.__aenter__()
        self.alg = (await self.client.getkey2()).hashAlg
        self.jwt = await self.client.authenticate()
        st = await self.client.load_structure()
        self.controls = st.get("controls", {})
        self.rooms = st.get("rooms", {})
        self.cats = st.get("cats", {})
        self.rooms_with = sorted(
            {c.get("room") for c in self.controls.values() if c.get("room") in self.rooms},
            key=lambda r: self.rooms[r].get("name", ""))
        self.cats_with = sorted(
            {c.get("cat") for c in self.controls.values() if c.get("cat") in self.cats},
            key=lambda c: self.cats[c].get("name", ""))
        self.bell_map = {}
        for _u, _c in self.controls.items():
            if _c.get("type") == "Intercom":
                _bu = (_c.get("states") or {}).get("bell")
                if _bu:
                    self.bell_map[_bu] = _u
        log.info("Struktur: %d Controls, %d Räume, %d Kategorien, %d Intercom-Klingeln",
                 len(self.controls), len(self.rooms_with), len(self.cats_with), len(self.bell_map))

        ctx = _ssl.SSLContext(_ssl.PROTOCOL_TLS_CLIENT)
        if not self.verify_tls:
            ctx.check_hostname = False
            ctx.verify_mode = _ssl.CERT_NONE
        self.icon_session = aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=ctx))

        await self._connect_ws()

    async def _connect_ws(self) -> None:
        self.ws = LoxoneWS(host=self.host, port=self.port, user=self.user, jwt=self.jwt,
                           hash_alg=self.alg, verify_tls=self.verify_tls)
        await self.ws.connect()

    async def _reauth(self) -> None:
        # Token erneuern (kann nach langer Laufzeit ablaufen)
        if self.client:
            self.jwt = await self.client.authenticate()

    # ---- Zustands-Helfer ----
    def _state(self, control: dict, name: str):
        su = (control.get("states") or {}).get(name)
        return self.states.get(su) if su else None

    def _text(self, control: dict, name: str) -> str:
        """Text-State, URL-dekodiert (Loxone liefert songName/artist prozentkodiert)."""
        v = self._state(control, name)
        return unquote(str(v)) if v not in (None, "") else ""

    def _song(self, control: dict) -> str:
        """songName, aber rohe Stream-URLs (Radio) ausblenden."""
        s = self._text(control, "songName")
        return "" if s.startswith(("http://", "https://")) else s

    def _fmt_num(self, value, fmt: str) -> str:
        """Loxone-Formatstring anwenden, Einheiten skalieren (kWh→MWh), Komma-Dezimal."""
        try:
            value = float(value)
        except (TypeError, ValueError):
            return ""
        m = _NUMFMT.match(fmt or "%.1f")
        numfmt, unit = (m.group(1), m.group(2)) if m else ("%.1f", "")
        if unit[:1] in _PREFIX:
            i = _PREFIX.index(unit[0]); rest = unit[1:]
            while abs(value) >= 1000 and i < len(_PREFIX) - 1:
                value /= 1000.0
                i += 1
            unit = _PREFIX[i] + rest
        try:
            s = numfmt % value
        except (TypeError, ValueError):
            s = str(value)
        s = s.replace(".", ",")
        return (s + " " + unit) if unit else s

    def _with_uuid(self, uuid: str) -> dict:
        c = dict(self.controls[uuid])
        c["uuid"] = uuid
        return c

    def _jal_status(self, c: dict) -> str:
        s = c.get("states") or {}
        ai = s.get("autoInfoText")
        if ai and self.states.get(ai):
            return str(self.states.get(ai))
        aa = s.get("autoActive")
        if aa:
            return "Automatik aktiv" if self.states.get(aa) else "Sonnenstandsautomatik inaktiv"
        return "Manuell"

    @staticmethod
    def _icon_url(image: str | None) -> str | None:
        if image and (image.endswith(".svg") or image.endswith(".png")):
            return f"/icon?p={quote(image)}"
        return None

    def _control_icon_url(self, c: dict) -> str | None:
        """Echtes Loxone-Icon eines Controls: control-eigenes Bild, sonst Kategorie-Icon."""
        di = (c.get("details") or {}).get("image")
        if isinstance(di, str):
            img = di
        elif isinstance(di, dict):
            img = di.get("on") or di.get("off")
        else:
            img = None
        if not img:
            img = (self.cats.get(c.get("cat")) or {}).get("image")
        return self._icon_url(img)

    def _cat_color(self, cat_uuid: str | None) -> str | None:
        name = _clean((self.cats.get(cat_uuid) or {}).get("name") or "").lower()
        if not name:
            return None
        for key, color in self.theme.get("categories", {}).items():
            if key.lower() in name:
                return color
        return None

    async def fetch_icon(self, path: str) -> tuple[bytes, str] | None:
        if path in self.icon_cache:
            return self.icon_cache[path]
        if not self.icon_session:
            return None
        url = f"https://{self.host}:{self.port}/{path.lstrip('/')}"
        headers = {"Authorization": f"Bearer {self.jwt}"} if self.jwt else {}
        try:
            async with self.icon_session.get(url, headers=headers) as r:
                if r.status != 200:
                    return None
                body = await r.read()
                ctype = r.headers.get("Content-Type", "application/octet-stream")
        except aiohttp.ClientError:
            return None
        self.icon_cache[path] = (body, ctype)
        return self.icon_cache[path]

    async def fetch_cover(self, url: str) -> tuple[bytes, str] | None:
        if not self.icon_session:
            return None
        try:
            async with self.icon_session.get(url) as r:
                if r.status != 200:
                    return None
                return (await r.read(), r.headers.get("Content-Type", "image/jpeg"))
        except aiohttp.ClientError:
            return None

    # ---- Kachel fuer ein Control ----
    def _control_item(self, uuid: str) -> dict:
        c = self.controls.get(uuid)
        if not c:
            return {"id": uuid, "label": "?", "icon": "info", "on": False}
        t = c.get("type")
        name = _clean(c.get("name"))
        it: dict = {"id": uuid, "label": name, "on": False, "icon": "info"}
        iu = self._control_icon_url(c)
        if iu:
            it["iconUrl"] = iu
        cc = self._cat_color(c.get("cat"))
        if cc:
            it["color"] = cc
        if t == "LightControllerV2":
            r = LIGHT.render(self._with_uuid(uuid), self.states)
            it.update(on=r["on"], sublabel=r["label"], icon="bulb",
                      nav={"view": "control", "id": uuid})
        elif t == "Jalousie":
            r = JAL.render(self._with_uuid(uuid), self.states)
            it.update(on=r["on"], sublabel=r["label"], icon="blind",
                      nav={"view": "control", "id": uuid})
        elif t == "Gate":
            pct = round((self._state(c, "position") or 0) * 100)
            it.update(on=pct > 0, icon="gate", nav={"view": "control", "id": uuid},
                      sublabel=("Offen" if pct >= 100 else
                                ("Geschlossen" if pct <= 0 else f"{pct}% offen")))
        elif t == "IRoomControllerV2":
            ta = self._state(c, "tempActual"); tt = self._state(c, "tempTarget")
            it.update(icon="thermo", nav={"view": "control", "id": uuid},
                      sublabel=(f"{self._fmt_num(ta, '%.1f')}° → {self._fmt_num(tt, '%.1f')}°"
                                if ta is not None else "Heizung"))
        elif t == "Intercom":
            it.update(icon="cam", sublabel="Türsprechanlage",
                      nav={"view": "control", "id": uuid})
        elif t in SWITCHY:
            on = bool(self._state(c, "active"))
            it.update(on=on, sublabel="Ein" if on else "Aus", icon="switch",
                      cmd={"uuid": c.get("uuidAction"), "cmd": "off" if on else "on"})
        elif t == "AudioZone":
            playing = self._state(c, "playState") == 2
            ua = c.get("uuidAction")
            it.update(on=playing, sublabel=(self._song(c) or ("An" if playing else "Aus")),
                      icon="music", nav={"view": "control", "id": uuid},
                      controls=[
                          {"icon": "prev", "cmd": {"uuid": ua, "cmd": "queueminus"}},
                          {"icon": "pause" if playing else "play",
                           "cmd": {"uuid": ua, "cmd": "pause" if playing else "play"}},
                          {"icon": "next", "cmd": {"uuid": ua, "cmd": "queueplus"}},
                      ])
        elif t == "Pushbutton":
            it.update(icon="switch", sublabel="Taster",
                      cmd={"uuid": c.get("uuidAction"), "cmd": "pulse"})
        elif t == "InfoOnlyDigital":
            on = bool(self._state(c, "active"))
            txt = (c.get("details") or {}).get("text") or {}
            it.update(on=on, sublabel=(txt.get("on") if on else txt.get("off")) or ("Ein" if on else "Aus"))
        elif t == "Meter":
            det = c.get("details") or {}
            a = self._fmt_num(self._state(c, "actual"), det.get("actualFormat", "%.1f"))
            tot = self._fmt_num(self._state(c, "total"), det.get("totalFormat", "%.1f"))
            it["sublabel"] = " • ".join(x for x in (a, tot) if x)
        elif t in ("Slider", "InfoOnlyAnalog"):
            det = c.get("details") or {}
            it["sublabel"] = self._fmt_num(self._state(c, "value"), det.get("format", "%.1f"))
        elif t in ("TextState", "InfoOnlyText"):
            it["sublabel"] = str(self._state(c, "textAndIcon") or self._state(c, "text") or "")
        elif t == "SmokeAlarm":
            ok = (self._state(c, "level") or 0) == 0
            it.update(icon="alarm", sublabel=("Alles ok" if ok else "Alarm!"),
                      tone=("good" if ok else "crit"))
        elif (t or "").startswith("Central"):
            muuids = [m.get("uuid") for m in ((c.get("details") or {}).get("controls") or [])
                      if m.get("uuid") in self.controls]
            n = 0
            if t == "CentralLightController":
                n = sum(1 for mu in muuids if LIGHT.render(self._with_uuid(mu), self.states)["on"])
                it["sublabel"] = f"In {n} Räumen aktiv" if n else "Aus"
            elif t == "CentralAudioZone":
                n = sum(1 for mu in muuids if self._state(self.controls[mu], "playState") == 2)
                it["sublabel"] = f"Spielt in {n} Räumen" if n else "Aus"
            it.update(icon="central", on=(n > 0),
                      nav={"view": "group", "kind": "central", "id": uuid})
        return it

    # ---- Views ----
    def _view_tab(self, tab: str) -> dict:
        if tab == "favoriten":
            items = [self._control_item(u) for u, c in self.controls.items() if c.get("isFavorite")]
            title = "Favoriten"
        elif tab == "zentral":
            items = [self._control_item(u) for u, c in self.controls.items()
                     if (c.get("type") or "").startswith("Central")]
            title = "Zentral"
        elif tab == "raeume":
            items = [{"id": ru, "label": _clean(self.rooms[ru].get("name")), "icon": "folder",
                      "iconUrl": self._icon_url(self.rooms[ru].get("image")),
                      "on": False, "nav": {"view": "group", "kind": "room", "id": ru}}
                     for ru in self.rooms_with]
            title = "Räume"
        else:
            items = [{"id": cu, "label": _clean(self.cats[cu].get("name")), "icon": "folder",
                      "iconUrl": self._icon_url(self.cats[cu].get("image")),
                      "color": self._cat_color(cu),
                      "on": False, "nav": {"view": "group", "kind": "cat", "id": cu}}
                     for cu in self.cats_with]
            title = "Kategorien"
        return {"t": "view", "title": title, "tab": tab, "route": {"view": "tab", "tab": tab},
                "items": items}

    def _view_group(self, route: dict) -> dict:
        kind, gid = route.get("kind"), route.get("id")
        layout = None
        if kind == "cat":
            uuids = [u for u, c in self.controls.items() if c.get("cat") == gid]
            title = _clean(self.cats.get(gid, {}).get("name")); tab = "kategorien"
        elif kind == "room":
            uuids = [u for u, c in self.controls.items() if c.get("room") == gid]
            title = _clean(self.rooms.get(gid, {}).get("name")); tab = "raeume"
        elif kind == "central":
            c = self.controls.get(gid, {})
            members = (c.get("details") or {}).get("controls") or []
            uuids = [m.get("uuid") for m in members if m.get("uuid") in self.controls]
            title = _clean(c.get("name")); tab = "zentral"
            if c.get("type") == "CentralAudioZone":
                layout = "list"
        else:
            uuids, title, tab = [], "", None
        return {"t": "view", "title": title, "tab": tab, "route": route,
                "layout": layout, "items": [self._control_item(u) for u in uuids]}

    def _view_control(self, uuid: str) -> dict:
        c = self.controls.get(uuid, {})
        t = c.get("type")
        route = {"view": "control", "id": uuid}
        if t == "LightControllerV2":
            cu = self._with_uuid(uuid)
            active = LIGHT.active_moods(cu, self.states)
            items = [{"id": f"{uuid}:{m.get('id')}", "label": m.get("name", str(m.get("id"))),
                      "on": m.get("id") in active, "icon": "mood",
                      "cmd": {"uuid": c.get("uuidAction"), "cmd": f"changeTo/{m.get('id')}"}}
                     for m in LIGHT.moods(cu, self.states)]
            r = LIGHT.render(cu, self.states)
            return {"t": "view", "title": _clean(c.get("name")), "subtitle": r["label"],
                    "route": route, "layout": "list", "items": items}
        if t == "Jalousie":
            ua = c.get("uuidAction")
            cu = self._with_uuid(uuid)
            s = c.get("states") or {}
            up_move = bool(self.states.get(s.get("up")))
            down_move = bool(self.states.get(s.get("down")))
            moving = up_move or down_move
            pct = JAL.render(cu, self.states).get("pct")
            base = "–" if pct is None else ("Offen" if pct <= 0 else
                                            ("Geschlossen" if pct >= 100 else f"{pct}% geschlossen"))
            val = ("▲ fährt … " + base) if up_move else (("▼ fährt … " + base) if down_move else base)
            # Wie Original-Visu: kein Stop-Button. Tipp auf die Richtung waehrend der
            # Fahrt sendet Stop (haelt an); im Stand startet er die Fahrt.
            auf = {"label": "Auf", "on": up_move, "cmd": {"uuid": ua, "cmd": "Stop" if moving else "Up"}}
            ab = {"label": "Ab", "on": down_move, "cmd": {"uuid": ua, "cmd": "Stop" if moving else "Down"}}
            blocks = [
                {"k": "hero", "icon": "blind"},
                {"k": "status", "text": self._jal_status(cu)},
                {"k": "value", "text": val},
                {"k": "row", "cells": [auf, ab]},
                {"k": "row", "cells": [
                    {"label": "Ganz Auf", "cmd": {"uuid": ua, "cmd": "FullUp"}},
                    {"label": "Ganz Ab", "cmd": {"uuid": ua, "cmd": "FullDown"}},
                ]},
                {"k": "row", "cells": [{"label": "Beschatten", "cmd": {"uuid": ua, "cmd": "shade"}}]},
            ]
            return {"t": "view", "title": _clean(c.get("name")), "route": route, "blocks": blocks}
        if t == "AudioZone":
            ua = c.get("uuidAction")
            playing = self._state(c, "playState") == 2
            title = self._song(c) or "Radio"
            sub = self._text(c, "artist") or self._text(c, "album")
            vol = int(self._state(c, "volume") or 0)
            cover = self._state(c, "cover")
            blocks = []
            if cover:
                blocks.append({"k": "cover", "src": "/cover?u=" + quote(str(cover), safe="")})
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
            return {"t": "view", "title": _clean(c.get("name")), "route": route, "blocks": blocks}
        if t == "Gate":
            ua = c.get("uuidAction")
            pct = round((self._state(c, "position") or 0) * 100)
            active = self._state(c, "active") or 0
            postext = "Offen" if pct >= 100 else ("Geschlossen" if pct <= 0 else f"{pct}% offen")
            status = "öffnet …" if active > 0 else ("schließt …" if active < 0 else postext)
            return {"t": "view", "title": _clean(c.get("name")), "route": route, "blocks": [
                {"k": "hero", "icon": "gate"},
                {"k": "status", "text": status},
                {"k": "value", "text": postext},
                {"k": "row", "cells": [
                    {"label": "Öffnen", "cmd": {"uuid": ua, "cmd": "open"}},
                    {"label": "Stop", "cmd": {"uuid": ua, "cmd": "stop"}},
                    {"label": "Schließen", "cmd": {"uuid": ua, "cmd": "close"}},
                ]},
            ]}
        if t == "IRoomControllerV2":
            ua = c.get("uuidAction")
            ta = self._fmt_num(self._state(c, "tempActual"), "%.1f")
            tt = self._fmt_num(self._state(c, "tempTarget"), "%.1f")
            try:
                comfort = float(self._state(c, "comfortTemperature")
                                or self._state(c, "tempTarget") or 20)
            except (TypeError, ValueError):
                comfort = 20.0
            return {"t": "view", "title": _clean(c.get("name")), "route": route, "blocks": [
                {"k": "hero", "icon": "thermo"},
                {"k": "value", "text": f"{ta} °C"},
                {"k": "status", "text": f"Soll {tt} °C"},
                {"k": "row", "cells": [
                    {"label": "−", "cmd": {"uuid": ua, "cmd": f"setComfortTemperature/{comfort - 0.5:.1f}"}},
                    {"label": "+", "cmd": {"uuid": ua, "cmd": f"setComfortTemperature/{comfort + 0.5:.1f}"}},
                ]},
            ]}
        if t == "Intercom":
            ent = self.intercom_cfg.get(uuid)
            has_url = bool(ent.get("url") if isinstance(ent, dict) else ent)
            subs = c.get("subControls") or {}
            cells = [{"label": _clean(sc.get("name")),
                      "cmd": {"uuid": sc.get("uuidAction"), "cmd": "pulse"}}
                     for sc in subs.values()]
            blocks = [{"k": "video", "src": f"/mjpeg?id={quote(uuid)}"}] if has_url else \
                     [{"k": "status", "text": "Kein Video konfiguriert (loxhasp.cfg → intercom)"}]
            if cells:
                blocks.append({"k": "row", "cells": cells})
            return {"t": "view", "title": _clean(c.get("name")), "route": route, "blocks": blocks}
        return {"t": "view", "title": _clean(c.get("name")), "route": route,
                "items": [self._control_item(uuid)]}

    def render(self, route: dict) -> dict:
        v = (route or {}).get("view", "tab")
        if v == "group":
            return self._view_group(route)
        if v == "control":
            return self._view_control(route.get("id"))
        return self._view_tab(route.get("tab", "favoriten"))

    async def command(self, uuid: str, cmd: str) -> None:
        if self.client and uuid and cmd:
            log.info("cmd %s/%s", uuid, cmd)
            try:
                await self.client.jdev_get(f"sps/io/{uuid}/{cmd}")
            except Exception as err:  # Befehl darf den Server nicht killen
                log.warning("cmd fehlgeschlagen: %s", err)

    def _on_value(self, uuid: str, value: object) -> None:
        self.states[uuid] = value
        self._dirty = True
        if uuid in self.bell_map:
            if value and not self._bell_prev.get(uuid):
                self._pending_ring = self.bell_map[uuid]
            self._bell_prev[uuid] = value

    async def stream_task(self) -> None:
        # Dauer-Loop mit automatischem Reconnect zum Miniserver.
        while True:
            try:
                if self.ws is None:
                    await self._connect_ws()
                await self.ws.stream(self._on_value)
                raise ConnectionError("WS-Stream regulär beendet")
            except asyncio.CancelledError:
                raise
            except Exception as err:
                log.warning("Loxone-WS unterbrochen (%s) — Reconnect in 5s", err)
                try:
                    if self.ws:
                        await self.ws.close()
                except Exception:
                    pass
                self.ws = None
                await asyncio.sleep(5)
                try:
                    await self._reauth()
                except Exception as e2:
                    log.warning("Re-Auth fehlgeschlagen: %s", e2)

    async def broadcaster(self) -> None:
        while True:
            await asyncio.sleep(0.3)
            if self._pending_ring is not None:
                rid, self._pending_ring = self._pending_ring, None
                log.info("Klingel → Popup: %s", rid)
                for ws in list(self.conn_route):
                    try:
                        await ws.send_json({"t": "ring", "id": rid})
                    except ConnectionError:
                        self.conn_route.pop(ws, None)
            if self._dirty and self.conn_route:
                self._dirty = False
                for ws, route in list(self.conn_route.items()):
                    try:
                        await ws.send_json(self.render(route))
                    except ConnectionError:
                        self.conn_route.pop(ws, None)

    async def close(self) -> None:
        if self.ws:
            await self.ws.close()
        if self.icon_session:
            await self.icon_session.close()
        if self.client:
            await self.client.close()


async def index(request: web.Request) -> web.Response:
    return web.Response(text=HTML.read_text(encoding="utf-8"), content_type="text/html")


async def icon_handler(request: web.Request) -> web.Response:
    app: App = request.app["app"]
    p = request.query.get("p", "")
    if not p or ".." in p or not (p.endswith(".svg") or p.endswith(".png")):
        return web.Response(status=400, text="bad icon")
    res = await app.fetch_icon(p)
    if not res:
        return web.Response(status=404)
    body, ctype = res
    return web.Response(body=body, content_type=ctype.split(";")[0],
                        headers={"Cache-Control": "max-age=86400"})


async def cover_handler(request: web.Request) -> web.Response:
    app: App = request.app["app"]
    u = request.query.get("u", "")
    if not (u.startswith("http://") or u.startswith("https://")):
        return web.Response(status=400, text="bad cover")
    res = await app.fetch_cover(u)
    if not res:
        return web.Response(status=404)
    body, ctype = res
    return web.Response(body=body, content_type=ctype.split(";")[0],
                        headers={"Cache-Control": "max-age=60"})


async def mjpeg_handler(request: web.Request) -> web.StreamResponse:
    """Relais des MJPEG-Streams der Tuerstation (mit Auth) -> Browser.

    Eigene ClientSession (nicht icon_session): mit dem SSL-Connector der
    icon_session liefert die Mobotix nur ein Einzelbild statt des Streams.
    """
    app: App = request.app["app"]
    ent = app.intercom_cfg.get(request.query.get("id", ""))
    url = ent.get("url") if isinstance(ent, dict) else ent
    if not url:
        return web.Response(status=404)
    auth = None
    if isinstance(ent, dict) and ent.get("user"):
        auth = aiohttp.BasicAuth(ent.get("user", ""), ent.get("pass", ""))

    sess = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=None, sock_read=30))
    try:
        upstream = await sess.get(url, auth=auth)
    except aiohttp.ClientError:
        await sess.close()
        return web.Response(status=502, text="camera unreachable")
    if upstream.status != 200:
        st = upstream.status
        upstream.release()
        await sess.close()
        return web.Response(status=502, text=f"camera status {st}")

    ctype = upstream.headers.get("Content-Type", "multipart/x-mixed-replace")
    resp = web.StreamResponse(status=200, headers={
        "Content-Type": ctype, "Cache-Control": "no-cache, no-store"})
    await resp.prepare(request)
    try:
        async for chunk in upstream.content.iter_any():
            await resp.write(chunk)
    except (aiohttp.ClientError, ConnectionResetError, asyncio.CancelledError):
        pass
    finally:
        upstream.release()
        await sess.close()
    return resp


async def ws_handler(request: web.Request) -> web.WebSocketResponse:
    app: App = request.app["app"]
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    app.conn_route[ws] = {"view": "tab", "tab": "favoriten"}
    _s = app.theme.get("states", {})
    _u = app.theme.get("ui", {})
    _vars = {"--glow": _s.get("active"), "--good": _s.get("good"),
             "--crit": _s.get("crit"), "--warn": _s.get("warn"),
             "--ico-size": f"{_u.get('iconSize', 38)}px",
             "--name-size": f"{_u.get('nameSize', 18)}px",
             "--sub-size": f"{_u.get('subSize', 15)}px"}
    if _u.get("font"):
        _vars["--font"] = _u["font"]
    await ws.send_json({"t": "theme", "vars": {k: v for k, v in _vars.items() if v},
                        "tabs": _u.get("tabs") or ["favoriten", "zentral", "raeume", "kategorien"]})
    await ws.send_json(app.render(app.conn_route[ws]))
    try:
        async for msg in ws:
            if msg.type != WSMsgType.TEXT:
                continue
            try:
                data = json.loads(msg.data)
            except ValueError:
                continue
            if data.get("t") == "nav" and isinstance(data.get("route"), dict):
                app.conn_route[ws] = data["route"]
                await ws.send_json(app.render(data["route"]))
            elif data.get("t") == "cmd":
                await app.command(data.get("uuid"), data.get("cmd"))
    finally:
        app.conn_route.pop(ws, None)
    return ws


async def on_startup(a: web.Application) -> None:
    app: App = a["app"]
    await app.start()
    a["tasks"] = [asyncio.create_task(app.stream_task()),
                  asyncio.create_task(app.broadcaster())]


async def on_cleanup(a: web.Application) -> None:
    for t in a.get("tasks", []):
        t.cancel()
    await a["app"].close()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    p = argparse.ArgumentParser()
    p.add_argument("--port", type=int, default=8099)
    args = p.parse_args()

    a = web.Application()
    a["app"] = App(_config())
    a.router.add_get("/", index)
    a.router.add_get("/icon", icon_handler)
    a.router.add_get("/cover", cover_handler)
    a.router.add_get("/mjpeg", mjpeg_handler)
    a.router.add_get("/ws", ws_handler)
    a.on_startup.append(on_startup)
    a.on_cleanup.append(on_cleanup)
    web.run_app(a, host="0.0.0.0", port=args.port)


if __name__ == "__main__":
    main()
