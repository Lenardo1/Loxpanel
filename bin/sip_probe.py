"""SIP-Pruefung fuer das Gegensprechen: Antwortet die Tuerstation auf SIP, und
nimmt sie die Zugangsdaten an?

Schickt ein OPTIONS (RFC 3261, Abschnitt 11) ueber UDP an die SIP-Adresse aus
den gesicherten Details der Intercom. Verlangt die Gegenstelle eine Anmeldung
(401/407), antwortet die Pruefung mit Digest (RFC 2617, SHA-256 nach RFC 8760).
Ein OPTIONS loest bei der Gegenstelle keinen Anruf aus. Ausgewertet werden
Antwort, Gegenstelle (User-Agent/Server), erlaubte Methoden und, wenn die
Antwort ein SDP mitschickt, die Codecs.

Nur Standardbibliothek. Das Gespraech selbst fuehrt die LoxPanel-App.
"""
from __future__ import annotations

import asyncio
import hashlib
import os
import re
import time
from dataclasses import dataclass

SIP_PORT = 5060
T1 = 0.5                  # s: RFC 3261 Timer T1, erste Wiederholung, danach verdoppelt
WARTEN = 4.0              # s: so lange insgesamt auf eine Antwort warten
MAX_FORWARDS = 70
# Kurzformen der Kopfzeilen (RFC 3261, 7.3.3)
_KURZ = {"i": "call-id", "f": "from", "t": "to", "v": "via", "l": "content-length",
         "c": "content-type", "m": "contact", "k": "supported", "s": "subject"}
_PARAM_RE = re.compile(r'([A-Za-z-]+)\s*=\s*("(?:[^"\\]|\\.)*"|[^,\s]*)')
# Feste RTP-Nutzlasttypen (RFC 3551), falls das SDP kein rtpmap nennt
_STATISCH = {"0": "PCMU/8000", "3": "GSM/8000", "4": "G723/8000", "8": "PCMA/8000",
             "9": "G722/8000", "18": "G729/8000"}
_HASH = {"MD5": hashlib.md5, "SHA-256": hashlib.sha256}


def ziel(host: str) -> tuple[str, int]:
    """SIP-Adresse aus audioInfo.host -> (Host, Port). Nimmt "1.2.3.4",
    "1.2.3.4:5062", "tuer.local", "sip:benutzer@1.2.3.4" und "[::1]:5060".
    ValueError, wenn sich daraus keine Adresse ergibt."""
    t = str(host or "").strip()
    if t.lower().startswith("sip:"):
        t = t[4:]
    t = t.split("@", 1)[-1].split(";", 1)[0]
    if t.startswith("["):
        h, _, rest = t[1:].partition("]")
        port = rest[1:] if rest.startswith(":") else ""
    elif t.count(":") == 1:
        h, port = t.split(":")
    else:
        h, port = t, ""
    try:
        p = int(port) if port else SIP_PORT
    except ValueError:
        raise ValueError(f"Ungültiger Port in {host!r}") from None
    if not h or not 0 < p < 65536:
        raise ValueError(f"Keine SIP-Adresse in {host!r}")
    return h, p


def _hoststr(h: str) -> str:
    return f"[{h}]" if ":" in h else h


def sip_uri(user: str, host: str, port: int) -> str:
    """Request-URI wie die Loxone-App: sip:{user}@{host}, Port nur, wenn er
    vom Standard abweicht."""
    ort = _hoststr(host) + (f":{port}" if port != SIP_PORT else "")
    return f"sip:{user}@{ort}" if user else f"sip:{ort}"


def options(uri: str, lokal: str, call_id: str, cseq: int, branch: str, tag: str,
            autorisierung: str = "") -> bytes:
    """OPTIONS-Anfrage (RFC 3261, 11.1). lokal: eigene Adresse "host:port"."""
    zeilen = [f"OPTIONS {uri} SIP/2.0",
              f"Via: SIP/2.0/UDP {lokal};branch={branch};rport",
              f"Max-Forwards: {MAX_FORWARDS}",
              f"From: <sip:loxpanel@{lokal}>;tag={tag}",
              f"To: <{uri}>",
              f"Call-ID: {call_id}",
              f"CSeq: {cseq} OPTIONS",
              f"Contact: <sip:loxpanel@{lokal}>",
              "Accept: application/sdp",
              "User-Agent: LoxPanel"]
    if autorisierung:
        zeilen.append(autorisierung)
    return ("\r\n".join(zeilen + ["Content-Length: 0", "", ""])).encode("utf-8")


@dataclass
class Antwort:
    code: int
    grund: str
    kopf: list[tuple[str, str]]        # (Name klein, Wert), Kurzformen ausgeschrieben
    rumpf: str

    def alle(self, name: str) -> list[str]:
        return [w for n, w in self.kopf if n == name]

    def wert(self, name: str) -> str:
        w = self.alle(name)
        return w[0] if w else ""


