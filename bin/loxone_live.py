"""LoxHASP Live-Anbindung (Phase 2) - Wrapper um die loxone-api-Bibliothek.

Die loxone-api-LoxoneClient-API (bestaetigt an v0.1.25):
    LoxoneClient(*, host, user, password, port=443, verify_tls=True, timeout_s=120.0)
    await client.authenticate()          # getkey2/getjwt-Token-Flow
    await client.load_structure()        # LoxAPP3.json
    await client.jdev_get("sps/io/<uuid>[/<cmd>]")   # State lesen / Befehl senden
    client.jwt                           # aktuelles Token (fuer spaeteren WS-Ausbau)

Wichtig: Die Bibliothek bietet KEINEN Live-Event-Push (kein subscribe/listen).
Phase 2 liest Werte daher per Polling ueber jdev_get. Phase 2b ersetzt das
durch einen eigenen WebSocket-Event-Stream (wss://<host>/ws/rfc6455 +
enablebinstatusupdate + Binaerparsing), der das vorhandene Token weiterverwendet.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable

try:
    from loxone_api import LoxoneClient
except ImportError:  # Import ohne installierte Lib erlaubt (Skelett/Tests)
    LoxoneClient = None  # type: ignore

log = logging.getLogger("loxhasp.live")

ValueCallback = Callable[[str, Any], None]


def extract_value(resp: Any) -> Any:
    """Holt den nackten Wert aus einer jdev-Antwort (Form variiert je Endpunkt)."""
    if isinstance(resp, dict):
        ll = resp.get("LL")
        if isinstance(ll, dict) and "value" in ll:
            return ll["value"]
        if "value" in resp:
            return resp["value"]
    return resp


class LoxoneLive:
    def __init__(self, host: str, user: str, password: str,
                 port: int = 443, verify_tls: bool = False):
        if LoxoneClient is None:
            raise RuntimeError("Paket 'loxone-api' nicht installiert (pip install loxone-api).")
        self.host = host
        self.user = user
        self.password = password
        self.port = port
        self.verify_tls = verify_tls
        self._client: LoxoneClient | None = None
        self._callbacks: list[ValueCallback] = []
        self.structure: dict | None = None

    def on_value(self, cb: ValueCallback) -> None:
        self._callbacks.append(cb)

    def _emit(self, uuid: str, value: Any) -> None:
        for cb in self._callbacks:
            try:
                cb(uuid, value)
            except Exception:  # ein Callback-Fehler darf den Loop nicht killen
                log.exception("Fehler in on_value-Callback fuer %s", uuid)

    async def connect(self) -> dict:
        self._client = LoxoneClient(
            host=self.host, user=self.user, password=self.password,
            port=self.port, verify_tls=self.verify_tls)
        await self._client.__aenter__()
        await self._client.authenticate()
        self.structure = await self._client.load_structure()
        log.info("Loxone verbunden, %d Controls geladen",
                 len(self.structure.get("controls", {})))
        return self.structure

    async def read(self, uuid: str) -> Any:
        assert self._client is not None, "connect() zuerst aufrufen"
        return extract_value(await self._client.jdev_get(f"sps/io/{uuid}"))

    async def send_command(self, uuid: str, cmd: str) -> Any:
        assert self._client is not None, "connect() zuerst aufrufen"
        return await self._client.jdev_get(f"sps/io/{uuid}/{cmd}")

    async def watch(self, uuids: list[str], interval: float = 1.0) -> None:
        """Phase-2-Live-Mechanismus: pollt die UUIDs und meldet Aenderungen.

        Ersetzt sich in Phase 2b durch einen echten WebSocket-Event-Stream.
        """
        last: dict[str, Any] = {}
        log.info("Starte Polling fuer %d UUIDs (alle %.1fs)", len(uuids), interval)
        while True:
            for u in uuids:
                try:
                    val = await self.read(u)
                except Exception as err:  # einzelner Fehler stoppt den Loop nicht
                    log.debug("read(%s) fehlgeschlagen: %s", u, err)
                    continue
                if last.get(u) != val:
                    last[u] = val
                    self._emit(u, val)
            await asyncio.sleep(interval)

    async def close(self) -> None:
        if self._client is not None:
            await self._client.__aexit__(None, None, None)
            self._client = None
