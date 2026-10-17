"""Panel-Theme aus EINER Grundfarbe herleiten.

Der Nutzer waehlt ein Farbfeld; daraus fallen saemtliche Panelfarben ab -
Hintergrund, Kachel, Leiste, Schrift, Zweitzeile, Icon- und Zustandsfarben.
Nichts davon wird geraten: jeder Wert wird gegen die Flaeche nachgerechnet,
auf der er spaeter wirklich steht, und `derive()` liefert None, wenn eine
Grundfarbe kein tragfaehiges Theme hergibt.

Massstaebe (WCAG 2.1):
  * Hauptschrift 7:1 (AAA) auf Hintergrund und Tableiste,
  * alles uebrige 4,5:1 (AA) auf Kachel, Leiste und getoenten Kacheln,
  * grafische Elemente wie die Ringe im Energiefluss 3:1 (1.4.11).

Zusaetzlich wird jedes Paar, das nebeneinander steht, unter Deuteranopie und
Protanopie simuliert. Farbton allein traegt naemlich nicht: auf hellem Grund
sind dunkles Bernstein und dunkles Rot fuer rot-gruen-blinde Augen dieselbe
Farbe. Darum laeuft "Stoerung" ueber die FORM - die Kachel kippt um und wird
gefuellt - und der Netz-Ring im Energiefluss bekommt seinen Farbton gesucht
statt gesetzt.

Nur Standardbibliothek, keine zusaetzliche Abhaengigkeit.
"""
from __future__ import annotations

import colorsys
import functools
import math
import re

# Schwellen
AAA = 7.0       # Hauptschrift
AA = 4.5        # Zweitzeile, Zustandsfarben
GRAFIK = 3.0    # Ringe, Linien (WCAG 1.4.11)
TRENNUNG = 40   # Mindestabstand zweier Farben nach Farbsehschwaeche-Simulation

_HEX = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")


def _rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _hex(rgb) -> str:
    return "#%02x%02x%02x" % tuple(max(0, min(255, round(c))) for c in rgb)


def _linear(c: float) -> float:
    c /= 255
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def luminanz(h: str) -> float:
    r, g, b = _rgb(h)
    return 0.2126 * _linear(r) + 0.7152 * _linear(g) + 0.0722 * _linear(b)


def kontrast(a: str, b: str) -> float:
    la, lb = luminanz(a), luminanz(b)
    hoch, tief = max(la, lb), min(la, lb)
    return (hoch + 0.05) / (tief + 0.05)


def ueber(vorn: str, hinten: str, deckung: float) -> str:
    """`vorn` mit der Deckung `deckung` ueber `hinten` legen."""
    f, h = _rgb(vorn), _rgb(hinten)
    return _hex([f[i] * deckung + h[i] * (1 - deckung) for i in range(3)])


def _hls(h: str):
    r, g, b = (c / 255 for c in _rgb(h))
    return colorsys.rgb_to_hls(r, g, b)


def _aus_hls(farbton: float, helligkeit: float, saettigung: float) -> str:
    helligkeit = max(0.0, min(1.0, helligkeit))
    return _hex([c * 255 for c in colorsys.hls_to_rgb(farbton, helligkeit, saettigung)])


def _simuliere(h: str, art: str) -> str:
    """Farbsehschwaeche nach Vienot, Brettel & Mollon (1999)."""
    r, g, b = (_linear(c) for c in _rgb(h))
    lang = 17.8824 * r + 43.5161 * g + 4.11935 * b
    mittel = 3.45565 * r + 27.1554 * g + 3.86714 * b
    kurz = 0.0299566 * r + 0.184309 * g + 1.46709 * b
    if art == "deuteranopie":
        mittel = 0.494207 * lang + 1.24827 * kurz
    else:                                   # Protanopie
        lang = 2.02344 * mittel - 2.52581 * kurz
    r2 = 0.080944 * lang - 0.130504 * mittel + 0.116721 * kurz
    g2 = -0.0102485 * lang + 0.0540194 * mittel - 0.113615 * kurz
    b2 = -0.000365294 * lang - 0.00412163 * mittel + 0.693513 * kurz

    def gamma(c: float) -> float:
        c = max(0.0, min(1.0, c))
        return 255 * (12.92 * c if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055)

    return _hex([gamma(r2), gamma(g2), gamma(b2)])


def buntheit(h: str) -> int:
    """Abstand zwischen groesstem und kleinstem Kanal.

    Null bei Schwarz, Weiss und jedem Grau. Eine Rollenfarbe, die gegen Null
    laeuft, besteht zwar jede Kontrastrechnung, ist aber keine Farbe mehr -
    ein schwarzer Ring im Energiefluss sagt nichts ueber "Netz" aus.
    """
    r, g, b = _rgb(h)
    return max(r, g, b) - min(r, g, b)


BUNT_MIN = 24   # darunter liest sich eine Rollenfarbe als Schwarz oder Grau


def _abstand(a: str, b: str) -> float:
    x, y = _rgb(a), _rgb(b)
    return math.sqrt(sum((x[i] - y[i]) ** 2 for i in range(3)))


