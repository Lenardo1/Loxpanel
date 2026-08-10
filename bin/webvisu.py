#!/usr/bin/env python3
"""LoxPanel Live-Web-Visu (Phase 3) — Navigations-Shell.

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
import hashlib
import hmac
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

log = logging.getLogger("loxpanel.webvisu")
_WEB = Path(__file__).resolve().parent.parent / "webfrontend" / "html"
HTML = _WEB / "panel.html"
CONFIG_HTML = _WEB / "config.html"
PANELS_FILE = Path(__file__).resolve().parent.parent / "config" / "panels.json"
LIGHT = LightControllerV2Adapter()
JAL = JalousieAdapter()

SWITCHY = {"Switch", "TimedSwitch"}
VALID_TABS = ["favoriten", "zentral", "raeume", "kategorien"]
_COLOR_RE = re.compile(r"^(#[0-9a-fA-F]{3,8}|rgba?\([0-9.,%\s]+\)|[a-zA-Z]{3,20})$")


def _color_ok(v) -> bool:
    return isinstance(v, str) and bool(_COLOR_RE.match(v.strip()))


def _clean_icon(ic):
    """Icon-Referenz einer Kachel validieren (Quelle + sicherer Bezeichner)."""
    if not isinstance(ic, dict):
        return None
    s = ic.get("src")
    if s == "builtin" and isinstance(ic.get("id"), str) and re.match(r"^[A-Za-z0-9_]{1,32}$", ic["id"]):
        return {"src": "builtin", "id": ic["id"]}
    if s == "loxone" and isinstance(ic.get("p"), str) and ".." not in ic["p"] \
            and (ic["p"].endswith(".svg") or ic["p"].endswith(".png")):
        return {"src": "loxone", "p": ic["p"]}
    if s == "google" and isinstance(ic.get("name"), str) and re.match(r"^[a-z0-9_]{1,48}$", ic["name"]):
        return {"src": "google", "name": ic["name"]}
    if s == "custom" and isinstance(ic.get("file"), str) and re.match(r"^[A-Za-z0-9._-]{1,80}$", ic["file"]):
        return {"src": "custom", "file": ic["file"]}
    return None
_NUMFMT = re.compile(r"^(%[-+ 0-9.]*[dfeg])(.*)$")
_PREFIX = ["k", "M", "G", "T"]


def _clean(name: str) -> str:
    return re.sub(r"^[^0-9A-Za-zÄÖÜäöü]+", "", name or "").strip() or (name or "")


def _config() -> dict:
    base = Path(__file__).resolve().parent.parent / "config"
    f = base / "loxpanel.cfg"
    if not f.is_file():
        f = base / "loxpanel.cfg.example"
    return json.loads(f.read_text(encoding="utf-8")).get("miniserver", {})


def _intercom_config() -> dict:
    base = Path(__file__).resolve().parent.parent / "config"
    f = base / "loxpanel.cfg"
    if not f.is_file():
        f = base / "loxpanel.cfg.example"
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


def load_panels() -> dict:
    """Panel-Profile aus config/panels.json (Auswahl per URL ?panel=<id>).

    Jedes Profil kann Theme-Overrides (ui/states) + Sichtbarkeits-Whitelists
    (rooms/cats als UUID ODER Name) + Tab-Auswahl tragen. Leere/fehlende
    Whitelist = alles sichtbar. Wird später von der LoxBerry-Config-Seite
    befuellt (Räume/Kategorien anklickbar pro Gerät).
    """
    f = Path(__file__).resolve().parent.parent / "config" / "panels.json"
    if f.is_file():
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            p = data.get("panels")
            if isinstance(p, dict):
                return {k: v for k, v in p.items() if not k.startswith("_")}
        except ValueError:
            pass
    return {}


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
        self.conn_prof: dict[web.WebSocketResponse, dict] = {}
        self.panels = load_panels()
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

    def _lc_scenes(self, c: dict) -> dict:
        """LightController-V1 sceneList (Loxone-Format id=\"name\") -> {id:name}."""
        raw = str(self._state(c, "sceneList") or "")
        return {int(m.group(1)): m.group(2) for m in re.finditer(r'(\d+)="([^"]*)"', raw)}

    def _json_list_map(self, c: dict, name: str) -> dict:
        """State-Wert = JSON-Array [{id,name}] -> {id:name}."""
        raw = self._state(c, name)
        try:
            arr = json.loads(raw) if isinstance(raw, str) else raw
        except (ValueError, TypeError):
            return {}
        return {int(x["id"]): x.get("name") for x in (arr or [])
                if isinstance(x, dict) and x.get("id") is not None}

    def _audio_favs(self, c: dict) -> list:
        """Raum-Favoriten (Radio/Playlist/Spotify) aus dem sourceList-State."""
        raw = self._state(c, "sourceList")
        if not raw:
            return []
        try:
            data = json.loads(raw)
        except (ValueError, TypeError):
            return []
        out = []
        for grp in data.get("getroomfavs_result", []):
            for it in grp.get("items", []):
                slot = it.get("slot")
                if slot is None:
                    continue
                out.append({"slot": slot, "cover": it.get("coverurl") or "",
                            "type": (it.get("type") or "").lower(),
                            "name": unquote(str(it.get("name") or it.get("title") or f"Favorit {slot}"))})
        return out

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
        if not img:
            img = c.get("defaultIcon")
        return self._icon_url(img)

    def _cat_color(self, cat_uuid: str | None) -> str | None:
        name = _clean((self.cats.get(cat_uuid) or {}).get("name") or "").lower()
        if not name:
            return None
        for key, color in self.theme.get("categories", {}).items():
            if key.lower() in name:
                return color
        return None

    # ---- Panel-Profile ----
    def _resolve_ids(self, entries, table: dict):
        """Whitelist-Einträge (UUID ODER Name) auf UUID-Menge abbilden.

        Leer/fehlend -> None (= keine Einschränkung, alles sichtbar). Namen
        matchen exakt oder als Teilstring (Loxone-Räume haben Präfixe wie
        „1.0.2 Terrasse" -> Eintrag „Terrasse" genügt).
        """
        if not entries:
            return None
        names = {k: _clean(v.get("name", "")).lower() for k, v in table.items()}
        out = set()
        for e in entries:
            e = str(e).strip()
            if not e:
                continue
            if e in table:                       # exakte UUID
                out.add(e)
                continue
            el = _clean(e).lower()
            exact = [k for k, n in names.items() if n == el]
            if exact:
                out.update(exact)
            elif el:                             # Teilstring-Treffer
                out.update(k for k, n in names.items() if el in n)
        return out

    @staticmethod
    def _theme_vars(states: dict, ui: dict) -> dict:
        v = {"--glow": states.get("active"), "--good": states.get("good"),
             "--crit": states.get("crit"), "--warn": states.get("warn"),
             "--ico-size": f"{ui.get('iconSize', 38)}px",
             "--name-size": f"{ui.get('nameSize', 18)}px",
             "--sub-size": f"{ui.get('subSize', 15)}px"}
        if ui.get("font"):
            v["--font"] = ui["font"]
        return {k: val for k, val in v.items() if val}

    def resolve_profile(self, pid: str | None) -> dict:
        """Aufgeloestes Panel-Profil: Theme-Vars, Tabs, Raum-/Kategorie-Filter."""
        prof = self.panels.get(pid or "") or self.panels.get("default") or {}
        ui = {**self.theme.get("ui", {}), **(prof.get("ui") or {})}
        states = {**self.theme.get("states", {}), **(prof.get("states") or {})}
        tabs = prof.get("tabs") or ui.get("tabs") or \
            ["favoriten", "zentral", "raeume", "kategorien"]
        return {
            "id": pid or "default",
            "title": prof.get("title") or "LoxPanel",
            "tabs": list(tabs),
            "rooms": self._resolve_ids(prof.get("rooms"), self.rooms),
            "cats": self._resolve_ids(prof.get("cats"), self.cats),
            "vars": self._theme_vars(states, ui),
            "tiles": prof.get("tiles") or {},
        }

    def _room_ok(self, uuid: str, prof: dict | None) -> bool:
        ar = prof.get("rooms") if prof else None
        if ar is None:
            return True
        return self.controls.get(uuid, {}).get("room") in ar

    # ---- Config-Seite (Panel-Editor) ----
    def _panel_export(self, raw: dict) -> dict:
        """Rohes Profil aus der Datei -> UI-Form (rooms/cats als UUID-Listen,
        in Anzeige-Reihenfolge; leere Liste = alle)."""
        r = self._resolve_ids(raw.get("rooms"), self.rooms)
        c = self._resolve_ids(raw.get("cats"), self.cats)
        tabs = [t for t in (raw.get("tabs") or VALID_TABS) if t in VALID_TABS]
        return {
            "title": raw.get("title") or "",
            "tabs": tabs or list(VALID_TABS),
            "rooms": [u for u in self.rooms_with if r and u in r],
            "cats": [u for u in self.cats_with if c and u in c],
            "ui": {k: v for k, v in (raw.get("ui") or {}).items()
                   if k in ("iconSize", "nameSize", "subSize", "font")},
            "states": {k: v for k, v in (raw.get("states") or {}).items()
                       if k in ("active", "good", "warn", "crit")},
            "tiles": raw.get("tiles") if isinstance(raw.get("tiles"), dict) else {},
        }

    def _loxone_icons(self) -> list:
        """Alle im Struktur-Baum referenzierten Loxone-Icon-Pfade (für den Picker)."""
        paths = set()
        for c in self.controls.values():
            di = (c.get("details") or {}).get("image")
            if isinstance(di, str):
                paths.add(di)
            elif isinstance(di, dict):
                for v in (di.get("on"), di.get("off")):
                    if isinstance(v, str):
                        paths.add(v)
        for table in (self.cats, self.rooms):
            for v in table.values():
                im = v.get("image")
                if isinstance(im, str):
                    paths.add(im)
        return sorted(p for p in paths if p.endswith(".svg") or p.endswith(".png"))

    @staticmethod
    def _sanitize_panels(panels: dict) -> dict:
        out: dict = {}
        for pid, p in panels.items():
            if not isinstance(pid, str) or not pid or pid.startswith("_") or not isinstance(p, dict):
                continue
            e: dict = {}
            if p.get("title"):
                e["title"] = str(p["title"])[:40]
            tabs = [t for t in (p.get("tabs") or []) if t in VALID_TABS]
            e["tabs"] = tabs or list(VALID_TABS)
            e["rooms"] = [str(x) for x in (p.get("rooms") or []) if isinstance(x, str)]
            e["cats"] = [str(x) for x in (p.get("cats") or []) if isinstance(x, str)]
            ui = p.get("ui") or {}
            cui = {k: ui[k] for k in ("iconSize", "nameSize", "subSize")
                   if isinstance(ui.get(k), (int, float))}
            if ui.get("font"):
                cui["font"] = str(ui["font"])[:120]
            if cui:
                e["ui"] = cui
            st = p.get("states") or {}
            cst = {k: str(st[k]) for k in ("active", "good", "warn", "crit")
                   if isinstance(st.get(k), str)}
            if cst:
                e["states"] = cst
            tiles = p.get("tiles")
            if isinstance(tiles, dict):
                ct = {}
                for cu, ov in tiles.items():
                    if not isinstance(cu, str) or not isinstance(ov, dict):
                        continue
                    e2 = {}
                    for k in ("iconColor", "textColor", "bg", "border"):
                        if _color_ok(ov.get(k)):
                            e2[k] = ov[k].strip()
                    if ov.get("font"):
                        e2["font"] = str(ov["font"])[:120]
                    for bk in ("bold", "italic"):
                        if ov.get(bk) is True:
                            e2[bk] = True
                    icc = _clean_icon(ov.get("icon"))
                    if icc:
                        e2["icon"] = icc
                    if e2:
                        ct[cu] = e2
                if ct:
                    e["tiles"] = ct
            out[pid] = e
        return out

    def _write_panels(self, panels: dict) -> None:
        doc = {"_comment": "Von der LoxPanel-Konfigurationsseite (/config) verwaltet. "
                           "Jedes Panel oeffnet die Visu mit ?panel=<id>. "
                           "rooms/cats leer = alle sichtbar.",
               "panels": panels}
        PANELS_FILE.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n",
                               encoding="utf-8")
        self.panels = load_panels()

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
    def _control_item(self, uuid: str, prof: dict | None = None) -> dict:
        c = self.controls.get(uuid)
        if not c:
            return {"id": uuid, "label": "?", "icon": "info", "on": False}
        t = c.get("type")
        name = _clean(c.get("name"))
        it: dict = {"id": uuid, "label": name, "on": False, "icon": "info"}
        if c.get("isSecured"):
            it["secured"] = True
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
        elif t == "Radio":
            outs = (c.get("details") or {}).get("outputs") or {}
            aoi = int(self._state(c, "activeOutput") or 0)
            it.update(icon="switch", nav={"view": "control", "id": uuid},
                      sublabel=(outs.get(str(aoi)) or ("–" if aoi == 0 else f"Ausgang {aoi}")))
        elif t == "LightController":
            scenes = self._lc_scenes(c)
            asc = int(self._state(c, "activeScene") or 0)
            it.update(icon="bulb", on=asc != 0, nav={"view": "control", "id": uuid},
                      sublabel=(scenes.get(asc) or ("Aus" if asc == 0 else f"Szene {asc}")))
        elif t == "PresenceDetector":
            on = bool(self._state(c, "active"))
            itxt = self._text(c, "infoText")
            it.update(icon="info", on=on,
                      sublabel=(itxt if itxt and itxt.lower() not in ("on", "off")
                                else ("Anwesend" if on else "Abwesend")))
        elif t == "WindowMonitor":
            op = int(self._state(c, "numOpen") or 0) + int(self._state(c, "numTilted") or 0)
            it.update(icon="blind", on=op > 0, nav={"view": "control", "id": uuid},
                      sublabel=(f"{op} offen" if op else "Alle geschlossen"))
        elif t == "Alarm":
            armed = bool(self._state(c, "armed"))
            lvl = self._state(c, "level") or 0
            it.update(icon="alarm", on=armed, tone=("crit" if lvl else None),
                      sublabel=("Alarm!" if lvl else ("Scharf" if armed else "Unscharf")))
        elif t == "AcControl":
            modes = self._json_list_map(c, "operatingModes")
            tt = self._fmt_num(self._state(c, "targetTemperature"), "%.1f")
            it.update(icon="thermo", on=(self._state(c, "status") or 0) != 0,
                      sublabel=(" · ".join(x for x in (modes.get(int(self._state(c, "mode") or 0)),
                                                       (tt + " °C" if tt else "")) if x) or "Klima"))
        elif t == "ClimateControllerUS":
            it.update(icon="thermo", sublabel="Klimasteuerung")
        elif t == "SystemScheme":
            it.update(icon="info", sublabel="Anlagenschema")
        elif t == "Hourcounter":
            it["sublabel"] = ("Wartung fällig" if self._state(c, "overdue")
                              else self._fmt_num(self._state(c, "total"), "%.0f h"))
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
            elif t == "CentralGate":
                n = sum(1 for mu in muuids if (self._state(self.controls[mu], "position") or 0) > 0)
                it["sublabel"] = f"{n} offen" if n else "Alle geschlossen"
            elif t == "CentralJalousie":
                it["sublabel"] = "Beschattung"
            elif t == "CentralAlarm":
                it["sublabel"] = "Alarmzentrale"
            it.setdefault("sublabel", "Zentral")
            it.update(icon="central", on=(n > 0),
                      nav={"view": "group", "kind": "central", "id": uuid})
        return self._apply_tile_style(it, uuid, prof)

    def _apply_tile_style(self, it: dict, uuid: str, prof: dict | None) -> dict:
        """Pro-Kachel-Overrides (Farben/Icon/Schrift) aus dem Panel-Profil."""
        ov = (prof.get("tiles") if prof else {}).get(uuid) if prof else None
        if not isinstance(ov, dict):
            return it
        if ov.get("iconColor"):
            it["color"] = ov["iconColor"]           # Icon-Farbe (--ico)
            it["colorFixed"] = ov["iconColor"]      # gewinnt auch im Aktiv-Zustand
        style = {}
        for src, dst in (("bg", "bg"), ("border", "border"),
                         ("textColor", "txt"), ("font", "font")):
            if ov.get(src):
                style[dst] = ov[src]
        if ov.get("bold"):
            style["weight"] = 700
        if ov.get("italic"):
            style["italic"] = True
        if style:
            it["style"] = style
        ic = ov.get("icon")
        if isinstance(ic, dict):
            s = ic.get("src")
            if s == "builtin" and ic.get("id"):
                it["icon"] = ic["id"]
                it.pop("iconUrl", None)
                it.pop("iconImg", None)
            elif s == "loxone" and ic.get("p"):
                u = self._icon_url(ic["p"])
                if u:
                    it["iconUrl"] = u
                    it.pop("iconImg", None)
            elif s == "google" and ic.get("name"):
                it["iconUrl"] = "/gicon?name=" + quote(str(ic["name"]))
                it.pop("iconImg", None)
            elif s == "custom" and ic.get("file"):
                it["iconImg"] = "/uicon?f=" + quote(str(ic["file"]))
                it.pop("iconUrl", None)
        return it

    # ---- Views ----
    def _view_tab(self, tab: str, prof: dict | None = None) -> dict:
        ar = prof.get("rooms") if prof else None
        ac = prof.get("cats") if prof else None
        if tab == "favoriten":
            items = [self._control_item(u, prof) for u, c in self.controls.items()
                     if c.get("isFavorite") and self._room_ok(u, prof)]
            title = "Favoriten"
        elif tab == "zentral":
            items = [self._control_item(u, prof) for u, c in self.controls.items()
                     if (c.get("type") or "").startswith("Central")]
            title = "Zentral"
        elif tab == "raeume":
            rooms = [ru for ru in self.rooms_with if ar is None or ru in ar]
            items = [{"id": ru, "label": _clean(self.rooms[ru].get("name")), "icon": "folder",
                      "iconUrl": self._icon_url(self.rooms[ru].get("image")),
                      "on": False, "nav": {"view": "group", "kind": "room", "id": ru}}
                     for ru in rooms]
            title = "Räume"
        else:
            if ac is not None:
                cats = [cu for cu in self.cats_with if cu in ac]
            elif ar is not None:
                present = {c.get("cat") for c in self.controls.values() if c.get("room") in ar}
                cats = [cu for cu in self.cats_with if cu in present]
            else:
                cats = list(self.cats_with)
            items = [{"id": cu, "label": _clean(self.cats[cu].get("name")), "icon": "folder",
                      "iconUrl": self._icon_url(self.cats[cu].get("image")),
                      "color": self._cat_color(cu),
                      "on": False, "nav": {"view": "group", "kind": "cat", "id": cu}}
                     for cu in cats]
            title = "Kategorien"
        return {"t": "view", "title": title, "tab": tab, "route": {"view": "tab", "tab": tab},
                "items": items}

    def _view_group(self, route: dict, prof: dict | None = None) -> dict:
        kind, gid = route.get("kind"), route.get("id")
        layout = None
        if kind == "cat":
            uuids = [u for u, c in self.controls.items()
                     if c.get("cat") == gid and self._room_ok(u, prof)]
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
                "layout": layout, "items": [self._control_item(u, prof) for u in uuids]}

    def _view_sources(self, uuid: str) -> dict:
        """Musikauswahl einer AudioZone: feste Rubriken (immer sichtbar, auch leer).

        'Favoriten' = die Zonen-Favoriten (roomfavs, vom Miniserver). 'Playlisten'
        ist vorerst ein Platzhalter (Bibliothek/Playlisten liegen im Audioserver
        und werden noch nicht abgefragt).
        """
        c = self.controls.get(uuid, {})
        ua = c.get("uuidAction")
        favs = self._audio_favs(c)

        def strip(items):
            return {"k": "favs", "wrap": True, "items": [
                {"label": f["name"], "cmd": {"uuid": ua, "cmd": f"roomfav/play/{f['slot']}"},
                 "cover": ("/cover?u=" + quote(f["cover"], safe="")) if f["cover"] else ""}
                for f in items]}

        empty = {"k": "status", "text": "noch keine – im Tablet / der App anlegen"}
        blocks = [{"k": "title", "text": _clean(c.get("name")), "sub": "Musikauswahl"},
                  {"k": "head", "text": "Favoriten"},
                  strip(favs) if favs else dict(empty),
                  {"k": "head", "text": "Playlisten"},
                  dict(empty)]
        return {"t": "view", "title": _clean(c.get("name")),
                "route": {"view": "sources", "id": uuid}, "blocks": blocks}

    def _view_control(self, uuid: str) -> dict:
        v = self._view_control_inner(uuid)
        if self.controls.get(uuid, {}).get("isSecured"):
            v["secured"] = True   # Client fragt vor Befehlen die Visu-PIN ab
        return v

    def _view_control_inner(self, uuid: str) -> dict:
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
        if t == "Radio":
            ua = c.get("uuidAction")
            det = c.get("details") or {}
            outs = det.get("outputs") or {}
            ao = int(self._state(c, "activeOutput") or 0)
            items = []
            if det.get("allOff"):
                items.append({"id": f"{uuid}:0", "label": det["allOff"], "on": ao == 0,
                              "icon": "stop", "cmd": {"uuid": ua, "cmd": "reset"}})
            for k in sorted(outs, key=lambda x: int(x)):
                items.append({"id": f"{uuid}:{k}", "label": outs[k], "on": ao == int(k),
                              "icon": "mood", "cmd": {"uuid": ua, "cmd": str(k)}})
            return {"t": "view", "title": _clean(c.get("name")), "route": route,
                    "layout": "list", "items": items}
        if t == "LightController":
            ua = c.get("uuidAction")
            scenes = self._lc_scenes(c)
            asc = int(self._state(c, "activeScene") or 0)
            items = [{"id": f"{uuid}:0", "label": "Aus", "on": asc == 0, "icon": "stop",
                      "cmd": {"uuid": ua, "cmd": "0"}}]
            for sid in sorted(scenes):
                items.append({"id": f"{uuid}:{sid}", "label": scenes[sid], "on": asc == sid,
                              "icon": "mood", "cmd": {"uuid": ua, "cmd": str(sid)}})
            return {"t": "view", "title": _clean(c.get("name")), "route": route,
                    "layout": "list", "items": items}
        if t == "WindowMonitor":
            windows = (c.get("details") or {}).get("windows") or []
            codes = [x for x in str(self._state(c, "windowStates") or "").split(",") if x != ""]

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
            if self._audio_favs(c):   # Quellen (Radio/Playlist/Spotify) auf Unterseite
                blocks.append({"k": "more", "route": {"view": "sources", "id": uuid}})
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
                     [{"k": "status", "text": "Kein Video konfiguriert (loxpanel.cfg → intercom)"}]
            if cells:
                blocks.append({"k": "row", "cells": cells})
            return {"t": "view", "title": _clean(c.get("name")), "route": route, "blocks": blocks}
        return {"t": "view", "title": _clean(c.get("name")), "route": route,
                "items": [self._control_item(uuid)]}

    def render(self, route: dict, prof: dict | None = None) -> dict:
        v = (route or {}).get("view", "tab")
        if v == "group":
            return self._view_group(route, prof)
        if v == "control":
            return self._view_control(route.get("id"))
        if v == "sources":
            return self._view_sources(route.get("id"))
        return self._view_tab(route.get("tab", "favoriten"), prof)

    async def command(self, uuid: str, cmd: str, pin: str | None = None) -> str | None:
        """Fuehrt einen Befehl aus. Mit pin: gesicherter Befehl (Visu-Passwort)."""
        if not (self.client and uuid and cmd):
            return None
        try:
            if pin is not None:
                return await self._secured_command(uuid, cmd, pin)
            log.info("cmd %s/%s", uuid, cmd)
            await self.client.jdev_get(f"sps/io/{uuid}/{cmd}")
            return "200"
        except Exception as err:  # Befehl darf den Server nicht killen
            log.warning("cmd fehlgeschlagen: %s", err)
            return None

    async def _secured_command(self, uuid: str, cmd: str, pin: str) -> str | None:
        """Loxone secured-command: getvisusalt -> Hash(visuPw:salt) -> HMAC(key) -> ios."""
        r = await self.client.jdev_get(f"sys/getvisusalt/{quote(self.user)}")
        val = (r.get("LL") or {}).get("value") or {}
        key, salt = val.get("key", ""), val.get("salt", "")
        alg = (val.get("hashAlg") or "SHA1").upper()
        digest = hashlib.sha256 if alg == "SHA256" else hashlib.sha1
        pwhash = digest(f"{pin}:{salt}".encode()).hexdigest().upper()
        h = hmac.new(bytes.fromhex(key), pwhash.encode(), digest).hexdigest()
        resp = await self.client.jdev_get(f"sps/ios/{h}/{uuid}/{cmd}")
        ll = resp.get("LL") or {}
        code = str(ll.get("Code") or ll.get("code") or "")
        log.info("secured cmd %s/%s -> Code %s", uuid, cmd, code)
        return code

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
                        await ws.send_json(self.render(route, self.conn_prof.get(ws)))
                    except ConnectionError:
                        self.conn_route.pop(ws, None)
                        self.conn_prof.pop(ws, None)

    async def close(self) -> None:
        if self.ws:
            await self.ws.close()
        if self.icon_session:
            await self.icon_session.close()
        if self.client:
            await self.client.close()


