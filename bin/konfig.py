"""Konfiguration von LoxPanel: die Dateien unter config/ (loxpanel.cfg,
panels.json, theme.json) lesen, pruefen und schreiben.

- Pfade und atomares Schreiben (_atomic_write), die Leser der loxpanel.cfg
  (_config/_ms_zugang fuer den Miniserver, _audio_config, _intercom_config,
  _night_config, _calendar_config ...), load_theme/load_panels/load_devices.
- Was eine Ansicht, ein Geraet und die Vorgaben enthalten duerfen: die
  Konstanten (PANEL_STANDARD, THEME_UI_KEYS, KACHEL_ZIEL, GERAETE_KATALOG ...),
  die Wertepruefer (_clean_*, _color_ok, _pin_merken) und die Sanitizer
  (_sanitize_panels, _sanitize_devices, _sanitize_theme_ui ...), die der
  Server beim Speichern und die Sicherung beim Einspielen rufen. App haelt sie
  als statische Methoden (App._sanitize_panels ...), damit Server und Tests sie
  wie bisher rufen.
- Tabs und Seiten einer Ansicht (VALID_TABS, PICK_TAB, _pick_tabs ...).

Importiert webvisu.py nicht; webvisu.py importiert von hier. Die Tests leiten
die Pfade ueber die Fixture cfg_ordner in allen Server-Modulen um."""
from __future__ import annotations

import json
import logging
import math
import os
import re
from pathlib import Path

import theme_colors

log = logging.getLogger("loxpanel.konfig")

# Die Konfigdateien (im Container das Volume /app/config). Die Tests leiten die
# Pfade ueber die Fixture cfg_ordner um, in jedem Modul, das sie kennt.
_CFGDIR = Path(__file__).resolve().parent.parent / "config"
PANELS_FILE = _CFGDIR / "panels.json"
CFG_FILE = _CFGDIR / "loxpanel.cfg"
CFG_EXAMPLE = _CFGDIR / "loxpanel.cfg.example"
THEME_FILE = _CFGDIR / "theme.json"


def _load_cfg() -> dict:
    for f in (CFG_FILE, CFG_EXAMPLE):
        if f.is_file():
            try:
                cfg = json.loads(f.read_text(encoding="utf-8"))
            except ValueError:
                continue
            if f == CFG_EXAMPLE and isinstance(cfg, dict):
                # Der Miniserver-Abschnitt der Vorlage ist ein Platzhalter
                # (192.168.1.50, CHANGEME): nie als Zugang anzeigen und nie beim
                # Speichern einer anderen Einstellung nach loxpanel.cfg uebernehmen.
                cfg.pop("miniserver", None)
            return cfg
    return {}


def _atomic_write(path: Path, text: str) -> None:
    """Schreibt text atomar: erst nach <datei>.tmp, fsync, dann os.replace, zum
    Schluss fsync auf das Verzeichnis (macht auch das Umbenennen dauerhaft). Ein
    Crash/Stromausfall mitten im Schreiben laesst so die alte, vollstaendige
    Datei stehen statt einer halben, kaputten (F5). Die .tmp wird bei einem
    Fehler wieder entfernt, damit keine Bruchstuecke liegen bleiben."""
    tmp = path.with_name(path.name + ".tmp")
    try:
        with open(tmp, "w", encoding="utf-8") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            tmp.unlink()
        except OSError:
            pass
        raise
    try:                       # Verzeichnis-fsync: macht os.replace dauerhaft
        dfd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(dfd)
        finally:
            os.close(dfd)
    except OSError:
        pass                   # nicht auf jeder Plattform/FS moeglich, best effort


def _write_cfg(cfg: dict) -> None:
    _atomic_write(CFG_FILE, json.dumps(cfg, indent=2, ensure_ascii=False) + "\n")


VALID_TABS = ["favoriten", "zentral", "raeume", "kategorien"]

# Freie Bausteinauswahl: bis zu 4 Seiten je Panel, die Bausteine unabhaengig von
# Raum und Kategorie zusammenstellen. Tabs: "auswahl", "auswahl2".."auswahl4".
# Die Seiten stehen im Profil unter "pickTabs" [{name, picks}]; ein altes
# picks/pickName (Einzel-Seite) wird rueckwaertskompatibel zur ersten Seite.
PICK_TAB = "auswahl"

PICK_TABS_MAX = 4


def _pick_key(i):
    """Tab-Kennung der i-ten freien Seite: auswahl, auswahl2, auswahl3, auswahl4."""
    return PICK_TAB if i == 0 else PICK_TAB + str(i + 1)


def _pick_index(t):
    """Index (0..3) eines Auswahl-Tabs, sonst -1."""
    if t == PICK_TAB:
        return 0
    if isinstance(t, str) and t.startswith(PICK_TAB):
        s = t[len(PICK_TAB):]
        if s.isdigit() and 2 <= int(s) <= PICK_TABS_MAX:
            return int(s) - 1
    return -1


def _is_pick(t):
    return _pick_index(t) >= 0


def _seiten_layout(v) -> list | None:
    """Anordnung einer freien Seite aus dem Seiten-Editor (pickTabs[i].layout,
    Punkt 10): [{id, w, h}] in der Reihenfolge der Seite, w und h je 1 oder 2.
    Eine hohe Kachel ist immer auch breit - die Groessen sind 1x1, 2x1 und 2x2.
    Doppelte ids fallen weg; kein Layout (None) heisst Groesse nach tiles bzw.
    Typ und Reihenfolge wie in picks."""
    if not isinstance(v, list):
        return None
    out, gesehen = [], set()
    for e in v[:60]:
        if not isinstance(e, dict):
            continue
        u = e.get("id")
        if not isinstance(u, str) or not u or u in gesehen:
            continue
        gesehen.add(u)
        w, h = _kachel_breite(e.get("w")) or 1, _kachel_breite(e.get("h")) or 1
        out.append({"id": u, "w": 2 if h == 2 else w, "h": h})
    return out


def _layout_mit_picks(layout, picks: list) -> tuple[list, list | None]:
    """picks bestimmt, was auf der Seite steht, das Layout Reihenfolge und
    Groesse: Eintraege, die nicht (mehr) in picks stehen, fallen weg, Bausteine
    ohne Eintrag kommen hinten an (Groesse nach tiles bzw. Typ) - so bleibt
    eine Seite stimmig, auch wenn nur picks geaendert wurde (Raumtausch beim
    Duplizieren, Bausteinliste). -> (picks in Seitenfolge, Layout)."""
    if layout is None:
        return picks, None
    drin = set(picks)
    layout = [e for e in layout if e["id"] in drin]
    im_layout = {e["id"] for e in layout}
    return [e["id"] for e in layout] + [u for u in picks if u not in im_layout], layout


def _pick_tabs(prof):
    """Freie Seiten eines Profils als [{name, picks}] (max 4). Rueckwaerts-
    kompatibel: ein altes picks/pickName wird zur ersten Seite. Mit Layout aus
    dem Seiten-Editor stehen die picks in dessen Reihenfolge; byRoom (Standard
    an) gruppiert die Seite in der Visu nach Raum."""
    if not prof:
        return []
    pt = prof.get("pickTabs")
    if isinstance(pt, list) and pt:
        out = []
        for e in pt[:PICK_TABS_MAX]:
            if isinstance(e, dict):
                picks, layout = _layout_mit_picks(_seiten_layout(e.get("layout")),
                                                  [u for u in (e.get("picks") or []) if isinstance(u, str)])
                seite = {"name": str(e.get("name") or "Auswahl"),
                         "picks": picks,
                         "icon": str(e.get("icon") or ""),
                         # Statt Kacheln kann eine freie Seite ein Widget sein
                         # (Wetter/Kalender/Energie/Kamera/Verlauf/Werte/Audio),
                         # als Vollbild-Tab. Leer = Kachelseite (picks).
                         "widget": _clean_widget_tab(e.get("widget")),
                         "byRoom": e.get("byRoom") is not False}
                if layout is not None:
                    seite["layout"] = layout
                out.append(seite)
        return out
    if prof.get("picks"):
        return [{"name": str(prof.get("pickName") or "Auswahl"),
                 "picks": [u for u in prof.get("picks") if isinstance(u, str)],
                 "icon": ""}]
    return []


# Kalender und Wetter als eigene Seite in der unteren Leiste. Der Inhalt kommt
# aus der Front ({t:"front"}), die jedes Panel ohnehin bekommt; die Seite sagt
# nur, welcher Teil gezeigt wird. Schluessel -> (Titel, Teil der Front).
FRONT_TABS = {"kalender": ("Kalender", "calendar"), "wetter": ("Wetter", "weather")}

# Hausuebersicht als eigene Seite (_view_haus): Raeume mit Hauptwert, was gerade
# an ist (mit Aus-Taste), Schnellaktionen und der Spieler einer Audio-Zone.
HAUS_TAB = "haus"

# Aufbau der Hausseite je Ansicht (ui.hausAufbau), Name -> Beschriftung im
# Konfigurator (i18n.js uebersetzt sie): "status" stellt "Gerade aktiv" nach
# oben (Entwurf "Hausübersicht B"), "raeume" schaltet in jeder Raumkarte
# direkt (Entwurf "Hausübersicht C"), "spalte" hat links eine Spalte mit Uhr,
# Wetter, Energie, "Auf einen Blick" und den Schnellaktionen (Entwurf "Großes
# Display"). Ohne Einstellung "status" (PANEL_STANDARD).
HAUS_AUFBAUTEN = {"status": "Status zuerst", "raeume": "Räume direkt", "spalte": "Spalte links"}

