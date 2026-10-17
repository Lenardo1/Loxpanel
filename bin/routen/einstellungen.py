"""Rubrik Einstellungen: /api/settings lesen, den Miniserver-Zugang pruefen und
speichern (/api/settings/miniserver), Nacht, Audioserver-Metadaten und
Kalender speichern, die Sicherung herunterladen und einspielen (/api/backup,
/api/restore; die Arbeit macht sicherung.py).

Die Handler holen die App aus request.app["app"]; main() in webvisu.py traegt
sie in die Routentabelle ein. Importiert webvisu nicht (App nur als Typangabe)."""
from __future__ import annotations

import asyncio
import copy
import logging
from datetime import datetime
from types import SimpleNamespace
from typing import TYPE_CHECKING

import aiohttp
from aiohttp import web

import front_info
from bausteine.gemeinsam import _clean, INTERCOM_TYPES
from diagnosedaten import VERSION
from konfig import (
    _audiometa_config, _calendar_config, _CFGDIR, _config, _load_cfg, _ms_zugang, _night_config,
    _write_cfg)
from miniserver import _ms_unerreichbar
from routen.gemeinsam import _NOCACHE
from sicherung import _backup_zip, _sicherung_lesen, _sicherung_pruefen, _sicherung_schreiben

if TYPE_CHECKING:   # nur fuer die Typangabe, kein Import zur Laufzeit (webvisu importiert hierher)
    from webvisu import App

log = logging.getLogger("loxpanel.webvisu")   # derselbe Logger wie der Server


async def api_backup(request: web.Request) -> web.Response:
    """Einstellungen als ZIP herunterladen (Settings -> Sicherung)."""
    name = f"loxpanel-einstellungen-{datetime.now():%Y-%m-%d_%H%M}.zip"
    return web.Response(body=_backup_zip(_CFGDIR), content_type="application/zip",
                        headers={**_NOCACHE, "Content-Disposition": f'attachment; filename="{name}"'})


async def api_restore(request: web.Request) -> web.Response:
    """Sicherung einspielen (Settings -> Sicherung): Body = ZIP aus /api/backup."""
    app: App = request.app["app"]
    try:
        daten = await request.read()
    except web.HTTPRequestEntityTooLarge:
        return web.json_response({"ok": False, "error": "Die Datei ist zu groß für eine LoxPanel-Sicherung."},
                                 status=413)
    if not daten:
        return web.json_response({"ok": False, "error": "Keine Datei erhalten."}, status=400)
    async with app._einspiel_sperre, app._zugang_sperre:
        # _zugang_sperre: Der Plan merkt sich den bisherigen Miniserver-Zugang
        # (ms_alt) und schreibt ihn bei Bedarf zurueck - kein Speichern dazwischen.
        # Lesen und Pruefen kosten bei grossen Sicherungen Sekunden Rechenzeit
        # (Grundfarben je Profil, Sanitizer, Groessenpruefung); im Thread bleibt
        # die Visu derweil bedienbar. Der Thread sieht vom laufenden Server nur
        # eine Momentaufnahme der Bausteinnamen und Geraete.
        stand = SimpleNamespace(controls=dict(app.controls), devices=copy.deepcopy(app.devices))
        try:
            plan = await asyncio.to_thread(lambda: _sicherung_pruefen(stand, *_sicherung_lesen(daten)))
        except ValueError as err:
            log.warning("Sicherung nicht eingespielt: %s", err)
            return web.json_response({"ok": False, "error": str(err)}, status=400)
        ergebnis = await _sicherung_schreiben(app, plan)
    return web.json_response(ergebnis, status=200 if ergebnis["ok"] else 500)


