"""Verlaeufe aus einer Grafana-Installation (etwa der von Stats4Lox): Panels
eines Dashboards auswaehlen und ihre Daten als dieselben Diagramm-Bloecke
zeigen wie die Loxone-Statistik (Block k:"chart", statistik.py).

Ablauf: Grafana per IP:Port (loxpanel.cfg `grafana`: url, token bzw.
user/pass). Das Dashboard (/api/dashboards/uid/<uid>) liefert je Panel die
Abfragen (targets) und die Datenquelle; LoxPanel laesst Grafana sie ueber
/api/ds/query im gewaehlten Zeitraum ausfuehren. So funktioniert jede
Datenquelle, die Grafana kennt (InfluxDB von Stats4Lox, Prometheus, SQL ...),
und Makros wie $timeFilter oder $__interval setzt Grafana selbst ein.
Dashboard-Variablen ($raum ...) setzt LoxPanel mit ihrem gespeicherten Wert ein.

Ein Grafana-Panel steht in einer Verlaufs-Pane wie ein Baustein, als
Pseudo-UUID "gf:<dashboard-uid>:<panel-id>" ("chart:gf:abc:2,<uuid>"). Damit
laufen Auswahl, Stapeln/Blaettern, Zeitraum-Knoepfe und Senden ueber denselben
Weg wie die Loxone-Verlaeufe; chart_blocks() verzweigt hierher.

Die Methoden sind ein Mixin (Grafana): App erbt sie. Importiert webvisu nicht."""
from __future__ import annotations

import asyncio
import calendar
import logging
import re
import time
from datetime import datetime
from urllib.parse import quote, urlsplit

import aiohttp

from bausteine.gemeinsam import _clean
from konfig import STAT_RANGES, _load_cfg
from statistik import _stat_thin

log = logging.getLogger("loxpanel.webvisu")   # derselbe Logger wie der Server

# Pseudo-UUID eines Grafana-Panels: Dashboard-UID (Grafana: Buchstaben, Ziffern,
# - und _, hoechstens 40 Zeichen) und Panel-ID
GF_ID = re.compile(r"^gf:([A-Za-z0-9_-]{1,64}):(\d{1,9})$")

GF_TIMEOUT = 15          # s je Anfrage an Grafana
GF_RETRY = 60            # nach einem Abruffehler fruehestens wieder versuchen
GF_DASH_REFRESH = 300    # Dashboard (Abfragen, Titel) so lange wiederverwenden
GF_KATALOG_REFRESH = 60  # Panel-Liste fuer den Konfigurator
GF_DS_REFRESH = 300      # Datenquellen-Liste (/api/frontend/settings)
GF_MAX_SERIES = 6        # Reihen je Diagramm
GF_MAX_POINTS = 240      # wie STAT_MAX_POINTS: Diagramm ~440 px breit
GF_CACHE_MAX = 64
GF_KATALOG_DASH_MAX = 200
# Daten neu holen nach so vielen Sekunden, je Zeitraum
GF_REFRESH = {"24h": 60, "7d": 300, "30d": 900}

# Panels ohne Zeitreihen
GF_SKIP_TYPES = {"row", "text", "news", "dashlist", "alertlist", "annolist", "welcome",
                 "gettingstarted", "nodeGraph", "logs", "traces", "flamegraph", "canvas",
                 "geomap", "debug"}

