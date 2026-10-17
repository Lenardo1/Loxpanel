"""Diagnosepaket: was Server und Panels gerade tun, als ZIP zum Weitergeben.

Konfigurator -> Geraete -> "Diagnose" (je Geraet) oder Einstellungen ->
Sicherung -> "Diagnose herunterladen" (Server gesamt), Route GET
/api/diagnose[?device=]. Das ZIP soll eine Fehlersuche mit einem Klick
beginnen lassen - auch fuer Claude: welcher Stand laeuft, wie es um die
Verbindungen steht, was das Geraet zeigt und was der Server zuletzt
protokolliert hat.

  diagnose.md    lesbar, oben die Zusammenfassung (ein Satz je Verbindung)
  diagnose.json  dieselben Angaben maschinenlesbar
  einstellungen/ loxpanel.cfg, panels.json, theme.json, soweit vorhanden
  log.txt        die letzten Log-Zeilen (LOG_ZEILEN, hoechstens LOG_MINUTEN alt)

Geheimnisse verlassen den Server nicht (bereinigen): Kennwoerter, Tokens und
Schluessel (GEHEIM_SCHLUESSEL) fallen weg, Kalender-Abos (ihr Pfad ist der
Zugang) bleiben nur mit Schema und Host, Benutzer:Kennwort in Adressen wird
gestrichen und der Standort (ORT_SCHLUESSEL) entfernt. Jeder gefundene Wert
wird danach in allen Texten des Pakets geschwaerzt (schwaerzen), auch im Log,
falls er dort auftaucht. Die Routen haben keine Anmeldung: lieber zu viel
entfernen als zu wenig.

Nur Standardbibliothek. webvisu sammelt die Angaben (App.diagnose_daten) und
ruft paket(); der Log-Puffer haengt am Root-Logger (_logging_einrichten).
"""
from __future__ import annotations

import collections
import io
import json
import logging
import re
import time
import zipfile
from datetime import datetime
from urllib.parse import quote, quote_plus, urlsplit

# Log-Puffer: so viele Zeilen hoechstens, und davon nur die der letzten
# LOG_MINUTEN - "was unmittelbar davor passiert ist", ohne Tage an Rauschen.
LOG_ZEILEN = 2000
LOG_MINUTEN = 30
# Was an Stelle eines Geheimnisses steht. Ein leerer Wert bleibt leer: so
# sieht man, ob etwas eingetragen ist.
ENTFERNT = "(entfernt)"
# Schluessel, deren Wert immer wegfaellt (Kleinschreibung verglichen)
GEHEIM_SCHLUESSEL = frozenset({"pass", "password", "passwort", "token", "jwt", "secret"})
# Kalender-Abos: der Pfad ist der Zugang (Google "private-...", iCloud
# "published/2/..."), es bleiben Schema und Host
ABO_SCHLUESSEL = frozenset({"url", "ical_url", "holiday_url"})
ABO_ABSCHNITT = "calendar"
# Standort des Hauses
ORT_SCHLUESSEL = frozenset({"lat", "lon", "latitude", "longitude"})
# Kuerzere Werte schwaerzt schwaerzen() nicht im freien Text: "1" oder "ab"
# stuenden sonst ueberall
SCHWAERZEN_MIN = 4
# Benutzer und Kennwort in einer Adresse (http://user:pass@host)
_ZUGANG_IN_ADRESSE = re.compile(r"(?P<schema>[a-z][a-z0-9+.-]*://)(?P<zugang>[^/@\s]+)@", re.I)


class LogPuffer(logging.Handler):
    """Die letzten LOG_ZEILEN Log-Eintraege im Speicher, mit Zeitpunkt."""

    def __init__(self, zeilen: int = LOG_ZEILEN):
        super().__init__()
        self._eintraege: collections.deque = collections.deque(maxlen=zeilen)
        self.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self._eintraege.append((record.created, self.format(record)))
        except Exception:      # ein Log-Eintrag darf nie etwas anderes stoeren
            self.handleError(record)

    def zeilen(self, minuten: float = LOG_MINUTEN, jetzt: float | None = None) -> list[str]:
        grenze = (time.time() if jetzt is None else jetzt) - minuten * 60
        return [text for wann, text in list(self._eintraege) if wann >= grenze]


# Der eine Puffer des Servers (webvisu haengt ihn an den Root-Logger)
LOG = LogPuffer()


def _adresse_kuerzen(wert: str) -> str:
    """Kalender-Abo -> Schema und Host, der Rest ist der Zugang."""
    try:
        teile = urlsplit(wert.strip())
    except ValueError:
        return ENTFERNT
    if not teile.scheme or not teile.hostname:
        return ENTFERNT
    return f"{teile.scheme}://{teile.hostname}/{ENTFERNT}"


