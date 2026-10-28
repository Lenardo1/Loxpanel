"""Was die Bausteinfamilien (bausteine/*.py) und der Server gemeinsam brauchen:
die Adapter fuer Licht und Jalousie, die Typmengen und Konstanten aus der
Loxone-Strukturdoku und reine Helfer ohne Zustand. webvisu.py importiert die
Namen von hier, damit alles, was sie bisher dort gefunden hat (auch die Tests),
sie weiter findet. Keine Abhaengigkeit zum Server, nur Standardbibliothek und
adapters.py."""
from __future__ import annotations

import functools
import json
import re

from adapters import JalousieAdapter, LightControllerV2Adapter


LIGHT = LightControllerV2Adapter()
JAL = JalousieAdapter()
SWITCHY = {"Switch"}   # TimedSwitch wird eigen behandelt (anderer State)
# Wochentage kurz, Montag zuerst (datetime.weekday()): Verlaeufe, Wecker, Klingelzeiten
STAT_WEEKDAYS = ("Mo", "Di", "Mi", "Do", "Fr", "Sa", "So")
# Betriebsarten des Sauna-Bausteins (State "mode", 0..6), Zuordnung aus der
# offiziellen Loxone-Sauna-Dokumentation. Als Klartext auf Kachel und Detailseite.
SAUNA_MODES = {0: "Manuell", 1: "Finnisch manuell", 2: "Feuchte manuell",
               3: "Finnische Sauna", 4: "Kräutersauna", 5: "Sanftdampfbad", 6: "Warmluftbad"}
# ... was die Sauna meldet (States lessWater bzw. error/saunaError), auf der
# Detailseite und als Hinweis der Hausseite
SAUNA_WASSER, SAUNA_STOERUNG = "Wasser nachfüllen", "Störung"
# Alte Raumregelung (IRoomController, v1) laut Loxone-Strukturdoku: Nummern der
# Temperaturen fuer settemp/starttimer und currHeatTempIx/currCoolTempIx. Die
# Struktur liefert dazu je Nummer einen State (Liste "temperatures") und in
# details.temperatures, ob der Wert absolut ist oder von Komfort abhaengt.
IRC1_TEMPS = {0: "Eco", 1: "Komfort Heizen", 2: "Komfort Kühlen", 3: "Haus leer",
              4: "Hitzeschutz", 5: "Erhöhte Wärme", 6: "Party", 7: "Manuell"}
IRC1_ECO, IRC1_KOMFORT_HEIZEN, IRC1_KOMFORT_KUEHLEN = 0, 1, 2
# State "mode": 2 = Autopilot kuehlt gerade, 4 = Autopilot Kuehlen, 6 = Manuell
# Kuehlen; alle anderen Betriebsarten heizen (bzw. 0 = keine Periode aktiv).
IRC1_KUEHL_MODI = {2, 4, 6}
# 5 = Manuell Heizen, 6 = Manuell Kuehlen: dann gilt die manuelle Temperatur.
IRC1_MANUELL_MODI, IRC1_MANUELL = {5, 6}, 7
# Eco/Komfort-Knoepfe halten die Temperatur so lange wie der Override beim V2.
IRC1_TIMER_S = 3600
# Betriebsart der alten Raumregelung, waehlbar per mode/<Nr> (Loxone-Strukturdoku):
# 1 und 2 ("Automatik, heizt/kuehlt gerade") meldet nur der State, gesendet
# werden 3 und 4. details.restrictedToMode: 1 = nur Kuehlen, 2 = nur Heizen.
IRC1_BETRIEBSARTEN = {0: "Automatik", 3: "Automatik Heizen", 4: "Automatik Kühlen",
                      5: "Manuell Heizen", 6: "Manuell Kühlen"}
IRC1_NUR_KUEHLEN, IRC1_NUR_HEIZEN = 1, 2
# Betriebsart des IRoomControllerV2 (State operatingMode, setOperatingMode/<Nr>),
# Bedeutung wie in der openHAB-Loxone-Anbindung; 3..5 sind manuell.
IRC2_BETRIEBSARTEN = {0: "Automatik Heizen & Kühlen", 1: "Automatik nur Heizen",
                      2: "Automatik nur Kühlen", 3: "Manuell Heizen & Kühlen",
                      4: "Manuell nur Heizen", 5: "Manuell nur Kühlen"}