HAUS_AUFBAU_STANDARD = "status"

# Gesten (Loxone-Standard wie auf den Tastern, docs/TODO.md §9): zwei Finger
# bedienen den Raum der Seite - Mitte Licht, links Beschattung, rechts Musik,
# Doppeltipp Raum verlassen, Dreifachtipp Haus aus. Die Visu erkennt die
# Geste; welche Bausteine sie trifft und welche Befehle gehen, entscheidet
# App.geste(). Ohne Einstellung in Vorgaben und Ansicht aus.
GESTEN_STANDARD = False

# Hinweis-Symbol der Gesten: rechts in der Fusszeile unter dem Kachelfeld, auf
# Seiten, auf denen Gesten wirken; ein Tipp zeigt, was zwei Finger dort tun.
# An, sobald Gesten an sind, wenn weder Vorgaben noch Ansicht etwas sagen.
GESTEN_HINWEIS_STANDARD = True

# Display-Treiber fuer Kiosk-Apps (Android) mit Standard-Port ihrer HTTP-Schnittstelle
DISPLAY_DRIVERS = {"fully": 2323, "wallpanel": 2971}


def _is_tab(t) -> bool:
    """Gueltiges Tab-Kennzeichen: einer der 4 Standard-Tabs, die freie Auswahl
    (`auswahl`), Kalender/Wetter (FRONT_TABS), die Hausuebersicht (HAUS_TAB)
    ODER eine einzelne Kategorie bzw. ein einzelner Raum als Direkt-Tab
    (`cat:<uuid>`/`room:<uuid>`)."""
    if t in VALID_TABS or _is_pick(t) or t in FRONT_TABS or t == HAUS_TAB:
        return True
    if not isinstance(t, str):
        return False
    return ((t.startswith("cat:") and len(t) > 4)
            or (t.startswith("room:") and len(t) > 5))


# Verlaufs-Diagramme fuer Bausteine mit `statistic` in der Struktur. Die Daten
# liegen am Miniserver als Monatsdateien /stats/<uuidAction>.<JJJJMM>.xml (so
# listet sie /stats/, und so fuehrt sie die Loxone-App: STATISTIC-Befehle in
# scripts4.js, ermittelt mit bin/statistic_probe.py). Der Zeitraum laeuft in der
# Route mit: {"view": "control", "id": uuid, "range": "7d"}.
STAT_RANGES = {"24h": ("24 h", 86400), "7d": ("7 Tage", 7 * 86400), "30d": ("30 Tage", 30 * 86400)}

# Anfragen an den Miniserver (Befehle, Verlaeufe, Icons) tragen das Token der
# Anmeldung. Es laeuft nach einiger Zeit ab, die WebSocket-Verbindung fuer die
# Anzeige braucht es danach aber nicht mehr - ohne Erneuerung zeigte das Panel
# nach 1-2 Tagen weiter Werte an, nahm aber keine Befehle mehr an. Meldet der
# Miniserver 401, meldet _ms_http() sich neu an und wiederholt die Anfrage.
MS_CMD_TIMEOUT = 10      # s: ein Befehl blockiert solange die Nachrichten seines Panels

# Lebenszeichen der Live-Verbindung (WebSocket): Nach der Anmeldung sendete
# LoxPanel dort nichts mehr, eine still abgerissene Verbindung (Strom, WLAN,
# NAT) oder ein Miniserver, der annimmt und schweigt, blieb unbemerkt haengen.
# Jetzt geht so oft "keepalive" raus (miniserver.keepalive_interval), der
# Miniserver antwortet mit einem Header der Kennung 6. Kommt danach binnen
# _ms_antwortfrist() nichts, wird neu verbunden. 60 s: Laut Loxone-Doku trennt
# der Miniserver Clients, die ueber 5 Minuten nichts senden; ein Ausfall faellt
# so nach gut einer Minute auf, und 8 Byte je Minute belasten niemanden.
MS_KEEPALIVE = 60        # s: Abstand der keepalive an den Miniserver

# Darstellung des Mini-Verlaufs in der Kachel (tiles.<uuid>.chartStyle). Fehlt der
# Schluessel, gilt "trend". Tagesmuster und Tagesspanne zeigen immer 7 Tage.
STAT_TILE_STYLES = ("trend", "pattern", "span")

KACHEL_BREITEN = (1, 2)

# Gesicherte Bausteine (isSecured): Nach richtiger Visu-PIN fragt die Visu so
# viele Sekunden nicht erneut (Panel-Option ui.pinMerken, 0 = jedes Mal). 30 s
# reichen fuer eine Bedienung (Helligkeit oder Lautstaerke in Schritten,
# Halten am Garagentor) und sind kurz genug, dass ein verlassenes Panel nicht
# offen bleibt; Uhr-Seite, Display aus und Seitenwechsel vergessen die PIN
# ohnehin sofort. Obergrenze wie bei "Display aus": eine Stunde.
PIN_MERKEN_STANDARD = 30

PIN_MERKEN_MAX = 3600

# Automatisches Raster (ui.grid "auto", fuer Tablets): Zielgroesse einer Kachel
# in CSS-Pixeln (ui.tileSize, je Geraet devices[name].tileTarget). Die Visu
# rechnet daraus Spalten und Zeilen fuer den Schirm, ein groesserer Schirm
# zeigt so mehr Kacheln statt groesserer; passen alle Kacheln einer Seite auf
# den Schirm, wachsen sie (KACHEL_WACHSEN unten, autoRaster() in panel.html).
# Einzige Quelle: effective_grid_auto() schickt den Wert mit der
# theme-Nachricht (Geraet vor Profil, wie bei der Skalierung). Die drei
# Stufen sind die alte Schreibweise und bleiben fuer bestehende Dateien lesbar
# (_clean_kachelziel).
KACHEL_ZIEL = {"small": 150, "medium": 170, "large": 200}

KACHEL_ZIEL_STANDARD = KACHEL_ZIEL["medium"]

KACHEL_ZIEL_MIN, KACHEL_ZIEL_MAX = 100, 400

# Passen alle Kacheln einer Seite auf den Schirm, duerfen sie bis auf das
# KACHEL_WACHSEN-Fache der Zielkachel wachsen (autoRaster() in panel.html,
# geschickt als gridGrow mit der theme-Nachricht).
KACHEL_WACHSEN = 1.4

# Katalog fuer den Assistenten (Punkt 9, Schritt 1): Geraete, die noch nicht
# verbunden sind, mit ihrer sichtbaren Flaeche in CSS-Pixeln - dieselben
# Standardgeraete wie in der Messreihe vom 06.10.2026 und den Browser-Tests.
# Der Konfigurator rechnet damit wie mit einer gemeldeten Groesse vor.
GERAETE_KATALOG = (
    {"name": "4″-Wandpanel", "vw": 480, "vh": 480},
    {"name": "Galaxy Tab A9 quer", "vw": 893, "vh": 533},
    {"name": "Galaxy Tab A9 hochkant", "vw": 533, "vh": 893},
    {"name": "iPad quer", "vw": 1024, "vh": 768},
    {"name": "iPad hochkant", "vw": 768, "vh": 1024},
    {"name": "10″-Tablet quer", "vw": 1280, "vh": 800},
    {"name": "10″-Tablet hochkant", "vw": 800, "vh": 1280},
)

# Widget (Pane 2) im automatischen Raster: ohne Einstellung belegt es diesen
# Anteil der Kachelspalten (quer) bzw. -zeilen (hochkant), gerundet
# (autoRaster() in panel.html, geschickt als paneShare mit der theme-Nachricht).
# ui.paneCols legt stattdessen eine feste Breite in Kachelspalten fest,
# 1 bis PANE_SPALTEN_MAX; 0 oder fehlt = Automatik.
PANE_ANTEIL = 0.4

PANE_SPALTEN_MAX = 3

# Panel-Angaben, die _sanitize_panels bewusst NICHT speichert, weil sie der
# Standard sind - beim Speichern kein Verlust (siehe _panels_verworfen).
# Pfad-Muster, "*" steht fuer einen beliebigen Schluessel (z. B. Kachel-UUID);
# ein Tupel nennt mehrere Schreibweisen desselben Standards.
PANEL_STANDARD = {("ui", "split"): True, ("ui", "tileSize"): (KACHEL_ZIEL_STANDARD, "medium"),
                  ("ui", "hausAufbau"): HAUS_AUFBAU_STANDARD,
                  ("ui", "pinMerken"): PIN_MERKEN_STANDARD,
                  ("ui", "paneCols"): 0,
                  # Farbton und aktive Kachel des Kachel-Sets mit Rechnung (touch)
                  ("ui", "tileHue"): theme_colors.KACHEL_SETS["touch"]["farbton"]["standard"],
                  ("ui", "tileActive"): theme_colors.KACHEL_SETS["touch"]["aktiv"]["standard"],
                  ("tiles", "*", "chartStyle"): "trend",
                  ("pickTabs", "*", "byRoom"): True}

