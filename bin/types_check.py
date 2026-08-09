#!/usr/bin/env python3
"""Prueft Gate/Heizung-Detail (Blocks) und Licht-Szenen-Layout."""
import asyncio
import json

import aiohttp

BASE = "http://localhost:8099"
GATE = "1021c17e-0160-3b22-ffffaba260ecd863"     # Gartentor
ROOM = "12a7e0c0-0221-97f9-ffffaba260ecd863"     # IRR Poolhaus
LIGHT = "13fd4279-02df-a7be-ffffdabd9fbb674e"    # Aussenlicht Terrasse


async def main() -> None:
    async with aiohttp.ClientSession() as s, s.ws_connect(BASE + "/ws") as ws:
        async def recv():
            return json.loads((await ws.receive()).data)

        async def nav(r):
            await ws.send_json({"t": "nav", "route": r})
            return await recv()

        m = await recv()
        if m.get("t") == "theme":
            print("theme vars:", m.get("vars"))
            print("tabs:", m.get("tabs"))
        await recv()  # initial view

        for name, uid in (("GATE", GATE), ("HEIZUNG", ROOM)):
            v = await nav({"view": "control", "id": uid})
            print(f"\n== {name}: {v.get('title')} ==")
            for b in v.get("blocks", []):
                if b["k"] == "row":
                    print("  row:", [c.get("label") + "→" + c.get("cmd", {}).get("cmd", "")
                                     for c in b["cells"]])
                else:
                    print("  ", b["k"], "->", b.get("text", b.get("icon")))

        v = await nav({"view": "control", "id": LIGHT})
        print(f"\n== LICHT: {v.get('title')} | layout={v.get('layout')} | "
              f"{len(v.get('items', []))} Szenen ==")


if __name__ == "__main__":
    asyncio.run(main())
