"""Minimaler Loxone-Miniserver-Client fuer LoxHASP.

Phase 1 implementiert den Struktur-Import ueber HTTP (data/LoxAPP3.json).
Die Live-Werte ueber den token-authentifizierten WebSocket sind als Stub
angelegt (siehe LoxoneWebSocket) und werden in Phase 2 ausgebaut.

Abhaengigkeit: python3-requests
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import requests

log = logging.getLogger("loxhasp.loxone")


@dataclass
class Control:
    uuid: str
    name: str
    type: str
    room: str | None = None
    cat: str | None = None
    states: dict[str, Any] = field(default_factory=dict)
    default_icon: str | None = None
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class Structure:
    ms_name: str
    rooms: dict[str, str]          # uuid -> name
    cats: dict[str, str]           # uuid -> name
    room_icons: dict[str, str]     # uuid -> svg-icon-uuid
    cat_icons: dict[str, str]      # uuid -> svg-icon-uuid
    controls: dict[str, Control]

    def by_room(self) -> dict[str | None, list[Control]]:
        out: dict[str | None, list[Control]] = {u: [] for u in self.rooms}
        for c in self.controls.values():
            out.setdefault(c.room, []).append(c)
        return out


def fetch_structure(host: str, user: str, password: str,
                    https: bool = False, timeout: int = 15) -> Structure:
    """Laedt LoxAPP3.json vom Miniserver und normalisiert es."""
    scheme = "https" if https else "http"
    url = f"{scheme}://{host}/data/LoxAPP3.json"
    log.info("Lade Struktur von %s", url)
    resp = requests.get(url, auth=(user, password), timeout=timeout)
    resp.raise_for_status()
    return parse_structure(resp.json())


def parse_structure(data: dict) -> Structure:
    """Wandelt das rohe LoxAPP3.json in eine Structure um.

    Hinweis: Manche Controls tragen verschachtelte subControls - die werden hier
    noch nicht rekursiv aufgeloest (TODO Phase 2, z.B. fuer AudioZone-Unterobjekte).
    """
    raw_rooms = data.get("rooms", {}) or {}
    raw_cats = data.get("cats", {}) or {}

    rooms = {u: v.get("name", "") for u, v in raw_rooms.items()}
    cats = {u: v.get("name", "") for u, v in raw_cats.items()}
    room_icons = {u: v["image"] for u, v in raw_rooms.items() if v.get("image")}
    cat_icons = {u: v["image"] for u, v in raw_cats.items() if v.get("image")}

    controls: dict[str, Control] = {}
    for uuid, v in (data.get("controls", {}) or {}).items():
        controls[uuid] = Control(
            uuid=uuid,
            name=v.get("name", ""),
            type=v.get("type", ""),
            room=v.get("room"),
            cat=v.get("cat"),
            states=v.get("states", {}) or {},
            default_icon=v.get("defaultIcon"),
            details=v.get("details", {}) or {},
        )

    ms_name = (data.get("msInfo", {}) or {}).get("msName", "Miniserver")
    log.info("Struktur geladen: %d Raeume, %d Kategorien, %d Controls",
             len(rooms), len(cats), len(controls))
    return Structure(ms_name, rooms, cats, room_icons, cat_icons, controls)


class LoxoneWebSocket:
    """Stub fuer die Live-Wert-Anbindung ueber den Miniserver-WebSocket.

    TODO Phase 2:
      - Token-Handshake (jdev/sys/getkey2, AES/RSA) implementieren, z.B. auf
        Basis von PyLoxone (JoDehli) / loxwebsocket.
      - Verbindung ws://<host>/ws/rfc6455, Binaernachrichten parsen
        (Header-Typen 0..6, Value-/Text-States je UUID).
      - Callback pro geaenderter UUID -> Daemon aktualisiert Panel-Objekte.
      - Senden von Befehlen: jdev/sps/io/<uuid>/<cmd>.
    """

    def __init__(self, host: str, user: str, password: str, https: bool = False):
        self.host = host
        self.user = user
        self.password = password
        self.https = https

    def connect(self) -> None:  # pragma: no cover - Stub
        raise NotImplementedError(
            "Loxone-WebSocket-Anbindung folgt in Phase 2 (Token-Auth + Binaerparsing).")