# Grafana-Einheiten (fieldConfig.defaults.unit) -> Anzeige. Unbekannte bleiben leer.
GF_UNITS = {
    "celsius": "°C", "fahrenheit": "°F", "kelvin": "K",
    "percent": "%", "percentunit": "", "humidity": "%",
    "watt": "W", "kwatt": "kW", "mwatt": "mW", "megwatt": "MW",
    "watth": "Wh", "kwatth": "kWh", "mwatth": "mWh", "kwattm": "kWm",
    "voltamp": "VA", "kvoltamp": "kVA", "voltampreact": "var",
    "volt": "V", "mvolt": "mV", "kvolt": "kV",
    "amp": "A", "mamp": "mA", "hertz": "Hz",
    "lux": "lx", "lumens": "lm",
    "pressurehpa": "hPa", "pressurembar": "mbar", "pressurebar": "bar", "pressurekpa": "kPa",
    "pressurepa": "Pa", "pressurepsi": "psi",
    "lengthmm": "mm", "lengthm": "m", "lengthkm": "km",
    "velocityms": "m/s", "velocitykmh": "km/h", "velocitymph": "mph", "velocityknot": "kn",
    "m3": "m³", "litre": "l", "mlitre": "ml", "flowlpm": "l/min", "flowcms": "m³/s",
    "flowm3h": "m³/h", "litreh": "l/h",
    "ppm": "ppm", "conppm": "ppm", "conppb": "ppb", "conμgm3": "µg/m³", "conmgm3": "mg/m³",
    "degree": "°", "s": "s", "m": "min", "h": "h", "d": "d", "ms": "ms",
    "currencyEUR": "€", "currencyUSD": "$", "currencyCHF": "CHF",
    "decbytes": "B", "bytes": "B",
}
GF_BOOL_UNITS = {"bool", "bool_yes_no", "bool_on_off"}

# $name, ${name}, ${name:format}, [[name]]
_GF_VAR = re.compile(r"\$\{(\w+)(?::[^}]*)?\}|\$(\w+)|\[\[(\w+)\]\]")


def gf_id(dash_uid: str, panel_id) -> str:
    return f"gf:{dash_uid}:{panel_id}"


def gf_parse(u) -> tuple[str, int] | None:
    """Pseudo-UUID "gf:<dashboard-uid>:<panel-id>" -> (uid, id), sonst None."""
    m = GF_ID.match(str(u or ""))
    return (m.group(1), int(m.group(2))) if m else None


def gf_url(raw) -> str:
    """Eingabe "10.0.0.55:3000" o.ae. -> "http://10.0.0.55:3000" (ohne / am Ende).
    Ein Pfad bleibt (Grafana hinter einem Proxy). Ungueltig -> ""."""
    s = str(raw or "").strip()
    if not s:
        return ""
    if "://" not in s:
        s = "http://" + s
    try:
        p = urlsplit(s)
    except ValueError:
        return ""
    if p.scheme not in ("http", "https") or not p.hostname or p.username or p.password:
        return ""
    return s.split("?", 1)[0].split("#", 1)[0].rstrip("/")


def _grafana_config() -> dict:
    """loxpanel.cfg `grafana`: {"url", "token", "user", "pass"}; ohne gueltige URL {}."""
    g = _load_cfg().get("grafana")
    if not isinstance(g, dict) or not gf_url(g.get("url")):
        return {}
    return {"url": gf_url(g.get("url")), "token": str(g.get("token") or "").strip(),
            "user": str(g.get("user") or "").strip(), "pass": str(g.get("pass") or "")}


def _gf_panels(dash: dict) -> list[dict]:
    """Alle Panels eines Dashboards, auch die in (zugeklappten) Zeilen und im
    alten Schema mit `rows`."""
    out = []

    def walk(panels):
        for p in panels or []:
            if not isinstance(p, dict):
                continue
            if p.get("type") == "row":
                walk(p.get("panels"))
            else:
                out.append(p)
                walk(p.get("panels"))   # Bibliotheks-/verschachtelte Panels
    walk(dash.get("panels"))
    for r in dash.get("rows") or []:
        if isinstance(r, dict):
            walk(r.get("panels"))
    return out


def _gf_panel_ok(p: dict) -> bool:
    """Zeigt das Panel Zeitreihen aus Abfragen? (Text, Listen, Zeilen nicht)"""
    return (p.get("type") not in GF_SKIP_TYPES and isinstance(p.get("id"), int)
            and any(isinstance(t, dict) and not t.get("hide") for t in p.get("targets") or []))


def _gf_unit(u) -> str:
    u = str(u or "")
    if u in GF_UNITS:
        return GF_UNITS[u]
    for kopf in ("suffix:", "si:"):
        if u.startswith(kopf):
            return u[len(kopf):].strip()[:12]
    return ""


def _gf_vars(dash: dict) -> dict:
    """Dashboard-Variablen mit ihrem gespeicherten Wert (templating.list[].current)."""
    out = {}
    for v in ((dash.get("templating") or {}).get("list") or []):
        if not isinstance(v, dict) or not v.get("name"):
            continue
        cur = (v.get("current") or {}).get("value")
        if cur is None and v.get("type") == "constant":
            cur = v.get("query")
        if cur is not None:
            out[str(v["name"])] = cur
    return out