_COLOR_RE = re.compile(r"^(#[0-9a-fA-F]{3,8}|rgba?\([0-9.,%\s]+\)|[a-zA-Z]{3,20})$")


def _color_ok(v) -> bool:
    return isinstance(v, str) and bool(_COLOR_RE.match(v.strip()))


# Unterstuetzte Panel-Sprachen (Basis-Codes). Steuert vorerst nur Datum/Uhr am
# Panel; die Uebersetzung der festen UI-/Statustexte folgt (i18n-Ausbau).
SUPPORTED_LANGS = ("de", "en", "fr", "it", "es", "nl")


def _pin_merken(v) -> int:
    """Sekunden, die die Visu eine richtige PIN behaelt; ungueltig -> Standard.
    json.loads nimmt Infinity und NaN an, int() wuerfe dabei."""
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
        return PIN_MERKEN_STANDARD
    return max(0, min(PIN_MERKEN_MAX, int(v)))


def _clean_lang(v):
    """Sprach-Code validieren (z.B. 'de', 'en', 'en-US'); '' wenn nicht unterstuetzt."""
    if not isinstance(v, str):
        return ""
    v = v.strip().lower()[:8]
    return v if v.split("-")[0] in SUPPORTED_LANGS else ""


# Screensaver: hoechstens so viele Status-Kacheln in der rechten Spalte. Mehr
# passt neben Uhr und Wetter auf keinem Panel lesbar hin.
SV_STATUS_MAX = 8

# Skalierung der Visu. Kette: global (theme.json ui.scale) -> Profil (ui.scale)
# -> Geraet (devices[name].scale); die spaetere gewinnt, FEHLT sie, gilt die
# fruehere. Deshalb speichern Profil und Geraet auch "off" ausdruecklich - sonst
# koennte ein Profil ein globales "auto" nicht abschalten. "auto" = das Panel
# rechnet selbst aus, wie weit es seinen Kasten ohne Rand und ohne Verzerrung
# vergroessern kann; eine Zahl ist ein fester Faktor (das Panel begrenzt ihn
# so, dass alles auf den Schirm passt); "off" = feste Groesse wie bisher. Die
# Grenzen stehen nur hier, der Konfigurator liest sie ueber /api/meta.
SCALE_MIN, SCALE_MAX = 0.5, 2.0

# Keys der globalen ui (theme.json), die der Konfigurator unter Vorgaben
# (Darstellung, Verhalten) setzt. Einzige Liste: _write_theme() schreibt genau
# diese, /api/meta liefert genau diese; was _sanitize_theme_ui() neu erlaubt,
# muss auch hier stehen, sonst geht es beim Speichern still verloren.
THEME_UI_KEYS = ("iconSize", "nameSize", "subSize", "roomSize", "bigSize", "font", "textColor",
                 "baseColor", "bold", "lang", "scale", "nightDim", "nightWake", "dpmsOff", "reloadHours",
                 "gesten", "gestenHinweis", "hausAus", "raumVerlassen", "nightClock", "nightClockBright")

# Groessen (px), wenn weder das Panel noch die globale Darstellung eine setzt,
# je Kachel-Aufbau. Der neue stellt meist den Zustand gross und den Namen klein
# darunter (wie die Kacheln der Loxone-App) und kommt mit etwas kleinerer
# Schrift aus. Einzige Quelle: _theme_vars() rechnet damit, /api/meta gibt sie
# dem Konfigurator, der sie in leeren Feldern anzeigt.
GROESSEN_STANDARD = {
    "neu": {"iconSize": 38, "nameSize": 16, "subSize": 14, "roomSize": 13, "bigSize": 36},
    "classic": {"iconSize": 38, "nameSize": 18, "subSize": 15, "roomSize": 12, "bigSize": 36},
}

# Nachtmodus ohne Einstellung in Ansicht und Vorgaben: Abdunkelung in Prozent
# (0 = aus) und Sekunden, die eine Beruehrung voll aufhellt. Einzige Quelle:
# panel_night() rechnet damit, /api/meta gibt sie dem Konfigurator, der sie in
# leeren Feldern anzeigt.
NACHT_STANDARD = {"nightDim": 0, "nightWake": 20, "nightClock": False, "nightClockBright": 40}

# Nacht-Uhr: nachts zeigt die Uhr-Seite nur die Uhrzeit, gedimmt auf Schwarz,
# und die Symbole der Gesten-Spalten (wie die Nachtanzeige der Loxone-Taster).
# Helligkeit der Ziffern und Symbole in Prozent, zusaetzlich zu "Nachts
# abdunkeln"; unter NACHT_UHR_HELL_MIN waere sie nicht mehr zu lesen.
NACHT_UHR_HELL_MIN = 5


def _clean_kachel_set(v):
    """Kachel-Set eines Profils (ui.tileSet): ein Name aus
    theme_colors.KACHEL_SETS, sonst None (= Standard, Farben aus der Grundfarbe)."""
    return v if isinstance(v, str) and v in theme_colors.KACHEL_SETS else None


def _clean_kachel_farbton(v):
    """Farbton des Kachel-Sets mit Rechnung (ui.tileHue): ganze Grad 0-359,
    sonst None (= Standard aus theme_colors.KACHEL_SETS)."""
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not 0 <= v < 360:
        return None
    return int(v)


def _clean_kachel_aktiv(v):
    """Aktive Kachel des Kachel-Sets mit Rechnung (ui.tileActive): ein Schluessel
    aus theme_colors.KACHEL_SETS["touch"]["aktiv"], sonst None (= Standard)."""
    keys = [a["key"] for a in theme_colors.KACHEL_SETS["touch"]["aktiv"]["auswahl"]]
    return v if v in keys else None


def _clean_scale(v):
    """Skalierungswert pruefen: "off" | "auto" | Zahl in [SCALE_MIN, SCALE_MAX]
    (auf zwei Stellen gerundet, deutsches Komma erlaubt). Ungueltiges ergibt
    None = nicht gesetzt. Zahlen ausserhalb werden an die Grenze gesetzt, wie
    die uebrigen Groessen in dieser Datei auch."""
    if isinstance(v, str):
        v = v.strip().lower()
        if v in ("off", "auto"):
            return v
        try:
            v = float(v.replace(",", "."))
        except ValueError:
            return None
    if isinstance(v, bool) or not isinstance(v, (int, float)) or v != v:   # v != v: NaN
        return None
    return round(max(SCALE_MIN, min(SCALE_MAX, float(v))), 2)


def _clean_kachelziel(v) -> int | None:
    """Zielgroesse einer Kachel (ui.tileSize, devices[name].tileTarget) als
    Zahl in CSS-Pixeln: Zahl oder Ziffernfolge in [KACHEL_ZIEL_MIN,
    KACHEL_ZIEL_MAX] (an die Grenze gesetzt, wie die uebrigen Groessen in
    dieser Datei), oder eine der alten Stufen "small" | "medium" | "large"
    (KACHEL_ZIEL). Ungueltiges ergibt None = nicht gesetzt."""
    if isinstance(v, str):
        v = v.strip().lower()
        if v in KACHEL_ZIEL:
            return KACHEL_ZIEL[v]
        if not v.isdigit():
            return None
        v = int(v)
    if isinstance(v, bool) or not isinstance(v, (int, float)) or v != v:   # v != v: NaN
        return None
    return int(round(max(KACHEL_ZIEL_MIN, min(KACHEL_ZIEL_MAX, float(v)))))


def _clean_pane_spalten(v) -> int | None:
    """Feste Breite des Widgets im automatischen Raster (ui.paneCols) in
    Kachelspalten, hochkant Kachelzeilen: ganze Zahl oder Ziffernfolge ab 1,
    hoechstens PANE_SPALTEN_MAX (an die Grenze gesetzt wie die uebrigen
    Groessen). 0, True/False und alles andere ergibt None = Automatik
    (PANE_ANTEIL), 0 ist zugleich der Standard (PANEL_STANDARD)."""
    if isinstance(v, str):
        v = v.strip()
        if not v.isdigit():
            return None
        v = int(v)
    if isinstance(v, bool) or not isinstance(v, (int, float)) or v != v or v < 1:   # v != v: NaN
        return None
    return int(min(PANE_SPALTEN_MAX, int(v)))


# Groesste Bildschirmkante in CSS-px, die der Server annimmt: fuer die Meldung
# eines Panels (_clean_screen) und fuer die im Profil gespeicherte Zielgroesse
# (_clean_zielgeraet) dieselbe Grenze, sonst passt eine gemeldete Groesse nicht
# in das Profil und der Abgleich unter Displays kann nie warnen.
BILDSCHIRM_PX_MAX = 20000


def _clean_zielgeraet(v) -> dict | None:
    """Zielgeraet eines Profils (profil.device): {"name": Geraetename, dazu
    optional "vw"/"vh" = Bildschirm in CSS-Pixeln, wie das Geraet ihn beim
    Waehlen gemeldet hat}. Ein blosser Name (str) wird zum dict. Ohne Namen
    None = kein Zielgeraet; eine unbrauchbare Groesse faellt still weg."""
    if isinstance(v, str):
        v = {"name": v}
    if not isinstance(v, dict):
        return None
    name = str(v.get("name") or "").strip()[:60]
    if not name:
        return None
    out = {"name": name}
    vw, vh = v.get("vw"), v.get("vh")
    if all(isinstance(x, (int, float)) and not isinstance(x, bool) and x == x and 1 <= x <= BILDSCHIRM_PX_MAX
           for x in (vw, vh)):
        out["vw"], out["vh"] = int(vw), int(vh)
    return out


