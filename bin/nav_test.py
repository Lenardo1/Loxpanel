#!/usr/bin/env python3
"""Treibt die Web-Visu-Navigation ueber den WebSocket durch (Servertest)."""
import asyncio
import json

import aiohttp

URL = "http://localhost:8099/ws"


def summarize(v: dict) -> str:
    items = v.get("items", [])
    head = f"[{v.get('title')}] sub={v.get('subtitle','')} ({len(items)} Items)"
    lines = [head]
    for it in items[:12]:
        mark = "●" if it.get("on") else "·"
        arrow = "→" if it.get("nav") else ("⚡" if it.get("cmd") else " ")
        img = "[i]" if it.get("iconUrl") else "   "
        lines.append(f"   {mark} {arrow} {img} {it.get('label')}  {it.get('sublabel','')}")
    return "\n".join(lines)


async def main() -> None:
    async with aiohttp.ClientSession() as s:
        async with s.ws_connect(URL) as ws:
            async def recv():
                return json.loads((await ws.receive()).data)

            async def nav(route):
                await ws.send_json({"t": "nav", "route": route})
                return await recv()

            print("== INITIAL =="); print(summarize(await recv()))

            v = await nav({"view": "tab", "tab": "kategorien"})
            print("\n== KATEGORIEN =="); print(summarize(v))

            bel = next((i for i in v["items"] if "Beleucht" in (i.get("label") or "")), None)
            if not bel:
                print("Keine Beleuchtungs-Kategorie gefunden"); return
            v = await nav(bel["nav"])
            print("\n== GRUPPE Beleuchtung =="); print(summarize(v))

            light = next((i for i in v["items"] if i.get("nav", {}).get("view") == "control"), None)
            if not light:
                print("Kein LightControllerV2 in der Gruppe"); return
            v = await nav(light["nav"])
            print(f"\n== LICHT-DETAIL ({light['label']}) =="); print(summarize(v))


if __name__ == "__main__":
    asyncio.run(main())