def _ohne_zugang(text: str, gefunden: set) -> str:
    """Benutzer:Kennwort aus Adressen im Text streichen (gefunden merkt sie)."""
    def weg(m):
        gefunden.add(m.group("zugang"))
        return m.group("schema") + ENTFERNT + "@"
    return _ZUGANG_IN_ADRESSE.sub(weg, text)


def bereinigen(obj, pfad: tuple = ()) -> tuple:
    """Kopie ohne Geheimnisse -> (daten, {gefundene Werte}). Die Werte braucht
    schwaerzen(), um sie auch im freien Text (Log) zu finden."""
    gefunden: set = set()

    def gang(o, p):
        if isinstance(o, dict):
            out = {}
            for k, v in o.items():
                name = str(k).lower()
                if v in (None, "") or isinstance(v, bool):
                    out[k] = v
                elif name in GEHEIM_SCHLUESSEL:
                    if isinstance(v, (str, int, float)):
                        gefunden.add(str(v))
                    out[k] = ENTFERNT
                elif name in ORT_SCHLUESSEL:
                    # nicht schwaerzen(): eine Zahl wie 48.2 stuende auch in Messwerten
                    out[k] = ENTFERNT
                elif name in ABO_SCHLUESSEL and ABO_ABSCHNITT in p and isinstance(v, str):
                    gefunden.add(v)
                    out[k] = _adresse_kuerzen(v)
                else:
                    out[k] = gang(v, p + (name,))
            return out
        if isinstance(o, list):
            return [gang(v, p) for v in o]
        if isinstance(o, str):
            return _ohne_zugang(o, gefunden)
        return o
    return gang(obj, tuple(str(x).lower() for x in pfad)), gefunden


def kodierungen(wert: str) -> set:
    """Der Wert und wie er in Adressen und Formularen kodiert im Log stehen
    kann (Pfad, Abfrage, Formular)."""
    return {wert, quote(wert), quote(wert, safe=""), quote_plus(wert), quote_plus(wert, safe="")}


def schwaerzen(text: str, geheimnisse) -> str:
    """Jeden bekannten geheimen Wert, auch URL-kodiert (kodierungen), im Text
    ersetzen, laengste zuerst, damit kein Rest eines laengeren stehen bleibt."""
    werte = set()
    for g in geheimnisse:
        g = str(g)
        if len(g) >= SCHWAERZEN_MIN:
            werte |= kodierungen(g)
    for g in sorted(werte, key=len, reverse=True):
        text = text.replace(g, ENTFERNT)
    return _ohne_zugang(text, set())


def _uhr(sekunden) -> str:
    return datetime.fromtimestamp(sekunden).strftime("%d.%m.%Y %H:%M:%S") if sekunden else ""


def zusammenfassung(d: dict) -> list[str]:
    """Ein Satz je Verbindung und je Auffaelligkeit, oben in diagnose.md."""
    saetze = []
    ms = d.get("miniserver") or {}
    if not ms.get("host"):
        saetze.append("Kein Miniserver eingetragen.")
    elif not ms.get("struktur"):
        saetze.append(f"Miniserver {ms['host']}: noch keine Struktur geladen"
                      + (f" (letzter Fehler: {ms['fehler']})." if ms.get("fehler") else "."))
    elif ms.get("verbunden"):
        saetze.append(f"Miniserver {ms['host']} verbunden.")
    elif not ms.get("weg_seit"):
        saetze.append(f"Miniserver {ms['host']} nicht verbunden (noch kein Versuch abgeschlossen).")
    else:
        satz = f"Miniserver {ms['host']} seit {_uhr(ms.get('weg_seit'))} nicht erreichbar"
        if ms.get("bestaetigt"):
            satz += f", letzte Nachricht {_uhr(ms['bestaetigt'])}"
        saetze.append(satz + (f" (Fehler: {ms['fehler']})." if ms.get("fehler") else "."))
    for a in d.get("audioserver") or []:
        if a.get("verbunden"):
            art = "gekoppelt" if a.get("gekoppelt") else ("nicht gekoppelt" if a.get("gekoppelt") is False
                                                          else "Kopplung unbekannt")
            saetze.append(f"Audioserver {a['host']} verbunden ({art}, "
                          + ("angemeldet" if a.get("angemeldet") else "nicht angemeldet") + ").")
        else:
            saetze.append(f"Audioserver {a['host']} nicht verbunden.")
    srv = d.get("server") or {}
    beendet = [n for n, s in (srv.get("aufgaben") or {}).items() if s != "läuft"]
    if beendet:
        saetze.append("Hintergrundaufgaben beendet: " + ", ".join(beendet) + " (Neustart nötig).")
    saetze.append(f"{srv.get('panels', 0)} Panel-Verbindung(en) offen.")
    g = d.get("geraet")
    if g:
        satz = f"Gerät „{g['name']}“ ({g.get('typ') or 'unbekannt'}) " + ("online" if g.get("online") else "offline")
        if g.get("ansicht"):
            satz += f", Ansicht „{g['ansicht']}“"
        saetze.append(satz + ".")
    return saetze


