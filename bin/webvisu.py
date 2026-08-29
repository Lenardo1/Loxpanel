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
import os
import re
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

import ssl as _ssl
from urllib.parse import quote, unquote

import aiohttp
from aiohttp import WSMsgType, web

sys.path.insert(0, str(Path(__file__).resolve().parent))
from loxone_api import LoxoneClient  # noqa: E402
from loxone_ws import LoxoneWS  # noqa: E402
from adapters import JalousieAdapter, LightControllerV2Adapter  # noqa: E402
from audioserver import make_backend, AudioBackend  # noqa: E402

log = logging.getLogger("loxpanel.webvisu")
_WEB = Path(__file__).resolve().parent.parent / "webfrontend" / "html"
HTML = _WEB / "panel.html"
CONFIG_HTML = _WEB / "config.html"
SETTINGS_HTML = _WEB / "settings.html"
INSTALL_SH = Path(__file__).resolve().parent.parent / "deploy" / "install-agent.sh"
_CFGDIR = Path(__file__).resolve().parent.parent / "config"
PANELS_FILE = _CFGDIR / "panels.json"
CFG_FILE = _CFGDIR / "loxpanel.cfg"
CFG_EXAMPLE = _CFGDIR / "loxpanel.cfg.example"


def _load_cfg() -> dict:
    for f in (CFG_FILE, CFG_EXAMPLE):
        if f.is_file():
            try:
                return json.loads(f.read_text(encoding="utf-8"))
            except ValueError:
                pass
    return {}


