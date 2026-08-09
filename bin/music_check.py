#!/usr/bin/env python3
"""Prueft die Player-Ansicht (Blocks) + Cover-Proxy ueber localhost."""
import asyncio
import json

import aiohttp

BASE = "http://localhost:8099"


async def main() -> None:
    async with aiohttp.ClientSession() as s:
        async with s.ws_connect(BASE + "/ws") as ws:
            async def recv():
                return json.loads((await ws.receive()).data)

            async def nav(r):
                await ws.send_json({"t": "nav", "route": r})
                return await recv()

            await recv()
            v = await nav({"view": "tab", "tab": "kategorien"})
            audio = next((i for i in v["items"] if "Audio" in (i.get("label") or "")), None)
            print("Audio-Kategorie:", audio and audio["label"])
            v = await nav(audio["nav"])
            zone = next((i for i in v["items"] if i.get("icon") == "music"), None)
            print("Zone:", zone and zone["label"], "| sub:", zone and zone.get("sublabel"))
            v = await nav(zone["nav"])
            print("Detail-Keys:", list(v.keys()), "| title:", v.get("title"))
            cover_src = None
            for b in v.get("blocks", []):
                if b["k"] == "row":
                    print("  row:", [c.get("icon") or c.get("label") for c in b["cells"]])
                elif b["k"] == "cover":
                    cover_src = b["src"]
                    print("  cover:", b["src"][:70], "…")
                elif b["k"] == "slider":
                    print("  slider: value", b["value"])
                else:
                    print("  ", b["k"], "->", b.get("text"), "/", b.get("sub"))

        if cover_src:
            async with s.get(BASE + cover_src) as r:
                print(f"\nCover-Proxy: HTTP {r.status} {r.headers.get('Content-Type')} "
                      f"{len(await r.read())} Bytes")


if __name__ == "__main__":
    asyncio.run(main())
