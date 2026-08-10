#!/usr/bin/env python3
"""Feindiagnose: haelt 'Stop' das Rollo, oder haelt erst erneutes 'Up'/'Down'?"""
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from loxone_api import LoxoneClient  # noqa: E402
from loxone_ws import LoxoneWS  # noqa: E402

CTRL = "14c86344-00a5-a436-ffffb84256f3c2d0"   # Pool Rollo Links
POS = "14c86344-00a6-a45e-ffffb84256f3c2d0"
UP = "14c86344-00a5-a42a-ffffb84256f3c2d0"
DOWN = "14c86344-00a5-a42e-ffffb84256f3c2d0"


def _conn():
    f = Path(__file__).resolve().parent.parent / "config" / "loxpanel.cfg"
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

    async def cmd(c):
        r = await client.jdev_get(f"sps/io/{CTRL}/{c}")
        print(f"\n>>> {c} (Code {r.get('LL',{}).get('Code')})")

    async def sample(n, tag):
        for _ in range(n):
            await asyncio.sleep(0.5)
            print(f"   {tag}: pos={st.get(POS):.4f} up={st.get(UP)} down={st.get(DOWN)}")

    try:
        await asyncio.sleep(2.5)
        print(f"START pos={st.get(POS)}")
        await cmd("Down"); await sample(6, "faehrt")      # in Bewegung bringen
        await cmd("Stop"); await sample(6, "nach Stop")    # haelt Stop?
        # Falls Stop nicht haelt: erneutes Down (Toggle) testen
        await cmd("Down"); await sample(4, "Down2")
        await cmd("Down"); await sample(6, "nach Down3")   # erneutes Down = Stop?
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
