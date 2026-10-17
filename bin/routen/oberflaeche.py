"""Die Dateien der Oberflaeche: die Visu (/, /panel/{name}), der Konfigurator
(/config, /config.css, /config/{name}), /settings (leitet nur weiter),
i18n.js und raster.js. Alle ohne Zwischenspeichern, damit ein Update sofort
ankommt; Namen der Teile nur nach festem Muster, sonst 404.

Die Handler holen die App aus request.app["app"]; main() in webvisu.py traegt
sie in die Routentabelle ein. Importiert webvisu nicht (App nur als Typangabe)."""
from __future__ import annotations

import logging
import re
from pathlib import Path

from aiohttp import web

from routen.gemeinsam import _NOCACHE

log = logging.getLogger("loxpanel.webvisu")   # derselbe Logger wie der Server


_WEB = Path(__file__).resolve().parents[2] / "webfrontend" / "html"   # bin/routen/ -> Repo
HTML = _WEB / "panel.html"
CONFIG_HTML = _WEB / "config.html"
SETTINGS_HTML = _WEB / "settings.html"
I18N_JS = _WEB / "i18n.js"
RASTER_JS = _WEB / "raster.js"   # Rasterrechnung fuer Visu und Konfigurator (Punkt 9)
CONFIG_CSS = _WEB / "config.css"  # Stylesheet des Konfigurators
CONFIG_JS = _WEB / "config"       # die Teile des Konfigurator-Skripts, config.html laedt sie der Reihe nach
PANEL_TEILE = _WEB / "panel"      # Stylesheets und Skriptteile der Visu, panel.html laedt sie der Reihe nach


def _web_file(path: Path, ctype: str) -> web.Response:
    """Eine der Oberflaechen-Dateien ausliefern. Fehlt sie (kaputtes Image,
    falsch gemountetes Volume), gibt es einen 404 mit Dateinamen statt eines
    Stacktrace als 500."""
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as err:
        log.error("%s nicht lesbar: %s", path, err)
        return web.Response(status=404, text=f"{path.name} fehlt im LoxPanel-Image")
    return web.Response(text=text, content_type=ctype, headers=_NOCACHE)


async def index(request: web.Request) -> web.Response:
    return _web_file(HTML, "text/html")


async def config_index(request: web.Request) -> web.Response:
    return _web_file(CONFIG_HTML, "text/html")


async def i18n_js(request: web.Request) -> web.Response:
    """Gemeinsamer Uebersetzungs-Katalog fuer /settings und /config."""
    return _web_file(I18N_JS, "application/javascript")


async def raster_js(request: web.Request) -> web.Response:
    """Gemeinsame Rasterrechnung: die Visu baut damit ihr Raster, der
    Seiten-Editor des Konfigurators zeichnet ein Geraet damit vor."""
    return _web_file(RASTER_JS, "application/javascript")


async def config_css(request: web.Request) -> web.Response:
    """Stylesheet des Konfigurators (webfrontend/html/config.css)."""
    return _web_file(CONFIG_CSS, "text/css")


_CONFIG_JS_NAME = re.compile(r"^[a-z][a-z0-9-]*\.js$")


async def config_js(request: web.Request) -> web.Response:
    """Ein Teil des Konfigurator-Skripts (webfrontend/html/config/<name>.js).
    config.html laedt die Teile in fester Reihenfolge; nur schlichte Namen,
    damit kein Pfad aus dem Ordner herausfuehrt."""
    name = request.match_info["name"]
    if not _CONFIG_JS_NAME.match(name):
        raise web.HTTPNotFound()
    return _web_file(CONFIG_JS / name, "application/javascript")


_PANEL_TEIL_NAME = re.compile(r"^[a-z][a-z0-9-]*\.(js|css)$")

_TEIL_TYPEN = {"js": "application/javascript", "css": "text/css"}


async def panel_teil(request: web.Request) -> web.Response:
    """Ein Stylesheet oder ein Teil des Visu-Skripts (webfrontend/html/panel/
    <name>.css|.js). panel.html laedt sie in fester Reihenfolge; nur schlichte
    Namen, damit kein Pfad aus dem Ordner herausfuehrt."""
    name = request.match_info["name"]
    m = _PANEL_TEIL_NAME.match(name)
    if not m:
        raise web.HTTPNotFound()
    return _web_file(PANEL_TEILE / name, _TEIL_TYPEN[m.group(1)])


async def settings_index(request: web.Request) -> web.Response:
    return _web_file(SETTINGS_HTML, "text/html")


