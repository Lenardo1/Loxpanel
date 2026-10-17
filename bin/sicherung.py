"""Sicherung der Konfiguration (Einstellungen -> Sicherung): das Backup als ZIP
ohne Kennwoerter (_backup_zip, mit Vermerk, wo welche fehlen) und das
Einspielen (_sicherung_lesen -> _sicherung_pruefen -> _sicherung_schreiben):
jede Datei wird gelesen, auf Groesse, Tiefe, Typen und Inhalt geprueft, durch
dieselben Sanitizer wie beim Speichern gezogen (konfig.py), vorhandene
Kennwoerter bleiben, wo der Vermerk sie nennt, und erst dann geschrieben.
Die Routen /api/backup und /api/restore liegen in webvisu.py und rufen hier.

Importiert webvisu.py nicht."""
from __future__ import annotations

import copy
import io
import json
import logging
import math
import os
import zipfile
import zlib
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING
from urllib.parse import urlsplit

from audioserver import make_backend
from bausteine.gemeinsam import _clean
from konfig import (
    CFG_FILE, THEME_FILE, _SECRET_KEYS, _atomic_write, _audio_config, _audiometa_config,
    _calendar_config, _cfg_datei, _color_ok, _intercom_config, _is_tab, _night_config, _panels_doc,
    _panels_verworfen, _sanitize_categories, _sanitize_devices, _sanitize_panels, _write_cfg,
    load_theme)

if TYPE_CHECKING:   # nur fuer die Typangabe, kein Import zur Laufzeit (webvisu importiert hierher)
    from webvisu import App

log = logging.getLogger("loxpanel.sicherung")

# Einstellungen, die /api/backup einpackt (alles, was LoxPanel in config/ schreibt).
BACKUP_FILES = ("loxpanel.cfg", "panels.json", "theme.json")

# Maschinenlesbarer Vermerk in der Sicherung: je Datei die Pfade der entfernten
# Kennwoerter. /api/restore setzt nur an diesen Stellen vorhandene wieder ein.
BACKUP_VERMERK = "sicherung.json"

BACKUP_FORMAT = 1

# Lesbare Beschreibung in der Sicherung. Sie listet die entfernten Kennwoerter
# als Zeilen "  - <datei>: <pfad>" - aeltere Sicherungen ohne sicherung.json
# haben nur diese Liste.
BACKUP_LIESMICH = "LIESMICH.txt"

# Die Zeile vor der Liste; so schreibt sie auch das aeltere Format. Fehlt sie
# (Datei in einem Editor anders kodiert gespeichert), ist die Liste nicht
# verlaesslich und zaehlt nicht.
LIESMICH_KENNWOERTER = "Kennwörter sind entfernt (leer), weil diese Datei ohne Anmeldung"


def _ohne_kennwoerter(obj, pfad: tuple = ()) -> tuple:
    """Kopie ohne Kennwoerter (leer statt Wert) -> (daten, [entfernte Pfade]).
    Ein Pfad ist ein Tupel aus Schluesseln und Listen-Indizes."""
    if isinstance(obj, dict):
        out, weg = {}, []
        for k, v in obj.items():
            p = pfad + (k,)
            if str(k).lower() in _SECRET_KEYS and v not in (None, ""):
                out[k] = ""
                weg.append(p)
            else:
                out[k], sub = _ohne_kennwoerter(v, p)
                weg += sub
        return out, weg
    if isinstance(obj, list):
        out, weg = [], []
        for i, v in enumerate(obj):
            w, sub = _ohne_kennwoerter(v, pfad + (i,))
            out.append(w)
            weg += sub
        return out, weg
    return obj, []


def _pfad_text(pfad) -> str:
    """Pfad als Text, wie ihn die LIESMICH.txt nennt: a.b[0].c"""
    s = ""
    for t in pfad:
        s += f"[{t}]" if isinstance(t, int) else (f".{t}" if s else str(t))
    return s


