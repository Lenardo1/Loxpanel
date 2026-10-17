"""Bausteine der Visu, Familie Werte: Wertauswahl, Schieberegler, Texteingabe, Anzeigen (analog, digital, Text), Zaehler, Betriebsstunden, Tracker, Webseite, Anlagenschema.

Kachel (@kachel) und Detailseite (@detail) je Typ, siehe bausteine/__init__.py.
Die Helfer (app._state, app._fmt_num ...) sind Mixins: die allgemeinen in helfer.py,
die dieser Familie in der Klasse unten; App erbt sie ueber bausteine.BausteinHelfer."""
from __future__ import annotations

import re
from urllib.parse import quote, unquote

from bausteine import detail, kachel
from bausteine.gemeinsam import _clean


@kachel("ValueSelector", "UpDownAnalog")
def kachel_wertauswahl(app, uuid, c, it):
    det = c.get("details") or {}
    it.update(icon="switch", nav={"view": "control", "id": uuid},
              sublabel=app._fmt_num(app._state(c, "value"), det.get("format") or "%.1f"))


@kachel("TextInput")
def kachel_texteingabe(app, uuid, c, it):
    it.update(icon="info", nav={"view": "control", "id": uuid},
              sublabel=str(app._state(c, "text") or ""))


@kachel("Webpage")
def kachel_webseite(app, uuid, c, it):
    det = c.get("details") or {}
    host = re.sub(r"^https?://", "", det.get("url") or "").split("/")[0]
    it.update(icon="info", nav={"view": "control", "id": uuid},
              sublabel=(host or "Webseite"), subInfo=True)
    img = det.get("image")
    if img and not it.get("iconUrl"):
        it["iconUrl"] = "/icon?p=" + quote(img)


@kachel("InfoOnlyDigital")
def kachel_digitalwert(app, uuid, c, it):
    on = bool(app._state(c, "active"))
    txt = (c.get("details") or {}).get("text") or {}
    it.update(on=on, sublabel=(txt.get("on") if on else txt.get("off")) or ("Ein" if on else "Aus"))


# Zaehler (Strukturdoku Meter, ab 13.01): Zeitraeume als State-Endung,
# details.type mit Gegenrichtung (totalNeg...) und ihre Namen
ZAEHLER_ZEITRAEUME = (("Heute", "Day"), ("Woche", "Week"), ("Monat", "Month"), ("Jahr", "Year"))
ZAEHLER_BEIDSEITIG = frozenset({"bidirectional", "storage"})
ZAEHLER_SPEICHER = "storage"
ZAEHLER_RICHTUNG = ("Bezug", "Lieferung")


@kachel("Meter")
def kachel_zaehler(app, uuid, c, it):
    det = c.get("details") or {}
    a = app._fmt_num(app._state(c, "actual"), det.get("actualFormat", "%.1f"))
    tot = app._fmt_num(app._state(c, "total"), det.get("totalFormat", "%.1f"))
    it["sublabel"] = " • ".join(x for x in (a, tot) if x)


@kachel("Slider")
def kachel_schieberegler(app, uuid, c, it):
    det = c.get("details") or {}
    it.update(sublabel=app._fmt_num(app._state(c, "value"), det.get("format", "%.1f")),
              nav={"view": "control", "id": uuid})


@kachel("InfoOnlyAnalog")
def kachel_analogwert(app, uuid, c, it):
    det = c.get("details") or {}
    it["sublabel"] = app._fmt_num(app._state(c, "value"), det.get("format", "%.1f"))


@kachel("TextState", "InfoOnlyText")
def kachel_textwert(app, uuid, c, it):
    it["sublabel"] = str(app._state(c, "textAndIcon") or app._state(c, "text") or "")


@kachel("SystemScheme")
def kachel_anlagenschema(app, uuid, c, it):
    # Kachel oeffnet die volle Schema-Ansicht (Hintergrundbild + Live-Werte).
    # Als Sublabel den Hauptbaustein (details.mainControl) zeigen, sonst Hinweis.
    main = app._resolve_control((c.get("details") or {}).get("mainControl"))
    wert = app._scheme_value(main).get("text") if main else ""
    it.update(icon="central", sublabel=(wert or "Anlagenschema"), nav={"view": "control", "id": uuid})
    if not wert:
        it["subInfo"] = True


@kachel("Hourcounter")
def kachel_betriebsstunden(app, uuid, c, it):
    it["sublabel"] = ("Wartung fällig" if app._state(c, "overdue")
                      else app._fmt_num(app._state(c, "total"), "%.0f h"))


