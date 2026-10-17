"""Intercom: Kameras speichern (/api/settings/intercom), den SIP-Zugang zeigen
und pruefen (/api/sip, /api/sip/pruefen), Gegensprechen ueber den Server
(/api/intercom/talk/*) und das Kamerabild ueber den MJPEG-Proxy (/mjpeg).

Die Handler holen die App aus request.app["app"]; main() in webvisu.py traegt
sie in die Routentabelle ein. Importiert webvisu nicht (App nur als Typangabe)."""
from __future__ import annotations

import asyncio
import hmac
import ipaddress
import logging
import os
import re
from typing import TYPE_CHECKING

import aiohttp
from aiohttp import web

import sip_probe
from bausteine.gemeinsam import _clean, INTERCOM_TYPES
from intercom_talk import TalkBusy
from intercomdienst import _gesichert_felder, _sip_zugang
from konfig import _intercom_config, _load_cfg, _write_cfg
from miniserver import KEIN_SIP, OhneGesicherteDetails, ZugangFehler

if TYPE_CHECKING:   # nur fuer die Typangabe, kein Import zur Laufzeit (webvisu importiert hierher)
    from webvisu import App

log = logging.getLogger("loxpanel.webvisu")   # derselbe Logger wie der Server


async def api_settings_intercom(request: web.Request) -> web.Response:
    app: App = request.app["app"]
    try:
        data = await request.json()
    except (ValueError, aiohttp.ContentTypeError):
        return web.json_response({"ok": False, "error": "kein gültiges JSON"}, status=400)
    items = data.get("intercoms") or {}
    cfg = _load_cfg()
    ic = dict(cfg.get("intercom", {}))
    for uuid, e in items.items():
        if not isinstance(e, dict):
            continue
        cur = ic.get(uuid)
        cur = dict(cur) if isinstance(cur, dict) else ({"url": cur} if isinstance(cur, str) else {})
        cur["url"] = str(e.get("url", "")).strip()
        cur["user"] = str(e.get("user", "")).strip()
        if e.get("pass"):
            cur["pass"] = str(e["pass"])
        if cur.get("url"):
            ic[uuid] = cur
        else:
            ic.pop(uuid, None)
    cfg["intercom"] = ic
    try:
        _write_cfg(cfg)
    except OSError as err:
        return web.json_response({"ok": False, "error": str(err)}, status=500)
    app.intercom_cfg = _intercom_config()
    log.info("Intercom-Settings gespeichert (%d Einträge)", len(ic))
    return web.json_response({"ok": True})


async def api_sip(request: web.Request) -> web.Response:
    """Settings -> SIP: die Intercoms der Anlage mit ihrem SIP-Zugang aus den
    gesicherten Details. Das Passwort verlaesst den Server nie, die Routen haben
    keine Anmeldung; es heisst nur, ob es eines gibt (hasPass wie bei
    /api/settings). Nennt eine Intercom keinen, steht ohneSip darin und, wenn
    sie gesicherte Details hat, unter felder, welche Felder diese haben und ob
    sie gefuellt sind, ohne Werte.
    Laedt erst, wenn der Konfigurator den Reiter oeffnet: jede Intercom mit
    gesicherten Details kostet eine verschluesselte Anfrage an den Miniserver.
    type ist der Bausteintyp (Intercom = Tuersteuerung, IntercomV2 = Baustein
    Intercom), deviceType wie im Baustein (Strukturdoku 17.0): bei Intercom 0
    andere oder unbekannte Tuerstation, 1 Loxone Intercom, 2 Loxone Intercom
    XL; bei IntercomV2 0 andere oder unbekannte, 1 Loxone Intercom."""
    app: App = request.app["app"]
    liste = []
    for uuid, c in app.controls.items():
        if c.get("type") not in INTERCOM_TYPES:
            continue
        e = {"uuid": uuid, "name": _clean(c.get("name")), "type": c.get("type"),
             "room": _clean((app.rooms.get(c.get("room")) or {}).get("name")),
             "deviceType": (c.get("details") or {}).get("deviceType")}
        # ohneSip: der Miniserver nennt keinen SIP-Zugang (anders als bei einem
        # Fehler mit Verbindung oder Rechten); der Konfigurator sagt dann, wo er
        # in Loxone Config hingehoert
        try:
            details = await app.secured_details(uuid)
        except OhneGesicherteDetails as err:
            e.update(error=str(err), ohneSip=True)
        except ZugangFehler as err:
            e["error"] = str(err)
        else:
            sip = _sip_zugang(details)
            if sip:
                e["sip"] = {"host": sip["host"], "user": sip["user"], "hasPass": bool(sip["pass"])}
            else:
                e.update(error=KEIN_SIP, felder=_gesichert_felder(details), ohneSip=True)
        liste.append(e)
    liste.sort(key=lambda e: (e["name"].lower(), e["room"].lower()))
    return web.json_response({"connected": app.client is not None, "intercoms": liste})