def _backup_zip(cfgdir: Path) -> bytes:
    """Die Einstellungs-Dateien als ZIP, Kennwoerter entfernt, mit LIESMICH.txt.
    Eine Datei, die kein lesbares JSON ist, bleibt draussen: ungeprueft koennte
    sie ein Kennwort enthalten."""
    buf, drin, weg, fehlt, vermerk = io.BytesIO(), [], [], [], {}
    jetzt = datetime.now()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for name in BACKUP_FILES:
            f = cfgdir / name
            if not f.is_file():
                continue
            try:
                daten, entfernt = _ohne_kennwoerter(json.loads(f.read_text(encoding="utf-8")))
            except (OSError, ValueError) as err:
                log.warning("Backup: %s nicht lesbar (%s) - nicht enthalten", name, err)
                fehlt.append(name)
                continue
            z.writestr(name, json.dumps(daten, ensure_ascii=False, indent=2) + "\n")
            drin.append(name)
            weg += [f"{name}: {_pfad_text(p)}" for p in entfernt]
            vermerk[name] = [list(p) for p in entfernt]
        zeilen = [f"LoxPanel-Einstellungen vom {jetzt:%d.%m.%Y %H:%M}", "",
                  "Enthalten: " + (", ".join(drin) or "keine (noch nichts gespeichert)")]
        if fehlt:
            zeilen.append("Nicht enthalten, weil nicht lesbar: " + ", ".join(fehlt))
        zeilen += ["", LIESMICH_KENNWOERTER, "herunterzuladen ist. Entfernt wurden:"]
        zeilen += [f"  - {p}" for p in weg] or ["  (keine gesetzt)"]
        zeilen += ["", "Zurückspielen: im Konfigurator unter Einstellungen → Sicherung diese",
                   "ZIP-Datei einspielen. Kennwörter, die dort schon eingetragen sind,",
                   "bleiben, solange ihr Ziel gleich bleibt (Miniserver: Host und Benutzer,",
                   "Kamera: Adresse und Benutzer, Display: Host und Treiber); fehlende",
                   "nennt der Konfigurator danach. Von Hand geht es auch: die Dateien in den",
                   "Config-Ordner legen (Unraid: appdata/loxpanel, im Container /app/config)",
                   "und LoxPanel neu starten. " + BACKUP_VERMERK + " vermerkt für das",
                   "Einspielen, wo Kennwörter entfernt sind."]
        z.writestr(BACKUP_LIESMICH, "\n".join(zeilen) + "\n")
        z.writestr(BACKUP_VERMERK, json.dumps(
            {"format": BACKUP_FORMAT, "erstellt": jetzt.isoformat(timespec="seconds"),
             "dateien": drin, "kennwoerter_entfernt": vermerk},
            ensure_ascii=False, indent=2) + "\n")
    return buf.getvalue()


# Groesste Datei, die das Einspielen annimmt (entpackt). Die Einstellungsdateien
# haben wenige KB; die Grenze haelt eine ZIP-Datei, die sich beim Entpacken
# aufblaeht, vom Speicher fern. Sie greift nur ungepackt und bei Deflate: Bei
# bzip2 und LZMA entpackt zipfile den ganzen Strom, bevor eine Grenze greift.
# Darum sind nur diese beiden Verfahren erlaubt (so packen _backup_zip,
# Windows und macOS).
RESTORE_MAX_DATEI = 2 * 1024 * 1024

RESTORE_VERFAHREN = (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED)

# Tiefste Verschachtelung in einer Sicherung. Die Einstellungsdateien kommen
# mit etwa sechs Ebenen aus; tiefere braechten Kopieren und Pruefen an die
# Rekursionsgrenze.
RESTORE_MAX_TIEFE = 32

# Meiste Eintraege (Werte, Listen, Objekte) je Datei. Die Beispiel-Dateien
# haben unter 100; eine sehr grosse, voll gestaltete Anlage (20 Profile mit je
# 500 Kachel-Einstellungen, Ausblend-Listen, Raeumen) kommt auf rund 100.000.
# Mehr kann eine ZIP-Datei von wenigen KB trotzdem tragen (Wiederholungen
# packen sich fast auf nichts) - und jeder Eintrag kostet beim Pruefen,
# Kopieren und Schreiben Zeit, in der der Server nichts anderes tut.
RESTORE_MAX_EINTRAEGE = 200_000

# Was ein Kennwort an sein Ziel bindet: Ein vorhandenes Kennwort bleibt beim
# Einspielen nur, wenn diese Angaben gleich bleiben - sonst ginge es an einen
# anderen Host oder Benutzer.
_KENNWORT_ZIEL = ("host", "url", "user", "driver")

# Wo LoxPanel Kennwoerter fuehrt ("*" = jeder Schluessel). Bei einer aelteren
# Sicherung ohne Vermerk gelten nur hier leere Kennwoerter als entfernt.
_KENNWORT_ORTE = {"loxpanel.cfg": (("miniserver", "pass"), ("intercom", "*", "pass")),
                  "panels.json": (("devices", "*", "display", "password"),)}

# Groesste ganze Zahl in einer Sicherung (in JavaScript noch genau). Groessere
# lassen int()/float() im Server ueberlaufen.
_GROESSTE_ZAHL = 2 ** 53

# Erwartete Typen der Abschnitte von loxpanel.cfg, die der Server liest. Ein
# fehlendes Feld ist erlaubt; "port" = ganze Zahl 1..65535.
_CFG_TYPEN = {
    "miniserver": {"host": str, "user": str, "pass": str, "port": "port", "verify_tls": bool},
    "audio": {"host": (str, type(None)), "port": "port", "enabled": bool},
    "audiometa": {"enabled": bool},
    "intercom": {},
    "night": {"control": (str, type(None))},
    "calendar": {"sources": list, "ical_url": (str, type(None)), "holiday_url": (str, type(None)),
                 "name": (str, type(None)), "colors": bool, "days": int, "sv_events": int,
                 "fore_days": int, "lat": (int, float, type(None)), "lon": (int, float, type(None))},
}


