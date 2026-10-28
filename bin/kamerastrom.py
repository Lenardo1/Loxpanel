"""Kamerabilder fuer /mjpeg: ein Strom je Kamera, verteilt an alle Zuschauer.

Bisher holte /mjpeg fuer jeden Zuschauer einen eigenen Strom von der Kamera:
drei Panels und zwei Bento-Zellen hiessen fuenf Stroeme an der Tuerstation, und
riss einer ab, blieb sein Bild stehen. Jetzt haelt der Kameraverteiler je
Kamera (Adresse und Anmeldung) einen Kamerastrom. Der zerlegt den MJPEG-Strom
in Bilder (MjpegZerleger) und gibt jedem Zuschauer das jeweils neueste: Ein
langsames Panel ueberspringt Bilder, statt die anderen aufzuhalten.

- Bricht die Kamera ab, verbindet der Strom mit wachsender Pause neu
  (PAUSE_MIN_S bis PAUSE_MAX_S, klein wieder nach einem Strom, der
  LAUF_MIN_S lief). Die Zuschauer bleiben verbunden und sehen bis dahin das
  letzte Bild. Ein neuer Zuschauer kuerzt die Pause ab: Er wartet auf einen
  Versuch von jetzt, nicht auf den letzten Fehlschlag. Ein 4xx (ausser 408
  und 429) ist endgueltig: Wiederholte Fehlanmeldungen sperren manche Kameras.
- Jedes Bild geht mit dem Kopf des naechsten Teils dahinter hinaus: Chromium
  (auch Android-WebView und LoxOS) zeigt einen Teil erst, wenn der naechste
  beginnt; sonst kaeme jedes Bild ein Bild zu spaet.
- Nach dem letzten Zuschauer laeuft er noch NACHLAUF_S weiter (Seitenwechsel,
  neu aufgebaute Seite), dann trennt er.
- Antworten wie bisher: 502, wenn die Kamera nicht erreichbar ist oder nicht
  mit 200 antwortet, 200, sobald sie es tut (auch wenn ihr Strom danach
  abreisst: der Zuschauer wartet dann aufs Neuverbinden). Ein neuer Zuschauer
  bekommt sofort das letzte Bild, solange der Strom laeuft; ist die Kamera
  weg, nur, wenn es juenger als BILD_FRISCH_S ist, sonst 502. Schickt die
  Kamera auf den ersten Abruf ein Einzelbild statt multipart, geht es
  unveraendert an den Zuschauer, und jeder Abruf holt ein neues.
- Je Kamera hoechstens ZUSCHAUER_MAX Zuschauer, danach 503 (docs/ARCHITEKTUR.md,
  Befund S6).

Nur aiohttp, importiert kein Server-Modul. Ins Log kommt von der Adresse nur
der Host: Anmeldedaten in der Adresse bleiben draussen."""
from __future__ import annotations

import asyncio
import logging
import re
import time
from urllib.parse import urlsplit

import aiohttp
from aiohttp import web

log = logging.getLogger("loxpanel.webvisu")   # derselbe Logger wie der Server

NACHLAUF_S = 10.0          # so lange haelt der Strom nach dem letzten Zuschauer
PAUSE_MIN_S = 1.0          # Pause vor dem ersten neuen Versuch, verdoppelt sich ...
PAUSE_MAX_S = 30.0         # ... bis hierher; ein Strom, der LAUF_MIN_S lief, setzt sie zurueck
LAUF_MIN_S = 10.0          # so lange muss ein Strom laufen, damit sein Ende ein Abriss ist
VERBINDEN_S = 10.0         # Verbindungsaufbau zur Kamera
LESEN_S = 30.0             # so lange darf die Kamera schweigen (wie bisher)
BILD_FRISCH_S = 30.0       # ein spaeter Zuschauer bekommt ein so junges letztes Bild sofort
ZUSCHAUER_MAX = 16         # je Kamera
SCHREIBEN_S = 30.0         # haengt ein Zuschauer so lange an einem Bild, ist er weg
PRUEF_S = 1.0              # so oft schaut ein wartender Zuschauer, ob er noch verbunden ist
BILD_MAX = 8 * 1024 * 1024
KOPF_MAX = 8 * 1024        # Kopf eines Teils oder Zeile vor der ersten Grenze
GRENZE = "loxpanelbild"    # boundary der Antwort an die Zuschauer

