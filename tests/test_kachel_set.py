"""Kachel-Sets (theme_colors.KACHEL_SETS): feste Farben nachgerechnet, Aufbau
"zeile" mit eigenem Raster.

Start im Repo:  python -m pytest tests/test_kachel_set.py"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "bin"))

import theme_colors  # noqa: E402
from ansicht import Ansicht  # noqa: E402
from theme_colors import AA, AAA, GRAFIK, KACHEL_SETS, kontrast  # noqa: E402

AUFBAUTEN = {"lx", "mitte", "kreis", "zeile"}
LEISTEN = {"pille", "oben", "links", "reiter"}


class _App(Ansicht):
    def __init__(self, panels):
        self.panels = panels
        self.theme = {"ui": {}, "states": {}}
        self.rooms = {}
        self.cats = {}


@pytest.mark.parametrize("name", sorted(KACHEL_SETS))
def test_set_ist_vollstaendig(name):
    e = KACHEL_SETS[name]
    assert e["label"] and e["info"]
    assert e["aufbau"] in AUFBAUTEN and e["leiste"] in LEISTEN
    assert theme_colors.kachel_set_art(name) == (e["aufbau"], e["leiste"])
    v = theme_colors.kachel_set(name)
    for rolle in ("--bg", "--screen", "--tile", "--taste", "--tabbar", "--ink", "--muted", "--kachel-an"):
        assert v.get(rolle), rolle
    assert name in [s["key"] for s in theme_colors.kachel_set_liste()]


def test_loxapp_farben_lesbar():
    v = theme_colors.kachel_set("loxapp")
    assert kontrast(v["--ink"], v["--tile"]) >= AAA          # Zustand bzw. Name auf der Zeile
    assert kontrast(v["--muted"], v["--tile"]) >= AA         # Name darunter
    assert kontrast(v["--ink"], v["--taste"]) >= AAA         # Symbol auf der Taste
    assert kontrast(v["--ink"], v["--tabbar"]) >= AAA        # Tab in der Pille
    assert kontrast(v["--tab-an-ink"], v["--tab-an-flaeche"]) >= AAA   # aktiver Tab
    # Symbol in der Zustandsfarbe: die Farben sind die der Loxone-App, sie
    # tragen nur Symbol und Wippe, nie Schrift (Rot erreicht 4,3:1)
    for farbe in ("--glow", "--good", "--warn", "--crit"):
        assert kontrast(v[farbe], v["--tile"]) >= GRAFIK, farbe


def test_loxapp_bringt_zeilenmasse_mit():
    v = theme_colors.kachel_set("loxapp")
    for mass in ("--zeile-h", "--zeile-spalte", "--tabs-hoehe", "--pille-h", "--pille-tab-breite"):
        assert v[mass].endswith("px") and float(v[mass][:-2]) > 0, mass


def test_zeile_rechnet_das_raster_immer_selbst():
    app = _App({"default": {"ui": {}},
                "app": {"ui": {"tileSet": "loxapp"}},
                "appgross": {"ui": {"tileSet": "loxapp", "grid": "auto", "tileSize": 200}},
                "fest": {"ui": {"tileSet": "loxone"}},
                "auto": {"ui": {"tileSet": "loxone", "grid": "auto"}}})
    prof = app.resolve_profile("app")
    assert (prof["tileSetAufbau"], prof["tileSetLeiste"]) == ("zeile", "reiter")
    assert prof["gridAuto"] > 0
    assert app.resolve_profile("appgross")["gridAuto"] == 200
    assert app.resolve_profile("fest")["gridAuto"] == 0
    assert app.resolve_profile("auto")["gridAuto"] > 0
    assert app.resolve_profile("default")["gridAuto"] == 0


def test_groessen_des_sets_gehen_vor_die_vorgaben():
    app = _App({"default": {"ui": {}},
                "app": {"ui": {"tileSet": "loxapp"}},
                "eigen": {"ui": {"tileSet": "loxapp", "nameSize": 22}}})
    app.theme = {"ui": {"iconSize": 38, "nameSize": 18, "subSize": 15, "roomSize": 11}, "states": {}}
    soll = KACHEL_SETS["loxapp"]["groessen"]
    v = app.resolve_profile("app")["vars"]
    assert (v["--ico-size"], v["--name-size"], v["--sub-size"]) == \
        (f"{soll['iconSize']}px", f"{soll['nameSize']}px", f"{soll['subSize']}px")
    assert v["--room-size"] == "11px"                    # bringt das Set nicht mit: Vorgabe gilt
    v = app.resolve_profile("eigen")["vars"]
    assert v["--name-size"] == "22px"                    # an der Ansicht eingestellt
    assert v["--sub-size"] == f"{soll['subSize']}px"
    v = app.resolve_profile("default")["vars"]           # ohne Set bleibt es bei den Vorgaben
    assert (v["--ico-size"], v["--name-size"], v["--sub-size"]) == ("38px", "18px", "15px")