def _keine_konstante(c):
    raise ValueError(f"{c} ist keine Zahl")


def _utf8_ok(s: str) -> bool:
    try:
        s.encode("utf-8")
    except UnicodeEncodeError:
        return False
    return True


def _inhalt_pruefen(obj, datei: str) -> None:
    """Was der Server aus einer Sicherung nicht verkraftet: NaN, Unendlich und
    ganze Zahlen ueber _GROESSTE_ZAHL (int()/float(), JSON.parse im
    Konfigurator), Text, der sich nicht als UTF-8 schreiben laesst (einzelne
    Surrogate), zu tiefe Verschachtelung und zu viele Eintraege. Ohne
    Rekursion; den Pfad baut erst die Fehlermeldung, sonst kostete jeder
    Knoten seine Tiefe."""
    stapel = [(obj, None, None, 0)]          # (wert, schluessel, eltern, tiefe)
    anzahl = 0

    def pfad(e) -> str:
        teile = []
        while e is not None and e[1] is not None:
            teile.append(e[1])
            e = e[2]
        s = _pfad_text(teile[::-1]) or "oberste Ebene"
        return s if len(s) <= 80 else s[:80] + " …"

    while stapel:
        e = stapel.pop()
        v, tiefe = e[0], e[3]
        anzahl += 1
        if anzahl > RESTORE_MAX_EINTRAEGE:
            grenze = f"{RESTORE_MAX_EINTRAEGE:,}".replace(",", ".")
            raise ValueError(f"{datei} hat mehr als {grenze} Einträge, mehr als eine "
                             "LoxPanel-Sicherung haben kann.")
        if isinstance(v, (dict, list)):
            if tiefe >= RESTORE_MAX_TIEFE:
                raise ValueError(f"{datei}: {pfad(e)} ist zu tief verschachtelt.")
            for k, w in (v.items() if isinstance(v, dict) else enumerate(v)):
                if isinstance(k, str) and not _utf8_ok(k):
                    raise ValueError(f"{datei}: {pfad(e)} enthält ungültige Zeichen.")
                stapel.append((w, k, e, tiefe + 1))
        elif (isinstance(v, float) and not math.isfinite(v)) or \
                (isinstance(v, int) and not isinstance(v, bool) and abs(v) > _GROESSTE_ZAHL):
            raise ValueError(f"{datei}: {pfad(e)} ist keine gültige Zahl.")
        elif isinstance(v, str) and not _utf8_ok(v):
            raise ValueError(f"{datei}: {pfad(e)} enthält ungültige Zeichen.")


def _sicherung_lesen(daten: bytes) -> tuple:
    """ZIP aus /api/backup lesen und pruefen -> ({datei: objekt}, vermerk).
    vermerk sagt, wo Kennwoerter entfernt wurden: {"json": Inhalt von
    sicherung.json oder None, "liesmich": Listenzeilen der LIESMICH.txt als
    frozenset oder None} (siehe _vermerk_pfade). Ordner in der ZIP-Datei sind
    egal (neu gepackt), Fremdes wird ignoriert. Wirft ValueError mit lesbarer
    Meldung; schreibt nichts."""
    try:
        z = zipfile.ZipFile(io.BytesIO(daten))
    except zipfile.BadZipFile as err:
        raise ValueError("Das ist keine ZIP-Datei.") from err
    except (NotImplementedError, EOFError, OSError, ValueError) as err:
        # z. B. eine Versionsangabe, die zipfile nicht kennt
        raise ValueError(f"Die ZIP-Datei lässt sich nicht lesen ({err}).") from err
    gesucht = set(BACKUP_FILES) | {BACKUP_VERMERK, BACKUP_LIESMICH}
    gefunden: dict = {}
    gesehen: set = set()
    liesmich = None
    with z:
        for info in z.infolist():
            teile = PurePosixPath(info.filename.replace("\\", "/")).parts
            if info.is_dir() or not teile or teile[-1] not in gesucht or "__MACOSX" in teile:
                continue
            name = teile[-1]
            if name in gesehen:
                raise ValueError(f"{name} steckt mehrmals in der ZIP-Datei.")
            gesehen.add(name)
            if info.compress_type not in RESTORE_VERFAHREN:
                raise ValueError(f"{name} ist mit einem nicht unterstützten Verfahren gepackt "
                                 "(erlaubt: Deflate oder ungepackt).")
            if info.file_size > RESTORE_MAX_DATEI:
                raise ValueError(f"{name} ist zu groß für eine LoxPanel-Sicherung.")
            try:
                with z.open(info) as fh:
                    roh = fh.read(RESTORE_MAX_DATEI + 1)
            except (zipfile.BadZipFile, zlib.error, RuntimeError, NotImplementedError,
                    EOFError, OSError) as err:
                raise ValueError(f"{name} lässt sich nicht entpacken ({err}).") from err
            if len(roh) > RESTORE_MAX_DATEI:
                raise ValueError(f"{name} ist zu groß für eine LoxPanel-Sicherung.")
            if name == BACKUP_LIESMICH:
                # Nur an \n trennen: splitlines() bricht auch an Zeichen wie
                # \x0c oder \x85, die in einem Geraetenamen stehen koennen.
                zeilen = [z.rstrip("\r").strip() for z in roh.decode("utf-8-sig", errors="replace").split("\n")]
                if LIESMICH_KENNWOERTER in zeilen:
                    liesmich = frozenset(z[2:] for z in zeilen if z.startswith("- "))
                continue
            try:
                obj = json.loads(roh.decode("utf-8-sig"), parse_constant=_keine_konstante)
            except (UnicodeDecodeError, ValueError, RecursionError) as err:
                raise ValueError(f"{name} ist kein gültiges JSON ({err}).") from err
            if not isinstance(obj, dict):
                raise ValueError(f"{name} enthält kein JSON-Objekt.")
            _inhalt_pruefen(obj, name)
            gefunden[name] = obj
    vermerk = {"json": gefunden.pop(BACKUP_VERMERK, None), "liesmich": liesmich}
    if not gefunden:
        raise ValueError("Keine LoxPanel-Sicherung: In der ZIP-Datei steckt weder "
                         + " noch ".join(BACKUP_FILES) + ".")
    return gefunden, vermerk


