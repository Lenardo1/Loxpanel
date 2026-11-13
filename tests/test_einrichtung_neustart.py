"""Karte "Keine Verbindung zum Miniserver" nach einem Neustart des Servers.

Start im Repo:  python -m pytest tests/test_einrichtung_neustart.py"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "bin"))

import verteilung  # noqa: E402


class _App(verteilung.Verteilung):
    def __init__(self, gestartet_vor: float, fehler: str = "Timeout", host: str = "10.0.0.2"):
        self.controls = {}
        self.host = host
        self._ms_fehler = fehler
        self._gestartet = time.monotonic() - gestartet_vor


def test_fehler_gleich_nach_dem_start_zeigt_keine_karte():
    assert _App(gestartet_vor=5)._einrichtung_stand() is None


def test_fehler_nach_der_karenz_zeigt_die_karte():
    stand = _App(gestartet_vor=verteilung.EINRICHTUNG_KARENZ + 1)._einrichtung_stand()
    assert stand == ("Keine Verbindung zum Miniserver", "10.0.0.2: Timeout")


def test_ohne_miniserver_kommt_die_karte_sofort():
    assert _App(gestartet_vor=1, host="")._einrichtung_stand()[0] == "Miniserver einrichten"


def test_mit_struktur_nie_eine_karte():
    app = _App(gestartet_vor=verteilung.EINRICHTUNG_KARENZ + 1)
    app.controls = {"x": {}}
    assert app._einrichtung_stand() is None


def test_konfigurator_sieht_den_fehler_sofort():
    assert _App(gestartet_vor=1)._einrichtung_info()["stand"] == "fehler"