def _kachel_breite(v) -> int | None:
    """Breite einer Kachel in Spalten (tiles[uuid].w): 1 oder 2, auch als
    Ziffer; True/False und alles andere ergibt None = nach Typ."""
    if isinstance(v, bool):
        return None
    if isinstance(v, str) and v.strip().isdigit():
        v = int(v.strip())
    return int(v) if isinstance(v, (int, float)) and int(v) == v and int(v) in KACHEL_BREITEN else None


def _kachel_vorschlag(screen) -> int | None:
    """Vorschlag fuer die Zielkachel eines Geraets aus seiner Bildschirmmeldung
    (_clean_screen: vw, vh in CSS-Pixeln, dpr Pixeldichte). Mit Pixeldichte ab
    1,5 ist es ein Tablet in der Hand, dort passt der Standard. Ohne
    Pixeldichte (Monitor, Wanddisplay, Linux-Panel) sagt die Groesse in
    CSS-Pixeln, wie weit weg der Schirm haengt: ein Fuenftel der kuerzeren
    Seite, auf Zehner gerundet, nicht unter dem Standard und nicht ueber 300
    px (FullHD 220, 2560 x 1600 300). Nur ein Vorschlag fuer den Konfigurator
    (Displays), nichts davon steuert den Server."""
    if not isinstance(screen, dict) or not screen.get("vw") or not screen.get("vh"):
        return None
    if (screen.get("dpr") or 1) >= 1.5:
        return KACHEL_ZIEL_STANDARD
    kurz = min(screen["vw"], screen["vh"])
    return int(max(KACHEL_ZIEL_STANDARD, min(300, round(kurz / 5 / 10) * 10)))


def _clean_screen(d) -> dict:
    """Bildschirmmeldung eines Panels ({t:"screen"}) auf plausible Zahlen
    beschraenken. Dient nur der Anzeige unter Settings -> Panels; nichts davon
    steuert den Server."""
    if not isinstance(d, dict):
        return {}

    def zahl(k, lo, hi, stellen=0):
        v = d.get(k)
        if isinstance(v, bool) or not isinstance(v, (int, float)) or v != v:
            return None
        v = max(lo, min(hi, float(v)))
        return round(v, stellen) if stellen else int(round(v))

    px = BILDSCHIRM_PX_MAX
    out = {"vw": zahl("vw", 1, px), "vh": zahl("vh", 1, px),           # sichtbare Flaeche (CSS-px)
           "sw": zahl("sw", 1, px), "sh": zahl("sh", 1, px),           # Bildschirm laut Geraet (CSS-px)
           "dpr": zahl("dpr", 0.25, 8, 2),                              # Pixeldichte
           "bw": zahl("bw", 1, px), "bh": zahl("bh", 1, px),           # Kasten der Visu (ungeskaliert)
           "k": zahl("k", 0.1, 10, 3),                                  # wirksamer Faktor
           "rc": zahl("rc", 1, 50), "rr": zahl("rr", 1, 50)}            # Raster der Kachelansicht
    return {k: v for k, v in out.items() if v is not None}


def _clean_camera(v: str) -> str:
    """Kamera-Widget pruefen: "camera:<uuid>" oder "camera:<uuid>|<uuid>,<uuid>,..."
    Hinter dem senkrechten Strich stehen frei gewaehlte Werte (wie "status:"),
    die das Panel unter dem Kamerabild zeigt - auf einem Tablet bleibt dort
    sonst die halbe Pane leer. Die Liste wird je Eintrag getrimmt und auf
    SV_STATUS_MAX begrenzt; ohne Eintraege faellt der Strich weg. "" = ungueltig."""
    kopf = "camera:"
    if not (isinstance(v, str) and v.startswith(kopf) and len(v) > len(kopf)):
        return ""
    rest = v[len(kopf):]
    cam, _, werte = rest.partition("|")
    cam = cam.strip()
    if not cam:
        return ""
    uu = [x.strip() for x in werte.split(",") if x.strip()][:SV_STATUS_MAX]
    return kopf + cam + ("|" + ",".join(uu) if uu else "")


def _clean_tabpane(v) -> str:
    """Split-Pane eines Tabs pruefen: "weather" | "calendar" | "player:<uuid>"
    | "energy:<uuid>" | "camera:<uuid>[|<uuid>,...]" (Kamera, dahinter optional
    Werte unter dem Bild, _clean_camera) | "chart:<uuid>,<uuid>,..." (ein oder
    mehrere Verlaufs-Bausteine mit Aufzeichnung, gestapelt) | "status:<uuid>,..."
    (frei gewaehlte Werte, wie auf der Uhr-Seite) | "header" bzw.
    "header:<uuid>,..." (Kopfzeile: Uhr, Wetter und bis zu SV_STATUS_MAX Werte
    in EINER Zeile ueber dem Kachelraster statt einer Pane daneben; ohne
    Bausteine nur Uhr und Wetter). "" heisst "kein Widget".

    Derselbe Widget-Katalog wie die Uhr-Seite (_clean_svpane), damit Zusatz und
    Screensaver dieselben Inhalte anbieten; nur die Kopfzeile gibt es dort
    nicht (die Uhr-Seite IST schon Uhr und Wetter). Prueft OHNE strip() am
    Gesamtwert; nur die Listen werden (wie dort) je Eintrag getrimmt und
    begrenzt."""
    if v in ("weather", "calendar", "header"):
        return v
    if isinstance(v, str):
        if v.startswith("camera:"):
            return _clean_camera(v)
        for kopf in ("player:", "energy:"):
            if v.startswith(kopf) and len(v) > len(kopf):
                return v
        for kopf in ("chart:", "status:"):   # mehrere Bausteine, komma-getrennt (Verlauf/Werte)
            if v.startswith(kopf):
                uu = [x.strip() for x in v[len(kopf):].split(",") if x.strip()][:SV_STATUS_MAX]
                if uu:
                    return kopf + ",".join(uu)
        if v.startswith("header:"):          # Kopfzeile mit Werten; ohne Werte nur Uhr und Wetter
            uu = [x.strip() for x in v[len("header:"):].split(",") if x.strip()][:SV_STATUS_MAX]
            return "header:" + ",".join(uu) if uu else "header"
    return ""


def _clean_widget_tab(v) -> str:
    """Widget einer freien Seite (pickTabs[].widget, Vollbild-Tab): dieselbe
    Grammatik wie eine Tab-Pane, nur die Kopfzeile nicht - sie ist eine Zeile
    UEBER Kacheln, als ganze Seite bliebe darunter nichts. Dazu die
    Hausuebersicht (HAUS_TAB): eine freie Seite kann sie sein, statt dass die
    Ansicht den Tab "haus" in der klassischen Leiste braucht."""
    if v == HAUS_TAB:
        return v
    w = _clean_tabpane(v)
    return "" if w == "header" or w.startswith("header:") else w


def _clean_werteleiste(v) -> list:
    """Seiten, deren Anzeige-Bausteine als Werteleiste ueber dem Raster stehen
    statt als Kacheln (ui.valueBar): Tab-Kennungen wie in "tabs" - auch
    "raeume" und "kategorien" fuer die Raum- und Kategorie-Seiten darunter -,
    nur gueltige, jede einmal, in der Reihenfolge der Eingabe. Alles andere
    ergibt [] = keine Leiste."""
    if not isinstance(v, list):
        return []
    out: list = []
    for t in v:
        if isinstance(t, str) and _is_tab(t) and t not in out:
            out.append(t)
    return out


def _clean_kennung(v) -> str:
    """UUID eines Bausteins oder Raums aus einer Einstellung: getrimmt, hoechstens
    60 Zeichen, sonst "". Ob es ihn gibt, entscheidet erst die Struktur - wie bei
    presence und hide bleibt die Kennung, auch wenn der Miniserver gerade fehlt."""
    return v.strip()[:60] if isinstance(v, str) else ""


def _clean_raum_verlassen(v) -> dict:
    """Taster je Raum fuer "Raum verlassen" (Vorgaben, ui.raumVerlassen):
    {Raum-UUID: Taster-UUID}, nur Paare mit beiden Kennungen."""
    if not isinstance(v, dict):
        return {}
    out = {}
    for ru, tu in v.items():
        ru, tu = _clean_kennung(ru), _clean_kennung(tu)
        if ru and tu:
            out[ru] = tu
    return out


def _clean_licht_start(v) -> dict | None:
    """Stimmung beim Einschalten eines Geraets (devices[name].lichtStart):
    {lc: Lichtsteuerung, mood: Stimmungs-ID aus ihrer moodList}, sonst None."""
    if not isinstance(v, dict) or isinstance(v.get("mood"), bool):
        return None
    lc = _clean_kennung(v.get("lc"))
    try:
        mood = int(v.get("mood"))
    except (TypeError, ValueError):
        return None
    return {"lc": lc, "mood": mood} if lc and mood >= 0 else None


