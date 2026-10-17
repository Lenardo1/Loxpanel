#!/usr/bin/env python3
"""Sonde fuer den Loxone-Audioserver (Port 7091): Was antwortet er ohne Anmeldung?

Laeuft im LoxPanel-Container, weil dort aiohttp vorhanden ist und der Server
die Audioserver-Adressen aus der Miniserver-Struktur kennt:

    curl -fsSL <url dieser datei> | docker exec -i LoxPanel python3 - [playerid]

Teil 1 fragt je Audioserver per HTTP und per WebSocket die Zonenliste, den
Zonenstatus und die Raumfavoriten ab und lauscht auf audio_event-Pushs. Die
Ausgabe zeigt, ob der Audioserver Befehle ohne Anmeldung annimmt (JSON) oder
ablehnt ("command not allowed when paired").

Teil 2 holt sich mit den Miniserver-Zugangsdaten aus /app/config/loxpanel.cfg
(oder LOXPANEL_MS_*) ein App-Token (JWT) vom Miniserver und probiert damit die
Anmeldevarianten, die der Audioserver kennen koennte: secure/authenticate,
secure/init, secure/hello, Bearer-Header und Token in der URL. Nach jedem
Versuch wird audio/cfg/all gesendet; verschwindet die Fehlermeldung, ist der
Weg gefunden. Das Token erscheint in der Ausgabe nur als <JWT>. Es wird nichts
dauerhaft veraendert.
"""
import asyncio
import json
import os
import sys
import uuid as uuidlib
from pathlib import Path

import aiohttp

ARG = sys.argv[1] if len(sys.argv) > 1 else ""
FAVS_ONLY = ARG == "favs"
ROOMFAV_ONLY = ARG == "roomfav"
ROOMFAVWS_ONLY = ARG == "roomfavws"
ZONEDUMP_ONLY = ARG == "zonedump"
APPJS_ONLY = ARG == "appjs"
APPHUB_ONLY = ARG == "apphub"
AUTH_ONLY = ARG == "auth"
PLAYER = int(ARG) if ARG.isdigit() else 1
PANEL = "http://127.0.0.1:8099"
APP_DIR = Path(__file__).resolve().parent.parent if "__file__" in globals() else Path("/app")
JWT = ""   # wird in Teil 2 gesetzt, damit cut() das Token unkenntlich macht


def cut(s, n=500):
    s = str(s).replace("\n", " ")
    if JWT:
        s = s.replace(JWT, "<JWT>")
    return s if len(s) <= n else s[:n] + " …"


def miniserver_config() -> dict:
    """Zugang wie der Server: loxpanel.cfg (Settings) vor Umgebungsvariablen."""
    for base in (APP_DIR / "config", Path("/app/config")):
        f = base / "loxpanel.cfg"
        if f.is_file():
            try:
                ms = json.loads(f.read_text(encoding="utf-8")).get("miniserver", {})
            except ValueError:
                ms = {}
            if ms.get("host"):
                return ms
    env = os.environ
    if env.get("LOXPANEL_MS_HOST"):
        return {"host": env["LOXPANEL_MS_HOST"], "user": env.get("LOXPANEL_MS_USER", ""),
                "pass": env.get("LOXPANEL_MS_PASS", ""), "port": int(env.get("LOXPANEL_MS_PORT") or "443"),
                "verify_tls": env.get("LOXPANEL_MS_VERIFY_TLS", "false").lower() in ("1", "true", "yes")}
    return {}


async def fetch_jwt() -> str:
    """App-Token (permission 4) vom Miniserver, derselbe Weg wie im Server."""
    for d in (str(APP_DIR / "bin"), "/app/bin"):
        if d not in sys.path:
            sys.path.insert(0, d)
    from loxone_api import LoxoneClient
    ms = miniserver_config()
    if not ms.get("host"):
        raise RuntimeError("kein Miniserver-Zugang gefunden (loxpanel.cfg oder LOXPANEL_MS_*)")
    port = int(ms.get("port", 443))
    c = LoxoneClient(host=ms["host"], user=ms.get("user", ""), password=ms.get("pass", ""),
                     port=port, verify_tls=bool(ms.get("verify_tls", False)))
    if port == 80:   # wie _ms_https() im Server: Gen 1 spricht nur HTTP
        c.base_url = f"http://{ms['host']}:{port}/"
    async with c:
        await c.getkey2()
        return await c.authenticate()


async def listen(ws, secs):
    """Alle Nachrichten der naechsten `secs` Sekunden ausgeben."""
    loop = asyncio.get_event_loop()
    end = loop.time() + secs
    while True:
        left = end - loop.time()
        if left <= 0:
            return
        try:
            m = await asyncio.wait_for(ws.receive(), timeout=left)
        except asyncio.TimeoutError:
            return
        if m.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.CLOSE, aiohttp.WSMsgType.ERROR):
            print(f"  WS geschlossen: {m.type.name} code={m.data} {m.extra or ''}")
            return
        print(f"  WS <- {cut(m.data)}")


