"""Die Seiten der Visu: render() nimmt eine Route und baut die view-Nachricht,
die Tabs (_view_tab: Favoriten, Zentral, Raeume, Kategorien, freie Seiten),
Gruppen, Detailseiten (_view_control mit Verlauf und verlinkten Objekten),
die Kacheln (_control_item mit Kopf, Typ-Funktion aus bausteine und Fuss,
_apply_tile_style), die Werteleiste, die Status-Pane und was eine Ansicht
zeigen darf (_shown, _room_ok, _cat_ok).

Die Methoden sind ein Mixin (Seiten): App erbt sie und arbeitet mit ihnen auf ihrem
Zustand (self ist die App). Importiert webvisu nicht."""
from __future__ import annotations

import logging
from urllib.parse import quote

import bausteine
from ansicht import _hex_rgb, _inactive_border, _overlay_alphas, _posring
from bausteine.gemeinsam import _clean, SPERRE_KURZ, TYP_UNBEKANNT
from konfig import (
    _clean_widget_tab, FRONT_TABS, HAUS_TAB, _is_pick, _kachel_breite, _pick_index, _pick_tabs,
    STAT_RANGES, STAT_TILE_STYLES, SV_STATUS_MAX)
from statistik import STAT_DEFAULT_RANGE

log = logging.getLogger("loxpanel.webvisu")   # derselbe Logger wie der Server: die Methoden gehoeren zu App


# Reine Anzeige-Bausteine: keine Steuer-2.-Ebene -> Antippen zeigt eine
# grosse 1/1-Wertseite (_view_control -> _big_view).
STATUS_BIG = {"Meter", "InfoOnlyAnalog", "TextState", "InfoOnlyText",
              "InfoOnlyDigital", "SmokeAlarm", "PresenceDetector",
              "ClimateControllerUS", "Hourcounter"}

# Werteleiste (ui.valueBar nennt die Seiten): diese Anzeige-Bausteine stehen
# dort als Kette von Werten in EINER Zeile ueber dem Raster statt als Kacheln,
# das Raster bleibt dem Bedienbaren (_leiste_trennen). Nicht dabei: der
# Rauchmelder (ein Alarm gehoert gross auf eine Kachel) und die Klimaregelung
# (hat Einstellungen, keine reine Anzeige).
WERTE_LEISTE_TYPEN = frozenset(STATUS_BIG - {"SmokeAlarm", "ClimateControllerUS"})

# Breite Kacheln (2 x 1): Bausteine, deren Kachel von Haus aus zwei Spalten
# belegt - Audio (Titel und Tasten), Raumregelung (Soll und Ist) und der
# Energiefluss. Je Kachel uebersteuerbar: tiles[uuid].w = 1 | 2
# (KACHEL_BREITEN). Die Visu setzt daraus grid-column: span 2 und rechnet
# Seiten und Rastpunkte mit (rasterLage in panel.html).
KACHEL_BREIT_TYPEN = frozenset({"AudioZone", "AudioZoneV2", "IRoomControllerV2", "IRoomController",
                                "EFM", "EnergyManager2"})

# Reine Wert-/Analog-Anzeigen (kein an/aus) -> keine Kategorie-Ampel, neutral.
_ANALOG = {"InfoOnlyAnalog", "Slider", "UpDownAnalog", "Meter", "TextState", "InfoOnlyText",
           "Hourcounter", "EFM", "EnergyManager2", "PvProductionForecast", "SteakThermo"}

# Trenner, die nach dem Streichen des Raumnamens am Rand eines Kachelnamens
# haengen blieben ("Licht - Wohnzimmer" -> "Licht")
_NAMEN_TRENNER = frozenset({"-", "–", "—", "·", "/", ",", ":", "|"})


def _ohne_raum(name: str, raum: str) -> str:
    """Kachelname ohne den Raumnamen, wenn die Seite den Raum schon nennt
    ("Jalousie Wohnzimmer Süd" auf der Wohnzimmer-Seite -> "Jalousie Süd").
    Nur ganze Woerter zaehlen (Gross-/Kleinschreibung egal, ein Satzzeichen
    am Wort stoert nicht), die uebrigen Woerter bleiben in ihrer Reihenfolge,
    ein uebrig gebliebener Trenner am Rand faellt weg. Kommt der Raum nicht
    vor oder bliebe nichts uebrig ("Wohnzimmer"), bleibt der Name."""
    woerter, rw = (name or "").split(), (raum or "").split()
    if not woerter or not rw:
        return name
    low = [w.lower().strip(",:;") for w in woerter]
    rlow = [w.lower().strip(",:;") for w in rw]
    for i in range(len(low) - len(rw) + 1):
        if low[i:i + len(rw)] == rlow:
            rest = woerter[:i] + woerter[i + len(rw):]
            while rest and rest[0] in _NAMEN_TRENNER:
                rest.pop(0)
            while rest and rest[-1] in _NAMEN_TRENNER:
                rest.pop()
            return " ".join(rest) or name
    return name