def _typ_ok(v, erwartet) -> bool:
    if erwartet == "port":
        return isinstance(v, int) and not isinstance(v, bool) and 1 <= v <= 65535
    typen = erwartet if isinstance(erwartet, tuple) else (erwartet,)
    if isinstance(v, bool) and bool not in typen:
        return False
    return isinstance(v, typen)


def _cfg_pruefen(cfg: dict) -> None:
    """Typen der Abschnitte von loxpanel.cfg pruefen, die der Server liest
    (_CFG_TYPEN, dazu intercom-Eintraege und Kalenderquellen). Ports als
    Ziffern-Text werden zu Zahlen. Wirft ValueError mit dem Pfad."""
    for abschnitt, felder in _CFG_TYPEN.items():
        if abschnitt not in cfg:
            continue
        sec = cfg[abschnitt]
        if not isinstance(sec, dict):
            raise ValueError(f"loxpanel.cfg: „{abschnitt}“ muss ein Objekt sein.")
        for k, erwartet in felder.items():
            if k not in sec:
                continue
            if erwartet == "port" and isinstance(sec[k], str) and sec[k].strip().isdigit():
                sec[k] = int(sec[k].strip())
            if not _typ_ok(sec[k], erwartet):
                raise ValueError(f"loxpanel.cfg: {abschnitt}.{k} hat einen ungültigen Wert.")
    for uuid, e in (cfg.get("intercom") or {}).items():
        if str(uuid).startswith("_") or isinstance(e, str):
            continue
        # user wird zu HTTP-Basic-Auth: kein Doppelpunkt, sonst wirft aiohttp
        if not isinstance(e, dict) or not all(isinstance(e.get(k, ""), str) for k in ("url", "user", "pass")) \
                or ":" in e.get("user", ""):
            raise ValueError(f"loxpanel.cfg: intercom.{uuid} hat einen ungültigen Wert.")
    for i, q in enumerate((cfg.get("calendar") or {}).get("sources") or []):
        if isinstance(q, str):
            continue
        if not isinstance(q, dict) or not all(isinstance(q.get(k), (str, type(None)))
                                              for k in ("url", "name", "color", "key")):
            raise ValueError(f"loxpanel.cfg: calendar.sources[{i}] hat einen ungültigen Wert.")


def _leere_geheimnisse(obj):
    """Pfade aller leeren Kennwort-Felder (_SECRET_KEYS) in obj."""
    stapel = [((), obj)]
    while stapel:
        pfad, knoten = stapel.pop()
        if isinstance(knoten, dict):
            for k, v in reversed(list(knoten.items())):
                if str(k).lower() in _SECRET_KEYS and v in (None, ""):
                    yield pfad + (k,)
                else:
                    stapel.append((pfad + (k,), v))
        elif isinstance(knoten, list):
            stapel += [(pfad + (i,), v) for i, v in reversed(list(enumerate(knoten)))]


def _vermerk_pfade(vermerk, name: str, obj):
    """Pfade der entfernten Kennwoerter einer Datei (obj = ihr Inhalt), None
    wenn die Sicherung es nicht sagt. Erste Quelle ist sicherung.json.
    Aeltere Sicherungen haben nur die Liste in der LIESMICH.txt; sie wird
    nicht zurueckgelesen, sondern jede leere Kennwort-Stelle der Datei als
    Text damit verglichen - ein Punkt im Geraetenamen bringt so nichts
    durcheinander."""
    vermerk = vermerk if isinstance(vermerk, dict) else {}
    eintrag = (vermerk.get("json") or {}).get("kennwoerter_entfernt")
    if isinstance(eintrag, dict) and isinstance(eintrag.get(name, []), list):
        return [tuple(p) for p in eintrag.get(name, [])
                if isinstance(p, list) and p
                and all(isinstance(t, (str, int)) and not isinstance(t, bool) for t in p)]
    if isinstance(vermerk.get("liesmich"), frozenset):
        return [p for p in _leere_geheimnisse(obj) if f"{name}: {_pfad_text(p)}" in vermerk["liesmich"]]
    return None


