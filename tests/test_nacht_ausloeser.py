"""Nacht mit mehreren Ausloesern (Vorgaben -> Verhalten -> Nacht).

Start im Repo:  python -m pytest tests/test_nacht_ausloeser.py"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "bin"))

import konfig  # noqa: E402
from geraete import Geraete  # noqa: E402


def test_night_controls():
    assert konfig.night_controls({"control": "a"}) == ["a"]
    assert konfig.night_controls({"control": "a, b,,c"}) == ["a", "b", "c"]
    assert konfig.night_controls({}) == []
    assert konfig.night_controls(None) == []


class _App(Geraete):
    def __init__(self, control, aktiv):
        self.night_cfg = {"control": control}
        self.controls = {u: {"uuid": u} for u in ("abwesend", "schlafen", "tiefschlaf")}
        self._aktiv = aktiv

    def _state(self, c, name):
        return 1 if c["uuid"] in self._aktiv else 0

    def _sun_minutes(self):
        return (0, 24 * 60)   # Sonne: nie Nacht, damit nur die Ausloeser zaehlen


def test_nacht_sobald_einer_an_ist():
    liste = "abwesend,schlafen,tiefschlaf"
    assert not _App(liste, set())._night_now()
    assert _App(liste, {"schlafen"})._night_now()
    assert _App(liste, {"tiefschlaf", "abwesend"})._night_now()


def test_einzelner_ausloeser_wie_bisher():
    assert _App("schlafen", {"schlafen"})._night_now()
    assert not _App("schlafen", {"abwesend"})._night_now()


def test_unbekannte_ausloeser_fallen_auf_sonne_zurueck():
    assert not _App("weg1,weg2", {"weg1"})._night_now()