def antwort_lesen(data: bytes) -> Antwort | None:
    """SIP-Antwort zerlegen; None, wenn es keine ist (etwa eine Anfrage)."""
    text = data.decode("utf-8", "replace").replace("\r\n", "\n")
    kopfteil, _, rumpf = text.partition("\n\n")
    zeilen = kopfteil.split("\n")
    m = re.match(r"SIP/2\.0\s+(\d{3})\s*(.*)$", zeilen[0].strip())
    if not m:
        return None
    kopf: list[tuple[str, str]] = []
    for z in zeilen[1:]:
        if z[:1] in (" ", "\t") and kopf:            # Fortsetzungszeile
            kopf[-1] = (kopf[-1][0], kopf[-1][1] + " " + z.strip())
            continue
        name, sep, wert = z.partition(":")
        if sep:
            n = name.strip().lower()
            kopf.append((_KURZ.get(n, n), wert.strip()))
    return Antwort(int(m.group(1)), m.group(2).strip(), kopf, rumpf)


def _parameter(text: str) -> dict[str, str]:
    return {k.lower(): (v[1:-1].replace('\\"', '"') if v.startswith('"') else v)
            for k, v in _PARAM_RE.findall(text)}


def digest(aufforderung: str, user: str, passwort: str, methode: str, uri: str,
           cnonce: str | None = None) -> str:
    """Wert fuer den Authorization-/Proxy-Authorization-Kopf auf eine
    Digest-Aufforderung (WWW-/Proxy-Authenticate). ValueError bei einem anderen
    Verfahren als Digest mit MD5 oder SHA-256."""
    art, _, rest = aufforderung.strip().partition(" ")
    if art.lower() != "digest":
        raise ValueError(f"Anmeldeverfahren {art or '?'} statt Digest")
    p = _parameter(rest)
    alg = (p.get("algorithm") or "MD5").upper()
    sess = alg.endswith("-SESS")
    h = _HASH.get(alg[:-5] if sess else alg)
    if h is None:
        raise ValueError(f"Digest-Verfahren {alg} wird nicht unterstützt")

    def H(x: str) -> str:
        return h(x.encode("utf-8")).hexdigest()
    realm, nonce = p.get("realm", ""), p.get("nonce", "")
    cnonce = cnonce or os.urandom(8).hex()
    nc = "00000001"
    ha1 = H(f"{user}:{realm}:{passwort}")
    if sess:
        ha1 = H(f"{ha1}:{nonce}:{cnonce}")
    ha2 = H(f"{methode}:{uri}")
    qop = "auth" in [q.strip() for q in p.get("qop", "").split(",")]
    antwort = H(f"{ha1}:{nonce}:{nc}:{cnonce}:auth:{ha2}") if qop else H(f"{ha1}:{nonce}:{ha2}")
    teile = [f'username="{user}"', f'realm="{realm}"', f'nonce="{nonce}"', f'uri="{uri}"',
             f'response="{antwort}"', f"algorithm={alg}"]
    if qop:
        teile += [f'cnonce="{cnonce}"', f"nc={nc}", "qop=auth"]
    if "opaque" in p:
        teile.append(f'opaque="{p["opaque"]}"')
    return "Digest " + ", ".join(teile)


def codecs(sdp: str) -> list[str]:
    """Audio-Codecs aus einem SDP in der Reihenfolge der m=audio-Zeile."""
    rtpmap = dict(re.findall(r"^a=rtpmap:(\d+)\s+(\S+)", sdp or "", re.M))
    m = re.search(r"^m=audio\s+\d+(?:/\d+)?\s+\S+\s+([\d ]+)", sdp or "", re.M)
    if not m:
        return []
    return [rtpmap.get(pt) or _STATISCH.get(pt) or f"Typ {pt}" for pt in m.group(1).split()]


class _Empfang(asyncio.DatagramProtocol):
    def __init__(self) -> None:
        self.eingang: asyncio.Queue[bytes | None] = asyncio.Queue()
        self.fehler = ""

    def datagram_received(self, data: bytes, addr) -> None:
        self.eingang.put_nowait(data)

    def error_received(self, exc: Exception) -> None:
        # ICMP "Port unerreichbar" kommt bei UDP als ConnectionRefusedError an
        self.fehler = ("Port geschlossen: an dieser Adresse läuft kein SIP-Dienst"
                       if isinstance(exc, ConnectionRefusedError) else f"Netzwerkfehler: {exc}")
        self.eingang.put_nowait(None)      # beendet das Warten; ein leeres Paket waere b""


