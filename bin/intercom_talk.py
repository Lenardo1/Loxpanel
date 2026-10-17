"""Eine native Gen-1-Sprechverbindung; SIP-Zugang bleibt im Python-Prozess.

Die App reserviert RTP zuerst. Status-Abfragen halten die Verbindung am Leben;
ohne native Anzeige endet sie auch nach einem Prozess-/WebView-Fehler.
"""
from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable

from sip_call import SipCall

log = logging.getLogger(__name__)
LEASE_SECONDS = 15.0
ACTIVE = {"connecting", "connected", "ending"}


class TalkBusy(Exception):
    pass


class IntercomTalk:
    def __init__(self, credentials: Callable[[str], Awaitable[dict]],
                 factory=SipCall, lease: float = LEASE_SECONDS):
        self.credentials, self.factory, self.lease = credentials, factory, lease
        self.session = self.uuid = self.message = ""
        self.state = "idle"
        self.call = None
        self._run_task = self._lease_task = self._stop_task = None
        self._lock = asyncio.Lock()
        self._heartbeat = 0.0
        # Ein Stop kann den zuvor abgesendeten Start im HTTP-Netz ueberholen.
        self._cancelled: dict[str, float] = {}

    def _snapshot(self) -> dict:
        if self.call is not None and self.state == "connected":
            if self.call.state in {"idle", "error"}:
                self.state = self.call.state
                self.message = self.call.error
        result = {"ok": True, "session": self.session, "uuid": self.uuid,
                  "state": self.state, "message": self.message}
        if self.state == "connected":
            result["media"] = dict(self.call.media)
        return result

    async def start(self, session: str, uuid: str, port: int) -> dict:
        async with self._lock:
            now = time.monotonic()
            self._cancelled = {s: until for s, until in self._cancelled.items() if until > now}
            if session in self._cancelled:
                return {"ok": True, "session": session, "uuid": uuid, "state": "idle", "message": ""}
            self._snapshot()
            if self.session == session:
                if self.uuid != uuid:
                    raise TalkBusy("Diese Verbindung gehört zu einer anderen Türstation")
                self._heartbeat = now
                return self._snapshot()
            if self.state in ACTIVE:
                raise TalkBusy("Es läuft bereits ein Gespräch")
            # Eine abgeschlossene SIP-Verbindung kann noch UDP-Listener besitzen.
            await self._finish()
            # Waehrend des Aufraeumens nimmt stop() keine Sperre: ein Stop fuer
            # DIESE Sitzung kann inzwischen eingetroffen sein (Seite verlassen,
            # Taste losgelassen) - dann darf sie nicht mehr starten.
            if session in self._cancelled:
                return {"ok": True, "session": session, "uuid": uuid, "state": "idle", "message": ""}
            self.session, self.uuid, self.state, self.message = session, uuid, "connecting", ""
            self.call = None
            self._heartbeat = now
            self._run_task = asyncio.create_task(self._run(uuid, port))
            self._lease_task = asyncio.create_task(self._watch())
            return self._snapshot()

    async def _run(self, uuid: str, port: int) -> None:
        try:
            sip = await self.credentials(uuid)
            if self.state != "connecting":
                return
            self.call = self.factory(sip["host"], sip["user"], sip["pass"], port)
            await self.call.start()
            if self.state == "connecting":
                self.state = self.call.state
                self.message = self.call.error
        except asyncio.CancelledError:
            raise
        except ValueError as err:
            # SipCall meldet Protokollfehler ohne Zugangsdaten.
            if self.state == "connecting":
                self.state, self.message = "error", str(err)
        except Exception:
            if self.state == "connecting":
                self.state, self.message = "error", "SIP-Verbindung konnte nicht aufgebaut werden"
            # Keine Exception-Texte loggen: sie koennten gesicherte Details enthalten.
            log.warning("Intercom-Verbindung konnte nicht aufgebaut werden")

    def status(self, session: str) -> dict:
        if session != self.session:
            return {"ok": True, "session": session, "state": "idle", "uuid": "", "message": ""}
        self._heartbeat = time.monotonic()
        return self._snapshot()

    async def stop(self, session: str) -> dict:
        self._cancelled[session] = time.monotonic() + 60.0
        # Die Liste ist durch die lokale Bridge klein; begrenzt auch bei defekten Clients.
        if len(self._cancelled) > 128:
            self._cancelled.pop(next(iter(self._cancelled)))
        if session != self.session:
            return {"ok": True, "session": session, "state": "idle", "uuid": "", "message": ""}
        if self.state in ACTIVE and self._stop_task is None:
            self.state = "ending"
            self._stop_task = asyncio.create_task(self._finish())
        return self._snapshot()

    async def _watch(self) -> None:
        try:
            while self._snapshot()["state"] in ACTIVE:
                await asyncio.sleep(min(1.0, self.lease / 2))
                if time.monotonic() - self._heartbeat > self.lease:
                    await self.stop(self.session)
                    return
        except asyncio.CancelledError:
            pass

    async def _finish(self) -> None:
        current = asyncio.current_task()
        if self._lease_task is not None and self._lease_task is not current:
            self._lease_task.cancel()
            await asyncio.gather(self._lease_task, return_exceptions=True)
        if self.call is not None:
            try:
                await self.call.stop()
            except Exception:
                log.warning("Intercom-Verbindung konnte nicht sauber beendet werden")
        if self._run_task is not None and self._run_task is not current:
            if not self._run_task.done():
                self._run_task.cancel()
            await asyncio.gather(self._run_task, return_exceptions=True)
        self._run_task = self._lease_task = None
        self._stop_task = None
        self.state, self.message = "idle", ""

    async def close(self) -> None:
        if self._stop_task is not None:
            await self._stop_task
        await self._finish()
