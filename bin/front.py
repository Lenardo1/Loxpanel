"""Front (Uhr-Seite): Termine aus den Kalender-Abos und Wetter (Loxone-Wetterserver
mit Vorrang, sonst Open-Meteo), regelmaessig geholt (front_task) und als
{t:"front"} an die Panels; Sonnenzeiten aus dem Miniserver. Das Parsen steht in
front_info.py und loxone_weather.py.

Die Methoden sind ein Mixin (Front): App erbt sie und arbeitet mit ihnen auf ihrem
Zustand (self ist die App). Importiert webvisu nicht."""
from __future__ import annotations

import asyncio
import copy
import json
import logging
import time
from datetime import date

import aiohttp

import front_info
import loxone_weather

log = logging.getLogger("loxpanel.webvisu")   # derselbe Logger wie der Server: die Methoden gehoeren zu App


FRONT_INTERVAL = 900     # s: Kalender + Open-Meteo so oft neu holen; Wetter-Pushes dazwischen ohne Abruf


class Front:
    """Kalender und Wetter der Uhr-Seite; Mixin der App (self ist die App)."""

    def _on_weather(self, uuid: str, entries: list) -> None:
        """Wetter-Tabelle vom Miniserver uebernehmen (nur mit Wetterdienst).

        Die Front wird sofort neu gebaut, statt bis zum naechsten 15-Minuten-Takt
        zu warten: aus dem letzten Stand, mit neuem Wetter und OHNE neuen
        Kalenderabruf (siehe _front_nur_wetter()). Nur bei echter Aenderung,
        sonst baute jeder Wiederholungs-Push die Front umsonst neu."""
        if self._lox_wx.get(uuid) == entries:
            return
        self._lox_wx[uuid] = entries
        self._front_refresh.set()

    def _ms_sun_hhmm(self) -> tuple[str | None, str | None]:
        """Sonnenauf-/-untergang des Miniservers als "HH:MM".

        Quelle sind die globalen States (Minuten seit Mitternacht) — dieselbe,
        an der auch der Nachtmodus haengt. Ohne Werte (None, None)."""
        gs = self.global_states or {}
        out: list[str | None] = []
        for key in ("sunrise", "sunset"):
            u = gs.get(key)
            v = self.states.get(u) if isinstance(u, str) else None
            if isinstance(v, (int, float)) and 0 <= v < 1440:
                out.append(f"{int(v) // 60:02d}:{int(v) % 60:02d}")
            else:
                out.append(None)
        return out[0], out[1]

    def _loxone_weather(self) -> dict | None:
        """Wetter vom Loxone-Wetterserver aufbereitet — oder None, wenn die
        Anlage keinen hat bzw. die Daten nicht tragfaehig sind. Dann bleibt
        Open-Meteo zustaendig."""
        states = (self.weather_cfg or {}).get("states")
        if not isinstance(states, dict):
            return None
        actual = self._lox_wx.get(states.get("actual")) or []
        if not actual:
            return None
        forecast = self._lox_wx.get(states.get("forecast")) or []
        sr, ss = self._ms_sun_hhmm()
        try:
            fore = int((self.calendar_cfg or {}).get("fore_days") or 4)
        except (TypeError, ValueError):
            fore = 4
        try:
            return loxone_weather.build(self.weather_cfg, actual, forecast,
                                        sunrise=sr, sunset=ss, fore_days=fore)
        except Exception:
            log.exception("Wetterserver: Aufbereitung fehlgeschlagen — Open-Meteo bleibt")
            return None

    def _front_payload(self, data: dict) -> dict:
        return {"t": "front", "weather": data.get("weather"),
                "events": data.get("events") or [], "holidays": data.get("holidays") or {},
                "calName": data.get("calName") or "Family",
                # Legende der Kalender (Name + Farbe, ohne die Abo-URLs) und
                # die Anzeigeoptionen, die das Panel dafuer braucht.
                "cals": data.get("cals") or [],
                "calColors": bool(data.get("colors", True)),
                "svEvents": data.get("sv_events") or 3}

    def _front_cached_events(self, events: list) -> list:
        """Gespeicherte Termine auf HEUTE umschreiben.

        Der gespeicherte Stand kann von gestern sein — dauert der Aussetzer
        ueber Mitternacht, zeigt sein "Heute" auf den Vortag und laengst
        vergangene Tage stehen noch in der Liste. Beides hier richtigstellen,
        statt einen falschen Tag aufs Panel zu schicken.
        """
        heute = date.today()
        raus = []
        for e in events:
            try:
                d = date.fromisoformat(e.get("date") or "")
            except (ValueError, TypeError):
                continue
            if d < heute:
                continue
            label = front_info.day_label(d, heute)
            raus.append(e if e.get("day") == label else dict(e, day=label))
        return raus

    def _front_wetter(self, data: dict, wx: dict | None) -> None:
        """Wetter vom Loxone-Wetterserver einsetzen (Vorrang vor Open-Meteo) und
        die tatsaechlich verwendete Quelle fuer die Diagnose festhalten."""
        if wx is not None:
            data["weather"] = wx
            data["meta"]["wx_configured"] = True
            data["meta"]["wx_error"] = None
        data["meta"]["wx_source"] = "miniserver" if wx is not None else "open-meteo"
        self._wx_source = data["meta"]["wx_source"]

    def _front_nur_wetter(self, wx: dict | None) -> dict | None:
        """Front aus dem letzten Stand neu bauen, nur mit frischem Wetter.

        So reagiert die Front auf einen Wetter-Push des Miniservers, ohne
        Kalender und Open-Meteo erneut abzufragen. Wie oft der Miniserver
        schickt, bestimmt er selbst. Hing daran ein Kalenderabruf, fragte
        LoxPanel iCloud Durchgang an Durchgang an, und iCloud sperrte das Abo
        mit 503 und Retry-After. Der letzte Stand ist schon durch _front_keep()
        gelaufen; ein zweiter Durchgang wuerde die Uhrzeit des letzten guten
        Kalenderstands verfaelschen.
        """
        if self._front_last is None:
            return None
        data = copy.deepcopy(self._front_last)
        # Liefert der Wetterserver gerade nichts Brauchbares, bleibt der letzte
        # Stand samt seiner Quelle stehen; Open-Meteo kommt im naechsten Takt.
        if wx is not None:
            self._front_wetter(data, wx)
        self._front_meta = data.get("meta", {})
        return self._front_payload(data)

    def _front_keep(self, data: dict) -> dict:
        """Bei einem fehlgeschlagenen Abruf den letzten guten Stand behalten.

        Ohne das loescht ein einzelner Aussetzer die Anzeige: `load_front()`
        faengt den Fehler ab und liefert eine LEERE Liste zurueck, der
        Diff-Vergleich sieht darin eine echte Aenderung und schickt sie los -
        der Kalender ist am Panel bis zu 15 Minuten weg, nur weil iCloud einmal
        503 gesagt hat. Der alte Stand ist in dem Fall die bessere Auskunft als
        gar keiner; die Einstellungsseite nennt den Fehler weiterhin und sagt
        jetzt dazu, von wann die gezeigten Daten sind.

        Die Termine werden JE KALENDER ueberbrueckt: bei mehreren Abos ist die
        Liste auch dann gefuellt, wenn eine Quelle ausfaellt — ein gemeinsamer
        Stand wuerde genau dann ueberschrieben und die Termine der ausgefallenen
        Quelle verschwinden lassen.
        """
        meta = data.get("meta") or {}

        quellen = meta.get("cal_sources") or []
        if quellen:
            frisch: dict = {}
            for e in data.get("events") or []:
                frisch.setdefault(e.get("ck") or "", []).append(e)
            zusammen, stale = [], None
            for q in quellen:
                k = q.get("key") or ""
                gut = self._front_good_cal.get(k)
                if q.get("error") and not frisch.get(k) and gut:
                    zusammen.extend(self._front_cached_events(gut["events"]))
                    q["stale"] = gut["zeit"]
                    stale = gut["zeit"]
                else:
                    ev = frisch.get(k, [])
                    zusammen.extend(ev)
                    if not q.get("error"):
                        self._front_good_cal[k] = {"events": ev, "zeit": time.strftime("%H:%M")}
            # Quellen einzeln sortiert -> zusammengefuehrt neu ordnen.
            zusammen.sort(key=front_info.event_sort_key)
            data["events"] = zusammen
            meta["cal_count"] = len(zusammen)
            if stale:
                meta["events_stale"] = stale
        # Entfernte Kalender nicht ewig im Speicher mitschleppen.
        aktuell = {q.get("key") for q in quellen}
        for k in list(self._front_good_cal):
            if k not in aktuell:
                del self._front_good_cal[k]

        for fehler, feld in (("hol_error", "holidays"),
                             ("wx_error", "weather")):
            if meta.get(fehler) and not data.get(feld) and self._front_good.get(feld):
                data[feld] = self._front_good[feld]
                meta[f"{feld}_stale"] = self._front_good.get("_zeit")
            elif not meta.get(fehler) and data.get(feld):
                self._front_good[feld] = data[feld]
                self._front_good["_zeit"] = time.strftime("%H:%M")
        return data

    async def front_task(self) -> None:
        """Kalender + Wetter periodisch laden und an die Panels schicken. Laeuft nur
        aktiv, wenn mindestens ein iCal-Abo ODER Koordinaten gesetzt sind.

        _front_refresh weckt die Schleife vorzeitig. Nach dem Speichern holt sie
        alles neu; bei neuem Wetter vom Miniserver tauscht sie nur das Wetter und
        laesst den Kalender bis zum naechsten Takt in Ruhe."""
        # Grenze je Host: mehrere Abos liegen oft beim selben Anbieter (iCloud,
        # Google). Acht gleichzeitige Verbindungen dorthin sehen nach einem
        # Ansturm aus — genau das beantwortet iCloud gern mit 503.
        self._front_session = aiohttp.ClientSession(
            connector=aiohttp.TCPConnector(limit_per_host=3))
        try:
            while True:
                cfg = dict(self.calendar_cfg or {})
                # Koordinaten automatisch vom Miniserver, wenn keine in der Config.
                if cfg.get("lat") in (None, "") and self.ms_lat is not None:
                    cfg["lat"], cfg["lon"] = self.ms_lat, self.ms_lon
                # Wetter vom Miniserver hat Vorrang; Open-Meteo bleibt Rueckfall
                # fuer Anlagen ohne Loxone-Wetterdienst. Liefert der Wetterserver
                # Wetter, braucht es weder Koordinaten noch einen zweiten Abruf.
                wx = self._loxone_weather()
                configured = bool(front_info.calendar_sources(cfg)) or wx is not None or (
                    cfg.get("lat") not in (None, "") and cfg.get("lon") not in (None, ""))
                if configured:
                    try:
                        if time.monotonic() < self._front_cal_due:
                            # Geweckt vom Wetter-Push, der Kalender ist noch nicht
                            # wieder faellig: nur das Wetter tauschen.
                            payload = self._front_nur_wetter(wx)
                        else:
                            # Vor dem Abruf vormerken: auch ein unerwarteter Fehler
                            # darf keinen Abruf nach dem anderen nach sich ziehen.
                            self._front_cal_due = time.monotonic() + FRONT_INTERVAL
                            data = await front_info.load_front(self._front_session, cfg,
                                                               skip_weather=wx is not None)
                            self._front_wetter(data, wx)
                            data = self._front_keep(data)   # Aussetzer loescht nichts
                            self._front_last = copy.deepcopy(data)
                            self._front_meta = data.get("meta", {})
                            payload = self._front_payload(data)
                    except Exception:
                        log.exception("front_task: Laden fehlgeschlagen")
                        payload = None
                else:
                    self._front_meta = {}
                    self._wx_source = "open-meteo"
                    payload = {"t": "front", "weather": None, "events": [],
                               "holidays": {}, "cals": [], "calColors": True,
                               "svEvents": 3,
                               "calName": (cfg.get("name") or "Family")}
                # Nur bei echter Aenderung senden (spart Broadcasts bei gleichem Stand).
                if payload is not None:
                    key = json.dumps(payload, sort_keys=True, ensure_ascii=False)
                    if key != self._front_key:
                        self._front = payload
                        self._front_key = key
                        self._front_dirty = True
                # Bis der Kalender wieder faellig ist (hoechstens FRONT_INTERVAL) ODER
                # bis ein Speichern oder neues Wetter vom Miniserver weckt. Nach einem
                # Wetter-Push nur die RESTzeit warten, sonst schoebe jeder Push den
                # naechsten Kalenderabruf weiter hinaus.
                warte = FRONT_INTERVAL
                if configured:
                    warte = min(FRONT_INTERVAL, max(1.0, self._front_cal_due - time.monotonic()))
                try:
                    await asyncio.wait_for(self._front_refresh.wait(), timeout=warte)
                except asyncio.TimeoutError:
                    pass
                self._front_refresh.clear()
        finally:
            if self._front_session is not None:
                await self._front_session.close()
                self._front_session = None
