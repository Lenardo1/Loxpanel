#!/usr/bin/env python3
"""Verifikation der SETZ-Befehle des Loxone-Sauna-Bausteins.

Die Loxone-Struktur (LoxAPP3.json) enthaelt die States des Sauna-Bausteins,
aber NICHT die Schreibbefehle fuer Solltemperatur und Betriebsart. Dieses
Skript probiert die ueblichen Befehlskandidaten an der ECHTEN Anlage durch und
meldet, welcher die Solltemperatur (State `tempTarget`) bzw. den Modus
(State `mode`) tatsaechlich setzt. Damit lassen sich die Schalt-Buttons im
Server (bin/webvisu.py) belegt statt geraten ergaenzen.

Sicherheit:
  * Ohne --write laeuft nur ein TROCKENLAUF (zeigt, was getestet wuerde).
  * Mit --write wird die Sauna kurzzeitig umgestellt; JEDER veraenderte Wert
    wird sofort wieder auf den Originalwert zurueckgesetzt.
  * Der Solltemperatur-Test aendert nur um 1 Grad; getestet wird nur, wenn die
    Sauna eingeschaltet ist (sonst ist tempTarget/mode nicht aussagekraeftig).
  * Der Modus-Test laeuft nur zusaetzlich mit --mode.

Ausfuehren (am besten bei EINGESCHALTETER Sauna).
  Unraid: die Datei in den appdata-Ordner legen (/mnt/user/appdata/loxpanel/config,
  im Container /app/config); der Container heisst "LoxPanel":
    docker exec -it LoxPanel python /app/config/sauna_probe.py --mode          # Trockenlauf
    docker exec -it LoxPanel python /app/config/sauna_probe.py --write --mode  # echte Verifikation
  Lokal (mit config/loxpanel.cfg oder LOXPANEL_MS_*-Variablen):
    python bin/sauna_probe.py --write --mode

Zugang: erst Env (LOXPANEL_MS_HOST/USER/PASS/PORT/VERIFY_TLS), sonst
config/loxpanel.cfg (wie der Server). Die komplette Ausgabe bitte teilen.
"""
import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

# Hilfsmodule (loxone_api via pip, loxone_ws lokal im bin-Ordner). Damit das
# Skript auch laeuft, wenn es woanders liegt - z.B. im gemounteten /app/config
# eines Unraid-Containers -, werden moegliche bin-Pfade zum Suchpfad ergaenzt.
_here = Path(__file__).resolve().parent
for _cand in (_here, _here.parent / "bin", Path("/app/bin")):
    if _cand.is_dir() and str(_cand) not in sys.path:
        sys.path.insert(0, str(_cand))
from loxone_api import LoxoneClient  # noqa: E402
from loxone_ws import LoxoneWS  # noqa: E402

# Uebliche Loxone-Befehlsformen zum Setzen eines analogen Sollwerts / einer
# Betriebsart. Reihenfolge = Testreihenfolge; der erste Treffer gewinnt.
TEMP_CMDS = ["temp/{v}", "settemp/{v}", "setTemp/{v}", "targetTemp/{v}",
             "tempTarget/{v}", "setpoint/{v}"]
MODE_CMDS = ["mode/{n}", "setmode/{n}", "setMode/{n}", "changeTo/{n}", "program/{n}"]

TEMP_MIN, TEMP_MAX = 30, 110   # Plausible Grenzen fuer den Test-Sollwert (Grad)


def _conn() -> dict:
    """Miniserver-Zugang: Env hat Vorrang (wie im Server), sonst loxpanel.cfg."""
    env = os.environ.get
    if env("LOXPANEL_MS_HOST"):
        return {"host": env("LOXPANEL_MS_HOST"), "user": env("LOXPANEL_MS_USER", ""),
                "pass": env("LOXPANEL_MS_PASS", ""), "port": int(env("LOXPANEL_MS_PORT") or "443"),
                "verify_tls": env("LOXPANEL_MS_VERIFY_TLS", "false").lower() in ("1", "true", "yes")}
    f = Path(__file__).resolve().parent.parent / "config" / "loxpanel.cfg"
    return json.loads(f.read_text(encoding="utf-8"))["miniserver"]


def _num(v):
    return v if isinstance(v, (int, float)) and not isinstance(v, bool) else None


async def _settle(st: dict, su: str, want: float, tries: int = 10, delay: float = 0.6):
    """Wartet, bis State `su` ~= `want` ist (oder Timeout). Gibt letzten Wert zurueck."""
    last = _num(st.get(su))
    for _ in range(tries):
        await asyncio.sleep(delay)
        last = _num(st.get(su))
        if last is not None and abs(last - want) < 0.5:
            return last
    return last