_TYP = re.compile(r"[A-Za-z0-9.+-]+/[A-Za-z0-9.+-]+")


def _boundary(ctype: str) -> str:
    """boundary aus dem Content-Type der Kamera, ohne Anfuehrungszeichen; "" ohne."""
    m = re.search(r'boundary\s*=\s*"?([^";]+)"?', ctype or "", re.I)
    return m.group(1).strip() if m else ""


def _kopf_lesen(kopf: str) -> tuple[str, int | None]:
    """Kopf eines Teils -> (Content-Type, Content-Length). Ein Typ, der keiner
    ist, wird image/jpeg; ValueError bei einer Laenge ueber BILD_MAX."""
    typ, laenge = "image/jpeg", None
    for zeile in kopf.splitlines():
        name, _, wert = zeile.partition(":")
        name, wert = name.strip().lower(), wert.strip()
        if name == "content-type" and _TYP.fullmatch(wert.split(";")[0].strip()):
            typ = wert.split(";")[0].strip()
        elif name == "content-length" and wert.isdigit():
            laenge = int(wert)
            if laenge > BILD_MAX:
                raise ValueError(f"Bild mit {laenge} Bytes")
    return typ, laenge


class MjpegZerleger:
    """Zerlegt multipart/x-mixed-replace in Bilder. Die Grenze kommt aus dem
    boundary des Content-Type (mit oder ohne fuehrende "--"); ohne boundary
    gilt die erste Zeile, die mit "--" beginnt. Ein Teil endet nach seinem
    Content-Length oder vor der naechsten Grenze (ohne Content-Length kommt
    ein Bild also erst mit dem Beginn des naechsten). Die Grenze darf wie in
    Chromium auch ohne Zeilenumbruch direkt hinter dem Bild stehen. Folgt auf
    ein Bild mit Content-Length etwas anderes als die Grenze, war die Laenge zu
    klein: Ab dann gilt sie fuer diese Kamera nicht mehr (laenge_falsch, der
    Kamerastrom gibt es an den naechsten Zerleger weiter). Zeilen enden mit
    CRLF oder LF, ein Teil ohne Kopf (gleich das JPEG) geht auch, Text vor der
    ersten Grenze wird uebergangen. futter() -> fertige Bilder als
    (Content-Type, Daten); ValueError, wenn ein Teil oder ein Kopf ueber die
    Grenzen waechst."""

    def __init__(self, boundary: str = "", laenge_falsch: bool = False):
        b = boundary.encode("latin-1", "replace")
        self._kandidaten = {b"--" + b, b} if b else set()
        self._grenze = b""
        self._puffer = bytearray()
        self._stand = "grenze"
        self._typ, self._laenge = "image/jpeg", None
        self._ab = 0                 # bis hierher ist der Puffer schon nach der Grenze durchsucht
        self._nach_laenge = False    # das letzte Bild endete nach seinem Content-Length
        self.laenge_falsch = laenge_falsch

    def _ist_grenze(self, zeile: bytes) -> bool:
        if self._grenze:
            return zeile in (self._grenze, self._grenze + b"--")
        if (zeile in self._kandidaten) if self._kandidaten else zeile.startswith(b"--"):
            self._grenze = zeile
            return True
        return False

    def _reste(self, daten) -> None:
        """Vor der Grenze steht mehr als Leerraum: nach einem Bild mit
        Content-Length der Rest des Bildes, die Laenge war also zu klein."""
        if self._nach_laenge and bytes(daten).strip():
            self.laenge_falsch = True

    def _grenze_suchen(self, p: bytearray) -> bool:
        """Stand "grenze" mit bekannter Grenze: sie steht irgendwo, nicht
        unbedingt am Zeilenanfang. True, wenn danach der Kopf kommt."""
        i = p.find(self._grenze)
        if i < 0:
            behalten = len(self._grenze)
            self._reste(p[:-behalten])
            del p[:max(0, len(p) - behalten)]
            return False
        self._reste(p[:i])
        del p[:i]
        j = p.find(b"\n")
        if j < 0:
            if len(p) > KOPF_MAX:
                raise ValueError("Grenze ohne Zeilenende im MJPEG-Strom")
            return False
        zeile = bytes(p[:j]).strip()
        del p[:j + 1]
        if self._ist_grenze(zeile):
            self._stand, self._nach_laenge = "kopf", False
        return True

    def futter(self, daten: bytes) -> list[tuple[str, bytes]]:
        self._puffer += daten
        fertig = []
        while True:
            p = self._puffer
            if self._stand == "grenze" and self._grenze:
                if not self._grenze_suchen(p):
                    break
            elif self._stand == "grenze":
                i = p.find(b"\n")
                if i < 0:
                    if len(p) > KOPF_MAX:
                        raise ValueError("keine Grenze im MJPEG-Strom")
                    break
                zeile = bytes(p[:i]).strip()
                del p[:i + 1]
                if zeile and self._ist_grenze(zeile):
                    self._stand = "kopf"
            elif self._stand == "kopf":
                if p[:2] == b"\xff\xd8":                     # ohne Kopf: gleich das JPEG
                    self._typ, self._laenge, self._stand, self._ab = "image/jpeg", None, "inhalt", 0
                    continue
                if p[:1] == b"\n" or p[:2] == b"\r\n":        # leerer Kopf
                    ende, n = 0, (1 if p[:1] == b"\n" else 2)
                else:
                    treffer = [(i, n) for i, n in ((p.find(b"\r\n\r\n"), 4), (p.find(b"\n\n"), 2)) if i >= 0]
                    if not treffer:
                        if len(p) > KOPF_MAX:
                            raise ValueError("Kopf eines Bildes zu lang")
                        break
                    ende, n = min(treffer)
                self._typ, self._laenge = _kopf_lesen(bytes(p[:ende]).decode("latin-1"))
                if self.laenge_falsch:
                    self._laenge = None
                del p[:ende + n]
                self._stand, self._ab = "inhalt", 0
            elif self._laenge is not None:
                if len(p) < self._laenge:
                    break
                bild = bytes(p[:self._laenge])
                del p[:self._laenge]
                self._stand, self._nach_laenge = "grenze", True
                if bild:
                    fertig.append((self._typ, bild))
            else:
                if p.startswith(self._grenze):               # leerer Teil
                    self._stand = "grenze"
                    continue
                i = p.find(self._grenze, self._ab)
                if i < 0:
                    if len(p) > BILD_MAX:
                        raise ValueError("Bild ohne Ende im MJPEG-Strom")
                    self._ab = max(0, len(p) - len(self._grenze))
                    break
                bild = bytes(p[:i])
                bild = bild[:-2] if bild.endswith(b"\r\n") else bild[:-1] if bild.endswith(b"\n") else bild
                del p[:i]
                self._stand, self._nach_laenge = "grenze", False
                if bild:
                    fertig.append((self._typ, bild))
        return fertig


