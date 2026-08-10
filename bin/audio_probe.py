#!/usr/bin/env python3
"""Read-only-Probe: zeigt AudioZone-Controls und ihre Live-Werte."""
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from loxone_api import LoxoneClient  # noqa: E402
from loxone_ws import LoxoneWS  # noqa: E402

FIELDS = ["playState", "power", "volume", "mute", "songName", "artist", "album",
          "station", "cover", "duration", "progress", "source", "queueIndex"]


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
    structure = await client.load_structure()
    await client.close()

    zones = [(u, c) for u, c in structure["controls"].items()
             if c.get("type") in ("AudioZone", "CentralAudioZone")]
    print(f"{len(zones)} Audio-Zonen\n")

    ws = LoxoneWS(host=ms["host"], port=ms.get("port", 443), user=ms["user"], jwt=jwt,
                  hash_alg=alg, verify_tls=ms.get("verify_tls", False))
    await ws.connect()
    task = asyncio.ensure_future(ws.stream(lambda u, v: st.__setitem__(u, v)))
    await asyncio.sleep(3.5)

    for u, c in zones:
        s = c.get("states") or {}
        print(f"# {c.get('name')}  [{c.get('type')}]  uuidAction={c.get('uuidAction')}")
        for f in FIELDS:
            su = s.get(f)
            if su is None:
                continue
            v = st.get(su)
            if isinstance(v, str) and len(v) > 90:
                v = v[:90] + "…"
            print(f"    {f:12} = {v!r}")
        # unbekannte States mit auflisten
        extra = [k for k in s if k not in FIELDS and k not in ("jLocked",)]
        print(f"    (weitere States: {extra})")
        print()

    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    await ws.close()


if __name__ == "__main__":
    asyncio.run(main())
