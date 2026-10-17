"""Geraete und Agenten: der Agent meldet sich (/api/agent/announce), Liste und
Befehle der Agenten, Geraete speichern und lesen (/api/devices), Ansicht
wechseln, Vorschau beenden, Namen vergeben, Display, Betriebsmodus
(/api/mode), Neuladen, eine Seite oeffnen (/api/goto), Hinweis
(/api/notify), Testton und das Installationsskript des Agenten.

Die Handler holen die App aus request.app["app"]; main() in webvisu.py traegt
sie in die Routentabelle ein. Importiert webvisu nicht (App nur als Typangabe)."""
from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import TYPE_CHECKING

import aiohttp
from aiohttp import web

from geraete import AGENT_BEFEHL_TIMEOUT, AGENT_KANN_PANEL, AGENT_ONLINE, VORSCHAU_GERAET_DAUER
from konfig import _devices_export, _is_tab, _sanitize_devices
from routen.gemeinsam import _json_or_empty, _push, _push_filter, server_stand
from sicherung import _kennwoerter_einsetzen

if TYPE_CHECKING:   # nur fuer die Typangabe, kein Import zur Laufzeit (webvisu importiert hierher)
    from webvisu import App

log = logging.getLogger("loxpanel.webvisu")   # derselbe Logger wie der Server


INSTALL_SH = Path(__file__).resolve().parents[2] / "deploy" / "install-agent.sh"   # bin/routen/ -> Repo


async def install_script(request: web.Request) -> web.Response:
    """Liefert das Panel-Installer-Skript (fuer 'curl ... | bash' vom Panel aus)."""
    try:
        txt = INSTALL_SH.read_text(encoding="utf-8").replace("\r\n", "\n")
    except OSError:
        return web.Response(status=404, text="install-agent.sh nicht gefunden")
    return web.Response(text=txt, content_type="text/plain")


# ---- Panel-Agenten (Fernstart der Displays) ----
async def api_agent_announce(request: web.Request) -> web.Response:
    """Panel-Agent meldet sich periodisch (Auto-Discovery). Steht fuer ihn eine
    Ansicht an (agent_wunsch) und kann er sie uebernehmen, nennt die Antwort
    sie als `panel`, und die Geraeteeinstellungen gelten schon fuer sie."""
    app: App = request.app["app"]
    try:
        d = await request.json()
    except (ValueError, aiohttp.ContentTypeError):
        d = {}
    ip = str(d.get("ip") or "").strip() or request.remote or "?"
    feats = d.get("features")
    feats = [f for f in feats if isinstance(f, str)][:8] if isinstance(feats, list) else []
    panel = str(d.get("panel") or "")
    app.agents[ip] = {"ip": ip, "name": str(d.get("name") or ip)[:60],
                      "panel": panel, "port": int(d.get("port") or 8130),
                      "kiosk": bool(d.get("kiosk")), "ts": time.time(), "features": feats}
    wunsch = app.agent_wunsch.get(ip)
    if wunsch is not None and (wunsch == panel or AGENT_KANN_PANEL not in feats):
        app.agent_wunsch.pop(ip, None)   # gemeldet, also uebernommen
        wunsch = None
    # Keine offene Wahl: meldet der Agent eine andere Ansicht als die, die dem
    # Geraet zusteht (Zuordnung oder Betriebsmodus, Schritt 2), bekommt er sie -
    # so gilt sie auch nach einem Neustart des Panels mit altem PANEL in der kiosk.conf
    if wunsch is None and AGENT_KANN_PANEL in feats:
        soll = app.ansicht_fuer_geraet(app.agents[ip]["name"])
        if soll is not None and soll != app.ansicht_wirksam(panel):
            wunsch = soll
    pid = panel if wunsch is None else wunsch
    # Panel-spezifische Geraeteeinstellungen an den Agenten zurueckgeben
    # (der wendet sie am Geraet an, z.B. Display-Abschaltung per xset).
    out = {"ok": True, "dpmsOff": app.panel_dpms(pid, dev=app.agents[ip]["name"]), "reloadHours": app.panel_reload(pid)}
    if wunsch is not None:
        out["panel"] = wunsch
    return web.json_response(out)


