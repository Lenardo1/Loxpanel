#!/usr/bin/env python3
"""Prueft, ob der Miniserver die Loxone-Icon-Dateien ausliefert."""
import asyncio
import json
import ssl
import sys
from pathlib import Path

import aiohttp

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
    host, port = ms["host"], ms.get("port", 443)
    async with LoxoneClient(host=host, user=ms["user"], password=ms["pass"],
                            port=port, verify_tls=ms.get("verify_tls", False)) as c:
        jwt = await c.authenticate()

    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    candidates = [
        "IconsFilled/sun.svg",
        "/IconsFilled/sun.svg",
        "IconsFilled/flame-2.svg",
        "101f3ece-0005-7ffa-ffffaba260ecd863.png",
        "data/IconsFilled/sun.svg",
    ]
    base = f"https://{host}:{port}/"
    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=ctx)) as s:
        for path in candidates:
            for auth in (True, False):
                url = base + path.lstrip("/")
                headers = {"Authorization": f"Bearer {jwt}"} if auth else {}
                try:
                    async with s.get(url, headers=headers) as r:
                        body = await r.read()
                        head = body[:60].decode("utf-8", "replace").replace("\n", " ")
                        print(f"[{'auth' if auth else 'anon'}] {r.status} {r.headers.get('Content-Type','?'):24} {len(body):6}B  {path}  | {head}")
                except Exception as err:
                    print(f"[{'auth' if auth else 'anon'}] ERR {path}: {err}")


if __name__ == "__main__":
    asyncio.run(main())