def _clean_svpane(v) -> str:
    """Rechte Spalte der Uhr-Seite (Screensaver) pruefen und normieren.

    Erlaubt: "off" (keine zweite Spalte), "calendar", "weather",
    "player:<zone>", "energy:<uuid>", "camera:<uuid>", "chart:<uuid>,..." (ein
    oder mehrere Verlaufs-Bausteine, gestapelt) und "status:<uuid>,<uuid>,...".
    Alles andere ergibt "" — das ist die Automatik: Termine, wenn welche
    anstehen, sonst die Wetter-Details. Unbekannte Werte wandern damit auf
    die Automatik statt eine leere Spalte zu erzeugen."""
    if not isinstance(v, str):
        return ""
    v = v.strip()
    if v in ("off", "calendar", "weather"):
        return v
    if v.startswith("camera:"):
        return _clean_camera(v)
    for kopf in ("player:", "energy:"):
        if v.startswith(kopf) and len(v) > len(kopf):
            return v
    for kopf in ("chart:", "status:"):   # mehrere Bausteine, komma-getrennt (Verlauf/Werte)
        if v.startswith(kopf):
            uu = [x.strip() for x in v[len(kopf):].split(",") if x.strip()][:SV_STATUS_MAX]
            if uu:
                return kopf + ",".join(uu)
    return ""


# Loxone-Icon-Bibliothek: SVGs des LoxBerry-Plugins "loxoneicons", read-only in
# den Container gemountet (docker-compose). Fehlt der Mount/das Plugin, ist der
# Ordner leer -> die Icon-Quelle erscheint gar nicht. Ueber Env ueberschreibbar.
LOXLIB_DIR = os.environ.get("LOXPANEL_LOXLIB_DIR", "/app/loxone-icons/filled")

_LOXLIB_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,79}\.svg$")


def _loxlib_names() -> list:
    """Dateinamen der Loxone-Bibliothek (flache .svg im gemounteten Ordner)."""
    try:
        return sorted(fn for fn in os.listdir(LOXLIB_DIR)
                      if _LOXLIB_NAME.match(fn) and ".." not in fn)
    except OSError:
        return []


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
    if s == "loxlib" and isinstance(ic.get("name"), str) and _LOXLIB_NAME.match(ic["name"]) \
            and ".." not in ic["name"]:
        return {"src": "loxlib", "name": ic["name"]}
    if s == "google" and isinstance(ic.get("name"), str) and re.match(r"^[a-z0-9_]{1,48}$", ic["name"]):
        return {"src": "google", "name": ic["name"]}
    if s == "custom" and isinstance(ic.get("file"), str) and re.match(r"^[A-Za-z0-9._-]{1,80}$", ic["file"]):
        return {"src": "custom", "file": ic["file"]}
    return None


def _sanitize_overlay(ov) -> dict:
    """Overlay-Config aus der Config-Seite auf erlaubte Werte eindampfen."""
    if not isinstance(ov, dict):
        return {}
    out: dict = {}
    if ov.get("mode") in ("both", "border", "fill"):
        out["mode"] = ov["mode"]
    for k in ("fill", "bord", "ibord", "ring", "rtrk"):
        if isinstance(ov.get(k), (int, float)):
            out[k] = max(0, min(100, int(ov[k])))
    for k in ("bw", "ibw"):
        if isinstance(ov.get(k), (int, float)):
            out[k] = max(1, min(4, int(ov[k])))
    if isinstance(ov.get("rw"), (int, float)):
        out["rw"] = max(1, min(12, int(ov["rw"])))
    return out


def _config() -> dict:
    return _ms_zugang()[0]


def _ms_zugang() -> tuple[dict, str]:
    """Wirksamer Miniserver-Zugang und seine Quelle: "datei", wenn der
    Abschnitt miniserver der loxpanel.cfg einen Host hat (dann gilt er ganz),
    sonst "umgebung" (LOXPANEL_MS_*), sonst ({}, ""). Verbinden (_config),
    Anzeige (/api/settings) und Speichern (api_settings_ms) lesen ihn hier."""
    # Reihenfolge: geschriebene loxpanel.cfg (Settings-Seite) -> Env (Docker) -> keiner.
    base = Path(__file__).resolve().parent.parent / "config"
    f = base / "loxpanel.cfg"
    if f.is_file():
        try:
            cfg = json.loads(f.read_text(encoding="utf-8"))
        except ValueError:
            cfg = {}
        ms = cfg.get("miniserver") if isinstance(cfg, dict) else None
        if isinstance(ms, dict) and ms.get("host"):
            return ms, "datei"
    env = os.environ
    if env.get("LOXPANEL_MS_HOST"):
        try:   # leer oder kaputt: Standardport wie in den Sonden, statt beim Start abzustuerzen
            port = int(env.get("LOXPANEL_MS_PORT") or 443)
        except ValueError:
            port = 443
        return {
            "host": env["LOXPANEL_MS_HOST"],
            "user": env.get("LOXPANEL_MS_USER", ""),
            "pass": env.get("LOXPANEL_MS_PASS", ""),
            "port": port if 1 <= port <= 65535 else 443,
            "verify_tls": env.get("LOXPANEL_MS_VERIFY_TLS", "false").lower() in ("1", "true", "yes"),
        }, "umgebung"
    # Die Vorlage loxpanel.cfg.example traegt nur einen Platzhalter-Zugang
    # (192.168.1.50, CHANGEME). Mit dem anzumelden waere sinnlos und deckte ein
    # fremdes Geraet unter dieser Adresse mit Fehlanmeldungen ein (die App
    # bringt die Vorlage mit). Ohne Zugang startet der Server trotzdem, wartet
    # in stream_task und zeigt den Panels den Einrichtungshinweis.
    return {}, ""


def _ms_sekunden(schluessel: str, standard: float) -> float:
    """Zeitwert in s aus dem Abschnitt miniserver der loxpanel.cfg. Fehlt er
    oder ist er keine Zahl > 0, gilt `standard` (ungueltig: mit Warnung)."""
    ms = _cfg_datei().get("miniserver")
    wert = ms.get(schluessel) if isinstance(ms, dict) else None
    if isinstance(wert, (int, float)) and not isinstance(wert, bool) and math.isfinite(wert) and wert > 0:
        return float(wert)
    if wert is not None:
        log.warning("loxpanel.cfg: miniserver.%s %r ungueltig, es gelten %s s",
                    schluessel, wert, standard)
    return float(standard)


def _ms_antwortfrist() -> float:
    """Sekunden, die der Miniserver fuer eine Antwort bekommt (loxpanel.cfg,
    miniserver.response_timeout), etwa auf die Anmeldung beim Pruefen eines
    neuen Zugangs, auf jeden Schritt der WebSocket-Anmeldung und auf
    keepalive. Ohne gueltigen Wert MS_CMD_TIMEOUT: So lange darf auch ein
    Befehl dauern, bevor er als gescheitert gilt - ein erreichbarer
    Miniserver beantwortet eine Anmeldung deutlich schneller, und laenger
    soll niemand vor "Verbinden & Speichern" warten."""
    return _ms_sekunden("response_timeout", MS_CMD_TIMEOUT)


def _ms_keepalive_abstand() -> float:
    """Sekunden zwischen zwei keepalive an den Miniserver-WebSocket
    (loxpanel.cfg, miniserver.keepalive_interval), Standard MS_KEEPALIVE."""
    return _ms_sekunden("keepalive_interval", MS_KEEPALIVE)


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
    except (ValueError, OSError):
        return {}
    return cfg if isinstance(cfg, dict) else {}


def _audiometa_config() -> dict:
    """Metadaten-Quelle Audioserver4Home/Sonn (REST /api/v1/zones, Port 7090).

    Aus loxpanel.cfg `audiometa`-Block: {"host": "10.0.0.55", "port": 7090,
    "enabled": true}. Sonns AudioZoneV2-Ausgaenge liefern ueber das Loxone-
    Protokoll KEINE Track-Metadaten; dieser Block fuellt Cover/Titel/Interpret
    per Namensabgleich aus der Sonn-API nach.
    """
    base = Path(__file__).resolve().parent.parent / "config"
    f = base / "loxpanel.cfg"
    if not f.is_file():
        f = base / "loxpanel.cfg.example"
    try:
        cfg = json.loads(f.read_text(encoding="utf-8")).get("audiometa", {})
    except (ValueError, OSError):
        return {}
    return cfg if isinstance(cfg, dict) else {}


def _audiometa_sekunden(am: dict, schluessel: str, standard: float) -> float:
    """Eine Zeit (s) des Audioserver-Ereignis-Clients aus loxpanel.cfg
    audiometa.<schluessel> (retry_interval, response_timeout). Ohne gueltigen
    Wert `standard` (AudioEventClient.NEU_VERSUCH_S bzw. PRUEF_ZEITLIMIT_S,
    begruendet in audioserver_events.py)."""
    wert = am.get(schluessel) if isinstance(am, dict) else None
    if isinstance(wert, (int, float)) and not isinstance(wert, bool) and math.isfinite(wert) and wert > 0:
        return float(wert)
    if wert is not None:
        log.warning("loxpanel.cfg: audiometa.%s %r ungueltig, es gelten %s s", schluessel, wert, standard)
    return float(standard)


