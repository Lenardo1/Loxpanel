"""Schriftdateien der Visu (/schrift/<name>.woff2), die ein Kachel-Set mitbringt.

Start im Repo:  python -m pytest tests/test_schrift.py"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest
from aiohttp import web

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "bin"))

from routen import oberflaeche as O  # noqa: E402
from theme_colors import KACHEL_SETS  # noqa: E402

WEB = Path(__file__).resolve().parent.parent / "webfrontend" / "html"


async def _client(aiohttp_client):
    app = web.Application()
    app.router.add_get("/schrift/{name}", O.schrift)
    return await aiohttp_client(app)


async def test_schrift_wird_ausgeliefert(aiohttp_client):
    c = await _client(aiohttp_client)
    r = await c.get("/schrift/figtree-latin-400-normal.woff2")
    assert r.status == 200 and r.content_type == "font/woff2"
    assert (await r.read())[:4] == b"wOF2"


@pytest.mark.parametrize("name", ["gibtsnicht.woff2", "OFL.txt", "Figtree.woff2", "a.b.woff2", "%2e%2e%2fpanel.woff2"])
async def test_schrift_nur_eigene_woff2(aiohttp_client, name):
    c = await _client(aiohttp_client)
    assert (await c.get("/schrift/" + name)).status == 404


def test_schrift_der_sets_liegt_bei():
    """Jede @font-face-Datei aus grund.css liegt im Ordner, mit Lizenztext; die
    Schrift, die das Set loxapp nennt, ist dort auch erklaert."""
    css = (WEB / "panel" / "grund.css").read_text(encoding="utf-8")
    dateien = re.findall(r"url\(/schrift/([a-z0-9-]+\.woff2)\)", css)
    assert dateien
    for d in dateien:
        assert (WEB / "schrift" / d).is_file(), d
    assert (WEB / "schrift" / "OFL.txt").is_file()
    erste = KACHEL_SETS["loxapp"]["masse"]["--font"].split(",")[0].strip().strip('"')
    assert 'font-family:"%s"' % erste in css
