#!/usr/bin/env python3
"""Read-only-Diagnose der Miniserver-Struktur (LoxAPP3.json): Was liefert die
Anlage, und was davon nutzt LoxPanel schon?

Die Loxone-App und das Wall Display bauen ihre Oberflaeche aus genau dieser
Struktur. Diese Sonde laedt sie mit dem vorhandenen Zugang (wie der Server) und
zeigt:

  Teil 1  Alle obersten Schluessel mit Typ und Groesse, markiert als
          [genutzt] oder [UNGENUTZT] gegenueber dem, was webvisu.py liest.
  Teil 2  Die ungenutzten/seltenen Sonderschluessel gekuerzt als JSON — hier
          steckt, falls vorhanden, eine App-/Wall-Display-Ansichtsdefinition.
  Teil 3  Volkszaehlung der Bausteine: Typen und wie oft, dazu alle
          vorkommenden Feldnamen eines Controls (genutzt/UNGENUTZT).
  Teil 4  msInfo (Firmware, Seriennummer, Standort — keine Zugangsdaten).

Aufruf im Container (nur Lesen, veraendert nichts, gibt keine Passwoerter aus):

    curl -fsSL <raw-url> | docker exec -i LoxPanel python3 -u -
    docker exec -i LoxPanel python3 -u bin/structure_probe.py           # im Image

Zugang wie der Server: loxpanel.cfg (Settings) vor LOXPANEL_MS_*.
"""
import asyncio
import json
import os
import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent if "__file__" in globals() else Path("/app")

# Was webvisu.py aus der Struktur liest (ermittelt aus dem Quelltext). Alles
# andere ist fuer LoxPanel derzeit ungenutzt und damit der interessante Teil.
USED_TOP = {"controls", "rooms", "cats", "mediaServer", "weatherServer",
            "operatingModes", "msInfo", "globalStates"}
USED_CTRL = {"name", "type", "uuidAction", "room", "cat", "states", "details",
             "subControls", "isSecured", "isFavorite", "defaultIcon"}
# Schluessel-/Typnamen, die nach einer Ansichts- oder Client-Definition klingen.
HINT = ("view", "app", "display", "client", "page", "screen", "favor",
        "tab", "layout", "present", "wall", "panel")


def cut(s, n=1200):
    s = str(s).replace("\n", " ")
    return s if len(s) <= n else s[:n] + f" … (+{len(s) - n} Zeichen)"


def shape(v) -> str:
    if isinstance(v, dict):
        return f"dict, {len(v)} Eintraege"
    if isinstance(v, list):
        return f"list, {len(v)} Elemente"
    if isinstance(v, str):
        return f"str ({len(v)} Zeichen): {cut(v, 60)}"
    return f"{type(v).__name__}: {cut(v, 60)}"


def looks_interesting(name: str) -> bool:
    low = str(name).lower()
    return any(h in low for h in HINT)


def miniserver_config() -> dict:
    """Zugang wie der Server: loxpanel.cfg (Settings) vor Umgebungsvariablen."""
    for base in (APP_DIR / "config", Path("/app/config")):
        f = base / "loxpanel.cfg"
        if f.is_file():
            try:
                ms = json.loads(f.read_text(encoding="utf-8")).get("miniserver", {})
            except ValueError:
                ms = {}
            if ms.get("host"):
                return ms
    env = os.environ
    if env.get("LOXPANEL_MS_HOST"):
        return {"host": env["LOXPANEL_MS_HOST"], "user": env.get("LOXPANEL_MS_USER", ""),
                "pass": env.get("LOXPANEL_MS_PASS", ""), "port": int(env.get("LOXPANEL_MS_PORT") or "443"),
                "verify_tls": env.get("LOXPANEL_MS_VERIFY_TLS", "false").lower() in ("1", "true", "yes")}
    return {}


async def load_structure() -> dict:
    for d in (str(APP_DIR / "bin"), "/app/bin"):
        if d not in sys.path:
            sys.path.insert(0, d)
    from loxone_api import LoxoneClient
    ms = miniserver_config()
    if not ms.get("host"):
        raise RuntimeError("kein Miniserver-Zugang gefunden (loxpanel.cfg oder LOXPANEL_MS_*)")
    port = int(ms.get("port", 443))
    c = LoxoneClient(host=ms["host"], user=ms.get("user", ""), password=ms.get("pass", ""),
                     port=port, verify_tls=bool(ms.get("verify_tls", False)))
    if port == 80:   # Gen 1 spricht nur HTTP
        c.base_url = f"http://{ms['host']}:{port}/"
    async with c:
        await c.getkey2()
        await c.authenticate()
        return await c.load_structure()