def trennbar(a: str, b: str, schwelle: int = TRENNUNG) -> bool:
    """Bleiben zwei Farben auch fuer rot-gruen-blinde Augen unterscheidbar?

    Der SCHLECHTERE der beiden Faelle zaehlt. Ein deutlicher Helligkeits-
    unterschied rettet ein Paar auch dann, wenn der Farbton zusammenfaellt.
    """
    schlechtester = min(_abstand(_simuliere(a, art), _simuliere(b, art))
                        for art in ("deuteranopie", "protanopie"))
    return schlechtester >= schwelle or kontrast(a, b) >= 1.6


def _schiebe(start: str, flaechen: list[str], ziel: float, richtung: int) -> str | None:
    """Helligkeit schrittweise verschieben, bis die Farbe auf ALLEN Flaechen traegt."""
    farbton, hell, saettigung = _hls(start)
    for schritt in range(101):
        kandidat = _aus_hls(farbton, hell + richtung * schritt / 100, saettigung)
        if all(kontrast(kandidat, f) >= ziel for f in flaechen):
            return kandidat
    return None


def _dritte_rolle(screen: str, glow: str, good: str, muted: str, helle_schrift: bool):
    """Dritte Rollenfarbe (Netz im Energiefluss, Stoerungspunkt, Sonntag).

    Auf der Kachel reicht Rot fuer "Stoerung", weil dort die ganze Flaeche
    umkippt. Im Energiefluss ist Netz aber nur ein 3 px starker Ring - auf
    rotem Panelgrund geht der unter. Deshalb wird der Farbton gesucht statt
    gesetzt. Erst mit weitem Abstand, und nur wenn kein Farbton den schafft,
    mit dem Mindestabstand.

    Geprueft wird gegen AA, nicht gegen die Grafik-Schwelle: dieselbe Farbe
    traegt in panel.html die Fehlermeldung der PIN-Eingabe (.pinmsg, 13 px auf
    .pinbox mit --screen) und den Sonntag im Kalender. Das ist normaler Text,
    und der braucht 4,5:1, nicht 3:1.
    """
    kandidaten = ((4 / 360, 0.72), (330 / 360, 0.62), (272 / 360, 0.58), (198 / 360, 0.70))
    basis = 0.55 if helle_schrift else 0.45
    richtung = 1 if helle_schrift else -1
    for schwelle in (60, TRENNUNG):
        for farbton, saettigung in kandidaten:
            for schritt in range(101):
                kandidat = _aus_hls(farbton, basis + richtung * schritt / 100, saettigung)
                if kontrast(kandidat, screen) < AA or buntheit(kandidat) < BUNT_MIN:
                    continue
                # Auch gegen die Zweitzeile pruefen: im Energiefluss steht der
                # Ring direkt ueber seinem Knotennamen, im Kalender der Sonntag
                # neben den Wochentagen.
                if all(trennbar(kandidat, p, schwelle) for p in (glow, good, muted)):
                    return kandidat
    return None


def _gegenfarbe(auf: str) -> str:
    """Schrift, die auf `auf` steht (z.B. dunkler Text auf Bernstein)."""
    farbton, _, saettigung = _hls(auf)
    dunkel = _aus_hls(farbton, 0.08, min(saettigung, 0.55))
    hell = _aus_hls(farbton, 0.97, min(saettigung, 0.20))
    return dunkel if kontrast(dunkel, auf) >= kontrast(hell, auf) else hell


# Farbton (Grad) und Saettigung der Rollenfarben. derive() und die Kachel-Sets
# (_ergaenzen) suchen von hier aus die Helligkeit, die auf ihren Flaechen traegt.
ROLLEN_TON = {"--glow": (38, 0.95), "--good": (152, 0.62), "--crit": (4, 0.72),
              "--warn": (32, 0.90), "--cool": (205, 0.65)}


def _stoerung(helle_schrift: bool) -> tuple[str, str | None, str | None]:
    """Gefuellte Stoerungskachel: (Fuellung, Schrift, Zweitzeile). Auf dunklem
    Grund eine helle Fuellung, auf hellem eine dunkle."""
    rot = ROLLEN_TON["--crit"][0] / 360
    if helle_schrift:                       # dunkler Grund -> helle Fuellung
        fuellung = _aus_hls(rot, 0.95, 0.45)
        return (fuellung, _schiebe(_aus_hls(rot, 0.32, 0.65), [fuellung], AAA, -1),
                _schiebe(_aus_hls(rot, 0.46, 0.32), [fuellung], AA, -1))
    fuellung = _aus_hls(rot, 0.28, 0.72)    # heller Grund -> dunkle Fuellung
    return (fuellung, _schiebe(_aus_hls(rot, 0.90, 0.30), [fuellung], AAA, 1),
            _schiebe(_aus_hls(rot, 0.74, 0.28), [fuellung], AA, 1))