IRC2_MANUELL = {3, 4, 5}
# Bewaesserung (Irrigation) laut Loxone-Strukturdoku: zones[].id beginnt bei 0,
# currentZone -1 = aus, 0..7 = diese Zone, 8 = alle Zonen. Der Befehl select
# entspricht dem Eingang "Sel" des Bausteins (Loxone-Wissensdatenbank): 1..8
# schaltet Ventil V1..V8, also Zone id + 1; 0 schaltet alle aus, 9 alle an.
# setDuration/{id}={Sekunden} nimmt dagegen die id aus zones.
IRR_AUS, IRR_ALLE_AKTIV = -1, 8
IRR_SELECT_AUS, IRR_SELECT_ALLE = 0, 9
# Tuersprechstellen laut Strukturdoku 17.0: Intercom ("Door Controller", in
# Loxone Config die Tuersteuerung, auch mit benutzerdefinierter Intercom) und
# IntercomV2 (der Baustein Intercom). Beide haben bell, answer und Ausgaenge
# als Pushbutton-Subcontrols; v2 dazu Antworten (playTts), Stumm (mute) und
# den Geraetezustand (deviceState).
INTERCOM_TYPES = ("Intercom", "IntercomV2")
# Gesperrte Bausteine (Strukturdoku "Locking and Unlocking Controls", seit
# 11.3.2.11): details.jLockable sagt, ob ein Baustein sich sperren laesst, der
# Text-State jLocked haelt bei einer Sperre ein JSON {locked, reason}. locked:
# 0 nicht gesperrt, 1 ueber die Visualisierung, 2 durch die Logik; leerer Text
# = nicht gesperrt. Gesperrt nimmt der Baustein keine Befehle an.
SPERRE_DURCH = {1: "über die Visualisierung", 2: "durch die Logik"}
SPERRE_KURZ = "Gesperrt"
# Zweitzeile einer Kachel, deren Bausteintyp LoxPanel nicht kennt
TYP_UNBEKANNT = "Typ nicht unterstützt"
# Zeitstempel der Bausteine zaehlen Sekunden seit dem 1.1.2009 in UTC
# (Strukturdoku: Briefkasten disableEndTime, Strompreis-Optimierer cycleFrom);
# beim Wecker (nextEntryTime) nennt die Doku keine Zeitbasis, eine Anlage
# zeigte als Wanduhr gelesen genau den UTC-Abstand zu frueh. Unix-Zeit des
# 1.1.2009 00:00 UTC; datetime.fromtimestamp(LOX_EPOCH_UTC + ts) ist die Ortszeit.
LOX_EPOCH_UTC = 1230768000


def _pos_pct(value) -> int | None:
    """Stellung als ganze Prozent 0..100 fuer den Ring auf der Kachel.

    None bedeutet "dieser Baustein hat keine Stellung" - dann zeichnet das
    Panel gar keinen Ring. Der Wert ist immer derselbe, den auch die
    Zweitzeile nennt, damit Ring und Text nicht auseinanderlaufen.
    """
    try:
        return max(0, min(100, int(round(float(value)))))
    except (TypeError, ValueError):
        return None


@functools.lru_cache(maxsize=256)
def _sperre_lesen(text: str) -> tuple | None:
    """(locked, Grund) aus dem Text des States jLocked, None = nicht gesperrt.
    Zwischengespeichert, denn jede Kachel fragt bei jedem Rendern."""
    try:
        d = json.loads(text) if text else None
    except ValueError:
        return None
    if not isinstance(d, dict):
        return None
    art = d.get("locked")
    if isinstance(art, bool):
        art = int(art)
    if not isinstance(art, int) or not art:
        return None
    return art, str(d.get("reason") or "").strip()


def _clean(name: str) -> str:
    return re.sub(r"^[^0-9A-Za-zÄÖÜäöü]+", "", name or "").strip() or (name or "")


def _dauer_text(sek) -> str:
    """Dauer in Sekunden als Text: '45 s', '10 min', '1 min 30 s', '1 h 30 min', '0 min'.
    Leer, wenn keine Zahl. Dieselbe Schreibweise baut die Visu fuer -/+ nach
    (dauerText in panel.html)."""
    try:
        s = int(round(float(sek)))
    except (TypeError, ValueError):
        return ""
    s = max(0, s)
    if not s:
        return "0 min"
    h, m, r = s // 3600, s % 3600 // 60, s % 60
    if h:
        return f"{h} h" + (f" {m} min" if m else "")
    if m:
        return f"{m} min" + (f" {r} s" if r else "")
    return f"{r} s"


# Schrittweite der -/+ Tasten fuer Dauern (Laufzeit einer Zone, Wecker-Dauern)
# und Prozentwerte (Lautstaerke, Helligkeit)
DAUER_SCHRITT = 60

PROZENT_SCHRITT = 5