def _kopf(typ: str) -> bytes:
    """Grenze und Kopf eines Teils der Antwort an die Zuschauer (boundary
    GRENZE), ohne Content-Length: Sie stehen hinter dem Bild davor, denn
    Chromium (auch Android-WebView und LoxOS) zeigt einen Teil erst, wenn der
    naechste beginnt."""
    return f"--{GRENZE}\r\nContent-Type: {typ}\r\n\r\n".encode("latin-1")


async def _ganz_lesen(antwort: aiohttp.ClientResponse) -> bytes:
    """Antwort der Kamera ganz, hoechstens BILD_MAX Bytes (sonst ValueError)."""
    daten = bytearray()
    async for teil in antwort.content.iter_any():
        daten += teil
        if len(daten) > BILD_MAX:
            raise ValueError("Einzelbild zu gross")
    return bytes(daten)


class Kamerastrom:
    """Der eine Strom von einer Kamera fuer alle ihre Zuschauer. zustand:
    "verbinden", "laeuft" (die Kamera hat mit 200 und multipart geantwortet),
    "abgerissen" (danach endete der Strom, er verbindet neu), "fehler" (nicht
    erreichbar oder nicht 200, Text in fehler), "einzelbild" (die Kamera
    schickte ein Bild statt eines Stroms) oder "ende" (getrennt)."""

    def __init__(self, cam: dict, beim_ende):
        self.schluessel = Kameraverteiler.schluessel(cam)
        self.url, self.user, self.passwort = self.schluessel
        try:
            self.host = urlsplit(self.url).hostname or "?"
        except ValueError:
            self.host = "?"
        self.zustand, self.fehler = "verbinden", ""
        self.einzelbild: tuple[str, bytes] | None = None
        self.teil = b""              # das neueste Bild mit dem Kopf des naechsten Teils dahinter
        self.typ = "image/jpeg"      # Content-Type des neuesten Bildes
        self.war_strom = False       # hat die Kamera schon einmal multipart geschickt
        self.endgueltig = False      # die Kamera lehnt ab (4xx): kein neuer Versuch
        self._laenge_falsch = False  # ihr Content-Length stimmt nicht (MjpegZerleger)
        self.nummer = 0              # zaehlt die Bilder
        self.zeit = 0.0              # monotonic des neuesten Bildes
        self.zuschauer = 0
        self.ergebnisse = 0          # zaehlt die Ergebnisse der Versuche (laeuft, Fehler, Einzelbild)
        self._signal = asyncio.Event()
        self._weck = asyncio.Event()  # kuerzt die Pause vor dem naechsten Versuch ab
        self._task: asyncio.Task | None = None
        self._nachlauf: asyncio.Task | None = None
        self._beim_ende = beim_ende

    def _melden(self) -> None:
        """Wartende Zuschauer wecken: jeder wartet auf das Event von eben."""
        signal, self._signal = self._signal, asyncio.Event()
        signal.set()

    def _neues_bild(self, typ: str, bild: bytes) -> None:
        self.teil = bild + b"\r\n" + _kopf(typ)
        self.typ = typ
        self.nummer += 1
        self.zeit = time.monotonic()
        self._melden()

    def frisch(self) -> bool:
        return self.nummer > 0 and time.monotonic() - self.zeit < BILD_FRISCH_S

    def bild_gilt(self) -> bool:
        """Darf ein neuer Zuschauer das letzte Bild sofort sehen: bei einem
        laufenden Strom immer (es ist das aktuelle), sonst nur, wenn es frisch ist."""
        return self.nummer > 0 and (self.zustand == "laeuft" or self.frisch())

    def aktiv(self) -> bool:
        return self._task is not None and not self._task.done()

    def starten(self) -> None:
        self._task = asyncio.create_task(self._lauf())

    def nachlauf_abbrechen(self) -> None:
        if self._nachlauf is not None:
            self._nachlauf.cancel()
            self._nachlauf = None

    def nachlauf_starten(self) -> None:
        self.nachlauf_abbrechen()
        self._nachlauf = asyncio.create_task(self._spaeter_trennen())

    async def _spaeter_trennen(self) -> None:
        await asyncio.sleep(NACHLAUF_S)
        self._nachlauf = None
        if self.zuschauer <= 0:
            self._beim_ende(self)        # vor dem Trennen: wer jetzt kommt, bekommt einen neuen Strom
            await self._trennen()

    async def _trennen(self) -> None:
        task, self._task = self._task, None
        if task is not None and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    async def beenden(self) -> None:
        """Strom trennen und alle Zuschauer entlassen (Herunterfahren)."""
        self.nachlauf_abbrechen()
        await self._trennen()
        if self.zustand != "einzelbild":
            self.zustand = "ende"
        self._melden()

    async def _lauf(self) -> None:
        pause = PAUSE_MIN_S
        try:
            while True:
                if await self._einmal():
                    pause = PAUSE_MIN_S
                if self.zustand == "einzelbild" or self.endgueltig:
                    return
                try:
                    await asyncio.wait_for(self._weck.wait(), pause)
                except asyncio.TimeoutError:
                    pass
                self._weck.clear()
                pause = min(pause * 2, PAUSE_MAX_S)
        except Exception:
            log.exception("Kamera %s: Strom abgebrochen", self.host)
        finally:
            if self.zustand != "einzelbild":
                self.zustand = "ende"
            self._melden()
            self._beim_ende(self)

    def _ergebnis(self, zustand: str) -> None:
        self.zustand = zustand
        self.ergebnisse += 1
        self._melden()

    def _fehlschlag(self, text: str) -> None:
        self.fehler = text
        self._ergebnis("fehler")

    def _abgerissen(self, grund: object, lange: bool) -> None:
        """Der Strom endete nach einer 200; lange: er lief LAUF_MIN_S (sonst nur
        ins Debug-Log, eine Kamera mit einem Bild je Verbindung schriebe es voll)."""
        log.log(logging.INFO if lange else logging.DEBUG,
                "Kamera %s getrennt (%s), verbinde neu", self.host, grund)
        self.zustand = "abgerissen"
        self._melden()

    async def _einmal(self) -> bool:
        """Ein Abruf bei der Kamera, bis sie den Strom beendet oder abbricht.
        True, wenn er LAUF_MIN_S lief (oder ein Einzelbild brachte): Dann
        beginnt die Pause vor dem naechsten Versuch wieder klein.
        - 4xx ausser 408 und 429 ist endgueltig (falsches Kennwort, falsche
          Adresse): Wiederholte Fehlanmeldungen sperren manche Kameras.
        - Eine Antwort ohne multipart ist nur als erste ein Einzelbild; spaeter
          (etwa eine Fehlerseite unter Last) zaehlt sie wie ein Abriss.
        Eigene ClientSession (nicht icon_session): mit deren SSL-Connector
        liefert die Mobotix nur ein Einzelbild statt des Stroms."""
        self.zustand = "verbinden"
        sess = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(
            total=None, sock_connect=VERBINDEN_S, sock_read=LESEN_S))
        try:
            # ValueError: unbrauchbarer Host ("cam..lan") oder Benutzer, der nicht
            # in den Basic-Auth-Kopf passt (Doppelpunkt, Zeichen ausserhalb Latin-1)
            auth = aiohttp.BasicAuth(self.user, self.passwort) if self.user else None
            async with sess.get(self.url, auth=auth) as antwort:
                if antwort.status != 200:
                    if 400 <= antwort.status < 500 and antwort.status not in (408, 429):
                        self.endgueltig = True
                        log.warning("Kamera %s antwortet %d, kein neuer Versuch", self.host, antwort.status)
                    self._fehlschlag(f"camera status {antwort.status}")
                    return False
                ctype = antwort.headers.get("Content-Type", "multipart/x-mixed-replace")
                if not ctype.lower().startswith("multipart/"):
                    if self.war_strom:
                        self._abgerissen(f"kein MJPEG ({ctype})", False)
                        return False
                    bild = await _ganz_lesen(antwort)
                    self.einzelbild = (ctype, bild)
                    self._beim_ende(self)    # der naechste Abruf holt ein neues Bild
                    typ = ctype.split(";")[0].strip()
                    self._neues_bild(typ if _TYP.fullmatch(typ) else "image/jpeg", bild)
                    self._ergebnis("einzelbild")
                    return True
                zerleger = MjpegZerleger(_boundary(ctype), self._laenge_falsch)
                self.fehler, self.war_strom = "", True
                self._ergebnis("laeuft")
                beginn = time.monotonic()
                try:
                    async for daten in antwort.content.iter_any():
                        for typ, bild in zerleger.futter(daten):
                            self._neues_bild(typ, bild)
                    grund: object = "Strom zu Ende"
                except (aiohttp.ClientError, asyncio.TimeoutError, ValueError, OSError) as err:
                    grund = err
                finally:
                    self._laenge_falsch = zerleger.laenge_falsch
                lange = time.monotonic() - beginn >= LAUF_MIN_S
                self._abgerissen(grund, lange)
                return lange
        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError, OSError):
            self._fehlschlag("camera unreachable")
            return False
        finally:
            await sess.close()

    async def _warten(self, bedingung, frist: float) -> None:
        """Warten, bis bedingung() gilt oder frist um ist."""
        bis = time.monotonic() + frist
        while not bedingung() and time.monotonic() < bis:
            signal = self._signal
            try:
                await asyncio.wait_for(signal.wait(), bis - time.monotonic())
            except asyncio.TimeoutError:
                break

    async def senden(self, request: web.Request) -> web.StreamResponse:
        """Antwort an einen Zuschauer: wartet, bis die Kamera geantwortet hat
        (oder ein Bild gilt, bild_gilt), dann 502, das Einzelbild oder der
        Strom mit dem jeweils neuesten Bild, bis der Zuschauer geht oder der
        Strom endet. Steht der Strom ohne gueltiges Bild in der Pause (nach
        einem Fehlschlag oder einem abgerissenen Strom), kuerzt der Zuschauer
        sie ab und wartet auf das Ergebnis dieses neuen Versuchs."""
        stand = self.ergebnisse
        if self.zustand in ("fehler", "abgerissen") and not self.bild_gilt():
            self._weck.set()
        await self._warten(lambda: self.bild_gilt() or self.zustand in ("laeuft", "einzelbild", "ende")
                           or (self.zustand in ("fehler", "abgerissen") and self.ergebnisse > stand),
                           VERBINDEN_S + LESEN_S)
        if self.zustand == "einzelbild" and self.einzelbild is not None:
            typ, bild = self.einzelbild
            return web.Response(body=bild, headers={"Content-Type": typ, "Cache-Control": "no-cache, no-store"})
        if self.zustand not in ("laeuft", "abgerissen") and not self.bild_gilt():
            return web.Response(status=502, text=self.fehler or "camera unreachable")
        resp = web.StreamResponse(status=200, headers={
            "Content-Type": f"multipart/x-mixed-replace; boundary={GRENZE}", "Cache-Control": "no-cache, no-store"})
        await resp.prepare(request)
        gesehen = self.nummer - 1 if self.bild_gilt() else self.nummer
        try:
            await asyncio.wait_for(resp.write(_kopf(self.typ)), SCHREIBEN_S)
            while True:
                if self.nummer > gesehen:
                    gesehen = self.nummer
                    await asyncio.wait_for(resp.write(self.teil), SCHREIBEN_S)
                    continue
                if self.zustand in ("ende", "einzelbild"):
                    break
                signal = self._signal
                try:
                    await asyncio.wait_for(signal.wait(), PRUEF_S)
                except asyncio.TimeoutError:
                    if request.transport is None or request.transport.is_closing():
                        break
        except (ConnectionResetError, asyncio.TimeoutError, aiohttp.ClientError):
            pass                         # Zuschauer weg oder haengt
        return resp