def _versuch(screen: str, grundfarbe: str, helle_schrift: bool) -> dict | None:
    """Vollstaendigen Satz fuer EINE Bildschirmfarbe versuchen."""
    farbton, _, saettigung = _hls(grundfarbe)
    wash = "#ffffff" if helle_schrift else "#000000"
    wash_deckung = 0.08 if helle_schrift else 0.055

    ink = (_aus_hls(farbton, 0.965, min(saettigung, 0.30)) if helle_schrift
           else _aus_hls(farbton, 0.11, min(saettigung, 0.45)))
    tile = ueber(wash, screen, wash_deckung)
    if kontrast(ink, screen) < AAA or kontrast(ink, tile) < AA:
        return None

    # Tableiste: dunkle Oberflaechen setzen sie dunkler ab, helle heller.
    # Bei fast weissem Grund gibt es nach oben keinen Platz mehr -> Gegenrichtung.
    leiste = None
    for toenung in (("#000000", "#ffffff") if helle_schrift else ("#ffffff", "#000000")):
        for prozent in range(28, 3, -1):
            kandidat = ueber(toenung, screen, prozent / 100)
            if kontrast(ink, kandidat) >= AAA and kontrast(kandidat, screen) >= 1.06:
                leiste = kandidat
                break
        if leiste:
            break
    if leiste is None:
        return None

    muted = _schiebe(_aus_hls(farbton, 0.80 if helle_schrift else 0.30, min(saettigung, 0.35)),
                     [tile, screen, leiste], AA, 1 if helle_schrift else -1)
    if muted is None:
        return None

    # Zustandsfarben. Die Toenung der Kachel haengt an der Farbe selbst, also
    # erst loesen, dann die getoente Kachel daraus bauen und erneut pruefen.
    deckung = 0.16 if luminanz(screen) < 0.05 else 0.10
    zustand = {}
    for name in ("glow", "good"):
        fton, saett = ROLLEN_TON["--" + name]
        basis = 0.55 if helle_schrift else 0.45
        treffer = None
        for schritt in range(101):
            kandidat = _aus_hls(fton / 360, basis + (1 if helle_schrift else -1) * schritt / 100, saett)
            getoent = ueber(kandidat, screen, deckung)
            # Der Akzent muss sich auch von der Zweitzeile absetzen, sonst
            # verschwimmt "aktiv" mit "nur ein Zusatztext" - das passiert
            # genau dann, wenn Grundfarbe und Akzent denselben Farbton haben.
            if (kontrast(kandidat, getoent) >= AA and kontrast(ink, getoent) >= AA
                    and kontrast(kandidat, screen) >= GRAFIK
                    and buntheit(kandidat) >= BUNT_MIN
                    and trennbar(kandidat, muted)):
                treffer = kandidat
                break
        if treffer is None:
            return None
        zustand[name] = treffer
    if not trennbar(zustand["glow"], zustand["good"]):
        return None

    # Stoerung laeuft ueber die Form: die Kachel kippt um und wird gefuellt.
    fuellung, f_ink, f_muted = _stoerung(helle_schrift)
    if f_ink is None or f_muted is None or kontrast(fuellung, screen) < GRAFIK:
        return None

    netz = _dritte_rolle(screen, zustand["glow"], zustand["good"], muted, helle_schrift)
    if netz is None:
        return None
    kuehl = _schiebe(_aus_hls(ROLLEN_TON["--cool"][0] / 360, 0.70 if helle_schrift else 0.40,
                              ROLLEN_TON["--cool"][1]),
                     [screen, tile], AA, 1 if helle_schrift else -1)
    if kuehl is None:
        return None

    return {
        "screen": screen, "tile": tile, "leiste": leiste,
        "rahmen": ueber("#000000", screen, 0.14 if helle_schrift else 0.10),
        "wash": "255,255,255" if helle_schrift else "0,0,0",
        "ink": ink, "muted": muted,
        "glow": zustand["glow"], "good": zustand["good"], "netz": netz, "kuehl": kuehl,
        "fuellung": fuellung, "f_ink": f_ink, "f_muted": f_muted,
        "deckung": deckung,
    }


def derive(grundfarbe: str) -> dict | None:
    """Grundfarbe (#rrggbb) -> CSS-Variablen fuers Panel. None, wenn unmoeglich.

    Die Grundfarbe wird in ihrer Helligkeit so weit verschoben, bis der GANZE
    Satz aufgeht, nicht nur die Hauptschrift. Gesaettigte Mitteltoene wie
    Senfgelb liegen sonst in einer toten Zone, in der weder helle noch dunkle
    Akzente Platz haben und alles Richtung Schwarz zusammenfaellt.

    Eine Herleitung kostet 10 bis 60 ms und wird bei jeder Panel-Verbindung
    und jedem Speichern gebraucht; das Ergebnis je Farbe bleibt gemerkt
    (_derive). Zurueck kommt jedes Mal ein eigenes dict.
    """
    if not isinstance(grundfarbe, str) or not _HEX.match(grundfarbe.strip()):
        return None
    satz = _derive(grundfarbe.strip().lower())
    return dict(satz) if satz is not None else None


# So viele Grundfarben bleiben gemerkt - mehr als ein Haus je an Profilen hat.
DERIVE_MERKEN = 256


