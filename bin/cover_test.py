#!/usr/bin/env python3
"""Liest die volle cover-URL der Zone 'Zentral' und prueft, ob sie ein Bild liefert."""
import asyncio
import json
import sys
from pathlib import Path
from urllib.parse import unquote

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from loxone_api import LoxoneClient  # noqa: E402
from loxone_ws import LoxoneWS  # noqa: E402

ZONE = "1d763528-02ea-2bbd-ffffaba260ecd863"  # Zentral


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

    s = structure["controls"][ZONE]["states"]
    cover_uuid = s["cover"]
    song_uuid = s["songName"]

    ws = LoxoneWS(host=ms["host"], port=ms.get("port", 443), user=ms["user"], jwt=jwt,
                  hash_alg=alg, verify_tls=ms.get("verify_tls", False))
    await ws.connect()
    task = asyncio.ensure_future(ws.stream(lambda u, v: st.__setitem__(u, v)))
    await asyncio.sleep(3.0)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    await ws.close()

    cover = st.get(cover_uuid)
    print("songName   :", unquote(str(st.get(song_uuid))))
    print("cover (roh):", cover)
    if cover:
        try:
            r = requests.get(str(cover), timeout=8)
            ct = r.headers.get("Content-Type")
            print(f"HTTP {r.status_code}  {ct}  {len(r.content)} Bytes")
        except Exception as e:
            print("Cover-GET fehlgeschlagen:", e)


if __name__ == "__main__":
    asyncio.run(main())