async def probe(host, port, volume):
    print(f"\n===== Audioserver {host}:{port}")
    async with aiohttp.ClientSession() as s:
        for path in ("audio/cfg/all", f"audio/{PLAYER}/status",
                     f"audio/cfg/getroomfavs/{PLAYER}/0/10"):
            try:
                async with s.get(f"http://{host}:{port}/{path}",
                                 timeout=aiohttp.ClientTimeout(total=6)) as r:
                    print(f"HTTP GET /{path} -> {r.status} {cut(await r.text(), 400)}")
            except Exception as err:
                print(f"HTTP GET /{path} -> Fehler: {err}")
        try:
            async with s.ws_connect(f"ws://{host}:{port}/", timeout=8) as ws:
                print("WS verbunden, 4 s lauschen:")
                await listen(ws, 4)
                cmds = ["audio/cfg/all", f"audio/{PLAYER}/status",
                        f"audio/cfg/getroomfavs/{PLAYER}/0/10"]
                if volume is not None:
                    cmds.append(f"audio/{PLAYER}/volume/{volume}")
                for cmd in cmds:
                    if ws.closed:
                        break
                    print(f"WS -> {cmd}")
                    await ws.send_str(cmd)
                    await listen(ws, 4)
        except Exception as err:
            print(f"WS Fehler: {err}")


async def ws_try(host, port, label, cmds, headers=None, query="", path="/", protocols=()):
    """Eine frische WebSocket-Verbindung, Befehle nacheinander, Antworten zeigen."""
    print(f"\n--- {label}")
    try:
        async with aiohttp.ClientSession() as s:
            async with s.ws_connect(f"ws://{host}:{port}{path}{query}", timeout=8,
                                    headers=headers or {}, protocols=protocols) as ws:
                if ws.protocol:
                    print(f"  Unterprotokoll bestaetigt: {ws.protocol}")
                await listen(ws, 1.5)
                for cmd in cmds:
                    if ws.closed:
                        print("  (Verbindung ist zu)")
                        break
                    print(f"  WS -> {cut(cmd, 120)}")
                    await ws.send_str(cmd)
                    await listen(ws, 3)
    except Exception as err:
        print(f"  WS Fehler: {cut(err)}")


async def auth_probe(host, port):
    global JWT
    print(f"\n===== Teil 2: Anmeldeversuche an {host}:{port}")
    try:
        JWT = await fetch_jwt()
    except Exception as err:
        print(f"Token vom Miniserver nicht bekommen: {cut(err)}")
        return
    print(f"App-Token vom Miniserver erhalten ({len(JWT)} Zeichen)")
    cid = str(uuidlib.uuid4())
    check = "audio/cfg/all"
    await ws_try(host, port, "secure/info/pairing und secure/hello ohne Token",
                 ["secure/info/pairing", f"secure/hello/{cid}/probe", check])
    await ws_try(host, port, "secure/authenticate/<JWT>", [f"secure/authenticate/{JWT}", check])
    await ws_try(host, port, "secure/init/<JWT>", [f"secure/init/{JWT}", check])
    await ws_try(host, port, "secure/hello/<id>/<JWT> dann authenticate/init",
                 [f"secure/hello/{cid}/{JWT}", f"secure/authenticate/{JWT}", f"secure/init/{JWT}", check])
    await ws_try(host, port, "Bearer-Header", [check], headers={"Authorization": f"Bearer {JWT}"})
    await ws_try(host, port, "Token in der URL (?token=)", [check], query=f"?token={JWT}")
    print("\n--- HTTP: secure/authenticate, dann audio/cfg/all in derselben Sitzung (Cookies)")
    try:
        async with aiohttp.ClientSession() as s:
            for path in (f"secure/authenticate/{JWT}", check, f"{check}?token={JWT}"):
                async with s.get(f"http://{host}:{port}/{path}", headers={"Authorization": f"Bearer {JWT}"},
                                 timeout=aiohttp.ClientTimeout(total=6)) as r:
                    print(f"  HTTP GET /{cut(path, 60)} -> {r.status} {cut(await r.text(), 300)}")
    except Exception as err:
        print(f"  HTTP Fehler: {cut(err)}")


async def path_probe(host, port):
    """Teil 3: Auf welchem Pfad und mit welchem Unterprotokoll antwortet der
    WebSocket ueberhaupt? Der Miniserver nutzt /ws/rfc6455 und das
    Unterprotokoll "remotecontrol"; die App verwendet dieselbe Bibliothek."""
    print(f"\n===== Teil 3: WebSocket-Pfade an {host}:{port}")
    probe_cmds = ["secure/info/pairing", "audio/cfg/all"]
    for path in ("/ws/rfc6455", "/ws", "/websocket", "/rfc6455", "/"):
        for protos in (("remotecontrol",), ()):
            label = f"Pfad {path}" + (f", Unterprotokoll {protos[0]}" if protos else ", ohne Unterprotokoll")
            await ws_try(host, port, label, probe_cmds, path=path, protocols=protos)
    print("\n--- HTTP: welche secure/*-Befehle kennt der Server (Fehlertext unterscheidet)?")
    cid = str(uuidlib.uuid4())
    try:
        async with aiohttp.ClientSession() as s:
            for path in ("secure/info/pairing", "secure/info", f"secure/hello/{cid}/probe", "secure/hello/probe",
                         "secure/init/probe", "secure/init", "secure/authenticate/probe", "secure/authenticate",
                         "audio/cfg/ready", "audio/cfg/miniserverip", "audio/cfg/getkey"):
                async with s.get(f"http://{host}:{port}/{path}", timeout=aiohttp.ClientTimeout(total=6)) as r:
                    print(f"  HTTP GET /{cut(path, 60)} -> {r.status} {cut(await r.text(), 220)}")
    except Exception as err:
        print(f"  HTTP Fehler: {cut(err)}")


