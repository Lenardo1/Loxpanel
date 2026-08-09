#!/usr/bin/env python3
"""Diagnose: bewegt 'Pool Rollo Links' kurz und prueft, ob Up bewegt und Stop haelt."""
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from loxone_api import LoxoneClient  # noqa: E402
from loxone_ws import LoxoneWS  # noqa: E402

CTRL = "14c86344-00a5-a436-ffffb84256f3c2d0"
S = {
    "up": "14c86344-00a5-a42a-ffffb84256f3c2d0",
    "down": "14c86344-00a5-a42e-ffffb84256f3c2d0",
    "position": "14c86344-00a6-a45e-ffffb84256f3c2d0",
    "safetyActive": "14c86344-00a6-a461-ffffb84256f3c2d0",
    "autoActive": "14c86344-00a6-a460-ffffb84256f3c2d0",
    "locked": "14c86344-00a6-a462-ffffb84256f3c2d0",
}


def _conn():
    base = Path(__file__).resolve().parent.parent / "config"
    f = base / "loxhasp.cfg"
    return json.loads(f.read_text(encoding="utf-8"))["miniserver"]


async def main():
    ms = _conn()
    st = {}
    client = LoxoneClient(host=ms["host"], user=ms["user"], password=ms["pass"],
                          port=ms.get("port", 443), verify_tls=ms.get("verify_tls", False))
    await client.__aenter__()
    alg = (await client.getkey2()).hashAlg
    jwt = await client.authenticate()
    ws = LoxoneWS(host=ms["host"], port=ms.get("port", 443), user=ms["user"], jwt=jwt,
                  hash_alg=alg, verify_tls=ms.get("verify_tls", False))
    await ws.connect()
    task = asyncio.ensure_future(ws.stream(lambda u, v: st.__setitem__(u, v)))

    def snap(tag):
        vals = {k: st.get(u) for k, u in S.items()}
        print(f"{tag:14} up={vals['up']} down={vals['down']} pos={vals['position']} "
              f"auto={vals['autoActive']} safety={vals['safetyActive']} locked={vals['locked']}")

    async def cmd(c):
        r = await client.jdev_get(f"sps/io/{CTRL}/{c}")
        print(f"  -> {c}: {r.get('LL',{}).get('Code')}")

    try:
        await asyncio.sleep(2.5)
        snap("BASELINE")
        await cmd("Up"); await asyncio.sleep(2.5); snap("nach Up")
        await cmd("Stop"); await asyncio.sleep(2.5); snap("nach Stop")
        # Vergleich: FullDown, dann Stop
        await cmd("FullDown"); await asyncio.sleep(2.0); snap("nach FullDown")
        await cmd("Stop"); await asyncio.sleep(2.5); snap("nach Stop2")
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        await ws.close()
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
