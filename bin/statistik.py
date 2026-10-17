"""Verlaeufe aus den Statistik-Dateien des Miniservers: die Dateien laden
(Statistik v1 als XML je Monat, v2 als Binaerdaten je Zeitraum), parsen, auf
die Punktzahl der Visu ausduennen und zu Tagesbalken buendeln, daraus die
Verlaufsbloecke der Detailseite (Block k:"chart") und die Mini-Verlaeufe der
Kacheln (it.spark).

Die Methoden sind ein Mixin (Statistik): App erbt sie, sie arbeiten mit dem
Zustand der App (stat_cache, stat2_cache, stat_memo, stat_pending, Client).
Importiert webvisu nicht."""
from __future__ import annotations

import asyncio
import calendar
import logging
import math
import re
import struct
import time
from datetime import datetime, timedelta
from urllib.parse import quote

import aiohttp

from bausteine.gemeinsam import _clean, STAT_WEEKDAYS
from konfig import STAT_RANGES, SV_STATUS_MAX

log = logging.getLogger("loxpanel.webvisu")   # derselbe Logger wie der Server: die Methoden gehoeren zu App


STAT_DEFAULT_RANGE = "24h"

STAT_MAX_POINTS = 240    # Punkte je Linie nach dem Ausduennen (Diagramm ~440 px breit)

STAT_REFRESH = 300       # Monatsdatei, die noch waechst, nach so vielen Sekunden neu holen

STAT_RETRY = 60          # nach einem Abruffehler fruehestens wieder versuchen

STAT_CACHE_MAX = 240     # Monatsdateien im Speicher (abgeschlossene Monate aendern sich nicht)

# visuType der Statistik-Ausgaenge, wie an der Anlage beobachtet: 0 Analogwert
# (Temperatur, Leistung ...), 1 Digitalwert (Regen, Sonnenschein), 2 Zaehlerstand
# (Gesamtverbrauch kWh). Zaehlerstaende zeigen den Verbrauch je Stunde/Tag als Balken.
STAT_KIND = {1: "digital", 2: "counter"}

_STAT_ROW = re.compile(r"<S\s([^>]*?)/?>")

_STAT_ATTR = re.compile(r'(\w+)="([^"]*)"')


def _parse_stat_xml(text: str) -> list:
    """Loxone-Statistik-Monatsdatei -> [(sekunden, [werte ...])], zeitlich sortiert.

    Jede Zeile ist <S T="JJJJ-MM-TT hh:mm:ss" V="1.23"/>; bei mehreren
    Ausgaengen stehen weitere Wert-Attribute in Ausgangsreihenfolge dahinter.
    Gelesen wird deshalb jedes Attribut ausser T in Dokumentreihenfolge, ohne
    Annahme ueber seinen Namen. Per Regex statt XML-Parser: die Datei ist flach,
    und so gibt es keine Entitaeten-Aufloesung. Zeitstempel sind Ortszeit des
    Miniservers und werden als Wanduhr-Sekunden (timegm) gefuehrt, damit Server
    und Panel ohne Zeitzonenrechnung dieselbe Uhrzeit zeigen."""
    out = []
    for m in _STAT_ROW.finditer(text or ""):
        ts, vals = None, []
        for name, raw in _STAT_ATTR.findall(m.group(1)):
            if name == "T":
                try:
                    ts = calendar.timegm(datetime.strptime(raw, "%Y-%m-%d %H:%M:%S").timetuple())
                except ValueError:
                    ts = None
            else:
                try:
                    vals.append(float(raw))
                except ValueError:
                    vals.append(None)
        if ts is not None and vals:
            out.append((ts, vals))
    out.sort(key=lambda r: r[0])
    return out


def _stat_fmt(fmt) -> tuple[int, str]:
    """Loxone-Zahlenformat -> (Nachkommastellen, Einheit). Zwei Schreibweisen:
    printf wie bei `statistic` ("%.1f °C", "%.0f%", "%.0fLx") und die Maske von
    `statisticV2` ("0,000kW", "0,0kWh", "0,00€"). Ohne Format -> (0, "")."""
    s = str(fmt or "")
    m = re.search(r"%(?:\.(\d+))?[fd]", s)
    if m:
        return int(m.group(1) or 0), s[m.end():].replace("%%", "%").strip()
    m = re.match(r"^[#0]+(?:[.,]([#0]+))?(.*)$", s.strip())
    if m:
        return len(m.group(1) or ""), m.group(2).strip()
    return 0, ""