async def event_probe(host, port):
    """Teil 4: Verhalten des Ereigniskanals mit Unterprotokoll remotecontrol.
    Kommen Ereignisse laufend ohne Befehl? Welcher Befehl schliesst die
    Verbindung? Antwortet secure/info/pairing allein?"""
    print(f"\n===== Teil 4: Ereigniskanal (remotecontrol) an {host}:{port}")
    print("\n--- 10 s nur hoeren, kein Befehl (Lautstaerke oder Titel am Geraet aendern zeigt Ereignisse)")
    try:
        async with aiohttp.ClientSession() as s:
            async with s.ws_connect(f"ws://{host}:{port}/", timeout=8, protocols=("remotecontrol",)) as ws:
                await listen(ws, 10)
                print(f"  Verbindung danach offen: {not ws.closed}")
    except Exception as err:
        print(f"  WS Fehler: {cut(err)}")
    for cmd in (f"audio/{PLAYER}/status", "secure/info/pairing", "audio/cfg/getkey"):
        await ws_try(host, port, f"remotecontrol, nur {cmd}", [cmd], protocols=("remotecontrol",))


async def collect_players(host, port, secs=3):
    """Playerids aus den audio_event-Pushs einer remotecontrol-Verbindung."""
    ids = {}
    try:
        async with aiohttp.ClientSession() as s:
            async with s.ws_connect(f"ws://{host}:{port}/", timeout=8, protocols=("remotecontrol",)) as ws:
                end = asyncio.get_event_loop().time() + secs
                while True:
                    left = end - asyncio.get_event_loop().time()
                    if left <= 0:
                        break
                    try:
                        m = await asyncio.wait_for(ws.receive(), timeout=left)
                    except asyncio.TimeoutError:
                        break
                    if m.type != aiohttp.WSMsgType.TEXT:
                        break
                    try:
                        data = json.loads(m.data)
                    except (ValueError, TypeError):
                        continue
                    for e in data.get("audio_event", []) or []:
                        if isinstance(e, dict) and e.get("playerid") is not None:
                            ids.setdefault(e["playerid"], (e.get("name") or "").strip())
    except Exception as err:
        print(f"  Playerids nicht lesbar: {cut(err)}")
    return ids


async def favs_probe(host, port):
    """Teil 5: Holt der gekoppelte Audioserver Favoriten heraus, bevor er die
    remotecontrol-Verbindung schliesst? Je Zone eine frische Verbindung:
    zuerst die Events abwarten, dann getroomfavs senden und die Antwort samt
    Schliess-Zeitpunkt zeigen. Nichts wird veraendert."""
    print(f"\n===== Teil 5: Favoriten ueber frische remotecontrol-Verbindungen an {host}:{port}")
    players = await collect_players(host, port)
    if not players:
        print("  Keine Playerids aus den Ereignissen — laeuft Musik? Sonst spaeter erneut.")
        return
    print("  Playerids:", ", ".join(f"{pid} ({name})" for pid, name in sorted(players.items())))
    for pid in sorted(players):
        label = f"Zone {pid} ({players[pid]})"
        got = {"result": False, "closed_after_send": False}
        try:
            async with aiohttp.ClientSession() as s:
                async with s.ws_connect(f"ws://{host}:{port}/", timeout=8, protocols=("remotecontrol",)) as ws:
                    await listen(ws, 1.5)   # Banner + erste Events schlucken
                    cmd = f"audio/cfg/getroomfavs/{pid}/0/50"
                    print(f"\n--- {label}: sende {cmd}")
                    if ws.closed:
                        print("  (Verbindung war schon zu)")
                        continue
                    await ws.send_str(cmd)
                    loop = asyncio.get_event_loop(); end = loop.time() + 6
                    while True:
                        left = end - loop.time()
                        if left <= 0:
                            break
                        try:
                            m = await asyncio.wait_for(ws.receive(), timeout=left)
                        except asyncio.TimeoutError:
                            break
                        if m.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.CLOSE, aiohttp.WSMsgType.ERROR):
                            print(f"  WS geschlossen: {m.type.name}")
                            got["closed_after_send"] = True
                            break
                        if m.type == aiohttp.WSMsgType.TEXT:
                            if "getroomfavs_result" in m.data or "roomfav" in m.data:
                                got["result"] = True
                                print(f"  >>> FAVORITEN: {cut(m.data, 700)}")
                            else:
                                print(f"  WS <- {cut(m.data, 160)}")
        except Exception as err:
            print(f"  WS Fehler: {cut(err)}")
        print(f"  Ergebnis Zone {pid}: Favoriten={got['result']}, Verbindung geschlossen={got['closed_after_send']}")