async def _transaktion(transport, empfang: _Empfang, anfrage: bytes, call_id: str, cseq: int,
                       warten: float) -> Antwort | None:
    """Anfrage senden und auf die passende Antwort warten (Call-ID und CSeq);
    ohne Antwort nach T1, 2*T1, 4*T1 ... wiederholen, bis warten um ist.
    Vorlaeufige Antworten (1xx) beenden das Warten nicht."""
    ende = time.monotonic() + warten
    intervall, naechste = T1, 0.0
    vorlaeufig = False
    while True:
        jetzt = time.monotonic()
        if jetzt >= ende:
            return None
        if jetzt >= naechste and not vorlaeufig:
            transport.sendto(anfrage)
            naechste, intervall = jetzt + intervall, intervall * 2
        warte_bis = ende if vorlaeufig else min(naechste, ende)
        try:
            data = await asyncio.wait_for(empfang.eingang.get(),
                                          timeout=max(0.01, warte_bis - time.monotonic()))
        except asyncio.TimeoutError:
            continue
        if data is None:                   # error_received
            return None
        a = antwort_lesen(data)
        if a is None or a.wert("call-id") != call_id or a.wert("cseq").split()[:1] != [str(cseq)]:
            continue                       # fremdes oder kaputtes Paket
        if a.code < 200:
            vorlaeufig = True
            continue
        return a


async def pruefen(host: str, user: str, passwort: str, warten: float = WARTEN) -> dict:
    """OPTIONS an die Tuerstation, bei Bedarf mit Anmeldung. -> {"ziel",
    "erreichbar", "antwort", "anmeldung", "gegenstelle", "methoden", "codecs"
    (nur mit SDP), "ms", "error"}. anmeldung: "angenommen", "abgelehnt", "nicht verlangt",
    "kein Passwort", "unbekanntes Verfahren" oder "keine Antwort"; error nennt
    den Grund, wenn die Pruefung nicht durchkam (Schluessel wie bei den
    anderen Routen)."""
    erg: dict = {"ziel": "", "erreichbar": False}
    try:
        h, port = ziel(host)
    except ValueError as err:
        erg["error"] = str(err)
        return erg
    uri = sip_uri(user, h, port)
    erg["ziel"] = uri
    empfang = _Empfang()
    loop = asyncio.get_running_loop()
    try:
        transport, _ = await loop.create_datagram_endpoint(lambda: empfang, remote_addr=(h, port))
    except OSError as err:
        erg["error"] = f"Adresse nicht erreichbar: {err.strerror or err}"
        return erg
    try:
        lip, lport = transport.get_extra_info("sockname")[:2]
        lokal = f"{_hoststr(lip)}:{lport}"
        call_id, tag = f"{os.urandom(8).hex()}@loxpanel", os.urandom(4).hex()
        beginn = time.monotonic()
        a = await _transaktion(transport, empfang,
                               options(uri, lokal, call_id, 1, "z9hG4bK" + os.urandom(6).hex(), tag),
                               call_id, 1, warten)
        if a is None:
            erg["error"] = empfang.fehler or "Keine Antwort: an dieser Adresse meldet sich kein SIP-Dienst"
            return erg
        erg.update(erreichbar=True, ms=round((time.monotonic() - beginn) * 1000),
                   antwort=f"{a.code} {a.grund}".strip(),
                   gegenstelle=a.wert("user-agent") or a.wert("server"))
        if a.code in (401, 407):
            aufforderung = a.wert("www-authenticate" if a.code == 401 else "proxy-authenticate")
            if not passwort:
                erg["anmeldung"] = "kein Passwort"
                return erg
            try:
                auth = digest(aufforderung, user, passwort, "OPTIONS", uri)
            except ValueError as err:
                erg.update(anmeldung="unbekanntes Verfahren", error=str(err))
                return erg
            kopf = "Authorization" if a.code == 401 else "Proxy-Authorization"
            a2 = await _transaktion(transport, empfang,
                                    options(uri, lokal, call_id, 2, "z9hG4bK" + os.urandom(6).hex(), tag,
                                            f"{kopf}: {auth}"),
                                    call_id, 2, warten)
            if a2 is None:
                erg.update(anmeldung="keine Antwort",
                           error=empfang.fehler or "Keine Antwort auf die Anmeldung")
                return erg
            a = a2
            erg["antwort"] = f"{a.code} {a.grund}".strip()
            erg["anmeldung"] = "angenommen" if 200 <= a.code < 300 else "abgelehnt"
        else:
            erg["anmeldung"] = "nicht verlangt"
        erg["gegenstelle"] = a.wert("user-agent") or a.wert("server") or erg.get("gegenstelle", "")
        erg["methoden"] = [x.strip() for x in ",".join(a.alle("allow")).split(",") if x.strip()]
        liste = codecs(a.rumpf)          # nur, wenn die Antwort ein SDP mit Audio mitschickt
        if liste:
            erg["codecs"] = liste
        return erg
    finally:
        transport.close()