class Seiten:
    """Seiten, Kacheln und Detailseiten; Mixin der App (self ist die App)."""

    def status_blocks(self, uuids) -> list:
        """Frei gewaehlte Bausteine als Nur-Lese-Kacheln fuer die rechte Spalte
        des Screensavers. Baut bewusst ueber _control_item() — damit stehen dort
        Name, Wert, Icon und Zustandsfarbe genau so wie auf einer Kachel, und ein
        neuer Bausteintyp wirkt hier mit, ohne dass jemand daran denken muss.
        Unbekannte UUIDs (geloeschter Baustein) fallen still weg."""
        raus = []
        for u in list(uuids or [])[:SV_STATUS_MAX]:
            if u not in self.controls:
                continue
            try:
                it = self._control_item(u, show_room=True)
            except Exception:
                log.exception("status_blocks: Baustein uebersprungen (%s)", u)
                continue
            # Die Uhr-Seite zeigt nur an — Navigation und Steuer-Buttons haetten
            # dort keine Wirkung (ein Tipp weckt das Panel) und wuerden Platz
            # kosten. Deshalb hier raus, statt sie im Panel zu ignorieren.
            for k in ("nav", "controls", "secured"):
                it.pop(k, None)
            raus.append(it)
        return raus

    def _tab_meta(self, tab_keys, prof: dict | None = None) -> dict:
        """Label + Icon fuer dynamische Tabs (Kategorie-, Raum- und Auswahl-Tab).
        Die 4 Standard-Tabs kennt das Frontend selbst; hier nur `cat:`/`room:`
        und `auswahl` - letzteres traegt einen frei gewaehlten Namen, sein
        Symbol bringt das Panel selbst mit."""
        meta = {}
        for t in tab_keys or []:
            if _is_pick(t):
                _pts = _pick_tabs(prof)
                _i = _pick_index(t)
                _e = _pts[_i] if 0 <= _i < len(_pts) else {}
                _ic = _e.get("icon") or ""
                # Fertige URL (/icon?p=… oder /loxlib?n=…) direkt, sonst ein
                # Loxone-Pfad ueber _icon_url aufloesen (rueckwaertskompatibel).
                _url = _ic if (isinstance(_ic, str) and _ic.startswith("/")) else (self._icon_url(_ic) or "")
                meta[t] = {"label": (_e.get("name") or "Auswahl"), "iconUrl": _url}
                if _e.get("widget") == HAUS_TAB:
                    meta[t]["haus"] = True   # ohne eigenes Symbol das Haus der Leiste
            elif isinstance(t, str) and t.startswith("cat:"):
                cat = self.cats.get(t[4:], {})
                meta[t] = {"label": _clean(cat.get("name")) or "Kategorie",
                           "iconUrl": self._icon_url(cat.get("image")) or ""}
            elif isinstance(t, str) and t.startswith("room:"):
                room = self.rooms.get(t[5:], {})
                meta[t] = {"label": _clean(room.get("name")) or "Raum",
                           "iconUrl": self._icon_url(room.get("image")) or ""}
        return meta

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

    def _sichtbar(self, uuid: str, prof: dict | None) -> bool:
        """Darf die Ansicht diesen Baustein zeigen: Raum, Kategorie und hide wie
        auf ihren Seiten. Fuer Meldungen, die an keiner Seite haengen (Wecker)."""
        return self._room_ok(uuid, prof) and self._cat_ok(uuid, prof) and self._shown(uuid, prof)

    # ---- Kachel fuer ein Control ----
    def _spans_rooms(self, uuids) -> bool:
        """True, wenn die Bausteine ueber mehr als einen bekannten Raum verteilt
        sind. Dann lohnt es sich, den Raum je Kachel zu zeigen (Kategorie Licht
        ueber mehrere Raeume). Bausteine ohne Raum (z.B. Zentral) zaehlen nicht."""
        rooms = {self.controls[u].get("room") for u in uuids
                 if u in self.controls and self.controls[u].get("room") in self.rooms}
        return len(rooms) > 1

    def _leiste_trennen(self, uuids: list, tab, prof: dict | None) -> tuple[list, list]:
        """Seite mit Werteleiste (ui.valueBar nennt den Tab): die Anzeige-
        Bausteine (WERTE_LEISTE_TYPEN) wandern aus dem Raster in die Leiste ->
        (Raster, Leiste), beide in der Reihenfolge von uuids. Ohne Leiste, und
        wenn im Raster nichts bliebe (eine Seite nur aus Werten: dann SIND die
        Kacheln die Seite), bleibt alles im Raster."""
        if not prof or tab not in (prof.get("valueBar") or []):
            return uuids, []
        leiste = [u for u in uuids if (self.controls.get(u) or {}).get("type") in WERTE_LEISTE_TYPEN]
        if not leiste or len(leiste) == len(uuids):
            return uuids, []
        weg = set(leiste)
        return [u for u in uuids if u not in weg], leiste

    def _leiste_items(self, uuids: list, prof: dict | None, **kw) -> dict:
        """Die Werteleiste einer Ansicht als {"leiste": [...]}: dieselben
        Kacheln wie im Raster (_control_item: Name, Wert, Symbol, Farbe,
        Wertseite), das Panel zeigt sie als Kette ueber dem Raster
        (renderLeiste). Leer: kein Schluessel, die Ansicht bleibt wie bisher."""
        if not uuids:
            return {}
        return {"leiste": [self._control_item(u, prof, **kw) for u in uuids]}

    def _control_item(self, uuid: str, prof: dict | None = None,
                      show_room: bool = False, ohne_raum: str = "") -> dict:
        """Kachel eines Bausteins. show_room: Raum an der Kachel (Seite ueber
        mehrere Raeume). ohne_raum: Name des Raums, den die Seite schon nennt
        (Raum-Seite) - er faellt aus dem Kachelnamen (_ohne_raum), die
        meisten abgeschnittenen Namen der Messung trugen ihn."""
        c = self.controls.get(uuid)
        if not c:
            return {"id": uuid, "label": "?", "icon": "info", "on": False}
        t = c.get("type")
        name = _clean(c.get("name"))
        if ohne_raum:
            name = _ohne_raum(name, ohne_raum)
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
        fn = bausteine.kachel_fuer(t)
        if fn:
            fn(self, uuid, c, it)
        # Status-Bausteine antippbar machen -> grosse Wertseite
        if t in STATUS_BIG and "nav" not in it and "cmd" not in it:
            it["nav"] = {"view": "control", "id": uuid}
        # Typ, den LoxPanel nicht kennt: sagen statt einer leeren Kachel. Der
        # Text beschreibt nur (subInfo); ausblenden wie jede Kachel ueber hide.
        # unbekannt: /api/types zaehlt ihn trotz Zweitzeile als nicht unterstuetzt
        if not fn and not any(k in it for k in ("nav", "cmd", "controls", "sublabel")):
            it.update(sublabel=TYP_UNBEKANNT, subInfo=True, unbekannt=True)
        # Gesperrt (jLocked): die Kachel schaltet nicht, ein Tipp oeffnet die
        # Detailseite, die nennt, wer gesperrt hat und warum
        if self._sperre_text(uuid):
            it["sublabel"] = SPERRE_KURZ
            it.pop("subInfo", None)
            if "bigSub" in it:
                it["bigSub"] = SPERRE_KURZ
            it.pop("cmd", None)
            it.pop("controls", None)
            it.setdefault("nav", {"view": "control", "id": uuid})
        # Kategorie-Ampel: Bausteine mit an/aus-Zustand einer Kategorie mit
        # Zustandsfarben leuchten aktiv (on-Farbe) bzw. ok (off-Farbe). Analoge
        # Anzeigen, Zentralbausteine und Bausteine mit eigenem tone (Rauch/…)
        # bleiben unberuehrt.
        cs = self._cat_states(c.get("cat"))
        if cs and t not in _ANALOG and not (t or "").startswith("Central") and not it.get("tone"):
            rgb = _hex_rgb(cs.get("on") if it.get("on") else cs.get("off"))
            if rgb:
                st = it.setdefault("style", {})
                # Deckkraft folgt den Overlay-Reglern (--ov-fill/--ov-bord, Panel-
                # bzw. Pro-Kachel-Einstellung, inkl. Modus nur-Rahmen/nur-Fuellung)
                # statt fest .16/.55 -> "Hintergrund/Rahmen transparenter" wirkt
                # damit auch auf die Kategorie-Ampel-Kacheln. Fallback = altes
                # Aussehen, wenn kein Overlay konfiguriert ist.
                st.setdefault("bg", "rgba(%s,var(--ov-fill,.16))" % rgb)
                st.setdefault("border", "rgba(%s,var(--ov-bord,.55))" % rgb)
        return self._apply_tile_style(it, uuid, prof)

    def _apply_tile_style(self, it: dict, uuid: str, prof: dict | None) -> dict:
        """Pro-Kachel-Overrides (Farben/Icon/Schrift/Breite) aus dem Panel-Profil."""
        ov = (prof.get("tiles") if prof else {}).get(uuid) if prof else None
        # Breite: zwei Spalten fuer Audio, Raumregelung und Energiefluss
        # (KACHEL_BREIT_TYPEN), je Kachel uebersteuerbar (w = 1 | 2); nur die
        # breite Kachel traegt das Feld, schmal ist der Standard der Visu.
        w = _kachel_breite(ov.get("w")) if isinstance(ov, dict) else None
        if w is None:
            w = 2 if (self.controls.get(uuid) or {}).get("type") in KACHEL_BREIT_TYPEN else 1
        if w == 2:
            it["w"] = 2
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
            ialpha, ibw = _inactive_border(ov["overlay"])
            style["tileBord"] = f"rgba(255,255,255,{ialpha:.3g})"   # inaktiver Rahmen nur fuer diese Kachel
            style["tileBw"] = ibw
            rop, rtrk, rw = _posring(ov["overlay"])
            style["ringOp"] = f"{rop:.3g}"      # Positionsring nur fuer diese Kachel
            style["ringTrk"] = f"{rtrk:.3g}"
            style["ringW"] = rw
        if style:
            it["style"] = style
        ic = ov.get("icon")
        if isinstance(ic, dict):
            s = ic.get("src")
            if s == "builtin" and ic.get("id"):
                it["icon"] = ic["id"]
                it.pop("iconUrl", None)
            elif s == "loxone" and ic.get("p"):
                u = self._icon_url(ic["p"])
                if u:
                    it["iconUrl"] = u
            elif s == "loxlib" and ic.get("name"):
                it["iconUrl"] = "/loxlib?n=" + quote(str(ic["name"]))
        # Mini-Verlauf in der Kachel (tiles.<uuid>.chart = Zeitraum), nur fuer
        # Bausteine mit Aufzeichnung. Ein Tipp oeffnet wie bisher die Detailseite.
        rng = ov.get("chart")
        c = self.controls.get(uuid) or {}
        if rng in STAT_RANGES and (c.get("statistic") or c.get("statisticV2")):
            style = ov.get("chartStyle") if ov.get("chartStyle") in STAT_TILE_STYLES else "trend"
            sp = self._stat_spark(c, rng, style)
            if sp:
                it["spark"] = sp
        return it

    # ---- Views ----
    def _view_tab(self, tab: str, prof: dict | None = None) -> dict:
        if tab == HAUS_TAB:
            return self._view_haus({"view": "tab", "tab": tab}, prof)
        if tab in FRONT_TABS:
            titel, teil = FRONT_TABS[tab]
            return {"t": "view", "title": titel, "tab": tab,
                    "route": {"view": "tab", "tab": tab}, "items": [], "front": teil}
        ar = prof.get("rooms") if prof else None
        ac = prof.get("cats") if prof else None
        if self._haus_seite(tab, prof):
            return self._view_haus({"view": "tab", "tab": tab}, prof)
        if _is_pick(tab):
            # Freie Auswahl: genau die handverlesenen Bausteine, in der
            # gespeicherten Reihenfolge (= Klickreihenfolge in der Konfig).
            #
            # BEWUSST OHNE _room_ok/_cat_ok: wer einen Baustein ausdruecklich
            # auswaehlt, will ihn sehen - auch wenn sein Raum oder seine
            # Kategorie im Panelfilter fehlt. Sonst waere das Auswaehlen
            # wirkungslos und der Sinn der Seite dahin.
            #
            # _shown bleibt: "hide" ist panelweit und das Sicherheitsnetz.
            # Die Konfigurationsseite zeigt so einen Baustein ausgegraut.
            _pts = _pick_tabs(prof)
            _i = _pick_index(tab)
            _entry = _pts[_i] if 0 <= _i < len(_pts) else {"name": "Auswahl", "picks": []}
            # Widget-Seite: die ganze Seite ist EIN Widget (Vollbild-Tab), keine
            # Kacheln. Das Panel rendert es wie eine Pane, nur ueber die volle
            # Flaeche; der Datenkanal (energy/camera/status/player/chart) laeuft
            # ueber dieselbe set*-Mechanik wie Pane 2.
            _wdg = _clean_widget_tab(_entry.get("widget"))
            if _wdg:
                return {"t": "view", "title": _clean(_entry.get("name")) or "",
                        "tab": tab, "widget": _wdg,
                        "route": {"view": "tab", "tab": tab}}
            gewaehlt = _entry["picks"]
            uuids, gesehen = [], set()
            for u in gewaehlt:
                # Doppelte ueberspringen: zwei Kacheln mit derselben id wuerden
                # den In-place-Abgleich im Panel (updateGrid) durcheinander bringen.
                if u in gesehen or u not in self.controls or not self._shown(u, prof):
                    continue
                gesehen.add(u)
                uuids.append(u)
            sr = self._spans_rooms(uuids)
            # Werteleiste statt Anzeige-Kacheln - VOR dem Gruppieren, damit
            # Anker und Marken zu den Kacheln gehoeren, die im Raster bleiben
            uuids, leiste = self._leiste_trennen(uuids, tab, prof)
            # Groessen aus dem Seiten-Editor (Punkt 10): 1x1, 2x1 oder 2x2 je
            # Baustein, uebersteuern Typ und tiles[uuid].w auf dieser Seite
            groessen = {e["id"]: e for e in (_entry.get("layout") or [])}

            def kachel(u, **kw):
                it = self._control_item(u, prof, show_room=sr, **kw)
                g = groessen.get(u)
                if g:
                    if g["w"] == 2:
                        it["w"] = 2
                    else:
                        it.pop("w", None)
                    if g["h"] == 2:
                        it["h"] = 2
                return it
            title = _entry["name"] or "Auswahl"
            if not _entry.get("byRoom", True):
                # Ohne Gruppierung: genau die Reihenfolge der Seite, ohne
                # Sprungmarken - so, wie der Seiten-Editor sie zeigt
                return {"t": "view", "title": title, "tab": tab,
                        "route": {"view": "tab", "tab": tab}, "items": [kachel(u) for u in uuids],
                        "catTabs": [], **self._leiste_items(leiste, prof, show_room=sr)}
            # Nach RAUM gruppieren, damit die untere Leiste die vorkommenden
            # Raeume als Sprungmarken zeigen kann und ein Tipp zur Gruppe
            # scrollt - dieselbe Bauform wie das Raum-Panel, nur nach Raum
            # statt nach Kategorie. Ohne das ist eine Seite aus 40 Bausteinen
            # quer durchs Haus auf einem 4-Zoll-Panel nicht mehr zu bedienen.
            #
            # Reihenfolge der Raeume = erstes Vorkommen in der Auswahl. Damit
            # bleibt die Klickreihenfolge aus der Konfiguration die fuehrende
            # Ordnung; innerhalb eines Raums stehen die Bausteine ebenfalls so,
            # wie sie gewaehlt wurden. Dicts halten die Einfuegereihenfolge.
            nach_raum: dict = {}
            for u in uuids:
                nach_raum.setdefault(self.controls[u].get("room"), []).append(u)
            raeume = [ru for ru in nach_raum if ru in self.rooms]
            # Sprungmarken ERSETZEN im Panel die ganze untere Leiste. Das ist
            # nur dann richtig, wenn diese Seite die einzige des Panels ist.
            # Steht der Auswahl-Tab dagegen neben anderen Seiten in der
            # klassischen Leiste, waeren die uebrigen Tabs nicht mehr
            # erreichbar - und der Zurueck-Knopf hilft nicht, weil die Seite
            # die unterste im Stapel ist.
            # Erst ab zwei Raeumen sind Sprungmarken ausserdem etwas wert: bei
            # einem einzigen zeigte die Leiste nur den Raum, in dem man steht.
            allein = list((prof.get("tabs") or []) if prof else []) == [tab]
            marken = allein and len(raeume) > 1
            items = []
            for ru in raeume:
                for j, u in enumerate(nach_raum[ru]):
                    it = kachel(u)
                    if marken and j == 0:
                        # Scroll-Anker fuer die Sprungmarke. Der Schluessel
                        # heisst im Panel catKey, weil dieselbe Mechanik schon
                        # fuer die Kategorien des Raum-Panels da ist - fuer das
                        # Panel ist er ein undurchsichtiger Schluessel. Ohne
                        # Leiste waere er ein totes Attribut, also nur dann.
                        it["catKey"] = ru
                    if marken:
                        # Gruppe an JEDER Kachel: das Panel laesst beim Sprung
                        # die ganze Gruppe aufleuchten und filtert nach ihr.
                        it["grp"] = ru
                    items.append(it)
            # Bausteine ohne bekannten Raum ans Ende, wie im Raum-Panel.
            for ru, us in nach_raum.items():
                if ru not in self.rooms:
                    items += [kachel(u) for u in us]
            raum_tabs = ([{"key": ru,
                           "label": _clean(self.rooms[ru].get("name")) or "Raum",
                           "iconUrl": self._icon_url(self.rooms[ru].get("image")) or ""}
                          for ru in raeume[:4]] if marken else [])
            return {"t": "view", "title": title, "tab": tab,
                    "route": {"view": "tab", "tab": tab}, "items": items,
                    "catTabs": raum_tabs, **self._leiste_items(leiste, prof, show_room=sr)}
        if isinstance(tab, str) and tab.startswith("cat:"):
            # Kategorie-Direkt-Tab: dieselben Controls wie im Kategorie-Drilldown
            cu = tab[4:]
            uuids = [u for u, c in self.controls.items()
                     if c.get("cat") == cu and self._room_ok(u, prof) and self._shown(u, prof)]
            sr = self._spans_rooms(uuids)
            uuids, leiste = self._leiste_trennen(uuids, tab, prof)
            items = [self._control_item(u, prof, show_room=sr) for u in uuids]
            title = _clean(self.cats.get(cu, {}).get("name")) or "Kategorie"
            return {"t": "view", "title": title, "tab": tab,
                    "route": {"view": "tab", "tab": tab}, "items": items,
                    **self._leiste_items(leiste, prof, show_room=sr)}
        if isinstance(tab, str) and tab.startswith("room:"):
            # Raum-Direkt-Tab: dieselben Controls wie im Raum-Drilldown. Als
            # ERSTER Tab ist er die Startseite - dann weckt das Panel direkt in
            # diesem Raum auf, ohne vorher Raum oder Kategorie zu waehlen.
            # Der Raumname steht schon im Tab, deshalb nicht noch an jeder Kachel.
            ru = tab[5:]
            uuids = [u for u, c in self.controls.items()
                     if c.get("room") == ru and self._cat_ok(u, prof) and self._shown(u, prof)]
            # Werteleiste VOR dem Gruppieren: Anker (catKey) und Marken gehoeren
            # zu den Kacheln, die im Raster bleiben
            uuids, leiste = self._leiste_trennen(uuids, tab, prof)
            # Raum-Panel: nach Kategorie gruppieren, damit die untere Leiste die
            # im Raum vorkommenden Kategorien als Tabs zeigt und ein Tipp zur
            # jeweiligen Kachel-Gruppe scrollt (keine Ueberschriften, Kacheln
            # bleiben normal 2x2). Die erste Kachel jeder Gruppe traegt catKey als
            # Scroll-Anker. Reihenfolge = cats_with; Bausteine ohne bekannte
            # Kategorie kommen ans Ende. Tabs: die ersten 4 Kategorien.
            by_cat: dict = {}
            for u in uuids:
                cu = self.controls[u].get("cat")
                by_cat.setdefault(cu if cu in self.cats else None, []).append(u)
            present = [c for c in self.cats_with if c in by_cat]
            # Gewaehlte Tab-Kategorien (Config) vor die uebrigen; leer = automatisch.
            chosen = [c for c in (prof.get("roomCats") or []) if c in by_cat] if prof else []
            if chosen:
                order = chosen + [c for c in present if c not in chosen]
                tab_cats = chosen[:4]
            else:
                order = present
                tab_cats = present[:4]
            # Der Raumname steht im Titel der Seite: aus den Kachelnamen faellt er heraus
            raumname = _clean(self.rooms.get(ru, {}).get("name"))
            items = []
            for cu in order:
                for j, u in enumerate(by_cat[cu]):
                    it = self._control_item(u, prof, ohne_raum=raumname)
                    if j == 0:
                        it["catKey"] = cu       # Scroll-Anker fuer den Kategorie-Tab
                    it["grp"] = cu              # Gruppe: Aufleuchten und Filter im Panel
                    items.append(it)
            cat_tabs = [{"key": cu,
                         "label": _clean(self.cats.get(cu, {}).get("name")) or "Kategorie",
                         "iconUrl": self._icon_url(self.cats.get(cu, {}).get("image")) or ""}
                        for cu in tab_cats]
            for u in by_cat.get(None, []):
                items.append(self._control_item(u, prof, ohne_raum=raumname))
            title = raumname or "Raum"
            return {"t": "view", "title": title, "tab": tab,
                    "route": {"view": "tab", "tab": tab}, "items": items,
                    "catTabs": cat_tabs, **self._leiste_items(leiste, prof, ohne_raum=raumname)}
        extra: dict = {}   # Werteleiste der Seite (nur Favoriten; Zentral, Raeume, Kategorien sind Listen)
        if tab == "favoriten":
            uuids = [u for u, c in self.controls.items()
                     if c.get("isFavorite") and self._room_ok(u, prof) and self._shown(u, prof)]
            sr = self._spans_rooms(uuids)
            uuids, leiste = self._leiste_trennen(uuids, tab, prof)
            items = [self._control_item(u, prof, show_room=sr) for u in uuids]
            extra = self._leiste_items(leiste, prof, show_room=sr)
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
                "items": items, **extra}

    def _view_group(self, route: dict, prof: dict | None = None) -> dict:
        kind, gid = route.get("kind"), route.get("id")
        layout = None
        ohne_raum = ""   # Raum-Seite: der Raumname steht im Titel, nicht noch in jedem Kachelnamen
        if kind == "cat":
            uuids = [u for u, c in self.controls.items()
                     if c.get("cat") == gid and self._room_ok(u, prof) and self._shown(u, prof)]
            title = _clean(self.cats.get(gid, {}).get("name")); tab = "kategorien"
            sr = self._spans_rooms(uuids)
            uuids, leiste = self._leiste_trennen(uuids, tab, prof)
            return {"t": "view", "title": title, "tab": tab, "route": route,
                    "layout": layout,
                    "items": [self._control_item(u, prof, show_room=sr) for u in uuids],
                    **self._leiste_items(leiste, prof, show_room=sr)}
        elif kind == "room":
            uuids = [u for u, c in self.controls.items()
                     if c.get("room") == gid and self._cat_ok(u, prof) and self._shown(u, prof)]
            title = _clean(self.rooms.get(gid, {}).get("name")); tab = "raeume"
            ohne_raum = title
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
        uuids, leiste = self._leiste_trennen(uuids, tab, prof)
        return {"t": "view", "title": title, "tab": tab, "route": route,
                "layout": layout, "items": [self._control_item(u, prof, ohne_raum=ohne_raum) for u in uuids],
                **self._leiste_items(leiste, prof, ohne_raum=ohne_raum)}

    def _view_control(self, uuid: str, rng: str | None = None, prof: dict | None = None) -> dict:
        v = self._view_control_inner(uuid)
        c = self.controls.get(uuid, {})
        # Verlaufs-Diagramme unter die Detailseite haengen, wenn der Baustein eine
        # Aufzeichnung hat. Nur bei Block-Seiten; die Route traegt dann den Zeitraum.
        if (c.get("statistic") or c.get("statisticV2")) and isinstance(v.get("blocks"), list):
            rng = rng if rng in STAT_RANGES else STAT_DEFAULT_RANGE
            charts = self._stat_blocks(c, rng)
            if charts:
                v["blocks"] = v["blocks"] + charts
                v["route"] = dict(v.get("route") or {}, range=rng)
        # Verlinkte Objekte (Structure File "links": Bausteine, die in Loxone
        # Config am Baustein verlinkt sind, etwa die Abholtermine am
        # Muell-Status): unter die Detailseite als Zeile tippbarer Zellen,
        # wie in der Loxone-App. Jede Zelle zeigt Name und Zustand, ein Tipp
        # oeffnet die Detailseite des Ziels oder schaltet es (Kacheln, die
        # direkt schalten). Nur bekannte, auf dem Panel nicht ausgeblendete
        # Bausteine; nur Block-Seiten.
        if isinstance(v.get("blocks"), list):
            links = self._link_blocks(c, uuid, prof)
            if links:
                v["blocks"] = v["blocks"] + links
        return v

    def _link_blocks(self, c: dict, uuid: str, prof: dict | None = None) -> list:
        """Blocks fuer die verlinkten Objekte eines Bausteins: Ueberschrift und
        eine umbrechende Zeile mit einer Zelle je Ziel. Leer, wenn der
        Baustein keine (bekannten) Links hat oder nur auf sich selbst zeigt.
        Auf dem Panel ausgeblendete Ziele (hide) bleiben weg wie ueberall
        sonst; ein gesichertes Ziel (Visu-PIN) traegt secured an der Zelle,
        die Visu fragt dann vor dem Schalten die PIN ab (Codex-Befunde)."""
        ziele = [u for u in (c.get("links") or []) if isinstance(u, str)
                 and u != uuid and u in self.controls and self._shown(u, prof)]
        if not ziele:
            return []
        cells = []
        for u in dict.fromkeys(ziele):   # Reihenfolge wie in Loxone Config, ohne Dubletten
            it = self._control_item(u, show_room=True)
            label = it.get("label") or "?"
            if it.get("sublabel"):
                label = f"{label} · {it['sublabel']}"
            cell = {"label": label, "on": bool(it.get("on"))}
            if it.get("nav"):
                cell["nav"] = it["nav"]
            elif it.get("cmd"):
                cell["cmd"] = it["cmd"]
                if it.get("secured"):
                    cell["secured"] = True
            else:
                cell["nav"] = {"view": "control", "id": u}
            cells.append(cell)
        return [{"k": "head", "text": "Verlinkte Objekte"},
                {"k": "row", "id": f"links:{uuid}", "wrap": True, "cells": cells}]

    def _view_control_inner(self, uuid: str) -> dict:
        c = self.controls.get(uuid, {})
        t = c.get("type")
        route = {"view": "control", "id": uuid}
        fn = bausteine.detail_fuer(t)
        if fn:
            return fn(self, uuid, c, route)
        return {"t": "view", "title": _clean(c.get("name")), "route": route,
                "items": [self._control_item(uuid)]}

    def render(self, route: dict, prof: dict | None = None) -> dict:
        out = self._render_seite(route, prof)
        # Seiten, auf denen Gesten wirken: was zwei Finger hier tun (Hinweis-Symbol)
        if (route or {}).get("view", "tab") in ("tab", "group"):
            hilfe = self.gesten_hilfe(route, prof)
            if hilfe:
                out["gestenHilfe"] = hilfe
        # Jede Seite eines gesicherten Bausteins, auch seine Unterseiten (Zone,
        # Weckzeit, Musikauswahl ...): die Visu fragt vor jedem Befehl die
        # Visu-PIN ab. Gruppe und Tab nicht - dort zaehlt die einzelne Kachel.
        if (out.get("route") or {}).get("view") not in ("group", "tab") \
                and self._gesichert((route or {}).get("id")):
            out["secured"] = True
        # Ebenso gesperrt (jLocked): oben steht, wer gesperrt hat und warum, die
        # Visu nimmt der Bedienung dieses Bausteins die Wirkung (gesperrt);
        # verlinkte Objekte bleiben bedienbar
        sperre = self._sperre_text((route or {}).get("id"))
        if sperre and (out.get("route") or {}).get("view") not in ("group", "tab"):
            out["gesperrt"] = sperre
            bl = out.get("blocks")
            if isinstance(bl, list):
                i = next((n for n, b in enumerate(bl) if b.get("k") not in ("hero", "cover", "video")), len(bl))
                out["blocks"] = bl[:i] + [{"k": "status", "text": sperre}] + bl[i:]
        return out

    def _render_seite(self, route: dict, prof: dict | None = None) -> dict:
        v = (route or {}).get("view", "tab")
        if v == "group":
            return self._view_group(route, prof)
        if v == "control":
            return self._view_control(route.get("id"), route.get("range"), prof)
        if v == "sources":
            return self._view_sources(route.get("id"))
        if v == "irrzone":
            return self._view_irr_zone(route.get("id"), route.get("zone"))
        if v == "alarmentry":
            return self._view_alarm_entry(route.get("id"), route.get("entry"))
        if v == "alarmsettings":
            return self._view_alarm_settings(route.get("id"))
        if v == "bells":
            return self._view_bells(route.get("id"))
        if v == "verlauf":
            return self._view_verlauf(route.get("id"))
        if v == "ircset":
            return self._view_irc_einstellungen(route.get("id"))
        if v == "durchsage":
            return self._view_durchsage(route.get("id"))
        if v == "tab" and self._haus_seite((route or {}).get("tab"), prof):
            # Hausuebersicht braucht die ganze Route (gewaehlte Zone, Unterseite)
            return self._view_haus(route, prof)
        return self._view_tab(route.get("tab", "favoriten"), prof)

    def _gesichert(self, uuid) -> bool:
        """Baustein mit Visu-Passwort (isSecured): Befehle nur mit PIN (sps/ios)."""
        return isinstance(uuid, str) and bool((self.controls.get(uuid) or {}).get("isSecured"))