@kachel("Tracker")
def kachel_tracker(app, uuid, c, it):
    lines = app._tracker_lines(c)
    _, last = app._split_ts(lines[0]) if lines else (None, "")
    it.update(icon="list", nav={"view": "control", "id": uuid},
              sublabel=(last or "Keine Einträge"))


@detail("SystemScheme")
def detail_anlagenschema(app, uuid, c, route):
    return app._view_scheme(uuid, c, route)


@detail("Tracker")
def detail_tracker(app, uuid, c, route):
    items = app._tracker_items(uuid, c)
    if not items:
        return app._big_view(uuid, "list", "Keine Einträge")
    return {"t": "view", "title": _clean(c.get("name")), "route": route,
            "layout": "list", "items": items}


# --- Status-Bausteine: grosse 1/1-Wertseite ---
@detail("Meter")
def detail_zaehler(app, uuid, c, route):
    """Zaehler (Strukturdoku Meter): Leistung bzw. Durchfluss gross, der
    Zaehlerstand, beim Speicher der Fuellstand, und je Zeitraum
    (totalDay ... totalYear) der Stand; ein Zaehler in beide Richtungen
    (details.type bidirectional/storage) nennt dazu die Gegenrichtung
    (totalNeg...)."""
    det = c.get("details") or {}
    fmt, fmt_neg = det.get("totalFormat", "%.1f"), det.get("totalFormatNeg") or det.get("totalFormat", "%.1f")
    a = app._fmt_num(app._state(c, "actual"), det.get("actualFormat", "%.1f"))
    beide = det.get("type") in ZAEHLER_BEIDSEITIG
    pos, neg = ZAEHLER_RICHTUNG if beide else ("", "")
    blocks = app._big_view(uuid, "info", a or "–")["blocks"]   # Loxone-Symbol wie auf der Kachel
    if det.get("powerName"):
        blocks.append({"k": "status", "text": _clean(det["powerName"])})
    stand = [(pos or "Zählerstand", app._fmt_num(app._state(c, "total"), fmt))]
    if beide:
        stand.append((neg, app._fmt_num(app._state(c, "totalNeg"), fmt_neg)))
    blocks += [{"k": "status", "text": f"{t} {w}"} for t, w in stand if w]
    if det.get("type") == ZAEHLER_SPEICHER:
        voll = app._endlich(c, "storage")
        if voll is not None:
            txt = "Speicher " + app._fmt_num(voll, det.get("storageFormat") or fmt)
            try:
                mx = float(det.get("storageMax"))
            except (TypeError, ValueError):
                mx = 0
            if mx > 0:
                txt += f" ({app._fmt_num(voll / mx * 100, '%.0f')} %)"
            blocks.append({"k": "status", "text": txt})
    zeilen = []
    for name, endung in ZAEHLER_ZEITRAEUME:
        w = app._fmt_num(app._state(c, "total" + endung), fmt)
        if not w:
            continue
        w_neg = app._fmt_num(app._state(c, "totalNeg" + endung), fmt_neg) if beide else ""
        zeilen.append({"k": "status", "text": f"{name}: " + (f"{pos} {w} · {neg} {w_neg}" if w_neg else w)})
    if zeilen:
        blocks += [{"k": "head", "text": "Verbrauch" if not beide else "Zeiträume"}, *zeilen]
    return {"t": "view", "title": _clean(c.get("name")), "route": route, "blocks": blocks}


@detail("Slider", "UpDownAnalog")
def detail_schieberegler(app, uuid, c, route):
    t = c.get("type")
    # Schieberegler und Auf/Ab-Taster sind laut Loxone-Strukturdoku
    # dieselbe Art virtueller Eingang (UpDownAnalog = "UpDownLeftRight
    # analog"): details format/min/max/step, State value und error
    # (ungueltiger Wert), Befehl {wert} zwischen min und max. Die
    # -/+ Tasten schalten um step weiter.
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
    val = app._state(c, "value")
    try:
        cur = float(val)
    except (TypeError, ValueError):
        cur = mn
    ico = "info" if t == "Slider" else "switch"
    blocks = [{"k": "hero", "icon": ico},
              {"k": "big", "text": app._fmt_num(val, fmt) or "–"}]
    if app._state(c, "error"):
        blocks.append({"k": "status", "text": "Ungültiger Wert"})
    blocks.append({"k": "slider", "icon": "vol" if t == "Slider" else ico, "value": _n(cur),
                   "min": _n(mn), "max": _n(mx), "step": _n(stp),
                   "cmd": {"uuid": ua, "tmpl": "{v}"}})
    return {"t": "view", "title": _clean(c.get("name")), "route": route, "blocks": blocks}