async def api_settings(request: web.Request) -> web.Response:
    app: App = request.app["app"]
    cfg = _load_cfg()
    ms = _config()        # derselbe Zugang, mit dem verbunden wird (Datei, sonst LOXPANEL_MS_*)
    ic = cfg.get("intercom", {})

    def icv(uuid):
        e = ic.get(uuid) or {}
        if isinstance(e, str):
            e = {"url": e}
        return {"url": (e.get("url") or "").strip(), "user": e.get("user", ""),
                "hasPass": bool(e.get("pass"))}

    intercoms = [{"uuid": u, "name": _clean(c.get("name")), **icv(u)}
                 for u, c in app.controls.items() if c.get("type") in INTERCOM_TYPES]
    am = cfg.get("audiometa", {}) if isinstance(cfg.get("audiometa"), dict) else {}
    cal = cfg.get("calendar", {}) if isinstance(cfg.get("calendar"), dict) else {}
    return web.json_response({
        "miniserver": {
            "host": ms.get("host", ""),
            "user": ms.get("user", ""),
            "port": ms.get("port", 443),
            "verify_tls": bool(ms.get("verify_tls", False)),
            "hasPass": bool(ms.get("pass")),
        },
        "intercoms": intercoms,
        "audiometa": {"enabled": bool(am.get("enabled", True)),
                      "servers": sorted(app.mediaservers.values())},
        "calendar": {
            # Quellen normalisiert (inkl. Migration einer alten einzelnen
            # ical_url), damit die Einstellungsseite genau das sieht, womit der
            # Server auch arbeitet.
            "sources": [{"name": q["name"], "url": q["url"], "color": q["color"],
                         "key": q["key"]}
                        for q in front_info.calendar_sources(cal)],
            "holiday_url": (cal.get("holiday_url") or "").strip(),
            "name": cal.get("name") or "Family",
            "colors": bool(cal.get("colors", True)),
            "sv_events": cal.get("sv_events", 3),
            "palette": front_info.CAL_COLORS,
            "max_sources": front_info.MAX_SOURCES,
            "lat": cal.get("lat"),
            "lon": cal.get("lon"),
            "days": cal.get("days", 14),
            "fore_days": cal.get("fore_days", 4),
            "status": app._front_meta,
            # Auto-Standort vom Miniserver (Fallback, wenn keine Koordinaten gesetzt)
            "ms_lat": app.ms_lat, "ms_lon": app.ms_lon, "ms_location": app.ms_location,
        },
        "night": {"control": (app.night_cfg or {}).get("control") or "",
                  "options": app.night_control_options()},
        "connected": app.client is not None,
        "nControls": len(app.controls),
        "version": VERSION,
        # Ohne Struktur fuehrt der Konfigurator zuerst zum Miniserver
        "einrichtung": app._einrichtung_info(),
    })


async def api_settings_ms(request: web.Request) -> web.Response:
    """Miniserver-Zugang pruefen, dann speichern (Settings -> Miniserver).
    Lehnt der Miniserver ab, bleibt alles beim Alten, Datei wie Verbindung.
    Antwortet er nicht, ist offen, ob der Zugang stimmt: Er wird gespeichert,
    eine bestehende Verbindung bleibt aber, bis stream_task sie neu aufbaut
    (_zugang_neu). Leeres Kennwort = das bisherige, nur fuer denselben Host
    und Benutzer. "error" ist ein fester Text (i18n), der Fehler des
    Miniservers steht getrennt in "fehler"."""
    app: App = request.app["app"]
    try:
        data = await request.json()
    except (ValueError, aiohttp.ContentTypeError):
        return web.json_response({"ok": False, "error": "kein gültiges JSON"}, status=400)
    host = str(data.get("host", "")).strip()
    if not host:
        return web.json_response({"ok": False, "error": "Host fehlt"}, status=400)
    user = str(data.get("user", "")).strip()
    if not user:
        return web.json_response({"ok": False, "error": "Benutzer fehlt"}, status=400)
    try:
        port = int(data.get("port") or 443)
    except (TypeError, ValueError):
        port = 0
    if not 1 <= port <= 65535:
        return web.json_response({"ok": False, "error": "Port ungültig"}, status=400)
    neu = {"host": host, "user": user, "port": port, "verify_tls": bool(data.get("verify_tls"))}
    async with app._zugang_sperre:
        alt, quelle = _ms_zugang()
        if data.get("pass"):
            neu["pass"] = str(data["pass"])
        elif alt.get("pass") and (str(alt.get("host") or "").strip(), str(alt.get("user") or "").strip()) == (host, user):
            neu["pass"] = alt["pass"]
        else:
            return web.json_response({"ok": False, "error": "Neuer Host oder Benutzer: bitte das Passwort eingeben."
                                      if alt.get("pass") else "Passwort fehlt"}, status=400)

        def speichern() -> None:
            if quelle == "umgebung" and all(alt.get(k) == v for k, v in neu.items()):
                return   # unveraendert aus LOXPANEL_MS_*: gilt dort weiter, Kennwort nicht in die Datei
            cfg = _load_cfg()   # erst jetzt: andere Abschnitte koennen sich waehrend der Pruefung geaendert haben
            datei = cfg.get("miniserver") if isinstance(cfg.get("miniserver"), dict) else {}
            cfg["miniserver"] = {**datei, **neu}     # msno, _comment, Zeitwerte bleiben
            _write_cfg(cfg)

        try:
            n = await app.reconnect(neu)
        except Exception as err:
            fehler = " ".join(str(err).split()) or type(err).__name__
            if not _ms_unerreichbar(err):
                log.warning("Miniserver-Zugang nicht gespeichert, Anmeldung an %s gescheitert: %s", host, fehler)
                return web.json_response({"ok": False, "fehler": fehler, "error":
                                          "Anmeldung am Miniserver gescheitert. Der Zugang wurde nicht gespeichert."})
            verbunden = app.client is not None
            try:
                speichern()
            except OSError as err2:
                log.warning("Miniserver-Zugang nicht gespeichert: %s", err2)
                return web.json_response({"ok": False, "connected": verbunden, "fehler": f"{fehler} · {err2}",
                                          "error": "Miniserver nicht erreichbar, und der Zugang ließ sich nicht "
                                                   "speichern. Es bleibt beim bisherigen."}, status=500)
            app._zugang_neu = neu
            log.warning("Miniserver %s nicht erreichbar (%s), Zugang trotzdem gespeichert", host, fehler)
            return web.json_response({
                "ok": False, "gespeichert": True, "connected": verbunden, "fehler": fehler,
                "error": "Miniserver nicht erreichbar. Der Zugang ist trotzdem gespeichert: Die bestehende "
                         "Verbindung bleibt, der neue Zugang gilt ab dem nächsten Verbindungsaufbau." if verbunden
                else "Miniserver nicht erreichbar. Der Zugang ist trotzdem gespeichert, LoxPanel versucht es damit weiter."})
        # Audioserver-Clients merken sich den Benutzer beim Anlegen
        for cl in list(app.audio_clients.values()):
            await cl.close()
        app.audio_clients.clear()
        app._front_refresh.set()
        try:
            speichern()
        except OSError as err:
            log.warning("Miniserver verbunden, Zugang aber nicht gespeichert: %s", err)
            return web.json_response({"ok": False, "connected": True, "nControls": n, "fehler": str(err),
                                      "error": "Verbunden, aber der Zugang ließ sich nicht speichern. "
                                               "Nach einem Neustart gilt er nicht mehr."}, status=500)
    log.info("Miniserver-Settings gespeichert, verbunden (%d Controls)", n)
    return web.json_response({"ok": True, "connected": True, "nControls": n})