@functools.lru_cache(maxsize=DERIVE_MERKEN)
def _derive(grundfarbe: str) -> tuple | None:
    """derive() ohne Pruefung der Eingabe, Ergebnis als Tupel (unveraenderlich,
    damit der Speicher nicht von aussen veraendert wird)."""
    farbton, hell, saettigung = _hls(grundfarbe)
    helle_schrift = luminanz(grundfarbe) < 0.18
    richtung = -1 if helle_schrift else 1

    satz = None
    for schritt in range(101):
        kandidat = _aus_hls(farbton, hell + richtung * schritt / 100, saettigung)
        satz = _versuch(kandidat, grundfarbe, helle_schrift)
        if satz:
            break
    if not satz:
        return None

    def tripel(h: str) -> str:
        return "%d,%d,%d" % _rgb(h)

    return tuple({
        "--bg": satz["rahmen"], "--screen": satz["screen"],
        "--tile": satz["tile"], "--tabbar": satz["leiste"],
        "--wash": satz["wash"],
        "--ink": satz["ink"], "--muted": satz["muted"],
        # Aktiv und OK. --accent bekommt denselben Wert wie --good, genau wie
        # die Vorgaben im Stylesheet es tun; sonst blieben der aktive Tab, der
        # Erzeugungsring im Energiefluss und "heute" im Kalender im alten Gruen.
        "--glow": satz["glow"], "--on-rgb": tripel(satz["glow"]),
        "--good": satz["good"], "--good-rgb": tripel(satz["good"]),
        "--accent": satz["good"], "--accent-rgb": tripel(satz["good"]),
        # Rollenfarbe fuer Linien und Punkte (Netz, Stoerungspunkt, Sonntag).
        "--crit": satz["netz"], "--crit-rgb": tripel(satz["netz"]),
        "--crit-dot": satz["netz"],
        # Gefuellte Stoerungskachel.
        "--crit-fill": satz["fuellung"], "--crit-ink": satz["f_ink"],
        "--crit-muted": satz["f_muted"],
        "--cool": satz["kuehl"],
        "--on-glow": _gegenfarbe(satz["glow"]), "--on-accent": _gegenfarbe(satz["good"]),
        # Toenung der Aktiv-/OK-Kachel. Auf gesaettigtem Grund hebt eine
        # kraeftige Toenung den Kontrast der Zustandsfarbe auf.
        "--ov-fill": f"{satz['deckung']:.3g}",
    }.items())