async def api_agents(request: web.Request) -> web.Response:
    app: App = request.app["app"]
    now = time.time()
    out = [{**a, "online": (now - a["ts"]) < AGENT_ONLINE}
           for a in app.agents.values() if (now - a["ts"]) < 600]
    out.sort(key=lambda a: a["name"])
    return web.json_response({"agents": out})


async def api_agent_command(request: web.Request) -> web.Response:
    """Leitet Start/Reload/Stop an den Panel-Agenten weiter."""
    app: App = request.app["app"]
    try:
        d = await request.json()
    except (ValueError, aiohttp.ContentTypeError):
        return web.json_response({"ok": False, "error": "kein JSON"}, status=400)
    ip = str(d.get("ip", ""))
    action = str(d.get("action", ""))
    a = app.agents.get(ip)
    if not a:
        return web.json_response({"ok": False, "error": "Gerät nicht bekannt"}, status=404)
    if action not in ("start", "reload", "stop"):
        return web.json_response({"ok": False, "error": "unbekannte Aktion"}, status=400)
    payload = {"panel": str(d.get("panel") or "")} if action == "start" else {}
    # "Start" mit Ansicht ist eine ausdrueckliche Wahl wie "Ansicht wechseln"
    # (bei gestopptem Kiosk der einzige Weg dazu)
    wahl = action == "start"
    if wahl:
        app.agent_wunsch.pop(ip, None)   # neuer als eine noch offene Wahl
        if payload["panel"] and payload["panel"] not in app.panels:
            return web.json_response({"ok": False, "error": "unbekannte Ansicht"}, status=400)
        try:
            app.geraet_zuordnen(a["name"], payload["panel"])   # die Wahl ist die Zuordnung (Schritt 2)
        except Exception as err:
            return web.json_response({"ok": False, "error": f"Zuordnung nicht gespeichert: {err}"}, status=500)
    elif action == "reload" and ip in app.agent_wunsch:
        # Wahl noch nicht gemeldet: mit ihr neu starten, sonst oeffnete der
        # Agent die alte Ansicht und uebernaehme die neue erst danach. Sie
        # bleibt stehen, bis er sie meldet: scheitert der Befehl, uebernimmt
        # er sie mit der naechsten Meldung.
        action, payload = "start", {"panel": app.agent_wunsch[ip]}
    url = f"http://{a['ip']}:{a['port']}/{action}"
    try:
        async with aiohttp.ClientSession() as s:
            async with s.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=AGENT_BEFEHL_TIMEOUT)) as r:
                body = await r.text()
                log.info("Agent %s %s -> %s", ip, action, r.status)
                if wahl and r.status == 200:
                    # hebt den Betriebsmodus fuer das Geraet auf: sonst zoege
                    # ws_handler die Visu auf dessen Profil, der Agent bliebe
                    # bei der Wahl
                    app.ansicht_gewaehlt.add(a["name"])
                return web.json_response({"ok": r.status == 200, "status": r.status,
                                          "body": body[:200]})
    except Exception as err:
        return web.json_response({"ok": False, "error": str(err)})


