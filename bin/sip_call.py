"""Direkter Gen-1-SIP-Anruf; Signalisierung hier, G.711-RTP in Android.

Kein Registrar, Proxy, ICE oder Medienrelay. Ein Objekt besitzt einen Anruf und
seinen UDP-Empfang bis zum Auflegen. Zugangsdaten verlassen Python nicht.
"""
from __future__ import annotations

import asyncio
import contextlib
import ipaddress
import os
import re
import socket
import time

import sip_probe as P

T1 = 0.5
T2 = 4.0
END_TIMEOUT = 4.0


def _tag(value: str) -> str:
    m = re.search(r"(?:^|;)\s*tag=([^;\s]+)", value)
    return m.group(1) if m else ""


def _branch(value: str) -> str:
    m = re.search(r"(?:^|;)\s*branch=([^;\s]+)", value)
    return m.group(1) if m else ""


def _new_branch() -> str:
    return "z9hG4bK" + os.urandom(12).hex()


def parse_sdp(sdp: str) -> dict:
    """G.711-Audioantwort: Medien-c=/Richtung haben Vorrang vor Sitzungswerten.
    Nur unverschluesseltes IPv4 RTP/AVP, 8 kHz mono, volle Sprechrichtung.
    """
    session: dict = {}
    audio = None
    current = session
    for line in str(sdp or "").replace("\r\n", "\n").splitlines():
        if line.startswith("m="):
            fields = line[2:].split()
            current = {"fields": fields, "maps": {}}
            if fields[:1] == ["audio"] and audio is None:
                audio = current
        elif line.startswith("c="):
            current["connection"] = line[2:].split()
        elif line in ("a=sendrecv", "a=sendonly", "a=recvonly", "a=inactive"):
            current["direction"] = line[2:]
        elif line.startswith("a=rtpmap:"):
            match = re.fullmatch(r"a=rtpmap:(\d+)\s+(\S+)\s*", line, re.I)
            if match:
                current.setdefault("maps", {})[match.group(1)] = match.group(2).upper()
    if not audio:
        raise ValueError("Die SIP-Antwort enthält kein Audio")
    fields = audio["fields"]
    if len(fields) < 4 or fields[2].upper() != "RTP/AVP":
        raise ValueError("Die Türstation unterstützt kein direktes RTP/AVP-Audio")
    try:
        port = int(fields[1])
    except ValueError:
        raise ValueError("Ungültiger RTP-Port der Türstation") from None
    if not 0 < port < 65536:
        raise ValueError("Die Türstation hat Audio abgelehnt (RTP-Port)")
    connection = audio.get("connection", session.get("connection", []))
    try:
        if len(connection) != 3 or connection[:2] != ["IN", "IP4"]:
            raise ValueError
        host = str(ipaddress.IPv4Address(connection[2]))
        addr = ipaddress.IPv4Address(host)
        if addr.is_unspecified or addr.is_multicast or host == "255.255.255.255":
            raise ValueError
    except ValueError:
        raise ValueError("Die Türstation nennt keine nutzbare IPv4-RTP-Adresse") from None
    if audio.get("direction", session.get("direction", "sendrecv")) != "sendrecv":
        raise ValueError("Die Türstation bietet kein beidseitiges Audio an")
    for pt in fields[3:]:
        # Es werden ausschliesslich die angebotenen festen Payload-Typen akzeptiert.
        codec = {"0": "PCMU", "8": "PCMA"}.get(pt)
        if codec and audio["maps"].get(pt, codec + "/8000") in (codec + "/8000", codec + "/8000/1"):
            return {"remoteHost": host, "remotePort": port, "codec": codec,
                    "payloadType": int(pt), "sampleRate": 8000, "ptime": 20}
    raise ValueError("Die Türstation bietet weder PCMA noch PCMU mit 8 kHz an")


class _Wire(asyncio.DatagramProtocol):
    def __init__(self) -> None:
        self.queue: asyncio.Queue = asyncio.Queue()

    def datagram_received(self, data: bytes, addr) -> None:
        self.queue.put_nowait((data, addr))

    def error_received(self, exc: Exception) -> None:
        self.queue.put_nowait((exc, None))