@detail("InfoOnlyAnalog")
def detail_analogwert(app, uuid, c, route):
    det = c.get("details") or {}
    return app._big_view(uuid, "info",
                          app._fmt_num(app._state(c, "value"), det.get("format", "%.1f")) or "–")


@detail("TextState", "InfoOnlyText")
def detail_textwert(app, uuid, c, route):
    return app._big_view(uuid, "info",
                          str(app._state(c, "textAndIcon") or app._state(c, "text") or "–"))


@detail("InfoOnlyDigital")
def detail_digitalwert(app, uuid, c, route):
    on = bool(app._state(c, "active"))
    tx = (c.get("details") or {}).get("text") or {}
    return app._big_view(uuid, "info",
                          (tx.get("on") if on else tx.get("off")) or ("Ein" if on else "Aus"))


@detail("ValueSelector")
def detail_wertauswahl(app, uuid, c, route):
    ua = c.get("uuidAction")
    det = c.get("details") or {}
    val = app._state(c, "value") or 0
    mn = app._state(c, "min"); mx = app._state(c, "max"); stp = app._state(c, "step")
    mn = 0 if mn is None else mn
    mx = 100 if mx is None else mx
    stp = stp if isinstance(stp, (int, float)) and stp else 1
    return {"t": "view", "title": _clean(c.get("name")), "route": route,
            "anchor": "bottom", "blocks": [
        {"k": "hero", "icon": "switch"},
        {"k": "big", "text": app._fmt_num(val, det.get("format") or "%.1f")},
        {"k": "slider", "icon": "vol", "value": val, "min": mn,
         "max": mx, "step": stp, "cmd": {"uuid": ua, "tmpl": "{v}"}},
    ]}


@detail("TextInput")
def detail_texteingabe(app, uuid, c, route):
    return app._big_view(uuid, "info", str(app._state(c, "text") or "–"))


@detail("Webpage")
def detail_webseite(app, uuid, c, route):
    det = c.get("details") or {}
    url = (det.get("urlHd") or det.get("url") or "").strip()
    if url and not re.match(r"^https?://", url):
        url = "http://" + url
    return {"t": "view", "title": _clean(c.get("name")), "route": route,
            "blocks": [{"k": "web", "url": url}]}


@detail("Hourcounter")
def detail_betriebsstunden(app, uuid, c, route):
    ov = app._state(c, "overdue")
    return app._big_view(uuid, "info", app._fmt_num(app._state(c, "total"), "%.0f h") or "–",
                          "Wartung fällig" if ov else "", tone=("crit" if ov else None))


