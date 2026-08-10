#!/usr/bin/env python3
"""LoxPanel Phase-2-Probe: ein Control auslesen und schalten.

Verbindungsdaten kommen aus config/loxpanel.cfg (Block "miniserver"), koennen
aber per CLI ueberschrieben werden. So muss kein Passwort auf der Kommandozeile
stehen.

  - ohne --uuid: listet alle LightControllerV2 (mit UUID + Zustands-UUIDs) auf
  - --uuid <uuid> --read: liest den aktuellen Wert (Control- ODER State-UUID)
  - --uuid <uuid> --cmd changeTo/778 : sendet einen Befehl (Control-UUID)
  - --uuid <uuid> --watch: pollt und zeigt Wertaenderungen live

Beispiel:
  python light_test.py                         # nutzt config/loxpanel.cfg
  python light_test.py --uuid 13fd... --read
  python light_test.py --uuid 13fd...a7be --cmd changeTo/778
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from loxone_live import LoxoneLive  # noqa: E402

log = logging.getLogger("loxpanel.lighttest")


def _config_file() -> Path:
    base = Path(__file__).resolve().parent.parent / "config"
    real = base / "loxpanel.cfg"
    return real if real.is_file() else base / "loxpanel.cfg.example"


def resolve_conn(args: argparse.Namespace) -> dict:
    """CLI-Werte haben Vorrang, sonst aus config/loxpanel.cfg (miniserver-Block)."""
    cfg: dict = {}
    f = _config_file()
    if f.is_file():
        try:
            cfg = json.loads(f.read_text(encoding="utf-8")).get("miniserver", {})
        except ValueError as err:
            log.warning("Config %s nicht lesbar: %s", f, err)

    conn = {
        "host": args.host or cfg.get("host"),
        "user": args.user or cfg.get("user"),
        "password": args.password or cfg.get("pass"),
        "port": args.port or cfg.get("port", 443),
        "verify_tls": args.verify_tls if args.verify_tls else cfg.get("verify_tls", False),
    }
    missing = [k for k in ("host", "user", "password") if not conn[k]]
    if missing:
        log.error("Fehlende Verbindungsdaten: %s (CLI oder config/loxpanel.cfg)", ", ".join(missing))
        sys.exit(2)
    return conn


def list_lights(structure: dict) -> None:
    controls = structure.get("controls", {})
    lights = {u: c for u, c in controls.items() if c.get("type") == "LightControllerV2"}
    if not lights:
        print("Keine LightControllerV2 gefunden. Vorhandene Typen:")
        print("  " + ", ".join(sorted({c.get("type", "?") for c in controls.values()})))
        return
    print(f"{len(lights)} LightControllerV2 gefunden:\n")
    for u, c in lights.items():
        print(f"  {c.get('name','?')}")
        print(f"    control : {u}")
        for sname, suuid in (c.get("states") or {}).items():
            print(f"    state   : {sname} = {suuid}")
        print()


async def run(args: argparse.Namespace, conn: dict) -> int:
    live = LoxoneLive(host=conn["host"], user=conn["user"], password=conn["password"],
                      port=conn["port"], verify_tls=conn["verify_tls"])
    structure = await live.connect()
    try:
        if not args.uuid:
            list_lights(structure)
            return 0

        if args.cmd:
            resp = await live.send_command(args.uuid, args.cmd)
            print(f"Befehl '{args.cmd}' gesendet -> Antwort: {resp}")

        if args.watch:
            live.on_value(lambda uuid, value: print(f"[live] {uuid} = {value!r}"))
            print("Polling laeuft (Strg+C zum Beenden) ...")
            await live.watch([args.uuid], interval=args.interval)
        elif args.read or not args.cmd:
            print(f"Wert von {args.uuid}: {await live.read(args.uuid)!r}")
        return 0
    finally:
        await live.close()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    p = argparse.ArgumentParser(description="LoxPanel Phase-2-Probe")
    p.add_argument("--host")
    p.add_argument("--user")
    p.add_argument("--pass", dest="password")
    p.add_argument("--port", type=int)
    p.add_argument("--verify-tls", dest="verify_tls", action="store_true",
                   help="TLS-Zertifikat pruefen (Standard: aus, Gen2 selbstsigniert)")
    p.add_argument("--uuid", help="Control- oder State-UUID")
    p.add_argument("--read", action="store_true")
    p.add_argument("--cmd", help="Befehl senden (z.B. changeTo/778, plus, minus)")
    p.add_argument("--watch", action="store_true", help="Live pollen")
    p.add_argument("--interval", type=float, default=1.0)
    args = p.parse_args()
    conn = resolve_conn(args)
    sys.exit(asyncio.run(run(args, conn)))


if __name__ == "__main__":
    main()
