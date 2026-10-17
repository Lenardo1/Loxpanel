#!/usr/bin/env python3
"""Steuerbefehle an der echten Anlage nachpruefen.

LoxPanel sendet seit 03.10.2026, was die Loxone-Strukturdoku (Stand 16.0) und
die Wissensdatenbank angeben. Dieses Skript prueft an der eigenen Anlage nach,
ob der Miniserver es so annimmt:

  --updown : UpDownAnalog – laut Doku ist der Befehl der Wert selbst
             (sps/io/<uuid>/<wert>). Prueft das; wirkt er nicht, testet es die
             Auf/Ab-Puls-Befehle (UpOn/UpOff/DownOn/DownOff) wie bei
             UpDownDigital. Harmlos (Beschattungs-/Analogwert), wird
             zurueckgesetzt.
  --zones  : Irrigation – laut Doku ist select/1 die Zone mit id 0, also
             currentZone 0 (siehe IRR_SELECT_* in webvisu.py). Sendet select/1
             und liest currentZone ab. ACHTUNG: das laesst KURZ echtes Wasser
             laufen; direkt danach wird stop + select/0 gesendet. Nur
             ausfuehren, wenn das ok ist.

Ohne --write laeuft ein TROCKENLAUF (zeigt nur, was getestet wuerde).
Mindestens eines von --updown / --zones angeben.

Ausfuehren (Unraid, Container "LoxPanel"; Datei nach /app/config oder per docker cp):
    docker exec -it LoxPanel python /app/config/steuer_probe.py --updown            # Trockenlauf
    docker exec -it LoxPanel python /app/config/steuer_probe.py --updown --write     # echt (harmlos)
    docker exec -it LoxPanel python /app/config/steuer_probe.py --zones  --write     # echt (Wasser!)
Lokal: python bin/steuer_probe.py --updown --write   (mit config/loxpanel.cfg oder LOXPANEL_MS_*)

Zugang: erst Env (LOXPANEL_MS_HOST/USER/PASS/PORT/VERIFY_TLS), sonst
config/loxpanel.cfg. Die komplette Ausgabe bitte teilen.
"""
import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

_here = Path(__file__).resolve().parent
for _cand in (_here, _here.parent / "bin", Path("/app/bin")):
    if _cand.is_dir() and str(_cand) not in sys.path:
        sys.path.insert(0, str(_cand))
from loxone_api import LoxoneClient  # noqa: E402
from loxone_ws import LoxoneWS  # noqa: E402


def _conn() -> dict:
    env = os.environ.get
    if env("LOXPANEL_MS_HOST"):
        return {"host": env("LOXPANEL_MS_HOST"), "user": env("LOXPANEL_MS_USER", ""),
                "pass": env("LOXPANEL_MS_PASS", ""), "port": int(env("LOXPANEL_MS_PORT") or "443"),
                "verify_tls": env("LOXPANEL_MS_VERIFY_TLS", "false").lower() in ("1", "true", "yes")}
    f = Path(__file__).resolve().parent.parent / "config" / "loxpanel.cfg"
    return json.loads(f.read_text(encoding="utf-8"))["miniserver"]


def _num(v):
    return v if isinstance(v, (int, float)) and not isinstance(v, bool) else None


async def _settle(st, su, want, tries=10, delay=0.6):
    last = _num(st.get(su))
    for _ in range(tries):
        await asyncio.sleep(delay)
        last = _num(st.get(su))
        if last is not None and abs(last - want) < 0.5:
            return last
    return last


def _fmt(v):
    return str(int(v)) if float(v).is_integer() else repr(v)


