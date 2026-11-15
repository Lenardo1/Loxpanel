"""Begleit-Tablets (eigene Version): Einstellungen pruefen, speichern, Meldung der App."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "bin"))
import begleiter  # noqa: E402


def test_bereinigen_standard_und_grenzen():
    d = begleiter.bereinigen({"wetter": False, "farbe": "gruen", "x": 99999, "y": -5,
                              "startPaket": "com.loxone.kerberos", "wetterQuelle": "http://10.0.0.1/plugins/weather4lox/",
                              "wetterSymbole": "javascript:alert(1)", "unbekannt": 1, "ble": "ja"})
    assert d["wetter"] is False and d["farbe"] == "gruen"
    assert d["x"] == 4000 and d["y"] == -1
    assert d["wetterQuelle"] == "http://10.0.0.1/plugins/weather4lox/"
    assert d["wetterSymbole"] == ""
    assert "unbekannt" not in d and d["ble"] is True


def test_farbe_eigen_und_falsch():
    assert begleiter.bereinigen({"farbe": "#AABBCC"})["farbe"] == "#aabbcc"
    assert begleiter.bereinigen({"farbe": "rot"})["farbe"] == "schwarz"
    assert begleiter.farbe_hex("gruen") == "#8dff70"
    assert begleiter.farbe_hex("#123456") == "#123456"


def test_paket_und_name():
    assert begleiter.bereinigen({"startPaket": "kein paket"})["startPaket"] == "com.loxone.kerberos"
    assert begleiter.name_ok("Flur UG") and not begleiter.name_ok("") and not begleiter.name_ok("a/b")


def test_melden_und_speichern(tmp_path, monkeypatch):
    monkeypatch.setattr(begleiter, "BEGLEITER_FILE", tmp_path / "begleiter.json")
    begleiter.GESEHEN.clear()
    assert begleiter.melden("Flur UG", "10.0.0.5", {"version": "1.0.2", "ist": {"wetter": True}}) is None
    begleiter.speichern({"Flur UG": begleiter.bereinigen({"farbe": "gruen", "wetter": False})})
    soll = begleiter.melden("Flur UG", "10.0.0.5", {})
    assert soll["wetter"] is False and soll["farbeHex"] == "#8dff70"
    u = begleiter.uebersicht()
    assert u["Flur UG"]["soll"]["farbe"] == "gruen" and u["Flur UG"]["gesehen"]["ip"] == "10.0.0.5"


def test_ble_schluessel_nie_zurueck(tmp_path, monkeypatch):
    monkeypatch.setattr(begleiter, "BEGLEITER_FILE", tmp_path / "begleiter.json")
    begleiter.GESEHEN.clear()
    alt = begleiter.bereinigen({"bleName": "Flur UG", "bleSchluessel": "ABCDEF0123"})
    assert alt["bleSchluessel"] == "abcdef0123"
    begleiter.speichern({"Flur UG": alt})
    u = begleiter.uebersicht()["Flur UG"]["soll"]
    assert u["bleSchluessel"] == "" and u["bleSchluesselGesetzt"] is True
    # leeres Feld beim Speichern behaelt den Schluessel, die App bekommt ihn
    neu = begleiter.zusammenfuehren(alt, begleiter.bereinigen({"bleName": "Flur UG", "bleSchluessel": ""}))
    assert neu["bleSchluessel"] == "abcdef0123"
    assert begleiter.melden("Flur UG", "10.0.0.5", {})["bleSchluessel"] == "abcdef0123"
    assert begleiter.bereinigen({"bleSchluessel": "kein hex!"})["bleSchluessel"] == ""