async def roomfav_probe():
    """Teil 6: Holt der MINISERVER die Raumfavoriten inline zurueck?

    Baut den Miniserver-Client wie der Server (Token-Anmeldung), laedt die
    Struktur, findet die AudioZoneV2-Zonen und schickt fuer die ersten zwei
    `jdev/sps/io/<uuidAction>/roomfav/get/0/50`. Zeigt die rohe Antwort und
    LL.value. Erwartung bei Erfolg: LL.value ist ein (evtl. prozentkodierter)
    JSON-Text mit getroomfavs_result und items (slot, name, coverurl). Damit
    liesse sich die Favoritenliste ohne Audioserver-Anmeldung fuellen.
    Es wird nichts veraendert (roomfav/get liest nur)."""
    print("\n===== Teil 6: Raumfavoriten ueber den Miniserver (roomfav/get)")
    for d in (str(APP_DIR / "bin"), "/app/bin"):
        if d not in sys.path:
            sys.path.insert(0, d)
    from loxone_api import LoxoneClient
    ms = miniserver_config()
    if not ms.get("host"):
        print("  kein Miniserver-Zugang gefunden"); return
    port = int(ms.get("port", 443))
    c = LoxoneClient(host=ms["host"], user=ms.get("user", ""), password=ms.get("pass", ""),
                     port=port, verify_tls=bool(ms.get("verify_tls", False)))
    if port == 80:
        c.base_url = f"http://{ms['host']}:{port}/"
    async with c:
        await c.getkey2()
        await c.authenticate()
        st = await c.load_structure()
    controls = st.get("controls", {}) if isinstance(st, dict) else {}
    zones = [(u, cc) for u, cc in controls.items() if isinstance(cc, dict) and cc.get("type") == "AudioZoneV2"]
    print(f"  {len(zones)} AudioZoneV2-Zonen in der Struktur")
    if not zones:
        return
    # Der Client muss fuer die Kommandos offen bleiben:
    c2 = LoxoneClient(host=ms["host"], user=ms.get("user", ""), password=ms.get("pass", ""),
                      port=port, verify_tls=bool(ms.get("verify_tls", False)))
    if port == 80:
        c2.base_url = f"http://{ms['host']}:{port}/"
    async with c2:
        await c2.getkey2()
        await c2.authenticate()
        for u, cc in zones[:2]:
            ua = cc.get("uuidAction") or u
            name = cc.get("name", "")
            print(f"\n--- Zone {name} (uuidAction {ua})")
            path = f"sps/io/{ua}/roomfav/get/0/50"
            try:
                r = await c2.jdev_get(path)
            except Exception as err:
                print(f"  jdev_get Fehler: {cut(err, 300)}"); continue
            ll = (r.get("LL") or {}) if isinstance(r, dict) else {}
            val = ll.get("value")
            code = ll.get("Code") or ll.get("code")
            print(f"  Code: {code}")
            print(f"  LL.value (roh): {cut(repr(val), 700)}")
            if isinstance(val, str) and val.strip():
                from urllib.parse import unquote
                txt = unquote(val)
                try:
                    parsed = json.loads(txt)
                    print(f"  LL.value als JSON: {cut(json.dumps(parsed, ensure_ascii=False), 700)}")
                except (ValueError, TypeError):
                    if txt != val:
                        print(f"  LL.value (url-dekodiert): {cut(txt, 500)}")
                    print("  (nicht als JSON parsebar)")


async def roomfav_ws_probe():
    """Teil 7: Kommt die Favoritenliste als Zustands-Push ueber DIESELBE
    WebSocket, die den Befehl sendet? Der Miniserver echot roomfav/get nur
    (Teil 6), die Liste kommt asynchron als Text-State. Dieser Push geht an die
    WS-Sitzung, die den Befehl abgesetzt hat. Also: eine LoxoneWS-Verbindung
    aufbauen (Status-Updates an), roomfav/get UEBER DIESE WS senden und sehen,
    welcher Text-State die Liste traegt. Nichts wird veraendert."""
    print("\n===== Teil 7: Favoriten als Zustands-Push (roomfav/get ueber die Status-WS)")
    for d in (str(APP_DIR / "bin"), "/app/bin"):
        if d not in sys.path:
            sys.path.insert(0, d)
    from loxone_api import LoxoneClient
    from loxone_ws import LoxoneWS
    ms = miniserver_config()
    if not ms.get("host"):
        print("  kein Miniserver-Zugang gefunden"); return
    host = ms["host"]; port = int(ms.get("port", 443)); secure = port != 80
    c = LoxoneClient(host=host, user=ms.get("user", ""), password=ms.get("pass", ""),
                     port=port, verify_tls=bool(ms.get("verify_tls", False)))
    if not secure:
        c.base_url = f"http://{host}:{port}/"
    async with c:
        alg = (await c.getkey2()).hashAlg
        jwt = await c.authenticate()
        st = await c.load_structure()
    controls = st.get("controls", {}) if isinstance(st, dict) else {}
    # Reverse-Map: State-UUID -> "Zone.stateName" fuer alle AudioZoneV2
    state_name = {}
    zones = []
    for u, cc in controls.items():
        if not (isinstance(cc, dict) and cc.get("type") == "AudioZoneV2"):
            continue
        zones.append((cc.get("uuidAction") or u, cc.get("name", "")))
        for sname, suid in (cc.get("states") or {}).items():
            if isinstance(suid, str):
                state_name[suid] = f"{cc.get('name','')}.{sname}"
    print(f"  {len(zones)} AudioZoneV2-Zonen, {len(state_name)} bekannte State-UUIDs")
    if not zones:
        return
    ws = LoxoneWS(host=host, port=port, user=ms.get("user", ""), jwt=jwt,
                  hash_alg=alg, verify_tls=bool(ms.get("verify_tls", False)), secure=secure)
    texts = {}
    def on_value(uuid, val):
        if isinstance(val, str):
            texts[uuid] = val
    await ws.connect()
    stream = asyncio.ensure_future(ws.stream(on_value))
    try:
        await asyncio.sleep(3)          # Voll-Dump abwarten (Basis)
        base = dict(texts)
        for ua, name in zones[:2]:
            print(f"\n--- Zone {name}: sende roomfav/get ueber die Status-WS")
            texts.clear(); texts.update(base)
            await ws._ws.send_str(f"jdev/sps/io/{ua}/roomfav/get/0/50")
            await asyncio.sleep(4)
            hits = []
            for uuid, val in texts.items():
                changed = base.get(uuid) != val
                if "getroomfavs_result" in val or ("roomfav" in val and "{" in val) or \
                   ('"slot"' in val and ("coverurl" in val or "\"name\"" in val)):
                    hits.append((uuid, val, changed))
            if hits:
                for uuid, val, changed in hits:
                    label = state_name.get(uuid, "(nicht in der Zonen-Statenliste)")
                    print(f"  >>> FAVORITEN-STATE {uuid}  [{label}]  geaendert={changed}")
                    print(f"      {cut(val, 700)}")
            else:
                ch = [(u, v) for u, v in texts.items() if base.get(u) != v]
                print(f"  keine Favoriten-Liste erkannt. Geaenderte Text-States: {len(ch)}")
                for u, v in ch[:6]:
                    print(f"    {u} [{state_name.get(u,'?')}]: {cut(v, 200)}")
    finally:
        stream.cancel()
        await ws.close()


