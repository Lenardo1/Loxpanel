"""Kachel direkt schalten: Licht-Tipp, Tor direkt, Schutz (1 s halten).

Start im Repo:  python -m pytest tests/test_kachel_direkt.py"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "bin"))

import konfig  # noqa: E402
from seiten import Seiten  # noqa: E402


class _App(Seiten):
    def __init__(self, zustaende=None):
        self.zustaende = zustaende or {}

    def _state(self, c, name):
        return self.zustaende.get(name)


def _prof(**ov):
    return {"tiles": {"u1": ov}}


LICHT = {"uuidAction": "ua-licht", "type": "LightControllerV2"}
TOR = {"uuidAction": "ua-tor", "type": "Gate"}


def test_ohne_einstellung_bleibt_alles():
    it = {"on": True, "nav": {"view": "control", "id": "u1"}}
    _App()._kachel_direkt("u1", LICHT, "LightControllerV2", it, {})
    assert it == {"on": True, "nav": {"view": "control", "id": "u1"}}


@pytest.mark.parametrize("an,erwartet", [(False, "changeTo/5"), (True, "changeTo/778")])
def test_licht_tipp(an, erwartet):
    it = {"on": an}
    _App()._kachel_direkt("u1", LICHT, "LightControllerV2", it, _prof(lichtTipp=5))
    assert it["tipp"] == {"uuid": "ua-licht", "cmd": erwartet}


@pytest.mark.parametrize("an,fahrt,erwartet", [
    (False, 0, "open"), (True, 0, "close"), (True, 1, "stop"), (False, -1, "stop"),
])
def test_tor_direkt(an, fahrt, erwartet):
    it = {"on": an, "nav": {"view": "control", "id": "u1"}}
    _App({"active": fahrt})._kachel_direkt("u1", TOR, "Gate", it, _prof(direkt=True))
    assert it["cmd"] == {"uuid": "ua-tor", "cmd": erwartet}
    assert "nav" not in it


def test_schutz_nur_mit_befehl():
    it = {"cmd": {"uuid": "x", "cmd": "pulse"}}
    _App()._kachel_direkt("u1", {}, "Pushbutton", it, _prof(lang=True))
    assert it["lang"] is True
    it = {"nav": {"view": "control", "id": "u1"}}
    _App()._kachel_direkt("u1", {}, "Pushbutton", it, _prof(lang=True))
    assert "lang" not in it


def test_konfig_prueft_werte():
    roh = {"p": {"tiles": {
        "a": {"lichtTipp": 5, "direkt": True, "lang": True},
        "b": {"lichtTipp": True, "direkt": "ja", "lang": 1},
        "c": {"lichtTipp": 1000},
    }}}
    tiles = konfig._sanitize_panels(roh)["p"].get("tiles", {})
    assert tiles.get("a") == {"lichtTipp": 5, "direkt": True, "lang": True}
    assert "b" not in tiles and "c" not in tiles
