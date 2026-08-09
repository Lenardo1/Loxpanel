#!/usr/bin/env python3
"""Phase-2b-Test: WebSocket-Live-Stream gegen den echten Miniserver.

Authentifiziert per loxone-api (JWT), oeffnet den WS, schaltet Status-Updates
ein und sammelt fuer einige Sekunden alle State-Updates. Gibt danach die Werte
der gesuchten UUIDs aus (Standard: activeMoods/moodList des Terrassenlichts).

Aufruf:
  python ws_test.py                 # nutzt config/loxhasp.cfg
  python ws_test.py --seconds 6 --uuid 13fd4279-02df-a776-ffff4a950f3ecb07
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from loxone_api import LoxoneClient  # noqa: E402
from loxone_ws import LoxoneWS  # noqa: E402

log = logging.getLogger("loxhasp.wstest")

TARGET_DEFAULTS = [
    "13fd4279-02df-a776-ffff4a950f3ecb07",  # activeMoods Terrasse
    "13fd4279-02df-a777-ffff4a950f3ecb07",  # moodList Terrasse
]


def _conn() -> dict:
    base = Path(__file__).resolve().parent.parent / "config"
    f = base / "loxhasp.cfg"
    if not f.is_file():
        f = base / "loxhasp.cfg.example"
    ms = json.loads(f.read_text(encoding="utf-8")).get("miniserver", {})
    return ms


async def run(args: argparse.Namespace) -> int:
    ms = _conn()
    host, port = ms["host"], ms.get("port", 443)
    user, password = ms["user"], ms["pass"]
    verify = ms.get("verify_tls", False)

    # 1) JWT + Hash-Algorithmus via loxone-api
    async with LoxoneClient(host=host, user=user, password=password,
                            port=port, verify_tls=verify) as client:
        alg = (await client.getkey2()).hashAlg
        jwt = await client.authenticate()
    log.info("JWT erhalten (hashAlg=%s)", alg)

    # 2) WebSocket-Stream
    ws = LoxoneWS(host=host, port=port, user=user, jwt=jwt, hash_alg=alg, verify_tls=verify)
    await ws.connect()

    latest: dict[str, object] = {}
    count = 0

    def on_value(uuid: str, value: object) -> None:
        nonlocal count
        count += 1
        latest[uuid] = value

    task = asyncio.ensure_future(ws.stream(on_value))
    await asyncio.sleep(args.seconds)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    await ws.close()

    targets = [args.uuid] if args.uuid else TARGET_DEFAULTS
    print(f"\n{count} State-Updates in {args.seconds}s empfangen. Gesuchte UUIDs:")
    for u in targets:
        print(f"  {u} = {latest.get(u, '<nicht gesehen>')!r}")
    return 0


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    p = argparse.ArgumentParser()
    p.add_argument("--seconds", type=float, default=6.0)
    p.add_argument("--uuid")
    sys.exit(asyncio.run(run(p.parse_args())))


if __name__ == "__main__":
    main()