def _write_cfg(cfg: dict) -> None:
    CFG_FILE.write_text(json.dumps(cfg, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
LIGHT = LightControllerV2Adapter()
JAL = JalousieAdapter()

SWITCHY = {"Switch"}   # TimedSwitch wird eigen behandelt (anderer State)
VALID_TABS = ["favoriten", "zentral", "raeume", "kategorien"]


def _is_tab(t) -> bool:
    """Gueltiges Tab-Kennzeichen: einer der 4 Standard-Tabs ODER eine einzelne
    Kategorie als Direkt-Tab (`cat:<uuid>`)."""
    return t in VALID_TABS or (isinstance(t, str) and t.startswith("cat:") and len(t) > 4)
# Reine Anzeige-Bausteine: keine Steuer-2.-Ebene -> Antippen zeigt eine
# grosse 1/1-Wertseite (_view_control -> _big_view).
STATUS_BIG = {"Meter", "InfoOnlyAnalog", "TextState", "InfoOnlyText",
              "InfoOnlyDigital", "SmokeAlarm", "PresenceDetector",
              "ClimateControllerUS", "Hourcounter"}
# Reine Wert-/Analog-Anzeigen (kein an/aus) -> keine Kategorie-Ampel, neutral.
_ANALOG = {"InfoOnlyAnalog", "Slider", "Meter", "TextState", "InfoOnlyText", "Hourcounter"}
_COLOR_RE = re.compile(r"^(#[0-9a-fA-F]{3,8}|rgba?\([0-9.,%\s]+\)|[a-zA-Z]{3,20})$")
# Tracker-Zeile: fuehrender Zeitstempel (TT.MM.JJ[JJ] HH:MM[:SS]) wird vom Text
# getrennt, damit er als Untertitel erscheint. Matcht sonst nichts -> ganze Zeile.
_TS_RE = re.compile(r"^\s*(\d{1,2}[.\-/]\d{1,2}[.\-/]\d{2,4}[ ,]+\d{1,2}:\d{2}(?::\d{2})?)\s+(.+)$")


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


def _hex_rgb(value) -> str | None:
    """#RRGGBB / #RGB -> \"r,g,b\" (fuer rgba() mit variabler Deckkraft). None bei ungueltig."""
    h = str(value or "").lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    if len(h) != 6:
        return None
    try:
        return f"{int(h[0:2], 16)},{int(h[2:4], 16)},{int(h[4:6], 16)}"
    except ValueError:
        return None


def _overlay_alphas(ov: dict) -> tuple[float, float, int]:
    """Overlay-Config -> (Fuellung-Alpha, Rahmen-Alpha, Rahmenbreite px).

    Defaults entsprechen dem bisherigen fest verdrahteten Aussehen. `mode`
    schaltet Fuellung bzw. Rahmen komplett ab (Rahmen/Fuellung/Beides).
    """
    ov = ov if isinstance(ov, dict) else {}
    def _num(key, default):
        try:
            return float(ov.get(key, default))
        except (TypeError, ValueError):
            return float(default)
    fill = max(0.0, min(1.0, _num("fill", 16) / 100.0))
    bord = max(0.0, min(1.0, _num("bord", 55) / 100.0))
    bw = max(1, min(4, int(_num("bw", 1))))
    mode = ov.get("mode")
    if mode == "border":
        fill = 0.0
    elif mode == "fill":
        bord = 0.0
    return fill, bord, bw


def _sanitize_overlay(ov) -> dict:
    """Overlay-Config aus der Config-Seite auf erlaubte Werte eindampfen."""
    if not isinstance(ov, dict):
        return {}
    out: dict = {}
    if ov.get("mode") in ("both", "border", "fill"):
        out["mode"] = ov["mode"]
    for k in ("fill", "bord"):
        if isinstance(ov.get(k), (int, float)):
            out[k] = max(0, min(100, int(ov[k])))
    if isinstance(ov.get("bw"), (int, float)):
        out["bw"] = max(1, min(4, int(ov["bw"])))
    return out


def _config() -> dict:
    # Reihenfolge: geschriebene loxpanel.cfg (Settings-Seite) -> Env (Docker) -> Beispiel.
    base = Path(__file__).resolve().parent.parent / "config"
    f = base / "loxpanel.cfg"
    if f.is_file():
        try:
            ms = json.loads(f.read_text(encoding="utf-8")).get("miniserver", {})
        except ValueError:
            ms = {}
        if ms.get("host"):
            return ms
    env = os.environ
    if env.get("LOXPANEL_MS_HOST"):
        return {
            "host": env["LOXPANEL_MS_HOST"],
            "user": env.get("LOXPANEL_MS_USER", ""),
            "pass": env.get("LOXPANEL_MS_PASS", ""),
            "port": int(env.get("LOXPANEL_MS_PORT", "443")),
            "verify_tls": env.get("LOXPANEL_MS_VERIFY_TLS", "false").lower() in ("1", "true", "yes"),
        }
    return json.loads((base / "loxpanel.cfg.example").read_text(encoding="utf-8")).get("miniserver", {})


def _audio_config() -> dict:
    """Audio-Backend-Config (Loxone-Audioserver / MS4H auf Port 7091).

    Aus loxpanel.cfg `audio`-Block: {"host": "10.0.2.2", "port": 7091}.
    Fehlt `host`, wird er aus einer roomfav-Cover-URL abgeleitet (die zeigen
    auf den Audioserver, z.B. http://10.0.2.2:7092/...), sobald verfügbar.
    """
    base = Path(__file__).resolve().parent.parent / "config"
    f = base / "loxpanel.cfg"
    if not f.is_file():
        f = base / "loxpanel.cfg.example"
    try:
        cfg = json.loads(f.read_text(encoding="utf-8")).get("audio", {})
    except ValueError:
        return {}
    return cfg if isinstance(cfg, dict) else {}


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
    base = Path(__file__).resolve().parent.parent / "config"
    f = base / "theme.json"
    if not f.is_file():
        f = base / "theme.example.json"   # Vorlage fuer frische Installationen
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
    def __init__(self, ms: dict, audio: dict | None = None):
        self.host, self.port = ms["host"], ms.get("port", 443)
        self.user, self.password = ms["user"], ms["pass"]
        self.verify_tls = ms.get("verify_tls", False)

        self.audio_cfg = audio or {}
        self.audio: AudioBackend | None = make_backend(self.audio_cfg)
        # uuidAction -> Loxone-playerid (fuer Audioserver-Kommandos)
        self.playerid_by_action: dict[str, int] = {}

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
        # Wecker (AlarmClock): isAlarmActive-State-UUID -> Control-UUID. Flanke
        # 0->1/1->0 wird als {"t":"alarm",...} ans Panel gepusht (Weckton an/aus).
        self.alarm_map: dict[str, str] = {}
        self._alarm_prev: dict[str, object] = {}
        self._pending_alarm: list[dict] = []
        self.agents: dict[str, dict] = {}   # ip -> Panel-Agent (Fernstart)
        self.bg_tasks: set = set()          # laufende Hintergrund-Tasks (z.B. Favs anfordern)

    def _ssl_ctx(self) -> _ssl.SSLContext:
        ctx = _ssl.SSLContext(_ssl.PROTOCOL_TLS_CLIENT)
        if not self.verify_tls:
            ctx.check_hostname = False
            ctx.verify_mode = _ssl.CERT_NONE
        return ctx

    def _apply_structure(self, st: dict) -> None:
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
        self.alarm_map = {}
        # Betriebsarten (id -> Name) fuer die Wecker-Wiederholung: die `modes`
        # eines Eintrags verweisen hierauf (z.B. Wochentage Mo-So).
        self.op_modes = {str(k): v for k, v in (st.get("operatingModes") or {}).items()}
        self.playerid_by_action = {}
        for _u, _c in self.controls.items():
            if _c.get("type") == "Intercom":
                _bu = (_c.get("states") or {}).get("bell")
                if _bu:
                    self.bell_map[_bu] = _u
            elif _c.get("type") == "AlarmClock":
                _au = (_c.get("states") or {}).get("isAlarmActive")
                if _au:
                    self.alarm_map[_au] = _u
            elif _c.get("type") == "AudioZone":
                _pid = (_c.get("details") or {}).get("playerid")
                _ua = _c.get("uuidAction")
                if _ua and _pid is not None:
                    self.playerid_by_action[_ua] = int(_pid)
        log.info("Struktur: %d Controls, %d Räume, %d Kategorien, %d Intercom-Klingeln, %d Wecker, %d AudioZones",
                 len(self.controls), len(self.rooms_with), len(self.cats_with),
                 len(self.bell_map), len(self.alarm_map), len(self.playerid_by_action))

    async def start(self) -> None:
        try:
            self.client = LoxoneClient(host=self.host, user=self.user, password=self.password,
                                       port=self.port, verify_tls=self.verify_tls)
            await self.client.__aenter__()
            self.alg = (await self.client.getkey2()).hashAlg
            self.jwt = await self.client.authenticate()
            self._apply_structure(await self.client.load_structure())
            self.icon_session = aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=self._ssl_ctx()))
            await self._connect_ws()
            log.info("Mit Miniserver verbunden (%s).", self.host)
        except Exception:
            await self._close_conn()   # sauber zuruecksetzen, damit Retry neu aufbaut
            raise

    async def _close_conn(self) -> None:
        for c in (self.ws, self.icon_session, self.client):
            try:
                if c:
                    await c.close()
            except Exception:
                pass
        self.ws = self.icon_session = self.client = None

    async def reconnect(self) -> int:
        """Verbindung mit (ge-aenderter) Config neu aufbauen. Gibt Control-Anzahl
        zurueck; wirft bei falschen Zugangsdaten. Alte Verbindung bleibt bei
        Fehler bestehen (neuer Client wird nur bei Erfolg uebernommen)."""
        ms = _config()
        newc = LoxoneClient(host=ms["host"], user=ms["user"], password=ms["pass"],
                            port=ms.get("port", 443), verify_tls=ms.get("verify_tls", False))
        try:
            await newc.__aenter__()
            alg = (await newc.getkey2()).hashAlg
            jwt = await newc.authenticate()
            st = await newc.load_structure()
        except Exception:
            try:
                await newc.close()
            except Exception:
                pass
            raise
        # Erfolg -> uebernehmen
        self.host, self.port = ms["host"], ms.get("port", 443)
        self.user, self.password = ms["user"], ms["pass"]
        self.verify_tls = ms.get("verify_tls", False)
        old_client, self.client = self.client, newc
        self.alg, self.jwt = alg, jwt
        self._apply_structure(st)
        self.states = {}
        old_is, self.icon_session = self.icon_session, \
            aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=self._ssl_ctx()))
        self.icon_cache = {}
        old_ws, self.ws = self.ws, None   # stream_task baut WS mit neuen Daten neu auf
        self.intercom_cfg = _intercom_config()
        self._dirty = True
        for closer in (old_client, old_is, old_ws):
            try:
                if closer:
                    await closer.close()
            except Exception:
                pass
        return len(self.controls)

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

    def _tracker_lines(self, control: dict) -> list[str]:
        """Ereignis-Zeilen eines Tracker-Bausteins (State 'entries'). Loxone
        liefert einen mehrzeiligen, ggf. prozentkodierten Text; neueste zuerst.
        Der Zeilentrenner variiert je nach Firmware: echtes Newline, Literal
        "\\n"/"\\r" (Backslash+Buchstabe) oder CR -> alle normalisieren, sonst
        landet der ganze Verlauf in EINER Zeile."""
        raw = self._state(control, "entries")
        if raw in (None, ""):
            return []
        txt = unquote(str(raw))
        for sep in ("\r\n", "\\r\\n", "\\n", "\\r", "\r"):
            txt = txt.replace(sep, "\n")
        return [ln.strip() for ln in txt.split("\n") if ln.strip()]

    @staticmethod
    def _split_ts(line: str) -> tuple[str | None, str]:
        """Fuehrenden Zeitstempel abtrennen -> (zeitstempel|None, text)."""
        m = _TS_RE.match(line or "")
        return (m.group(1), m.group(2)) if m else (None, line or "")

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
        if c.get("type") != "AudioZone":
            return
        ua = c.get("uuidAction")
        if ua:
            await self.command(ua, "roomfav/get/0/20")

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
        """Echtes Loxone-Icon eines Controls. Reihenfolge wie in der Loxone-App:
        control-eigenes Bild -> `defaultIcon` (hier legt Loxone das pro Control
        gewaehlte/GEAENDERTE Icon ab, auch eigene Uploads) -> Kategorie-Icon."""
        di = (c.get("details") or {}).get("image")
        if isinstance(di, str):
            img = di
        elif isinstance(di, dict):
            img = di.get("on") or di.get("off")
        else:
            img = None
        if not img:
            img = c.get("defaultIcon")      # pro-Control gewaehltes Icon (inkl. Aenderung/Upload)
        if not img:
            img = (self.cats.get(c.get("cat")) or {}).get("image")   # Kategorie als Fallback
        return self._icon_url(img)

    def _cat_entry(self, cat_uuid: str | None):
        """Passender categories-Eintrag (Match: Schluessel als Teilstring des
        Kategorienamens). Rueckgabe: str (nur Icon-Farbe) | dict {on,off}
        (Zustandsfarben) | None."""
        name = _clean((self.cats.get(cat_uuid) or {}).get("name") or "").lower()
        if not name:
            return None
        for key, val in self.theme.get("categories", {}).items():
            if not key.startswith("_") and key.lower() in name:
                return val
        return None

    def _cat_color(self, cat_uuid: str | None) -> str | None:
        val = self._cat_entry(cat_uuid)
        if isinstance(val, dict):
            return val.get("on") or val.get("off")   # Icon-Farbe = Aktiv-Farbe
        return val if isinstance(val, str) else None

    def _cat_states(self, cat_uuid: str | None):
        """Zustandsfarben {on, off} einer Kategorie (Ampel) oder None."""
        val = self._cat_entry(cat_uuid)
        return val if isinstance(val, dict) else None

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
             "--sub-size": f"{ui.get('subSize', 15)}px",
             "--name-weight": "700" if ui.get("bold") else "450"}
        # Zustands-Farben zusaetzlich als R,G,B-Tripel, damit das Aktiv-Overlay
        # (Fuellung/Rahmen) die konfigurierte Farbe mit variabler Deckkraft nutzt.
        for skey, rvar in (("active", "--on-rgb"), ("good", "--good-rgb"),
                           ("crit", "--crit-rgb"), ("warn", "--warn-rgb")):
            rgb = _hex_rgb(states.get(skey))
            if rgb:
                v[rvar] = rgb
        # Aussehen des Aktiv-Overlays (global fuers Panel; pro Kachel ueberschreibbar).
        if isinstance(ui.get("overlay"), dict):
            fill, bord, bw = _overlay_alphas(ui["overlay"])
            v["--ov-fill"] = f"{fill:.3g}"
            v["--ov-bord"] = f"{bord:.3g}"
            v["--ov-bw"] = f"{bw}px"
        if ui.get("font"):
            v["--font"] = ui["font"]
        if ui.get("textColor"):
            v["--name-color"] = ui["textColor"]
        if ui.get("cols") == 3:
            v["--cols"] = "3"          # 3x2-Kachelraster (Tablet); Default 2x2
        nudge = ui.get("nudgeX")
        if nudge not in (None, ""):
            # Horizontaler Feinversatz der ganzen Visu (px, negativ = nach links)
            # gegen Display-Overscan. Wird vom Frontend als --nudge-x angewandt.
            try:
                v["--nudge-x"] = f"{float(nudge):g}px"
            except (TypeError, ValueError):
                pass
        return {k: val for k, val in v.items() if val}

    def resolve_profile(self, pid: str | None) -> dict:
        """Aufgeloestes Panel-Profil: Theme-Vars, Tabs, Raum-/Kategorie-Filter."""
        prof = self.panels.get(pid or "") or self.panels.get("default") or {}
        ui = {**self.theme.get("ui", {}), **(prof.get("ui") or {})}
        states = {**self.theme.get("states", {}), **(prof.get("states") or {})}
        tabs = [t for t in (prof.get("tabs") or ui.get("tabs") or []) if _is_tab(t)] or \
            ["favoriten", "zentral", "raeume", "kategorien"]
        return {
            "id": pid or "default",
            "title": prof.get("title") or "LoxPanel",
            "tabs": list(tabs),
            "rooms": self._resolve_ids(prof.get("rooms"), self.rooms),
            "cats": self._resolve_ids(prof.get("cats"), self.cats),
            "vars": self._theme_vars(states, ui),
            "tiles": prof.get("tiles") or {},
            "hide": {u for u in (prof.get("hide") or []) if isinstance(u, str)},
        }

    def _tab_meta(self, tab_keys) -> dict:
        """Label + Icon fuer dynamische Tabs (Kategorie-Direkt-Tabs). Die 4
        Standard-Tabs kennt das Frontend selbst; hier nur die `cat:`-Tabs."""
        meta = {}
        for t in tab_keys or []:
            if isinstance(t, str) and t.startswith("cat:"):
                cat = self.cats.get(t[4:], {})
                meta[t] = {"label": _clean(cat.get("name")) or "Kategorie",
                           "iconUrl": self._icon_url(cat.get("image")) or ""}
        return meta

    def panel_dpms(self, pid: str | None):
        """Display-Abschaltzeit (Sek.) fuer ein Panel aus dem Profil (0=nie,
        None=nicht gesetzt -> Agent nutzt seinen kiosk.conf-Default). Wird dem
        Panel-Agenten in der Announce-Antwort mitgegeben (er fuehrt xset aus)."""
        ui = {**self.theme.get("ui", {}),
              **((self.panels.get(pid or "") or {}).get("ui") or {})}
        v = ui.get("dpmsOff")
        return max(0, min(3600, int(v))) if isinstance(v, (int, float)) else None

    def panel_reload(self, pid: str | None):
        """Auto-Neustart-Intervall (Stunden) fuer ein Panel aus dem Profil
        (0/None = aus). Gegen Einfrieren; der Agent startet Chromium periodisch
        neu. Wird in der Announce-Antwort mitgegeben."""
        ui = {**self.theme.get("ui", {}),
              **((self.panels.get(pid or "") or {}).get("ui") or {})}
        v = ui.get("reloadHours")
        return max(0, min(168, float(v))) if isinstance(v, (int, float)) else None

    def _room_ok(self, uuid: str, prof: dict | None) -> bool:
        ar = prof.get("rooms") if prof else None
        if ar is None:
            return True
        return self.controls.get(uuid, {}).get("room") in ar

    def _cat_ok(self, uuid: str, prof: dict | None) -> bool:
        ac = prof.get("cats") if prof else None
        if ac is None:
            return True
        return self.controls.get(uuid, {}).get("cat") in ac

    def _shown(self, uuid: str, prof: dict | None) -> bool:
        """False, wenn diese Kachel auf dem Panel einzeln ausgeblendet wurde
        (zusaetzlich zum Raum-/Kategorie-Filter). Gilt panelweit."""
        return not (prof and uuid in prof.get("hide", ()))

    # ---- Config-Seite (Panel-Editor) ----
    def _panel_export(self, raw: dict) -> dict:
        """Rohes Profil aus der Datei -> UI-Form (rooms/cats als UUID-Listen,
        in Anzeige-Reihenfolge; leere Liste = alle)."""
        r = self._resolve_ids(raw.get("rooms"), self.rooms)
        c = self._resolve_ids(raw.get("cats"), self.cats)
        tabs = [t for t in (raw.get("tabs") or VALID_TABS) if _is_tab(t)]
        return {
            "title": raw.get("title") or "",
            "tabs": tabs or list(VALID_TABS),
            "rooms": [u for u in self.rooms_with if r and u in r],
            "cats": [u for u in self.cats_with if c and u in c],
            "ui": {k: v for k, v in (raw.get("ui") or {}).items()
                   if k in ("iconSize", "nameSize", "subSize", "font", "nudgeX",
                            "dpmsOff", "reloadHours", "cols", "overlay", "textColor", "bold")},
            "states": {k: v for k, v in (raw.get("states") or {}).items()
                       if k in ("active", "good", "warn", "crit")},
            "tiles": raw.get("tiles") if isinstance(raw.get("tiles"), dict) else {},
            "hide": [u for u in (raw.get("hide") or [])
                     if isinstance(u, str) and u in self.controls],
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
            tabs = [t for t in (p.get("tabs") or []) if _is_tab(t)][:4]
            e["tabs"] = tabs or list(VALID_TABS)
            e["rooms"] = [str(x) for x in (p.get("rooms") or []) if isinstance(x, str)]
            e["cats"] = [str(x) for x in (p.get("cats") or []) if isinstance(x, str)]
            hide = [str(x) for x in (p.get("hide") or []) if isinstance(x, str)]
            if hide:
                e["hide"] = hide           # einzeln ausgeblendete Kacheln (panelweit)
            ui = p.get("ui") or {}
            cui = {k: ui[k] for k in ("iconSize", "nameSize", "subSize")
                   if isinstance(ui.get(k), (int, float))}
            if ui.get("font"):
                cui["font"] = str(ui["font"])[:120]
            if isinstance(ui.get("nudgeX"), (int, float)):
                cui["nudgeX"] = max(-40, min(40, ui["nudgeX"]))  # horiz. Versatz px
            if isinstance(ui.get("dpmsOff"), (int, float)):
                cui["dpmsOff"] = max(0, min(3600, int(ui["dpmsOff"])))  # Display aus nach Sek.
            if isinstance(ui.get("reloadHours"), (int, float)):
                cui["reloadHours"] = max(0, min(168, float(ui["reloadHours"])))  # Auto-Neustart Std.
            if ui.get("cols") in (2, 3):
                cui["cols"] = int(ui["cols"])   # Kacheln pro Zeile (2x2 oder 3x2)
            if _color_ok(ui.get("textColor")):
                cui["textColor"] = ui["textColor"].strip()   # globale Schriftfarbe (Name)
            if ui.get("bold"):
                cui["bold"] = True                            # Kachel-Namen fett
            ovc = _sanitize_overlay(ui.get("overlay"))
            if ovc:
                cui["overlay"] = ovc            # Aussehen des Aktiv-Overlays
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
                    tov = _sanitize_overlay(ov.get("overlay"))
                    if tov:
                        e2["overlay"] = tov     # Aktiv-Overlay nur fuer diese Kachel
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

    @staticmethod
    def _sanitize_theme_ui(ui: dict) -> dict:
        """Globale Darstellungs-ui (theme.json) validieren: nur bekannte Keys."""
        ui = ui or {}
        out: dict = {}
        for k in ("iconSize", "nameSize", "subSize"):
            if isinstance(ui.get(k), (int, float)):
                out[k] = max(8, min(80, int(ui[k])))
        if ui.get("font"):
            out["font"] = str(ui["font"])[:120]
        if _color_ok(ui.get("textColor")):
            out["textColor"] = ui["textColor"].strip()
        if ui.get("bold"):
            out["bold"] = True
        return out

    @staticmethod
    def _sanitize_categories(cats) -> dict:
        """categories aus dem Config-Editor validieren. Wert = Farbe (nur Icon)
        oder {on,off} (Zustands-Ampel). Ungueltiges/leeres wird verworfen."""
        out: dict = {}
        if not isinstance(cats, dict):
            return out
        for k, v in cats.items():
            k = str(k).strip()
            if not k or k.startswith("_"):
                continue
            if isinstance(v, dict):
                e = {}
                if _color_ok(v.get("on")):
                    e["on"] = str(v["on"]).strip()
                if _color_ok(v.get("off")):
                    e["off"] = str(v["off"]).strip()
                if e:
                    out[k[:40]] = e
            elif _color_ok(v):
                out[k[:40]] = str(v).strip()
        return out

    def _write_theme(self, ui: dict, categories=None) -> None:
        """Globale Darstellung in theme.json schreiben (Darstellungs-Keys ersetzen,
        uebrige Theme-Inhalte wie states/tabs bleiben erhalten). categories wird,
        wenn uebergeben, komplett ersetzt (der _comment-Schluessel bleibt)."""
        base = Path(__file__).resolve().parent.parent / "config"
        f = base / "theme.json"
        src = f if f.is_file() else (base / "theme.example.json")   # Vorlage als Basis
        try:
            doc = json.loads(src.read_text(encoding="utf-8")) if src.is_file() else {}
        except ValueError:
            doc = {}
        cur = doc.get("ui") if isinstance(doc.get("ui"), dict) else {}
        for k in ("iconSize", "nameSize", "subSize", "font", "textColor", "bold"):
            if k in ui:
                cur[k] = ui[k]
            else:
                cur.pop(k, None)
        doc["ui"] = cur
        if categories is not None:
            keep = {k: v for k, v in (doc.get("categories") or {}).items()
                    if str(k).startswith("_")}   # _comment behalten
            doc["categories"] = {**keep, **categories}
        f.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        self.theme = load_theme()
        self._dirty = True   # verbundene Panels neu rendern lassen

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
    def _spans_rooms(self, uuids) -> bool:
        """True, wenn die Bausteine ueber mehr als einen bekannten Raum verteilt
        sind. Dann lohnt es sich, den Raum je Kachel zu zeigen (Kategorie Licht
        ueber mehrere Raeume). Bausteine ohne Raum (z.B. Zentral) zaehlen nicht."""
        rooms = {self.controls[u].get("room") for u in uuids
                 if u in self.controls and self.controls[u].get("room") in self.rooms}
        return len(rooms) > 1

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

    def _alarm_entries(self, c: dict) -> list[dict]:
        """Weckzeit-Eintraege eines Weckers aus dem State `entryList`. Loxone
        liefert ein JSON-Objekt {entryID: {name, isActive, alarmTime (Sek seit
        Mitternacht), modes:[...], daily, nightLight}} — ggf. als (prozentkodierter)
        String. Gibt [{name, hm, active, repeat}] sortiert nach Uhrzeit zurueck;
        [] wenn nichts parsebar (dann wird der Rohwert einmal geloggt)."""
        raw = self._state(c, "entryList")
        if raw in (None, ""):
            return []
        data = raw
        if isinstance(raw, str):
            txt = unquote(raw).strip()
            try:
                data = json.loads(txt)
            except Exception:
                log.warning("Wecker entryList nicht als JSON parsebar: %r", txt[:200])
                return []
        seq = data.values() if isinstance(data, dict) else data
        if not isinstance(seq, (list, tuple)) and not hasattr(seq, "__iter__"):
            return []
        out = []
        for e in seq:
            if not isinstance(e, dict):
                continue
            try:
                secs = int(float(e.get("alarmTime") or 0))
            except (TypeError, ValueError):
                secs = 0
            hm = "%02d:%02d" % ((secs // 3600) % 24, (secs % 3600) // 60)
            repeat = self._alarm_repeat(e)
            out.append({"name": _clean(e.get("name")) or "Weckzeit", "hm": hm,
                        "active": bool(e.get("isActive")), "repeat": repeat})
        out.sort(key=lambda x: (not x["active"], x["hm"]))
        return out

    _WD_ABBR = {"montag": "Mo", "dienstag": "Di", "mittwoch": "Mi", "donnerstag": "Do",
                "freitag": "Fr", "samstag": "Sa", "sonntag": "So"}

    def _alarm_repeat(self, e: dict) -> str:
        """Wiederholungs-Text eines Weckzeit-Eintrags. `daily` -> „Täglich"; sonst
        die `modes` (Betriebsart-IDs) ueber die globalen operatingModes zu Namen
        aufloesen — Wochentage werden auf Mo/Di/… gekuerzt. Fallback, wenn keine
        Namen ermittelbar: Anzahl der Betriebsarten."""
        if e.get("daily"):
            return "Täglich"
        modes = e.get("modes")
        if not isinstance(modes, list) or not modes:
            return ""
        op = getattr(self, "op_modes", {})
        names = []
        for m in modes:
            nm = _clean(op.get(str(m)))
            if not nm:
                continue
            names.append(self._WD_ABBR.get(nm.lower(), nm))
        if not names:
            return "%d Betriebsarten" % len(modes)
        # Alle 7 Wochentage -> „Täglich" (kompakter)
        if len(names) == 7 and all(v in names for v in self._WD_ABBR.values()):
            return "Täglich"
        return " ".join(names)

    def _daytimer_mode(self, c: dict) -> str:
        """Aktiver Modus/Tag eines Daytimers als Name. `mode` (Zahl) wird ueber
        `modeList` aufgeloest, Format: '0:mode=0;name=\"Feiertag\",1:mode=3;
        name=\"Montag\",...' (Anfuehrungszeichen escaped)."""
        raw = str(self._state(c, "modeList") or "").replace('\\"', '"')
        modes = {int(m): n for m, n in re.findall(r'mode=(\d+);name="([^"]*)"', raw)}
        try:
            return modes.get(int(float(self._state(c, "mode"))), "")
        except (TypeError, ValueError):
            return ""

    def _daytimer_value(self, c: dict) -> str:
        """Aktueller Wert eines Daytimers als Text: 0/leer -> „Aus"; analog ->
        formatiert (details.format); digital -> „Ein"."""
        val = self._state(c, "value")
        if not val:
            return "Aus"
        det = c.get("details") or {}
        if det.get("analog"):
            return self._fmt_num(val, det.get("format") or "%.1f")
        return "Ein"

    def _control_item(self, uuid: str, prof: dict | None = None,
                      show_room: bool = False) -> dict:
        c = self.controls.get(uuid)
        if not c:
            return {"id": uuid, "label": "?", "icon": "info", "on": False}
        t = c.get("type")
        name = _clean(c.get("name"))
        it: dict = {"id": uuid, "label": name, "on": False, "icon": "info"}
        # Raum-Kennzeichnung: nur wenn die Ansicht mehrere Raeume umfasst (z.B.
        # Kategorie Licht ueber alle Raeume). Zentralbausteine haben keinen Raum.
        if show_room:
            rn = _clean((self.rooms.get(c.get("room")) or {}).get("name"))
            if rn:
                it["room"] = rn
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
            prep = self._state(c, "prepareState")
            bits = self._irc_activity(prep, self._state(c, "openWindow"))
            sub = (f"{self._fmt_num(ta, '%.1f')}° → {self._fmt_num(tt, '%.1f')}°"
                   if ta is not None else "Heizung")
            if bits:
                sub += " · " + " · ".join(bits)
            it.update(icon="thermo", nav={"view": "control", "id": uuid},
                      on=bool(prep), sublabel=sub)
        elif t == "Intercom":
            it.update(icon="cam", sublabel="Türsprechanlage",
                      nav={"view": "control", "id": uuid})
        elif t in SWITCHY:
            on = bool(self._state(c, "active"))
            it.update(on=on, sublabel="Ein" if on else "Aus", icon="switch",
                      cmd={"uuid": c.get("uuidAction"), "cmd": "off" if on else "on"})
        elif t == "TimedSwitch":
            # Treppenhaus-/Zeitschalter: kein 'active'-State, sondern
            # 'deactivationDelay' (>0 = laeuft noch N Sek, -1 = dauerhaft an,
            # 0 = aus). 'pulse' startet den Timer, 'off' schaltet aus.
            dd = self._state(c, "deactivationDelay")
            try:
                dd = float(dd if dd is not None else 0)
            except (TypeError, ValueError):
                dd = 0.0
            on = dd != 0
            if dd > 0:
                sub = "noch %d:%02d" % (int(dd) // 60, int(dd) % 60)
            elif dd < 0:
                sub = "Ein"
            else:
                sub = "Aus"
            it.update(on=on, sublabel=sub, icon="bulb",
                      cmd={"uuid": c.get("uuidAction"), "cmd": "off" if on else "pulse"})
        elif t == "Daytimer":
            # Wochenschaltuhr: aktueller Wert + ob ein manueller Timer (override) laeuft.
            ov = bool(self._state(c, "override"))
            it.update(icon="info", on=bool(self._state(c, "value")),
                      nav={"view": "control", "id": uuid},
                      sublabel=self._daytimer_value(c) + (" · Timer läuft" if ov else ""))
        elif t == "Dimmer":
            pos = self._state(c, "position") or 0
            it.update(icon="bulb", on=pos > 0, nav={"view": "control", "id": uuid},
                      sublabel=(f"{round(pos)} %" if pos > 0 else "Aus"))
        elif t == "Webpage":
            det = c.get("details") or {}
            host = re.sub(r"^https?://", "", det.get("url") or "").split("/")[0]
            it.update(icon="info", nav={"view": "control", "id": uuid},
                      sublabel=(host or "Webseite"))
            img = det.get("image")
            if img and not it.get("iconUrl"):
                it["iconUrl"] = "/icon?p=" + quote(img)
        elif t == "UpDownDigital":
            # Auf/Ab-Taster (keine States) -> Detailseite mit Auf/Ab/Stop.
            it.update(icon="blind", nav={"view": "control", "id": uuid}, sublabel="Auf / Ab")
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
        elif t == "Slider":
            det = c.get("details") or {}
            it.update(sublabel=self._fmt_num(self._state(c, "value"), det.get("format", "%.1f")),
                      nav={"view": "control", "id": uuid})
        elif t == "InfoOnlyAnalog":
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
                      nav={"view": "control", "id": uuid},
                      sublabel=("Alarm!" if lvl else ("Scharf" if armed else "Unscharf")))
        elif t == "AlarmClock":
            ringing = bool(self._state(c, "isAlarmActive"))
            nxt = self._alarm_next_text(c)
            has = bool(self._alarm_entries(c))
            rn = _clean((self.rooms.get(c.get("room")) or {}).get("name"))
            if rn:
                it["room"] = rn   # Raum auf der Kachel zeigen (mehrere Wecker unterscheidbar)
            it.update(icon="alarm", on=ringing, tone=("crit" if ringing else None),
                      nav={"view": "control", "id": uuid},
                      sublabel=("Weckt!" if ringing else
                                (nxt or ("Keine Weckzeit aktiv" if has else "Kein Wecker"))))
        elif t == "AcControl":
            modes = self._json_list_map(c, "operatingModes")
            tt = self._fmt_num(self._state(c, "targetTemperature"), "%.1f")
            it.update(icon="thermo", on=(self._state(c, "status") or 0) != 0,
                      nav={"view": "control", "id": uuid},
                      sublabel=(" · ".join(x for x in (modes.get(int(self._state(c, "mode") or 0)),
                                                       (tt + " °C" if tt else "")) if x) or "Klima"))
        elif t == "ClimateControllerUS":
            dh = self._state(c, "demandHeat") or 0
            dc = self._state(c, "demandCool") or 0
            it.update(icon="thermo", on=bool(dh or dc),
                      nav={"view": "control", "id": uuid},
                      sublabel=("Heizt" if dh else ("Kühlt" if dc else "Bereit")))
        elif t == "SystemScheme":
            it.update(icon="info", sublabel="Anlagenschema")
        elif t == "Hourcounter":
            it["sublabel"] = ("Wartung fällig" if self._state(c, "overdue")
                              else self._fmt_num(self._state(c, "total"), "%.0f h"))
        elif t == "Tracker":
            lines = self._tracker_lines(c)
            _, last = self._split_ts(lines[0]) if lines else (None, "")
            it.update(icon="list", nav={"view": "control", "id": uuid},
                      sublabel=(last or "Keine Einträge"))
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
        # Status-Bausteine antippbar machen -> grosse Wertseite
        if t in STATUS_BIG and "nav" not in it and "cmd" not in it:
            it["nav"] = {"view": "control", "id": uuid}
        # Kategorie-Ampel: Bausteine mit an/aus-Zustand einer Kategorie mit
        # Zustandsfarben leuchten aktiv (on-Farbe) bzw. ok (off-Farbe). Analoge
        # Anzeigen, Zentralbausteine und Bausteine mit eigenem tone (Rauch/…)
        # bleiben unberuehrt.
        cs = self._cat_states(c.get("cat"))
        if cs and t not in _ANALOG and not (t or "").startswith("Central") and not it.get("tone"):
            rgb = _hex_rgb(cs.get("on") if it.get("on") else cs.get("off"))
            if rgb:
                st = it.setdefault("style", {})
                st.setdefault("bg", "rgba(%s,.16)" % rgb)
                st.setdefault("border", "rgba(%s,.55)" % rgb)
        return self._apply_tile_style(it, uuid, prof)

    def _apply_tile_style(self, it: dict, uuid: str, prof: dict | None) -> dict:
        """Pro-Kachel-Overrides (Farben/Icon/Schrift) aus dem Panel-Profil."""
        ov = (prof.get("tiles") if prof else {}).get(uuid) if prof else None
        if not isinstance(ov, dict):
            return it
        if ov.get("iconColor"):
            it["color"] = ov["iconColor"]           # Icon-Farbe (--ico)
            it["colorFixed"] = ov["iconColor"]      # gewinnt auch im Aktiv-Zustand
        style = dict(it.get("style") or {})         # Kategorie-Ampel als Basis, manuell ueberschreibt
        for src, dst in (("bg", "bg"), ("border", "border"),
                         ("textColor", "txt"), ("font", "font")):
            if ov.get(src):
                style[dst] = ov[src]
        if ov.get("bold"):
            style["weight"] = 700
        if ov.get("italic"):
            style["italic"] = True
        if isinstance(ov.get("overlay"), dict):
            fill, bord, bw = _overlay_alphas(ov["overlay"])
            style["ovFill"] = f"{fill:.3g}"     # ueberschreibt --ov-* nur fuer diese Kachel
            style["ovBord"] = f"{bord:.3g}"
            style["ovBw"] = bw
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
        if isinstance(tab, str) and tab.startswith("cat:"):
            # Kategorie-Direkt-Tab: dieselben Controls wie im Kategorie-Drilldown
            cu = tab[4:]
            uuids = [u for u, c in self.controls.items()
                     if c.get("cat") == cu and self._room_ok(u, prof) and self._shown(u, prof)]
            sr = self._spans_rooms(uuids)
            items = [self._control_item(u, prof, show_room=sr) for u in uuids]
            title = _clean(self.cats.get(cu, {}).get("name")) or "Kategorie"
            return {"t": "view", "title": title, "tab": tab,
                    "route": {"view": "tab", "tab": tab}, "items": items}
        if tab == "favoriten":
            uuids = [u for u, c in self.controls.items()
                     if c.get("isFavorite") and self._room_ok(u, prof) and self._shown(u, prof)]
            sr = self._spans_rooms(uuids)
            items = [self._control_item(u, prof, show_room=sr) for u in uuids]
            title = "Favoriten"
        elif tab == "zentral":
            items = [self._control_item(u, prof) for u, c in self.controls.items()
                     if (c.get("type") or "").startswith("Central") and self._shown(u, prof)]
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
                     if c.get("cat") == gid and self._room_ok(u, prof) and self._shown(u, prof)]
            title = _clean(self.cats.get(gid, {}).get("name")); tab = "kategorien"
            sr = self._spans_rooms(uuids)
            return {"t": "view", "title": title, "tab": tab, "route": route,
                    "layout": layout,
                    "items": [self._control_item(u, prof, show_room=sr) for u in uuids]}
        elif kind == "room":
            uuids = [u for u, c in self.controls.items()
                     if c.get("room") == gid and self._cat_ok(u, prof) and self._shown(u, prof)]
            title = _clean(self.rooms.get(gid, {}).get("name")); tab = "raeume"
        elif kind == "central":
            c = self.controls.get(gid, {})
            members = (c.get("details") or {}).get("controls") or []
            uuids = [m.get("uuid") for m in members
                     if m.get("uuid") in self.controls and self._shown(m.get("uuid"), prof)]
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

    def _big_view(self, uuid: str, icon: str, big: str, sub: str = "", tone=None) -> dict:
        """Grosse 1/1-Wertseite fuer reine Status-Bausteine. Das Hero-Icon ist
        dasselbe wie auf der Kachel vorne: Loxone-eigenes Icon, falls vorhanden,
        sonst das Builtin-Icon (`icon`)."""
        c = self.controls.get(uuid, {})
        hero = {"k": "hero", "icon": icon}
        iu = self._control_icon_url(c)
        if iu:
            hero["iconUrl"] = iu
        blk = {"k": "big", "text": big}
        if tone:
            blk["tone"] = tone
        blocks = [hero, blk]
        if sub:
            blocks.append({"k": "status", "text": sub})
        return {"t": "view", "title": _clean(c.get("name")),
                "route": {"view": "control", "id": uuid}, "blocks": blocks}

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
            return {"t": "view", "title": _clean(c.get("name")), "route": route,
                    "anchor": "bottom", "blocks": blocks}
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
            # Quellen (Radio/Playlist/Spotify) immer auf Unterseite erreichbar
            # (Favoriten werden dort per prime_favs frisch angefordert).
            blocks.append({"k": "more", "route": {"view": "sources", "id": uuid}})
            return {"t": "view", "title": _clean(c.get("name")), "route": route, "blocks": blocks}
        if t == "Gate":
            ua = c.get("uuidAction")
            pct = round((self._state(c, "position") or 0) * 100)
            active = self._state(c, "active") or 0
            postext = "Offen" if pct >= 100 else ("Geschlossen" if pct <= 0 else f"{pct}% offen")
            status = "öffnet …" if active > 0 else ("schließt …" if active < 0 else postext)
            return {"t": "view", "title": _clean(c.get("name")), "route": route,
                    "anchor": "bottom", "blocks": [
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
            modes = self._irc_modes(c)
            am = self._state(c, "activeMode")
            try:
                am = int(am) if am is not None else None
            except (TypeError, ValueError):
                am = None
            # Status: Soll-Temp + aktiver Modus + heizt/kuehlt/Fenster
            sbits = []
            if am is not None and am in modes:
                sbits.append(modes[am])
            sbits += self._irc_activity(self._state(c, "prepareState"),
                                        self._state(c, "openWindow"))
            status = f"Soll {tt} °C" + (" · " + " · ".join(sbits) if sbits else "")
            blocks = [
                {"k": "big", "text": f"{ta} °C"},          # grosse Ist-Temp statt Icon
                {"k": "status", "text": status},
                {"k": "row", "cells": [
                    {"label": "−", "cmd": {"uuid": ua, "cmd": f"setComfortTemperature/{comfort - 0.5:.1f}"}},
                    {"label": "+", "cmd": {"uuid": ua, "cmd": f"setComfortTemperature/{comfort + 0.5:.1f}"}},
                ]},
            ]
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
            return {"t": "view", "title": _clean(c.get("name")), "route": route,
                    "anchor": "bottom", "blocks": blocks}
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
        if t == "Tracker":
            lines = self._tracker_lines(c)
            if not lines:
                return self._big_view(uuid, "list", "Keine Einträge")
            items = []
            for i, ln in enumerate(lines):
                ts, txt = self._split_ts(ln)
                entry = {"id": f"{uuid}:{i}", "icon": "list", "label": txt}
                if ts:
                    entry["sublabel"] = ts
                items.append(entry)
            return {"t": "view", "title": _clean(c.get("name")), "route": route,
                    "layout": "list", "items": items}
        # --- Status-Bausteine: grosse 1/1-Wertseite ---
        if t == "Meter":
            det = c.get("details") or {}
            a = self._fmt_num(self._state(c, "actual"), det.get("actualFormat", "%.1f"))
            tot = self._fmt_num(self._state(c, "total"), det.get("totalFormat", "%.1f"))
            return self._big_view(uuid, "info", a or "–", (tot + " gesamt") if tot else "")
        if t == "Slider":
            ua = c.get("uuidAction")
            det = c.get("details") or {}
            fmt = det.get("format", "%.1f")

            def _f(key, dflt):
                try:
                    return float(det.get(key, dflt))
                except (TypeError, ValueError):
                    return float(dflt)

            def _n(x):   # ganzzahlig darstellen, wenn ohne Nachkommastelle
                return int(x) if float(x).is_integer() else x
            mn, mx = _f("min", 0), _f("max", 100)
            stp = _f("step", 1) or 1
            val = self._state(c, "value")
            try:
                cur = float(val)
            except (TypeError, ValueError):
                cur = mn
            return {"t": "view", "title": _clean(c.get("name")), "route": route, "blocks": [
                {"k": "hero", "icon": "info"},
                {"k": "big", "text": self._fmt_num(val, fmt) or "–"},
                {"k": "slider", "icon": "vol", "value": _n(cur), "min": _n(mn),
                 "max": _n(mx), "step": _n(stp), "cmd": {"uuid": ua, "tmpl": "{v}"}},
            ]}
        if t == "InfoOnlyAnalog":
            det = c.get("details") or {}
            return self._big_view(uuid, "info",
                                  self._fmt_num(self._state(c, "value"), det.get("format", "%.1f")) or "–")
        if t in ("TextState", "InfoOnlyText"):
            return self._big_view(uuid, "info",
                                  str(self._state(c, "textAndIcon") or self._state(c, "text") or "–"))
        if t == "InfoOnlyDigital":
            on = bool(self._state(c, "active"))
            tx = (c.get("details") or {}).get("text") or {}
            return self._big_view(uuid, "info",
                                  (tx.get("on") if on else tx.get("off")) or ("Ein" if on else "Aus"))
        if t == "SmokeAlarm":
            ok = (self._state(c, "level") or 0) == 0
            return self._big_view(uuid, "alarm", "Alles ok" if ok else "Alarm!",
                                  tone=("good" if ok else "crit"))
        if t == "PresenceDetector":
            on = bool(self._state(c, "active"))
            itxt = self._text(c, "infoText")
            big = itxt if (itxt and itxt.lower() not in ("on", "off")) else ("Anwesend" if on else "Abwesend")
            return self._big_view(uuid, "info", big)
        if t == "Alarm":
            ua = c.get("uuidAction")
            armed = bool(self._state(c, "armed"))
            lvl = self._state(c, "level") or 0
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
            return {"t": "view", "title": _clean(c.get("name")), "route": route,
                    "anchor": "bottom", "blocks": [
                {"k": "hero", "icon": "alarm"},
                big,
                {"k": "status", "text": sub},
                {"k": "row", "cells": cells},
            ]}
        if t == "AlarmClock":
            ua = c.get("uuidAction")
            ringing = bool(self._state(c, "isAlarmActive"))
            nxt = self._alarm_next_text(c)
            entries = self._alarm_entries(c)
            room = _clean((self.rooms.get(c.get("room")) or {}).get("name"))
            # Layout wie IRR/Klima (anchor:bottom): Statuszeile mittig oben (Raum
            # als Unterzeile), die Weckzeit-Eintraege unten angedockt. Read-only —
            # keine Eintrags-Bearbeitung; klingelt der Wecker, gibt es genau EINEN
            # Button (Loxone 'dismiss' -> isAlarmActive 0 -> Weckton stoppt).
            stat = {"k": "astat", "text": ("Weckt jetzt" if ringing else (nxt or "Keine Weckzeit aktiv"))}
            if ringing:
                stat["tone"] = "crit"
            if room:
                stat["sub"] = room
            blocks = [{"k": "hero", "icon": "alarm"}, stat, {"k": "alarmlist", "entries": entries}]
            if ringing:
                blocks.append({"k": "row", "cells": [
                    {"label": "Wecker aus", "cmd": {"uuid": ua, "cmd": "dismiss"}}]})
            return {"t": "view", "title": _clean(c.get("name")), "route": route,
                    "anchor": "bottom", "blocks": blocks}
        if t == "Daytimer":
            ua = c.get("uuidAction")
            ov = bool(self._state(c, "override"))
            mode = self._daytimer_mode(c)
            sub = ("Timer läuft · " + mode) if (ov and mode) else ("Timer läuft" if ov else mode)
            hero = {"k": "hero", "icon": "info"}
            iu = self._control_icon_url(c)
            if iu:
                hero["iconUrl"] = iu
            blocks = [hero, {"k": "astat", "text": self._daytimer_value(c), "sub": sub}]
            # Laeuft ein manueller Timer (override), kann er beendet werden
            # (stopOverride). Sonst 4 feste Dauern zum Starten: startOverride/
            # {value}/{sekunden} — value=1 (einschalten) fuer die gewaehlte Zeit.
            if ov:
                blocks.append({"k": "row", "cells": [
                    {"label": "Timer beenden", "cmd": {"uuid": ua, "cmd": "stopOverride"}}]})
            else:
                blocks.append({"k": "row", "wrap": True, "cells": [
                    {"label": "15 min", "cmd": {"uuid": ua, "cmd": "startOverride/1/900"}},
                    {"label": "30 min", "cmd": {"uuid": ua, "cmd": "startOverride/1/1800"}},
                    {"label": "60 min", "cmd": {"uuid": ua, "cmd": "startOverride/1/3600"}},
                    {"label": "90 min", "cmd": {"uuid": ua, "cmd": "startOverride/1/5400"}},
                ]})
            return {"t": "view", "title": _clean(c.get("name")), "route": route,
                    "anchor": "bottom", "blocks": blocks}
        if t == "Dimmer":
            ua = c.get("uuidAction")
            pos = self._state(c, "position") or 0
            mn = self._state(c, "min"); mx = self._state(c, "max"); stp = self._state(c, "step")
            mn = 0 if mn is None else mn
            mx = 100 if mx is None else mx
            stp = stp if isinstance(stp, (int, float)) and stp else 1
            return {"t": "view", "title": _clean(c.get("name")), "route": route,
                    "anchor": "bottom", "blocks": [
                {"k": "hero", "icon": "bulb"},
                {"k": "big", "text": f"{round(pos)} %"},
                {"k": "slider", "icon": "bulb", "value": round(pos), "min": round(mn),
                 "max": round(mx), "step": stp, "cmd": {"uuid": ua, "tmpl": "{v}"}},
                {"k": "row", "cells": [
                    {"label": "Aus", "cmd": {"uuid": ua, "cmd": "off"}},
                    {"label": "Ein", "cmd": {"uuid": ua, "cmd": "on"}}]},
            ]}
        if t == "Webpage":
            det = c.get("details") or {}
            url = (det.get("urlHd") or det.get("url") or "").strip()
            if url and not re.match(r"^https?://", url):
                url = "http://" + url
            return {"t": "view", "title": _clean(c.get("name")), "route": route,
                    "blocks": [{"k": "web", "url": url}]}
        if t == "UpDownDigital":
            # Auf/Ab-Taster ohne States: gedrueckt halten = fahren (UpOn), loslassen
            # = stoppen (UpOff). Push&hold ist die sichere Taster-Semantik.
            ua = c.get("uuidAction")
            return {"t": "view", "title": _clean(c.get("name")), "route": route,
                    "anchor": "bottom", "blocks": [
                {"k": "hero", "icon": "blind"},
                {"k": "status", "text": "Zum Fahren gedrückt halten"},
                {"k": "row", "cells": [
                    {"icon": "up", "hold": True, "cmd": {"uuid": ua, "cmd": "UpOn"},
                     "release": {"uuid": ua, "cmd": "UpOff"}},
                    {"icon": "down", "hold": True, "cmd": {"uuid": ua, "cmd": "DownOn"},
                     "release": {"uuid": ua, "cmd": "DownOff"}}]},
            ]}
        if t == "AcControl":
            ua = c.get("uuidAction")
            # An die IRR-Detailseite angeglichen: grosse Ist-Temp oben, Status-
            # zeile, dann 2 Bedienzeilen. Modus/Fan klappen ihre Auswahl inline
            # auf (viele Optionen passen nicht in eine feste Zeile).
            modes = self._json_list_map(c, "operatingModes")   # {id: name}
            fans = self._json_list_map(c, "fanspeeds")          # {id: name}
            on = (self._state(c, "status") or 0) != 0
            cur_mode = int(self._state(c, "mode") or 0)
            cur_fan = int(self._state(c, "fan") or 0)
            tgt = self._state(c, "targetTemperature")
            ist = self._state(c, "temperature")
            try:
                cur_t = float(tgt)
            except (TypeError, ValueError):
                cur_t = 22.0
            try:
                lo = float(self._state(c, "minTemp"))
            except (TypeError, ValueError):
                lo = 5.0
            try:
                hi = float(self._state(c, "maxTemp"))
            except (TypeError, ValueError):
                hi = 40.0
            dn = max(lo, cur_t - 0.5); up = min(hi, cur_t + 0.5)
            # grosse Anzeige = Ist-Temp (wie IRR); Fallback Soll, wenn kein Ist
            try:
                ist_ok = ist is not None and float(ist) > -50
            except (TypeError, ValueError):
                ist_ok = False
            big = (self._fmt_num(ist, "%.1f") + " °C") if ist_ok else \
                  ((self._fmt_num(tgt, "%.1f") + " °C") if tgt is not None else "–")
            sbits = []
            if tgt is not None:
                sbits.append(f"Soll {self._fmt_num(tgt, '%.1f')} °C")
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
        if t == "ClimateControllerUS":
            dh = self._state(c, "demandHeat") or 0
            dc = self._state(c, "demandCool") or 0
            big = "Heizt" if dh else ("Kühlt" if dc else "Bereit")
            # verwaltete AC-Einheiten + wie viele gerade Bedarf anmelden
            try:
                units = json.loads(self._state(c, "controls") or "[]")
            except (ValueError, TypeError):
                units = []
            active = sum(1 for u in units if isinstance(u, dict) and u.get("demand"))
            sbits = [f"{active}/{len(units)} Anlagen aktiv"] if units else []
            hum = self._state(c, "humidity") or 0
            if hum:
                sbits.append(f"Feuchte {self._fmt_num(hum, '%.0f')} %")
            out = self._state(c, "actualOutdoorTemp")
            try:
                if out is not None and float(out) > -100:
                    sbits.append(f"Außen {self._fmt_num(out, '%.1f')} °C")
            except (TypeError, ValueError):
                pass
            return self._big_view(uuid, "thermo", big, " · ".join(sbits),
                                  tone=("crit" if dc else None))
        if t == "Hourcounter":
            ov = self._state(c, "overdue")
            return self._big_view(uuid, "info", self._fmt_num(self._state(c, "total"), "%.0f h") or "–",
                                  "Wartung fällig" if ov else "", tone=("crit" if ov else None))
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

    def _audio_backend(self) -> AudioBackend | None:
        """Liefert das Audio-Backend; erkennt den Host bei Bedarf automatisch."""
        if self.audio is not None:
            return self.audio
        host = self._detect_audio_host()
        if host:
            self.audio = make_backend({"host": host, "port": self.audio_cfg.get("port", 7091)})
            if self.audio:
                log.info("Audioserver-Host automatisch erkannt: %s", host)
        return self.audio

    async def command(self, uuid: str, cmd: str, pin: str | None = None) -> str | None:
        """Fuehrt einen Befehl aus. Mit pin: gesicherter Befehl (Visu-Passwort)."""
        if not (self.client and uuid and cmd):
            return None
        try:
            if pin is not None:
                return await self._secured_command(uuid, cmd, pin)
            # AudioZone-Steuerung laeuft ueber den Audioserver (Loxone-Music-
            # Server-Protokoll, Port 7091), NICHT ueber den Miniserver: play,
            # pause, queueplus/-minus, volume/{n}, roomfav/play/{slot} werden zu
            # audio/{playerid}/{cmd}. uuid = AudioZone-uuidAction -> Loxone-
            # playerid; der Audioserver mappt sie intern auf den realen Player,
            # die Anzeige folgt ueber die Loxone-States. Ausnahme roomfav/get:
            # die Favoriten-Abfrage muss ueber den Miniserver laufen, sie
            # befuellt den sourceList-State fuer die Anzeige.
            pid = self.playerid_by_action.get(uuid)
            if pid is not None and not cmd.startswith("roomfav/get"):
                backend = self._audio_backend()
                if backend:
                    ok = await backend.command(pid, cmd)
                    return "200" if ok else None
                log.warning("AudioZone-Befehl ohne Audio-Backend (uuid=%s, cmd=%s)", uuid, cmd)
                return None
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
        if uuid in self.alarm_map:
            now = bool(value)
            if now != bool(self._alarm_prev.get(uuid)):
                # Beide Flanken pushen: 0->1 startet den Weckton, 1->0 (z.B. in
                # Loxone/App oder am Panel quittiert) stoppt ihn wieder.
                self._pending_alarm.append({"id": self.alarm_map[uuid], "on": now})
            self._alarm_prev[uuid] = value

    async def stream_task(self) -> None:
        # Dauer-Loop: Erstverbindung + Reconnect zum Miniserver. Bricht NIEMALS
        # den HTTP-Server ab — auch wenn der Miniserver (noch) nicht erreichbar
        # oder das Passwort falsch ist (dann bleibt /settings bedienbar).
        while True:
            try:
                if self.client is None:
                    await self.start()          # Erstverbindung / nach hartem Reset
                elif self.ws is None:
                    await self._connect_ws()    # nur WS neu (z.B. nach Settings-Reconnect)
                await self.ws.stream(self._on_value)
                raise ConnectionError("WS-Stream regulär beendet")
            except asyncio.CancelledError:
                raise
            except Exception as err:
                log.warning("Miniserver nicht verbunden (%s) — neuer Versuch in 10s", err)
                try:
                    if self.ws:
                        await self.ws.close()
                except Exception:
                    pass
                self.ws = None
                try:
                    if self.client:
                        await self._reauth()    # Token erneuern, Client behalten
                except Exception:
                    await self._close_conn()    # Client kaputt -> harter Reset (start() baut neu)
                await asyncio.sleep(10)

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
            while self._pending_alarm:
                ev = self._pending_alarm.pop(0)
                log.info("Wecker %s → %s", "an" if ev["on"] else "aus", ev["id"])
                for ws in list(self.conn_route):
                    try:
                        await ws.send_json({"t": "alarm", "id": ev["id"], "on": ev["on"]})
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
        if self.audio:
            await self.audio.close()


# Panel-/Config-/Settings-HTML immer frisch ausliefern: der Kiosk-Chromium
# cachte die Seite sonst heuristisch und zeigte nach einem Update die alte
# Version (aufklappende Auswahl etc. griff nicht) bis der Profil-Cache geleert
# wurde. no-cache erzwingt Revalidierung -> Updates greifen sofort.
_NOCACHE = {"Cache-Control": "no-cache, no-store, must-revalidate"}


async def index(request: web.Request) -> web.Response:
    return web.Response(text=HTML.read_text(encoding="utf-8"),
                        content_type="text/html", headers=_NOCACHE)


async def config_index(request: web.Request) -> web.Response:
    return web.Response(text=CONFIG_HTML.read_text(encoding="utf-8"),
                        content_type="text/html", headers=_NOCACHE)


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
            "cat": c.get("cat"),
            "iconUrl": app._control_icon_url(c),
        })
    return web.json_response({
        "rooms": rooms, "cats": cats, "controls": controls,
        "icons": {"loxone": app._loxone_icons()},
        "tabs": [{"tab": "favoriten", "label": "Favoriten"},
                 {"tab": "zentral", "label": "Zentral"},
                 {"tab": "raeume", "label": "Räume"},
                 {"tab": "kategorien", "label": "Kategorien"}]
        + [{"tab": "cat:" + cu, "label": _clean(app.cats[cu].get("name", "")),
            "iconUrl": app._icon_url(app.cats[cu].get("image")), "cat": True}
           for cu in app.cats_with],
        "panels": panels,
        "theme": {"ui": {k: v for k, v in (app.theme.get("ui") or {}).items()
                         if k in ("iconSize", "nameSize", "subSize", "font",
                                  "textColor", "bold")},
                  "categories": {k: v for k, v in (app.theme.get("categories") or {}).items()
                                 if not str(k).startswith("_")}},
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


async def api_save_theme(request: web.Request) -> web.Response:
    """Globale Darstellung (theme.json ui) speichern — gilt fuer alle Panels."""
    app: App = request.app["app"]
    try:
        data = await request.json()
    except (ValueError, aiohttp.ContentTypeError):
        return web.json_response({"ok": False, "error": "kein gültiges JSON"}, status=400)
    ui = data.get("ui")
    if not isinstance(ui, dict):
        return web.json_response({"ok": False, "error": "Feld 'ui' fehlt"}, status=400)
    clean = App._sanitize_theme_ui(ui)
    cats = data.get("categories")
    clean_cats = App._sanitize_categories(cats) if isinstance(cats, dict) else None
    try:
        app._write_theme(clean, clean_cats)
    except OSError as err:
        return web.json_response({"ok": False, "error": str(err)}, status=500)
    log.info("theme.json (globale Darstellung%s) gespeichert",
             " + Kategorie-Farben" if clean_cats is not None else "")
    return web.json_response({"ok": True})


async def settings_index(request: web.Request) -> web.Response:
    return web.Response(text=SETTINGS_HTML.read_text(encoding="utf-8"),
                        content_type="text/html", headers=_NOCACHE)


async def install_script(request: web.Request) -> web.Response:
    """Liefert das Panel-Installer-Skript (fuer 'curl ... | bash' vom Panel aus)."""
    try:
        txt = INSTALL_SH.read_text(encoding="utf-8").replace("\r\n", "\n")
    except OSError:
        return web.Response(status=404, text="install-agent.sh nicht gefunden")
    return web.Response(text=txt, content_type="text/plain")


async def api_settings(request: web.Request) -> web.Response:
    app: App = request.app["app"]
    cfg = _load_cfg()
    ms = cfg.get("miniserver", {})
    ic = cfg.get("intercom", {})
    env_ms = bool(os.environ.get("LOXPANEL_MS_HOST"))

    def icv(uuid):
        e = ic.get(uuid) or {}
        if isinstance(e, str):
            e = {"url": e}
        return {"url": (e.get("url") or "").strip(), "user": e.get("user", ""),
                "hasPass": bool(e.get("pass"))}

    intercoms = [{"uuid": u, "name": _clean(c.get("name")), **icv(u)}
                 for u, c in app.controls.items() if c.get("type") == "Intercom"]
    return web.json_response({
        "miniserver": {
            "host": ms.get("host") or os.environ.get("LOXPANEL_MS_HOST", ""),
            "user": ms.get("user") or os.environ.get("LOXPANEL_MS_USER", ""),
            "port": ms.get("port", 443),
            "verify_tls": bool(ms.get("verify_tls", False)),
            "hasPass": bool(ms.get("pass")) or env_ms,
        },
        "intercoms": intercoms,
        "connected": app.client is not None,
        "nControls": len(app.controls),
    })


async def api_settings_ms(request: web.Request) -> web.Response:
    app: App = request.app["app"]
    try:
        data = await request.json()
    except (ValueError, aiohttp.ContentTypeError):
        return web.json_response({"ok": False, "error": "kein gültiges JSON"}, status=400)
    host = str(data.get("host", "")).strip()
    if not host:
        return web.json_response({"ok": False, "error": "Host fehlt"}, status=400)
    cfg = _load_cfg()
    ms = dict(cfg.get("miniserver", {}))
    ms["host"] = host
    ms["user"] = str(data.get("user", "")).strip()
    try:
        ms["port"] = int(data.get("port") or 443)
    except (TypeError, ValueError):
        ms["port"] = 443
    ms["verify_tls"] = bool(data.get("verify_tls"))
    if data.get("pass"):                       # leer = altes Passwort behalten
        ms["pass"] = str(data["pass"])
    if not ms.get("pass"):
        return web.json_response({"ok": False, "error": "Passwort fehlt"}, status=400)
    cfg["miniserver"] = ms
    _write_cfg(cfg)
    try:
        n = await app.reconnect()
        log.info("Miniserver-Settings gespeichert, verbunden (%d Controls)", n)
        return web.json_response({"ok": True, "connected": True, "nControls": n})
    except Exception as err:
        return web.json_response({"ok": False, "error": f"Verbindung fehlgeschlagen: {err}"})


async def api_settings_intercom(request: web.Request) -> web.Response:
    app: App = request.app["app"]
    try:
        data = await request.json()
    except (ValueError, aiohttp.ContentTypeError):
        return web.json_response({"ok": False, "error": "kein gültiges JSON"}, status=400)
    items = data.get("intercoms") or {}
    cfg = _load_cfg()
    ic = dict(cfg.get("intercom", {}))
    for uuid, e in items.items():
        if not isinstance(e, dict):
            continue
        cur = ic.get(uuid)
        cur = dict(cur) if isinstance(cur, dict) else ({"url": cur} if isinstance(cur, str) else {})
        cur["url"] = str(e.get("url", "")).strip()
        cur["user"] = str(e.get("user", "")).strip()
        if e.get("pass"):
            cur["pass"] = str(e["pass"])
        if cur.get("url"):
            ic[uuid] = cur
        else:
            ic.pop(uuid, None)
    cfg["intercom"] = ic
    _write_cfg(cfg)
    app.intercom_cfg = _intercom_config()
    log.info("Intercom-Settings gespeichert (%d Einträge)", len(ic))
    return web.json_response({"ok": True})


# ---- Panel-Agenten (Fernstart der Displays) ----
async def api_agent_announce(request: web.Request) -> web.Response:
    """Panel-Agent meldet sich periodisch (Auto-Discovery)."""
    app: App = request.app["app"]
    try:
        d = await request.json()
    except (ValueError, aiohttp.ContentTypeError):
        d = {}
    ip = str(d.get("ip") or "").strip() or request.remote or "?"
    app.agents[ip] = {"ip": ip, "name": str(d.get("name") or ip)[:60],
                      "panel": str(d.get("panel") or ""), "port": int(d.get("port") or 8130),
                      "kiosk": bool(d.get("kiosk")), "ts": time.time()}
    # Panel-spezifische Geraeteeinstellungen an den Agenten zurueckgeben
    # (der wendet sie am Geraet an, z.B. Display-Abschaltung per xset).
    return web.json_response({"ok": True, "dpmsOff": app.panel_dpms(d.get("panel")),
                              "reloadHours": app.panel_reload(d.get("panel"))})


async def api_agents(request: web.Request) -> web.Response:
    app: App = request.app["app"]
    now = time.time()
    out = [{**a, "online": (now - a["ts"]) < 60}
           for a in app.agents.values() if (now - a["ts"]) < 600]
    out.sort(key=lambda a: a["name"])
    return web.json_response({"agents": out})


async def api_agent_command(request: web.Request) -> web.Response:
    """Leitet Start/Reload/Stop an den Panel-Agenten weiter."""
    app: App = request.app["app"]
    try:
        d = await request.json()
    except (ValueError, aiohttp.ContentTypeError):
        return web.json_response({"ok": False, "error": "kein JSON"}, status=400)
    ip = str(d.get("ip", ""))
    action = str(d.get("action", ""))
    a = app.agents.get(ip)
    if not a:
        return web.json_response({"ok": False, "error": "Panel nicht bekannt"}, status=404)
    if action not in ("start", "reload", "stop"):
        return web.json_response({"ok": False, "error": "unbekannte Aktion"}, status=400)
    url = f"http://{a['ip']}:{a['port']}/{action}"
    payload = {"panel": str(d.get("panel") or "")} if action == "start" else {}
    try:
        async with aiohttp.ClientSession() as s:
            async with s.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=8)) as r:
                body = await r.text()
                log.info("Agent %s %s -> %s", ip, action, r.status)
                return web.json_response({"ok": r.status == 200, "status": r.status,
                                          "body": body[:200]})
    except Exception as err:
        return web.json_response({"ok": False, "error": str(err)})


async def api_testtone(request: web.Request) -> web.Response:
    """Schickt einen kurzen Test-Weckton an die Panel-Browser (zum Pruefen der
    Audio-Ausgabe am Geraet, z.B. YC-41PM). Mit `panel` auf ein Profil begrenzt,
    sonst an alle offenen Visu-Verbindungen. Der Ton wird im Browser per Web
    Audio erzeugt (derselbe Weg wie der echte Weckton)."""
    app: App = request.app["app"]
    try:
        d = await request.json()
    except (ValueError, aiohttp.ContentTypeError):
        d = {}
    target = str(d.get("panel") or "").strip()
    n = 0
    for ws, prof in list(app.conn_prof.items()):
        if target and (prof or {}).get("id") != target:
            continue
        try:
            await ws.send_json({"t": "testtone"})
            n += 1
        except ConnectionError:
            app.conn_route.pop(ws, None)
            app.conn_prof.pop(ws, None)
    return web.json_response({"ok": True, "sent": n})


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
                        "tabMeta": app._tab_meta(prof["tabs"]), "title": prof["title"]})
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
                route = data["route"]
                app.conn_route[ws] = route
                await ws.send_json(app.render(route, prof))
                # Beim Oeffnen einer AudioZone / Musikauswahl die Zonen-Favoriten
                # aktiv anfordern; das frische Ergebnis wird per broadcaster
                # nachgereicht (roomfav/get befuellt den sourceList-State).
                if route.get("view") in ("control", "sources") and route.get("id"):
                    task = asyncio.create_task(app.prime_favs(route["id"]))
                    app.bg_tasks.add(task)
                    task.add_done_callback(app.bg_tasks.discard)
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
    # HTTP-Server startet SOFORT; die Miniserver-Verbindung baut stream_task im
    # Hintergrund auf (mit Retry) — so ist /settings auch ohne/mit falschen
    # Zugangsdaten erreichbar.
    app: App = a["app"]
    a["tasks"] = [asyncio.create_task(app.stream_task()),
                  asyncio.create_task(app.broadcaster())]


