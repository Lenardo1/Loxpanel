"""Bausteine der Visu: je Familie ein Modul, das seine Kachel- und Detailseiten-
Funktionen in die Tabellen KACHEL und DETAIL eintraegt.

- @kachel("Typ", ...)  registriert fn(app, uuid, c, it): ergaenzt das Kachel-Dict it
  (on, sublabel, icon, nav, cmd, controls ...). Kopf (Name, Raum, Farbe, secured)
  und Fuss (Status-Bausteine antippbar, Kategorie-Ampel, Kachelstil) baut
  App._control_item() in webvisu.py.
- @detail("Typ", ...)  registriert fn(app, uuid, c, route) -> view-Nachricht der
  Detailseite; Verlauf und verlinkte Objekte haengt App._view_control() an.
- @kachel_praefix("Central") fuer Typen, die ueber ihr Praefix laufen
  (Zentralbausteine). Erst die genaue Tabelle, dann die Praefixe.

Ein Typ steht in jeder Tabelle hoechstens einmal, ein zweiter Eintrag ist ein
Fehler beim Import. Die Helfer der Bausteine (_state, _fmt_num, _jal_fahrt ...)
sind Methoden von Mixin-Klassen: die allgemeinen in helfer.py (Grundhelfer),
die einer Familie in ihrem Modul (KlimaHelfer, WeckerHelfer ...), dort auch die
Unterseiten (Weckzeit, Bewaesserungszone, Klingelbilder, Favoriten).
BausteinHelfer unten fasst sie zusammen, App erbt es; gerufen wird ueber
app. bzw. self. Gemeinsame Konstanten, Adapter und reine Helfer liegen in
gemeinsam.py. Die Familien: licht, schalten,
beschattung, klima, audio, intercom, werte, sicherheit, wecker, energie, garten,
wellness, zentral. Ein neuer Typ bekommt seine Funktionen in der passenden
Familie (oder einer neuen, die unten importiert wird), nicht in webvisu.py."""
from __future__ import annotations

from collections.abc import Callable

KACHEL: dict[str, Callable] = {}
DETAIL: dict[str, Callable] = {}
KACHEL_PRAEFIX: list[tuple[str, Callable]] = []


def _eintragen(tabelle: dict, typen: tuple, fn: Callable, was: str) -> None:
    for t in typen:
        if t in tabelle:
            raise RuntimeError(f"{was} fuer {t} doppelt: {tabelle[t].__module__} und {fn.__module__}")
        tabelle[t] = fn


def kachel(*typen: str) -> Callable:
    """Kachel-Funktion fuer diese Typen eintragen."""
    def deko(fn: Callable) -> Callable:
        _eintragen(KACHEL, typen, fn, "Kachel")
        return fn
    return deko


def detail(*typen: str) -> Callable:
    """Detailseiten-Funktion fuer diese Typen eintragen."""
    def deko(fn: Callable) -> Callable:
        _eintragen(DETAIL, typen, fn, "Detailseite")
        return fn
    return deko


def kachel_praefix(praefix: str) -> Callable:
    """Kachel-Funktion fuer alle Typen mit diesem Praefix (nach der genauen Tabelle)."""
    def deko(fn: Callable) -> Callable:
        if any(p == praefix for p, _ in KACHEL_PRAEFIX):
            raise RuntimeError(f"Kachel-Praefix {praefix} doppelt")
        KACHEL_PRAEFIX.append((praefix, fn))
        return fn
    return deko


def kachel_fuer(typ) -> Callable | None:
    fn = KACHEL.get(typ)
    if fn is None and typ:
        fn = next((f for p, f in KACHEL_PRAEFIX if str(typ).startswith(p)), None)
    return fn


def detail_fuer(typ) -> Callable | None:
    return DETAIL.get(typ)


def typen() -> dict[str, dict]:
    """Alle eingetragenen Typen mit Modul und ob es Kachel und Detailseite gibt
    (Diagnose, Tests)."""
    out: dict[str, dict] = {}
    for t, f in KACHEL.items():
        out.setdefault(t, {"modul": f.__module__.rsplit(".", 1)[-1]})["kachel"] = True
    for t, f in DETAIL.items():
        out.setdefault(t, {"modul": f.__module__.rsplit(".", 1)[-1]})["detail"] = True
    return out


# Die Familien registrieren sich beim Import; Reihenfolge nur fuer die Lesbarkeit.
from . import licht, schalten, beschattung, klima, audio, intercom, werte  # noqa: E402
from . import sicherheit, wecker, energie, garten, wellness, zentral  # noqa: E402,F401  # sicherheit traegt nur Tabellen
from . import helfer  # noqa: E402


class BausteinHelfer(helfer.Grundhelfer, licht.LichtHelfer, schalten.SchaltenHelfer,
                     beschattung.BeschattungHelfer, klima.KlimaHelfer, audio.AudioHelfer,
                     intercom.IntercomHelfer, werte.WerteHelfer, wecker.WeckerHelfer,
                     energie.EnergieHelfer, garten.GartenHelfer, wellness.WellnessHelfer,
                     zentral.ZentralHelfer):
    """Alle Helfer der Bausteine in einer Klasse; App erbt sie (Mixin)."""