async def zonedump_probe():
    """Teil 8: Aufbau einer AudioZoneV2 in der Struktur (states, details,
    subControls) und die ROHEN WebSocket-Antworten des Miniservers auf
    roomfav/get. LoxoneWS.stream() verwirft Text-Frames (Kommando-Antworten);
    hier wird jeder Frame gezeigt. Nichts wird veraendert."""
    print("\n===== Teil 8: AudioZoneV2-Aufbau und rohe WS-Antworten auf roomfav/get")
    for d in (str(APP_DIR / "bin"), "/app/bin"):
        if d not in sys.path:
            sys.path.insert(0, d)
    from loxone_api import LoxoneClient
    from loxone_ws import LoxoneWS, format_uuid
    import struct
    ms = miniserver_config()
    if not ms.get("host"):
        print("  kein Miniserver-Zugang gefunden"); return
    host = ms["host"]; port = int(ms.get("port", 443)); secure = port != 80
    c = LoxoneClient(host=host, user=ms.get("user", ""), password=ms.get("pass", ""),
                     port=port, verify_tls=bool(ms.get("verify_tls", False)))
    if not secure:
        c.base_url = f"http://{host}:{port}/"
    async with c:
        alg = (await c.getkey2()).hashAlg
        jwt = await c.authenticate()
        st = await c.load_structure()
    print("  Struktur-Abschnitte:", ", ".join(sorted(k for k in st.keys() if isinstance(st, dict))))
    for u, v in (st.get("mediaServer") or {}).items():
        print(f"  mediaServer {u}: {cut(json.dumps(v, ensure_ascii=False), 400)}")
    controls = st.get("controls", {}) if isinstance(st, dict) else {}
    zones = [(u, cc) for u, cc in controls.items() if isinstance(cc, dict) and cc.get("type") == "AudioZoneV2"]
    if not zones:
        print("  keine AudioZoneV2"); return
    u, cc = zones[0]
    print(f"\n--- Control {cc.get('name')} ({u}) vollstaendig:")
    print("  " + cut(json.dumps(cc, ensure_ascii=False), 3000))
    ua = cc.get("uuidAction") or u
    state_name = {suid: sname for sname, suid in (cc.get("states") or {}).items() if isinstance(suid, str)}

    ws = LoxoneWS(host=host, port=port, user=ms.get("user", ""), jwt=jwt,
                  hash_alg=alg, verify_tls=bool(ms.get("verify_tls", False)), secure=secure)
    await ws.connect()
    raw = ws._ws
    pending = {"ident": None}

    async def drain(secs, label):
        loop = asyncio.get_event_loop(); end = loop.time() + secs
        n_bin = 0; n_txt = 0
        while True:
            left = end - loop.time()
            if left <= 0:
                break
            try:
                m = await asyncio.wait_for(raw.receive(), timeout=left)
            except asyncio.TimeoutError:
                break
            if m.type == aiohttp.WSMsgType.TEXT:
                n_txt += 1
                print(f"  [{label}] TEXT <- {cut(m.data, 1500)}")
            elif m.type == aiohttp.WSMsgType.BINARY:
                data = m.data
                if len(data) == 8 and data[0] == 0x03:
                    pending["ident"] = data[1]; continue
                ident, pending["ident"] = pending["ident"], None
                n_bin += 1
                if ident == 3:      # Text-States: nur die dieser Zone bzw. mit roomfav zeigen
                    off = 0
                    while off + 36 <= len(data):
                        suid = format_uuid(data[off:off + 16])
                        tlen = struct.unpack("<I", data[off + 32:off + 36])[0]
                        text = data[off + 36:off + 36 + tlen].decode("utf-8", "replace")
                        off += (36 + tlen + 3) & ~3
                        if suid in state_name or "roomfav" in text or "getroomfavs" in text:
                            print(f"  [{label}] TEXT-STATE {suid} [{state_name.get(suid, '?')}] = {cut(text, 300)}")
                elif ident not in (2, 3):
                    print(f"  [{label}] BINARY ident={ident} {len(data)} Bytes")
            else:
                print(f"  [{label}] WS {m.type.name}"); break
        print(f"  [{label}] Frames: {n_bin} binaer, {n_txt} text")

    try:
        await drain(3, "Voll-Dump")
        for cmd in (f"jdev/sps/io/{ua}/roomfav/get/0/50", f"jdev/sps/io/{ua}/roomfav/get",
                    f"jdev/sps/io/{ua}/roomfavs", f"jdev/sps/io/{ua}/getroomfavs/0/50"):
            print(f"\n--- sende {cmd}")
            await raw.send_str(cmd)
            await drain(4, "Antwort")
    finally:
        await ws.close()


APPJS_KEYWORDS = ("secure/hello", "secure/authenticate", "secure/init", "audio/cfg/getkey",
                  "keyexchange", "getroomfavs", "Session-Token")
APPJS_BROAD = ("audioserver", "AudioServer", "mediaServer", "7091", "LWSS", "remotecontrol", "audio_event")


