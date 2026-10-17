#!/usr/bin/env python3
"""LoxPanel Live-Web-Visu (Phase 3) — Navigations-Shell.

Baut die Loxone-App-Navigation nach, aber aufgeraeumt fuers 480x480-Panel:
kompakter Kopf (Titel + Uhr), 2x2-Kacheln, unten 4 Tabs
(Favoriten / Zentral / Raeume / Kategorien). Licht ist voll ausgebaut:
Kategorie/Raum/Zentral -> Raum-Lichtcontroller -> Stimmungen.

Client<->Server (WebSocket, JSON):
  Client: {t:'nav', route:{...}}     Server: {t:'view', ...}
  Client: {t:'cmd', uuid, cmd}

Aufbau: Hier stehen die Klasse App (Felder, Hintergrundaufgaben, Schliessen),
Start und Logging und main() mit der Routentabelle. Ihre Themen erbt App als
Mixins aus eigenen Modulen (miniserver.py, geraete.py, seiten.py ...), die
Routen-Handler liegen je Thema in routen/. docs/ARCHITEKTUR.md 3.3 und 4.

Start:  python webvisu.py   ->  http://localhost:8099
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
import time
from pathlib import Path

import aiohttp
from aiohttp import web

sys.path.insert(0, str(Path(__file__).resolve().parent))
from loxone_api import LoxoneClient  # noqa: E402
from loxone_ws import LoxoneWS  # noqa: E402
from audioserver import make_backend, AudioBackend  # noqa: E402
from audioserver_events import AudioEventClient  # noqa: E402
import front_info  # noqa: E402  # Kalender (iCal-Abos) + Wetter (Open-Meteo) fuer die Front
import loxone_secure  # noqa: E402  # verschluesselte Befehle (gesicherte Details der Intercom)
import audioserver_auth  # noqa: E402  # Audioserver-Anmeldung; hier nur HAVE_CRYPTO (_fehlende_pakete_melden)
from intercom_talk import IntercomTalk  # noqa: E402
import diagnose  # noqa: E402  # Diagnosepaket (/api/diagnose) und Log-Puffer
import konfig  # noqa: E402  # Konfigdateien: Pfade, Laden, Pruefen, Schreiben
from konfig import (  # noqa: E402  # Konfigdateien: Pfade, Laden, Pruefen, Schreiben
    _audio_config, _audiometa_config, _calendar_config, _config, _intercom_config, load_panels_doc,
    load_theme, _night_config)
# App setzt sich aus Mixins zusammen, je Thema ein Modul (Reihenfolge wie die Basisklassen).
from statistik import Statistik  # noqa: E402  # Verlaeufe (Statistik-Dateien)
from bausteine import BausteinHelfer  # noqa: E402  # Helfer der Bausteine
from haus import Haus  # noqa: E402  # Hausuebersicht
from gesten import Gesten  # noqa: E402  # Gesten der Visu
from miniserver import Miniserver  # noqa: E402  # Verbindung, Struktur, Befehle
from geraete import Geraete  # noqa: E402  # Geraete, Agenten, Display
from audiodienst import Audiodienst  # noqa: E402  # Audioserver, Cover, Favoriten
from intercomdienst import Intercomdienst  # noqa: E402  # SIP-Zugang, Kamera, Kamera-Pane
from front import Front  # noqa: E402  # Kalender und Wetter der Uhr-Seite
from verteilung import Verteilung  # noqa: E402  # Senden an die Browser
from medien import Medien  # noqa: E402  # Icons, Cover, Klingelbilder
from diagnosedaten import Diagnosedaten  # noqa: E402  # Diagnose und /api/types
from ansicht import Ansicht  # noqa: E402  # Profil, Theme, Export
from seiten import Seiten  # noqa: E402  # Seiten, Kacheln, Detailseiten
# Routen-Handler je Thema (routen/); main() traegt sie unten in die Routentabelle ein.
from routen.oberflaeche import (  # noqa: E402
    config_css, config_index, config_js, i18n_js, index, panel_teil, raster_js, settings_index)
from routen.visu import ws_handler  # noqa: E402
from routen.konfigurator import (  # noqa: E402
    api_entwurf, api_kachelset, api_meta, api_save_panels, api_save_theme, api_types)
from routen.einstellungen import (  # noqa: E402
    api_backup, api_restore, api_settings, api_settings_audiometa, api_settings_calendar, api_settings_ms,
    api_settings_night)
from routen.intercom import (  # noqa: E402
    api_intercom_talk_start, api_intercom_talk_status, api_intercom_talk_stop, api_settings_intercom, api_sip,
    api_sip_pruefen, mjpeg_handler)
from routen.geraete import (  # noqa: E402
    api_agent_announce, api_agent_command, api_agents, api_device_name, api_device_switch, api_devices_get,
    api_display, api_goto, api_mode, api_notify, api_reload, api_save_devices, api_testtone,
    api_vorschau_beenden, install_script)
from routen.medien import bellimg_handler, cover_handler, icon_handler, loxicons_handler, loxlib_handler  # noqa: E402
from routen.system import api_diagnose, api_health  # noqa: E402

log = logging.getLogger("loxpanel.webvisu")


class App(Statistik, BausteinHelfer, Haus, Gesten, Miniserver,
          Geraete, Audiodienst, Intercomdienst, Front, Verteilung, Medien, Diagnosedaten, Ansicht, Seiten):
    # Pruefen und Exportieren der Konfiguration liegt in konfig.py; hier als
    # statische Methoden erreichbar, weil Server, Sicherung und Tests sie so rufen.
    _sanitize_panels = staticmethod(konfig._sanitize_panels)
    _panels_verworfen = staticmethod(konfig._panels_verworfen)
    _panels_doc = staticmethod(konfig._panels_doc)
    _sanitize_devices = staticmethod(konfig._sanitize_devices)
    _sanitize_display = staticmethod(konfig._sanitize_display)
    _devices_export = staticmethod(konfig._devices_export)
    _sanitize_theme_ui = staticmethod(konfig._sanitize_theme_ui)
    _sanitize_categories = staticmethod(konfig._sanitize_categories)

    def __init__(self, ms: dict, audio: dict | None = None,
                 audiometa: dict | None = None):
        # ms kann leer sein (noch kein Miniserver konfiguriert) -> Server startet
        # trotzdem, /settings bleibt bedienbar; verbunden wird erst mit host.
        self.host, self.port = ms.get("host", ""), ms.get("port", 443)
        self.user, self.password = ms.get("user", ""), ms.get("pass", "")
        self.verify_tls = ms.get("verify_tls", False)
        # Einrichtungshinweis an die Panels (_einrichtung_stand): letzter Fehler
        # beim Verbinden mit dem Miniserver, und welcher Stand zuletzt rausging.
        self._ms_fehler = ""
        self._einrichtung_gemeldet: tuple | None = None
        # Verbindungszustand (_verbindung_stand): seit wann der Miniserver weg
        # ist (Unix-Sekunden, None = verbunden oder noch nie versucht), wann er
        # zuletzt etwas schickte, was zuletzt an die Panels ging und wann.
        self._ms_weg_seit: float | None = None
        self._ms_bestaetigt: float | None = None
        self._ms_verbunden_seit: float | None = None   # Datenstrom laeuft seit (Diagnose)
        self._verbindung_gemeldet: tuple | None = None
        self._verbindung_zuletzt = 0.0

        self.audio_cfg = audio or {}
        self.audio: AudioBackend | None = make_backend(self.audio_cfg)
        # Ein Steuerungs-Backend je Audioserver-Host (WS 7091), aufgebaut on
        # demand aus dem in der Struktur hinterlegten mediaServer-Host.
        self.audio_backends: dict[str, AudioBackend] = {}
        # Gen-2-Audioserver-Metadaten (universeller audio_event-Kanal, Port 7091):
        # Adressen werden AUTOMATISCH aus der Loxone-Struktur (/mediaServer/<uuid>
        # /host) gelesen; pro Audioserver ein Event-Client. Zonen-Zuordnung ueber
        # control.details.server (-> host) + details.playerid. Funktioniert mit
        # Original-Audioserver, Sonn und jedem Nachbau, ohne IP-Eingabe.
        self.audiometa_cfg = audiometa or {}
        self.mediaservers: dict[str, str] = {}          # serverUUID -> "host:port"
        self.audio_clients: dict[str, AudioEventClient] = {}  # host -> Client
        # uuidAction -> Loxone-playerid (fuer Audioserver-Kommandos)
        self.playerid_by_action: dict[str, int] = {}
        # uuidAction -> Audioserver-Host (aus mediaServer der Struktur). So
        # steht der Host auch fest, wenn nichts spielt (kein Cover zum Ableiten).
        self.audiohost_by_action: dict[str, str] = {}

        self.client: LoxoneClient | None = None
        self.ws: LoxoneWS | None = None
        self.states: dict[str, object] = {}
        self.controls: dict = {}
        self.rooms: dict = {}
        self.cats: dict = {}
        self.rooms_with: list[str] = []
        self.cats_with: list[str] = []
        self.conn_route: dict[web.WebSocketResponse, dict] = {}
        self.conn_prof: dict[web.WebSocketResponse, dict] = {}
        self.conn_dev: dict[web.WebSocketResponse, str] = {}   # ws -> Geraetename (?device=)
        self.conn_info: dict[web.WebSocketResponse, dict] = {}  # ws -> {dev, kiosk, ip, ts} (Geraeteverwaltung)
        self._drv_session: aiohttp.ClientSession | None = None   # HTTP-Session fuer Display-Treiber (Kiosk-Apps)
        self.conn_player: dict[web.WebSocketResponse, str] = {}   # ws -> AudioZone-UUID der aktiven Player-Pane (via setplayer)
        self.conn_energy: dict[web.WebSocketResponse, str] = {}   # ws -> EFM/EnergyManager2-UUID der aktiven Energiefluss-Pane (via setenergy)
        self.conn_camera: dict[web.WebSocketResponse, str] = {}   # ws -> Intercom-UUID der aktiven Kamera-Pane (via setcamera)
        self.conn_status: dict[web.WebSocketResponse, tuple] = {}  # ws -> UUIDs der Status-Kacheln auf der Uhr-Seite (via setsvstatus)
        self.conn_chart: dict[web.WebSocketResponse, tuple[tuple[str, ...], str]] = {}   # ws -> (Baustein-UUIDs, Zeitraum) der Verlaufs-Pane (via setchart)
        self.conn_geste: dict[web.WebSocketResponse, dict] = {}   # ws -> laufende Geste (Dimmen, Lautstaerke), App.geste()
        # Profile und Geraete aus derselben Datei, einmal gelesen
        # (Geraete: Agent-Name -> {panel, auto, modes:{modus:profil}, display ...})
        self.panels, self.devices = load_panels_doc()
        self.entwuerfe: dict[str, dict] = {}   # Token -> {id, panel (gesaeubert), ts}, nur im Speicher
        # Geraet -> {token, id, zurueck (Profil davor), bis}: zeigt gerade einen Entwurf (Punkt 12)
        self.vorschau_geraet: dict[str, dict] = {}
        # ... beendet, als keine Verbindung des Geraets den Entwurf zeigte (es lud gerade neu
        # oder war offline): Geraet -> {token, zurueck}. Gilt, bis es mit dem Token wiederkommt
        self.vorschau_ende: dict[str, dict] = {}
        self.last_mode = ""             # zuletzt gesetzter Betriebsmodus (fuer Nachziehen beim Verbinden)
        # Geraete, deren Ansicht unter Displays ausdruecklich gewaehlt wurde: der
        # Betriebsmodus zieht sie beim Verbinden nicht um, bis er neu wechselt.
        self.ansicht_gewaehlt: set[str] = set()
        self._struct_sig: str | None = None   # Signatur der Loxone-Struktur (erkennt Config-Aenderungen)
        self._pending_reload = False          # -> Panels beim naechsten Tick neu laden ({t:"reload"})
        self.global_states: dict = {}   # globale States der Anlage (Name -> UUID), s. _apply_structure
        self.op_modes: dict = {}        # Betriebsarten der Anlage (Id -> Name), s. _apply_structure
        self._night_on = False          # Nachtmodus aktiv? (-> {t:"night"} an die Panels)
        self.night_cfg = _night_config()  # {"control": uuid} -> dessen active-State = Nacht
        self._dirty = True
        # Zuletzt an JEDE Verbindung zugestellte Nutzlast, je Art getrennt
        # ({"view":…, "player":…, "energy":…}). Grundlage dafuer, unveraenderte
        # Ansichten gar nicht erst zu senden. Eingetragen wird ausschliesslich
        # NACH erfolgreichem Senden - ein abgebrochener Versuch darf nie als
        # zugestellt gelten.
        self._last_sent: dict = {}
        # Nur rendern, was betroffen ist (verteilung.py): die seit dem letzten
        # Tick geaenderten States (_on_value) und je Verbindung, welche States ihr
        # letztes Rendern gelesen hat, fuer welche Seite und wann
        self._geaendert: set[str] = set()
        self._render_spur: dict = {}
        self.jwt: str | None = None
        self.alg: str = "SHA1"
        self._ms_pubkey = None           # RSA-Schluessel des Miniservers fuer verschluesselte Befehle
        # Kamera je Intercom aus den gesicherten Details (intercom_video): {"url",
        # "user", "pass"} oder {"grund"}; gilt bis zur naechsten Struktur
        self.ms_video: dict[str, dict] = {}
        self._video_sperre = asyncio.Lock()
        self._auth_gen = 0               # zaehlt jede Anmeldung (-> _renew_token)
        self._auth_at = 0.0              # monotonic der letzten Anmeldung
        self._auth_lock = asyncio.Lock()
        self.icon_session: aiohttp.ClientSession | None = None
        self.icon_cache: dict[str, tuple[bytes, str]] = {}
        self.bell_cache: dict[str, tuple[bytes, str]] = {}   # camimage-Pfad -> (Bild, Typ)
        # Verlaufsdaten: (uuidAction, "JJJJMM") -> (monotonic, JJJJMM beim Abruf,
        # [(sekunden, [werte])] oder None nach Abruffehler). Ein Monat, der beim
        # Abruf schon vorbei war, aendert sich nicht mehr.
        self.stat_cache: dict[tuple[str, str], tuple[float, str, list | None]] = {}
        self.stat_pending: set[tuple] = set()
        # statisticV2 (Energie-Zaehler): (uuidAction, Gruppe, Ausgang, Zeitraum) ->
        # (monotonic, [(sekunden, [wert])] oder None nach Abruffehler). Hoechstens
        # zwei Abrufe gleichzeitig; die Loxone-App erlaubt 4 (Gen 2) bzw. 1 (Gen 1).
        self.stat2_cache: dict[tuple, tuple[float, list | None]] = {}
        self.stat2_sem = asyncio.Semaphore(2)
        self.stat_gen = 0              # zaehlt jeden Abruf, Schluessel fuer stat_memo
        self.stat_memo: dict[tuple, list] = {}
        self.theme = load_theme()
        self._cat_memo: tuple = (None, {})   # _cat_entry: (categories-Objekt, Name -> Eintrag)
        self._einspiel_sperre = asyncio.Lock()   # /api/restore: nur ein Einspielen zur Zeit
        # Miniserver-Zugang pruefen und speichern (api_settings_ms, auch beim
        # Einspielen) nur nacheinander, sonst laufen Datei und Verbindung
        # auseinander. _zugang_neu: gespeichert, aber beim Pruefen nicht
        # erreichbar - stream_task verbindet beim naechsten Aufbau damit.
        self._zugang_sperre = asyncio.Lock()
        self._zugang_neu: dict | None = None
        self.intercom_cfg = _intercom_config()
        self.intercom_talk = IntercomTalk(self._talk_credentials)
        # Front (Screensaver): Kalender + Wetter. front_task() laedt periodisch,
        # _front ist die zuletzt gebaute Nachricht ({"t":"front",...}), _front_key
        # ihr Abbild zum Vergleich (nur bei Aenderung neu senden), _front_meta der
        # Status fuer die Config-Seite. _front_refresh weckt front_task (nach dem
        # Speichern und bei neuem Wetter vom Miniserver).
        self.calendar_cfg = _calendar_config()
        # Loxone-Wetterserver: Konfiguration aus der Struktur, Rohdaten je
        # State-UUID (kommen ueber den WS als eigene Tabelle) und die zuletzt
        # tatsaechlich verwendete Quelle fuer die Diagnose.
        self.weather_cfg: dict = {}
        self._lox_wx: dict[str, list] = {}
        self._wx_source: str = "open-meteo"
        # Standort des Miniservers (aus msInfo) als Wetter-Fallback ohne Konfiguration.
        self.ms_lat: float | None = None
        self.ms_lon: float | None = None
        self.ms_location: str = ""
        self.ms_struktur: dict = {}   # msInfo fuer das Diagnosepaket (_apply_structure)
        self._front: dict | None = None
        self._front_key: str | None = None
        self._front_meta: dict = {}
        # Letzter erfolgreich geladener Stand je Teil (Feiertage, Wetter) plus
        # dessen Uhrzeit. Ueberbrueckt Aussetzer der Quellen, siehe _front_keep().
        self._front_good: dict = {}
        # Dasselbe fuer die Termine, aber JE KALENDER: {Quellenschluessel ->
        # {"events": [...], "zeit": "HH:MM"}}. Mit mehreren Abos reicht ein
        # gemeinsamer Stand nicht — faellt iCloud aus und Google liefert, waere
        # die Terminliste nicht leer und der alte Stand (mit den iCloud-
        # Terminen darin) wuerde ueberschrieben.
        self._front_good_cal: dict = {}
        self._front_dirty = False
        self._front_refresh = asyncio.Event()
        # Letzter fertig gebauter Front-Stand (nach _front_keep) und ab wann der
        # Kalender wieder aus dem Netz geholt wird (time.monotonic(), 0 = sofort).
        # Ein Wetter-Push des Miniservers baut die Front aus diesem Stand neu und
        # ruft KEINEN Kalender ab, siehe front_task().
        self._front_last: dict | None = None
        self._front_cal_due = 0.0
        self._front_session: aiohttp.ClientSession | None = None
        # Gesperrte Bausteine (jLocked): Befehlsempfaenger (Baustein, uuidAction,
        # Unterbaustein) -> State-UUID von jLocked, die fuer ihn gilt
        self.sperre_state: dict[str, str] = {}
        self.bell_map: dict[str, str] = {}
        self._bell_prev: dict[str, object] = {}
        self._pending_ring: str | None = None
        # Wecker (AlarmClock): isAlarmActive-State-UUID -> Control-UUID. Flanke
        # 0->1/1->0 wird als {"t":"alarm",...} ans Panel gepusht (Weckton an/aus).
        self.alarm_map: dict[str, str] = {}
        self._alarm_prev: dict[str, object] = {}
        self._pending_alarm: list[dict] = []
        # Praesenzmelder je Geraet (devices[name].presence = Control-UUID): solange
        # sein active-State jemanden meldet, bleibt das Display des Geraets an.
        # State-UUID -> Geraete, Stand je Geraet, offene Meldungen an die Panels
        # (verteilt in _broadcast_tick).
        self.presence_map: dict[str, list[str]] = {}
        self._presence_on: dict[str, bool] = {}
        self._pending_presence: list[dict] = []
        self._presence_quelle: tuple = (None, None)   # (devices, controls) hinter presence_map
        self.agents: dict[str, dict] = {}   # ip -> Panel-Agent (Fernstart)
        # ip -> Profil, das ein Agent mit seiner naechsten Meldung uebernehmen
        # soll (Displays, Betriebsmodus); faellt weg, sobald er es meldet
        self.agent_wunsch: dict[str, str] = {}
        self.bg_tasks: set = set()          # laufende Hintergrund-Tasks (z.B. Favs anfordern)
        # Dynamisches Song-Cover (iTunes) fuer Zonen, die nur ein Sender-Logo
        # liefern (z.B. Sonn/Audioserver): "artist\ntitle" -> (url|None, expiry).
        self._cover_cache: dict[str, tuple[str | None, float]] = {}
        self._cover_pending: set[str] = set()
        # Spieler der Hausseite: wann die Favoriten je Zone zuletzt angefordert
        # wurden (_haus_sender_anfordern)
        self._haus_sender_zeit: dict[str, float] = {}

    def _spawn(self, coro) -> None:
        """Hintergrund-Task starten und sauber referenziert halten."""
        task = asyncio.ensure_future(coro)
        self.bg_tasks.add(task)
        task.add_done_callback(self.bg_tasks.discard)

        # vorschau_ende bleibt: eine schon beendete Vorschau kehrt weiter zur Ansicht davor zurueck

    async def close(self) -> None:
        await self.intercom_talk.close()
        if self.ws:
            await self.ws.close()
        if self.icon_session:
            await self.icon_session.close()
        if self.client:
            await self.client.close()
        if self.audio:
            await self.audio.close()
        for be in list(self.audio_backends.values()):
            await be.close()
        self.audio_backends.clear()
        for cl in list(self.audio_clients.values()):
            await cl.close()
        self.audio_clients.clear()


# ---- Sicherung einspielen (POST /api/restore) ----
# Ablauf: ZIP lesen (_sicherung_lesen), alles pruefen und vorbereiten, ohne zu
# schreiben (_sicherung_pruefen), erst dann schreiben und den laufenden Server
# auffrischen (_sicherung_schreiben). Eine Sicherung kommt auch von einem
# anderen Server oder aus einer Hand-Bearbeitung; was der Server nicht
# verkraftet, wird deshalb vorher abgelehnt statt geschrieben.


async def on_startup(a: web.Application) -> None:
    # HTTP-Server startet SOFORT; die Miniserver-Verbindung baut stream_task im
    # Hintergrund auf (mit Retry) — so ist /settings auch ohne/mit falschen
    # Zugangsdaten erreichbar.
    app: App = a["app"]
    # Benannt, damit /api/health melden kann, welche Aufgabe nicht mehr laeuft.
    # Nur Aufgaben, die nie planmaessig enden: Sonst meldet /api/health 503, und
    # der Waechter der LoxPanel-App startet sie immer wieder neu.
    a["tasks"] = {"miniserver": asyncio.create_task(app.stream_task()),
                  "broadcaster": asyncio.create_task(app.broadcaster()),
                  "audio": asyncio.create_task(app.audio_events_task()),
                  "front": asyncio.create_task(app.front_task())}
    a["started"] = time.monotonic()


async def on_cleanup(a: web.Application) -> None:
    for t in a.get("tasks", {}).values():
        t.cancel()
    sess = a["app"]._drv_session
    if sess is not None and not sess.closed:
        await sess.close()
    await a["app"].close()


def _log_level() -> tuple[int, str | None]:
    """LOXPANEL_LOG_LEVEL (DEBUG, INFO, WARNING, ERROR) -> (Level, Warnung)."""
    roh = os.environ.get("LOXPANEL_LOG_LEVEL", "").strip()
    if not roh:
        return logging.INFO, None
    level = logging.getLevelName(roh.upper())
    if isinstance(level, int):
        return level, None
    return logging.INFO, f"LOXPANEL_LOG_LEVEL={roh!r} unbekannt (DEBUG, INFO, WARNING, ERROR) - INFO gilt"


def _logging_einrichten() -> int:
    """Log-Level aus LOXPANEL_LOG_LEVEL setzen -> Level. Der Zugriffs-Log von
    aiohttp (eine Zeile je HTTP-Anfrage, auch jedes Icon) nur bei DEBUG."""
    level, warnung = _log_level()
    logging.basicConfig(level=level, format="%(levelname)s %(name)s: %(message)s")
    logging.getLogger().setLevel(level)
    # die letzten Zeilen auch im Speicher, fuer das Diagnosepaket
    if diagnose.LOG not in logging.getLogger().handlers:
        logging.getLogger().addHandler(diagnose.LOG)
    logging.getLogger("aiohttp.access").setLevel(logging.DEBUG if level <= logging.DEBUG else logging.WARNING)
    if warnung:
        log.warning(warnung)
    return level


def _fehlende_pakete_melden() -> None:
    """Einmal beim Start: welche optionalen Pakete aus requirements.txt fehlen
    und was dadurch nicht geht. Ohne sie laeuft der Server weiter und meldet
    sich gesund (/api/health); auffallen wuerde es sonst erst am Kalender, an
    der Intercom oder am Audioserver."""
    fehlt: dict[str, list[str]] = {}
    for da, paket, funktion in (
            (front_info.HAVE_ICAL, "icalendar", "Kalender der Front"),
            (front_info.HAVE_RRULE, "python-dateutil", "Serientermine im Kalender"),
            (loxone_secure.HAVE_CRYPTO, "cryptography", "gesicherte Details der Intercom (SIP-Zugang)"),
            (audioserver_auth.HAVE_CRYPTO, "cryptography", "Anmeldung am Audioserver (Favoriten, Steuerung)")):
        if not da:
            fehlt.setdefault(paket, []).append(funktion)
    if fehlt:
        log.warning("Pakete aus requirements.txt fehlen (pip install -r requirements.txt) - %s",
                    "; ".join(f"ohne {paket}: {', '.join(f)}" for paket, f in fehlt.items()))


def main() -> None:
    _logging_einrichten()
    _fehlende_pakete_melden()
    p = argparse.ArgumentParser()
    p.add_argument("--port", type=int, default=int(os.environ.get("LOXPANEL_PORT", "8099")))
    args = p.parse_args()

    a = web.Application()
    a["app"] = App(_config(), _audio_config(), _audiometa_config())
    a.router.add_get("/", index)
    a.router.add_get("/config", config_index)
    a.router.add_get("/settings", settings_index)
    a.router.add_get("/i18n.js", i18n_js)
    a.router.add_get("/raster.js", raster_js)
    a.router.add_get("/config.css", config_css)
    a.router.add_get("/config/{name}", config_js)
    a.router.add_get("/panel/{name}", panel_teil)
    a.router.add_get("/install-agent.sh", install_script)
    a.router.add_get("/api/meta", api_meta)
    a.router.add_get("/api/kachelset", api_kachelset)
    a.router.add_post("/api/panels", api_save_panels)
    a.router.add_post("/api/entwurf", api_entwurf)
    a.router.add_post("/api/theme", api_save_theme)
    a.router.add_get("/api/settings", api_settings)
    a.router.add_get("/api/health", api_health)
    a.router.add_get("/api/backup", api_backup)
    a.router.add_get("/api/diagnose", api_diagnose)
    a.router.add_post("/api/restore", api_restore)
    a.router.add_get("/api/types", api_types)
    a.router.add_post("/api/settings/miniserver", api_settings_ms)
    a.router.add_post("/api/settings/intercom", api_settings_intercom)
    a.router.add_get("/api/sip", api_sip)
    a.router.add_post("/api/sip/pruefen", api_sip_pruefen)
    a.router.add_post("/api/intercom/talk/start", api_intercom_talk_start)
    a.router.add_get("/api/intercom/talk/status", api_intercom_talk_status)
    a.router.add_post("/api/intercom/talk/stop", api_intercom_talk_stop)
    a.router.add_post("/api/settings/night", api_settings_night)
    a.router.add_post("/api/settings/audiometa", api_settings_audiometa)
    a.router.add_post("/api/settings/calendar", api_settings_calendar)
    a.router.add_post("/api/agent/announce", api_agent_announce)
    a.router.add_get("/api/agents", api_agents)
    a.router.add_post("/api/agent/command", api_agent_command)
    a.router.add_post("/api/devices", api_save_devices)
    a.router.add_get("/api/devices", api_devices_get)
    a.router.add_post("/api/device/switch", api_device_switch)
    a.router.add_post("/api/vorschau/beenden", api_vorschau_beenden)
    a.router.add_post("/api/device/name", api_device_name)
    a.router.add_get("/api/display", api_display)
    a.router.add_post("/api/display", api_display)
    a.router.add_get("/api/mode", api_mode)
    a.router.add_post("/api/mode", api_mode)
    a.router.add_get("/api/mode/{mode}", api_mode)
    a.router.add_post("/api/mode/{mode}", api_mode)
    a.router.add_post("/api/testtone", api_testtone)
    a.router.add_get("/api/reload", api_reload)
    a.router.add_post("/api/reload", api_reload)
    a.router.add_get("/api/goto", api_goto)
    a.router.add_post("/api/goto", api_goto)
    a.router.add_get("/api/notify", api_notify)
    a.router.add_post("/api/notify", api_notify)
    a.router.add_get("/icon", icon_handler)
    a.router.add_get("/loxlib", loxlib_handler)
    a.router.add_get("/api/loxicons", loxicons_handler)
    a.router.add_get("/cover", cover_handler)
    a.router.add_get("/bellimg", bellimg_handler)
    a.router.add_get("/mjpeg", mjpeg_handler)
    a.router.add_get("/ws", ws_handler)
    a.on_startup.append(on_startup)
    a.on_cleanup.append(on_cleanup)
    web.run_app(a, host="0.0.0.0", port=args.port)


if __name__ == "__main__":
    main()
