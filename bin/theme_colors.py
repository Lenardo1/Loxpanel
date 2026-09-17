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
    for name, (fton, saett) in (("glow", (38 / 360, 0.95)), ("good", (152 / 360, 0.62))):
        basis = 0.55 if helle_schrift else 0.45
        treffer = None
        for schritt in range(101):
            kandidat = _aus_hls(fton, basis + (1 if helle_schrift else -1) * schritt / 100, saett)
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
    rot = 4 / 360
    if helle_schrift:                       # dunkler Grund -> helle Fuellung
        fuellung = _aus_hls(rot, 0.95, 0.45)
        f_ink = _schiebe(_aus_hls(rot, 0.32, 0.65), [fuellung], AAA, -1)
        f_muted = _schiebe(_aus_hls(rot, 0.46, 0.32), [fuellung], AA, -1)
    else:                                   # heller Grund -> dunkle Fuellung
        fuellung = _aus_hls(rot, 0.28, 0.72)
        f_ink = _schiebe(_aus_hls(rot, 0.90, 0.30), [fuellung], AAA, 1)
        f_muted = _schiebe(_aus_hls(rot, 0.74, 0.28), [fuellung], AA, 1)
    if f_ink is None or f_muted is None or kontrast(fuellung, screen) < GRAFIK:
        return None

    netz = _dritte_rolle(screen, zustand["glow"], zustand["good"], muted, helle_schrift)
    if netz is None:
        return None
    kuehl = _schiebe(_aus_hls(205 / 360, 0.70 if helle_schrift else 0.40, 0.65),
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
    """
    if not isinstance(grundfarbe, str) or not _HEX.match(grundfarbe.strip()):
        return None
    grundfarbe = grundfarbe.strip().lower()
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

    return {
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
    }
