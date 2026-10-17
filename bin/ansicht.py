"""Eine Ansicht (Panel-Profil) aufloesen: Vorgaben, Ansicht und Geraet zum
wirksamen Profil (resolve_profile), daraus die Theme-Variablen der Visu
(_theme_vars), Bausteine und Kategorien zu UUIDs (_resolve_ids, _cat_*), der
Export der Ansichten fuer den Konfigurator (_panel_export) und theme.json
schreiben.

Die Methoden sind ein Mixin (Ansicht): App erbt sie und arbeitet mit ihnen auf ihrem
Zustand (self ist die App). Importiert webvisu nicht."""
from __future__ import annotations

import json
from pathlib import Path

import theme_colors
from bausteine.gemeinsam import _clean
from konfig import (
    _atomic_write, _clean_kachel_aktiv, _clean_kachel_farbton, _clean_kachel_set, _clean_kachelziel,
    _clean_kennung, _clean_pane_spalten, _clean_scale, _clean_svpane, _clean_tabpane,
    _clean_werteleiste, _clean_zielgeraet, DEFAULT_THEME, GESTEN_HINWEIS_STANDARD, GESTEN_STANDARD,
    GROESSEN_STANDARD, HAUS_AUFBAU_STANDARD, HAUS_AUFBAUTEN, _is_tab, KACHEL_ZIEL_STANDARD,
    load_theme, _pick_tabs, _pin_merken, THEME_UI_KEYS, VALID_TABS)


def _kachel_klassisch(ui: dict) -> bool:
    """Bisheriger Kachel-Aufbau (ui.tileLayout "classic")? Nicht mit einem
    Kachel-Set: das bringt seinen eigenen, neuen Aufbau mit (lx, mitte, kreis)."""
    return ui.get("tileLayout") == "classic" and not _clean_kachel_set(ui.get("tileSet"))


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


def _inactive_border(ov: dict) -> tuple[float, int]:
    """Overlay-Config -> (Rahmen-Alpha, Rahmenbreite px) fuer NICHT aktive Kacheln.

    Defaults entsprechen dem bisherigen fest verdrahteten --line (weiss 8%) und
    1px, damit sich ohne Konfiguration nichts aendert. `ibord`/`ibw` machen den
    sonst kaum sichtbaren Kachelrahmen (z.B. auf hellen Shelly-Displays) staerker.
    """
    ov = ov if isinstance(ov, dict) else {}
    def _num(key, default):
        try:
            return float(ov.get(key, default))
        except (TypeError, ValueError):
            return float(default)
    alpha = max(0.0, min(1.0, _num("ibord", 8) / 100.0))
    bw = max(1, min(4, int(_num("ibw", 1))))
    return alpha, bw


def _posring(ov: dict) -> tuple[float, float, int]:
    """Overlay-Config -> (Deckkraft Bogen, Deckkraft Spur, Strichstaerke viewBox).

    Defaults entsprechen dem bisher fest verdrahteten Aussehen (Bogen voll
    deckend, Spur 18 %, Strichstaerke 6), ohne Konfiguration aendert sich also
    nichts. Die Strichstaerke zaehlt in viewBox-Einheiten des Rings (0..100);
    in Pixeln ergibt sie `rw/100 * (Icon-Groesse + 18)`. Das ist der Regler,
    der zaehlt: weil der Ring 18 px Sockel hat, die Icon-Linie aber sauber mit
    der Icon-Groesse skaliert, faellt der Ring bei kleinen Icons deutlich
    dicker aus als die Linien, die er umschliesst (bei 24 px Icon Faktor 1,5).
    """
    ov = ov if isinstance(ov, dict) else {}

    def _num(key, default):
        try:
            return float(ov.get(key, default))
        except (TypeError, ValueError):
            return float(default)
    ring = max(0.0, min(1.0, _num("ring", 100) / 100.0))
    rtrk = max(0.0, min(1.0, _num("rtrk", 18) / 100.0))
    rw = max(1, min(12, int(_num("rw", 6))))
    return ring, rtrk, rw


