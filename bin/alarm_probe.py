#!/usr/bin/env python3
"""Diagnose fuer Wecker-Bausteine (AlarmClock): zeigt Typ, alle State-Namen und
die LIVE-Werte (entryList ungekuerzt) direkt vom Miniserver.

Ausfuehren:
    docker exec -it loxpanel python bin/alarm_probe.py     # im Container
    python bin/alarm_probe.py                              # lokal (mit config/loxpanel.cfg)

Miniserver-Zugang: erst Env (LOXPANEL_MS_HOST/USER/PASS/PORT/VERIFY_TLS),
sonst config/loxpanel.cfg (wie der Server). Die Ausgabe bitte komplett teilen.
"""
import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from loxone_api import LoxoneClient  # noqa: E402
from loxone_ws import LoxoneWS  # noqa: E402


def _conn() -> dict:
    """Miniserver-Zugang: Env hat Vorrang (wie im Server), sonst loxpanel.cfg."""
    env = os.environ.get
    if env("LOXPANEL_MS_HOST"):
        return {"host": env("LOXPANEL_MS_HOST"), "user": env("LOXPANEL_MS_USER", ""),
                "pass": env("LOXPANEL_MS_PASS", ""), "port": int(env("LOXPANEL_MS_PORT", "443")),
                "verify_tls": env("LOXPANEL_MS_VERIFY_TLS", "false").lower() in ("1", "true", "yes")}
    f = Path(__file__).resolve().parent.parent / "config" / "loxpanel.cfg"
    return json.loads(f.read_text(encoding="utf-8"))["miniserver"]


async def main() -> None:
    ms = _conn()
    st: dict = {}
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
    await asyncio.sleep(4.0)   # kurz sammeln, damit die States eintrudeln

    op = structure.get("operatingModes") or {}
    print("\n=== operatingModes (fuer Wecker-Wiederholung / modes) ===")
    print(" ", json.dumps(op, ensure_ascii=False))

    controls = structure["controls"]
    clocks = [(u, c) for u, c in controls.items() if c.get("type") == "AlarmClock"]
    print(f"\n=== {len(clocks)} AlarmClock-Control(s) von {len(controls)} gesamt ===")
    # Falls kein AlarmClock: zeige Controls, deren Name nach Wecker aussieht
    if not clocks:
        print("KEIN Control mit type=='AlarmClock' gefunden! Kandidaten nach Name:")
        for u, c in controls.items():
            if "weck" in (c.get("name", "").lower()):
                print(f"  {c.get('name')!r}  type={c.get('type')}  states={list((c.get('states') or {}).keys())}")

    for u, c in clocks:
        s = c.get("states") or {}
        print(f"\n# {c.get('name')!r}  uuid={u}  uuidAction={c.get('uuidAction')}")
        print(f"  details: {json.dumps(c.get('details') or {}, ensure_ascii=False)[:300]}")
        print(f"  State-Namen: {list(s.keys())}")
        for sn, su in s.items():
            v = st.get(su)
            got = "  (kein Wert im Stream)" if su not in st else ""
            print(f"    {sn}  [{su}] = {v!r}{got}")

    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    await ws.close()


if __name__ == "__main__":
    asyncio.run(main())