def _parse_stat2_bin(body: bytes, nvals: int = 1) -> list | None:
    """Antwort von jdev/sps/getStatistic/.../raw/... -> [(sekunden, [werte])].

    Binaer, je Eintrag 4 Byte Zeitstempel (uint32, Unix-UTC) und je Wert 8 Byte
    (float64), little-endian - an der Anlage so gemessen (PV 7,42 kW, Netz
    -6,26 kW, Eintraege im Abstand der Gruppe). Die Zeit wird wie bei den
    Monatsdateien in Wanduhr-Sekunden der Container-Zeitzone umgerechnet.
    Passt die Laenge nicht zum Eintragsformat -> None (unbekannte Antwort)."""
    size = 4 + 8 * nvals
    if len(body) % size:
        return None
    out = []
    for off in range(0, len(body), size):
        ts, *vals = struct.unpack_from("<I" + "d" * nvals, body, off)
        vals = [v if math.isfinite(v) else None for v in vals]
        out.append((calendar.timegm(time.localtime(ts)), vals))
    out.sort(key=lambda r: r[0])
    return out


def _stat_thin(pts: list, t0: int, t1: int, n: int, digital: bool) -> list:
    """Linie auf hoechstens n Punkte ausduennen: je Zeitfenster der Mittelwert
    (Analog) bzw. das Maximum (Digital: ein kurzes "Ein" soll sichtbar bleiben)."""
    if len(pts) <= n or t1 <= t0:
        return pts
    w = (t1 - t0) / n
    buckets: dict[int, list] = {}
    for t, v in pts:
        buckets.setdefault(min(n - 1, max(0, int((t - t0) / w))), []).append((t, v))
    out = []
    for b in sorted(buckets):
        items = buckets[b]
        if digital:
            out.append((items[-1][0], max(v for _, v in items)))
        else:
            out.append((int(sum(t for t, _ in items) / len(items)),
                        sum(v for _, v in items) / len(items)))
    return out


def _stat_buckets(pts: list, edges: list, t_end: int) -> list:
    """Zeitgewichteter Mittelwert je Abschnitt [edges[i], edges[i+1]). Ein Messwert
    gilt bis zum naechsten (Treppe) - so stimmt das auch fuer Digitalwerte, die nur
    bei Aenderung aufgezeichnet werden: der Mittelwert ist dann der Ein-Anteil.
    Abschnitte ohne bekannten Wert oder nach t_end -> None."""
    out, k, n = [], 0, len(pts)
    for a, b in zip(edges, edges[1:]):
        b2 = min(b, t_end)
        while k + 1 < n and pts[k + 1][0] <= a:
            k += 1
        if b2 <= a or not n or pts[0][0] >= b2:
            out.append(None)
            continue
        acc = dur = 0.0
        j = k
        while j < n and pts[j][0] < b2:
            t, v = pts[j]
            lo, hi = max(a, t), min(b2, pts[j + 1][0] if j + 1 < n else t_end)
            if hi > lo:
                acc += v * (hi - lo)
                dur += hi - lo
            j += 1
        out.append(acc / dur if dur else None)
    return out


def _stat_day_range(pts: list, edges: list, t_end: int) -> list:
    """Tiefst- und Hoechstwert je Abschnitt, mit dem Stand, der zu Beginn des
    Abschnitts galt. Abschnitte ohne bekannten Wert oder nach t_end -> None."""
    out = []
    for a, b in zip(edges, edges[1:]):
        if a >= t_end:
            out.append(None)
            continue
        vals = [v for t, v in pts if a <= t < min(b, t_end + 1)]
        prev = [v for t, v in pts if t < a]
        if prev:
            vals.append(prev[-1])
        out.append((min(vals), max(vals)) if vals else None)
    return out