async def api_settings_night(request: web.Request) -> web.Response:
    """Nacht-Ausloeser: Baustein, dessen `active`-State den Nachtmodus schaltet.
    Leer = keiner, dann entscheiden die Sonnenzeiten."""
    app: App = request.app["app"]
    try:
        data = await request.json()
    except (ValueError, aiohttp.ContentTypeError):
        return web.json_response({"ok": False, "error": "kein gültiges JSON"}, status=400)
    u = str(data.get("control") or "").strip()
    if u and u not in app.controls:
        return web.json_response({"ok": False, "error": "Baustein nicht gefunden"}, status=400)
    cfg = _load_cfg()
    night = dict(cfg.get("night", {}) if isinstance(cfg.get("night"), dict) else {})
    night["control"] = u
    cfg["night"] = night
    try:
        _write_cfg(cfg)
    except OSError as err:
        return web.json_response({"ok": False, "error": str(err)}, status=500)
    app.night_cfg = _night_config()
    log.info("Nacht-Ausloeser gespeichert: %s", u or "(keiner -> Sonnenzeiten)")
    return web.json_response({"ok": True})


async def api_settings_audiometa(request: web.Request) -> web.Response:
    """Audioserver-Live-Daten (Gen-2-Event-Kanal) an/aus. Adressen werden
    automatisch aus der Struktur gelesen — es gibt nur den Master-Schalter."""
    app: App = request.app["app"]
    try:
        data = await request.json()
    except (ValueError, aiohttp.ContentTypeError):
        return web.json_response({"ok": False, "error": "kein gültiges JSON"}, status=400)
    cfg = _load_cfg()
    am = dict(cfg.get("audiometa", {}) if isinstance(cfg.get("audiometa"), dict) else {})
    am["enabled"] = bool(data.get("enabled"))
    cfg["audiometa"] = am
    try:
        _write_cfg(cfg)
    except OSError as err:
        return web.json_response({"ok": False, "error": str(err)}, status=500)
    app.audiometa_cfg = _audiometa_config()
    # Bei Deaktivierung laufende Clients sofort schliessen; beim Aktivieren
    # startet der audio_events_task sie beim naechsten Durchlauf automatisch.
    if not am["enabled"]:
        for cl in list(app.audio_clients.values()):
            await cl.close()
        app.audio_clients.clear()
    app._dirty = True
    log.info("Audioserver-Live-Daten %s", "aktiv" if am["enabled"] else "aus")
    return web.json_response({"ok": True})


