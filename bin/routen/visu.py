"""Der WebSocket der Visu (/ws): welche Ansicht ein Panel bekommt (Entwurf,
Wunsch des Agenten, Zuordnung des Geraets, ?panel=), Kopplungscode, die
theme- und view-Nachrichten, Navigation, Befehle, Gesten und das Aufraeumen
beim Trennen.

Die Handler holen die App aus request.app["app"]; main() in webvisu.py traegt
sie in die Routentabelle ein. Importiert webvisu nicht (App nur als Typangabe)."""
from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import TYPE_CHECKING

from aiohttp import web, WSMsgType

from geraete import KIOSK_APPS, NEULADEN_STUNDE
from konfig import _clean_screen, KACHEL_WACHSEN, PANE_ANTEIL, STAT_RANGES, SV_STATUS_MAX
from routen.gemeinsam import server_stand
from statistik import STAT_DEFAULT_RANGE

if TYPE_CHECKING:   # nur fuer die Typangabe, kein Import zur Laufzeit (webvisu importiert hierher)
    from webvisu import App

log = logging.getLogger("loxpanel.webvisu")   # derselbe Logger wie der Server


async def ws_handler(request: web.Request) -> web.WebSocketResponse:
    app: App = request.app["app"]
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    dev = (request.query.get("device", "") or "").strip()[:60]
    pid = request.query.get("panel", "")
    # ?entwurf=<Token>: ein noch nicht gespeichertes Profil (Vorschau aus dem Konfigurator).
    # Er geht der Geraete-Zuordnung unten vor: ein Vorschau-Fenster erbt die Geraetekennung
    # aus dem localStorage (derselbe Ursprung) und wuerde sonst auf ein fremdes Profil
    # umgelenkt. Unbekannt, abgelaufen oder fuer ein anderes Profil: das gespeicherte.
    ent = (request.query.get("entwurf", "") or "")[:64]
    roh = app.entwurf_profil(ent, pid) if ent else None
    agenten = app._agenten_der_visu(dev, request.remote or "") if dev else []
    # Wahl, die der Agent noch nicht gemeldet hat: Chromium startete vorher neu
    # (Absturz, Auto-Reload, Neustart des Agenten) und fragt nach der alten
    # Ansicht. Die Visu zeigt schon die, die der Agent gleich uebernimmt.
    offen = next((app.agent_wunsch[a["ip"]] for a in agenten if a["ip"] in app.agent_wunsch), None)
    if offen is not None and roh is None:
        pid = offen
    # Frisch verbundenes Geraet direkt auf die Ansicht setzen, die ihm zusteht
    # (ansicht_fuer_geraet: laufender Betriebsmodus, sonst die zugeordnete),
    # statt der Start-Ansicht aus ?panel= -> ohne Reload-Flackern gleich die
    # richtige Visu. Was in der Start-Adresse oder der kiosk.conf steht, gilt
    # nur noch fuer ein Geraet ohne Zuordnung.
    if dev and roh is None and offen is None:
        soll = app.ansicht_fuer_geraet(dev)
        if soll is not None and soll != app.ansicht_wirksam(pid):
            pid = soll
            # auch dem Agenten, sonst meldete er weiter ?panel= (dessen
            # Abschaltzeit und Neustartintervall, naechster Kiosk-Start)
            for a in agenten:
                app.agent_wunsch[a["ip"]] = soll
    prof = app.resolve_profile(pid, roh)
    app.conn_prof[ws] = prof
    app.conn_dev[ws] = dev
    kiosk = request.query.get("kiosk", "")
    app.conn_info[ws] = {"dev": dev, "kiosk": kiosk if kiosk in KIOSK_APPS else "",
                         "ip": request.remote or "", "ts": time.time()}
    if prof.get("entwurf"):
        app.conn_info[ws]["entwurf"] = ent   # api_entwurf laedt diese Vorschau bei Aenderungen neu
    if ent:
        app.conn_info[ws]["vorschau"] = True   # Vorschaufenster, auch mit abgelaufenem Token: kein Geraet
    if not dev:   # Browser ohne Namen: Kopplungscode (mitgeschickt oder neu)
        app.conn_info[ws]["code"] = app.kopplungscode(request.query.get("code", ""))
    first_tab = prof["tabs"][0] if prof["tabs"] else "favoriten"
    app.conn_route[ws] = {"view": "tab", "tab": first_tab}
    log.info("Panel verbunden: '%s' (Tabs %s, Räume %s, Kategorien %s)", prof["id"],
             prof["tabs"], "alle" if prof["rooms"] is None else len(prof["rooms"]),
             "alle" if prof["cats"] is None else len(prof["cats"]))
    # Display-Einstellungen gehen auch an die Visu: ohne Agent (Android-Panel,
    # Tablet mit Kiosk-App) schaltet die Seite das Display selbst ab und laedt
    # sich periodisch neu. `agent` sagt ihr, ob ein Agent das uebernimmt.
    await ws.send_json({"t": "theme", "vars": prof["vars"], "tabs": prof["tabs"],
                        "tabMeta": app._tab_meta(prof["tabs"], prof), "title": prof["title"],
                        "lang": prof["lang"], "fill": prof["fill"], "split": prof["split"],
                        "catFilter": prof["catFilter"],   # Leiste filtert statt zu springen
                        "tileLayout": prof["tileLayout"],  # Kachel-Aufbau ("" = neu, "classic")
                        "tileSet": prof["tileSet"],        # Kachel-Set ("" = Standard)
                        "tileSetAufbau": prof["tileSetAufbau"],   # ... seine Kachel-Art ("lx"|"mitte"|"kreis")
                        "tileSetLeiste": prof["tileSetLeiste"],   # ... seine Tab-Leiste ("pille"|"oben"|"links")
                        "gridAuto": app.effective_grid_auto(prof, dev),   # automatisches Raster: Zielkachel px (Geraet vor Profil), 0 = fest
                        "gridGrow": KACHEL_WACHSEN,   # ... Kacheln wachsen bis dahin, wenn alle auf eine Seite passen
                        "paneCols": prof["paneCols"],   # Widget-Breite in Kachelspalten (0 = Automatik)
                        "paneShare": PANE_ANTEIL,       # ... Anteil der Spalten in der Automatik
                        "panes": prof.get("panes") or {},
                        "svPane": prof.get("svPane") or "",   # rechte Spalte der Uhr-Seite
                        "scale": app.effective_scale(prof, dev),  # Skalierung (Geraet vor Profil)
                        "dpmsOff": app.panel_dpms(prof["id"], roh, dev),
                        "pinMerken": prof["pinMerken"],   # Visu-PIN behalten, Sek. (0 = jedes Mal)
                        "gesten": prof["gesten"],         # Zwei-Finger-Gesten (Loxone-Standard) an
                        # ... mit Hinweis-Symbol (reserviert die Fusszeile unter dem Kachelfeld)
                        "gestenHinweis": prof["gesten"] and prof["gestenHinweis"],
                        "reloadHours": app.panel_reload(prof["id"], roh),
                        "reloadAt": NEULADEN_STUNDE,   # nachts neu laden, wenn reloadHours fehlt
                        "night": {**app.panel_night(prof["id"], roh, dev), "on": app._night_on},
                        # Meldet der Praesenzmelder des Geraets gerade jemanden,
                        # bleibt das Display an - auch nach einem Neuladen.
                        "presence": app._presence_on.get(dev, False),
                        "agent": app._has_agent(dev),
                        # Vorschau eines ungespeicherten Entwurfs: die Visu kennzeichnet sie;
                        # ein Token, der nichts mehr trifft (abgelaufen), meldet sie auch
                        "entwurf": bool(prof.get("entwurf")) if ent else None,
                        "stand": server_stand()})   # anderer Stand als beim Laden: Seite neu laden
    _first = app.render(app.conn_route[ws], prof)
    await ws.send_json(_first)
    app._last_sent.setdefault(ws, {})["view"] = _first
    # Vorschau am Geraet beendet, waehrend es neu lud oder offline war: gleich zurueck. Auch
    # mit einem inzwischen abgelaufenen Token - sonst zeigte es das Profil des Entwurfs
    ende = app.vorschau_ende.get(dev) if dev and ent else None
    if ende and ende["token"] == ent:
        del app.vorschau_ende[dev]
        await app._neu_laden(ws, {"t": "switch", "panel": ende["zurueck"], "entwurf": ""})
    # Einrichtungshinweis, solange es keine Struktur vom Miniserver gibt
    await app._einrichtung_melden(neu=ws)
    # Verbindungszustand (Miniserver erreichbar?) und Takt des Lebenszeichens
    await app._verbindung_melden(neu=ws)
    # Browser ohne Namen: Kopplungscode, und die Karte "Dieses Geraet
    # einrichten" nur ohne ?panel= in der Adresse. Mit ?panel= hat jemand das
    # Geraet bewusst eingerichtet (Fully, WallPanel, alte Start-Adresse): die
    # Karte laege sonst nach jedem Neustart ueber der Visu und fienge die
    # Tipps ab. Der Konfigurator meldet das Geraet mit seinem Code trotzdem
    # (Banner "Neues Geraet gefunden", device_list anonymous[].code). Ein
    # Vorschaufenster des Konfigurators (?entwurf=) ist kein Geraet: kein Code.
    if not dev and not ent:
        await ws.send_json(app._kopplung_msg(app.conn_info[ws]["code"], not request.query.get("panel")))
    # Player-Pane fordert der Client selbst an (setplayer), sobald ein Tab mit
    # Player-Pane aktiv ist — je Tab eine eigene Zone moeglich.
    # Kalender/Wetter fuer die Uhr-Startseite sofort mitschicken (falls schon geladen)
    if app._front is not None:
        await ws.send_json(app._front)
    try:
        async for msg in ws:
            if msg.type != WSMsgType.TEXT:
                continue
            try:
                data = json.loads(msg.data)
            except ValueError:
                continue
            if data.get("t") == "nav" and isinstance(data.get("route"), dict):
                route = data["route"]
                app.conn_route[ws] = route
                try:
                    view_msg = app.render(route, app.conn_prof.get(ws, prof))
                except Exception:
                    # Detailseite wirft -> nicht die Verbindung abreissen lassen
                    # (sonst Reconnect-Loop). Fehler loggen, Hinweis anzeigen.
                    log.exception("render() (nav) fehlgeschlagen fuer route %s", route)
                    view_msg = {"t": "view", "title": "Fehler", "route": route,
                                "blocks": [{"k": "status", "text": "Diese Ansicht konnte nicht geladen werden."}]}
                await ws.send_json(view_msg)
                # Auch die Navigation sendet am Tick vorbei — eintragen, sonst
                # schickt der naechste Tick dieselbe Ansicht ein zweites Mal.
                app._last_sent.setdefault(ws, {})["view"] = view_msg
                # Beim Oeffnen einer AudioZone / Musikauswahl die Zonen-Favoriten
                # aktiv anfordern; das frische Ergebnis wird per broadcaster
                # nachgereicht (roomfav/get befuellt den sourceList-State).
                if route.get("view") in ("control", "sources") and route.get("id"):
                    task = asyncio.create_task(app.prime_favs(route["id"]))
                    app.bg_tasks.add(task)
                    task.add_done_callback(app.bg_tasks.discard)
            elif data.get("t") == "idle":
                # Visu ohne Kiosk-JS meldet Leerlauf -> Display ueber Treiber aus,
                # ausser der Praesenzmelder des Geraets sieht gerade jemanden
                if dev and not app._presence_on.get(dev):
                    app._spawn(app.display_drivers(False, dev))
            elif data.get("t") == "cmd":
                pin = data.get("pin")
                code = await app.command(data.get("uuid"), data.get("cmd"), pin)
                if pin is not None:
                    # uuid/cmd: die Visu ordnet das Ergebnis ihrem Befehl zu
                    # (Druecken und Loslassen kommen kurz hintereinander);
                    # code None = keine Antwort, keine abgelehnte PIN.
                    await ws.send_json({"t": "cmdresult", "ok": code == "200", "code": code,
                                        "uuid": data.get("uuid"), "cmd": data.get("cmd")})
                elif code != "200" and data.get("uuid") and data.get("cmd"):
                    # Sichtbar machen statt still verschlucken (Details im Log)
                    await ws.send_json({"t": "notify", "level": "warn", "secs": 4, "text":
                                        "Befehl nicht ausgeführt – Miniserver antwortet nicht" if code is None
                                        else f"Befehl nicht ausgeführt (Miniserver meldet {code})"})
            elif data.get("t") == "geste":
                # Zwei-Finger-Geste (Loxone-Standard): der Server sucht Raum,
                # Bausteine und Befehle, die Visu blendet die Antwort ein
                antwort = await app.geste(ws, data)
                if antwort:
                    await ws.send_json(antwort)
            elif data.get("t") == "setplayer":
                # Client meldet die AudioZone der aktiven Player-Pane (oder "" = keine).
                zone = str(data.get("zone") or "").strip()
                if zone:
                    app.conn_player[ws] = zone
                    try:
                        pb = app.player_blocks(zone)
                        if pb is not None:
                            _pm = app._pane_msg("player", zone, pb)
                            await ws.send_json(_pm)
                            app._last_sent.setdefault(ws, {})["player"] = _pm
                    except Exception:
                        log.exception("player_blocks (setplayer) fehlgeschlagen (%s)", zone)
                else:
                    app.conn_player.pop(ws, None)
            elif data.get("t") == "setenergy":
                # Client meldet die EFM/EnergyManager2-Kachel der aktiven
                # Energiefluss-Pane (oder "" = keine).
                euid = str(data.get("uuid") or "").strip()
                if euid:
                    app.conn_energy[ws] = euid
                    try:
                        eb = app.energy_blocks(euid)
                        if eb is not None:
                            _em = {"t": "energy", **eb}
                            await ws.send_json(_em)
                            app._last_sent.setdefault(ws, {})["energy"] = _em
                    except Exception:
                        log.exception("energy_blocks (setenergy) fehlgeschlagen (%s)", euid)
                else:
                    app.conn_energy.pop(ws, None)
            elif data.get("t") == "setchart":
                # Client meldet die Bausteine der aktiven Verlaufs-Pane (ein oder
                # mehrere, gestapelt) und den dort gewaehlten Zeitraum. "" = keine Pane.
                _cuu = tuple(x.strip() for x in str(data.get("uuid") or "").split(",")
                             if x.strip())[:SV_STATUS_MAX]
                rng = data.get("range") if data.get("range") in STAT_RANGES else STAT_DEFAULT_RANGE
                if _cuu:
                    app.conn_chart[ws] = (_cuu, rng)
                    try:
                        _cm = {"t": "chart", **app.chart_stack(_cuu, rng)}
                        await ws.send_json(_cm)
                        app._last_sent.setdefault(ws, {})["chart"] = _cm
                    except Exception:
                        log.exception("chart_stack (setchart) fehlgeschlagen (%s)", _cuu)
                else:
                    app.conn_chart.pop(ws, None)
            elif data.get("t") == "screen":
                # Das Panel meldet seine Bildschirmgroesse - beim Verbinden und
                # nach jeder Groessenaenderung. Nur fuer die Anzeige unter
                # Settings -> Panels; nichts davon steuert den Server.
                if ws in app.conn_info:
                    app.conn_info[ws]["screen"] = _clean_screen(data)
            elif data.get("t") == "setsvstatus":
                # Client meldet die Bausteine der Status-Spalte seines
                # Screensavers (oder [] = keine). Antwort sofort, damit die
                # Spalte beim Einblenden nicht leer bleibt.
                _uu = tuple(x.strip() for x in (data.get("uuids") or [])
                            if isinstance(x, str) and x.strip())[:SV_STATUS_MAX]
                if _uu:
                    app.conn_status[ws] = _uu
                    try:
                        sb = app.status_blocks(_uu)
                        _sm = {"t": "svstatus", "items": sb}
                        await ws.send_json(_sm)
                        app._last_sent.setdefault(ws, {})["svstatus"] = _sm
                    except Exception:
                        log.exception("status_blocks (setsvstatus) fehlgeschlagen")
                else:
                    app.conn_status.pop(ws, None)
            elif data.get("t") == "setcamera":
                # Client meldet die Intercom-Kachel der aktiven Kamera-Pane
                # (oder "" = keine).
                cuid = str(data.get("uuid") or "").strip()
                if cuid:
                    app.conn_camera[ws] = cuid
                    try:
                        ib = app.intercom_blocks(cuid)
                        if ib is not None:
                            await ws.send_json(app._pane_msg("camera", cuid, ib))
                    except Exception:
                        log.exception("intercom_blocks (setcamera) fehlgeschlagen (%s)", cuid)
                else:
                    app.conn_camera.pop(ws, None)
    finally:
        app.conn_route.pop(ws, None)
        app.conn_prof.pop(ws, None)
        app.conn_dev.pop(ws, None)
        app.conn_info.pop(ws, None)
        app.conn_player.pop(ws, None)
        app.conn_energy.pop(ws, None)
        app.conn_chart.pop(ws, None)
        app.conn_camera.pop(ws, None)
        app.conn_status.pop(ws, None)
        app.conn_geste.pop(ws, None)
    return ws


