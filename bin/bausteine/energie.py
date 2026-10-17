"""Bausteine der Visu, Familie Energie: Fronius, Energiefluss (EFM), Energiemanager, PV-Prognose.

Kachel (@kachel) und Detailseite (@detail) je Typ, siehe bausteine/__init__.py.
Die Helfer (app._state, app._fmt_num ...) sind Mixins: die allgemeinen in helfer.py,
die dieser Familie in der Klasse unten; App erbt sie ueber bausteine.BausteinHelfer."""
from __future__ import annotations

import math

from bausteine import detail, kachel
from bausteine.gemeinsam import _clean


@kachel("Fronius")
def kachel_fronius(app, uuid, c, it):
    prod = app._state(c, "prodCurr")
    it.update(icon="central", nav={"view": "control", "id": uuid},
              sublabel=(app._fmt_num(prod, "%.2fkW") if prod is not None else "PV-Anlage"))
    if prod is None:
        it["subInfo"] = True


@kachel("EFM")
def kachel_energiefluss(app, uuid, c, it):
    # Energieflussmonitor: Ppwr Erzeugung, Gpwr Netz (+Bezug/-Einspeisung),
    # Spwr Speicher (+Entladen/-Laden), actual0..5 = Knoten aus details.nodes
    fmt = (c.get("details") or {}).get("actualFormat") or "%.2f kW"
    bits = []
    p = app._endlich(c, "Ppwr")
    if p is not None:
        bits.append("PV " + app._fmt_num(p, fmt))
    g = app._flow_text(app._state(c, "Gpwr"), fmt, "Bezug", "Einspeisung")
    if g:
        bits.append(g)
    it.update(icon="central", nav={"view": "control", "id": uuid},
              sublabel=" · ".join(bits) or "Energiefluss")
    if not bits:
        it["subInfo"] = True


@kachel("EnergyManager2")
def kachel_energiemanager(app, uuid, c, it):
    bits = []
    p = app._endlich(c, "Ppwr")
    if p is not None:
        bits.append("PV " + app._fmt_num(p, "%.2f kW"))
    soc = app._endlich(c, "Ssoc")
    if soc is not None and (c.get("details") or {}).get("HasSsoc", True):
        bits.append("Speicher " + app._fmt_num(soc, "%.0f") + " %")
    it.update(icon="central", nav={"view": "control", "id": uuid},
              sublabel=" · ".join(bits) or "Energiemanager")
    if not bits:
        it["subInfo"] = True


@kachel("PvProductionForecast")
def kachel_pv_prognose(app, uuid, c, it):
    bits = [f"{lbl} {app._fmt_num(v, '%.1f kWh')}"
            for lbl, v in (("Heute", app._state(c, "today")), ("Morgen", app._state(c, "tomorrow")))
            if v is not None]
    it.update(icon="central", nav={"view": "control", "id": uuid},
              sublabel=" · ".join(bits) or "PV-Prognose")
    if not bits:
        it["subInfo"] = True


@detail("Fronius")
def detail_fronius(app, uuid, c, route):
    prod = app._state(c, "prodCurr")
    rows = []
    for nm, lbl, unit in (("consCurr", "Verbrauch", "%.2fkW"),
                          ("prodCurrDay", "Heute erzeugt", "%.1fkWh"),
                          ("deliveryDay", "Heute eingespeist", "%.1fkWh")):
        v = app._state(c, nm)
        if v is not None:
            rows.append({"k": "status", "text": f"{lbl}: {app._fmt_num(v, unit)}"})
    return {"t": "view", "title": _clean(c.get("name")), "route": route, "blocks": [
        {"k": "hero", "icon": "central"},
        {"k": "big", "text": (app._fmt_num(prod, "%.2fkW") if prod is not None else "–")},
        {"k": "status", "text": "Aktuelle Erzeugung"},
        *rows,
    ]}


