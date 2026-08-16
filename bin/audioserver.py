"""Audio-Backend-Adapter: Wiedergabesteuerung des Loxone-Musiksystems.

Loxone-Musik läuft NICHT über den Miniserver, sondern direkt über den
Audioserver (Loxone-Music-Server-Protokoll). Favoriten-Abspielen etc. wird
deshalb hier gekapselt. Jedes Backend implementiert dasselbe Interface, sodass
später neben dem Loxone-Audioserver (echt oder MS4H-Emulation) weitere
Backends stehen können.

LoxoneAudioServerBackend spricht das Protokoll über WebSocket auf Port 7091
(unverschlüsselt, ohne Auth-Handshake). Gesteuert wird über die Loxone-
`playerid` (aus control.details.playerid) — der Audioserver mappt sie intern
auf den realen Player, es ist also KEIN hausspezifisches Zone->Player-Mapping
nötig. Die Anzeige läuft weiter über die Loxone-States (der Audioserver meldet
Wiedergabewechsel an den Miniserver zurück).
"""
from __future__ import annotations

import asyncio
import logging

import aiohttp

log = logging.getLogger("loxpanel.audio")


class AudioBackend:
    """Interface: Wiedergabesteuerung einer Zone (Loxone-playerid)."""

    async def play_roomfav(self, playerid: int, slot: int) -> bool:
        raise NotImplementedError

    async def command(self, playerid: int, cmd: str) -> bool:
        """Roh-Kommando `audio/{playerid}/{cmd}` (z.B. play, pause, volume/30)."""
        raise NotImplementedError

    async def close(self) -> None:
        pass


class LoxoneAudioServerBackend(AudioBackend):
    """Loxone-Music-Server-Protokoll über WebSocket (Port 7091)."""

    def __init__(self, host: str, port: int = 7091):
        self.host = host
        self.port = port
        self._session: aiohttp.ClientSession | None = None
        self._ws: aiohttp.ClientWebSocketResponse | None = None
        self._reader: asyncio.Task | None = None
        self._lock = asyncio.Lock()

    @property
    def url(self) -> str:
        return f"ws://{self.host}:{self.port}/"

    async def _ensure(self) -> None:
        if self._ws is not None and not self._ws.closed:
            return
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        self._ws = await self._session.ws_connect(self.url, timeout=6, heartbeat=30)
        # Eingehende Events verwerfen (Anzeige läuft über Loxone-States),
        # aber lesen, damit der Empfangspuffer nicht volläuft.
        self._reader = asyncio.ensure_future(self._drain())
        log.info("Audioserver verbunden: %s", self.url)

    async def _drain(self) -> None:
        try:
            assert self._ws is not None
            async for _ in self._ws:
                pass
        except Exception:
            pass

    async def _send(self, cmd: str) -> bool:
        async with self._lock:
            for attempt in (1, 2):  # ein Reconnect-Versuch
                try:
                    await self._ensure()
                    assert self._ws is not None
                    await self._ws.send_str(cmd)
                    log.info("audio-cmd %s", cmd)
                    return True
                except Exception as err:
                    self._ws = None
                    if attempt == 2:
                        log.warning("Audioserver-Kommando fehlgeschlagen (%s): %s", cmd, err)
                        return False
            return False

    async def play_roomfav(self, playerid: int, slot: int) -> bool:
        return await self._send(f"audio/{playerid}/roomfav/play/{slot}")

    async def command(self, playerid: int, cmd: str) -> bool:
        return await self._send(f"audio/{playerid}/{cmd}")

    async def close(self) -> None:
        if self._reader:
            self._reader.cancel()
        if self._ws is not None and not self._ws.closed:
            await self._ws.close()
        if self._session is not None and not self._session.closed:
            await self._session.close()


def make_backend(cfg: dict | None) -> AudioBackend | None:
    """Baut das Audio-Backend aus der Config oder liefert None (deaktiviert).

    cfg: {"host": "10.0.2.2", "port": 7091, "enabled": true}
    """
    if not cfg or not cfg.get("enabled", True):
        return None
    host = (cfg.get("host") or "").strip()
    if not host:
        return None
    return LoxoneAudioServerBackend(host, int(cfg.get("port", 7091)))