class WerteHelfer:
    """Helfer der Familie Werte fuer Kachel, Detailseite und Unterseiten. Mixin: App erbt sie ueber
    bausteine.BausteinHelfer, gerufen wird ueber self bzw. app."""

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

    def _tracker_items(self, uuid: str, tracker: dict) -> list[dict]:
        """Eintraege eines Trackers als Listenzeilen, neueste zuerst: Text als
        Name, ein fuehrender Zeitstempel darunter."""
        items = []
        for i, ln in enumerate(self._tracker_lines(tracker)):
            ts, txt = self._split_ts(ln)
            entry = {"id": f"{uuid}:{i}", "icon": "list", "label": txt}
            if ts:
                entry["sublabel"] = ts
            items.append(entry)
        return items

    @staticmethod
    def _verlauf_sub(c: dict) -> tuple[str | None, dict | None]:
        """Der Verlauf eines Bausteins: sein erster Unterbaustein vom Typ
        Tracker (Strukturdoku, etwa MailBox: Subcontrol Tracker) als
        (UUID, Baustein), sonst (None, None)."""
        for su, s in (c.get("subControls") or {}).items():
            if isinstance(s, dict) and s.get("type") == "Tracker":
                return su, s
        return None, None

    def _view_verlauf(self, uuid: str) -> dict:
        """Unterseite Verlauf eines Bausteins (Route view=verlauf): die
        Eintraege seines Tracker-Unterbausteins wie auf der Detailseite eines
        Trackers."""
        c = self.controls.get(uuid or "") or {}
        route = {"view": "verlauf", "id": uuid}
        su, tracker = self._verlauf_sub(c)
        titel = f"{_clean(c.get('name'))} · Verlauf"
        if tracker is None:
            return self._gone_view(route, titel, "Dieser Baustein hat keinen Verlauf.")
        items = self._tracker_items(su, tracker)
        if not items:
            return {"t": "view", "title": titel, "route": route,
                    "blocks": [{"k": "status", "text": "Keine Einträge"}]}
        return {"t": "view", "title": titel, "route": route, "layout": "list", "items": items}

    # ---- Anlagenschema (SystemScheme) -----------------------------------
    def _resolve_control(self, uuid: str | None) -> dict | None:
        """Baustein zu einer UUID liefern – auch wenn es ein Subcontrol ist.
        self.controls enthaelt nur die Top-Level-Bausteine; die Referenzen im
        Anlagenschema zeigen teils auf Subcontrols (z.B. InfoOnly eines Oelkessels)."""
        if not uuid:
            return None
        c = self.controls.get(uuid)
        if c:
            return c
        for pc in self.controls.values():
            sub = (pc.get("subControls") or {}).get(uuid)
            if sub:
                return sub
        return None

    def _scheme_value(self, c: dict | None) -> dict:
        """Kompakter Anzeige-Wert eines im Schema referenzierten Bausteins:
        {text, on, tone}. Deckt die im Anlagenschema ueblichen Typen ab
        (Slider/InfoOnlyAnalog = Zahl, InfoOnlyDigital = Ein/Aus, TextState)."""
        if not c:
            return {"text": "", "on": False}
        t = c.get("type")
        det = c.get("details") or {}
        if t in ("Slider", "InfoOnlyAnalog", "Meter"):
            return {"text": self._fmt_num(self._state(c, "value") if t != "Meter"
                                          else self._state(c, "actual"),
                                          det.get("format", "%.1f")), "on": False}
        if t == "InfoOnlyDigital":
            on = bool(self._state(c, "active"))
            txt = det.get("text") or {}
            return {"text": (txt.get("on") if on else txt.get("off"))
                    or ("Ein" if on else "Aus"), "on": on}
        if t in ("TextState", "InfoOnlyText"):
            return {"text": str(self._state(c, "textAndIcon")
                               or self._state(c, "text") or ""), "on": False}
        # Fallback: erster vorhandener State als Text.
        for name in (c.get("states") or {}):
            v = self._state(c, name)
            if v not in (None, ""):
                return {"text": str(v), "on": False}
        return {"text": "", "on": False}

    def _view_scheme(self, uuid: str, c: dict, route: dict) -> dict:
        """Anlagenschema als Ansicht: Hintergrundbild vom Miniserver (ueber den
        /icon-Proxy) plus die Live-Werte der referenzierten Bausteine als Overlay
        an ihren Positionen. schemeSize ist das Original-Koordinatensystem, in dem
        pos/size angegeben sind – der Client skaliert es auf die Panelbreite."""
        det = c.get("details") or {}
        sz = det.get("schemeSize") or {}
        img = det.get("imagePath")
        # /icon liefert .png vom Miniserver (mit JWT); &v busted den Browser-Cache
        # bei geaenderter imageVersion. Hinweis: der Server-seitige icon_cache wird
        # per Pfad gehalten – aendert sich das Bild im Config, ggf. Server neu laden.
        src = None
        if img:
            src = "/icon?p=" + quote(img, safe="")
            if det.get("imageVersion"):
                src += "&v=" + str(det["imageVersion"])
        items = []
        for ref in (det.get("controlReferences") or []):
            rc = self._resolve_control(ref.get("uuidAction"))
            if not rc:
                continue
            val = self._scheme_value(rc)
            pos = ref.get("pos") or {}
            size = ref.get("size") or {}
            entry = {
                "x": pos.get("x", 0), "y": pos.get("y", 0),
                "w": size.get("width"), "h": size.get("height"),
                "text": (ref.get("text") or "") + val["text"],
                "on": val["on"],
            }
            # Bedienbare Referenzen (actionsVisible) sind antippbar -> Detailansicht
            # des Bausteins. Nur fuer Top-Level-Bausteine, die eine eigene View haben.
            ru = ref.get("uuidAction")
            if ref.get("actionsVisible") and ru in self.controls:
                entry["nav"] = {"view": "control", "id": ru}
            items.append(entry)
        return {"t": "view", "title": _clean(c.get("name")), "route": route,
                "layout": "scheme", "image": src,
                "sw": sz.get("width") or 1300, "sh": sz.get("height") or 866,
                "items": items}
