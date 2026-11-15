"""Begleit-Tablets (eigene Version, Marco): Tablets, auf denen die LoxPanel-App nur
im Hintergrund laeuft und vorn eine andere App zeigt (z. B. die Loxone-App).

Die App meldet sich jede Minute mit ihrem Namen und ihrem Stand (POST
/api/begleiter/melden) und bekommt die im Konfigurator gespeicherten Einstellungen
zurueck ("soll"). Solange fuer ein Tablet nichts gespeichert ist, ist "soll" null
und die App behaelt ihre eigenen Einstellungen; der Konfigurator schlaegt dann den
gemeldeten Stand als Vorbelegung vor.

Gespeichert wird in config/begleiter.json: {name: {einstellungen}}. Was die App
zuletzt gemeldet hat, steht nur im Speicher (GESEHEN)."""
from __future__ import annotations

import json
import logging
import re
import time

import konfig

log = logging.getLogger("loxpanel.begleiter")

BEGLEITER_FILE = konfig._CFGDIR / "begleiter.json"

FARBEN = {"schwarz": "#0e0e0e", "gruen": "#8dff70"}
STANDARD = {
    "wetter": True,            # Wetter-Einblendung ueber der fremden App
    "wetterQuelle": "",        # Weather4Lox-Adresse, z. B. http://<loxberry>/plugins/weather4lox/
    "wetterSymbole": "",       # Miniserver-Adresse fuer die Loxone-Wettersymbole, z. B. http://<miniserver>/
    "farbe": "schwarz",        # schwarz | gruen | #rrggbb
    "x": -1, "y": -1,          # Lage des Feldes in px; -1 = Standard der App
    "menueAusblenden": True,   # Wetter weg bei offenem Menue/Detailansicht (braucht die Bedienungshilfe)
    "startApp": True,          # eingestellte App nach dem Hochfahren oeffnen
    "startPaket": "com.loxone.kerberos",
    "weckdienst": True,        # Display per HTTP (Bewegungsmelder) an/aus
    "ble": True,               # BLE-Scanner fuer BLE Presence
    "bleName": "",             # Name des Scanners im Plugin BLE Presence (leer = wie bisher am Tablet)
    "bleSchluessel": "",       # API-Schluessel aus BLE Presence (Shelly-Clients); nie zurueck an den Konfigurator
}
GESEHEN: dict[str, dict] = {}
_NAME = re.compile(r"^[\w .\-äöüÄÖÜß]{1,40}$")
_PAKET = re.compile(r"^[A-Za-z][\w]*(\.[A-Za-z][\w]*)+$")
_FARBE = re.compile(r"^#[0-9a-fA-F]{6}$")


def name_ok(name) -> bool:
    return isinstance(name, str) and bool(_NAME.match(name.strip()))


def _url(v) -> str:
    v = str(v or "").strip()[:200]
    return v if re.match(r"^https?://[\w.\-:]+(/[\w.\-/%]*)?$", v) else ""


def bereinigen(d) -> dict:
    """Einstellungen eines Tablets pruefen; Unbekanntes faellt weg, Fehlendes nimmt den Standard."""
    d = d if isinstance(d, dict) else {}
    out = dict(STANDARD)
    for k in ("wetter", "menueAusblenden", "startApp", "weckdienst", "ble"):
        if isinstance(d.get(k), bool):
            out[k] = d[k]
    for k in ("wetterQuelle", "wetterSymbole"):
        if k in d:
            out[k] = _url(d.get(k))
    f = d.get("farbe")
    if isinstance(f, str) and (f in FARBEN or _FARBE.match(f)):
        out["farbe"] = f.lower() if f.startswith("#") else f
    for k in ("x", "y"):
        v = d.get(k)
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            out[k] = max(-1, min(4000, int(v)))
    n = d.get("bleName")
    if isinstance(n, str) and (n.strip() == "" or name_ok(n)):
        out["bleName"] = n.strip()
    k = d.get("bleSchluessel")
    if isinstance(k, str) and re.match(r"^[0-9a-fA-F]{0,128}$", k.strip()):
        out["bleSchluessel"] = k.strip().lower()
    p = d.get("startPaket")
    if isinstance(p, str) and _PAKET.match(p.strip()):
        out["startPaket"] = p.strip()[:100]
    return out


def farbe_hex(f: str) -> str:
    return FARBEN.get(f, f if _FARBE.match(f or "") else FARBEN["schwarz"])


def laden() -> dict:
    try:
        d = json.loads(BEGLEITER_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return {n: bereinigen(v) for n, v in d.items() if name_ok(n)} if isinstance(d, dict) else {}


def speichern(alle: dict) -> None:
    konfig._atomic_write(BEGLEITER_FILE, json.dumps(alle, indent=2, ensure_ascii=False) + "\n")


def melden(name: str, ip: str, d: dict) -> dict | None:
    """Meldung der App merken; gibt die gespeicherten Einstellungen (mit Farbe als Hex) zurueck."""
    ist = d.get("ist") if isinstance(d.get("ist"), dict) else {}
    GESEHEN[name] = {"ip": ip or "", "zeit": time.time(), "version": str(d.get("version") or "")[:40],
                     "android": str(d.get("android") or "")[:20], "modell": str(d.get("modell") or "")[:40],
                     "bedienungshilfe": d.get("bedienungshilfe") is True, "ist": bereinigen(ist)}
    soll = laden().get(name)
    return dict(soll, farbeHex=farbe_hex(soll["farbe"])) if soll else None


def ohne_schluessel(soll: dict | None) -> dict | None:
    """Fuer den Konfigurator: den BLE-Schluessel nie im Klartext, nur ob einer gesetzt ist."""
    if soll is None:
        return None
    return dict(soll, bleSchluessel="", bleSchluesselGesetzt=bool(soll.get("bleSchluessel")))


def zusammenfuehren(alt: dict | None, neu: dict) -> dict:
    """Speichern aus dem Konfigurator: leeres Schluesselfeld = bisherigen Schluessel behalten."""
    if not neu.get("bleSchluessel") and alt and alt.get("bleSchluessel"):
        neu = dict(neu, bleSchluessel=alt["bleSchluessel"])
    return neu


def uebersicht() -> dict:
    """Alle bekannten Tablets fuer den Konfigurator: gespeichert und/oder gemeldet."""
    gesp = laden()
    namen = sorted(set(gesp) | set(GESEHEN))
    jetzt = time.time()
    out = {}
    for n in namen:
        g = GESEHEN.get(n)
        out[n] = {"soll": ohne_schluessel(gesp.get(n)), "gesehen": dict(g, vorSek=int(jetzt - g["zeit"])) if g else None}
    return out
