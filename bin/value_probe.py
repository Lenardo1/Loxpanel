#!/usr/bin/env python3
"""Liest Live-Werte + Formatstrings der Wert-Kacheln (Favoriten)."""
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from loxone_api import LoxoneClient  # noqa: E402
from loxone_ws import LoxoneWS  # noqa: E402

TYPES = {"Meter", "Slider", "InfoOnlyAnalog", "InfoOnlyText", "TextState",
         "InfoOnlyDigital"}


def _conn():
    f = Path(__file__).resolve().parent.parent / "config" / "loxhasp.cfg"
    return json.loads(f.read_text(encoding="utf-8"))["miniserver"]


async def main():
    ms = _conn()
    st = {}
    client = LoxoneClient(host=ms["host"], user=ms["user"], password=ms["pass"],
                          port=ms.get("port", 443), verify_tls=ms.get("verify_tls", False))
    await client.__aenter__()
    alg = (await client.getkey2()).hashAlg
    jwt = await client.authenticate()
    structure = await client.load_structure()
    await client.close()

    ws = LoxoneWS(host=ms["host"], port=ms.get("port", 443), user=ms["user"], jwt=jwt,
                  hash_alg=alg, verify_tls=ms.get("verify_tls", False))
    await ws.connect()
    task = asyncio.ensure_future(ws.stream(lambda u, v: st.__setitem__(u, v)))
    await asyncio.sleep(3.5)

    for u, c in structure["controls"].items():
        if not (c.get("isFavorite") and c.get("type") in TYPES):
            continue
        s = c.get("states") or {}
        det = c.get("details") or {}
        print(f"# {c.get('name')!r} [{c.get('type')}]")
        print(f"  details: {json.dumps(det, ensure_ascii=False)[:160]}")
        for sn, su in s.items():
            v = st.get(su)
            if isinstance(v, str) and len(v) > 70:
                v = v[:70] + "…"
            print(f"    {sn} = {v!r}")
        print()

    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    await ws.close()


if __name__ == "__main__":
    asyncio.run(main())