def _gf_var_text(val) -> str:
    """Wert einer Variablen fuer die Abfrage: mehrere Werte als (a|b) - so
    passt er in die ueblichen Regex-Filter (=~ /^$raum$/)."""
    if isinstance(val, list):
        vals = [str(x) for x in val if x is not None]
        if any(x == "$__all" for x in vals):
            return ".*"
        if len(vals) == 1:
            return vals[0]
        return "(" + "|".join(vals) + ")"
    return ".*" if val == "$__all" else str(val)


def _gf_interpolate(obj, vars_: dict):
    """Dashboard-Variablen in allen Texten einer Abfrage einsetzen. Grafanas
    eigene ($__interval, $timeFilter ...) und unbekannte bleiben stehen."""
    if isinstance(obj, str):
        def ersetzen(m):
            name = m.group(1) or m.group(2) or m.group(3)
            if name.startswith("__") or name not in vars_:
                return m.group(0)
            return _gf_var_text(vars_[name])
        return _GF_VAR.sub(ersetzen, obj)
    if isinstance(obj, list):
        return [_gf_interpolate(x, vars_) for x in obj]
    if isinstance(obj, dict):
        return {k: _gf_interpolate(v, vars_) for k, v in obj.items()}
    return obj


def _gf_ds_ref(ref, vars_: dict, dsinfo: dict) -> dict | None:
    """Datenquelle eines Panels/Targets -> {"uid", "type"[, "id"]} fuer /api/ds/query.

    Grafana kennt drei Schreibweisen: {"type", "uid"} (ab 8.3), den Namen als
    Text (aelter) und Variablen (${DS_INFLUXDB}, $ds). Namen und Variablen
    loest die Datenquellen-Liste aus /api/frontend/settings auf; ohne Angabe
    gilt die Standard-Datenquelle."""
    by_name, by_uid, default = dsinfo.get("by_name", {}), dsinfo.get("by_uid", {}), dsinfo.get("default")
    if ref in (None, "", "default"):
        return default
    if isinstance(ref, dict):
        key = str(ref.get("uid") or "")
        if not key:
            return default
    else:
        key = str(ref)
    if key in ("-- Mixed --", "-- Dashboard --"):
        return None
    m = re.fullmatch(r"\$\{(\w+)(?::[^}]*)?\}|\$(\w+)", key)
    if m:
        name = m.group(1) or m.group(2)
        val = vars_.get(name)
        if isinstance(val, list):
            val = val[0] if val else None
        if val in (None, "", "default"):
            return default
        key = str(val)
    if key in by_uid:
        return by_uid[key]
    if key in by_name:
        return by_name[key]
    if isinstance(ref, dict) and ref.get("uid") == key:
        return {"uid": key, **({"type": ref["type"]} if ref.get("type") else {})}
    return {"uid": key}


def _gf_series(results: dict, order: list[str]) -> tuple[list, str]:
    """Antwort von /api/ds/query -> ([(name, [(epoch_s, wert)], feld-config)], fehler).

    Jede Abfrage (refId) liefert Frames: ein Zeitfeld und ein oder mehrere
    Zahlenfelder. Der Name kommt wie in Grafana aus displayNameFromDS bzw.
    displayName, sonst aus Labels, Frame- oder Feldname."""
    out, fehler = [], ""
    refs = [r for r in order if r in results] + [r for r in results if r not in order]
    for ref in refs:
        res = results.get(ref) or {}
        if res.get("error"):
            fehler = fehler or str(res.get("error"))[:200]
        for fr in res.get("frames") or []:
            schema = (fr or {}).get("schema") or {}
            fields = schema.get("fields") or []
            vals = ((fr or {}).get("data") or {}).get("values") or []
            ti = next((i for i, f in enumerate(fields) if (f or {}).get("type") == "time"), None)
            if ti is None or ti >= len(vals):
                continue
            nums = [i for i, f in enumerate(fields)
                    if i != ti and (f or {}).get("type") == "number" and i < len(vals)]
            for i in nums:
                f = fields[i] or {}
                cfg = f.get("config") or {}
                labels = f.get("labels") or {}
                name = cfg.get("displayNameFromDS") or cfg.get("displayName")
                if not name and labels:
                    name = ", ".join(str(v) for v in labels.values())
                if not name and len(nums) == 1 and schema.get("name"):
                    name = schema["name"]
                if not name:
                    name = f.get("name") or ref
                pts = []
                for t, v in zip(vals[ti], vals[i]):
                    if t is None or v is None or isinstance(v, bool):
                        continue
                    try:
                        pts.append((float(t) / 1000.0, float(v)))
                    except (TypeError, ValueError):
                        continue
                pts.sort(key=lambda p: p[0])
                out.append((_clean(str(name))[:60], pts, cfg))
    return out, fehler