async def appjs_probe():
    """Teil 9: Den Quellcode der Loxone-Weboberflaeche vom Miniserver holen und
    darin den Anmeldeablauf zum Audioserver suchen. Die Web-App ist dieselbe
    wie die Loxone-App; ihr JavaScript enthaelt die exakte Befehlsfolge
    (secure/hello, secure/authenticate, secure/init, getkey ...). Die App
    laedt ihre Module dynamisch nach, deshalb werden alle .js-Verweise aus der
    Startseite und aus jedem geladenen Skript rekursiv verfolgt. Zeigt je
    Stichwort die Fundstellen mit Umgebung. Es wird nichts veraendert."""
    import base64
    import re
    from urllib.parse import urljoin, urlparse
    print("\n===== Teil 9: Anmeldeablauf im Quellcode der Loxone-Weboberflaeche")
    ms = miniserver_config()
    if not ms.get("host"):
        print("  kein Miniserver-Zugang gefunden"); return
    host = ms["host"]; port = int(ms.get("port", 443))
    scheme = "http" if port == 80 else "https"
    base = f"{scheme}://{host}:{port}/"
    cred = base64.b64encode(f"{ms.get('user', '')}:{ms.get('pass', '')}".encode()).decode()
    auth_hdr = {"Authorization": "Basic " + cred}
    ref_re = re.compile(r'["\'\(]([^"\'\(\)\s]+?\.(?:m?js))(?:\?[^"\'\)\s]*)?["\'\)]')
    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False)) as s:
        async def get(url):
            for hdr in ({}, auth_hdr):
                async with s.get(url, headers=hdr, timeout=aiohttp.ClientTimeout(total=40)) as r:
                    if r.status in (401, 403) and not hdr:
                        continue
                    return r.status, str(r.url), await r.text(errors="replace")
            return 0, url, ""
        status, final, html = await get(base)
        print(f"  Startseite {base} -> {status} ({final}), {len(html)} Zeichen")
        if status != 200:
            print("  Startseite nicht lesbar, Abbruch"); return
        origin = "{u.scheme}://{u.netloc}".format(u=urlparse(final))
        queue = []
        seen = set()
        def collect(text, from_url):
            found = set(re.findall(r'<script[^>]+src=["\']([^"\']+)["\']', text, re.I))
            found |= set(m for m in ref_re.findall(text))
            out = []
            for ref in found:
                if ref.startswith(("data:", "blob:", "//")) or "://" in ref and not ref.startswith(origin):
                    continue
                url = urljoin(from_url, ref)
                if url.startswith(origin) and url not in seen:
                    seen.add(url); out.append(url)
            return out
        queue.extend(collect(html, final))
        print(f"  {len(queue)} Skript-Verweise in der Startseite: " +
              ", ".join(u.replace(origin, "") for u in queue[:15]) + (" …" if len(queue) > 15 else ""))
        # Inline-Skripte der Startseite ebenfalls durchsuchen
        docs = [("(Startseite inline)", html)]
        fetched = 0
        while queue and fetched < 80:
            url = queue.pop(0)
            try:
                st_, _, js = await get(url)
            except Exception as err:
                print(f"  {url.replace(origin, '')}: Fehler {cut(err, 120)}"); continue
            if st_ != 200 or not js:
                print(f"  {url.replace(origin, '')}: HTTP {st_}"); continue
            fetched += 1
            docs.append((url.replace(origin, ""), js))
            more = collect(js, url)
            if more:
                queue.extend(more)
        print(f"  {fetched} Skripte geladen, {len(queue)} nicht mehr verfolgt")
        found_any = False
        for name, text in docs:
            hits = {k: [m.start() for m in re.finditer(re.escape(k), text)] for k in APPJS_KEYWORDS}
            broad = {k: len(re.findall(re.escape(k), text)) for k in APPJS_BROAD}
            total = sum(len(v) for v in hits.values())
            btotal = sum(broad.values())
            if not total and not btotal:
                continue
            print(f"\n--- {name}: {len(text)} Zeichen, {total} Anmelde-Treffer, breit: " +
                  ", ".join(f"{k}={n}" for k, n in broad.items() if n))
            for k, pos in hits.items():
                for pnum, pstart in enumerate(pos[:2]):
                    found_any = True
                    a = max(0, pstart - 300); b = min(len(text), pstart + 1000)
                    print(f"  >>> '{k}' Treffer {pnum + 1}/{len(pos)} bei {pstart}:")
                    print("      " + text[a:b].replace("\n", " "))
            if not total:
                # nur breite Treffer: eine Fundstelle zur Orientierung zeigen
                for k in APPJS_BROAD:
                    m = re.search(re.escape(k), text)
                    if m:
                        a = max(0, m.start() - 150); b = min(len(text), m.start() + 350)
                        print(f"  ~ '{k}': " + text[a:b].replace("\n", " "))
                        break
        if not found_any:
            print("\n  Kein Anmelde-Stichwort gefunden. Liste aller geladenen Dateien:")
            for name, text in docs:
                print(f"    {name} ({len(text)} Zeichen)")


APPHUB_ANCHORS = (
    # (Suchbegriff, Zeichen davor, Zeichen danach, max. Treffer)
    ("rsaEnc", 1200, 1800, 3),
    ("sessionToken", 600, 1400, 4),
    ("getkey_result", 800, 1200, 2),
    ("pubkey", 600, 1200, 2),
    ("remotecontrol", 1500, 1500, 2),
    ("authenticate_result", 300, 300, 1),
    ("class AudioServerManager", 200, 2500, 1),
    ("hello", 400, 900, 3),
    ("secure/init", 600, 900, 2),
    ("LWSS", 300, 600, 2),
)