async def api_mode(request: web.Request) -> web.Response:
    """Betriebsmodus-Wechsel von Loxone (virtueller Ausgang). Loxone schickt nur
    den Modusnamen, z.B.  GET /api/mode/gaeste  oder  /api/mode?name=gaeste .
    Die Zuordnung Modus -> Profil je Panel liegt in den Panel-Einstellungen."""
    app: App = request.app["app"]
    mode = request.match_info.get("mode", "")
    if not mode:
        mode = request.query.get("name") or request.query.get("mode") or ""
    if not mode and request.method == "POST":
        try:
            d = await request.json()
            mode = str(d.get("name") or d.get("mode") or "")
        except (ValueError, aiohttp.ContentTypeError):
            pass
    if not mode:
        return web.json_response({"ok": False, "error": "kein Modus angegeben"},
                                 status=400)
    results = await app.switch_mode(mode)
    log.info("Betriebsmodus '%s' -> %d Panel(s) umgeschaltet", mode, len(results))
    return web.json_response({"ok": True, "mode": mode, "switched": results})


async def api_save_devices(request: web.Request) -> web.Response:
    """Speichert die Betriebsmodus-Automatik je Panel (aus den Einstellungen)."""
    app: App = request.app["app"]
    try:
        d = await request.json()
    except (ValueError, aiohttp.ContentTypeError):
        return web.json_response({"ok": False, "error": "kein JSON"}, status=400)
    roh = d.get("devices") or {}
    # Die Zuordnung Gerät -> Ansicht (panel) setzt nur /api/device/switch; nennt
    # ein Geraet sie nicht, bleibt die gespeicherte (wie das Display-Kennwort)
    if isinstance(roh, dict):
        for name, cfg in roh.items():
            if isinstance(cfg, dict) and "panel" not in cfg and (app.devices.get(name) or {}).get("panel"):
                cfg["panel"] = app.devices[name]["panel"]
    devices = _sanitize_devices(roh, set(app.panels))
    # Leeres Display-Kennwort = unveraendert (/api/meta gibt es nicht heraus),
    # aber nur beim selben Ziel wie beim Einspielen (_KENNWORT_ZIEL), sonst
    # ginge das gespeicherte an einen anderen Host. "verworfen": eines war da,
    # das Ziel ist ein anderes. Vor _write_devices, das app.devices ersetzt.
    _, verworfen = _kennwoerter_einsetzen(
        {"devices": devices}, {"devices": app.devices},
        [("devices", n, "display", "password") for n, e in devices.items() if "display" in e],
        nur_wo_eins_war=True)
    try:
        app._write_devices(devices)
    except Exception as err:
        return web.json_response({"ok": False, "error": str(err)}, status=500)
    # Skalierung je Geraet sofort wirksam machen: jedem verbundenen Panel
    # seinen (evtl. neuen) wirksamen Faktor schicken - ohne Neuladen, das
    # beim Speichern von Profilen noetig ist, hier aber nicht.
    for ws, info in list(app.conn_info.items()):
        await app._send_or_drop(ws, {"t": "scale", "scale": app.effective_scale(
            app.conn_prof.get(ws), info.get("dev", ""))})
        # ... und die Zielkachel je Geraet: die Visu baut ihr Raster neu
        await app._send_or_drop(ws, {"t": "gridAuto", "gridAuto": app.effective_grid_auto(
            app.conn_prof.get(ws), info.get("dev", ""))})
    return web.json_response({"ok": True, "devices": _devices_export(devices),
                              "kennwortVerworfen": [p[1] for p in verworfen]})


async def api_devices_get(request: web.Request) -> web.Response:
    """Alle Anzeigegeraete (Agent, Kiosk-App, Browser) mit Online-Status,
    Ansicht und Typ; Browser ohne Namen getrennt nach IP. Dazu der Stand des
    Servers: der Konfigurator fragt hier alle paar Sekunden nach und laedt
    nach einem Update neu."""
    app: App = request.app["app"]
    return web.json_response({**app.device_list(), "stand": server_stand()})