def _gf_wall(epoch: float) -> int:
    """Unix-Sekunden -> Wanduhr-Sekunden (Ortszeit als UTC gefuehrt), wie die
    Zeitstempel der Loxone-Statistik (statistik.py)."""
    return int(epoch + time.localtime(epoch).tm_gmtoff)


def _gf_dec(defaults: dict, vals: list) -> int:
    d = defaults.get("decimals")
    if isinstance(d, int) and not isinstance(d, bool) and 0 <= d <= 4:
        return d
    m = max((abs(v) for v in vals), default=0)
    return 2 if m < 10 else (1 if m < 100 else 0)


def _gf_kind(panel: dict, unit_raw: str) -> str:
    """Darstellung wie im Panel: Balken (Block-Art "counter": Balken je Punkt),
    Ein/Aus-Werte als Stufen ("digital"), sonst Linie."""
    if unit_raw in GF_BOOL_UNITS:
        return "digital"
    custom = ((panel.get("fieldConfig") or {}).get("defaults") or {}).get("custom") or {}
    if custom.get("drawStyle") == "bars" or (panel.get("type") == "graph" and panel.get("bars")
                                             and not panel.get("lines")):
        return "counter"
    return "line"


class Grafana:
    """Grafana als zweite Verlaufsquelle; Mixin der App (self ist die App)."""

    def _grafana_init(self) -> None:
        self.gf_cfg: dict = _grafana_config()
        self.gf_session: aiohttp.ClientSession | None = None
        # (pseudo-uuid, Zeitraum) -> (monotonic, Daten oder None, Fehlertext)
        self.gf_cache: dict[tuple[str, str], tuple[float, dict | None, str]] = {}
        self.gf_pending: set[tuple[str, str]] = set()
        self.gf_dash: dict[str, tuple[float, dict | None]] = {}     # uid -> (monotonic, Dashboard)
        self.gf_ds: tuple[float, dict] | None = None                # Datenquellen
        self.gf_katalog: tuple[float, dict] | None = None           # Panel-Liste
        self.gf_sem = asyncio.Semaphore(3)

    def grafana_neu(self) -> None:
        """Zugang neu gelesen (Einstellungen gespeichert): alles vergessen und neu holen."""
        self.gf_cfg = _grafana_config()
        self.gf_cache, self.gf_dash, self.gf_ds, self.gf_katalog = {}, {}, None, None
        self.stat_gen += 1
        self.stat_memo = {}
        self._dirty = True

    async def grafana_close(self) -> None:
        if self.gf_session:
            await self.gf_session.close()
            self.gf_session = None

    # ---- HTTP -------------------------------------------------------------------
    @staticmethod
    def _gf_auth(cfg: dict) -> tuple[dict, aiohttp.BasicAuth | None]:
        if cfg.get("token"):
            return {"Authorization": f"Bearer {cfg['token']}"}, None
        if cfg.get("user"):
            return {}, aiohttp.BasicAuth(cfg["user"], cfg.get("pass") or "")
        return {}, None

    async def _gf_request(self, method: str, path: str, body=None, cfg: dict | None = None):
        """Anfrage an Grafana -> (status, json oder None). Zertifikate werden nicht
        geprueft (Grafana im Heimnetz, oft selbstsigniert)."""
        cfg = cfg if cfg is not None else self.gf_cfg
        if not cfg.get("url"):
            raise ConnectionError("Grafana ist nicht eingerichtet")
        if self.gf_session is None or self.gf_session.closed:
            self.gf_session = aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False))
        headers, auth = self._gf_auth(cfg)
        headers = {**headers, "Accept": "application/json"}
        async with self.gf_sem:
            async with self.gf_session.request(
                    method, cfg["url"] + path, json=body, headers=headers, auth=auth,
                    timeout=aiohttp.ClientTimeout(total=GF_TIMEOUT), allow_redirects=False) as r:
                try:
                    data = await r.json(content_type=None)
                except ValueError:
                    data = None
                return r.status, data

    @staticmethod
    def _gf_fehler(status: int, data) -> str:
        if status in (401, 403):
            return "Anmeldung abgelehnt (Token bzw. Benutzer prüfen)"
        if status in (301, 302, 303, 307, 308):
            return "Grafana leitet zur Anmeldung um (Token bzw. Benutzer prüfen)"
        if status == 404:
            return "nicht gefunden (Adresse prüfen)"
        msg = (data or {}).get("message") if isinstance(data, dict) else None
        return f"HTTP {status}" + (f": {str(msg)[:160]}" if msg else "")

    async def grafana_pruefen(self, cfg: dict) -> dict:
        """Zugang testen (Einstellungen -> Grafana): Version und Zahl der Dashboards."""
        try:
            st, health = await self._gf_request("GET", "/api/health", cfg=cfg)
            if st != 200 or not isinstance(health, dict):
                return {"ok": False, "error": "Keine Grafana unter dieser Adresse"
                        + (f" ({self._gf_fehler(st, health)})" if st != 200 else "")}
            st, found = await self._gf_request("GET", "/api/search?type=dash-db&limit=1000", cfg=cfg)
            if st != 200 or not isinstance(found, list):
                return {"ok": False, "version": health.get("version"), "error": self._gf_fehler(st, found)}
            return {"ok": True, "version": health.get("version"), "dashboards": len(found)}
        except (aiohttp.ClientError, asyncio.TimeoutError, ConnectionError, OSError) as err:
            return {"ok": False, "error": f"nicht erreichbar ({err.__class__.__name__}: {err})"[:200]}

    # ---- Dashboards, Datenquellen, Panel-Liste ----------------------------------
    async def _gf_dashboard(self, uid: str) -> dict:
        ent = self.gf_dash.get(uid)
        if ent and ent[1] is not None and time.monotonic() - ent[0] < GF_DASH_REFRESH:
            return ent[1]
        st, data = await self._gf_request("GET", f"/api/dashboards/uid/{quote(uid)}")
        if st != 200 or not isinstance(data, dict) or not isinstance(data.get("dashboard"), dict):
            raise ConnectionError(f"Dashboard {uid}: {self._gf_fehler(st, data)}")
        dash = data["dashboard"]
        dash["_folder"] = ((data.get("meta") or {}).get("folderTitle") or "")
        self.gf_dash[uid] = (time.monotonic(), dash)
        if len(self.gf_dash) > GF_KATALOG_DASH_MAX:
            self.gf_dash.pop(next(iter(self.gf_dash)))
        return dash

    async def _gf_datasources(self) -> dict:
        """Datenquellen nach Name und UID aus /api/frontend/settings - das darf
        jeder angemeldete Benutzer lesen (/api/datasources nur Admins)."""
        if self.gf_ds and time.monotonic() - self.gf_ds[0] < GF_DS_REFRESH:
            return self.gf_ds[1]
        st, data = await self._gf_request("GET", "/api/frontend/settings")
        info: dict = {"by_name": {}, "by_uid": {}, "default": None}
        if st == 200 and isinstance(data, dict):
            for name, d in (data.get("datasources") or {}).items():
                if not isinstance(d, dict) or not d.get("uid"):
                    continue
                ref = {"uid": d["uid"], "type": d.get("type")}
                if isinstance(d.get("id"), int):
                    ref["id"] = d["id"]
                info["by_name"][name] = info["by_uid"][d["uid"]] = ref
                if d.get("isDefault"):
                    info["default"] = ref
            dn = data.get("defaultDatasource")
            if dn in info["by_name"]:
                info["default"] = info["by_name"][dn]
        self.gf_ds = (time.monotonic(), info)
        return info

    async def grafana_katalog(self, frisch: bool = False) -> dict:
        """Alle Grafana-Panels mit Abfragen fuer den Konfigurator:
        {"ok", "error", "panels": [{"uuid", "name", "roomName"}]}."""
        if not self.gf_cfg.get("url"):
            return {"ok": False, "error": "", "panels": []}
        if not frisch and self.gf_katalog and time.monotonic() - self.gf_katalog[0] < GF_KATALOG_REFRESH:
            return self.gf_katalog[1]
        try:
            st, found = await self._gf_request("GET", "/api/search?type=dash-db&limit=1000")
            if st != 200 or not isinstance(found, list):
                raise ConnectionError(self._gf_fehler(st, found))
            uids = [(d.get("uid"), d.get("title"), d.get("folderTitle"))
                    for d in found if isinstance(d, dict) and d.get("uid")][:GF_KATALOG_DASH_MAX]
            dashes = await asyncio.gather(*(self._gf_dashboard(u) for u, _t, _f in uids),
                                          return_exceptions=True)
            panels = []
            for (uid, title, folder), dash in zip(uids, dashes):
                if not isinstance(dash, dict):
                    continue
                ort = " / ".join(x for x in (_clean(folder or ""), _clean(dash.get("title") or title or uid)) if x)
                for p in _gf_panels(dash):
                    if _gf_panel_ok(p):
                        panels.append({"uuid": gf_id(uid, p["id"]),
                                       "name": _clean(p.get("title") or "") or f"Panel {p['id']}",
                                       "roomName": "Grafana · " + ort})
            erg = {"ok": True, "error": "", "panels": panels}
        except (aiohttp.ClientError, asyncio.TimeoutError, ConnectionError, OSError) as err:
            log.info("Grafana-Panels nicht abrufbar: %s", err)
            alt = self.gf_katalog[1]["panels"] if self.gf_katalog else []
            erg = {"ok": False, "error": str(err)[:200] or err.__class__.__name__, "panels": alt}
        self.gf_katalog = (time.monotonic(), erg)
        return erg

    # ---- Daten ------------------------------------------------------------------
    async def _gf_load(self, gid: str, rng: str) -> None:
        """Daten eines Panels im Zeitraum holen und in gf_cache legen; danach
        neu rendern lassen (wie _stat_load)."""
        key = (gid, rng)
        data, fehler = None, ""
        try:
            uid, pid = gf_parse(gid)
            dash = await self._gf_dashboard(uid)
            panel = next((p for p in _gf_panels(dash) if p.get("id") == pid), None)
            if panel is None:
                raise ConnectionError("Panel gibt es im Dashboard nicht mehr")
            dsinfo = await self._gf_datasources()
            vars_ = _gf_vars(dash)
            span = STAT_RANGES[rng][1]
            jetzt = int(time.time())
            queries, order = [], []
            for n, tg in enumerate(panel.get("targets") or []):
                if not isinstance(tg, dict) or tg.get("hide"):
                    continue
                ds = _gf_ds_ref(tg.get("datasource") or panel.get("datasource"), vars_, dsinfo)
                if ds is None:
                    continue
                q = _gf_interpolate({k: v for k, v in tg.items() if k != "datasource"}, vars_)
                q["refId"] = str(tg.get("refId") or chr(65 + n % 26))
                q["datasource"] = {k: v for k, v in ds.items() if k != "id"}
                if "id" in ds:
                    q["datasourceId"] = ds["id"]     # Grafana vor 8.5 verlangt die ID
                q["maxDataPoints"] = GF_MAX_POINTS
                q["intervalMs"] = max(1000, span * 1000 // GF_MAX_POINTS)
                queries.append(q)
                order.append(q["refId"])
            if not queries:
                raise ConnectionError("Panel hat keine Abfrage mit bekannter Datenquelle")
            body = {"queries": queries, "from": str((jetzt - span) * 1000), "to": str(jetzt * 1000)}
            st, res = await self._gf_request("POST", "/api/ds/query", body)
            if st not in (200, 207) or not isinstance(res, dict):
                raise ConnectionError(self._gf_fehler(st, res))
            series, fehler = _gf_series(res.get("results") or {}, order)
            defaults = (panel.get("fieldConfig") or {}).get("defaults") or {}
            unit_raw = str(defaults.get("unit") or panel.get("format") or "")
            name1 = defaults.get("displayName")
            if name1 and "$" not in str(name1) and len(series) == 1:
                series = [(_clean(str(name1))[:60], series[0][1], series[0][2])]
            data = {"title": _clean(panel.get("title") or "") or _clean(dash.get("title") or ""),
                    "unit": _gf_unit(unit_raw), "kind": _gf_kind(panel, unit_raw),
                    "dec": _gf_dec(defaults, [v for _n, pts, _c in series for _t, v in pts]),
                    "series": [(n, pts) for n, pts, _c in series[:GF_MAX_SERIES]]}
            if fehler and not any(pts for _n, pts in data["series"]):
                log.info("Grafana %s: %s", gid, fehler)
        except (aiohttp.ClientError, asyncio.TimeoutError, ConnectionError, OSError, ValueError) as err:
            fehler = str(err)[:200] or err.__class__.__name__
            log.info("Grafana %s (%s) nicht abrufbar: %s", gid, rng, fehler)
            data = None
        finally:
            self.gf_pending.discard(key)
        self.gf_cache.pop(key, None)
        self.gf_cache[key] = (time.monotonic(), data, fehler)
        while len(self.gf_cache) > GF_CACHE_MAX:
            self.gf_cache.pop(next(iter(self.gf_cache)))
        self.stat_gen += 1
        self.stat_memo = {}
        self._dirty = True

    def grafana_chart(self, gid: str, rng: str) -> dict | None:
        """Ein Grafana-Panel fuer die Verlaufs-Pane, im Format von chart_blocks():
        Name, letzter Wert, ein Diagramm-Block. Fehlende oder alte Daten werden
        im Hintergrund geholt. None, wenn Grafana nicht eingerichtet ist."""
        if not (self.gf_cfg.get("url") and gf_parse(gid)):
            return None
        key = (gid, rng)
        ent = self.gf_cache.get(key)
        alter = time.monotonic() - ent[0] if ent else 0.0
        if ent is None or alter >= (GF_RETRY if ent[1] is None else GF_REFRESH.get(rng, 300)):
            if key not in self.gf_pending:
                self.gf_pending.add(key)
                self._spawn(self._gf_load(gid, rng))
        now = calendar.timegm(datetime.now().timetuple())
        t1 = now - now % 60
        mkey = ("grafana", gid, rng, t1, self.stat_gen)
        if mkey in self.stat_memo:
            return self.stat_memo[mkey]
        t0 = t1 - STAT_RANGES[rng][1]
        data = ent[1] if ent else None
        name = (data or {}).get("title") or self._gf_katalog_name(gid) or "Grafana"
        blk = {"k": "chart", "kind": "line", "unit": "", "series": [], "t0": t0, "t1": t1,
               "range": rng, "ranges": [[k, v[0]] for k, v in STAT_RANGES.items()]}
        value = ""
        if data is None:
            blk["state"] = "loading" if ent is None else "error"
        else:
            kind, dec, unit = data["kind"], data["dec"], data["unit"]
            series = []
            for sname, pts in data["series"]:
                wp = [(_gf_wall(t), v) for t, v in pts]
                if kind != "counter" and len(wp) > GF_MAX_POINTS:
                    wp = _stat_thin(wp, t0, t1, GF_MAX_POINTS, kind == "digital")
                series.append({"name": sname, "dec": dec,
                               "pts": [[int(t), round(v, dec + 2)] for t, v in wp]})
            blk.update(kind=kind, unit=unit, series=series,
                       state="ok" if any(s["pts"] for s in series) else "empty")
            first = next((s for s in series if s["pts"]), None)
            if first and kind == "digital":
                value = "Ein" if first["pts"][-1][1] >= 0.5 else "Aus"
            elif first:
                value = self._fmt_num(first["pts"][-1][1], f"%.{dec}f" + (unit.replace("%", "%%")
                                                                         if unit else ""))
        out = {"control": gid, "name": name, "value": value, "range": rng, "blocks": [blk]}
        if len(self.stat_memo) > 64:
            self.stat_memo = {}
        self.stat_memo[mkey] = out
        return out

    def _gf_katalog_name(self, gid: str) -> str:
        if not self.gf_katalog:
            return ""
        return next((p["name"] for p in self.gf_katalog[1].get("panels") or [] if p["uuid"] == gid), "")