def _intercom_config() -> dict:
    base = Path(__file__).resolve().parent.parent / "config"
    f = base / "loxpanel.cfg"
    if not f.is_file():
        f = base / "loxpanel.cfg.example"
    try:
        cfg = json.loads(f.read_text(encoding="utf-8")).get("intercom", {})
    except (ValueError, OSError):
        return {}
    for k, v in cfg.items():
        if isinstance(v, dict) and isinstance(v.get("url"), str):
            v["url"] = v["url"].strip()
        elif isinstance(v, str):
            cfg[k] = v.strip()
    return cfg


def _night_config() -> dict:
    """Nachtmodus-Block aus loxpanel.cfg `night`: {"control": "<uuid>"}. Der
    `active`-State dieses Bausteins schaltet den Nachtmodus. Leer = kein
    Ausloeser, dann entscheiden die Sonnenzeiten."""
    base = Path(__file__).resolve().parent.parent / "config"
    f = base / "loxpanel.cfg"
    if not f.is_file():
        f = base / "loxpanel.cfg.example"
    try:
        cfg = json.loads(f.read_text(encoding="utf-8")).get("night", {})
    except (ValueError, OSError):
        return {}
    return cfg if isinstance(cfg, dict) else {}


def _calendar_config() -> dict:
    """Kalender-/Wetter-Block aus loxpanel.cfg `calendar`:
    {"sources": [{"name": "Familie", "url": "...", "color": "#e0a24d"}, ...],
     "holiday_url": "...", "name": "Family", "colors": true, "sv_events": 3,
     "lat": 47.07, "lon": 15.44, "days": 14, "fore_days": 4}.
    Steuert die Front (Screensaver). Eine aeltere einzelne `ical_url` wird von
    front_info.calendar_sources() als erste Quelle mitgelesen."""
    base = Path(__file__).resolve().parent.parent / "config"
    f = base / "loxpanel.cfg"
    if not f.is_file():
        f = base / "loxpanel.cfg.example"
    try:
        cfg = json.loads(f.read_text(encoding="utf-8")).get("calendar", {})
    except (ValueError, OSError):
        return {}
    return cfg if isinstance(cfg, dict) else {}


DEFAULT_THEME = {"states": {"active": "#e0a24d", "good": "#52b881",
                            "warn": "#d6a24a", "crit": "#e2695f"}}


def load_theme() -> dict:
    # Groessen nur, wenn eingestellt: sonst gilt GROESSEN_STANDARD des
    # Kachel-Aufbaus, und der Konfigurator zeigt ein leeres Feld
    theme = {"states": dict(DEFAULT_THEME["states"]), "categories": {},
             "ui": {"tabs": ["favoriten", "zentral", "raeume", "kategorien"], "font": ""}}
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


def load_devices() -> dict:
    """Geraete-Automatik aus config/panels.json (`devices`): pro physischem
    Panel (Schluessel = Agent-Name) eine Zuordnung Betriebsmodus -> Panel-Profil.
    Loxone schickt per virtuellem Ausgang nur den Modusnamen an /api/mode; der
    Server schaltet dann jedes Panel mit passender Zuordnung auf sein Profil um.
    """
    f = Path(__file__).resolve().parent.parent / "config" / "panels.json"
    if f.is_file():
        try:
            d = json.loads(f.read_text(encoding="utf-8")).get("devices")
            if isinstance(d, dict):
                return d
        except ValueError:
            pass
    return {}


# Schluessel mit Kennwoertern: Miniserver und Kamera ("pass"), Display-Treiber
# ("password"). /api/settings gibt sie nie heraus, das Backup auch nicht,
# /api/meta nennt beim Display nur hasPass (_devices_export).
_SECRET_KEYS = {"pass", "password"}