async def api_device_switch(request: web.Request) -> web.Response:
    """Ansicht eines Geraets wechseln: {device, panel, ip}. Die offene Visu
    wechselt per WebSocket-Push (Browser laedt sich mit neuem Profil neu).
    Hat das Geraet einen Agenten, der online ist, erfaehrt er die Wahl, damit
    sie Kiosk-Neustarts uebersteht und Abschaltzeit und Neustartintervall des
    neuen Profils gelten. Zugeordnet ueber `ip` aus der Geraeteliste, nicht
    ueber den Namen: geklonte Panels melden denselben Hostnamen. Ein Agent mit
    AGENT_KANN_PANEL uebernimmt sie mit seiner naechsten Meldung ohne
    Chromium-Neustart (`agent: "announce"`, auch bei gestopptem Kiosk: der
    startet dann damit). Einen aelteren Agenten, und jeden, dessen Kiosk ohne
    offene Visu laeuft, startet /start mit dem neuen Profil neu (`agent:
    "start"`; scheitert das bei einem Agenten mit AGENT_KANN_PANEL, uebernimmt
    er sie mit der naechsten Meldung: "announce"; "" = der Agent hat die Wahl
    nicht). Die Wahl hebt den Betriebsmodus fuer das Geraet auf."""
    app: App = request.app["app"]
    try:
        d = await request.json()
    except (ValueError, aiohttp.ContentTypeError):
        return web.json_response({"ok": False, "error": "kein JSON"}, status=400)
    device = str(d.get("device") or "").strip()
    panel = str(d.get("panel") or "").strip()
    if not device:
        return web.json_response({"ok": False, "error": "device fehlt"}, status=400)
    # Vorschau eines Entwurfs am Geraet (Punkt 12): {entwurf: <Token von /api/entwurf>}. Das Profil
    # muss nicht gespeichert sein (der Assistent zeigt eines, das es noch nicht gibt), der Token
    # gehoert aber zu ihm. Nur eine verbundene Visu kann ihn zeigen: ein Agent startet den Kiosk
    # mit einer Adresse ohne Token und wuerde stattdessen das Profil von der Platte zeigen.
    tok = str(d.get("entwurf") or "").strip()
    if tok:
        if not panel or app.entwurf_profil(tok, panel) is None:
            return web.json_response({"ok": False, "error": "Entwurf unbekannt oder abgelaufen"}, status=400)
        zurueck = app.vorschau_zurueck(device)
        n = await _push(app, {"t": "switch", "panel": panel, "entwurf": tok}, "", device)
        if not n:
            return web.json_response({"ok": False, "sent": 0,
                                      "error": "Keine verbundene Visu – eine Vorschau braucht sie"})
        app.vorschau_ende.pop(device, None)
        for info in app.conn_info.values():   # unterwegs zum Entwurf (laedt gleich neu): vorschau_beenden
            if info.get("dev") == device and not info.get("neuLaden") and info.get("entwurf") != tok:
                info["entwurfKommt"] = tok
        app.vorschau_geraet[device] = {"token": tok, "id": panel, "zurueck": zurueck,
                                       "bis": time.time() + VORSCHAU_GERAET_DAUER}
        return web.json_response({"ok": True, "sent": n, "via": "ws", "agent": "", "zurueck": zurueck})
    if panel and panel not in app.panels:
        return web.json_response({"ok": False, "error": "unbekannte Ansicht"}, status=400)
    app.vorschau_geraet.pop(device, None)   # eine ausdrueckliche Wahl beendet eine Vorschau am Geraet
    app.vorschau_ende.pop(device, None)
    # Die Wahl ist die Zuordnung des Geraets (Einrichtung Schritt 2): gespeichert,
    # damit sie jeden Neustart, jede Start-Adresse und die kiosk.conf ueberlebt.
    # Ein Geraet, das gerade nicht online ist, zieht ws_handler beim Verbinden darauf.
    try:
        app.geraet_zuordnen(device, panel)
    except Exception as err:
        return web.json_response({"ok": False, "error": f"Zuordnung nicht gespeichert: {err}"}, status=500)
    n = await _push(app, {"t": "switch", "panel": panel}, "", device)
    a = app.agents.get(str(d.get("ip") or "").strip())
    weg, ok = "", False
    if a and a["name"] == device and time.time() - a["ts"] < AGENT_ONLINE:
        if AGENT_KANN_PANEL in a.get("features", ()) and (n or not a["kiosk"]):
            app.agent_wunsch[a["ip"]] = panel
            weg, ok = "announce", True
        elif a["kiosk"]:
            weg, ok = "start", await app._agent_start(a, panel)
            if not ok and AGENT_KANN_PANEL in a.get("features", ()):
                weg, ok = "announce", True   # Wahl liegt in agent_wunsch (_agent_start)
    app.ansicht_gewaehlt.add(device)
    if n:
        return web.json_response({"ok": True, "sent": n, "via": "ws", "agent": weg if ok else ""})
    if ok:
        return web.json_response({"ok": True, "sent": 1, "via": "agent", "agent": weg})
    # nicht online: die Zuordnung steht, das Geraet zeigt sie, sobald es verbindet
    return web.json_response({"ok": True, "sent": 0, "via": "", "agent": "", "offline": True})