def _leere_kennwoerter(obj, datei: str) -> list:
    """Aeltere Sicherung ohne Vermerk: leere Kennwoerter an den bekannten
    Stellen (_KENNWORT_ORTE) neben einem Ziel (Host oder URL gesetzt)."""
    out = []
    for muster in _KENNWORT_ORTE.get(datei, ()):
        orte = [((), obj)]
        for teil in muster[:-1]:
            weiter = []
            for p, knoten in orte:
                if isinstance(knoten, dict):
                    weiter += [(p + (k,), knoten[k]) for k in (list(knoten) if teil == "*" else [teil])
                               if k in knoten]
            orte = weiter
        key = muster[-1]
        for p, knoten in orte:
            if isinstance(knoten, dict) and key in knoten and knoten[key] in (None, "") \
                    and any(str(knoten.get(z) or "").strip() for z in ("host", "url")):
                out.append(p + (key,))
    return out


def _knoten(obj, pfad: tuple):
    """Wert an einem Pfad (Schluessel/Indizes), None wenn es ihn nicht gibt."""
    for t in pfad:
        if isinstance(obj, dict) and isinstance(t, str):
            obj = obj.get(t)
        elif isinstance(obj, list) and isinstance(t, int) and 0 <= t < len(obj):
            obj = obj[t]
        else:
            return None
    return obj


def _kennwoerter_einsetzen(neu, alt, pfade, nur_wo_eins_war: bool = False) -> tuple:
    """Setzt entfernte Kennwoerter aus dem bisherigen Stand wieder ein, aber nur
    bei gleichem Ziel (_KENNWORT_ZIEL). Veraendert neu -> (behalten, fehlen)
    als Pfadlisten. nur_wo_eins_war: aeltere Sicherung, bei der unklar ist, ob
    an der Stelle je ein Kennwort stand - fehlend ist es dann nur, wenn der
    bisherige Stand dort eines hatte."""
    behalten, fehlen = [], []
    for pfad in pfade:
        if not pfad or not isinstance(pfad[-1], str):
            continue
        n, a, key = _knoten(neu, pfad[:-1]), _knoten(alt, pfad[:-1]), pfad[-1]
        if not isinstance(n, dict) or n.get(key) not in (None, ""):
            continue                      # Vermerk passt nicht zur Datei bzw. Kennwort steht drin
        wert = a.get(key) if isinstance(a, dict) else None
        if wert not in (None, "") and all(str(n.get(z) or "").strip() == str(a.get(z) or "").strip()
                                          for z in _KENNWORT_ZIEL):
            n[key] = wert
            behalten.append(pfad)
        elif wert not in (None, "") or not nur_wo_eins_war:
            fehlen.append(pfad)
    return behalten, fehlen


def _kennwort_ziel(datei: str, pfad: tuple, namen: dict) -> dict:
    """Wozu ein Kennwort gehoert, fuer die Anzeige im Konfigurator."""
    if datei == "loxpanel.cfg" and pfad == ("miniserver", "pass"):
        return {"art": "miniserver"}
    if datei == "loxpanel.cfg" and len(pfad) == 3 and pfad[0] == "intercom":
        return {"art": "kamera", "name": namen.get(pfad[1], str(pfad[1]))}
    if datei == "panels.json" and len(pfad) == 4 and pfad[0] == "devices" and pfad[2] == "display":
        return {"art": "display", "name": str(pfad[1])}
    return {"art": "sonst", "name": f"{datei}: {_pfad_text(pfad)}"}


def _profil_pruefen(datei: str, wer: str, fn, *args):
    """Vorhandene Sanitizer laufen lassen; stuerzen sie an einem falschen Typ
    ab, ist die Sicherung kaputt -> ValueError mit dem Ort."""
    try:
        return fn(*args)
    except (TypeError, AttributeError, ValueError, OverflowError, KeyError) as err:
        raise ValueError(f"{datei}: {wer} hat einen ungültigen Wert ({err}).") from err


def _zugang_komplett(ms) -> bool:
    return isinstance(ms, dict) and all(str(ms.get(k) or "").strip() for k in ("host", "user", "pass"))