class SipCall:
    """Ein direkter SIP-Anruf mit einem bereits in Android gebundenen RTP-Port."""
    def __init__(self, host: str, user: str, password: str, rtp_port: int,
                 timeout: float = 20) -> None:
        self.host, self.user, self.password = host, user, password
        self.rtp_port, self.timeout = rtp_port, max(0.1, float(timeout))
        self.state, self.error, self.media = "idle", "", {}
        self._transport = None
        self._wire = None
        self._receiver = None
        self._setup_task = None
        self._cancel_task = None
        self._linger_task = None
        self._stop_requested = False
        self._stop_lock = asyncio.Lock()
        self._queues: dict[tuple, asyncio.Queue] = {}
        self._acks: dict[tuple, tuple[bytes, tuple]] = {}
        self._dialog = None
        self._contact_peer = None
        self._peer = None
        self._remote_bye = None
        self._invite = None
        self._cseq = 0

    async def start(self) -> dict:
        """Aufbauen; Fehler werfen und in state/error ablegen. Stop bleibt parallel moeglich."""
        if self._setup_task is None:
            self._setup_task = asyncio.create_task(self._run_start())
        try:
            return await asyncio.shield(self._setup_task)
        except asyncio.CancelledError:
            await self.stop()
            raise

    async def _run_start(self) -> dict:
        self.state = "ending" if self._stop_requested else "connecting"
        deadline = time.monotonic() + self.timeout
        try:
            if self._stop_requested:
                raise RuntimeError("Anruf abgebrochen")
            if isinstance(self.rtp_port, bool) or not isinstance(self.rtp_port, int) or not 0 < self.rtp_port < 65536:
                raise ValueError("Ungültiger lokaler RTP-Port")
            if any(x in str(v) for v in (self.host, self.user) for x in ("\r", "\n", "<", ">")):
                raise ValueError("Ungültige SIP-Adresse")
            raw_host = str(self.host).strip()
            if raw_host.lower().startswith("sips:") or "?" in raw_host:
                raise ValueError("Gen-1-Gegensprechen benötigt direktes SIP über UDP")
            params = raw_host.split(";", 1)[1] if ";" in raw_host else ""
            if params and any(p.lower() != "transport=udp" for p in params.split(";")):
                raise ValueError("Die SIP-Adresse benötigt einen nicht unterstützten Transport oder eine Route")
            try:
                host, port = P.ziel(self.host)
            except ValueError:
                raise ValueError("Ungültige SIP-Adresse") from None
            if ":" in host:
                raise ValueError("Gen-1-Gegensprechen benötigt IPv4")
            loop = asyncio.get_running_loop()
            addresses = await asyncio.wait_for(
                loop.getaddrinfo(host, port, family=socket.AF_INET, type=socket.SOCK_DGRAM),
                timeout=max(0.001, deadline - time.monotonic()))
            if self._stop_requested:
                raise RuntimeError("Anruf abgebrochen")
            self._peer = addresses[0][4]
            self._target_host = host
            # Eine verbundene Hilfs-Socket bestimmt die LAN-Adresse fuer SDP.
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as route:
                route.connect(self._peer)
                local_ip = route.getsockname()[0]
            self._wire = _Wire()
            self._transport, _ = await asyncio.wait_for(
                loop.create_datagram_endpoint(
                    lambda: self._wire, local_addr=(local_ip, 0), family=socket.AF_INET),
                timeout=max(0.001, deadline - time.monotonic()))
            local_port = self._transport.get_extra_info("sockname")[1]
            self._local = f"{local_ip}:{local_port}"
            self._uri = P.sip_uri(self.user, host, port)
            self._call_id = os.urandom(16).hex() + "@loxpanel"
            self._from = f"<sip:loxpanel@{self._local}>;tag={os.urandom(8).hex()}"
            self._to = f"<{self._uri}>"
            self._receiver = asyncio.create_task(self._receive())
            sdp = (f"v=0\r\no=loxpanel 1 1 IN IP4 {local_ip}\r\ns=LoxPanel\r\n"
                   f"c=IN IP4 {local_ip}\r\nt=0 0\r\nm=audio {self.rtp_port} RTP/AVP 8 0\r\n"
                   "a=rtpmap:8 PCMA/8000\r\na=rtpmap:0 PCMU/8000\r\na=ptime:20\r\na=sendrecv\r\n")
            auth = ""
            for attempt in range(3):
                self._cseq += 1
                invite = {"uri": self._uri, "to": self._to, "branch": _new_branch(),
                          "cseq": self._cseq, "auth": auth, "sdp": sdp}
                self._invite = invite
                answer = await self._transaction("INVITE", invite, deadline)
                if answer.code in (401, 407) and not self._stop_requested and attempt < 2:
                    auth = self._authorization(answer, "INVITE", self._uri)
                    continue
                if 200 <= answer.code < 300:
                    self._establish(answer)
                    if self._stop_requested:
                        await self._bye()
                        raise RuntimeError("Anruf abgebrochen")
                    self.media = parse_sdp(answer.rumpf)
                    if not answer.wert("content-type").lower().startswith("application/sdp"):
                        raise ValueError("Die SIP-Antwort enthält kein SDP")
                    if answer.alle("record-route"):
                        raise ValueError("SIP-Routen über einen Proxy werden nicht unterstützt")
                    self.state = "connected"
                    return dict(self.media)
                raise RuntimeError(f"Die Türstation antwortet mit SIP {answer.code} {answer.grund}".strip())
            raise RuntimeError("Die Türstation lehnt die SIP-Anmeldung ab")
        except asyncio.CancelledError:
            await self._close()
            self.media = {}
            self.state = "idle" if self._stop_requested else "error"
            self.error = "" if self._stop_requested else "SIP-Anruf abgebrochen"
            raise
        except (ValueError, RuntimeError, OSError) as exc:
            message = ("Anruf abgebrochen" if self._stop_requested else
                       "Keine Antwort auf den SIP-Anruf" if isinstance(exc, asyncio.TimeoutError) else str(exc))
            if self._dialog and self._transport:
                with contextlib.suppress(Exception):
                    await self._bye()
            await self._close()
            self.media = {}
            self.state = "idle" if self._stop_requested else "error"
            self.error = "" if self._stop_requested else message
            raise ValueError(message) from exc

    def _request(self, method: str, context: dict) -> bytes:
        body = context.get("sdp", "")
        lines = [f"{method} {context['uri']} SIP/2.0",
                 f"Via: SIP/2.0/UDP {self._local};branch={context['branch']};rport",
                 "Max-Forwards: 70", f"From: {self._from}", f"To: {context['to']}",
                 f"Call-ID: {self._call_id}", f"CSeq: {context['cseq']} {method}"]
        if method == "INVITE":
            lines += [f"Contact: <sip:loxpanel@{self._local}>", "Accept: application/sdp"]
        lines.append("User-Agent: LoxPanel")
        if context.get("auth"):
            lines.append(context["auth"])
        if body:
            lines.append("Content-Type: application/sdp")
        return ("\r\n".join(lines + [f"Content-Length: {len(body.encode('utf-8'))}", "", body])).encode("utf-8")

    def _send(self, packet: bytes, destination=None) -> None:
        if self._transport:
            self._transport.sendto(packet, destination or self._peer)

    async def _transaction(self, method: str, context: dict, deadline: float) -> P.Antwort:
        key = (context["branch"], context["cseq"], method)
        queue: asyncio.Queue = asyncio.Queue()
        self._queues[key] = queue
        packet = self._request(method, context)
        interval, next_send = T1, 0.0
        provisional = False
        stopped_at = None
        try:
            while True:
                now = time.monotonic()
                if method == "INVITE" and self._stop_requested:
                    if stopped_at is None:
                        stopped_at = now
                        deadline = min(deadline, now + END_TIMEOUT)
                    if provisional and self._cancel_task is None:
                        self._cancel_task = asyncio.create_task(self._cancel(context))
                if now >= deadline:
                    raise RuntimeError("Keine Antwort auf den SIP-Anruf" if method == "INVITE"
                                       else f"Keine Antwort auf SIP {method}")
                if now >= next_send and not (method == "INVITE" and provisional):
                    self._send(packet, context.get("destination"))
                    next_send = now + interval
                    interval = interval * 2 if method == "INVITE" else min(interval * 2, T2)
                wait = min(0.1, deadline - now)
                if not (method == "INVITE" and provisional):
                    wait = min(wait, max(0.001, next_send - now))
                try:
                    answer = await asyncio.wait_for(queue.get(), wait)
                except asyncio.TimeoutError:
                    continue
                if isinstance(answer, Exception):
                    raise RuntimeError(f"SIP-Netzwerkfehler: {answer}")
                if answer.code < 200:
                    provisional = True
                    if method != "INVITE":
                        interval = T2
                    continue
                if method == "INVITE":
                    self._ack(answer, context)
                return answer
        finally:
            self._queues.pop(key, None)

    async def _cancel(self, invite: dict) -> None:
        with contextlib.suppress(RuntimeError):
            await self._transaction("CANCEL", {k: v for k, v in invite.items() if k not in ("sdp", "auth")},
                                    time.monotonic() + END_TIMEOUT)

    def _contact(self, answer: P.Antwort) -> tuple[str, tuple]:
        contact = answer.wert("contact")
        match = re.search(r"<([^<>]+)>", contact)
        uri = match.group(1) if match else contact.split(";", 1)[0].strip()
        if not uri.lower().startswith("sip:") or any(c in uri for c in ("\r", "\n", " ", "?", ",")):
            raise ValueError("Die SIP-Antwort nennt keinen nutzbaren Contact")
        params = uri.split(";", 1)[1] if ";" in uri else ""
        if params and any(p.lower() != "transport=udp" for p in params.split(";")):
            raise ValueError("Der SIP-Contact benötigt einen nicht unterstützten Transport oder eine Route")
        host, port = P.ziel(uri)
        if host not in (self._target_host, self._peer[0]):
            raise ValueError("Der SIP-Contact verweist auf eine andere Gegenstelle")
        return uri, (self._peer[0], port)

    def _ack(self, answer: P.Antwort, invite: dict) -> None:
        context = dict(invite)
        context.pop("sdp", None)
        context.pop("auth", None)
        context["to"] = answer.wert("to") or self._to
        destination = self._peer
        if answer.code < 300:
            context["branch"] = _new_branch()
            with contextlib.suppress(ValueError):
                context["uri"], destination = self._contact(answer)
        packet = self._request("ACK", context)
        self._acks[(invite["branch"], invite["cseq"], "INVITE", _tag(context["to"]))] = (packet, destination)
        self._send(packet, destination)

    def _establish(self, answer: P.Antwort) -> None:
        to = answer.wert("to")
        if not _tag(to) or _tag(answer.wert("from")) != _tag(self._from):
            raise ValueError("Die SIP-Antwort nennt keinen passenden Dialog")
        uri, destination = self._contact(answer)
        self._contact_peer = destination
        self._dialog = {"uri": uri, "to": to, "destination": destination}

    def _authorization(self, answer: P.Antwort, method: str, uri: str) -> str:
        header = "www-authenticate" if answer.code == 401 else "proxy-authenticate"
        if not self.password:
            raise ValueError("Die Türstation verlangt ein SIP-Passwort")
        error = "Die Türstation nennt keine unterstützte SIP-Digest-Anmeldung"
        for challenge in answer.alle(header):
            try:
                value = P.digest(challenge, self.user, self.password, method, uri)
                return ("Authorization" if answer.code == 401 else "Proxy-Authorization") + ": " + value
            except ValueError as exc:
                error = str(exc)
        raise ValueError(error)

    async def _bye(self) -> None:
        dialog, self._dialog = self._dialog, None
        if not dialog or not self._transport:
            return
        auth = ""
        deadline = time.monotonic() + min(self.timeout, END_TIMEOUT)
        for attempt in range(3):
            self._cseq += 1
            context = dict(dialog, branch=_new_branch(), cseq=self._cseq, auth=auth)
            answer = await self._transaction("BYE", context, deadline)
            if answer.code in (401, 407) and attempt < 2:
                auth = self._authorization(answer, "BYE", dialog["uri"])
                continue
            if not 200 <= answer.code < 300:
                raise RuntimeError(f"Die Türstation lehnt SIP BYE ab ({answer.code})")
            return

    async def _receive(self) -> None:
        while self._transport:
            data, sender = await self._wire.queue.get()
            if isinstance(data, Exception):
                for queue in self._queues.values():
                    queue.put_nowait(data)
                if self.state == "connected":
                    self.error, self.state, self.media = f"SIP-Netzwerkfehler: {data}", "error", {}
                    self._linger_task = asyncio.create_task(self._close_later())
                continue
            if not sender or sender[0] != self._peer[0] or sender[1] not in (
                    self._peer[1], (self._contact_peer or self._peer)[1]):
                continue
            answer = P.antwort_lesen(data)
            if answer is not None:
                cseq = answer.wert("cseq").split()
                if answer.wert("call-id") != self._call_id or len(cseq) != 2 or not cseq[0].isdigit():
                    continue
                key = (_branch(answer.wert("via")), int(cseq[0]), cseq[1])
                cached = self._acks.get((*key, _tag(answer.wert("to")))) if answer.code >= 200 else None
                if cached:
                    self._send(*cached)
                    continue
                queue = self._queues.get(key)
                if queue:
                    queue.put_nowait(answer)
            else:
                self._incoming(data, sender)

    def _incoming(self, data: bytes, sender: tuple) -> None:
        # Derselbe Headerparser kann nach Ersatz der Request-Zeile Kurzformen lesen.
        first, separator, remainder = data.partition(b"\n")
        parts = first.decode("utf-8", "replace").strip().split()
        if not separator or len(parts) != 3 or parts[0] != "BYE" or parts[2] != "SIP/2.0":
            return
        request = P.antwort_lesen(b"SIP/2.0 200 OK\n" + remainder)
        if request is None or request.wert("call-id") != self._call_id:
            return
        dialog = self._dialog or self._remote_bye
        cseq = request.wert("cseq").split()
        if (not dialog or _tag(request.wert("from")) != _tag(dialog["to"])
                or _tag(request.wert("to")) != _tag(self._from)
                or len(cseq) != 2 or cseq[1] != "BYE" or not cseq[0].isdigit()):
            return
        lines = ["SIP/2.0 200 OK"]
        for name in ("via", "from", "to", "call-id", "cseq"):
            lines.extend(f"{name}: {value}" for value in request.alle(name))
        self._send(("\r\n".join(lines + ["Content-Length: 0", "", ""])).encode(), sender)
        self._remote_bye, self._dialog = dialog, None
        self._stop_requested = True
        self.state, self.media = "idle", {}
        if self._linger_task is None:
            self._linger_task = asyncio.create_task(self._close_later())

    async def _close_later(self) -> None:
        await asyncio.sleep(0.5)
        await self._close()

    async def _close(self) -> None:
        if self._transport:
            self._transport.close()
            self._transport = None
        current = asyncio.current_task()
        tasks = [t for t in (self._receiver, self._cancel_task, self._linger_task)
                 if t and t is not current and not t.done()]
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self._queues.clear()

    async def stop(self) -> None:
        """Auflegen/Abbrechen; wiederholte Aufrufe und ein paralleles start sind erlaubt."""
        async with self._stop_lock:
            self._stop_requested = True
            deadline = time.monotonic() + 8.0
            if self._setup_task and not self._setup_task.done():
                self.state = "ending"
                try:
                    await asyncio.wait_for(asyncio.shield(self._setup_task),
                                           max(0.001, deadline - time.monotonic()))
                except asyncio.TimeoutError:
                    self._setup_task.cancel()
                    await asyncio.gather(self._setup_task, return_exceptions=True)
                except (RuntimeError, ValueError, asyncio.CancelledError):
                    pass
            if self._transport:
                self.state = "ending"
                with contextlib.suppress(RuntimeError, ValueError, asyncio.TimeoutError):
                    await asyncio.wait_for(self._bye(), max(0.001, deadline - time.monotonic()))
            await self._close()
            self.state, self.media = "idle", {}