class Kameraverteiler:
    """Die laufenden Kamerastroeme je Kamera (Adresse und Anmeldung). Der
    Handler meldet jeden Zuschauer an und nach seiner Antwort wieder ab."""

    def __init__(self):
        self._stroeme: dict[tuple[str, str, str], Kamerastrom] = {}
        self._geschlossen = False    # nach schliessen(): Herunterfahren, keine neuen Stroeme

    @staticmethod
    def schluessel(cam: dict) -> tuple[str, str, str]:
        return str(cam.get("url") or ""), str(cam.get("user") or ""), str(cam.get("pass") or "")

    def anmelden(self, cam: dict) -> Kamerastrom | None:
        """Zuschauer fuer die Kamera cam ({"url", "user", "pass"}): den
        laufenden Strom oder einen neuen. None, wenn sie schon ZUSCHAUER_MAX hat
        oder der Server herunterfaehrt (ein Abruf, der erst nach on_shutdown
        ankommt, bekaeme sonst einen Strom, den niemand mehr beendet)."""
        if self._geschlossen:
            return None
        strom = self._stroeme.get(self.schluessel(cam))
        if strom is None:
            strom = self._stroeme[self.schluessel(cam)] = Kamerastrom(cam, self._vergessen)
            strom.starten()
        elif strom.zuschauer >= ZUSCHAUER_MAX:
            return None
        strom.zuschauer += 1
        strom.nachlauf_abbrechen()
        return strom

    def abmelden(self, strom: Kamerastrom) -> None:
        strom.zuschauer -= 1
        if strom.zuschauer <= 0 and strom.aktiv():
            strom.nachlauf_starten()

    def _vergessen(self, strom: Kamerastrom) -> None:
        """Ein beendeter Strom (oder ein Einzelbild) wird nicht wieder vergeben."""
        if self._stroeme.get(strom.schluessel) is strom:
            del self._stroeme[strom.schluessel]

    def anzahl(self) -> int:
        return len(self._stroeme)

    async def schliessen(self) -> None:
        """Alle Stroeme trennen und ihre Zuschauer entlassen; danach endet jede
        offene /mjpeg-Antwort (Herunterfahren: aiohttp wartet sonst auf sie).
        Danach nimmt der Verteiler niemanden mehr an."""
        self._geschlossen = True
        for strom in list(self._stroeme.values()):
            await strom.beenden()
        self._stroeme.clear()