def _sicherung_pruefen(app: "App", dateien: dict, vermerk) -> dict:
    """Alles pruefen und vorbereiten, nichts schreiben -> Plan fuer
    _sicherung_schreiben. Wirft ValueError, wenn die Sicherung nicht passt.
    behalten, fehlen und verworfen tragen die Datei mit, damit die Antwort
    nach einem Schreibfehler nur Geschriebenes nennt. Vom laufenden Server
    braucht es nur controls und devices; api_restore uebergibt dafuer eine
    Momentaufnahme, weil es hier in einem Thread laeuft."""
    namen = {u: _clean(c.get("name")) or u for u, c in app.controls.items()}
    plan: dict = {"dateien": {}, "behalten": [], "fehlen": [], "verworfen": [], "miniserver": "",
                  "ms_alt": None, "ms_ziel": None, "namen": namen}

    if "loxpanel.cfg" in dateien:
        cfg = copy.deepcopy(dateien["loxpanel.cfg"])
        _cfg_pruefen(cfg)
        alt = _cfg_datei()
        pfade = _vermerk_pfade(vermerk, "loxpanel.cfg", cfg)
        behalten, fehlen = _kennwoerter_einsetzen(
            cfg, alt, _leere_kennwoerter(cfg, "loxpanel.cfg") if pfade is None else pfade, pfade is None)
        ms = cfg.get("miniserver") if isinstance(cfg.get("miniserver"), dict) else {}
        alt_ms = alt.get("miniserver") if isinstance(alt.get("miniserver"), dict) else None
        alt_host = bool(str((alt_ms or {}).get("host") or "").strip())
        env = bool(os.environ.get("LOXPANEL_MS_HOST"))
        plan["ms_alt"] = alt_ms
        # Einen laufenden Zugang nie fuer einen schlechteren aufgeben: Eine
        # Sicherung ohne Miniserver liesse den Server auf Umgebungsvariablen
        # oder das Beispiel zurueckfallen; ein Ziel ohne Kennwort waere nach
        # dem naechsten Neustart tot. In beiden Faellen bleibt der bisherige
        # Abschnitt, das Ziel der Sicherung nennt die Antwort.
        if not str(ms.get("host") or "").strip():
            plan["miniserver"] = "behalten" if alt_host else ("umgebung" if env else "keiner")
        elif not _zugang_komplett(ms) and (_zugang_komplett(alt_ms) or (env and not alt_host)):
            plan["miniserver"] = ("umgebung" if not _zugang_komplett(alt_ms)
                                  else "kein_kennwort_behalten" if str(ms.get("user") or "").strip()
                                  else "unvollstaendig_behalten")
            plan["ms_ziel"] = {"host": str(ms.get("host")).strip(), "user": str(ms.get("user") or "")}
        if plan["miniserver"]:
            if alt_ms is not None:
                cfg["miniserver"] = alt_ms
            else:
                cfg.pop("miniserver", None)
            fehlen = [p for p in fehlen if p[:1] != ("miniserver",)]
        plan["dateien"]["loxpanel.cfg"] = cfg
        plan["behalten"] += [("loxpanel.cfg", p) for p in behalten]
        plan["fehlen"] += [("loxpanel.cfg", p) for p in fehlen]

    if "panels.json" in dateien:
        doc = dateien["panels.json"]
        panels, devices = doc.get("panels", {}), copy.deepcopy(doc.get("devices", {}))
        for k, v in (("panels", panels), ("devices", devices)):
            if not isinstance(v, dict):
                raise ValueError(f"panels.json: „{k}“ muss ein Objekt sein.")
        sauber: dict = {}
        for pid, p in panels.items():
            sauber.update(_profil_pruefen("panels.json", f"Ansicht „{pid}“", _sanitize_panels, {pid: p}))
        roh = {"devices": devices}
        pfade = _vermerk_pfade(vermerk, "panels.json", roh)
        behalten, fehlen = _kennwoerter_einsetzen(
            roh, {"devices": app.devices},
            _leere_kennwoerter(roh, "panels.json") if pfade is None else pfade, pfade is None)
        geraete: dict = {}
        profile = set(sauber)
        for name, d in devices.items():
            geraete.update(_profil_pruefen("panels.json", f"Gerät „{name}“", _sanitize_devices,
                                           {name: d}, profile))
        # Ein Kennwort fuer einen Treiber, der nicht uebernommen wurde, fehlt nicht.
        fehlen = [p for p in fehlen if isinstance(_knoten({"devices": geraete}, p[:-1]), dict)]
        plan["verworfen"] += [("panels.json", t) for t in _panels_verworfen(panels, sauber, namen)]
        plan["dateien"]["panels.json"] = (sauber, geraete)
        plan["behalten"] += [("panels.json", p) for p in behalten]
        plan["fehlen"] += [("panels.json", p) for p in fehlen]

    if "theme.json" in dateien:
        doc = dateien["theme.json"]
        for k in ("states", "categories", "ui"):
            if k in doc and not isinstance(doc[k], dict):
                raise ValueError(f"theme.json: „{k}“ muss ein Objekt sein.")
        ui_roh = {k: v for k, v in (doc.get("ui") or {}).items() if not str(k).startswith("_")}
        tabs_roh = ui_roh.pop("tabs", None)
        if tabs_roh is not None and not isinstance(tabs_roh, list):
            raise ValueError("theme.json: ui.tabs muss eine Liste sein.")
        # Die globale Darstellung mischt sich in jedes Profil (resolve_profile),
        # darum dieselben Pruefungen wie fuer die ui eines Profils.
        ui = _profil_pruefen("theme.json", "„ui“", _sanitize_panels,
                             {"t": {"ui": ui_roh}})["t"].get("ui", {})
        tabs = [t for t in (tabs_roh or []) if isinstance(t, str) and _is_tab(t)][:4]
        if tabs:
            ui["tabs"] = tabs
        # Zustands- und Kategoriefarben landen als CSS im Panel: nur gueltige
        # Farben, Verworfenes wird gemeldet.
        states_roh = {k: v for k, v in (doc.get("states") or {}).items() if not str(k).startswith("_")}
        states = {str(k).strip()[:40]: v.strip() for k, v in states_roh.items() if _color_ok(v)}
        cats_roh = {k: v for k, v in (doc.get("categories") or {}).items() if not str(k).startswith("_")}
        cats = _sanitize_categories(cats_roh)
        theme = {"states": states, "categories": cats, "ui": ui}
        weg = _panels_verworfen(
            {"Darstellung": {"ui": {**ui_roh, **({"tabs": tabs_roh} if tabs_roh else {})}}},
            {"Darstellung": {"ui": ui}}, namen)
        weg += [f"Darstellung: states.{k}" for k, v in states_roh.items() if not _color_ok(v)]
        weg += [f"Darstellung: categories.{k}" for k in cats_roh if str(k).strip()[:40] not in cats]
        plan["verworfen"] += [("theme.json", t) for t in weg]
        plan["dateien"]["theme.json"] = theme

    # Was hier geschrieben wird, muss sich wieder einspielen lassen: _backup_zip
    # packt es im selben Format, und eingerueckt waechst es (eine ZIP von
    # wenigen KB mit 200.000 Werten 30 Ebenen tief -> ueber 10 MiB). Darum
    # stueckweise zaehlen und beim Ueberschreiten aufhoeren, statt erst die
    # ganze Datei zu bauen.
    for name, inhalt in plan["dateien"].items():
        doc = _panels_doc(*inhalt) if name == "panels.json" else inhalt
        groesse = 1                                  # abschliessender Zeilenumbruch
        for stueck in json.JSONEncoder(indent=2, ensure_ascii=False).iterencode(doc):
            groesse += len(stueck.encode("utf-8"))
            if groesse > RESTORE_MAX_DATEI:
                raise ValueError(f"{name} würde nach dem Einspielen größer, als eine "
                                 "LoxPanel-Sicherung sein darf.")
    return plan