async def index(request: web.Request) -> web.Response:
    return web.Response(text=HTML.read_text(encoding="utf-8"), content_type="text/html")


async def config_index(request: web.Request) -> web.Response:
    return web.Response(text=CONFIG_HTML.read_text(encoding="utf-8"), content_type="text/html")


async def api_meta(request: web.Request) -> web.Response:
    """Alle Räume/Kategorien der Anlage + aktuelle Profile (für den Editor)."""
    app: App = request.app["app"]
    rooms = [{"uuid": ru, "name": _clean(app.rooms[ru].get("name", ""))} for ru in app.rooms_with]
    cats = [{"uuid": cu, "name": _clean(app.cats[cu].get("name", ""))} for cu in app.cats_with]
    panels = {pid: app._panel_export(raw) for pid, raw in app.panels.items()}
    controls = []
    for u, c in app.controls.items():
        if not c.get("name"):
            continue
        room = c.get("room")
        controls.append({
            "uuid": u, "name": _clean(c.get("name")), "type": c.get("type"),
            "room": room,
            "roomName": _clean((app.rooms.get(room) or {}).get("name", "")) if room else "",
            "iconUrl": app._control_icon_url(c),
        })
    return web.json_response({
        "rooms": rooms, "cats": cats, "controls": controls,
        "icons": {"loxone": app._loxone_icons()},
        "tabs": [{"tab": "favoriten", "label": "Favoriten"},
                 {"tab": "zentral", "label": "Zentral"},
                 {"tab": "raeume", "label": "Räume"},
                 {"tab": "kategorien", "label": "Kategorien"}],
        "panels": panels,
    })


