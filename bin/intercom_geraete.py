"""Gegensprechen fuer Displays im Netz: welche LoxPanel-App (Server im Netz,
nicht der eigene auf dem Geraet) ein Gespraech ueber diesen Server fuehren darf.

Die App erzeugt einmal einen zufaelligen Geraeteschluessel und schickt ihn bei
jedem Gespraech im Kopf X-LoxPanel-Intercom-Geraet mit. Ein unbekannter
Schluessel landet als "wartet" in loxpanel.cfg (intercomGeraete); erst die
Freigabe im Konfigurator (Einstellungen -> SIP) laesst ihn sprechen. Gespeichert
wird nur der SHA-256 des Schluessels, nie der Schluessel selbst.

Der Ton geht direkt zwischen Tuerstation und Display (RTP), der Server fuehrt
nur die SIP-Signalisierung; die Adresse fuer den Ton ist die des anfragenden
Displays (request.remote), nie eine aus der Anfrage. Importiert webvisu nicht."""
from __future__ import annotations

import hashlib
import hmac
import ipaddress
import re
import time

from konfig import _load_cfg, _write_cfg

ABSCHNITT = "intercomGeraete"
KOPF = "X-LoxPanel-Intercom-Geraet"

# Hoechstens so viele wartende Eintraege: ein Geraet, das immer neue Schluessel
# schickt, fuellt die Datei nicht. Der aelteste wartende faellt weg.
WARTEND_MAX = 10

_SCHLUESSEL = re.compile(r"[A-Za-z0-9-]{32,128}")

FREI, WARTET = "frei", "wartet"


def _hash(schluessel: str) -> str:
    return hashlib.sha256(schluessel.encode("ascii")).hexdigest()


def kennung(h: str) -> str:
    """Kurze Kennung eines Eintrags fuer den Konfigurator (Anfang des Hashes)."""
    return h[:12]


def gueltiger_schluessel(schluessel: str | None) -> bool:
    return isinstance(schluessel, str) and _SCHLUESSEL.fullmatch(schluessel) is not None


def ton_adresse(remote: str | None) -> str | None:
    """IPv4-Adresse des anfragenden Displays fuer den Ton, None wenn keine
    brauchbare (IPv6, Loopback, unbestimmt). IPv4 in IPv6 (::ffff:a.b.c.d)
    zaehlt als IPv4."""
    try:
        ip = ipaddress.ip_address(remote or "")
    except ValueError:
        return None
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    if not isinstance(ip, ipaddress.IPv4Address) or ip.is_loopback or ip.is_unspecified \
            or ip.is_multicast:
        return None
    return str(ip)


def _eintraege(cfg: dict) -> dict:
    roh = cfg.get(ABSCHNITT)
    if not isinstance(roh, dict):
        return {}
    return {h: dict(e) for h, e in roh.items()
            if isinstance(h, str) and re.fullmatch(r"[0-9a-f]{64}", h) and isinstance(e, dict)}


def pruefen(schluessel: str, ip: str, name: str = "") -> str:
    """Stand eines Geraeteschluessels: FREI oder WARTET. Ein unbekannter wird
    als wartend gespeichert (mit IP und Name fuer den Konfigurator); bei einem
    bekannten werden IP, Name und Zeit nachgezogen."""
    h = _hash(schluessel)
    cfg = _load_cfg()
    eintraege = _eintraege(cfg)
    jetzt = int(time.time())
    treffer = next((k for k in eintraege if hmac.compare_digest(k, h)), None)
    if treffer is None:
        wartend = sorted((e.get("seit", 0), k) for k, e in eintraege.items() if e.get("status") != FREI)
        while len(wartend) >= WARTEND_MAX:
            eintraege.pop(wartend.pop(0)[1], None)
        eintraege[h] = {"status": WARTET, "ip": ip, "name": name, "seit": jetzt, "zuletzt": jetzt}
        status = WARTET
    else:
        e = eintraege[treffer]
        status = FREI if e.get("status") == FREI else WARTET
        if e.get("ip") == ip and e.get("name") == name and jetzt - int(e.get("zuletzt") or 0) < 3600:
            return status   # nichts Neues: die Datei nicht bei jedem Status-Abruf schreiben
        e.update(ip=ip, name=name or e.get("name", ""), zuletzt=jetzt)
    cfg[ABSCHNITT] = eintraege
    _write_cfg(cfg)
    return status


def ist_frei(schluessel: str) -> bool:
    """Nur lesen (Status und Auflegen): ist der Schluessel freigegeben?"""
    h = _hash(schluessel)
    return any(hmac.compare_digest(k, h) and e.get("status") == FREI
               for k, e in _eintraege(_load_cfg()).items())


def liste() -> list[dict]:
    """Eintraege fuer den Konfigurator, ohne Hash: Kennung, Status, IP, Name, Zeiten."""
    out = [{"id": kennung(h), "status": FREI if e.get("status") == FREI else WARTET,
            "ip": str(e.get("ip") or ""), "name": str(e.get("name") or ""),
            "seit": int(e.get("seit") or 0), "zuletzt": int(e.get("zuletzt") or 0)}
           for h, e in _eintraege(_load_cfg()).items()]
    out.sort(key=lambda e: (e["status"] != WARTET, -e["zuletzt"]))
    return out


def setzen(kurz: str, aktion: str) -> bool:
    """Konfigurator: Eintrag mit dieser Kennung freigeben, sperren (zurueck auf
    wartend) oder entfernen. False, wenn es ihn nicht gibt."""
    if aktion not in ("freigeben", "sperren", "entfernen") or not re.fullmatch(r"[0-9a-f]{12}", kurz or ""):
        return False
    cfg = _load_cfg()
    eintraege = _eintraege(cfg)
    treffer = [h for h in eintraege if kennung(h) == kurz]
    if len(treffer) != 1:
        return False
    h = treffer[0]
    if aktion == "entfernen":
        del eintraege[h]
    else:
        eintraege[h]["status"] = FREI if aktion == "freigeben" else WARTET
    cfg[ABSCHNITT] = eintraege
    _write_cfg(cfg)
    return True