def _vorher_sichern(f: Path) -> None:
    """Eine Generation Sicherung vor dem Ueberschreiben (wie panels.json.bak);
    best effort, ein Fehler darf das Einspielen nicht blockieren."""
    try:
        if f.is_file():
            _atomic_write(f.with_name(f.name + ".bak"), f.read_text(encoding="utf-8"))
    except (OSError, ValueError) as err:
        log.warning("%s.bak nicht geschrieben: %s", f.name, err)


async def _sicherung_schreiben(app: "App", plan: dict) -> dict:
    """Plan aus _sicherung_pruefen schreiben und den laufenden Server
    auffrischen, ohne Neustart. Den Kennwort-Abgleich hat _sicherung_pruefen
    mit den Dateien von vorher gemacht; wer waehrenddessen in einem anderen
    Fenster Einstellungen speichert, dessen Aenderung ersetzt das Einspielen
    wie alles andere."""
    dateien, geschrieben, fehler = plan["dateien"], [], ""
    try:
        for name in BACKUP_FILES:
            if name not in dateien:
                continue
            if name == "loxpanel.cfg":
                _vorher_sichern(CFG_FILE)
                _write_cfg(dateien[name])
            elif name == "panels.json":
                app._persist_panels_file(*dateien[name])   # legt selbst panels.json.bak an
            else:
                _vorher_sichern(THEME_FILE)
                _atomic_write(THEME_FILE, json.dumps(dateien[name], indent=2, ensure_ascii=False) + "\n")
            geschrieben.append(name)
    except (OSError, ValueError) as err:
        fehler = str(err)
        log.warning("Sicherung einspielen: Schreiben abgebrochen nach %s: %s", geschrieben or "-", err)

    # Auffrischen, was geschrieben ist - erst alles ohne await, dann der Rest.
    ms_status, ms_fehler = (plan["miniserver"] if "loxpanel.cfg" in geschrieben else ""), ""
    if "loxpanel.cfg" in geschrieben:
        app.night_cfg = _night_config()
        app.intercom_cfg = _intercom_config()
        app.calendar_cfg = _calendar_config()
        app._front_cal_due = 0.0
        app._front_good = {}          # Wetter/Feiertage vom alten Ort nicht als "stale" zeigen
        app._front_refresh.set()
        app.audiometa_cfg = _audiometa_config()
    if "panels.json" in geschrieben:
        app.panels, app.devices = dateien["panels.json"]
    if "theme.json" in geschrieben:
        app.theme = load_theme()
    app._dirty = True

    if "loxpanel.cfg" in geschrieben:
        if not app.audiometa_cfg.get("enabled", True):
            for cl in list(app.audio_clients.values()):
                await cl.close()
            app.audio_clients.clear()
        audio_neu = _audio_config()
        if audio_neu != app.audio_cfg:
            for be in [app.audio, *app.audio_backends.values()]:
                if be is not None:
                    try:
                        await be.close()
                    except Exception as err:
                        log.debug("Audio-Backend schliessen: %s", err)
            app.audio_backends.clear()
            app.audio_cfg = audio_neu
            app.audio = make_backend(audio_neu)
        if not ms_status:
            ms = dateien["loxpanel.cfg"]["miniserver"]
            laufend = (app.host, app.user, app.password, app.port, bool(app.verify_tls))
            neu = (ms.get("host"), ms.get("user"), ms.get("pass"), ms.get("port", 443),
                   bool(ms.get("verify_tls", False)))
            if not str(ms.get("user") or "").strip():
                ms_status = "unvollstaendig"
            elif not ms.get("pass"):
                ms_status = "kein_kennwort"
            elif neu == laufend:
                ms_status = "unveraendert"
            else:
                try:
                    await app.reconnect()
                    ms_status = "verbunden"
                    # Audioserver-Clients merken sich den Benutzer beim Anlegen
                    for cl in list(app.audio_clients.values()):
                        await cl.close()
                    app.audio_clients.clear()
                    app._front_refresh.set()
                except Exception as err:
                    ms_status, ms_fehler = "fehler", str(err)
                    # reconnect() behaelt die alte Verbindung; die Datei soll
                    # sie auch nach einem Neustart liefern. Das war entweder der
                    # Abschnitt der Datei oder - hatte der keinen Host - der
                    # Zugang aus LOXPANEL_MS_* (_config()).
                    alt_ms = plan["ms_alt"]
                    umgebung = bool(os.environ.get("LOXPANEL_MS_HOST")) and \
                        not str((alt_ms or {}).get("host") or "").strip()
                    if _zugang_komplett(alt_ms) or umgebung:
                        try:
                            cfg = _cfg_datei()
                            if alt_ms is None:
                                cfg.pop("miniserver", None)
                            else:
                                cfg["miniserver"] = alt_ms
                            _write_cfg(cfg)
                            ms_status = "fehler_behalten"
                        except (OSError, ValueError) as err2:
                            log.warning("Bisherigen Miniserver-Zugang nicht zurueckgeschrieben: %s", err2)
        if ms_status in ("unveraendert", "kein_kennwort", "unvollstaendig", "fehler"):
            app._zugang_neu = None   # der eingespielte Abschnitt ersetzt einen ungeprueft gespeicherten
    n = await app.push({"t": "reload"})   # offene Panels mit dem neuen Stand neu laden

    # Kameras ohne Namen aus der Struktur (neues Panel, noch nicht verbunden)
    # am Host ihrer URL erkennbar machen statt an der UUID.
    namen = dict(plan["namen"])
    for uuid, e in ((dateien.get("loxpanel.cfg") or {}).get("intercom") or {}).items():
        url = e.get("url") if isinstance(e, dict) else e
        if uuid not in namen and isinstance(url, str):
            try:
                namen[uuid] = urlsplit(url.strip()).hostname or uuid
            except ValueError:
                pass
    behalten = [(d, p) for d, p in plan["behalten"] if d in geschrieben]
    fehlen = [(d, p) for d, p in plan["fehlen"] if d in geschrieben]
    log.info("Sicherung eingespielt: %s (Kennwoerter behalten %d, fehlen %d, Miniserver %s)",
             ", ".join(geschrieben) or "-", len(behalten), len(fehlen), ms_status or "-")
    return {
        "ok": not fehler,
        **({"error": f"Schreiben abgebrochen: {fehler}"} if fehler else {}),
        "dateien": geschrieben,
        "nichtEnthalten": [n_ for n_ in BACKUP_FILES if n_ not in dateien],
        "nichtEingespielt": [n_ for n_ in BACKUP_FILES if n_ in dateien and n_ not in geschrieben],
        "kennwoerter": {"behalten": [_kennwort_ziel(d, p, namen) for d, p in behalten],
                        "fehlen": [_kennwort_ziel(d, p, namen) for d, p in fehlen]},
        "verworfen": [t for d, t in plan["verworfen"] if d in geschrieben],
        "miniserver": ms_status,
        **({"miniserverZiel": plan["ms_ziel"]}
           if ms_status in ("kein_kennwort_behalten", "unvollstaendig_behalten") and plan["ms_ziel"] else {}),
        **({"miniserverFehler": ms_fehler} if ms_fehler else {}),
        "reloaded": n,
    }
