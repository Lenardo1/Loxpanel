#!/usr/bin/env python3
"""Prueft die Zentral-Audio-Liste (Toggle-Kacheln)."""
import asyncio
import json

import aiohttp

BASE = "http://localhost:8099"
CENTRAL = "15ebe34b-0289-ae6b-ffffaba260ecd863"  # Audio Zentral


async def main() -> None:
    async with aiohttp.ClientSession() as s, s.ws_connect(BASE + "/ws") as ws:
        async def recv():
            return json.loads((await ws.receive()).data)

        async def nav(r):
            await ws.send_json({"t": "nav", "route": r})
            return await recv()

        await recv()
        v = await nav({"view": "group", "kind": "central", "id": CENTRAL})
        print("title:", v.get("title"), "| layout:", v.get("layout"),
              "| items:", len(v.get("items", [])))
        for it in v.get("items", [])[:8]:
            ctrls = [c.get("icon") for c in (it.get("controls") or [])]
            print(f"  {it['label']:14} controls={ctrls} "
                  f"nav={'ja' if it.get('nav') else 'nein'} sub={it.get('sublabel')!r}")


if __name__ == "__main__":
    asyncio.run(main())