async def apphub_probe():
    """Teil 10: Gezielte Auswertung von /scripts/AppHub.js der Loxone-Weboberflaeche.
    Zeigt alle secure/*- und audio/cfg/*-Befehlsliterale und grosse Ausschnitte
    um die Stellen, die die Anmeldung am Audioserver bauen (RSA-Block, AES-
    Chiffre, Session-Token). Es wird nichts veraendert."""
    import base64
    import re
    print("\n===== Teil 10: Anmeldung am Audioserver im Code der Loxone-App (AppHub.js)")
    ms = miniserver_config()
    if not ms.get("host"):
        print("  kein Miniserver-Zugang gefunden"); return
    host = ms["host"]; port = int(ms.get("port", 443))
    scheme = "http" if port == 80 else "https"
    url = f"{scheme}://{host}:{port}/scripts/AppHub.js"
    cred = base64.b64encode(f"{ms.get('user', '')}:{ms.get('pass', '')}".encode()).decode()
    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False)) as s:
        js = ""
        for hdr in ({}, {"Authorization": "Basic " + cred}):
            async with s.get(url, headers=hdr, timeout=aiohttp.ClientTimeout(total=60)) as r:
                if r.status in (401, 403) and not hdr:
                    continue
                if r.status != 200:
                    print(f"  {url} -> HTTP {r.status}"); return
                js = await r.text(errors="replace")
                break
    print(f"  AppHub.js: {len(js)} Zeichen")
    lits = sorted(set(re.findall(r'secure/[A-Za-z/_%]+', js)))
    print("  secure/*-Literale:", ", ".join(lits) or "keine")
    cfg = sorted(set(re.findall(r'audio/cfg/[A-Za-z_]+', js)))
    print("  audio/cfg/*-Literale:", ", ".join(cfg) or "keine")
    for key, before, after, maxhits in APPHUB_ANCHORS:
        pos = [m.start() for m in re.finditer(re.escape(key), js)]
        if not pos:
            print(f"\n--- '{key}': keine Fundstelle"); continue
        print(f"\n--- '{key}': {len(pos)} Fundstellen, zeige {min(maxhits, len(pos))}")
        shown = []
        for pstart in pos:
            if any(abs(pstart - q) < before for q in shown):
                continue      # ueberlappende Fenster ueberspringen
            shown.append(pstart)
            if len(shown) > maxhits:
                break
            a = max(0, pstart - before); b = min(len(js), pstart + after)
            print(f"  [{pstart}] " + js[a:b].replace("\n", " "))
            print("")


async def zone_players() -> dict:
    """playerid -> Zonenname aller AudioZoneV2 aus der Miniserver-Struktur."""
    for d in (str(APP_DIR / "bin"), "/app/bin"):
        if d not in sys.path:
            sys.path.insert(0, d)
    from loxone_api import LoxoneClient
    ms = miniserver_config()
    port = int(ms.get("port", 443))
    c = LoxoneClient(host=ms["host"], user=ms.get("user", ""), password=ms.get("pass", ""),
                     port=port, verify_tls=bool(ms.get("verify_tls", False)))
    if port == 80:
        c.base_url = f"http://{ms['host']}:{port}/"
    async with c:
        await c.getkey2()
        await c.authenticate()
        st = await c.load_structure()
    out = {}
    for cc in (st.get("controls") or {}).values():
        if isinstance(cc, dict) and cc.get("type") == "AudioZoneV2":
            pid = (cc.get("details") or {}).get("playerid")
            if pid is not None:
                out[int(pid)] = cc.get("name", "")
    return out


