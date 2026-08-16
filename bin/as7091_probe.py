#!/usr/bin/env python3
"""Read-only: versucht, MS4H auf Port 7091 im Loxone-Music-Server-Protokoll (WS)
anzusprechen und die Player-/Config-Liste (playerid<->MAC) abzufragen. Sendet nur
lesende audio/cfg-Kommandos."""
import asyncio
import aiohttp

HOST = "10.0.2.2"


async def try_cmds(url):
    async with aiohttp.ClientSession() as s:
        try:
            async with s.ws_connect(url, timeout=6, heartbeat=None) as ws:
                print(f"WS verbunden: {url}")
                for cmd in ["audio/cfg/getplayersdetails", "audio/cfg/getplayers",
                            "audio/cfg/getconfig", "audio/cfg/getmediafolder",
                            "audio/cfg/getservices", "secure/hello"]:
                    await ws.send_str(cmd)
                    try:
                        msg = await asyncio.wait_for(ws.receive(), timeout=3)
                        data = msg.data
                        if isinstance(data, (bytes, bytearray)):
                            data = data.decode("utf-8", "replace")
                        print(f"  >> {cmd}\n     {str(data)[:300]}")
                    except asyncio.TimeoutError:
                        print(f"  >> {cmd}  (keine Antwort)")
                return True
        except Exception as e:
            print(f"WS {url} fehlgeschlagen: {type(e).__name__}: {e}")
            return False


async def main():
    for url in [f"ws://{HOST}:7091/", f"ws://{HOST}:7091/ws",
                f"ws://{HOST}:7090/", f"ws://{HOST}:7091/audio"]:
        if await try_cmds(url):
            break


if __name__ == "__main__":
    asyncio.run(main())