def _cfg_datei() -> dict:
    """Nur die geschriebene loxpanel.cfg, ohne Rueckfall auf das Beispiel: Das
    traegt ein Platzhalter-Kennwort, das kein Einspielen uebernehmen darf."""
    try:
        d = json.loads(CFG_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return d if isinstance(d, dict) else {}


# ---- Sanitizer: was beim Speichern einer Ansicht, eines Geraets und der
# Vorgaben bleibt. Statisch, App haelt sie als staticmethod-Aliase.

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
        # Raum-Panel: welche Kategorien des Raums als untere Tabs dienen
        # (max 4). Leer/fehlt = automatisch (erste 4 im Raum).
        rc = [str(x) for x in (p.get("roomCats") or []) if isinstance(x, str)][:4]
        if rc:
            e["roomCats"] = rc
        hide = [str(x) for x in (p.get("hide") or []) if isinstance(x, str)]
        if hide:
            e["hide"] = hide           # einzeln ausgeblendete Kacheln (panelweit)
        # Zielgeraet, fuer das das Profil gemacht ist (Displays warnt bei
        # Abweichung); fehlt = keines
        ziel = _clean_zielgeraet(p.get("device"))
        if ziel:
            e["device"] = ziel
        # Freie Auswahl (Tab "auswahl"): handverlesene Bausteine in
        # Klickreihenfolge. Hier nur Form pruefen - ob die UUIDs existieren,
        # entscheidet _panel_export gegen self.controls, wie bei "hide".
        picks = [str(x) for x in (p.get("picks") or []) if isinstance(x, str)][:60]
        if picks:
            e["picks"] = picks
        pname = str(p.get("pickName") or "").strip()[:40]
        if pname:
            e["pickName"] = pname
        # Bis zu 4 freie Seiten [{name, picks}] - Form pruefen (Existenz der
        # UUIDs entscheidet _panel_export gegen self.controls, wie bei picks).
        pts = p.get("pickTabs")
        if isinstance(pts, list) and pts:
            cpt = []
            for it in pts[:PICK_TABS_MAX]:
                if not isinstance(it, dict):
                    continue
                ps = [str(x) for x in (it.get("picks") or []) if isinstance(x, str)][:60]
                nm = str(it.get("name") or "").strip()[:40]
                ic = str(it.get("icon") or "").strip()[:200]
                # Nur erlaubte Icon-Formen behalten: interne Endpunkte oder
                # ein Loxone-Icon-Pfad. Alles andere (z. B. externe URL) raus.
                if ic and not (ic.startswith("/icon?") or ic.startswith("/loxlib?")
                               or ic.endswith(".svg") or ic.endswith(".png")):
                    ic = ""
                # Widget-Seite statt Kacheln (Wetter/Kalender/Energie/Kamera/
                # Verlauf/Werte/Audio) - Form pruefen wie eine Tab-Pane,
                # nur die Kopfzeile nicht (_clean_widget_tab).
                wdg = _clean_widget_tab(it.get("widget"))
                # Seiten-Editor (Punkt 10): Reihenfolge und Groesse je
                # Baustein, und ob die Visu die Seite nach Raum gruppiert
                ps, lay = _layout_mit_picks(_seiten_layout(it.get("layout")), ps)
                if ps or nm or ic or wdg:
                    entry = {"name": nm or "Auswahl", "picks": ps}
                    if ic:
                        entry["icon"] = ic
                    if wdg:
                        entry["widget"] = wdg
                    if lay:
                        entry["layout"] = lay
                    if it.get("byRoom") is False:
                        entry["byRoom"] = False
                    cpt.append(entry)
            if cpt:
                e["pickTabs"] = cpt
        ui = p.get("ui") or {}
        # Groessen genauso klemmen wie der globale Pfad (_sanitize_theme_ui)
        # und wie die Nachbarfelder unten - sonst nimmt der Panel-Override
        # jeden Wert an, waehrend die globale Einstellung auf 8..80 begrenzt
        # ist.
        cui = {k: max(8, min(80, int(ui[k]))) for k in ("iconSize", "nameSize", "subSize", "roomSize", "bigSize")
               if isinstance(ui.get(k), (int, float))}
        if ui.get("font"):
            cui["font"] = str(ui["font"])[:120]
        if isinstance(ui.get("nudgeX"), (int, float)):
            cui["nudgeX"] = max(-40, min(40, ui["nudgeX"]))  # horiz. Versatz px
        if isinstance(ui.get("dpmsOff"), (int, float)):
            cui["dpmsOff"] = max(0, min(3600, int(ui["dpmsOff"])))  # Display aus nach Sek.
        if isinstance(ui.get("reloadHours"), (int, float)):
            cui["reloadHours"] = max(0, min(168, float(ui["reloadHours"])))  # Auto-Neustart Std.
        if isinstance(ui.get("nightDim"), (int, float)):
            cui["nightDim"] = max(0, min(90, int(ui["nightDim"])))    # Nachts abdunkeln in %
        if isinstance(ui.get("nightWake"), (int, float)):
            cui["nightWake"] = max(0, min(300, int(ui["nightWake"])))  # Aufhellen bei Beruehrung, Sek.
        if isinstance(ui.get("nightClock"), bool):
            cui["nightClock"] = ui["nightClock"]   # Nacht-Uhr an/aus; fehlt = wie Vorgaben
        if isinstance(ui.get("nightClockBright"), (int, float)) and not isinstance(ui["nightClockBright"], bool):
            cui["nightClockBright"] = max(NACHT_UHR_HELL_MIN, min(100, int(ui["nightClockBright"])))   # Helligkeit %
        if isinstance(ui.get("pinMerken"), (int, float)) and \
                _pin_merken(ui["pinMerken"]) != PIN_MERKEN_STANDARD:
            cui["pinMerken"] = _pin_merken(ui["pinMerken"])   # PIN merken, Sek.; fehlt = Standard
        if ui.get("cols") in (2, 3):
            cui["cols"] = int(ui["cols"])   # Spalten: 2 oder 3
        if ui.get("rows") in (2, 3):
            cui["rows"] = int(ui["rows"])   # Zeilen: 2 oder 3 (2x3 / 3x3)
        if ui.get("fill"):
            cui["fill"] = True              # Visu fuellt grosse Screens (quadratische Kacheln)
        if ui.get("split") is False:
            cui["split"] = False            # Split-Screen aus (4"-Panel: nur Visu)
        if ui.get("catFilter") is True:
            cui["catFilter"] = True         # untere Leiste filtert statt zu springen
        if isinstance(ui.get("gesten"), bool):
            cui["gesten"] = ui["gesten"]    # Gesten an/aus; fehlt = wie Vorgaben
        if _clean_kennung(ui.get("gestenRaum")):
            cui["gestenRaum"] = _clean_kennung(ui["gestenRaum"])   # Raum der Gesten ausserhalb von Raumseiten
        if isinstance(ui.get("gestenHinweis"), bool):
            cui["gestenHinweis"] = ui["gestenHinweis"]   # Hinweis-Symbol an/aus; fehlt = wie Vorgaben
        if ui.get("tileLayout") == "classic":
            cui["tileLayout"] = "classic"   # bisheriger Kachel-Aufbau; fehlt = neuer
        if ui.get("hausAufbau") in HAUS_AUFBAUTEN and ui["hausAufbau"] != HAUS_AUFBAU_STANDARD:
            cui["hausAufbau"] = ui["hausAufbau"]   # Aufbau der Hausseite; fehlt = HAUS_AUFBAU_STANDARD
        _ks = _clean_kachel_set(ui.get("tileSet"))
        if _ks:
            cui["tileSet"] = _ks            # Kachel-Set (fertiger Look); fehlt = Farben aus der Grundfarbe
        _kh = _clean_kachel_farbton(ui.get("tileHue"))
        if _kh is not None and _kh != PANEL_STANDARD[("ui", "tileHue")]:
            cui["tileHue"] = _kh            # Farbton des Sets mit Rechnung (touch); fehlt = Standard
        _ka = _clean_kachel_aktiv(ui.get("tileActive"))
        if _ka and _ka != PANEL_STANDARD[("ui", "tileActive")]:
            cui["tileActive"] = _ka         # aktive Kachel hell oder dunkel; fehlt = Standard
        if ui.get("grid") == "auto":
            cui["grid"] = "auto"            # Raster rechnet die Visu (Tablet), cols/rows gelten dann nicht
        _tz = _clean_kachelziel(ui.get("tileSize"))
        if _tz is not None and _tz != KACHEL_ZIEL_STANDARD:
            cui["tileSize"] = _tz           # Zielkachel px im automatischen Raster; fehlt = Standard
        _ps = _clean_pane_spalten(ui.get("paneCols"))
        if _ps is not None:
            cui["paneCols"] = _ps           # Widget-Breite in Kachelspalten (automatisches Raster); fehlt = Automatik
        if isinstance(ui.get("player"), str) and ui.get("player"):
            cui["player"] = ui["player"]    # Split-Layout: AudioZone-UUID fuer den festen Player
        if isinstance(ui.get("panes"), dict):
            # Gespeichert wird der normierte Wert (getrimmte, begrenzte
            # Listen), nicht die Eingabe - s. _panel_export.
            pn = {str(k): _clean_tabpane(v) for k, v in ui["panes"].items()
                  if isinstance(k, str) and _is_tab(k) and _clean_tabpane(v)}
            if pn:
                cui["panes"] = pn           # Widget je Tab: Pane 2 oder Kopfzeile ("header")
        _vb = _clean_werteleiste(ui.get("valueBar"))
        if _vb:
            cui["valueBar"] = _vb           # Seiten, deren Anzeige-Bausteine als Werteleiste stehen
        _sp = _clean_svpane(ui.get("svPane"))
        if _sp:
            cui["svPane"] = _sp             # rechte Spalte der Uhr-Seite (Screensaver)
        _sc = _clean_scale(ui.get("scale"))
        if _sc is not None:
            cui["scale"] = _sc              # Skalierung: off/auto/Faktor; fehlt = wie global
        if _color_ok(ui.get("textColor")):
            cui["textColor"] = ui["textColor"].strip()   # globale Schriftfarbe (Name)
        if _color_ok(ui.get("baseColor")):
            # Grundfarbe des Panel-Themes. Nur uebernehmen, wenn sich daraus
            # ueberhaupt ein tragfaehiger Satz bauen laesst - sonst stuende
            # eine Farbe in der Konfiguration, die das Panel ignoriert.
            _base = ui["baseColor"].strip()
            if theme_colors.derive(_base):
                cui["baseColor"] = _base
        if ui.get("bold"):
            cui["bold"] = True                            # Kachel-Namen fett
        lang = _clean_lang(ui.get("lang"))
        if lang:
            cui["lang"] = lang                            # Panel-Sprache (Datum/Uhr, i18n)
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
                if ov.get("chart") in STAT_RANGES:
                    e2["chart"] = ov["chart"]   # Mini-Verlauf in der Kachel, Wert = Zeitraum
                    if ov.get("chartStyle") in STAT_TILE_STYLES and ov["chartStyle"] != "trend":
                        e2["chartStyle"] = ov["chartStyle"]   # Tagesmuster / Tagesspanne
                if _kachel_breite(ov.get("w")) is not None:
                    e2["w"] = _kachel_breite(ov["w"])   # Breite in Spalten (1 | 2); fehlt = nach Typ
                if e2:
                    ct[cu] = e2
            if ct:
                e["tiles"] = ct
        out[pid] = e
    return out


def _panels_verworfen(roh: dict, sauber: dict, namen: dict | None = None) -> list[str]:
    """Was _sanitize_panels nicht uebernommen hat, als lesbare Pfade
    ("<Panel>: ui.cols", "<Panel>: tabs: foo"), damit der Konfigurator es
    meldet statt es still zu verlieren. Gemeldet wird nur, was einen Inhalt
    hatte: leere Werte (None, False, "", [], {}) nicht, begrenzte oder
    gekuerzte Werte (Groesse 100 -> 80, Titel auf 40 Zeichen) auch nicht -
    die kommen ja an. Standardwerte, die bewusst nicht gespeichert werden,
    stehen in PANEL_STANDARD. namen: UUID -> Bausteinname fuer lesbare
    Pfade (Kachel-Einstellungen stehen unter der UUID)."""
    namen = namen or {}

    def leer(v) -> bool:
        return v is None or v is False or (isinstance(v, str) and not v.strip()) \
            or (isinstance(v, (list, dict)) and not any(not leer(x) for x in
                                                        (v.values() if isinstance(v, dict) else v)))

    def standard(pfad: tuple, v) -> bool:
        for muster, wert in PANEL_STANDARD.items():
            if len(muster) == len(pfad) and all(m in ("*", p) for m, p in zip(muster, pfad)) \
                    and (v == wert or (isinstance(wert, tuple) and v in wert)):
                return True
        return False

    def kurz(xs: list) -> str:
        return ", ".join(str(x) for x in xs[:3]) + (f" … (+{len(xs) - 3})" if len(xs) > 3 else "")

    out: list[str] = []

    def vergleich(r, s, pfad: tuple, name: str):
        if isinstance(r, dict):
            for k, v in r.items():
                if leer(v) or standard(pfad + (str(k),), v):
                    continue
                p = pfad + (str(k),)
                if isinstance(s, dict) and k in s:
                    vergleich(v, s[k], p, name)
                elif isinstance(v, (dict, list)):
                    # ganz weggefallen (z. B. ui nur mit Unbekanntem): die
                    # einzelnen Angaben darin nennen
                    vergleich(v, {} if isinstance(v, dict) else [], p, name)
                else:
                    out.append(f"{name}: {'.'.join(namen.get(x, x) for x in p)}")
        elif isinstance(r, list) and isinstance(s, list):
            werte = [x for x in r if not leer(x)]
            if all(isinstance(x, (str, int, float)) for x in werte):
                # als Menge: "x not in s" auf der Liste waere quadratisch
                # (200.000 ausgeblendete Eintraege -> Minuten)
                da = {y for y in s if isinstance(y, (str, int, float))}
                fehlt = [x for x in werte if x not in da]
                if fehlt:
                    out.append(f"{name}: {'.'.join(namen.get(x, x) for x in pfad)}: "
                               f"{kurz([namen.get(x, x) for x in fehlt])}")
            elif len(s) < len(werte):
                out.append(f"{name}: {'.'.join(namen.get(x, x) for x in pfad)}: "
                           f"{len(werte) - len(s)} von {len(werte)}")
            else:
                for i, (x, y) in enumerate(zip(werte, s)):
                    vergleich(x, y, pfad + (str(i + 1),), name)

    for pid, p in (roh or {}).items():
        if leer(p):
            continue
        if pid not in sauber:
            out.append(f"Ansicht „{pid}“")
        else:
            titel = str(p.get("title") or "").strip() if isinstance(p, dict) else ""
            vergleich(p, sauber[pid], (), titel or pid)
    return out


def _panels_doc(panels: dict, devices: dict) -> dict:
    """Inhalt von config/panels.json, wie _persist_panels_file ihn schreibt."""
    doc = {"_comment": "Von der LoxPanel-Konfigurationsseite (/config bzw. "
                       "/settings) verwaltet. Jedes Panel oeffnet die Visu mit "
                       "?panel=<id>. rooms/cats leer = alle sichtbar. "
                       "`devices` bildet Betriebsmodus -> Profil je Panel ab.",
           "panels": panels}
    if devices:
        doc["devices"] = devices
    return doc


def _sanitize_devices(devices: dict, panel_ids: set) -> dict:
    """Geraete-Automatik validieren: Schluessel = Agent-Name; je Panel `auto`
    (bool) + `modes` = {Modusname -> Profil-Id}, dazu Display-Treiber,
    Skalierung, Praesenzmelder (`presence` = Control-UUID), "Display aus nach"
    (`dpmsOff`, Sek.) und Nacht (`nightDim` %, `nightWake` Sek.; Einrichtung
    Schritt 4 und 4b: vor Ansicht und Vorgaben) und die
    zugeordnete Ansicht (`panel`, Einrichtung Schritt 2: die eine Stelle,
    die sagt, was das Geraet zeigt). Nur existierende Profile werden
    uebernommen; leere Geraete fallen weg."""
    out: dict = {}
    if not isinstance(devices, dict):
        return out
    for name, cfg in devices.items():
        if not isinstance(name, str) or not name.strip() or not isinstance(cfg, dict):
            continue
        panel = cfg.get("panel")
        panel = panel.strip() if isinstance(panel, str) and panel.strip() in panel_ids else ""
        modes = {}
        for mode, prof in (cfg.get("modes") or {}).items():
            if not isinstance(mode, str) or not isinstance(prof, str):
                continue
            mode = mode.strip()[:40]
            prof = prof.strip()
            if mode and prof and prof in panel_ids:
                modes[mode] = prof
        display = _sanitize_display(cfg.get("display"))
        # Skalierung je Geraet (auch "off", um ein "auto" des Profils zu
        # uebersteuern). Ein Geraet, das NUR sie traegt, muss bleiben -
        # bisher fiel alles ohne Modi und Display-Treiber still weg.
        scale = _clean_scale(cfg.get("scale"))
        # Zielkachel des automatischen Rasters je Geraet (effective_grid_auto)
        ziel = _clean_kachelziel(cfg.get("tileTarget"))
        # Praesenzmelder: solange sein Baustein jemanden meldet, bleibt das
        # Display an (_presence_rebuild). Ob es ihn gibt, entscheidet erst
        # die Struktur - wie bei "hide" bleibt die Kennung erhalten, auch
        # wenn der Miniserver gerade nicht verbunden ist.
        presence = cfg.get("presence")
        presence = presence.strip()[:60] if isinstance(presence, str) else ""
        # Stimmung beim Einschalten (Gesten): was angeht, wenn im Raum alles
        # aus ist, und zu welcher Lichtsteuerung das Geraet gehoert
        licht_start = _clean_licht_start(cfg.get("lichtStart"))
        # Display aus nach Sek. und Nacht (Abdunkeln %, Aufhellen Sek.) am Geraet
        # (panel_dpms, panel_night: Geraet vor Ansicht vor Vorgaben)
        def _zahl(key, lo, hi):
            v = cfg.get(key)
            return max(lo, min(hi, int(v))) if isinstance(v, (int, float)) and not isinstance(v, bool) else None
        dpms, dim, wake = _zahl("dpmsOff", 0, 3600), _zahl("nightDim", 0, 90), _zahl("nightWake", 0, 300)
        if not modes and not display and scale is None and ziel is None and not presence \
                and not licht_start and not panel and dpms is None and dim is None and wake is None:
            continue
        entry = {"auto": bool(cfg.get("auto", True)), "modes": modes}
        if panel:
            entry["panel"] = panel
        if display:
            entry["display"] = display
        if scale is not None:
            entry["scale"] = scale
        if ziel is not None:
            entry["tileTarget"] = ziel
        if presence:
            entry["presence"] = presence
        if licht_start:
            entry["lichtStart"] = licht_start
        if dpms is not None:
            entry["dpmsOff"] = dpms
        if dim is not None:
            entry["nightDim"] = dim
        if wake is not None:
            entry["nightWake"] = wake
        out[name.strip()[:60]] = entry
    return out


def _sanitize_display(d) -> dict | None:
    """Display-Treiber eines Geraets: {driver: fully|wallpanel, host, port,
    password}. Ohne gueltigen Treiber oder Host -> None."""
    if not isinstance(d, dict):
        return None
    drv = str(d.get("driver") or "").strip().lower()
    if drv not in DISPLAY_DRIVERS:
        return None
    host = str(d.get("host") or "").strip()[:100]
    if not host:
        return None
    try:
        port = int(d.get("port") or DISPLAY_DRIVERS[drv])
    except (TypeError, ValueError):
        port = DISPLAY_DRIVERS[drv]
    return {"driver": drv, "host": host, "port": max(1, min(65535, port)),
            "password": str(d.get("password") or "")[:100]}


def _devices_export(devices: dict) -> dict:
    """Geraete fuer den Konfigurator (/api/meta, Antwort von POST
    /api/devices): das Display-Kennwort nur als hasPass, wie Miniserver
    und Kamera in /api/settings. Leer zurueck heisst es "unveraendert"
    (api_save_devices)."""
    out = {}
    for name, e in devices.items():
        if isinstance(e, dict) and isinstance(e.get("display"), dict):
            disp = {k: v for k, v in e["display"].items() if str(k).lower() not in _SECRET_KEYS}
            e = {**e, "display": {**disp, "hasPass": bool(e["display"].get("password"))}}
        out[name] = e
    return out


def _sanitize_theme_ui(ui: dict) -> dict:
    """Globale Darstellungs-ui (theme.json) validieren: nur bekannte Keys."""
    ui = ui or {}
    out: dict = {}
    for k in ("iconSize", "nameSize", "subSize", "roomSize", "bigSize"):
        if isinstance(ui.get(k), (int, float)):
            out[k] = max(8, min(80, int(ui[k])))
    if ui.get("font"):
        out["font"] = str(ui["font"])[:120]
    if _color_ok(ui.get("textColor")):
        out["textColor"] = ui["textColor"].strip()
    if _color_ok(ui.get("baseColor")) and theme_colors.derive(ui["baseColor"].strip()):
        out["baseColor"] = ui["baseColor"].strip()
    if ui.get("bold"):
        out["bold"] = True
    lang = _clean_lang(ui.get("lang"))
    if lang:
        out["lang"] = lang
    _sc = _clean_scale(ui.get("scale"))
    if _sc not in (None, "off"):
        out["scale"] = _sc          # Skalierung fuer alle Panels; "off" = Fehlen
    # Nacht, Display aus und Auto-Neustart fuer alle Panels (Vorgaben ->
    # Verhalten); panel_night(), panel_dpms() und panel_reload() nehmen sie,
    # solange das Profil keine eigenen setzt. Grenzen wie dort.
    if isinstance(ui.get("nightDim"), (int, float)):
        out["nightDim"] = max(0, min(90, int(ui["nightDim"])))
    if isinstance(ui.get("nightWake"), (int, float)):
        out["nightWake"] = max(0, min(300, int(ui["nightWake"])))
    if isinstance(ui.get("dpmsOff"), (int, float)):
        out["dpmsOff"] = max(0, min(3600, int(ui["dpmsOff"])))
    if isinstance(ui.get("reloadHours"), (int, float)):
        out["reloadHours"] = max(0, min(168, float(ui["reloadHours"])))
    # Nacht-Uhr fuer alle Panels (an/aus nur, wenn es vom Standard abweicht)
    # und ihre Helligkeit, Grenzen wie im Panel
    if isinstance(ui.get("nightClock"), bool) and ui["nightClock"] != NACHT_STANDARD["nightClock"]:
        out["nightClock"] = ui["nightClock"]
    if isinstance(ui.get("nightClockBright"), (int, float)) and not isinstance(ui["nightClockBright"], bool):
        out["nightClockBright"] = max(NACHT_UHR_HELL_MIN, min(100, int(ui["nightClockBright"])))
    # Gesten fuer alle Ansichten (eine Ansicht kann sie selbst an- oder
    # ausschalten); fehlt = GESTEN_STANDARD
    if isinstance(ui.get("gesten"), bool) and ui["gesten"] != GESTEN_STANDARD:
        out["gesten"] = ui["gesten"]
    # ... und ihr Hinweis-Symbol; fehlt = GESTEN_HINWEIS_STANDARD
    if isinstance(ui.get("gestenHinweis"), bool) and ui["gestenHinweis"] != GESTEN_HINWEIS_STANDARD:
        out["gestenHinweis"] = ui["gestenHinweis"]
    # Taster fuer "Haus aus" (Dreifachtipp) und je Raum fuer "Raum verlassen"
    # (Doppeltipp): die Logik dahinter steht in Loxone Config
    _ha = _clean_kennung(ui.get("hausAus"))
    if _ha:
        out["hausAus"] = _ha
    _rv = _clean_raum_verlassen(ui.get("raumVerlassen"))
    if _rv:
        out["raumVerlassen"] = _rv
    return out


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
