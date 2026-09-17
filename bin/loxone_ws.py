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
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import ssl
import struct
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


def format_uuid(b: bytes) -> str:
    d1 = struct.unpack("<I", b[0:4])[0]
    d2 = struct.unpack("<H", b[4:6])[0]
    d3 = struct.unpack("<H", b[6:8])[0]
    d4 = b[8:16].hex()
    return f"{d1:08x}-{d2:04x}-{d3:04x}-{d4}"


class LoxoneWS:
    def __init__(self, host: str, port: int, user: str, jwt: str,
                 hash_alg: str = "SHA1", verify_tls: bool = False, secure: bool = True):
        self.host = host
        self.port = port
        self.user = user
        self.jwt = jwt
        self.hash_alg = (hash_alg or "SHA1").upper()
        self.verify_tls = verify_tls
        self.secure = secure          # False = Gen1 (ws:// statt wss://)
        self._session: aiohttp.ClientSession | None = None
        self._ws: aiohttp.ClientWebSocketResponse | None = None

    def _ssl(self) -> ssl.SSLContext:
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        if not self.verify_tls:
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
        return ctx

    async def connect(self) -> None:
        self._session = aiohttp.ClientSession()
        scheme = "wss" if self.secure else "ws"
        url = f"{scheme}://{self.host}:{self.port}/ws/rfc6455"
        log.info("WS verbinde %s", url)
        self._ws = await self._session.ws_connect(
            url, ssl=(self._ssl() if self.secure else None),
            protocols=["remotecontrol"], max_msg_size=0)

        # 1) getkey -> HMAC(token) -> authwithtoken
        key_hex = await self._cmd_value("jdev/sys/getkey")
        digestmod = hashlib.sha256 if self.hash_alg == "SHA256" else hashlib.sha1
        token_hash = hmac.new(bytes.fromhex(key_hex), self.jwt.encode(), digestmod).hexdigest()
        auth = await self._cmd_json(f"authwithtoken/{token_hash}/{self.user}")
        code = str((auth.get("LL") or {}).get("Code") or (auth.get("LL") or {}).get("code"))
        if code != "200":
            raise ConnectionError(f"authwithtoken fehlgeschlagen: {auth}")
        log.info("WS authentifiziert")

        # 2) Status-Updates einschalten (loest sofort einen Voll-Dump aus)
        await self._ws.send_str("jdev/sps/enablebinstatusupdate")

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

    async def _cmd_json(self, command: str) -> dict:
        assert self._ws is not None
        await self._ws.send_str(command)
        return json.loads(await self._recv_text())

    async def _cmd_value(self, command: str) -> str:
        payload = await self._cmd_json(command)
        return str((payload.get("LL") or {}).get("value") or "")

    async def stream(self, on_value: ValueCallback,
                     on_weather: WeatherCallback | None = None) -> None:
        """Empfaengt Status-Tabellen und ruft on_value(uuid, wert) je Aenderung.

        on_weather(uuid, eintraege) wird zusaetzlich gerufen, wenn die Anlage
        Wetterdaten schickt (nur mit Loxone-Wetterdienst)."""
        assert self._ws is not None
        pending_ident: int | None = None
        seen_unknown: set[int] = set()
        async for msg in self._ws:
            if msg.type == aiohttp.WSMsgType.BINARY:
                data = msg.data
                if len(data) == 8 and data[0] == 0x03:
                    pending_ident = data[1]
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
            elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                log.warning("WS-Stream beendet (%s)", msg.type)
                break

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