async def api_sip_pruefen(request: web.Request) -> web.Response:
    """Settings -> SIP -> "Verbindung prüfen": OPTIONS an die Tuerstation mit
    dem SIP-Zugang aus den gesicherten Details (sip_probe). Body {"uuid"}. Die
    Adresse kommt vom Miniserver, nie aus der Anfrage: so schickt die Route die
    Anmeldung nur an die Tuerstation. Die Antwort sagt, ob sie angenommen
    wurde, das Passwort steht nicht darin."""
    app: App = request.app["app"]
    try:
        data = await request.json()
    except (ValueError, aiohttp.ContentTypeError):
        return web.json_response({"ok": False, "error": "kein gültiges JSON"}, status=400)
    uuid = str(data.get("uuid") or "") if isinstance(data, dict) else ""
    if (app.controls.get(uuid) or {}).get("type") not in INTERCOM_TYPES:
        return web.json_response({"ok": False, "error": "Unbekannte Intercom"}, status=404)
    try:
        sip = await app.intercom_sip(uuid)
    except ZugangFehler as err:
        return web.json_response({"ok": False, "error": str(err)})
    erg = await sip_probe.pruefen(sip["host"], sip["user"], sip["pass"])
    log.info("SIP-Prüfung %s: %s", erg.get("ziel"), erg.get("anmeldung") or erg.get("error"))
    return web.json_response({"ok": True, **erg})


def _native_talk(request: web.Request) -> None:
    """Nur die eingebettete App kennt den Prozess-Token; keine LAN-Call-API."""
    token = os.environ.get("LOXPANEL_INTERCOM_TOKEN", "")
    try:
        local = ipaddress.ip_address(request.remote or "").is_loopback
    except ValueError:
        local = False
    if not local or not token or not hmac.compare_digest(
            request.headers.get("X-LoxPanel-Intercom", ""), token):
        raise web.HTTPForbidden(text="Gegensprechen ist nur in der nativen LoxPanel-App verfügbar")


def _talk_session(data: dict) -> str:
    session = data.get("session")
    if not isinstance(session, str) or not re.fullmatch(r"[A-Za-z0-9-]{16,64}", session):
        raise web.HTTPBadRequest(text="Ungültige Verbindung")
    return session


async def _talk_json(request: web.Request) -> dict:
    try:
        data = await request.json()
    except (ValueError, aiohttp.ContentTypeError):
        raise web.HTTPBadRequest(text="Kein gültiges JSON") from None
    if not isinstance(data, dict):
        raise web.HTTPBadRequest(text="Kein gültiges JSON-Objekt")
    return data


async def api_intercom_talk_start(request: web.Request) -> web.Response:
    _native_talk(request)
    data = await _talk_json(request)
    session = _talk_session(data)
    uuid, port = data.get("uuid"), data.get("rtpPort")
    app: App = request.app["app"]
    if not isinstance(uuid, str) or (app.controls.get(uuid) or {}).get("type") != "Intercom":
        return web.json_response({"ok": False, "message": "Gegensprechen unterstützt nur die Intercom Gen-1"}, status=400)
    if type(port) is not int or not 1024 <= port <= 65535:
        return web.json_response({"ok": False, "message": "Ungültiger RTP-Port"}, status=400)
    try:
        result = await app.intercom_talk.start(session, uuid, port)
    except TalkBusy as err:
        return web.json_response({"ok": False, "message": str(err)}, status=409)
    return web.json_response(result)


async def api_intercom_talk_status(request: web.Request) -> web.Response:
    _native_talk(request)
    session = _talk_session(dict(request.query))
    return web.json_response(request.app["app"].intercom_talk.status(session))


async def api_intercom_talk_stop(request: web.Request) -> web.Response:
    _native_talk(request)
    session = _talk_session(await _talk_json(request))
    return web.json_response(await request.app["app"].intercom_talk.stop(session))


async def mjpeg_handler(request: web.Request) -> web.StreamResponse:
    """Relais des MJPEG-Streams der Tuerstation (mit Auth) -> Browser. Die
    Kamera kommt aus LoxPanel oder vom Miniserver (App.intercom_video).

    Eigene ClientSession (nicht icon_session): mit dem SSL-Connector der
    icon_session liefert die Mobotix nur ein Einzelbild statt des Streams.
    """
    app: App = request.app["app"]
    cam = await app.intercom_video(request.query.get("id", ""))
    if cam is None:
        return web.Response(status=404)
    url = cam["url"]
    # Session und Antwort der Kamera werden in jedem Fall freigegeben, auch
    # wenn der Handler mitten im Verbindungsaufbau abgebrochen wird
    # (Herunterfahren) - sonst bleiben Socket und Connector offen.
    sess = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=None, sock_read=30))
    upstream = None
    try:
        try:
            auth = aiohttp.BasicAuth(cam["user"], cam["pass"]) if cam["user"] else None
            upstream = await sess.get(url, auth=auth)
        except (aiohttp.ClientError, ValueError):
            # ValueError: unbrauchbarer Host ("cam..lan") oder Benutzer, der nicht
            # in den Basic-Auth-Kopf passt (Doppelpunkt, Zeichen ausserhalb Latin-1)
            return web.Response(status=502, text="camera unreachable")
        if upstream.status != 200:
            return web.Response(status=502, text=f"camera status {upstream.status}")

        ctype = upstream.headers.get("Content-Type", "multipart/x-mixed-replace")
        resp = web.StreamResponse(status=200, headers={
            "Content-Type": ctype, "Cache-Control": "no-cache, no-store"})
        await resp.prepare(request)
        try:
            async for chunk in upstream.content.iter_any():
                await resp.write(chunk)
        except (aiohttp.ClientError, ConnectionResetError, asyncio.CancelledError):
            pass
        return resp
    finally:
        if upstream is not None:
            upstream.release()
        await sess.close()