async def api_settings_calendar(request: web.Request) -> web.Response:
    """Kalender (iCal-Abos) + Wetter (Open-Meteo-Koordinaten) fuer die Front."""
    app: App = request.app["app"]
    try:
        data = await request.json()
    except (ValueError, aiohttp.ContentTypeError):
        return web.json_response({"ok": False, "error": "kein gültiges JSON"}, status=400)

    def _coord(v):
        # leer = nicht gesetzt; deutsches Komma erlauben; ausserhalb des Bereichs = ungueltig
        if v in (None, ""):
            return None
        try:
            f = float(str(v).replace(",", "."))
        except (TypeError, ValueError):
            return None
        return f if -90.0 <= f <= 180.0 else None

    def _int(v, default, lo, hi):
        try:
            return max(lo, min(hi, int(v)))
        except (TypeError, ValueError):
            return default

    cfg = _load_cfg()
    cal = dict(cfg.get("calendar", {}) if isinstance(cfg.get("calendar"), dict) else {})

    # Kalenderquellen NUR anfassen, wenn die Oberflaeche sie mitgeschickt hat.
    # Eine aeltere /config-Seite, die noch im Browser offen steht, kennt das
    # Feld nicht - ohne diese Pruefung loescht ihr "Speichern" saemtliche Abos.
    # Dasselbe gilt fuer die anderen neuen Felder weiter unten.
    roh = data.get("sources")
    if isinstance(roh, list):
        quellen, gesehen = [], set()
        for q in roh:
            if not isinstance(q, dict):
                continue
            url = front_info.normalize_ical_url(q.get("url"))
            # Doppelte URLs hier schon wegwerfen: calendar_sources() tut es
            # ohnehin, sonst stuenden sie in der Datei und die Oberflaeche
            # zeigte beim naechsten Laden weniger an, als gespeichert wurde.
            if not url or url in gesehen or len(quellen) >= front_info.MAX_SOURCES:
                continue
            gesehen.add(url)
            quellen.append({"name": str(q.get("name", "")).strip()[:40],
                            "url": url,
                            # Leer = spaeter die Vorschlagsfarbe der Position
                            "color": front_info.clean_color(q.get("color"), "")})
        cal["sources"] = quellen
        # Die alte Einzel-URL darf stehen bleiben, solange sie in der Liste
        # steht: calendar_sources() liest sie nur, wenn `sources` nichts
        # hergibt, ein Doppel-Kalender entsteht also nicht - und ein Downgrade
        # auf eine aeltere Version findet seinen Kalender noch vor. Erst wenn
        # der Benutzer sie aus der Liste genommen hat, verschwindet sie auch
        # hier, sonst kaeme sie beim Loeschen des letzten Abos zurueck.
        if front_info.normalize_ical_url(cal.get("ical_url")) not in gesehen:
            cal["ical_url"] = ""
    cal["holiday_url"] = str(data.get("holiday_url", "")).strip()
    cal["name"] = str(data.get("name", "")).strip() or "Family"
    if "colors" in data:
        cal["colors"] = bool(data.get("colors"))
    lat, lon = _coord(data.get("lat")), _coord(data.get("lon"))
    # Nur ein vollstaendiges Koordinatenpaar speichern (halb gesetzt = kein Wetter).
    cal["lat"] = lat if (lat is not None and lon is not None) else None
    cal["lon"] = lon if (lat is not None and lon is not None) else None
    cal["days"] = _int(data.get("days"), 14, 1, 60)
    cal["fore_days"] = _int(data.get("fore_days"), 4, 1, 7)
    if "sv_events" in data:
        cal["sv_events"] = _int(data.get("sv_events"), 3, 1, 10)
    cfg["calendar"] = cal
    try:
        _write_cfg(cfg)
    except OSError as err:
        return web.json_response({"ok": False, "error": str(err)}, status=500)
    app.calendar_cfg = _calendar_config()
    app._front_cal_due = 0.0   # Kalender sofort neu holen, nicht erst im naechsten Takt
    app._front_refresh.set()   # sofort neu laden und an die Panels schicken
    log.info("Kalender/Wetter gespeichert (%d iCal-Abo(s), Wetter %s)",
             len(front_info.calendar_sources(cal)),
             "gesetzt" if cal["lat"] is not None else "leer")
    return web.json_response({"ok": True})


