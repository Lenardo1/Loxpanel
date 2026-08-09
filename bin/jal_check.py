#!/usr/bin/env python3
"""Prueft die Jalousie-Detailansicht (Blocks) ueber den WebSocket."""
import asyncio
import json

import aiohttp

URL = "http://localhost:8099/ws"


async def main() -> None:
    async with aiohttp.ClientSession() as s, s.ws_connect(URL) as ws:
        async def recv():
            return json.loads((await ws.receive()).data)

        async def nav(r):
            await ws.send_json({"t": "nav", "route": r})
            return await recv()

        await recv()
        v = await nav({"view": "tab", "tab": "raeume"})
        room = next((i for i in v["items"] if "Terrasse" in (i.get("label") or "")), None)
        print("Raum:", room and room["label"])
        v = await nav(room["nav"])
        jal = next((i for i in v["items"] if i.get("icon") == "blind"), None)
        print("Jalousie:", jal and jal["label"])
        v = await nav(jal["nav"])
        print("Detail-Keys:", list(v.keys()), "| title:", v.get("title"))
        for b in v.get("blocks", []):
            if b["k"] == "row":
                print("  row:", [c["label"] + ("(hold)" if c.get("hold") else "") for c in b["cells"]])
            else:
                print("  ", b["k"], "->", b.get("text", b.get("icon", "")))


if __name__ == "__main__":
    asyncio.run(main())