class Ansicht:
    """Ansicht und Theme; Mixin der App (self ist die App)."""

    def _cat_entry(self, cat_uuid: str | None):
        """Passender categories-Eintrag (Match: Schluessel als Teilstring des
        Kategorienamens). Rueckgabe: str (nur Icon-Farbe) | dict {on,off}
        (Zustandsfarben) | None."""
        name = _clean((self.cats.get(cat_uuid) or {}).get("name") or "").lower()
        if not name:
            return None
        # Ergebnis je Kategoriename merken: jede Kachel fragt hier, und die
        # Suche laeuft ueber alle Eintraege (100.000 aus einer Sicherung ->
        # 0,7 s je Seite). Jede Theme-Aenderung laedt das Theme neu, also
        # gilt der Speicher genau solange wie dieses categories-Objekt.
        quelle = self.theme.get("categories", {})
        if self._cat_memo[0] is not quelle:
            self._cat_memo = (quelle, {})
        memo = self._cat_memo[1]
        if name not in memo:
            memo[name] = next((val for key, val in quelle.items()
                               if not key.startswith("_") and key.lower() in name), None)
        return memo[name]

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
        gesehen = set()
        for e in entries:
            e = str(e).strip()
            if not e or e in gesehen:          # doppelte Eintraege kosten sonst je einen Durchlauf
                continue
            gesehen.add(e)
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
        # Grundfarbe zuerst: daraus faellt der ganze Satz ab - Flaechen, Schrift,
        # Zweitzeile, Icon- und Zustandsfarben. Ohne Grundfarbe bleibt v leer und
        # es aendert sich nichts gegenueber frueher.
        # Ein Kachel-Set bringt seine Farben fertig mit und ersetzt die Herleitung
        # aus der Grundfarbe; ausdruecklich gewaehlte Zustandsfarben gelten auch dort.
        _set = theme_colors.kachel_set(_clean_kachel_set(ui.get("tileSet")),
                                       _clean_kachel_farbton(ui.get("tileHue")),
                                       _clean_kachel_aktiv(ui.get("tileActive")))
        if _set:
            v = _set
        else:
            v = dict(theme_colors.derive(ui["baseColor"]) or {}) if ui.get("baseColor") else {}
        # Ausdruecklich eingestellte Zustandsfarben schlagen die Herleitung.
        # Aber: "nicht gesetzt" gibt es bei states gar nicht - load_theme()
        # fuellt sie immer aus DEFAULT_THEME, und theme.example.json liefert
        # dieselben Werte. Als ausdrueckliche Wahl zaehlt deshalb nur ein Wert,
        # der von der eingebauten Vorgabe abweicht. Sonst wuerden die alten
        # Festfarben jedes hergeleitete Theme ueberschreiben und die ganze
        # Nachrechnung in theme_colors.py waere fuer diese Rollen wirkungslos.
        _hergeleitet = bool(v)
        _vorgabe = DEFAULT_THEME["states"]

        def _gewaehlt(key: str):
            wert = states.get(key)
            if not wert:
                return None
            if _hergeleitet and str(wert).strip().lower() == str(_vorgabe.get(key, "")).lower():
                return None
            return wert

        for _var, _key in (("--glow", "active"), ("--good", "good"),
                           ("--crit", "crit"), ("--warn", "warn")):
            _wert = _gewaehlt(_key)
            if _wert:
                v[_var] = _wert
        if _gewaehlt("good"):
            # Der Akzent zieht mit der OK-Farbe mit, damit aktiver Tab,
            # Energiefluss-Ring und Kalender ("heute") die eingestellte Farbe
            # uebernehmen statt auf dem Default (#52b881) zu bleiben - AUCH ohne
            # Panel-Farbe (loest #16: --accent wurde vorher nie an die Panels
            # geschickt). Mit Panel-Farbe schlaegt eine ausdrueckliche OK-Farbe
            # den hergeleiteten Akzent, sonst bleibt der hergeleitete Wert.
            v["--accent"] = _gewaehlt("good")
            _rgb = _hex_rgb(_gewaehlt("good"))
            if _rgb:
                v["--accent-rgb"] = _rgb
                # Schrift auf dem Akzent (Kalender "heute", Entwurfsmarke)
                # zieht mit, sonst bleibt sie fuer den alten Akzent gerechnet
                v["--on-accent"] = theme_colors.schrift_auf(_gewaehlt("good"))
        # Groessen in px: Panel, sonst global, sonst der Standard des Kachel-Aufbaus
        std = GROESSEN_STANDARD["classic" if _kachel_klassisch(ui) else "neu"]
        # ... ein Kachel-Set bringt eigene Standardgroessen mit (KACHEL_SETS "groessen")
        _ks_e = theme_colors.KACHEL_SETS.get(_clean_kachel_set(ui.get("tileSet")) or "") or {}
        std = {**std, **(_ks_e.get("groessen") or {})}
        for _var, _key in (("--ico-size", "iconSize"), ("--name-size", "nameSize"),
                           ("--sub-size", "subSize"), ("--room-size", "roomSize"),
                           ("--big-size", "bigSize")):
            v[_var] = f"{ui.get(_key) or std[_key]}px"
        v["--name-weight"] = "700" if ui.get("bold") else "450"
        # Zustands-Farben zusaetzlich als R,G,B-Tripel, damit das Aktiv-Overlay
        # (Fuellung/Rahmen) die konfigurierte Farbe mit variabler Deckkraft nutzt.
        for skey, rvar in (("active", "--on-rgb"), ("good", "--good-rgb"),
                           ("crit", "--crit-rgb"), ("warn", "--warn-rgb")):
            rgb = _hex_rgb(_gewaehlt(skey))
            if rgb:
                v[rvar] = rgb
        # Aussehen des Aktiv-Overlays (global fuers Panel; pro Kachel ueberschreibbar).
        if isinstance(ui.get("overlay"), dict):
            fill, bord, bw = _overlay_alphas(ui["overlay"])
            v["--ov-fill"] = f"{fill:.3g}"
            v["--ov-bord"] = f"{bord:.3g}"
            v["--ov-bw"] = f"{bw}px"
            # Rahmen der NICHT aktiven Kacheln (sonst kaum sichtbar auf hellen Displays).
            ialpha, ibw = _inactive_border(ui["overlay"])
            v["--tile-bord"] = f"rgba(255,255,255,{ialpha:.3g})"
            v["--tile-bw"] = f"{ibw}px"
            # Positionsring (Rollladen/Tor/Fenster/Dimmer) - herunterdrehbar, wo
            # er zu kraeftig wirkt.
            rop, rtrk, rw = _posring(ui["overlay"])
            v["--posring-op"] = f"{rop:.3g}"
            v["--posring-trk"] = f"{rtrk:.3g}"
            v["--posring-w"] = f"{rw}"
        if ui.get("font"):
            v["--font"] = ui["font"]
        if ui.get("textColor"):
            v["--name-color"] = ui["textColor"]
        if ui.get("cols") == 3:
            v["--cols"] = "3"          # 3 Spalten (3x2 / 3x3); Default 2
        if ui.get("rows") == 3:
            v["--rows"] = "3"          # 3 Zeilen (2x3 / 3x3); Default 2
        nudge = ui.get("nudgeX")
        if nudge not in (None, ""):
            # Horizontaler Feinversatz der ganzen Visu (px, negativ = nach links)
            # gegen Display-Overscan. Wird vom Frontend als --nudge-x angewandt.
            try:
                v["--nudge-x"] = f"{float(nudge):g}px"
            except (TypeError, ValueError):
                pass
        # Nacht-Uhr: ihr Grund und eine Schrift, die darauf traegt. Ohne
        # Schrift aus Set oder Grundfarbe gelten die Standardfarben der Visu
        # (dunkel, helle Schrift), dort nimmt sie --ink.
        v["--nacht-grund"] = theme_colors.NACHT_GRUND
        if v.get("--ink"):
            v["--nacht-ink"] = theme_colors.nacht_schrift(v["--ink"])
        # Gesten im Vollbild: Schrift auf der Fuellung, Vorhang der Jalousie,
        # gedaempft fuer die Nacht. Ohne Set und Grundfarbe aus den
        # Standardfarben der Visu, eine gewaehlte Zustandsfarbe geht mit.
        v.update(theme_colors.geste_farben(v))
        return {k: val for k, val in v.items() if val}

    def resolve_profile(self, pid: str | None, entwurf: dict | None = None) -> dict:
        """Aufgeloestes Panel-Profil: Theme-Vars, Tabs, Raum-/Kategorie-Filter.
        Mit `entwurf` (entwurf_profil) gilt dieses Profil statt des gespeicherten.
        Ein unbekanntes Profil (geloescht, vertippt) zeigt das Standardprofil und
        heisst auch so: sonst nennte die Geraeteliste eine Ansicht, die es nicht
        mehr gibt."""
        prof = entwurf if entwurf is not None else \
            (self.panels.get(pid or "") or self.panels.get("default") or {})
        pid = pid if pid and (entwurf is not None or pid in self.panels) else "default"
        ui = {**self.theme.get("ui", {}), **(prof.get("ui") or {})}
        states = {**self.theme.get("states", {}), **(prof.get("states") or {})}
        tabs = [t for t in (prof.get("tabs") or ui.get("tabs") or []) if _is_tab(t)] or \
            ["favoriten", "zentral", "raeume", "kategorien"]
        return {
            "id": pid,
            # Entwurf (nicht gespeichert): die Visu zeigt es an, die ID-Nachschlager
            # (panel_dpms, panel_night, panel_reload) lesen dann `roh` statt der Datei
            **({"entwurf": True, "roh": prof} if entwurf is not None else {}),
            "title": prof.get("title") or "LoxPanel",
            "tabs": list(tabs),
            "rooms": self._resolve_ids(prof.get("rooms"), self.rooms),
            "cats": self._resolve_ids(prof.get("cats"), self.cats),
            "vars": self._theme_vars(states, ui),
            "tiles": prof.get("tiles") or {},
            "roomCats": [c for c in (prof.get("roomCats") or []) if isinstance(c, str)],
            "hide": {u for u in (prof.get("hide") or []) if isinstance(u, str)},
            # Liste, kein Set: die Reihenfolge ist die Anzeigereihenfolge.
            "picks": [u for u in (prof.get("picks") or []) if isinstance(u, str)],
            "pickName": prof.get("pickName") or "",
            "pickTabs": _pick_tabs(prof),   # bis 4 freie Seiten [{name, picks}]
            "lang": (ui.get("lang") or "de"),   # Panel-Sprache (Datum/Uhr; spaeter i18n der Texte)
            "fill": bool(ui.get("fill")),       # Visu fuellt grosse Screens (quadratische Kacheln)
            # Split-Screen an/aus (aus = 4"-Panel: nur die Visu, keine Pane 2, keine
            # Verdopplung). Default an; nur bei explizitem False aus.
            "split": ui.get("split") is not False,
            # Sprungmarken der unteren Leiste (Raum-Panel, freie Auswahl): ein
            # Tipp springt zur Gruppe (Standard) oder zeigt nur sie (Filter).
            "catFilter": ui.get("catFilter") is True,
            # Kachel-Aufbau: "" = neuer (Raum oben rechts, Zustand gross, Bedienleiste
            # unten), "classic" = der bisherige. Das Raster (cols/rows) bleibt davon
            # unberuehrt. Ein Kachel-Set bringt seinen eigenen (neuen) Aufbau mit.
            "tileLayout": "classic" if _kachel_klassisch(ui) else "",
            # Kachel-Set: "" = Standard, sonst Name aus theme_colors.KACHEL_SETS.
            # Die Visu setzt ihn als html[data-kachelset], dazu seine Art fuer
            # Kachel und Tab-Leiste (html[data-kachelset-aufbau|-leiste], dort
            # haengen die Regeln); die Farben und Masse stehen in vars.
            "tileSet": _clean_kachel_set(ui.get("tileSet")) or "",
            "tileSetAufbau": theme_colors.kachel_set_art(_clean_kachel_set(ui.get("tileSet")))[0],
            "tileSetLeiste": theme_colors.kachel_set_art(_clean_kachel_set(ui.get("tileSet")))[1],
            # Automatisches Raster: Zielgroesse einer Kachel in px; 0 = festes
            # Raster aus cols/rows (4"-Panel und jedes Profil ohne "auto").
            "gridAuto": ((_clean_kachelziel(ui.get("tileSize")) or KACHEL_ZIEL_STANDARD)
                         if ui.get("grid") == "auto" else 0),
            # Feste Breite des Widgets im automatischen Raster in Kachelspalten
            # (hochkant Zeilen); 0 = Automatik, rund PANE_ANTEIL der Spalten.
            "paneCols": _clean_pane_spalten(ui.get("paneCols")) or 0,
            # Split-Pane pro Tab: Tab-Kennung -> "weather"|"calendar"|"player:<uuid>".
            # Nur wirksam, wenn split an ist. Das Panel rendert die passende Pane.
            # Normiert, denn die Datei wird beim Laden nicht sanitisiert: eine
            # von Hand geschriebene "status:A, B" kaeme sonst roh ins Panel.
            "panes": ({str(k): _clean_tabpane(v) for k, v in ui["panes"].items()
                       if isinstance(k, str) and _clean_tabpane(v)}
                      if isinstance(ui.get("panes"), dict) else {}),
            # Seiten (Tab-Kennungen), deren Anzeige-Bausteine als Werteleiste
            # in einer Zeile ueber dem Raster stehen statt als Kacheln.
            "valueBar": _clean_werteleiste(ui.get("valueBar")),
            # Rechte Spalte der Uhr-Seite: "" = Automatik (Termine, sonst
            # Wetter-Details), sonst off/calendar/weather/energy:/camera:/status:.
            "svPane": _clean_svpane(ui.get("svPane")),
            # Skalierung laut Profil, sonst global (ui ist oben schon aus Theme
            # und Profil gemischt): "off" | "auto" | Faktor. Ein Geraet kann
            # sie uebersteuern, siehe effective_scale().
            "scale": _clean_scale(ui.get("scale")) or "off",
            # Visu-PIN gesicherter Bausteine so viele Sekunden behalten (0 = nie)
            "pinMerken": _pin_merken(ui.get("pinMerken")),
            # Gesten wie auf den Loxone-Tastern (ui ist aus Vorgaben und Ansicht
            # gemischt: die Ansicht geht vor) und ihr Raum ausserhalb von
            # Raumseiten ("" = dort keine Wirkung)
            "gesten": ui["gesten"] if isinstance(ui.get("gesten"), bool) else GESTEN_STANDARD,
            "gestenRaum": _clean_kennung(ui.get("gestenRaum")),
            # ... und ihr Hinweis-Symbol (Vorgaben und Ansicht gemischt wie oben)
            "gestenHinweis": (ui["gestenHinweis"] if isinstance(ui.get("gestenHinweis"), bool)
                              else GESTEN_HINWEIS_STANDARD),
            # Aufbau der Hausseite (HAUS_AUFBAUTEN)
            "hausAufbau": ui["hausAufbau"] if ui.get("hausAufbau") in HAUS_AUFBAUTEN else HAUS_AUFBAU_STANDARD,
        }

    # ---- Config-Seite (Panel-Editor) ----
    def _panel_export(self, raw: dict) -> dict:
        """Rohes Profil aus der Datei -> UI-Form (rooms/cats als UUID-Listen,
        in Anzeige-Reihenfolge; leere Liste = alle)."""
        r = self._resolve_ids(raw.get("rooms"), self.rooms)
        c = self._resolve_ids(raw.get("cats"), self.cats)
        tabs = [t for t in (raw.get("tabs") or VALID_TABS) if _is_tab(t)]
        ui = {k: v for k, v in (raw.get("ui") or {}).items()
              if k in ("iconSize", "nameSize", "subSize", "roomSize", "bigSize", "font", "nudgeX",
                       "dpmsOff", "reloadHours", "nightDim", "nightWake",
                       "cols", "rows", "fill", "baseColor",
                       "overlay", "textColor", "bold", "lang", "player", "panes", "split",
                       "svPane", "scale", "catFilter", "tileLayout", "tileSet", "tileHue", "tileActive",
                       "grid", "tileSize", "pinMerken",
                       "valueBar", "paneCols", "gesten", "gestenRaum", "gestenHinweis",
                       "nightClock", "nightClockBright", "hausAufbau")}
        # Widget je Tab: nur gueltige Tab-Kennung und gueltiger Pane-Wert, und
        # zwar der NORMIERTE ("header:A, B" -> "header:A,B"): Dateien von Hand
        # oder ueber die API koennen Leerzeichen tragen, die das Panel sonst
        # als Teil der UUID meldete.
        if isinstance(ui.get("panes"), dict):
            ui["panes"] = {str(k): _clean_tabpane(v) for k, v in ui["panes"].items()
                           if isinstance(k, str) and _is_tab(k) and _clean_tabpane(v)}
            if not ui["panes"]:
                ui.pop("panes", None)
        else:
            ui.pop("panes", None)
        # Rechte Spalte des Screensavers: derselbe Pruefer wie beim Speichern,
        # damit der Konfigurator nie einen Wert anzeigt, den der Server verwirft.
        _sp = _clean_svpane(ui.get("svPane"))
        if _sp:
            ui["svPane"] = _sp
        else:
            ui.pop("svPane", None)
        # Skalierung: "off" | "auto" | Faktor; fehlt sie, gilt die globale.
        _sc = _clean_scale(ui.get("scale"))
        if _sc is not None:
            ui["scale"] = _sc
        else:
            ui.pop("scale", None)
        # Zielkachel als Zahl, auch wenn die Datei noch eine Stufe nennt
        _tz = _clean_kachelziel(ui.get("tileSize"))
        if _tz is not None:
            ui["tileSize"] = _tz
        else:
            ui.pop("tileSize", None)
        # Werteleiste: nur gueltige Tab-Kennungen, jede einmal
        _vb = _clean_werteleiste(ui.get("valueBar"))
        if _vb:
            ui["valueBar"] = _vb
        else:
            ui.pop("valueBar", None)
        return {
            "title": raw.get("title") or "",
            "tabs": tabs or list(VALID_TABS),
            "rooms": [u for u in self.rooms_with if r and u in r],
            "cats": [u for u in self.cats_with if c and u in c],
            # Raum-Panel: gewaehlte Kategorie-Tabs in Klickreihenfolge, wie sie
            # _sanitize_panels speichert (nicht sortieren, nicht gegen die
            # Struktur filtern). Fehlt es hier, zeigt der Editor "automatisch",
            # und das naechste Speichern - auch eines anderen Profils - loescht es.
            "roomCats": [x for x in (raw["roomCats"] if isinstance(raw.get("roomCats"), list) else [])
                         if isinstance(x, str)][:4],
            "ui": ui,
            "states": {k: v for k, v in (raw.get("states") or {}).items()
                       if k in ("active", "good", "warn", "crit")},
            "tiles": raw.get("tiles") if isinstance(raw.get("tiles"), dict) else {},
            "hide": [u for u in (raw.get("hide") or [])
                     if isinstance(u, str) and u in self.controls],
            # Zielgeraet (Punkt 15): nur, wenn eines gesetzt ist
            **({"device": _z} if (_z := _clean_zielgeraet(raw.get("device"))) else {}),
            # Reihenfolge ist die Klickreihenfolge, deshalb NICHT sortieren -
            # anders als rooms/cats, die der Loxone-Reihenfolge folgen.
            "picks": [u for u in (raw.get("picks") or [])
                      if isinstance(u, str) and u in self.controls],
            "pickName": raw.get("pickName") or "",
            # Bis zu 4 freie Seiten [{name, picks, icon}]. MUSS mit exportiert
            # werden, sonst verliert der Konfigurator beim Neuladen die Seiten
            # 2-4: er baut aus den (leeren) Legacy-Feldern nur EINE Pick-Seite,
            # waehrend "tabs" noch vier Kennungen fuehrt - beim naechsten
            # Bearbeiten synct der Client "tabs" dann auf die eine Seite herunter.
            "pickTabs": _pick_tabs(raw),
        }

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
        for k in THEME_UI_KEYS:
            if k in ui:
                cur[k] = ui[k]
            else:
                cur.pop(k, None)
        doc["ui"] = cur
        if categories is not None:
            keep = {k: v for k, v in (doc.get("categories") or {}).items()
                    if str(k).startswith("_")}   # _comment behalten
            doc["categories"] = {**keep, **categories}
        _atomic_write(f, json.dumps(doc, indent=2, ensure_ascii=False) + "\n")
        self.theme = load_theme()
        self._dirty = True   # verbundene Panels neu rendern lassen