# ---- Kachel-Sets ----------------------------------------------------------
# Ein Kachel-Set ist ein fertiger Look statt einer hergeleiteten Grundfarbe:
# Flaechen- und Rollenfarben, Masse und eine Art fuer Kachel und Tab-Leiste.
# Einzige Quelle fuer Name, Anzeige, Farben und Masse: _theme_vars() setzt die
# Farben und Masse als CSS-Variablen, /api/meta gibt die Auswahl an den
# Konfigurator, _clean_kachel_set() prueft gegen die Schluessel hier.
#
#   aufbau  Kachel: "lx" (neuer Aufbau, flach), "mitte" (Symbol mittig, Text
#           darunter, die aktive Kachel kippt ganz um), "kreis" (wie lx, das
#           Symbol in einem Kreis). panel.html haengt die Regeln an
#           html[data-kachelset-aufbau], nie an den Namen des Sets.
#   leiste  Tab-Leiste: "pille" (unten, als Pille), "oben" (nur Symbole ueber
#           dem Raster), "links" (Seitenleiste mit Symbol und Name), Regeln an
#           html[data-kachelset-leiste].
#   farben  feste Farben; fehlende Rollen rechnet _ergaenzen() nach.
#   masse   Radien, Schatten, Kreis, Leisten, Rahmen: CSS-Variablen ohne Farbe.
#           Ein Mass mit "-schmal" gilt auf schmalen Schirmen (raster.js
#           SCHMAL_UNTER, Klasse .schmal am Kasten). Was die Rasterrechnung
#           braucht (Leistenhoehe, Seitenleiste, Rahmen, Abstand, Innenrand),
#           liest der Konfigurator aus /api/meta, die Visu aus dem CSS.
#   groessen  Standardgroessen der Kachel (wie GROESSEN_STANDARD), die das Set
#           mitbringt; eine eingestellte Groesse geht vor.
#   satz    statt fester Farben eine Rechnung aus einem Farbton (touch_satz),
#           dazu farbton (Standard, Schnellwahl) und aktiv (Standard, Auswahl).
#   label, info  Name und Beschreibung im Konfigurator (i18n.js uebersetzt sie).
#
# Die Kontraste rechnet tests/test_kachel_set.py mit kontrast() nach, mit
# denselben Massstaeben wie derive() (AAA Hauptschrift, AA Rest, 3:1 Grafik).
#
# Rollen, die panel.html ausser den Theme-Variablen liest:
#   --kachel-an       Flaeche einer aktiven Kachel (statt der getoenten Auflage)
#   --kachel-an-ink   Schrift und Symbol auf ihr (Aufbau "mitte": kippt ganz um)
#   --an-text         Zustandstext "an", wo --glow fuer Text zu schwach ist
#   --taste           Flaeche der Tasten in Kachel und Detailseite (und des Kreises)
#   --kreis-an-symbol Symbol im Kreis einer aktiven Kachel (Aufbau "kreis")
#   --kachel-an-muted Zweitzeile auf der aktiven Kachel (Aufbau "mitte")
#   --tab-an, --tab-aus  Symbole der Leiste "oben"
#   --rahmen          Rahmen um das Feld (Leiste "oben") und Grund ausserhalb
#                     des Kastens. Nur Flaeche, nie Grund von Text: Text steht
#                     auf --bg (Uhr-Seite, PIN), und --bg traegt --ink wie
#                     --screen. Fehlt --rahmen, ist es --bg.
#   masse: --kachel-radius (bei 170-px-Kachel), --taste-radius,
#   --kachel-schatten, --kachel-abstand, --feld-innen (Abstand und Innenrand
#   des Rasters), --tabs-hoehe, --tab-symbol, --pille-h (Leiste "pille"),
#   --leiste-voll-ab (Schirmhoehe, ab der Leiste und Pille ihre vollen Masse
#   haben; darunter schrumpfen sie mit der Hoehe bis zu ihren -schmal-Massen,
#   raster.js leisteMass), --pille-tab-breite (Breite der Pille je Eintrag,
#   hoechstens so breit wie ohne das Mass),
#   --rahmen-seite, --rahmen-unten, --feld-radius (Leiste "oben": Rahmen um
#   das Feld der Kacheln), --rail-breite (Leiste "links"), --kreis-d,
#   --kreis-anteil (Aufbau "kreis": Kreis und Anteil des Symbols daran)
KACHEL_SETS = {
    "loxone": {
        "label": "Loxone-App (dunkel)",
        "info": "Flache dunkle Kacheln, weiße Symbole, dunkle Tasten, die Tab-Leiste als Pille.",
        "aufbau": "lx", "leiste": "pille",
        "farben": {
            "--bg": "#0a0a0a", "--screen": "#131313",
            "--tile": "#1e1e20", "--kachel-an": "#2c2c2f", "--taste": "#111112",
            "--tabbar": "#1e1e20", "--line": "rgba(255,255,255,.07)", "--wash": "255,255,255",
            "--ink": "#ffffff", "--muted": "#a1a1a6",
            "--glow": "#ffdc7a", "--good": "#69c350", "--accent": "#69c350",
            "--warn": "#f0a640", "--crit": "#ff6a5f", "--crit-dot": "#ff6a5f",
            "--crit-fill": "#4d1a16", "--crit-ink": "#ffffff", "--crit-muted": "#ffb3ad",
            "--cool": "#6cb4f0", "--on-glow": "#1f1600", "--on-accent": "#0d1a08",
        },
        "masse": {"--kachel-radius": "20px",
                  "--tabs-hoehe": "96px", "--tabs-hoehe-schmal": "64px",
                  "--pille-h": "68px", "--pille-h-schmal": "52px",
                  "--leiste-voll-ab": "820px", "--pille-tab-breite": "130px",
                  "--tab-symbol": "28px", "--tab-symbol-schmal": "22px"},
    },
    "touch": {
        "label": "Touch (Farbton wählbar)",
        "info": "Kacheln in einem Farbton, Symbol mittig, die aktive Kachel kippt ganz um; "
                "die Tab-Leiste steht nur mit Symbolen oben.",
        "aufbau": "mitte", "leiste": "oben",
        "farben": {"--tab-an": "#ffffff"},
        # Farbton in Grad: Standard und Schnellwahl im Konfigurator
        "farbton": {"standard": 270, "auswahl": [
            {"label": "Salbei", "wert": 95}, {"label": "Mint", "wert": 160},
            {"label": "Himmel", "wert": 205}, {"label": "Lavendel", "wert": 270},
            {"label": "Rosé", "wert": 345}, {"label": "Sand", "wert": 40}]},
        # Aktive Kachel: hell (fast weiss, Schrift im Farbton) oder dunkel
        "aktiv": {"standard": "hell", "auswahl": [
            {"key": "hell", "label": "Hell"}, {"key": "dunkel", "label": "Dunkel"}]},
        # touch_satz(): (Saettigung, Helligkeit) in Prozent wie CSS hsl(), der
        # Farbton ist der gewaehlte. "schritt" ist die Richtung, in der die
        # Helligkeit wandert (+1 heller, -1 dunkler), bis "ziel" erreicht ist.
        "satz": {
            "rahmen": "#0b0b0b",                                  # Tab-Leiste und Rand (--rahmen)
            "ink": (35, 12),
            "kachel": {"s": 42, "l": 70, "bis": 93, "ziel": AAA},  # ink darauf
            "feld": {"s": 42, "plus": 5, "bis": 95},                # Flaeche hinter den Kacheln
            "taste": {"s": 40, "minus": 10, "ziel": AA},            # ink darauf, aufhellen
            "aktiv": {
                "hell": {"flaeche": (30, 97), "schrift": (50, 38), "schritt": -1, "ziel": AA},
                "dunkel": {"flaeche": (12, 9), "schrift": (55, 82), "schritt": 1, "ziel": AAA},
            },
            "tab_aus": {"s": 8, "l": 62, "schritt": 1, "ziel": AA},  # auf dem Rahmen
            # Zweitzeile der aktiven Kachel: ihre Schrift mit dieser Deckung
            # ueber der Flaeche, mehr Deckung, bis sie AA traegt
            "an_zweit": 0.7,
        },
        "masse": {"--kachel-radius": "12px",
                  "--tabs-hoehe": "104px", "--tabs-hoehe-schmal": "82px",
                  "--tab-symbol": "32px", "--tab-symbol-schmal": "30px",
                  "--rahmen-seite": "28px", "--rahmen-seite-schmal": "18px",
                  "--rahmen-unten": "28px", "--rahmen-unten-schmal": "18px",
                  "--feld-radius": "22px", "--feld-radius-schmal": "16px",
                  "--feld-innen": "8px", "--feld-innen-schmal": "6px",
                  "--kachel-abstand": "8px", "--kachel-abstand-schmal": "6px"},
        "groessen": {"iconSize": 46, "nameSize": 17},
    },
    "kreide": {
        "label": "Kreide (hell)",
        "info": "Weiße Kacheln auf hellem Grund, das Symbol im Kreis, die Tabs als Seitenleiste links.",
        "aufbau": "kreis", "leiste": "links",
        "farben": {
            "--screen": "#f3f1ec", "--tabbar": "#e9e6df", "--tile": "#ffffff", "--taste": "#f0ede6",
            "--ink": "#1b1a17", "--muted": "#66625a",
            "--glow": "#c8611c", "--an-text": "#a3500f", "--kreis-an-symbol": "#ffffff",
            "--good": "#2f7d3a", "--crit": "#b3261e", "--crit-fill": "#fbe4e1",
        },
        "masse": {"--kachel-radius": "20px", "--taste-radius": "14px",
                  "--kreis-d": "52px", "--kreis-d-schmal": "42px", "--kreis-anteil": "0.54",
                  "--rail-breite": "208px", "--rail-breite-schmal": "68px",
                  "--kachel-schatten": "0 1px 3px rgba(27,26,23,.08)"},
    },
}