async def on_cleanup(a: web.Application) -> None:
    for t in a.get("tasks", []):
        t.cancel()
    await a["app"].close()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    p = argparse.ArgumentParser()
    p.add_argument("--port", type=int, default=int(os.environ.get("LOXPANEL_PORT", "8099")))
    args = p.parse_args()

    a = web.Application()
    a["app"] = App(_config(), _audio_config())
    a.router.add_get("/", index)
    a.router.add_get("/config", config_index)
    a.router.add_get("/settings", settings_index)
    a.router.add_get("/install-agent.sh", install_script)
    a.router.add_get("/api/meta", api_meta)
    a.router.add_post("/api/panels", api_save_panels)
    a.router.add_post("/api/theme", api_save_theme)
    a.router.add_get("/api/settings", api_settings)
    a.router.add_post("/api/settings/miniserver", api_settings_ms)
    a.router.add_post("/api/settings/intercom", api_settings_intercom)
    a.router.add_post("/api/agent/announce", api_agent_announce)
    a.router.add_get("/api/agents", api_agents)
    a.router.add_post("/api/agent/command", api_agent_command)
    a.router.add_post("/api/testtone", api_testtone)
    a.router.add_get("/icon", icon_handler)
    a.router.add_get("/cover", cover_handler)
    a.router.add_get("/mjpeg", mjpeg_handler)
    a.router.add_get("/ws", ws_handler)
    a.on_startup.append(on_startup)
    a.on_cleanup.append(on_cleanup)
    web.run_app(a, host="0.0.0.0", port=args.port)


if __name__ == "__main__":
    main()