async def auth_probe2(host, port):
    """Teil 11: Anmeldung wie die Loxone-App (bin/audioserver_auth.py) und danach
    getroomfavs fuer alle Zonen auf derselben Verbindung. Nichts wird veraendert."""
    global JWT
    print(f"\n===== Teil 11: Anmeldung am Audioserver wie die Loxone-App ({host}:{port})")
    for d in (str(APP_DIR / "bin"), "/app/bin"):
        if d not in sys.path:
            sys.path.insert(0, d)
    import audioserver_auth as aa
    if not aa.HAVE_CRYPTO:
        print("  Paket 'cryptography' fehlt im Container (aelteres Image). Image aktualisieren")
        print("  oder die Pakete aus requirements.txt nachinstallieren:")
        print("    docker exec LoxPanel pip install -q -r /app/requirements.txt")
        return
    ms = miniserver_config()
    user = ms.get("user", "")
    try:
        JWT = await fetch_jwt()
    except Exception as err:
        print(f"  Token vom Miniserver nicht bekommen: {cut(err)}"); return
    print(f"  Miniserver-Benutzer {user!r}, App-Token {len(JWT)} Zeichen")
    players = {}
    try:
        async with aiohttp.ClientSession() as s:
            async with s.ws_connect(f"ws://{host}:{port}/", timeout=8, protocols=("remotecontrol",)) as ws:
                greeting = None
                loop = asyncio.get_event_loop(); end = loop.time() + 4
                while greeting is None and loop.time() < end:
                    m = await asyncio.wait_for(ws.receive(), timeout=max(0.1, end - loop.time()))
                    if m.type != aiohttp.WSMsgType.TEXT:
                        print(f"  WS {m.type.name} vor dem Banner"); return
                    greeting = aa.parse_greeting(m.data)
                    if greeting is None:
                        try:
                            for e in json.loads(m.data).get("audio_event", []) or []:
                                players.setdefault(e.get("playerid"), (e.get("name") or "").strip())
                        except (ValueError, AttributeError):
                            pass
                if not greeting:
                    print("  kein Banner empfangen"); return
                print(f"  Banner: Firmware {greeting['firmware']}, API {greeting['api']}, Session-Token {len(greeting['token'])} Zeichen")
                await ws.send_str("audio/cfg/getkey")
                pubkey = None
                end = loop.time() + 5
                while pubkey is None and loop.time() < end:
                    m = await asyncio.wait_for(ws.receive(), timeout=max(0.1, end - loop.time()))
                    if m.type != aiohttp.WSMsgType.TEXT:
                        print(f"  WS {m.type.name} nach getkey"); return
                    try:
                        data = json.loads(m.data)
                    except ValueError:
                        continue
                    if "getkey_result" in data:
                        pubkey = aa.public_key_from_getkey(data)
                    else:
                        for e in data.get("audio_event", []) or []:
                            players.setdefault(e.get("playerid"), (e.get("name") or "").strip())
                if pubkey is None:
                    print("  kein brauchbares getkey_result"); return
                print(f"  RSA-Schluessel des Audioservers: {pubkey.key_size} Bit")
                cmd = aa.build_authenticate(user, JWT, greeting["token"], pubkey)
                print(f"  sende {cut(cmd, 90)}")
                await ws.send_str(cmd)
                result = None
                end = loop.time() + 6
                while result is None and loop.time() < end:
                    m = await asyncio.wait_for(ws.receive(), timeout=max(0.1, end - loop.time()))
                    if m.type != aiohttp.WSMsgType.TEXT:
                        print(f"  WS {m.type.name} nach secure/authenticate -> abgelehnt"); return
                    print(f"  WS <- {cut(m.data, 300)}")
                    try:
                        result = aa.auth_result(json.loads(m.data))
                    except ValueError:
                        pass
                print(f"  Anmeldung: {result!r}")
                if result != aa.AUTH_OK:
                    return
                try:
                    players.update({k: v for k, v in (await zone_players()).items() if k not in players})
                except Exception as err:
                    print(f"  Zonenliste aus der Struktur nicht lesbar: {cut(err, 120)}")
                if not players:
                    players = {PLAYER: "?"}
                for pid in sorted(k for k in players if k is not None):
                    cmd = f"audio/cfg/getroomfavs/{pid}/0/50"
                    await ws.send_str(cmd)
                    got = None; end = loop.time() + 5
                    while got is None and loop.time() < end:
                        m = await asyncio.wait_for(ws.receive(), timeout=max(0.1, end - loop.time()))
                        if m.type != aiohttp.WSMsgType.TEXT:
                            print(f"  WS {m.type.name} nach {cmd}"); return
                        if "getroomfavs_result" in m.data:
                            got = m.data
                    if got is None:
                        print(f"  Zone {pid} ({players[pid]}): keine Antwort auf getroomfavs"); continue
                    try:
                        grp = json.loads(got).get("getroomfavs_result", [])
                        items = (grp[0].get("items") if grp and isinstance(grp[0], dict) else []) or []
                        names = [it.get("name") or it.get("title") for it in items if isinstance(it, dict)]
                        print(f"  Zone {pid} ({players[pid]}): {len(items)} Favoriten: {cut(', '.join(str(n) for n in names), 300)}")
                        if items and pid == min(players):
                            print(f"    Felder des ersten Eintrags: {cut(json.dumps(items[0], ensure_ascii=False), 600)}")
                            print(f"    Rahmen: {cut(json.dumps({k: v for k, v in grp[0].items() if k != 'items'}, ensure_ascii=False), 300)}")
                    except (ValueError, AttributeError):
                        print(f"  Zone {pid}: {cut(got, 300)}")
                print(f"  Verbindung am Ende offen: {not ws.closed}")
    except Exception as err:
        print(f"  Fehler: {cut(err)}")


async def main():
    async with aiohttp.ClientSession() as s:
        async with s.get(f"{PANEL}/api/settings") as r:
            servers = (await r.json()).get("audiometa", {}).get("servers", [])
        volume = None
        try:
            async with s.get(f"{PANEL}/api/meta") as r:
                meta = await r.json()
            zones = [c for c in meta.get("controls", []) if c.get("type") == "AudioZoneV2"]
            print("AudioZoneV2-Zonen laut Struktur:",
                  ", ".join(f"{z.get('name')} ({z.get('roomName')})" for z in zones) or "keine")
        except Exception as err:
            print("Zonenliste nicht lesbar:", err)
    if ROOMFAV_ONLY:
        await roomfav_probe()
        return
    if ROOMFAVWS_ONLY:
        await roomfav_ws_probe()
        return
    if ZONEDUMP_ONLY:
        await zonedump_probe()
        return
    if APPJS_ONLY:
        await appjs_probe()
        return
    if APPHUB_ONLY:
        await apphub_probe()
        return
    if AUTH_ONLY:
        for hp in servers:
            host, _, port = hp.partition(":")
            await auth_probe2(host.strip(), int(port) if port.strip().isdigit() else 7091)
        return
    print("Audioserver laut Struktur:", ", ".join(servers) or "keine")
    for hp in servers:
        host, _, port = hp.partition(":")
        port = int(port) if port.strip().isdigit() else 7091
        if FAVS_ONLY:
            await favs_probe(host.strip(), port)
            continue
        await probe(host.strip(), port, volume)
        await event_probe(host.strip(), port)
        await path_probe(host.strip(), port)
        await auth_probe(host.strip(), port)
        await favs_probe(host.strip(), port)


if __name__ == "__main__":
    asyncio.run(main())