async def main() -> None:
    ap = argparse.ArgumentParser(description="Sauna-Setzbefehle an der Anlage verifizieren")
    ap.add_argument("--write", action="store_true", help="Befehle wirklich senden (sonst Trockenlauf)")
    ap.add_argument("--mode", action="store_true", help="zusaetzlich die Modus-Befehle testen")
    args = ap.parse_args()

    ms = _conn()
    st: dict = {}
    client = LoxoneClient(host=ms["host"], user=ms["user"], password=ms["pass"],
                          port=ms.get("port", 443), verify_tls=ms.get("verify_tls", False))
    await client.__aenter__()
    alg = (await client.getkey2()).hashAlg
    jwt = await client.authenticate()
    structure = await client.load_structure()
    # client bleibt OFFEN: er sendet die Test-Befehle (wie App.command im Server)

    ws = LoxoneWS(host=ms["host"], port=ms.get("port", 443), user=ms["user"], jwt=jwt,
                  hash_alg=alg, verify_tls=ms.get("verify_tls", False))
    await ws.connect()
    task = asyncio.ensure_future(ws.stream(lambda u, v: st.__setitem__(u, v)))
    await asyncio.sleep(4.0)   # States sammeln

    mode = "ECHTE BEFEHLE (--write)" if args.write else "TROCKENLAUF (kein --write)"
    print(f"\n=== Sauna-Setzbefehl-Verifikation | {mode} ===")

    saunas = [(u, c) for u, c in structure["controls"].items() if c.get("type") == "Sauna"]
    print(f"{len(saunas)} Control(s) mit type=='Sauna' von {len(structure['controls'])} gesamt")
    if not saunas:
        print("KEIN type=='Sauna' gefunden. Kandidaten nach Name:")
        for u, c in structure["controls"].items():
            if "sauna" in (c.get("name", "").lower()):
                print(f"  {c.get('name')!r}  type={c.get('type')}  uuidAction={c.get('uuidAction')}")

    async def send(uuid: str, cmd: str) -> None:
        print(f"      -> sps/io/{uuid}/{cmd}")
        try:
            await client.jdev_get(f"sps/io/{uuid}/{cmd}")
        except Exception as e:            # ungueltiger Befehl -> weiter zum naechsten
            print(f"         (Antwort/Fehler: {e})")

    async def probe(uuid, su, templates, base, target, key):
        """Testet die Befehlsformen fuer einen numerischen State. Stellt jeden
        veraenderten Wert sofort wieder her. Gibt das treffende Template zurueck."""
        found = None
        for tmpl in templates:
            cmd = tmpl.format(**{key: target})
            if not args.write:
                print(f"    [trocken] wuerde testen: {cmd}")
                continue
            print(f"    teste {tmpl}")
            await send(uuid, cmd)
            got = await _settle(st, su, target)
            hit = got is not None and abs(got - target) < 0.5
            changed = got is not None and abs(got - base) >= 0.5
            print(f"      Ergebnis: {su} = {got!r}  -> {'TREFFER' if hit else ('veraendert' if changed else 'keine Aenderung')}")
            if changed:                    # Originalwert zuruecksetzen
                await send(uuid, tmpl.format(**{key: base}))
                await _settle(st, su, base)
            if hit:
                found = tmpl
                break
        return found

    for u, c in saunas:
        s = c.get("states") or {}
        ua = c.get("uuidAction")
        print(f"\n# {c.get('name')!r}  uuidAction={ua}")
        print(f"  details: {json.dumps(c.get('details') or {}, ensure_ascii=False)}")

        # --- Solltemperatur ---
        su_t = s.get("tempTarget")
        cur_t = _num(st.get(su_t))
        print(f"  tempTarget [{su_t}] = {st.get(su_t)!r}")
        if cur_t is None or cur_t < TEMP_MIN:
            print(f"  -> uebersprungen: tempTarget < {TEMP_MIN} (Sauna vermutlich AUS). "
                  f"Bitte Sauna einschalten und erneut ausfuehren.")
        else:
            base = int(round(cur_t))
            target = base - 1 if base >= TEMP_MAX else base + 1
            print(f"  Test-Sollwert {target} (Original {base}, wird wiederhergestellt)")
            res = await probe(ua, su_t, TEMP_CMDS, base, target, "v")
            if args.write:
                print(f"  => Solltemperatur-Befehl: {res or 'KEINER der Kandidaten hat gewirkt'}")

        # --- Betriebsart (optional) ---
        if args.mode:
            su_m = s.get("mode")
            cur_m = _num(st.get(su_m))
            print(f"  mode [{su_m}] = {st.get(su_m)!r}")
            if cur_m is None:
                print("  -> uebersprungen: mode ist kein Zahlenwert im Stream.")
            else:
                base_m = int(round(cur_m))
                target_m = (base_m + 1) % 7
                print(f"  Test-Modus {target_m} (Original {base_m}, wird wiederhergestellt)")
                res_m = await probe(ua, su_m, MODE_CMDS, base_m, target_m, "n")
                if args.write:
                    print(f"  => Modus-Befehl: {res_m or 'KEINER der Kandidaten hat gewirkt'}")

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