def part1_toplevel(st: dict) -> None:
    print("\n===== Teil 1: Oberste Schluessel der Struktur")
    for k in sorted(st.keys()):
        tag = "[genutzt]  " if k in USED_TOP else "[UNGENUTZT]"
        hint = "  <- Ansicht?" if looks_interesting(k) else ""
        print(f"  {tag} {k:<20} {shape(st[k])}{hint}")
    unused = [k for k in st if k not in USED_TOP]
    print(f"\n  {len(st)} Schluessel gesamt, {len(unused)} davon nutzt LoxPanel nicht: "
          f"{', '.join(sorted(unused)) or 'keine'}")


def part2_unused(st: dict) -> None:
    print("\n===== Teil 2: Ungenutzte Sonderschluessel im Detail")
    big = {"controls", "rooms", "cats", "states", "controlsSubControls"}
    shown = False
    for k in sorted(st.keys()):
        if k in USED_TOP or k in big:
            continue
        shown = True
        try:
            js = json.dumps(st[k], ensure_ascii=False)
        except (TypeError, ValueError):
            js = repr(st[k])
        print(f"\n--- {k} ({shape(st[k])})")
        print("  " + cut(js, 1600))
    # Auch genutzte, aber ansichts-verdaechtige Schluessel kurz anzeigen.
    for k in sorted(st.keys()):
        if k in USED_TOP and looks_interesting(k):
            print(f"\n--- {k} (genutzt, aber ansichts-verdaechtig; {shape(st[k])})")
    if not shown:
        print("  keine ungenutzten Sonderschluessel (ausser den grossen Tabellen)")


def part3_controls(st: dict) -> None:
    controls = st.get("controls") or {}
    print(f"\n===== Teil 3: Bausteine ({len(controls)} Stueck)")
    types, fields, detail_keys = {}, {}, {}
    fav = sec = 0
    for c in controls.values():
        if not isinstance(c, dict):
            continue
        types[c.get("type", "?")] = types.get(c.get("type", "?"), 0) + 1
        for f in c:
            fields[f] = fields.get(f, 0) + 1
        if isinstance(c.get("details"), dict):
            for dk in c["details"]:
                detail_keys[dk] = detail_keys.get(dk, 0) + 1
        fav += 1 if c.get("isFavorite") else 0
        sec += 1 if c.get("isSecured") else 0
    print("\n  Bausteintypen (Anzahl):")
    for t, n in sorted(types.items(), key=lambda x: -x[1]):
        print(f"    {n:>4}  {t}")
    print(f"\n  Favoriten (isFavorite): {fav}   gesichert (isSecured): {sec}")
    print("\n  Feldnamen je Baustein (genutzt/UNGENUTZT):")
    for f, n in sorted(fields.items(), key=lambda x: -x[1]):
        tag = "genutzt   " if f in USED_CTRL else "UNGENUTZT "
        print(f"    {tag} {f:<20} in {n} Bausteinen")
    print("\n  Haeufigste details-Schluessel (Auswahl):")
    for dk, n in sorted(detail_keys.items(), key=lambda x: -x[1])[:25]:
        print(f"    {n:>4}  details.{dk}")


def part4_msinfo(st: dict) -> None:
    info = st.get("msInfo") or {}
    print("\n===== Teil 4: msInfo (keine Zugangsdaten)")
    if not isinstance(info, dict):
        print(f"  {shape(info)}")
        return
    skip = ("serialNr", "mac")   # gekuerzt zeigen, nicht komplett
    for k in sorted(info.keys()):
        v = info[k]
        if k in skip and isinstance(v, str) and len(v) > 4:
            v = v[:4] + "…"
        print(f"    {k:<22} {cut(v, 80)}")


async def main():
    print("Struktur laden ...")
    try:
        st = await load_structure()
    except Exception as err:
        print(f"Struktur nicht ladbar: {cut(err, 200)}")
        return
    if not isinstance(st, dict):
        print(f"Unerwartete Struktur: {shape(st)}")
        return
    print(f"Struktur geladen: {len(st)} oberste Schluessel.")
    part1_toplevel(st)
    part2_unused(st)
    part3_controls(st)
    part4_msinfo(st)
    print("\nFertig. [UNGENUTZT] mit Markierung '<- Ansicht?' ist der spannende Teil:\n"
          "steckt dort eine Seiten-/Kachel-Definition, kann LoxPanel sie uebernehmen.")


if __name__ == "__main__":
    asyncio.run(main())
