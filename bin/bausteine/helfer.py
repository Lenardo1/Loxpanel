"""Allgemeine Helfer der Bausteine: States lesen (_state, _text, _json_state,
_json_list_map), Zahlen formatieren (_fmt_num), benannte Eintraege aus den
details (_named_items), Farben (_color_parse, _hsv_hex) und die einfachen
Seiten (_big_view, _gone_view). Mixin: App erbt Grundhelfer ueber
bausteine.BausteinHelfer, gerufen wird ueber self bzw. app. Importiert
webvisu nicht."""
from __future__ import annotations

import functools
import logging
import math
import re
from urllib.parse import unquote

from adapters import json_aus_text, JSON_TEXTE_MAX
from bausteine.gemeinsam import _clean, _sperre_lesen, SPERRE_DURCH, SPERRE_KURZ

log = logging.getLogger("loxpanel.webvisu")   # derselbe Logger wie der Server: die Methoden gehoeren zu App


# Tracker-Zeile: fuehrender Zeitstempel (TT.MM.JJ[JJ] HH:MM[:SS]) wird vom Text
# getrennt, damit er als Untertitel erscheint. Matcht sonst nichts -> ganze Zeile.
_TS_RE = re.compile(r"^\s*(\d{1,2}[.\-/]\d{1,2}[.\-/]\d{2,4}[ ,]+\d{1,2}:\d{2}(?::\d{2})?)\s+(.+)$")

_NUMFMT = re.compile(r"^(%[-+ 0-9.]*[dfeg])(.*)$")

_PREFIX = ["k", "M", "G", "T"]


@functools.lru_cache(maxsize=JSON_TEXTE_MAX)
def _json_fehler_melden(wo: str, txt: str) -> None:
    """Unlesbaren JSON-State einmal je Text melden, nicht bei jedem Rendern."""
    log.warning("%s nicht als JSON parsebar: %r", wo, txt[:200])


class Grundhelfer:
    """Allgemeine Helfer der Bausteine; Mixin der App (self ist die App)."""

    # ---- Zustands-Helfer ----
    def _state(self, control: dict, name: str):
        su = (control.get("states") or {}).get(name)
        return self.states.get(su) if su else None

    def _endlich(self, control: dict, name: str) -> float | None:
        """Zahl-State als endliche Zahl; None, wenn er fehlt, keine Zahl ist oder
        NaN/unendlich (als Binaer-Double gueltig): dann ist der Wert unbekannt."""
        try:
            v = float(self._state(control, name))
        except (TypeError, ValueError):
            return None
        return v if math.isfinite(v) else None

    def _text(self, control: dict, name: str) -> str:
        """Text-State, URL-dekodiert (Loxone liefert songName/artist prozentkodiert)."""
        v = self._state(control, name)
        return unquote(str(v)) if v not in (None, "") else ""

    def _sperre_text(self, uuid) -> str | None:
        """Sperre des Bausteins, an den ein Befehl an `uuid` geht (Baustein,
        uuidAction oder Unterbaustein, Zuordnung in sperre_state): Klartext wie
        "Gesperrt durch die Logik: Wartung", None = nicht gesperrt."""
        su = self.sperre_state.get(uuid) if isinstance(uuid, str) else None
        roh = self.states.get(su) if su else None
        sp = _sperre_lesen(unquote(roh).strip()) if isinstance(roh, str) else None
        if not sp:
            return None
        art, grund = sp
        wer = SPERRE_DURCH.get(art)
        return SPERRE_KURZ + (f" {wer}" if wer else "") + (f": {grund}" if grund else "")

    def _json_state(self, control: dict, name: str):
        """JSON-State (Loxone liefert Listen/Objekte als ggf. prozentkodierten
        Text). None, wenn leer oder nicht parsebar (dann einmal geloggt)."""
        raw = self._state(control, name)
        if raw in (None, ""):
            return None
        if not isinstance(raw, str):
            return raw
        txt = unquote(raw).strip()
        ok, wert = json_aus_text(txt)
        if not ok:
            _json_fehler_melden(f"{control.get('type')}.{name}", txt)
        return wert

    @staticmethod
    def _named_items(data) -> list[tuple[str, dict]]:
        """Liste/Objekt aus einem JSON-State in (Label, Eintrag)-Paare wandeln.
        Label aus name/title/label, sonst laufende Nummer."""
        if isinstance(data, dict):
            seq = list(data.items())
        elif isinstance(data, (list, tuple)):
            seq = list(enumerate(data))
        else:
            return []
        out = []
        for i, (key, e) in enumerate(seq):
            if isinstance(e, dict):
                label = _clean(e.get("name") or e.get("title") or e.get("label")) or str(key if isinstance(key, str) else i + 1)
                out.append((label, e))
            else:
                out.append((str(key if isinstance(key, str) else i + 1), {"value": e}))
        return out

    @staticmethod
    def _split_ts(line: str) -> tuple[str | None, str]:
        """Fuehrenden Zeitstempel abtrennen -> (zeitstempel|None, text)."""
        m = _TS_RE.match(line or "")
        return (m.group(1), m.group(2)) if m else (None, line or "")

    def _json_list_map(self, c: dict, name: str) -> dict:
        """State-Wert = JSON-Array [{id,name}] -> {id:name}."""
        raw = self._state(c, name)
        arr = json_aus_text(raw)[1] if isinstance(raw, str) else raw
        if not isinstance(arr, list):
            return {}
        return {int(x["id"]): x.get("name") for x in arr
                if isinstance(x, dict) and x.get("id") is not None}

    def _fmt_num(self, value, fmt: str) -> str:
        """Loxone-Formatstring anwenden, Einheiten skalieren (kWh→MWh), Komma-Dezimal."""
        try:
            value = float(value)
        except (TypeError, ValueError):
            return ""
        m = _NUMFMT.match(fmt or "%.1f")
        numfmt, unit = (m.group(1), m.group(2)) if m else ("%.1f", "")
        unit = unit.strip().replace("%%", "%")   # "%.2f kW"/"%.2fkW" -> "3,25 kW"; Loxone-Escape "%%" -> "%"
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

    @staticmethod
    def _color_parse(raw) -> tuple:
        """Loxone color-State parsen. RGB: 'hsv(h,s,v)' (h 0-360, s/v 0-100) ->
        ('rgb', h, s, v). Tunable White: 'temp(brightness,kelvin)' ->
        ('temp', brightness, kelvin, None). Sonst ('none', 0, 0, 0)."""
        s = str(raw or "")
        m = re.match(r"hsv\((\d+),(\d+),(\d+)\)", s, re.I)
        if m:
            return ("rgb", int(m.group(1)), int(m.group(2)), int(m.group(3)))
        m = re.match(r"temp\((\d+),(\d+)\)", s, re.I)
        if m:
            return ("temp", int(m.group(1)), int(m.group(2)), None)
        return ("none", 0, 0, 0)

    @staticmethod
    def _hsv_hex(h, s, v) -> str:
        """HSV (h 0-360, s/v 0-100) -> #rrggbb fuer die Farb-Vorschau."""
        import colorsys
        r, g, b = colorsys.hsv_to_rgb((h % 360) / 360.0, s / 100.0, v / 100.0)
        return "#%02x%02x%02x" % (round(r * 255), round(g * 255), round(b * 255))

    @staticmethod
    def _gone_view(route: dict, title: str, text: str) -> dict:
        """Unterseite, deren Gegenstand es (nicht mehr) gibt: nur der Hinweis."""
        return {"t": "view", "title": title, "route": route, "blocks": [{"k": "status", "text": text}]}

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