# Rollen, zu denen panel.html zusaetzlich das R,G,B-Tripel braucht (Auflagen
# mit eigener Deckkraft). Werden aus dem Hex-Wert des Sets gerechnet.
_SET_TRIPEL = {"--glow": "--on-rgb", "--good": "--good-rgb", "--accent": "--accent-rgb",
               "--crit": "--crit-rgb", "--warn": "--warn-rgb"}

# Deckkraft der Linien (--line) aus der Auflagefarbe, wo ein Set keine nennt
LINIE_DECKUNG = 0.10


def _hsl(farbton: float, saettigung: float, helligkeit: float) -> str:
    """Farbe wie CSS hsl(): Farbton in Grad, Saettigung und Helligkeit in Prozent."""
    return _aus_hls((farbton % 360) / 360, helligkeit / 100, saettigung / 100)


def _wandern(farbton: float, saettigung: float, helligkeit: float, gegen: str,
             ziel: float, schritt: int, bis: float) -> str:
    """Helligkeit in Prozentpunkten um `schritt` verschieben, bis die Farbe auf
    `gegen` den Kontrast `ziel` hat oder `bis` erreicht ist."""
    while kontrast(_hsl(farbton, saettigung, helligkeit), gegen) < ziel and helligkeit != bis:
        helligkeit = max(0, min(100, helligkeit + schritt))
    return _hsl(farbton, saettigung, helligkeit)


@functools.lru_cache(maxsize=2 * 360)
def _touch_satz(farbton: int, aktiv_hell: bool) -> tuple:
    p = KACHEL_SETS["touch"]["satz"]
    ink = _hsl(farbton, *p["ink"])
    k = p["kachel"]
    hell = k["l"]
    while kontrast(ink, _hsl(farbton, k["s"], hell)) < k["ziel"] and hell < k["bis"]:
        hell += 1
    tile = _hsl(farbton, k["s"], hell)
    feld = _hsl(farbton, p["feld"]["s"], min(p["feld"]["bis"], hell + p["feld"]["plus"]))
    t = p["taste"]
    taste = _wandern(farbton, t["s"], hell - t["minus"], ink, t["ziel"], 1, 100)
    a = p["aktiv"]["hell" if aktiv_hell else "dunkel"]
    an = _hsl(farbton, *a["flaeche"])
    an_ink = _wandern(farbton, *a["schrift"], an, a["ziel"], a["schritt"], 0 if a["schritt"] < 0 else 100)
    deckung = p["an_zweit"]
    while kontrast(ueber(an_ink, an, deckung), an) < AA and deckung < 1:
        deckung = min(1, deckung + 0.05)
    an_muted = ueber(an_ink, an, deckung)
    ta = p["tab_aus"]
    tab_aus = _wandern(farbton, ta["s"], ta["l"], p["rahmen"], ta["ziel"], ta["schritt"], 100)
    return tuple({
        "--ink": ink, "--tile": tile, "--screen": feld, "--taste": taste,
        "--kachel-an": an, "--kachel-an-ink": an_ink, "--kachel-an-muted": an_muted,
        "--rahmen": p["rahmen"], "--tabbar": p["rahmen"], "--tab-aus": tab_aus,
    }.items())


