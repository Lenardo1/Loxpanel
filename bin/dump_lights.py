#!/usr/bin/env python3
"""Struktur-Dump der Licht-Controls, um Zentralbaustein <-> Raeume zu verstehen.

Gibt fuer alle licht-relevanten Controls Typ, Raum, details und states aus und
speichert die Roh-Struktur nach data/structure_full.json.
"""
from __future__ import annotations

import asyncio
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from loxone_api import LoxoneClient  # noqa: E402


def _conn() -> dict:
    base = Path(__file__).resolve().parent.parent / "config"
    f = base / "loxhasp.cfg"
    if not f.is_file():
        f = base / "loxhasp.cfg.example"
    return json.loads(f.read_text(encoding="utf-8")).get("miniserver", {})


async def main() -> None:
    ms = _conn()
    async with LoxoneClient(host=ms["host"], user=ms["user"], password=ms["pass"],
                            port=ms.get("port", 443), verify_tls=ms.get("verify_tls", False)) as c:
        await c.authenticate()
        st = await c.load_structure()

    out = Path(__file__).resolve().parent.parent / "data" / "structure_full.json"
    out.write_text(json.dumps(st, ensure_ascii=False, indent=2), encoding="utf-8")

    controls = st.get("controls", {})
    rooms = {u: v.get("name") for u, v in st.get("rooms", {}).items()}

    print("=== Alle Control-Typen (Anzahl) ===")
    for t, n in Counter(c.get("type") for c in controls.values()).most_common():
        print(f"  {n:3}  {t}")

    def is_lightish(c: dict) -> bool:
        t = (c.get("type") or "")
        name = (c.get("name") or "").lower()
        return "Light" in t or "licht" in name or "zentral" in name

    print("\n=== Licht-relevante Controls ===")
    for uuid, c in controls.items():
        if not is_lightish(c):
            continue
        print(f"\n# {c.get('name')}  [{c.get('type')}]")
        print(f"  uuidAction : {c.get('uuidAction', uuid)}")
        print(f"  room/cat   : {rooms.get(c.get('room'))} / {c.get('cat')}")
        print(f"  states     : {list((c.get('states') or {}).keys())}")
        details = c.get("details") or {}
        # details evtl. gross -> nur Schluessel + kompakte Werte
        keys = list(details.keys())
        print(f"  detail-keys: {keys}")
        for k in keys:
            v = details[k]
            s = json.dumps(v, ensure_ascii=False)
            if len(s) > 400:
                s = s[:400] + " …"
            print(f"      {k}: {s}")
        if "subControls" in c:
            print(f"  subControls: {list(c['subControls'].keys())}")

    print(f"\nVolle Struktur gespeichert: {out}")


if __name__ == "__main__":
    asyncio.run(main())