async def api_save_panels(request: web.Request) -> web.Response:
    app: App = request.app["app"]
    try:
        data = await request.json()
    except (ValueError, aiohttp.ContentTypeError):
        return web.json_response({"ok": False, "error": "kein gültiges JSON"}, status=400)
    panels = data.get("panels")
    if not isinstance(panels, dict):
        return web.json_response({"ok": False, "error": "Feld 'panels' fehlt"}, status=400)
    clean = App._sanitize_panels(panels)
    try:
        app._write_panels(clean)
    except OSError as err:
        return web.json_response({"ok": False, "error": str(err)}, status=500)
    log.info("panels.json gespeichert: %d Profile", len(clean))
    return web.json_response({"ok": True, "count": len(clean)})


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
    prof = app.resolve_profile(request.query.get("panel", ""))
    app.conn_prof[ws] = prof
    first_tab = prof["tabs"][0] if prof["tabs"] else "favoriten"
    app.conn_route[ws] = {"view": "tab", "tab": first_tab}
    log.info("Panel verbunden: '%s' (Tabs %s, Räume %s, Kategorien %s)", prof["id"],
             prof["tabs"], "alle" if prof["rooms"] is None else len(prof["rooms"]),
             "alle" if prof["cats"] is None else len(prof["cats"]))
    await ws.send_json({"t": "theme", "vars": prof["vars"], "tabs": prof["tabs"],
                        "title": prof["title"]})
    await ws.send_json(app.render(app.conn_route[ws], prof))
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
                await ws.send_json(app.render(data["route"], prof))
            elif data.get("t") == "cmd":
                pin = data.get("pin")
                code = await app.command(data.get("uuid"), data.get("cmd"), pin)
                if pin is not None:
                    await ws.send_json({"t": "cmdresult", "ok": code == "200"})
    finally:
        app.conn_route.pop(ws, None)
        app.conn_prof.pop(ws, None)
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
    a.router.add_get("/config", config_index)
    a.router.add_get("/api/meta", api_meta)
    a.router.add_post("/api/panels", api_save_panels)
    a.router.add_get("/icon", icon_handler)
    a.router.add_get("/cover", cover_handler)
    a.router.add_get("/mjpeg", mjpeg_handler)
    a.router.add_get("/ws", ws_handler)
    a.on_startup.append(on_startup)
    a.on_cleanup.append(on_cleanup)
    web.run_app(a, host="0.0.0.0", port=args.port)


if __name__ == "__main__":
    main()