def touch_satz(farbton, aktiv_hell: bool) -> dict:
    """Farben des Sets "touch" aus einem Farbton (Grad, 0-359): Schrift, Kachel,
    Flaeche dahinter, Taste, aktive Kachel (hell oder dunkel) und die Symbole der
    Leiste, jeweils so weit nachgeregelt, bis der Kontrast aus
    KACHEL_SETS["touch"]["satz"] erreicht ist. Jedes Mal ein eigenes dict."""
    return dict(_touch_satz(int(farbton) % 360, bool(aktiv_hell)))


def _ergaenzen(v: dict, kippt: bool) -> dict:
    """Rollen, die ein Set nicht nennt, nach denselben Regeln wie derive()
    gegen die Flaechen des Sets nachrechnen. kippt: die aktive Kachel hat ihre
    eigene Schrift (Aufbau "mitte"), dort steht keine Zweitzeile."""
    hell = luminanz(v["--tile"]) > 0.18           # helle Kacheln -> dunkle Schrift
    richtung, basis = (-1, 0.55) if hell else (1, 0.45)
    v.setdefault("--bg", v["--screen"])       # Grund der Uhr-Seite: traegt dieselbe Schrift
    v.setdefault("--rahmen", v["--bg"])
    v.setdefault("--kachel-an", v["--tile"])
    v.setdefault("--wash", "0,0,0" if hell else "255,255,255")
    v.setdefault("--line", f"rgba({v['--wash']},{LINIE_DECKUNG:g})")
    # Text steht auf Kachel und Flaeche (und ohne Umkippen auf der aktiven
    # Kachel), auf der Taste nur Symbole in --ink
    flaechen = [v["--tile"], v["--screen"]] + ([] if kippt else [v["--kachel-an"]])
    if "--muted" not in v:
        farbton, _, saettigung = _hls(v["--ink"])
        v["--muted"] = _schiebe(_aus_hls(farbton, basis, min(saettigung, 0.25)), flaechen, AA, richtung)
    for rolle in ("--glow", "--good", "--crit", "--warn", "--cool"):
        if rolle in v:
            continue
        farbton, saettigung = ROLLEN_TON[rolle]
        treffer = None
        for pruefen_trennung in (True, False):
            for schritt in range(101):
                kandidat = _aus_hls(farbton / 360, basis + richtung * schritt / 100, saettigung)
                if all(kontrast(kandidat, f) >= AA for f in flaechen) and buntheit(kandidat) >= BUNT_MIN \
                        and (not pruefen_trennung or trennbar(kandidat, v["--muted"])):
                    treffer = kandidat
                    break
            if treffer:
                break
        v[rolle] = treffer or _schiebe(_aus_hls(farbton / 360, basis, saettigung), flaechen, AA, richtung)
    v.setdefault("--accent", v["--good"])
    v.setdefault("--crit-dot", v["--crit"])
    if "--crit-fill" not in v:
        v["--crit-fill"], f_ink, f_muted = _stoerung(not hell)
        v.setdefault("--crit-ink", f_ink)
        v.setdefault("--crit-muted", f_muted)
    f_richtung = -1 if luminanz(v["--crit-fill"]) > 0.18 else 1
    if "--crit-ink" not in v:
        v["--crit-ink"] = v["--ink"] if kontrast(v["--ink"], v["--crit-fill"]) >= AAA \
            else _schiebe(v["--ink"], [v["--crit-fill"]], AAA, f_richtung)
    if "--crit-muted" not in v:
        v["--crit-muted"] = v["--muted"] if kontrast(v["--muted"], v["--crit-fill"]) >= AA \
            else _schiebe(v["--muted"], [v["--crit-fill"]], AA, f_richtung)
    v.setdefault("--on-glow", schrift_auf(v["--glow"]))
    v.setdefault("--on-accent", schrift_auf(v["--accent"]))
    return v


def schrift_auf(flaeche: str) -> str:
    """Text auf einer Rollenfarbe (OK-Taste der PIN auf --glow): die Gegenfarbe,
    nachgeregelt, bis sie AA traegt - _gegenfarbe() kennt nur zwei Helligkeiten."""
    schrift = _gegenfarbe(flaeche)
    if kontrast(schrift, flaeche) >= AA:
        return schrift
    return _schiebe(schrift, [flaeche], AA, -1 if luminanz(schrift) < luminanz(flaeche) else 1) or schrift


def _farbton(eintrag: dict, wert) -> int:
    """Gewaehlter Farbton eines Sets mit Rechnung, sonst sein Standard."""
    if isinstance(wert, (int, float)) and not isinstance(wert, bool) and 0 <= wert < 360:
        return int(wert)
    return eintrag["farbton"]["standard"]


