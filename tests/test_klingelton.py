"""Klingelton (Vorgaben -> Verhalten): Vorgabe speichern und Testton-Art.

Start im Repo:  python -m pytest tests/test_klingelton.py"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from aiohttp import web

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "bin"))

import konfig  # noqa: E402
from routen import geraete as R  # noqa: E402


@pytest.mark.parametrize("roh,erwartet", [
    ({"klingelTon": "app"}, {"klingelTon": "app"}),
    ({"klingelTon": "alle"}, {"klingelTon": "alle"}),
    ({"klingelTon": "laut"}, {}),
    ({"klingelTon": True}, {}),
    ({}, {}),
])
def test_vorgabe_klingelton(roh, erwartet):
    assert konfig._sanitize_theme_ui(roh) == erwartet


def test_klingelton_in_den_vorgaben_schluesseln():
    assert "klingelTon" in konfig.THEME_UI_KEYS


class _FakeApp:
    def __init__(self):
        self.conn_prof = {"ws1": {"id": "panel1"}, "ws2": {"id": "panel2"}}
        self.gesendet = []

    async def _send_or_drop(self, ws, msg):
        self.gesendet.append((ws, msg))
        return True


@pytest.fixture
async def client(aiohttp_client):
    app = web.Application()
    app["app"] = _FakeApp()
    app.router.add_post("/api/testtone", R.api_testtone)
    c = await aiohttp_client(app)
    c.fake = app["app"]
    return c


async def test_testton_klingel_an_ein_profil(client):
    r = await client.post("/api/testtone", json={"panel": "panel1", "art": "klingel"})
    assert (await r.json())["sent"] == 1
    assert client.fake.gesendet == [("ws1", {"t": "testtone", "art": "klingel"})]


async def test_testton_ohne_art_wie_bisher(client):
    r = await client.post("/api/testtone", json={})
    assert (await r.json())["sent"] == 2
    assert all(m == {"t": "testtone"} for _, m in client.fake.gesendet)
