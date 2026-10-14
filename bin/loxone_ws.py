"""Loxone WebSocket-Live-Client (Phase 2b).

Holt die echten State-Werte, die es ueber HTTP nicht gibt. Nutzt das per
loxone-api geholte JWT zur WS-Authentifizierung (authwithtoken) und abonniert
danach die binaeren Status-Updates (enablebinstatusupdate).

Protokoll (Kurzfassung, siehe "Communicating with the Miniserver"):
  - Jede Nachricht wird von einem 8-Byte-Header eingeleitet (Byte0=0x03,
    Byte1=Identifier, Byte4..7=Laenge, little-endian).
  - Identifier: 0=Text, 2=Value-States, 3=Text-States, 6=Keepalive,
    7=Weather-States (nur wenn die Anlage den Loxone-Wetterdienst hat).
  - Value-State-Eintrag: 16-Byte-UUID + 8-Byte-double (LE).
  - Text-State-Eintrag: 16-Byte-UUID + 16-Byte-Icon-UUID + 4-Byte-Laenge +
    Text + Padding auf 4-Byte-Grenze.
  - Weather-Eintrag ("EvDataWeather"): 16-Byte-UUID + 4-Byte lastUpdate
    (uint32) + 4-Byte nrEntries (int32), danach nrEntries Bloecke a 68 Byte
    ("EvDataWeatherEntry"): 5 * int32 (timestamp, weatherType, windDirection,
    solarRadiation, relativeHumidity) + 6 * double (temperature,
    perceivedTemperature, dewPoint, precipitation, windSpeed,
    barometricPressure), alles little-endian.

Nicht behandelte Identifier werden einmal pro Verbindung protokolliert — sonst
bliebe unsichtbar, dass der Miniserver etwas schickt, das hier niemand liest.

Lebenszeichen (Abschnitt "Keeping the connection alive"): Auf "keepalive"
antwortet der Miniserver mit einem Header der Kennung 6, und laut Doku trennt
er einen Client, der laenger als 5 Minuten nichts sendet. Ein still
abgerissener Socket (Strom, WLAN, NAT ohne RST) meldet dagegen nichts. Darum
hat jeder Schritt der Anmeldung eine Antwortfrist, und stream() sendet
regelmaessig "keepalive" und gibt auf, wenn danach binnen der Frist keine
Nachricht kommt. Beide Werte kommen vom Aufrufer (webvisu: loxpanel.cfg);
ohne sie wartet die Klasse wie frueher unbegrenzt (Hilfsskripte in bin/).
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import ssl
import struct
import time
from typing import Any, Callable

import aiohttp

log = logging.getLogger("loxpanel.ws")

ValueCallback = Callable[[str, Any], None]
# uuid -> Liste von Wetter-Eintraegen (siehe _parse_weather).
WeatherCallback = Callable[[str, list], None]


# Ein Wetter-Eintrag: 5 * int32, dann 6 * double, ohne Padding.
_WX_ENTRY = struct.Struct("<5i6d")
_WX_FIELDS = ("ts", "type", "wind_dir", "radiation", "humidity",
              "temp", "feels", "dew", "precip", "wind", "pressure")


def ms_ssl_kontext(verify_tls: bool) -> ssl.SSLContext:
    """TLS-Kontext fuer den Miniserver, wie ihn loxone_api fuer HTTP baut.
    verify_tls: Zertifikat und Namen gegen den Standard-Truststore pruefen
    (SSLContext(PROTOCOL_TLS_CLIENT) allein laedt keine einzige CA, dann
    scheitert jedes Zertifikat). Das gelingt nur, wenn host ein Name ist, den
    das Zertifikat nennt; per IP-Adresse scheitert der Namensvergleich. Sonst
    ohne jede Pruefung (etwa Gen2 mit selbstsigniertem Zertifikat).
    Das Laden der CAs blockiert; aus async-Code per asyncio.to_thread rufen."""
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    if verify_tls:
        ctx.load_default_certs(ssl.Purpose.SERVER_AUTH)
    else:
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    return ctx


def format_uuid(b: bytes) -> str:
    d1 = struct.unpack("<I", b[0:4])[0]
    d2 = struct.unpack("<H", b[4:6])[0]
    d3 = struct.unpack("<H", b[6:8])[0]
    d4 = b[8:16].hex()
    return f"{d1:08x}-{d2:04x}-{d3:04x}-{d4}"


class LoxoneWS:
    def __init__(self, host: str, port: int, user: str, jwt: str,
                 hash_alg: str = "SHA1", verify_tls: bool = False, secure: bool = True,
                 antwortfrist: float | None = None, keepalive_abstand: float | None = None):
        self.host = host
        self.port = port
        self.user = user
        self.jwt = jwt
        self.hash_alg = (hash_alg or "SHA1").upper()
        self.verify_tls = verify_tls
        self.secure = secure          # False = Gen1 (ws:// statt wss://)
        # s: Frist je Antwort (Aufbau, getkey, authwithtoken, keepalive) und
        # Abstand der keepalive; None = keine Frist bzw. kein keepalive.
        self.antwortfrist = antwortfrist
        self.keepalive_abstand = keepalive_abstand
        # time.monotonic() am Ende der Anmeldung und bei der letzten Nachricht
        # danach (lebenszeit()).
        self.angemeldet: float | None = None
        self.letzte_nachricht: float | None = None
        self._session: aiohttp.ClientSession | None = None
        self._ws: aiohttp.ClientWebSocketResponse | None = None

    def _ssl(self) -> ssl.SSLContext:
        return ms_ssl_kontext(self.verify_tls)

    async def connect(self) -> None:
        self._session = aiohttp.ClientSession()
        scheme = "wss" if self.secure else "ws"
        url = f"{scheme}://{self.host}:{self.port}/ws/rfc6455"
        log.info("WS verbinde %s", url)
        # Kontext vor der Frist und im Thread bauen: Das Laden der CAs
        # blockiert und ist keine Antwortzeit des Miniservers.
        ssl_ctx = (await asyncio.to_thread(self._ssl)) if self.secure else None
        self._ws = await self._frist(self._session.ws_connect(
            url, ssl=ssl_ctx, protocols=["remotecontrol"], max_msg_size=0),
            "den Verbindungsaufbau")

        # 1) getkey -> HMAC(token) -> authwithtoken
        key_hex = await self._cmd_value("jdev/sys/getkey")
        digestmod = hashlib.sha256 if self.hash_alg == "SHA256" else hashlib.sha1
        token_hash = hmac.new(bytes.fromhex(key_hex), self.jwt.encode(), digestmod).hexdigest()
        # Im Fehlertext nur der Befehlsname: er landet im Einrichtungshinweis
        # der Panels, der Pfad traegt den Token-Hash.
        auth = await self._cmd_json(f"authwithtoken/{token_hash}/{self.user}", "authwithtoken")
        code = str((auth.get("LL") or {}).get("Code") or (auth.get("LL") or {}).get("code"))
        if code != "200":
            raise ConnectionError(f"authwithtoken fehlgeschlagen: {auth}")
        log.info("WS authentifiziert")

        # 2) Status-Updates einschalten (loest sofort einen Voll-Dump aus)
        await self._ws.send_str("jdev/sps/enablebinstatusupdate")
        self.angemeldet = self.letzte_nachricht = time.monotonic()

    def lebenszeit(self) -> float:
        """Sekunden von der Anmeldung bis zur letzten Nachricht des Miniservers:
        so lange lebte die Verbindung nachweislich. Offen sein allein zaehlt
        nicht - eine stumme Verbindung endet erst nach Abstand + Frist."""
        if self.angemeldet is None or self.letzte_nachricht is None:
            return 0.0
        return self.letzte_nachricht - self.angemeldet

    async def _frist(self, aufruf, was: str):
        """aufruf abwarten, laengstens antwortfrist s. Laeuft sie ab, schweigt
        der Miniserver: ConnectionError, damit der Aufrufer neu verbindet."""
        try:
            return await asyncio.wait_for(aufruf, self.antwortfrist)
        except asyncio.TimeoutError as err:
            if self.antwortfrist is None or str(err):   # Zeitlimit von aiohttp selbst
                raise
            raise ConnectionError(f"Miniserver antwortet nicht auf {was} "
                                  f"(keine Antwort in {self.antwortfrist:g} s)") from None

    async def _recv_text(self) -> str:
        assert self._ws is not None
        while True:
            msg = await self._ws.receive()
            if msg.type == aiohttp.WSMsgType.BINARY:
                continue  # 8-Byte-Header ueberspringen
            if msg.type == aiohttp.WSMsgType.TEXT:
                return msg.data
            if msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.CLOSING,
                            aiohttp.WSMsgType.ERROR):
                raise ConnectionError(f"WS geschlossen im Handshake ({msg.type})")

    async def _cmd_json(self, command: str, name: str | None = None) -> dict:
        assert self._ws is not None
        await self._ws.send_str(command)
        return json.loads(await self._frist(self._recv_text(), name or command))

    async def _cmd_value(self, command: str) -> str:
        payload = await self._cmd_json(command)
        return str((payload.get("LL") or {}).get("value") or "")

    async def stream(self, on_value: ValueCallback,
                     on_weather: WeatherCallback | None = None) -> None:
        """Empfaengt Status-Tabellen und ruft on_value(uuid, wert) je Aenderung.

        on_weather(uuid, eintraege) wird zusaetzlich gerufen, wenn die Anlage
        Wetterdaten schickt (nur mit Loxone-Wetterdienst).

        Mit keepalive_abstand geht so oft "keepalive" raus. Kommt dann
        keepalive_abstand + antwortfrist lang keine Nachricht, endet die
        Verbindung mit ConnectionError. Die Grenze gilt je Nachricht, auch fuer
        den Voll-Dump nach der Anmeldung; der braucht im LAN einen Bruchteil."""
        ws = self._ws          # lokal: close() setzt self._ws auf None
        assert ws is not None
        wach = asyncio.create_task(self._keepalive(ws)) if self.keepalive_abstand else None
        try:
            await self._empfangen(ws, on_value, on_weather)
        finally:
            if wach is not None:
                wach.cancel()

    async def _keepalive(self, ws: aiohttp.ClientWebSocketResponse) -> None:
        """Alle keepalive_abstand s "keepalive" senden, unabhaengig vom
        eingehenden Verkehr: Die 5-Minuten-Grenze zaehlt, was der Client sendet."""
        while True:
            await asyncio.sleep(self.keepalive_abstand)
            try:
                await ws.send_str("keepalive")
            except Exception as err:     # Verbindung zu: das merkt _empfangen()
                log.debug("WS: keepalive nicht gesendet (%s)", err or type(err).__name__)
                return

    async def _empfangen(self, ws: aiohttp.ClientWebSocketResponse, on_value: ValueCallback,
                         on_weather: WeatherCallback | None) -> None:
        pending_ident: int | None = None
        seen_unknown: set[int] = set()
        keepalive_beantwortet = False
        stille = (self.keepalive_abstand + self.antwortfrist
                  if self.keepalive_abstand and self.antwortfrist else None)
        while True:
            try:
                msg = await ws.receive(timeout=stille)
            except asyncio.TimeoutError:
                raise ConnectionError(
                    f"Miniserver antwortet nicht mehr (keine Nachricht in {stille:g} s)") from None
            if msg.type in (aiohttp.WSMsgType.BINARY, aiohttp.WSMsgType.TEXT):
                self.letzte_nachricht = time.monotonic()
            if msg.type == aiohttp.WSMsgType.BINARY:
                data = msg.data
                if len(data) == 8 and data[0] == 0x03:
                    if data[1] == 6 and not keepalive_beantwortet:
                        # Einmal je Verbindung: zeigt im Log, dass die Anlage
                        # keepalive kennt (sonst endete jede ruhige Verbindung).
                        keepalive_beantwortet = True
                        log.info("WS: Miniserver beantwortet keepalive")
                    # Ein Header ohne Nutzdaten (keepalive-Antwort) kuendigt nichts an
                    pending_ident = data[1] if struct.unpack_from("<I", data, 4)[0] else None
                    continue
                ident, pending_ident = pending_ident, None
                if ident == 2:
                    self._parse_values(data, on_value)
                elif ident == 3:
                    self._parse_texts(data, on_value)
                elif ident == 7:
                    if on_weather is not None:
                        self._parse_weather(data, on_weather)
                elif ident is not None and ident not in seen_unknown:
                    # Einmal pro Verbindung melden: sonst bliebe unbemerkt, dass
                    # der Miniserver eine Tabelle schickt, die hier keiner liest.
                    seen_unknown.add(ident)
                    log.info("WS-Tabelle mit unbekannter Kennung %s (%d Byte) ignoriert",
                             ident, len(data))
            elif msg.type == aiohttp.WSMsgType.TEXT:
                pending_ident = None  # Kommando-Antwort im Stream ignorieren
            elif msg.type == aiohttp.WSMsgType.ERROR:
                log.warning("WS-Stream beendet (%s)", msg.type)
                break
            elif msg.type in (aiohttp.WSMsgType.CLOSE, aiohttp.WSMsgType.CLOSING,
                              aiohttp.WSMsgType.CLOSED):
                break   # wie zuvor bei `async for` ohne Warnung; stream_task meldet den Abbruch

    @staticmethod
    def _parse_values(data: bytes, on_value: ValueCallback) -> None:
        for off in range(0, len(data) - 23, 24):
            uuid = format_uuid(data[off:off + 16])
            val = struct.unpack("<d", data[off + 16:off + 24])[0]
            on_value(uuid, val)

    @staticmethod
    def _parse_weather(data: bytes, on_weather: WeatherCallback) -> None:
        """Wetter-Tabelle (Kennung 7) in Eintragslisten je UUID zerlegen.

        Aufbau siehe Modul-Docstring. Laengen werden vor jedem Zugriff geprueft:
        ein abgeschnittenes oder unerwartet aufgebautes Paket wird verworfen,
        nicht halb gelesen."""
        off = 0
        while off + 24 <= len(data):
            uuid = format_uuid(data[off:off + 16])
            count = struct.unpack("<i", data[off + 20:off + 24])[0]
            off += 24
            if count < 0 or off + count * _WX_ENTRY.size > len(data):
                log.warning("Wetter-Tabelle unplausibel (%s Eintraege, %d Byte Rest) — verworfen",
                            count, len(data) - off)
                return
            entries = []
            for _ in range(count):
                entries.append(dict(zip(_WX_FIELDS, _WX_ENTRY.unpack_from(data, off))))
                off += _WX_ENTRY.size
            on_weather(uuid, entries)

    @staticmethod
    def _parse_texts(data: bytes, on_value: ValueCallback) -> None:
        off = 0
        while off + 36 <= len(data):
            uuid = format_uuid(data[off:off + 16])
            tlen = struct.unpack("<I", data[off + 32:off + 36])[0]
            text = data[off + 36:off + 36 + tlen].decode("utf-8", "replace")
            on_value(uuid, text)
            off += (36 + tlen + 3) & ~3  # auf 4-Byte-Grenze aufrunden

    async def close(self) -> None:
        if self._ws is not None:
            await self._ws.close()
        if self._session is not None:
            await self._session.close()
        self._ws = self._session = None