async def api_vorschau_beenden(request: web.Request) -> web.Response:
    """Vorschau am Geraet beenden: {device}. Es kehrt zum Profil zurueck, das es vor
    der Vorschau zeigte. `beendet` sagt, ob eine Visu zurueckgeschaltet wurde."""
    app: App = request.app["app"]
    try:
        d = await request.json()
    except (ValueError, aiohttp.ContentTypeError):
        return web.json_response({"ok": False, "error": "kein JSON"}, status=400)
    device = str(d.get("device") or "").strip()
    if not device:
        return web.json_response({"ok": False, "error": "device fehlt"}, status=400)
    return web.json_response({"ok": True, "beendet": await app.vorschau_beenden(device) > 0})


async def api_device_name(request: web.Request) -> web.Response:
    """Gibt einem Browser ohne Namen einen Geraetenamen: {code, name} trifft
    genau die Verbindung mit diesem Kopplungscode, {ip, name} alle ohne
    Namen unter der IP (wie bisher). Die Visu merkt sich den Namen
    (localStorage) und verbindet sich neu."""
    app: App = request.app["app"]
    try:
        d = await request.json()
    except (ValueError, aiohttp.ContentTypeError):
        return web.json_response({"ok": False, "error": "kein JSON"}, status=400)
    ip = str(d.get("ip") or "").strip()
    code = str(d.get("code") or "").strip().upper()
    name = str(d.get("name") or "").strip()[:60]
    if not (ip or code) or not name:
        return web.json_response({"ok": False, "error": "code oder ip und name noetig"}, status=400)
    n = 0
    for ws, info in list(app.conn_info.items()):
        if info.get("dev") or (info.get("code") != code if code else info.get("ip") != ip):
            continue
        try:
            await ws.send_json({"t": "setdevice", "name": name})
            n += 1
        except ConnectionError:
            pass
    fehler = "kein Gerät ohne Namen mit diesem Code" if code else "kein Gerät ohne Namen unter dieser IP"
    return web.json_response({"ok": n > 0, "sent": n, **({} if n else {"error": fehler})})


async def api_display(request: web.Request) -> web.Response:
    """Display der Panels schalten: ?on=1|0, optional ?panel= / ?device=.
    Wirkt auf Geraete mit Kiosk-App (Fully Kiosk, LoxPanel-App), die die Visu offen haben;
    Linux-Panels mit Agent regeln das Display selbst. Auch aus Loxone nutzbar."""
    app: App = request.app["app"]
    d = await _json_or_empty(request)
    raw = d.get("on", request.query.get("on"))
    if isinstance(raw, bool):
        on = raw
    else:
        v = str(raw if raw is not None else "").strip().lower()
        if v in ("1", "true", "on", "an", "ein"):
            on = True
        elif v in ("0", "false", "off", "aus"):
            on = False
        else:
            return web.json_response({"ok": False, "error": "on=1|0 fehlt"}, status=400)
    panel, device = _push_filter(request, d)
    n = await _push(app, {"t": "display", "on": on}, panel, device)
    drivers = await app.display_drivers(on, device, panel)
    return web.json_response({"ok": True, "sent": n, "on": on, "drivers": drivers})