@detail("EFM")
def detail_energiefluss(app, uuid, c, route):
    det = c.get("details") or {}
    fmt = det.get("actualFormat") or "%.2f kW"
    p = app._endlich(c, "Ppwr")
    rows = []
    g = app._flow_text(app._state(c, "Gpwr"), fmt, "Netzbezug", "Einspeisung")
    if g:
        rows.append({"k": "status", "text": g})
    sp = app._flow_text(app._state(c, "Spwr"), det.get("storageFormat") or fmt,
                         "Speicher entlädt", "Speicher lädt", "Speicher")
    if sp:
        rows.append({"k": "status", "text": sp})
    nodes = app._named_items(det.get("nodes"))
    vals = [(label, app._endlich(c, f"actual{i}")) for i, (label, _n) in enumerate(nodes[:6])]
    vals = [(label, v) for label, v in vals if v is not None]
    if vals:
        rows.append({"k": "head", "text": "Verbraucher und Quellen"})
        rows += [{"k": "status", "text": f"{label}: {app._fmt_num(v, fmt)}"} for label, v in vals]
    eb = app.energy_blocks(uuid)   # Radial auch beim Antippen (4"-Panel ohne Split)
    if eb:
        blocks = [{"k": "eflow", "e": eb}]   # zeigt PV/Netz/Speicher + Verbraucher live, wie in der Loxone-App
    else:
        blocks = [{"k": "hero", "icon": "central"},
                  {"k": "big", "text": (app._fmt_num(p, fmt) if p is not None else "–")},
                  {"k": "status", "text": "Aktuelle Erzeugung"}, *rows]
    return {"t": "view", "title": _clean(c.get("name")), "route": route, "blocks": blocks}


@detail("EnergyManager2")
def detail_energiemanager(app, uuid, c, route):
    det = c.get("details") or {}
    p = app._endlich(c, "Ppwr")
    rows = []
    g = app._flow_text(app._state(c, "Gpwr"), "%.2f kW", "Netzbezug", "Einspeisung")
    if g:
        rows.append({"k": "status", "text": g})
    if det.get("HasSpwr", True):
        sp = app._flow_text(app._state(c, "Spwr"), "%.2f kW", "Speicher entlädt", "Speicher lädt", "Speicher")
        if sp:
            rows.append({"k": "status", "text": sp})
    soc = app._endlich(c, "Ssoc")
    if soc is not None and det.get("HasSsoc", True):
        txt = f"Speicher {app._fmt_num(soc, '%.0f')} %"
        mn = app._endlich(c, "MinSoc")
        if mn is not None:
            txt += f" (Reserve {app._fmt_num(mn, '%.0f')} %)"
        rows.append({"k": "status", "text": txt})
    loads = app._named_items(app._json_state(c, "loads"))
    if loads:
        rows.append({"k": "head", "text": "Verbraucher"})
        for label, e in loads:
            st = e.get("status", e.get("state", e.get("active")))
            if isinstance(st, bool) or st in (0, 1, "0", "1"):
                st = "Ein" if st in (True, 1, "1") else "Aus"
            rows.append({"k": "status", "text": label + (f": {st}" if st not in (None, "") else "")})
    eb = app.energy_blocks(uuid)   # Radial auch beim Antippen (4"-Panel ohne Split)
    head = ([{"k": "eflow", "e": eb}] if eb else
            [{"k": "hero", "icon": "central"},
             {"k": "big", "text": (app._fmt_num(p, "%.2f kW") if p is not None else "–")},
             {"k": "status", "text": "Aktuelle Erzeugung"}])
    return {"t": "view", "title": _clean(c.get("name")), "route": route,
            "blocks": [*head, *rows]}


@detail("PvProductionForecast")
def detail_pv_prognose(app, uuid, c, route):
    det = c.get("details") or {}
    today = app._state(c, "today")
    rows = []
    for nm, lbl in (("tomorrow", "Morgen"), ("period", "Aktueller Zeitraum"), ("after", "Danach")):
        v = app._state(c, nm)
        if v is not None:
            rows.append({"k": "status", "text": f"{lbl}: {app._fmt_num(v, '%.1f kWh')}"})
    mp = det.get("maxPower")
    if mp is not None:
        rows.append({"k": "status", "text": f"Anlagenleistung {app._fmt_num(mp, '%.1f kW')}"})
    err = app._text(c, "errorInfo")
    if err:
        rows.append({"k": "status", "text": err})
    return {"t": "view", "title": _clean(c.get("name")), "route": route, "blocks": [
        {"k": "hero", "icon": "central"},
        {"k": "big", "text": (app._fmt_num(today, "%.1f kWh") if today is not None else "–")},
        {"k": "status", "text": "Erwartete Erzeugung heute"},
        *rows,
    ]}


