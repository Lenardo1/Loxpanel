"""Eigene Version: Sammelkachel (tiles[uuid].mit).

Start im Repo:  python -m pytest tests/test_kachel_eigen.py"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "bin"))

import konfig  # noqa: E402
from seiten import Seiten  # noqa: E402

U1, U2, U3 = ("aaaaaaa1-0001-0001-ffff000000000001", "aaaaaaa2-0002-0002-ffff000000000002",
              "aaaaaaa3-0003-0003-ffff000000000003")


class _App(Seiten):
    def __init__(self, an):
        self.controls = {U1: {"name": "Bewohner: Anna"}, U2: {"name": "Bewohner: Ben"},
                         U3: {"name": "Bewohner: Clara"}}
        self.an = an

    def _control_item(self, uuid, prof=None, **kw):
        return {"id": uuid, "on": uuid in self.an}


def test_sammelkachel_nennt_wer_da_ist():
    it = {"on": True, "nav": {"view": "control", "id": U1}}
    _App({U1, U3})._sammelkachel(U1, [U2, U3], it)
    assert it["label"] == "Bewohner" and it["on"] is True
    assert it["sublabel"] == "Anna, Clara da"
    assert "nav" not in it


def test_sammelkachel_niemand():
    it = {"on": False}
    _App(set())._sammelkachel(U1, [U2, U3], it)
    assert it["on"] is False and it["sublabel"] == "Niemand da"


def test_konfig_mit():
    roh = {"p": {"tiles": {U1: {"mit": [U2, U3, U1, "x", 5]}}}}
    assert konfig._sanitize_panels(roh)["p"]["tiles"][U1] == {"mit": [U2, U3]}


def test_konfig_kurz():
    roh = {"p": {"tiles": {U1: {"kurz": "  Fenster  "}, U2: {"kurz": ""}, U3: {"kurz": 5}}}}
    tiles = konfig._sanitize_panels(roh)["p"]["tiles"]
    assert tiles == {U1: {"kurz": "Fenster"}}


def test_warnen_ruhig_erlaubt():
    out = konfig._sanitize_theme_ui({"warnen": {U1: "ruhig", U2: "bunt"}})
    assert out["warnen"] == {U1: "ruhig"}
