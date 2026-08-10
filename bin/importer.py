#!/usr/bin/env python3
"""LoxPanel Importer - Phase 1.

Laedt die Loxone-Struktur (LoxAPP3.json) und schreibt eine normalisierte
structure.json, die das Designer-Frontend als Navigationsbaum anzeigt.

Aufruf (Standalone-Test):
    python3 importer.py --host 192.168.1.10 --user admin --pass secret --out structure.json

Aufruf auf LoxBerry (Config wird gelesen):
    python3 importer.py
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import loxone_client as lox  # noqa: E402

log = logging.getLogger("loxpanel.importer")


def data_dir() -> Path:
    """Datenordner: auf LoxBerry $LBPDATA/loxpanel, sonst ./data."""
    lbpdata = os.environ.get("LBPDATA")
    if lbpdata:
        return Path(lbpdata) / "loxpanel"
    return Path(__file__).resolve().parent.parent / "data"


def config_path() -> Path:
    lbpconfig = os.environ.get("LBPCONFIG")
    if lbpconfig:
        return Path(lbpconfig) / "loxpanel" / "loxpanel.cfg"
    return Path(__file__).resolve().parent.parent / "config" / "loxpanel.cfg.example"


def miniserver_from_loxberry(msno: int = 1) -> dict | None:
    """Liest Miniserver-Zugangsdaten aus der LoxBerry-Systemconfig.

    TODO: An die konkrete general.json-Struktur der Ziel-LoxBerry-Version
    anpassen bzw. auf die offiziellen Python-Bindings umstellen, sobald genutzt.
    """
    lbsconfig = os.environ.get("LBSCONFIG")
    if not lbsconfig:
        return None
    general = Path(lbsconfig) / "general.json"
    if not general.is_file():
        return None
    try:
        cfg = json.loads(general.read_text(encoding="utf-8"))
        ms = cfg.get("Miniserver", {}).get(str(msno))
        if not ms:
            return None
        return {
            "host": ms.get("Ipaddress") or ms.get("IPAddress"),
            "user": ms.get("Admin"),
            "pass": ms.get("Pass"),
            "https": str(ms.get("Porthttps", "")).strip() not in ("", "0"),
        }
    except (OSError, ValueError) as err:
        log.warning("general.json konnte nicht gelesen werden: %s", err)
        return None


def load_conn(args: argparse.Namespace) -> dict:
    """Verbindungsdaten ermitteln: CLI > LoxBerry-MS > Plugin-Config."""
    if args.host:
        return {"host": args.host, "user": args.user, "pass": args.password,
                "https": args.https}

    cfg = {}
    cfgfile = config_path()
    if cfgfile.is_file():
        cfg = json.loads(cfgfile.read_text(encoding="utf-8")).get("miniserver", {})

    ms = miniserver_from_loxberry(cfg.get("msno", 1))
    if ms and ms.get("host"):
        return ms

    if cfg.get("host"):
        return {"host": cfg["host"], "user": cfg.get("user"),
                "pass": cfg.get("pass"), "https": cfg.get("https", False)}

    log.error("Keine Miniserver-Verbindungsdaten gefunden (CLI/LoxBerry/Config).")
    sys.exit(2)


def normalize(struct: lox.Structure) -> dict:
    """Erzeugt den Baum fuer das Designer-Frontend."""
    by_room = struct.by_room()
    tree: dict = {"miniserver": struct.ms_name, "rooms": [], "categories": []}

    for ruuid, name in sorted(struct.rooms.items(), key=lambda kv: kv[1].lower()):
        controls = []
        for c in sorted(by_room.get(ruuid, []), key=lambda c: c.name.lower()):
            controls.append({
                "uuid": c.uuid,
                "name": c.name,
                "type": c.type,
                "cat": c.cat,
                "states": list(c.states.keys()),
                "defaultIcon": c.default_icon,
            })
        tree["rooms"].append({
            "uuid": ruuid,
            "name": name,
            "icon": struct.room_icons.get(ruuid),
            "controlCount": len(controls),
            "controls": controls,
        })

    for cuuid, name in sorted(struct.cats.items(), key=lambda kv: kv[1].lower()):
        tree["categories"].append({
            "uuid": cuuid, "name": name, "icon": struct.cat_icons.get(cuuid),
        })
    return tree


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    p = argparse.ArgumentParser(description="LoxPanel Struktur-Importer")
    p.add_argument("--host")
    p.add_argument("--user", default="admin")
    p.add_argument("--pass", dest="password", default="")
    p.add_argument("--https", action="store_true")
    p.add_argument("--out", help="Zieldatei (Standard: <data>/structure.json)")
    args = p.parse_args()

    conn = load_conn(args)
    struct = lox.fetch_structure(conn["host"], conn.get("user") or "admin",
                                 conn.get("pass") or "", https=conn.get("https", False))
    tree = normalize(struct)

    out = Path(args.out) if args.out else (data_dir() / "structure.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(tree, ensure_ascii=False, indent=2), encoding="utf-8")
    log.info("structure.json geschrieben: %s (%d Raeume)", out, len(tree["rooms"]))

    # Kurze Baumausgabe zur Kontrolle
    for room in tree["rooms"]:
        print(f"[{room['name']}] ({room['controlCount']} Controls)")
        for c in room["controls"][:8]:
            print(f"    - {c['name']}  <{c['type']}>")


if __name__ == "__main__":
    main()