async def api_reload(request: web.Request) -> web.Response:
    """Laedt offene Panels neu (Server -> Browser). Optional ?panel= / ?device=.
    Auch aus Loxone per virtuellem Ausgang nutzbar."""
    app: App = request.app["app"]
    d = await _json_or_empty(request)
    panel, device = _push_filter(request, d)
    n = await _push(app, {"t": "reload"}, panel, device)
    return web.json_response({"ok": True, "reloaded": n})


async def api_goto(request: web.Request) -> web.Response:
    """Schickt offene Panels auf eine Seite. ?control=<uuid> (Detailseite) ODER
    ?tab=<favoriten|zentral|raeume|kategorien|kalender|wetter|auswahl|cat:...|room:...>.
    Optional ?panel= / ?device=."""
    app: App = request.app["app"]
    d = await _json_or_empty(request)
    control = str(d.get("control") or d.get("uuid") or request.query.get("control")
                  or request.query.get("uuid") or "").strip()
    tab = str(d.get("tab") or request.query.get("tab") or "").strip()
    if control:
        route = {"view": "control", "id": control}
    elif _is_tab(tab):
        route = {"view": "tab", "tab": tab}
    else:
        return web.json_response({"ok": False, "error": "control oder gueltiges tab noetig"},
                                 status=400)
    panel, device = _push_filter(request, d)
    n = await _push(app, {"t": "goto", "route": route}, panel, device)
    app._spawn(app.display_drivers(True, device, panel))   # Kiosk-Apps wecken
    return web.json_response({"ok": True, "route": route, "sent": n})


async def api_notify(request: web.Request) -> web.Response:
    """Blendet auf offenen Panels eine kurze Nachricht ein.
    ?text=... [&level=info|warn|crit] [&secs=5] [&panel=|&device=]."""
    app: App = request.app["app"]
    d = await _json_or_empty(request)
    text = str(d.get("text") or request.query.get("text") or "").strip()[:200]
    if not text:
        return web.json_response({"ok": False, "error": "text fehlt"}, status=400)
    level = str(d.get("level") or request.query.get("level") or "info").strip()
    if level not in ("info", "warn", "crit"):
        level = "info"
    try:
        secs = int(float(d.get("secs") or request.query.get("secs") or 5))
    except (TypeError, ValueError):
        secs = 5
    secs = max(1, min(60, secs))
    panel, device = _push_filter(request, d)
    app._spawn(app.display_drivers(True, device, panel))   # Kiosk-Apps wecken
    n = await _push(app, {"t": "notify", "text": text, "level": level, "secs": secs},
                    panel, device)
    return web.json_response({"ok": True, "sent": n})


async def api_testtone(request: web.Request) -> web.Response:
    """Schickt einen kurzen Test-Weckton an die Panel-Browser (zum Pruefen der
    Audio-Ausgabe am Geraet, z.B. YC-41PM). Mit `panel` auf ein Profil begrenzt,
    sonst an alle offenen Visu-Verbindungen. Der Ton wird im Browser per Web
    Audio erzeugt (derselbe Weg wie der echte Weckton)."""
    app: App = request.app["app"]
    try:
        d = await request.json()
    except (ValueError, aiohttp.ContentTypeError):
        d = {}
    target = str(d.get("panel") or "").strip()
    n = 0
    for ws, prof in list(app.conn_prof.items()):
        if target and (prof or {}).get("id") != target:
            continue
        if await app._send_or_drop(ws, {"t": "testtone"}):
            n += 1
    return web.json_response({"ok": True, "sent": n})