# Zeitpunkte (Unix-Sekunden) in den Angaben: diagnose.md zeigt sie als Uhrzeit,
# diagnose.json laesst sie maschinenlesbar
ZEIT_SCHLUESSEL = frozenset({"verbunden_seit", "weg_seit", "bestaetigt", "zuletzt"})


def _abschnitt(titel: str, werte: dict) -> list[str]:
    zeilen = [f"## {titel}", ""]
    for k, v in werte.items():
        if isinstance(v, bool):
            v = "ja" if v else "nein"
        elif k in ZEIT_SCHLUESSEL and isinstance(v, (int, float)):
            v = _uhr(v)
        elif isinstance(v, (dict, list)):
            v = json.dumps(v, ensure_ascii=False)
        zeilen.append(f"- **{k}:** {v if v not in (None, '') else '–'}")
    return zeilen + [""]


def markdown(d: dict) -> str:
    """diagnose.md: Zusammenfassung, dann je Bereich die Angaben."""
    v = d.get("version") or {}
    try:
        erstellt = datetime.fromisoformat(d.get("erstellt") or "").strftime("%d.%m.%Y %H:%M:%S")
    except ValueError:
        erstellt = d.get("erstellt") or ""
    zeilen = [f"# LoxPanel-Diagnose vom {erstellt}", "",
              f"Version {v.get('version') or '?'}, Commit {v.get('commit') or '?'}"
              + (f", gebaut {v['gebaut']}" if v.get("gebaut") else ""), "",
              "## Zusammenfassung", ""]
    zeilen += [f"- {s}" for s in zusammenfassung(d)] + [""]
    if d.get("geraet"):
        zeilen += _abschnitt("Gerät", d["geraet"])
    if d.get("ansicht"):
        zeilen += _abschnitt("Ansicht", d["ansicht"])
    zeilen += _abschnitt("Miniserver", d.get("miniserver") or {})
    for a in d.get("audioserver") or []:
        zeilen += _abschnitt(f"Audioserver {a.get('host', '')}", a)
    zeilen += _abschnitt("Server", d.get("server") or {})
    if d.get("geraete") is not None:
        zeilen += ["## Alle Geräte", ""]
        zeilen += [f"- {g['name']} ({g.get('typ') or '?'}): " + ("online" if g.get("online") else "offline")
                   + (f", Ansicht „{g['ansicht']}“" if g.get("ansicht") else "") for g in d["geraete"]] or ["- keine"]
        zeilen.append("")
    zeilen += ["## Weitere Dateien", "",
               "- `diagnose.json`: alle Angaben maschinenlesbar",
               "- `einstellungen/`: die Einstellungsdateien des Servers",
               f"- `log.txt`: die letzten Log-Zeilen (höchstens {LOG_MINUTEN} Minuten, {LOG_ZEILEN} Zeilen)", "",
               "Kennwörter, Tokens, Kalender-Abos (bis auf den Host), Zugangsdaten in Adressen und der "
               f"Standort sind entfernt und stehen als „{ENTFERNT}“ da.", ""]
    return "\n".join(zeilen)


def paket(daten: dict, einstellungen: dict, log_zeilen: list[str], geheimnisse=()) -> bytes:
    """Das ZIP. einstellungen: {Dateiname: Inhalt (dict) oder None, wenn
    unlesbar}. geheimnisse: Werte, die zusaetzlich zu den in daten und
    einstellungen gefundenen geschwaerzt werden (etwa das Token im Speicher)."""
    daten, g1 = bereinigen(daten)
    saubere = {}
    alle = set(geheimnisse) | g1
    for name, inhalt in einstellungen.items():
        if inhalt is None:
            continue
        saubere[name], g = bereinigen(inhalt)
        alle |= g
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("diagnose.md", schwaerzen(markdown(daten), alle))
        z.writestr("diagnose.json", schwaerzen(json.dumps(daten, ensure_ascii=False, indent=2), alle) + "\n")
        for name, inhalt in saubere.items():
            z.writestr(f"einstellungen/{name}",
                       schwaerzen(json.dumps(inhalt, ensure_ascii=False, indent=2), alle) + "\n")
        z.writestr("log.txt", schwaerzen("\n".join(log_zeilen), alle) + "\n")
    return buf.getvalue()
