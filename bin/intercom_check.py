#!/usr/bin/env python3
"""Prueft die Intercom-Detailansicht (Tuerstation Camera Phone)."""
import asyncio
import json

import aiohttp

BASE = "http://localhost:8099"
DOOR = "9a8b4d56-cf47-11e1-a39daba260ecd863"  # Camera Phone (Tuerstation)


async def main() -> None:
    async with aiohttp.ClientSession() as s, s.ws_connect(BASE + "/ws") as ws:
        async def recv():
            return json.loads((await ws.receive()).data)

        async def nav(r):
            await ws.send_json({"t": "nav", "route": r})
            return await recv()

        await recv()  # theme
        await recv()  # initial view
        v = await nav({"view": "control", "id": DOOR})
        print("Titel:", v.get("title"))
        for b in v.get("blocks", []):
            if b["k"] == "row":
                print("  row:", [f"{c.get('label')}→{c.get('cmd', {}).get('uuid')}/{c.get('cmd', {}).get('cmd')}"
                                 for c in b["cells"]])
            else:
                print("  ", b["k"], "->", b.get("text", b.get("src")))


if __name__ == "__main__":
    asyncio.run(main())
