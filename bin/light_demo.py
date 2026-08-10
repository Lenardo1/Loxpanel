#!/usr/bin/env python3
"""Phase-2-Abschluss: ein Licht komplett end-to-end ueber den Adapter.

  1) verbindet (HTTP fuer Befehle + WebSocket fuer Live-States)
  2) rendert den aktuellen Kachel-Zustand des Lichts (AN/AUS + Mood-Name)
  3) schaltet AN, zeigt den Live-Zustandswechsel
  4) schaltet wieder AUS (Ausgangszustand wiederhergestellt)

Aufruf:
  python light_demo.py                 # Terrassenlicht (Default)
  python light_demo.py --uuid <control-uuid>
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
from adapters import get_adapter  # noqa: E402

log = logging.getLogger("loxpanel.lightdemo")
DEFAULT_LIGHT = "13fd4279-02df-a7be-ffffdabd9fbb674e"  # Aussenlicht Terrasse


def _conn() -> dict:
    base = Path(__file__).resolve().parent.parent / "config"
    f = base / "loxpanel.cfg"
    if not f.is_file():
        f = base / "loxpanel.cfg.example"
    return json.loads(f.read_text(encoding="utf-8")).get("miniserver", {})


def show(tag: str, adapter, control, states) -> None:
    r = adapter.render(control, states)
    symbol = "●" if r["on"] else "○"
    print(f"  {tag:12} {symbol} {'AN' if r['on'] else 'AUS'}  ({r['label']})  activeMoods={r['activeMoods']}")


async def run(args: argparse.Namespace) -> int:
    ms = _conn()
    host, port = ms["host"], ms.get("port", 443)
    user, password, verify = ms["user"], ms["pass"], ms.get("verify_tls", False)

    client = LoxoneClient(host=host, user=user, password=password, port=port, verify_tls=verify)
    await client.__aenter__()
    try:
        alg = (await client.getkey2()).hashAlg
        jwt = await client.authenticate()
        structure = await client.load_structure()

        control = dict(structure["controls"][args.uuid])
        control["uuid"] = args.uuid
        adapter = get_adapter(control.get("type"))
        if adapter is None:
            print(f"Kein Adapter fuer Typ {control.get('type')}")
            return 1
        print(f"Control: {control.get('name')}  [{control.get('type')}]")

        # WebSocket-Live-Stream im Hintergrund
        states: dict[str, object] = {}
        ws = LoxoneWS(host=host, port=port, user=user, jwt=jwt, hash_alg=alg, verify_tls=verify)
        await ws.connect()
        task = asyncio.ensure_future(ws.stream(lambda u, v: states.__setitem__(u, v)))

        try:
            await asyncio.sleep(2.5)          # Voll-Dump abwarten
            show("IST", adapter, control, states)

            on_cmd = adapter.command(control, "on", states)
            print(f"  -> schalte AN  ({on_cmd[1]})")
            await client.jdev_get(f"sps/io/{on_cmd[0]}/{on_cmd[1]}")
            await asyncio.sleep(2.0)
            show("nach AN", adapter, control, states)

            off_cmd = adapter.command(control, "off", states)
            print(f"  -> schalte AUS ({off_cmd[1]})  [Ausgangszustand]")
            await client.jdev_get(f"sps/io/{off_cmd[0]}/{off_cmd[1]}")
            await asyncio.sleep(2.0)
            show("nach AUS", adapter, control, states)
        finally:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            await ws.close()
        return 0
    finally:
        await client.close()


def main() -> None:
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    p = argparse.ArgumentParser()
    p.add_argument("--uuid", default=DEFAULT_LIGHT)
    sys.exit(asyncio.run(run(p.parse_args())))


if __name__ == "__main__":
    main()