class EnergieHelfer:
    """Helfer der Familie Energie fuer Kachel, Detailseite und Unterseiten. Mixin: App erbt sie
    ueber bausteine.BausteinHelfer, gerufen wird ueber self bzw. app."""

    def _flow_text(self, value, fmt: str, pos: str, neg: str, zero: str | None = None) -> str:
        """Leistung mit Richtung: Vorzeichen -> Text (z.B. Bezug/Einspeisung).
        Loxone zaehlt aus Sicht des Hauses: positiv = fliesst ins Haus, also
        Netzbezug bzw. Speicher entlaedt; negativ = Einspeisung bzw. Laden.
        zero: Text fuer 0 (ohne Richtung), sonst gilt 0 als positiv."""
        try:
            v = float(value)
        except (TypeError, ValueError):
            return ""
        if not math.isfinite(v):   # NaN/unendlich (gueltige Binaer-Doubles): unbekannt
            return ""
        text = zero if (zero and v == 0) else (pos if v >= 0 else neg)
        return f"{text} {self._fmt_num(abs(v), fmt)}"

    def energy_blocks(self, uuid: str, max_cons: int = 6):
        """Energiefluss-Daten (Radial, Loxone-Standard) einer EFM/EnergyManager2-
        Kachel fuers Panel. EFM: genau die in der Loxone-Config angelegten Knoten
        (actual0..5, Name UND Icon vom Miniserver) – das ist wie in der Loxone-App
        die vollstaendige Liste inkl. PV/Netz/Speicher, daher KEINE zusaetzlichen
        Summen-Knoten (sonst Dopplung). EnergyManager2 (oder EFM ohne eigene
        Knoten): Summen-Knoten aus Ppwr/Gpwr/Spwr. 0-W-Knoten werden mitgezeigt
        (grau/inaktiv); nur nicht existierende (kein State) entfallen. Leistung in
        WATT, Flussrichtung fuers Diagramm. None bei ungueltiger Kachel. Reine
        Anzeige, keine Steuerung. max_cons = Loxones Grenze (actual0..5, max. 6).

        Vorzeichen wie bei Loxone aus Sicht des Hauses (siehe _flow_text):
        Gpwr>0 = Netzbezug (rein), <0 = Einspeisung (raus); Spwr>0 = Speicher
        entlaedt (rein), <0 = laedt (raus); Ppwr = Erzeugung (rein). Dasselbe
        gilt fuer EFM-Knoten mit nodeType Storage. flow: "in" = zur Mitte
        (gruen), "out" = nach aussen (orange), None = 0/inaktiv (grau)."""
        c = self.controls.get(uuid or "")
        if not c or c.get("type") not in ("EFM", "EnergyManager2"):
            return None
        det = c.get("details") or {}
        fmt = det.get("actualFormat") or "%.2f kW"
        to_w = 1000.0 if "kw" in fmt.lower() else 1.0   # States meist in kW -> Watt

        def watt(key):
            """Leistung in W; None, solange sie fehlt - auch bei NaN/unendlich, die als
            Binaer-Double gueltig sind: unbekannt, nicht 0 und nicht in Summen."""
            v = self._state(c, key)
            try:
                w = float(v) * to_w
            except (TypeError, ValueError):
                return None
            return w if math.isfinite(w) else None

        def classify(nt, v):
            """Richtung (flow: in/out/None) UND Farbe/Rolle (kind) je Knoten aus
            Loxone-nodeType + Vorzeichen:
              kind "prod" = Quelle, gruen  (PV/Production; Netz-Einspeisung; Speicher entladen)
              kind "grid" = Netzbezug, ROT (Netz liefert Strom ins Haus)
              kind "load" = Verbraucher, orange (Load/Group; Speicher laden)
              kind "idle" = 0 W, grau
            PV/Production ist immer Quelle (kann nie beziehen). Netz: Bezug (v>0)
            rein/rot, Einspeisung (v<0) raus/gruen. Speicher wie das Netz aus
            Sicht des Hauses: entladen (v>0) rein/gruen, laden (v<0) raus/orange."""
            ntl = (nt or "").lower()
            if not v:
                return (None, "idle")
            if ntl == "production":
                return ("in", "prod")
            if ntl == "grid":
                return ("in", "grid") if v > 0 else ("out", "prod")
            if ntl in ("storage", "battery"):
                return ("in", "prod") if v > 0 else ("out", "load")
            return ("out", "load") if v > 0 else ("in", "prod")

        pv = watt("Ppwr")                       # Erzeugung
        g = watt("Gpwr")                        # Netz: >0 Bezug (rein), <0 Einspeisung (raus)
        sp = watt("Spwr")                       # Speicher: >0 entlaedt (rein), <0 laedt (raus)
        try:
            soc = float(self._state(c, "Ssoc"))
        except (TypeError, ValueError):
            soc = None
        if soc is not None and not math.isfinite(soc):
            soc = None

        def agg_nodes():
            """Feste Summen-Knoten (PV/Netz/Speicher) aus Ppwr/Gpwr/Spwr – fuer
            EnergyManager2 und als Rueckfall, wenn ein EFM keine eigenen Knoten hat."""
            def mk(name, icon, val, nt, extra=None):
                fl, kd = classify(nt, val)
                n = {"name": name, "icon": icon, "w": abs(val) if val else 0.0,
                     "flow": fl, "kind": kd}
                if extra:
                    n.update(extra)
                return n
            ns = [mk("PV", "pv", pv, "production"),
                  mk("Netz", "grid", g, "grid")]
            if soc is not None or (sp not in (None, 0.0)):
                ns.append(mk("Speicher", "battery", sp, "storage",
                             {"soc": max(0.0, min(100.0, soc))} if soc is not None else None))
            return ns

        # EFM: die actual0..5-Knoten SIND – wie in der Loxone-App – die vollstaendige
        # Liste (inkl. PV/Netz/Speicher, falls dort angelegt). Daher KEINE
        # zusaetzlichen Summen-Knoten oben drauf (sonst Dopplung). Name, Icon UND
        # Rolle (nodeType) kommen vom Miniserver; 0-W-Knoten bleiben (grau).
        def bilanz():
            """Hausverbrauch aus der Energiebilanz (Sicht des Hauses: was
            hereinkommt, wird verbraucht) = Erzeugung + Netz + Speicher. Ohne
            Netzwert unbekannt (None), ebenso solange PV oder Speicher angelegt
            sind, aber noch keinen Wert haben. Fehlt der State ganz (beim EM2
            auch HasSpwr false), hat die Anlage keinen: Beitrag 0."""
            if g is None:
                return None
            summe = g
            for key, val, da in (("Ppwr", pv, True), ("Spwr", sp, det.get("HasSpwr", True))):
                if not da or key not in (c.get("states") or {}):
                    continue
                if val is None:
                    return None
                summe += val
            return max(0.0, summe)

        cons = []
        prod_sum = cons_sum = 0.0
        hat_verbraucher = prod_knoten = prod_fehlt = False
        if c.get("type") == "EFM":
            for i, (label, nd) in enumerate(self._named_items(det.get("nodes"))[:max_cons]):
                v = watt(f"actual{i}")
                nt = nd.get("nodeType") if isinstance(nd, dict) else None
                if v is None:
                    if (nt or "").lower() == "production":
                        prod_fehlt = True
                    continue
                flow, kind = classify(nt, v)
                cons.append({"name": label or f"Knoten {i + 1}", "icon": "load",
                             "iconUrl": self._node_icon_url(nd),
                             "w": abs(v), "flow": flow, "kind": kind})
                ntl = (nt or "").lower()
                if ntl == "production":
                    prod_knoten = True
                    prod_sum += abs(v)
                elif ntl in ("load", "group"):
                    hat_verbraucher = True
                    if v > 0:
                        cons_sum += abs(v)
        def erzeugung():
            """Erzeugung in W: die Erzeugungs-Knoten, sonst Ppwr. None, wenn eine
            Erzeugung angelegt ist, aber keinen Wert hat - keine erfundene Null."""
            if prod_sum:
                return prod_sum
            if pv is not None:
                return abs(pv)
            if prod_knoten:
                return 0.0
            if prod_fehlt or "Ppwr" in (c.get("states") or {}):
                return None
            return 0.0

        if cons:
            cons.sort(key=lambda n: (n["flow"] is None, -n["w"]))   # aktiv zuerst, 0 W ans Ende
            nodes = cons
            prod_total = erzeugung()
            # gemessene Verbraucher-Knoten, sonst die Bilanz
            cons_total = cons_sum if hat_verbraucher else bilanz()
        else:
            nodes = agg_nodes()   # EM2 oder EFM ohne eigene Knoten
            prod_total = erzeugung()
            cons_total = bilanz()
        return {"control": uuid, "name": _clean(c.get("name")) or "Energiefluss",
                "nodes": nodes,
                "totals": {"prod": prod_total, "cons": cons_total, "grid": g or 0.0}}
