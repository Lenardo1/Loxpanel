#!/usr/bin/env python3
"""End-to-End-Referenztest der Audio-Steuerung: verbindet sich als Panel mit dem
lokalen webvisu (localhost:8099), sendet Favoriten- und Steuerbefehle wie das
Frontend und prüft via LMS-CLI, ob der Server sie korrekt an den Audioserver
weiterreicht. Zone Poolhaus; Lautstärke nicht-invasiv, Wiedergabe wiederhergestellt."""
import asyncio
import json
import socket
import threading
import time
import urllib.request
from urllib.parse import unquote

import aiohttp

POOL_UA = "1d763546-0078-1706-ffffaba260ecd863"
MAC = "aa:aa:f0:9f:ef:98"
WS = "http://localhost:8099/ws"
events = []


def cli_listen(stop):
    s = socket.socket(); s.settimeout(1.5)
    s.connect(("10.0.2.2", 9090)); s.sendall(b"listen 1\n")
    buf = b""
    while not stop.is_set():
        try:
            chunk = s.recv(4096)
        except socket.timeout:
            continue
        if not chunk:
            break
        buf += chunk
        while b"\n" in buf:
            line, buf = buf.split(b"\n", 1)
            txt = unquote(line.decode("utf-8", "replace")).strip()
            if MAC in txt and any(k in txt for k in
                                  ("playlist play", "pause", "mixer", "index")):
                events.append((time.strftime("%H:%M:%S"), txt))
    s.close()


def lms_vol():
    req = urllib.request.Request("http://10.0.2.2:9000/jsonrpc.js",
        data=json.dumps({"id": 1, "method": "slim.request",
                         "params": [MAC, ["mixer", "volume", "?"]]}).encode(),
        headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=6).read())["result"].get("_volume")


async def main():
    cur_vol = lms_vol()
    stop = threading.Event()
    threading.Thread(target=cli_listen, args=(stop,), daemon=True).start()
    await asyncio.sleep(1.0)

    async with aiohttp.ClientSession() as s:
        async with s.ws_connect(WS) as ws:
            await ws.send_json({"t": "nav", "route": {"view": "sources", "id": POOL_UA}})
            await asyncio.sleep(2.0)

            async def cmd(c, label):
                n0 = len(events)
                await ws.send_json({"t": "cmd", "uuid": POOL_UA, "cmd": c})
                await asyncio.sleep(3.5)
                new = events[n0:]
                tag = "  >>> OK" if new else "  !!! keine Reaktion"
                print(f"[{label:22} cmd={c!r}]{tag}")
                for ts, t in new[:3]:
                    print(f"      {ts} {t.split(MAC)[-1].strip()[:70]}")

            await cmd("roomfav/play/2", "Favorit kronehit")
            await cmd("pause", "Pause")
            await cmd("play", "Play")
            await cmd(f"volume/{cur_vol}", "Lautstaerke")
            await cmd("queueplus", "Naechster")
            await cmd("queueminus", "Voriger")
            print("--- zuruecksetzen auf OE3 ---")
            await cmd("roomfav/play/1", "Favorit OE3")

    stop.set()
    print(f"\nGesamt beobachtete Events: {len(events)}")


if __name__ == "__main__":
    asyncio.run(main())