def _aktiv(eintrag: dict, wert) -> str:
    """Gewaehlte Art der aktiven Kachel eines Sets mit Rechnung, sonst ihr Standard."""
    keys = [a["key"] for a in eintrag["aktiv"]["auswahl"]]
    return wert if wert in keys else eintrag["aktiv"]["standard"]


def kachel_set(name, farbton=None, aktiv=None) -> dict | None:
    """CSS-Variablen eines Kachel-Sets (Farben und Masse), None bei unbekanntem
    Namen. farbton und aktiv gelten fuer ein Set mit Rechnung (satz), ungueltig
    oder fehlend gilt dessen Standard. Jedes Mal ein eigenes dict (der Aufrufer
    ergaenzt es)."""
    eintrag = KACHEL_SETS.get(name) if isinstance(name, str) else None
    if not eintrag:
        return None
    v = dict(eintrag.get("farben") or {})
    if "satz" in eintrag:
        v.update(touch_satz(_farbton(eintrag, farbton), _aktiv(eintrag, aktiv) == "hell"))
    _ergaenzen(v, kippt=eintrag["aufbau"] == "mitte")
    for rolle, tripel in _SET_TRIPEL.items():
        if _HEX.match(v.get(rolle, "")):
            v[tripel] = "%d,%d,%d" % _rgb(v[rolle])
    v.update(eintrag.get("masse") or {})
    return v


def kachel_set_pruefung(name, farbton=None, aktiv=None) -> list[dict]:
    """Nachgerechnete Kontraste eines Sets mit Rechnung fuer den Konfigurator
    ("Nachgerechnet"): je Ziel aus dem satz {name, wert, ziel}. Leer fuer ein
    Set ohne Rechnung (seine festen Farben prueft tests/test_kachel_set.py)."""
    e = KACHEL_SETS.get(name) if isinstance(name, str) else None
    if not e or "satz" not in e:
        return []
    p, v = e["satz"], kachel_set(name, farbton, aktiv)
    paare = (("Schrift auf Kachel", "--ink", "--tile", p["kachel"]["ziel"]),
             ("Schrift auf aktiver Kachel", "--kachel-an-ink", "--kachel-an", p["aktiv"][_aktiv(e, aktiv)]["ziel"]),
             ("Symbol auf Taste", "--ink", "--taste", p["taste"]["ziel"]))
    return [{"name": n, "wert": round(kontrast(v[a], v[b]), 2), "ziel": z} for n, a, b, z in paare]


def kachel_set_kachel(name, farbton=None, aktiv=None) -> str:
    """Kachelfarbe eines Sets (zur Anzeige neben dem Farbton), "" ohne Set."""
    v = kachel_set(name, farbton, aktiv)
    return v["--tile"] if v else ""


def kachel_set_vorschau(name, farbton=None, aktiv=None) -> dict:
    """Farben fuer die Vorschau eines Sets im Konfigurator (Auswahlkarte):
    Rahmen, Flaeche, Kachel, aktive Kachel und Akzent, wie die Visu sie
    zeigt. {} ohne Set."""
    v = kachel_set(name, farbton, aktiv)
    if not v:
        return {}
    return {"rahmen": v["--rahmen"], "flaeche": v["--screen"], "kachel": v["--tile"],
            "an": v["--kachel-an"], "akzent": v["--glow"]}


def kachel_set_art(name) -> tuple[str, str]:
    """(aufbau, leiste) eines Kachel-Sets, ("", "") ohne Set."""
    eintrag = KACHEL_SETS.get(name) if isinstance(name, str) else None
    return (eintrag["aufbau"], eintrag["leiste"]) if eintrag else ("", "")


# Stufen des Farbverlaufs unter dem Farbton-Regler im Konfigurator (Grad)
VERLAUF_SCHRITT = 30


def kachel_set_liste() -> list[dict]:
    """Auswahl fuer den Konfigurator in Definitionsreihenfolge: {key, label,
    info, aufbau, leiste, masse, groessen, vorschau}. Ein Set mit Rechnung bringt dazu farbton (Standard,
    Schnellwahl je mit der Kachelfarbe "farbe", "verlauf" als Kachelfarben in
    VERLAUF_SCHRITT-Stufen fuer den Regler) und aktiv (Standard, Auswahl) mit -
    die Farben rechnet touch_satz(), der Konfigurator zeigt sie nur."""
    liste = []
    for k, e in KACHEL_SETS.items():
        eintrag = {"key": k, "label": e["label"], "info": e["info"], "aufbau": e["aufbau"], "leiste": e["leiste"],
                   "masse": dict(e.get("masse") or {}), "groessen": dict(e.get("groessen") or {}),
                   "vorschau": kachel_set_vorschau(k)}
        if "satz" in e:
            hell = e["aktiv"]["standard"] == "hell"
            eintrag["farbton"] = {
                "standard": e["farbton"]["standard"],
                "auswahl": [{**a, "farbe": touch_satz(a["wert"], hell)["--tile"]} for a in e["farbton"]["auswahl"]],
                "verlauf": [touch_satz(h, hell)["--tile"] for h in range(0, 360, VERLAUF_SCHRITT)],
            }
            eintrag["aktiv"] = e["aktiv"]
        liste.append(eintrag)
    return liste
