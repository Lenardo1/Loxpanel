#!/usr/bin/env python3
"""Zeigt die Favoriten mit on/tone/sublabel."""
import asyncio
import json

import aiohttp


async def main() -> None:
    async with aiohttp.ClientSession() as s, s.ws_connect("http://localhost:8099/ws") as ws:
        v = None
        while v is None:
            m = json.loads((await ws.receive()).data)
            if m.get("t") == "theme":
                print("theme vars:", m.get("vars"))
            elif m.get("t") == "view":
                v = m
        print("title:", v.get("title"))
        for it in v.get("items", []):
            print(f"  {it['label']:22} on={str(it.get('on')):5} "
                  f"tone={str(it.get('tone', '')):5} color={str(it.get('color', '')):8} "
                  f"sub={it.get('sublabel', '')!r}")


if __name__ == "__main__":
    asyncio.run(main())