async def main() -> None:
    ap = argparse.ArgumentParser(description="Offene Steuerbefehle an der Anlage verifizieren")
    ap.add_argument("--write", action="store_true", help="Befehle wirklich senden (sonst Trockenlauf)")
    ap.add_argument("--updown", action="store_true", help="UpDownAnalog-Setzbefehl testen (harmlos)")
    ap.add_argument("--zones", action="store_true", help="Irrigation-Zonennummerierung testen — laesst KURZ Wasser laufen!")
    args = ap.parse_args()
    if not (args.updown or args.zones):
        print("Nichts zu tun: bitte --updown und/oder --zones angeben.")
        return

    ms = _conn()
    st: dict = {}
    client = LoxoneClient(host=ms["host"], user=ms["user"], password=ms["pass"],
                          port=ms.get("port", 443), verify_tls=ms.get("verify_tls", False))
    await client.__aenter__()
    alg = (await client.getkey2()).hashAlg
    jwt = await client.authenticate()
    structure = await client.load_structure()  # client bleibt offen zum Senden

    ws = LoxoneWS(host=ms["host"], port=ms.get("port", 443), user=ms["user"], jwt=jwt,
                  hash_alg=alg, verify_tls=ms.get("verify_tls", False))
    await ws.connect()
    task = asyncio.ensure_future(ws.stream(lambda u, v: st.__setitem__(u, v)))
    await asyncio.sleep(4.0)

    controls = structure["controls"]
    mode = "ECHTE BEFEHLE (--write)" if args.write else "TROCKENLAUF (kein --write)"
    print(f"\n=== Steuerbefehl-Verifikation | {mode} ===")

    async def send(uuid, cmd):
        print(f"      -> sps/io/{uuid}/{cmd}")
        try:
            await client.jdev_get(f"sps/io/{uuid}/{cmd}")
        except Exception as e:
            print(f"         (Antwort/Fehler: {e})")

    # --- UpDownAnalog: Zielwert setzen ---
    if args.updown:
        uda = [(u, c) for u, c in controls.items() if c.get("type") == "UpDownAnalog"]
        print(f"\n### UpDownAnalog: {len(uda)} Control(s)")
        for u, c in uda:
            ua = c.get("uuidAction")
            s = c.get("states") or {}
            det = c.get("details") or {}
            vu = s.get("value")
            cur = _num(st.get(vu))
            mn = _num(det.get("min")); mx = _num(det.get("max")); step = _num(det.get("step")) or 1
            print(f"\n# {c.get('name')!r} uuidAction={ua}")
            print(f"  value[{vu}]={st.get(vu)!r}  details.min={mn} max={mx} step={step}")
            if cur is None:
                print("  -> uebersprungen: kein Zahlenwert im Stream.")
                continue
            target = cur + step
            if mx is not None and target > mx:
                target = cur - step
            if mn is not None and target < mn:
                print("  -> uebersprungen: kein sicherer Testwert im Bereich min..max.")
                continue
            if not args.write:
                print(f"  [trocken] wuerde Roh-Wert testen: {_fmt(target)} (dann zurueck auf {_fmt(cur)})")
                print("  [trocken] Fallback bei Nicht-Wirkung: UpOn/UpOff bzw. DownOn/DownOff")
                continue
            # 1) Roh-Wert
            await send(ua, _fmt(target))
            got = await _settle(st, vu, target)
            if got is not None and abs(got - target) < 0.5:
                print(f"  Ergebnis: value={got!r} -> TREFFER: Roh-Wert 'sps/io/<uuid>/<wert>'")
                await send(ua, _fmt(cur)); await _settle(st, vu, cur)
                continue
            print(f"  Roh-Wert wirkt nicht (value={got!r}). Teste Auf/Ab-Puls (wie UpDownDigital)...")
            # 2) Auf/Ab-Puls
            await send(ua, "UpOn"); await asyncio.sleep(1.0); await send(ua, "UpOff")
            got = await _settle(st, vu, cur + step, tries=4)
            if got is not None and abs(got - cur) >= 0.5:
                print(f"  Ergebnis: value={got!r} -> TREFFER: Auf/Ab-Puls 'UpOn/UpOff' + 'DownOn/DownOff'")
                await send(ua, "DownOn"); await asyncio.sleep(1.0); await send(ua, "DownOff")
                await _settle(st, vu, cur)
            else:
                print(f"  Auch Auf/Ab-Puls wirkt nicht (value={got!r}). Bitte Ausgabe teilen — dann sehen wir weiter.")

    # --- Irrigation: Zonennummerierung ---
    if args.zones:
        irr = [(u, c) for u, c in controls.items() if c.get("type") == "Irrigation"]
        print(f"\n### Irrigation: {len(irr)} Control(s)")
        for u, c in irr:
            ua = c.get("uuidAction")
            s = c.get("states") or {}
            cz = s.get("currentZone")
            print(f"\n# {c.get('name')!r} uuidAction={ua}")
            print(f"  currentZone[{cz}]={st.get(cz)!r}")
            if not args.write:
                print("  [trocken] wuerde 'select/1' senden und currentZone ablesen,")
                print("            danach sofort 'stop' + 'select/0'. (--write laesst KURZ Wasser laufen!)")
                continue
            print("  ACHTUNG: sende jetzt select/1 (eine Zone laeuft kurz), messe, dann stop + select/0.")
            base = _num(st.get(cz))
            await send(ua, "select/1")
            await asyncio.sleep(2.0)
            got = _num(st.get(cz))
            print(f"  Ergebnis: currentZone {base!r} -> {got!r}  (0 => 0-basiert: Zone 1 = select/1, currentZone 0;"
                  f" 1 => 1-basiert)")
            await send(ua, "stop")
            await send(ua, "select/0")
            await asyncio.sleep(1.0)
            print(f"  zurueckgesetzt: currentZone={st.get(cz)!r}")

    print("\n=== fertig. Bitte die komplette Ausgabe teilen. ===")
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    await ws.close()
    await client.close()


if __name__ == "__main__":
    asyncio.run(main())