def _stat_bars(pts: list, edges: list) -> list:
    """Zaehlerstaende -> Verbrauch je Abschnitt [edges[i], edges[i+1]).

    Summiert von Messpunkt zu Messpunkt: Grundlage ist der letzte Stand davor
    (pts beginnt mit dem letzten Wert vor dem Fenster, falls bekannt; sonst ist
    der erste Stand die Basis). Faellt der Stand auf weniger als die Haelfte,
    wurde der Zaehler zurueckgesetzt und zaehlt ab 0 weiter. Ein kleiner
    Ruecksprung (Rundung, 1000,5 -> 1000,4) ist kein Verbrauch, sonst ergaebe
    er einen Balken in Hoehe des ganzen Zaehlerstands."""
    out, i, prev = [], 0, None
    while i < len(pts) and pts[i][0] < edges[0]:
        prev = pts[i][1]
        i += 1
    for a, b in zip(edges, edges[1:]):
        use = 0.0
        while i < len(pts) and pts[i][0] < b:
            v = pts[i][1]
            if prev is not None:
                if v >= prev:
                    use += v - prev
                elif v < prev / 2:
                    use += v              # zurueckgesetzt: ab 0 weitergezaehlt
            prev = v
            i += 1
        out.append((a, use))
    return out


class Statistik:
    """Verlaufsdaten und Verlaufsbloecke; Mixin der App (self ist die App)."""

    async def _stat_load(self, ua: str, ym: str) -> None:
        """Eine Statistik-Monatsdatei holen (/stats/<uuidAction>.<JJJJMM>.xml,
        Bearer-Token wie bei den Icons) und in stat_cache legen. 404 heisst:
        fuer diesen Monat gibt es keine Aufzeichnung (leere Liste). Andere
        Fehler legen None ab, dann wird erst nach STAT_RETRY erneut versucht.
        Danach neu rendern lassen, damit offene Detailseiten das Diagramm zeigen."""
        key = (ua, ym)
        rows: list | None = None
        try:
            status, body, _ = await self._ms_http(f"stats/{ua}.{ym}.xml", 20)
            if status == 404:
                rows = []
            elif status == 200:
                rows = _parse_stat_xml(body.decode("utf-8", "replace"))
            else:
                log.info("Statistik %s.%s: HTTP %s", ua, ym, status)
        except (aiohttp.ClientError, asyncio.TimeoutError, ConnectionError) as err:
            log.info("Statistik %s.%s nicht abrufbar: %s", ua, ym, err)
        finally:
            self.stat_pending.discard(key)
        self.stat_cache.pop(key, None)          # neu einsortieren = zuletzt benutzt
        self.stat_cache[key] = (time.monotonic(), datetime.now().strftime("%Y%m"), rows)
        while len(self.stat_cache) > STAT_CACHE_MAX:
            self.stat_cache.pop(next(iter(self.stat_cache)))
        self.stat_gen += 1
        self.stat_memo = {}
        self._dirty = True

    async def _stat2_load(self, key: tuple, ua: str, gid: str, out: str, span: int) -> None:
        """Verlauf eines statisticV2-Ausgangs holen: jdev/sps/getStatistic/<uuid>/raw/
        <vonUnixUtc>/<bisUnixUtc>/all/<gruppe>/<ausgang> (so baut ihn die Loxone-App,
        StatisticV2Ext.getStatisticRaw). Eine Stunde Vorlauf liefert den Stand vor
        dem ersten Balken. Leere Antwort oder JSON statt Binaerdaten heisst: keine
        Aufzeichnung (leere Liste); andere Fehler legen None ab."""
        rows: list | None = None
        now = int(time.time())
        path = f"jdev/sps/getStatistic/{ua}/raw/{now - span - 3600}/{now}/all/{quote(gid)}/{quote(out)}"
        try:
            async with self.stat2_sem:
                status, body, _ = await self._ms_http(path, 30)
            if status != 200:
                log.info("Statistik V2 %s: HTTP %s", path, status)
            elif not body:
                rows = []
            elif body[:1] == b"{":
                rows = []
                log.info("Statistik V2 %s: keine Daten (%s)", path, body[:160].decode("utf-8", "replace"))
            else:
                rows = _parse_stat2_bin(body)
                if rows is None:
                    log.info("Statistik V2 %s: unerwartete Antwort, %d Bytes", path, len(body))
        except (aiohttp.ClientError, asyncio.TimeoutError, ConnectionError) as err:
            log.info("Statistik V2 %s nicht abrufbar: %s", path, err)
        finally:
            self.stat_pending.discard(key)
        self.stat2_cache.pop(key, None)
        self.stat2_cache[key] = (time.monotonic(), rows)
        while len(self.stat2_cache) > STAT_CACHE_MAX:
            self.stat2_cache.pop(next(iter(self.stat2_cache)))
        self.stat_gen += 1
        self.stat_memo = {}
        self._dirty = True

    @staticmethod
    def _stat_months(t0: int, t1: int) -> list[str]:
        """Monatsschluessel JJJJMM, die das Fenster [t0, t1] (Wanduhr-Sekunden) beruehrt."""
        a = datetime(1970, 1, 1) + timedelta(seconds=t0)
        b = datetime(1970, 1, 1) + timedelta(seconds=t1)
        y, m, out = a.year, a.month, []
        while (y, m) <= (b.year, b.month):
            out.append(f"{y:04d}{m:02d}")
            y, m = (y + 1, 1) if m == 12 else (y, m + 1)
        return out

    @staticmethod
    def _stat_edges(rng: str, t1: int) -> list[int]:
        """Abschnittsgrenzen der Verbrauchsbalken: bei 24 h je volle Stunde, sonst
        je Tag ab Mitternacht. Der letzte Abschnitt laeuft bis jetzt."""
        if rng == "24h":
            step, n = 3600, 24
        else:
            step, n = 86400, STAT_RANGES[rng][1] // 86400
        start = t1 - t1 % step - (n - 1) * step
        return [start + k * step for k in range(n)] + [t1 + 1]

    def _stat_rows(self, ua: str, t0: int, t1: int) -> tuple[list, bool, bool]:
        """Zeilen im Fenster aus stat_cache, vorneweg der letzte Stand davor (falls
        bekannt). Fehlende oder noch wachsende Monate werden im Hintergrund
        nachgeladen. -> (zeilen, laedt_noch, abruffehler)"""
        allrows, loading, error = [], False, False
        now = time.monotonic()
        for ym in self._stat_months(t0, t1):
            key = (ua, ym)
            ent = self.stat_cache.get(key)
            if ent is None:
                want = True
            elif ent[2] is None:
                want = now - ent[0] >= STAT_RETRY
            else:
                want = ent[1] <= ym and now - ent[0] >= STAT_REFRESH
            if want and key not in self.stat_pending:
                self.stat_pending.add(key)
                self._spawn(self._stat_load(ua, ym))
            if ent is None:
                loading = True
            elif ent[2] is None:
                error = True
            else:
                allrows.extend(ent[2])
        allrows.sort(key=lambda r: r[0])
        before = [r for r in allrows if r[0] < t0]
        return ([before[-1]] if before else []) + [r for r in allrows if t0 <= r[0] <= t1], loading, error

    def _stat2_rows(self, ua: str, gid: str, out: str, rng: str, t0: int, t1: int) -> tuple[list, bool, bool]:
        """Wie _stat_rows, fuer einen statisticV2-Ausgang: Zeilen im Fenster, vorneweg
        der letzte Stand davor; fehlend oder aelter als STAT_REFRESH -> im
        Hintergrund neu holen. -> (zeilen, laedt_noch, abruffehler)"""
        key = (ua, gid, out, rng)
        ent = self.stat2_cache.get(key)
        age = time.monotonic() - ent[0] if ent else 0.0
        if ent is None or age >= (STAT_RETRY if ent[1] is None else STAT_REFRESH):
            if key not in self.stat_pending:
                self.stat_pending.add(key)
                self._spawn(self._stat2_load(key, ua, gid, out, STAT_RANGES[rng][1]))
        if ent is None:
            return [], True, False
        if ent[1] is None:
            return [], False, True
        before = [r for r in ent[1] if r[0] < t0]
        return ([before[-1]] if before else []) + [r for r in ent[1] if t0 <= r[0] <= t1], False, False

    @staticmethod
    def _stat_series_defs(c: dict) -> list:
        """Alle aufgezeichneten Reihen eines Bausteins als (name, art, stellen,
        einheit, quelle). `statistic`: je Ausgang, Art aus visuType, Quelle
        ("v1", index in der Monatsdatei). `statisticV2`: je Datenpunkt einer
        Gruppe, `accumulated` = Zaehlerstand, Quelle ("v2", gruppe, ausgang).
        Gleiche Titel in einer Gruppe (Netz: zweimal "Zaehlerstand") bekommen
        den Ausgangsnamen dazu."""
        defs = []
        for i, o in enumerate((c.get("statistic") or {}).get("outputs") or []):
            if isinstance(o, dict):
                dec, unit = _stat_fmt(o.get("format"))
                defs.append((_clean(o.get("name")) or f"Wert {i + 1}",
                             STAT_KIND.get(o.get("visuType"), "line"), dec, unit, ("v1", i)))
        for g in (c.get("statisticV2") or {}).get("groups") or []:
            if not isinstance(g, dict):
                continue
            dps = [d for d in (g.get("dataPoints") or []) if isinstance(d, dict) and d.get("output")]
            titles = [d.get("title") for d in dps]
            for d in dps:
                dec, unit = _stat_fmt(d.get("format"))
                name = _clean(d.get("title")) or d["output"]
                if titles.count(d.get("title")) > 1:
                    name = f"{name} · {d['output']}"
                defs.append((name, "counter" if g.get("accumulated") else "line", dec, unit,
                             ("v2", str(g.get("id")), str(d["output"]))))
        return defs

    def _stat_blocks(self, c: dict, rng: str) -> list:
        """Diagramm-Bloecke fuer einen Baustein mit `statistic` oder `statisticV2`.
        Reihen gleicher Art und Einheit teilen sich ein Diagramm (zwei Grillfuehler,
        Netz-Bezug und -Einspeisung), sonst je eines (Zaehler: Leistung als Linie,
        Verbrauch als Balken)."""
        defs = self._stat_series_defs(c)
        ua = c.get("uuidAction")
        if not (ua and defs):
            return []
        now = calendar.timegm(datetime.now().timetuple())
        t1 = now - now % 60                    # Fenster rueckt je Minute vor
        mkey = (ua, rng, t1, self.stat_gen)
        if mkey in self.stat_memo:
            return self.stat_memo[mkey]
        t0 = t1 - STAT_RANGES[rng][1]
        v1 = None                              # Monatsdateien: eine Abfrage fuer alle Ausgaenge
        groups: dict[tuple[str, str], list] = {}
        for d in defs:
            groups.setdefault((d[1], d[3]), []).append(d)
        blocks = []
        for kind, unit in groups:
            edges = self._stat_edges(rng, t1) if kind == "counter" else None
            series, any_rows, loading, error = [], False, False, False
            for name, _kind, dec, _unit, src in groups[(kind, unit)]:
                if src[0] == "v1":
                    if v1 is None:
                        v1 = self._stat_rows(ua, t0, t1)
                    rows, ld, er = v1
                    i = src[1]
                    pts = [(r[0], r[1][i]) for r in rows if i < len(r[1]) and r[1][i] is not None]
                else:
                    rows, ld, er = self._stat2_rows(ua, src[1], src[2], rng, t0, t1)
                    pts = [(r[0], r[1][0]) for r in rows if r[1] and r[1][0] is not None]
                any_rows, loading, error = any_rows or bool(rows), loading or ld, error or er
                if kind == "counter":
                    pts = _stat_bars(pts, edges)
                else:
                    if pts and pts[0][0] < t0:
                        pts[0] = (t0, pts[0][1])   # letzter Stand vor dem Fenster = Startwert
                    pts = _stat_thin(pts, t0, t1, STAT_MAX_POINTS, kind == "digital")
                series.append({"name": name, "dec": dec,
                               "pts": [[int(t), round(v, dec + 2)] for t, v in pts]})
            has = any_rows if kind == "counter" else any(s["pts"] for s in series)
            blk = {"k": "chart", "kind": kind, "unit": unit, "series": series,
                   "t0": edges[0] if edges else t0, "t1": t1,
                   "state": "ok" if has else ("loading" if loading else ("error" if error else "empty"))}
            if not blocks:                     # Zeitraum-Wahl nur am ersten Diagramm der Seite
                blk.update(range=rng, ranges=[[k, v[0]] for k, v in STAT_RANGES.items()])
            blocks.append(blk)
        if len(self.stat_memo) > 64:
            self.stat_memo = {}
        self.stat_memo[mkey] = blocks
        return blocks

    def chart_blocks(self, uuid: str, rng: str | None = None) -> dict | None:
        """Inhalt der Verlaufs-Pane im Split-Layout (panes "chart:<uuid>"): Name,
        aktueller Wert wie auf der Detailseite und die Diagramme aus
        _stat_blocks (dieselben Abrufe, Caches und Zustaende). None, wenn der
        Baustein fehlt oder nichts aufzeichnet."""
        c = self.controls.get(uuid)
        if not c or not (c.get("statistic") or c.get("statisticV2")):
            return None
        rng = rng if rng in STAT_RANGES else STAT_DEFAULT_RANGE
        v = self._view_control_inner(uuid)
        big = next((b.get("text") or "" for b in v.get("blocks") or [] if b.get("k") == "big"), "")
        return {"control": uuid, "name": _clean(c.get("name")), "value": big,
                "range": rng, "blocks": self._stat_blocks(c, rng)}

    def chart_stack(self, uuids, rng: str | None = None) -> dict:
        """Mehrere Verlaufs-Bausteine gestapelt fuer die Verlaufs-Pane
        (panes "chart:<uuid>,<uuid>,..."). Je Baustein Name, aktueller Wert und
        Diagramme (chart_blocks); der Zeitraum gilt fuer den ganzen Stapel. Die
        Zeitraum-Knoepfe traegt die Pane nur einmal oben (`ranges`), nicht jeder
        Baustein — die Visu blendet die Knoepfe der einzelnen Bloecke daher aus.
        Unbekannte/aufzeichnungslose Bausteine fallen still weg."""
        rng = rng if rng in STAT_RANGES else STAT_DEFAULT_RANGE
        charts = []
        for u in list(uuids or [])[:SV_STATUS_MAX]:
            cb = self.chart_blocks(u, rng)
            if cb is not None:
                charts.append(cb)
        return {"controls": [c["control"] for c in charts], "range": rng,
                "ranges": [[k, v[0]] for k, v in STAT_RANGES.items()],
                "charts": charts}

    def _stat_primary(self, c: dict) -> tuple | None:
        """Die Reihe, die eine Kachel zeigt: die erste Linie, sonst die erste Reihe."""
        defs = self._stat_series_defs(c)
        return next((d for d in defs if d[1] == "line"), defs[0] if defs else None)

    def _stat_raw(self, c: dict, d: tuple, rng: str, t0: int, t1: int) -> tuple[list, bool, bool]:
        """Rohpunkte einer Reihe im Fenster, vorneweg der letzte Stand davor, aus
        denselben Caches wie die Diagramme. -> (punkte, laedt_noch, abruffehler)"""
        ua, src = c.get("uuidAction"), d[4]
        if src[0] == "v1":
            rows, ld, er = self._stat_rows(ua, t0, t1)
            i = src[1]
            return [(r[0], r[1][i]) for r in rows if i < len(r[1]) and r[1][i] is not None], ld, er
        rows, ld, er = self._stat2_rows(ua, src[1], src[2], rng, t0, t1)
        return [(r[0], r[1][0]) for r in rows if r[1] and r[1][0] is not None], ld, er

    @staticmethod
    def _stat_dur(sec: float) -> str:
        """Dauer als "3 h 20 min" bzw. "40 min"."""
        h, m = int(sec // 3600), int(round(sec % 3600 / 60))
        if m == 60:
            h, m = h + 1, 0
        return f"{h} h" + (f" {m} min" if m else "") if h else f"{m} min"

    def _stat_spark(self, c: dict, rng: str, style: str = "trend") -> dict | None:
        """Mini-Verlauf fuer eine Kachel (tiles.<uuid>.chart/.chartStyle).

        trend    Verlauf im gewaehlten Zeitraum: Linie mit Tiefst-/Hoechstwert,
                 Digitalwert als Stufen, Zaehlerstand als Verbrauchsbalken.
        pattern  Tagesmuster: 7 Tage x 24 Stunden, je Stunde der zeitgewichtete
                 Mittelwert (Digital: Ein-Anteil, Zaehler: Verbrauch der Stunde).
        span     Tagesspanne (nur Linien): je Tag Tiefst-, Hoechst- und Mittelwert.

        `badge` ist die kurze Angabe im Kopf der Kachel; die Visu zeigt sie nur an."""
        d = self._stat_primary(c)
        ua = c.get("uuidAction")
        if not (d and ua):
            return None
        name, kind, dec, unit, src = d
        if style == "span" and kind != "line":
            style = "trend"
        now = calendar.timegm(datetime.now().timetuple())
        t1 = now - now % 60
        mkey = ("spark", ua, rng, style, t1, self.stat_gen)
        if mkey in self.stat_memo:
            return self.stat_memo[mkey]
        fmt = f"%.{dec}f{unit}"
        out: dict | None = None
        if style == "trend":
            blocks = self._stat_blocks(c, rng)
            b = next((x for x in blocks if x.get("kind") == kind and x.get("unit") == unit), None)
            if b is None:
                return None
            se = next((x for x in b.get("series") or [] if x.get("name") == name), (b.get("series") or [{}])[0])
            full = [tuple(p) for p in se.get("pts") or []]
            out = {"style": "trend", "kind": kind, "state": b.get("state"), "t0": b.get("t0"),
                   "t1": b.get("t1"), "dec": dec}
            if kind == "counter":
                out["pts"] = [list(p) for p in full]
                if full:
                    out["badge"] = "Σ " + self._fmt_num(sum(v for _, v in full), fmt)
            else:
                out["pts"] = [[int(t), round(v, dec + 2)]
                              for t, v in _stat_thin(full, b["t0"], b["t1"], 48, kind == "digital")]
                if full and kind == "line":
                    lo, hi = min(full, key=lambda p: p[1]), max(full, key=lambda p: p[1])
                    out["lo"], out["hi"] = [int(lo[0]), lo[1]], [int(hi[0]), hi[1]]
                    ago = [v for t, v in full if t <= t1 - 86400]
                    if ago:
                        delta = full[-1][1] - ago[-1]
                        step = 10 ** -dec / 2
                        arrow = "▲" if delta >= step else ("▼" if delta <= -step else "=")
                        out["badge"] = f"{arrow} {self._fmt_num(abs(delta), fmt)} in 24 h"
                elif full:
                    t0 = b["t0"]
                    raw, _ld, _er = self._stat_raw(c, d, rng, t0, t1)
                    share = _stat_buckets(raw, [t0, t1], t1)[0]
                    if share is not None:
                        out["badge"] = "Ein " + self._stat_dur(share * (t1 - t0))
        else:
            start = t1 - t1 % 86400 - 6 * 86400        # Mitternacht vor 6 Tagen
            raw, loading, error = self._stat_raw(c, d, "7d", start, t1)
            days = [STAT_WEEKDAYS[((start // 86400) + i + 3) % 7] for i in range(7)]   # 1.1.1970 = Do
            state = "ok" if raw else ("loading" if loading else ("error" if error else "empty"))
            out = {"style": style, "kind": kind, "state": state, "dec": dec, "days": days}
            if style == "pattern":
                edges = [start + h * 3600 for h in range(7 * 24 + 1)]
                if kind == "counter":
                    cells = [None if a >= t1 else v for (a, v) in _stat_bars(raw, edges)]
                else:
                    cells = _stat_buckets(raw, edges, t1)
                out["cells"] = [None if v is None else round(v, dec + 2) for v in cells]
                vals = [v for v in cells if v is not None]
                if vals and kind == "counter":
                    out["badge"] = "7 Tage · Σ " + self._fmt_num(sum(vals), fmt)
                elif vals and kind == "line":
                    out["badge"] = "7 Tage · max " + self._fmt_num(max(vals), fmt)
                elif vals:
                    out["badge"] = "7 Tage"
            else:
                edges = [start + i * 86400 for i in range(8)]
                rngs = _stat_day_range(raw, edges, t1)
                avgs = _stat_buckets(raw, edges, t1)
                out["spans"] = [None if r is None else [round(r[0], dec + 2), round(r[1], dec + 2),
                                                        None if a is None else round(a, dec + 2)]
                                for r, a in zip(rngs, avgs)]
                if rngs[-1] is not None:
                    lo, hi = rngs[-1]
                    out["badge"] = "heute " + self._fmt_num(lo, f"%.{dec}f") + "–" + self._fmt_num(hi, fmt)
        if len(self.stat_memo) > 64:
            self.stat_memo = {}
        self.stat_memo[mkey] = out
        return out
