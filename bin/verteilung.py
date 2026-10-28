"""Verteilung an die Browser: der Broadcaster schickt geaenderte Seiten und
Panes an jede Visu (_broadcast_tick), push() an ausgewaehlte, Neuladen,
die Hinweise zur Verbindung (Miniserver weg, Server weg) und zur Einrichtung
(kein Zugang, keine Struktur).

Die Methoden sind ein Mixin (Verteilung): App erbt sie und arbeitet mit ihnen auf ihrem
Zustand (self ist die App). Importiert webvisu nicht."""
from __future__ import annotations

import asyncio
import logging
import time

from geraete import _lan_adressen

log = logging.getLogger("loxpanel.webvisu")   # derselbe Logger wie der Server: die Methoden gehoeren zu App


# Verbindungszustand fuer die Panels ({t:"verbindung"}, _verbindung_msg): ob der
# Server den Miniserver erreicht, seit wann nicht und wann er zuletzt von ihm
# hoerte. Die Nachricht geht bei jeder Aenderung und alle VERBINDUNG_TAKT s an
# jedes Panel; so bemerkt die Visu auch einen Server, der still verschwindet
# (WLAN, Strom), und baut nach VERBINDUNG_STUMM s ohne jede Nachricht neu auf.
# Die Bedienung sperrt sie sofort, die Leiste zeigt sie erst nach
# VERBINDUNG_HINWEIS s: der Neustart des Miniservers nach dem Speichern in
# Loxone Config oder ein kurzer WLAN-Aussetzer soll nicht jedes Mal aufblitzen.
VERBINDUNG_TAKT = 15     # s: Lebenszeichen an jedes Panel

VERBINDUNG_STUMM = 40    # s: ohne Nachricht gilt der Server als weg (mehr als zwei Takte)

VERBINDUNG_HINWEIS = 8   # s: so lange fehlt eine Verbindung, bevor die Leiste erscheint

# Texte der Leiste; {seit} und {stand} setzt die Visu als Uhrzeit ein
VERBINDUNG_TEXTE = {
    "ms": "Miniserver seit {seit} nicht erreichbar",
    "server": "Keine Verbindung zum LoxPanel-Server seit {seit}",
    "stand": "Letzter bestätigter Stand: {stand}",
    "gesperrt": "Bedienung gesperrt",
}

# Eine Verbindung rendert nur neu, wenn sich ein State geaendert hat, den ihre
# Seite liest, oder etwas ausserhalb der States (_dirty). Spaetestens nach so
# vielen Sekunden aber auf jeden Fall: Countdowns und Uhrzeiten auf der Seite
# ("wird scharf um ...", Briefkasten-Pause, "heute"/"morgen" beim Wecker und
# im Klingelarchiv) und das Nachladen der Verlaeufe haengen an der Zeit, nicht
# an einem State.
RENDER_SPAETESTENS_S = 10


class _Lesespur:
    """Sicht auf App.states fuer ein Rendern, die mitschreibt, welche States es
    liest (get, [], in). Was die States im Ganzen braucht (Durchlaufen, Laenge,
    andere Methoden), setzt `alles`: dann rendert die Verbindung bei jedem Tick."""
    __slots__ = ("quelle", "gelesen", "alles")

    def __init__(self, quelle):
        self.quelle, self.gelesen, self.alles = quelle, set(), False

    def get(self, k, default=None):
        self.gelesen.add(k)
        return self.quelle.get(k, default)

    def __getitem__(self, k):
        self.gelesen.add(k)
        return self.quelle[k]

    def __contains__(self, k):
        self.gelesen.add(k)
        return k in self.quelle

    def __setitem__(self, k, v):
        self.quelle[k] = v

    def __iter__(self):
        self.alles = True
        return iter(self.quelle)

    def __len__(self):
        self.alles = True
        return len(self.quelle)

    def __getattr__(self, name):
        if name in _Lesespur.__slots__:
            raise AttributeError(name)
        self.alles = True
        return getattr(self.quelle, name)


class Verteilung:
    """Senden an die Browser; Mixin der App (self ist die App)."""

    def _pane_msg(self, art: str, uuid: str, blocks: list) -> dict:
        """{t:"player"|"camera"} fuer Player- bzw. Kamera-Bereich. Gesichert wie
        die Detailseite derselben Zone bzw. Intercom, sonst bedienten
        Lautstaerke, Transport und Tueroeffner sie ohne PIN."""
        m = {"t": art, "blocks": blocks}
        if self._gesichert(uuid):
            m["secured"] = True
        return m

    def _mark_dirty(self) -> None:
        self._dirty = True

    async def push(self, msg: dict, panel: str = "", device: str = "") -> int:
        """Push an offene Visu-Verbindungen (Server -> Browser). Optional gefiltert
        auf ein Panel-Profil (`panel`) oder ein Geraet (`device`, aus ?device=).
        Gibt die Anzahl erreichter Panels zurueck. Ein Panel, das gerade neu laedt
        (App._neu_laden), zaehlt nicht mehr: erreicht wird erst seine neue Verbindung."""
        panel = (panel or "").strip()
        device = (device or "").strip()
        n = 0
        for ws in list(self.conn_prof):
            if panel and (self.conn_prof.get(ws) or {}).get("id") != panel:
                continue
            if device and self.conn_dev.get(ws) != device:
                continue
            if (self.conn_info.get(ws) or {}).get("neuLaden"):
                continue
            if await (self._neu_laden(ws) if msg.get("t") == "reload" else self._send_or_drop(ws, msg)):
                n += 1
        return n

    async def _send_or_drop(self, ws, payload) -> bool:
        """Sendet an ein Panel; bei JEDEM Fehler ODER Haenger (Timeout) wird die
        Verbindung getrennt (nicht nur bei ConnectionError — aiohttp wirft bei
        sterbenden Sockets auch RuntimeError, oder send blockiert bei half-open).
        Das ws wird zusaetzlich geschlossen, damit das Panel den Abbruch bemerkt
        und sich neu verbindet (statt still ohne Live-Updates weiterzulaufen)."""
        try:
            await asyncio.wait_for(ws.send_json(payload), timeout=5)
            return True
        except Exception:
            self.conn_route.pop(ws, None)
            self.conn_prof.pop(ws, None)
            self.conn_dev.pop(ws, None)
            self.conn_info.pop(ws, None)
            self.conn_player.pop(ws, None)
            self.conn_energy.pop(ws, None)
            self.conn_chart.pop(ws, None)
            self.conn_camera.pop(ws, None)
            self.conn_status.pop(ws, None)
            self.conn_geste.pop(ws, None)
            try:
                await ws.close()
            except Exception:
                pass
            return False

    async def _neu_laden(self, ws, msg: dict | None = None) -> bool:
        """Ein Panel neu laden ({t:"reload"}, oder `msg`, das die Seite neu laedt,
        etwa {t:"entwurfEnde"}) und die Verbindung als abgeloest kennzeichnen: die
        Seite verschwindet gleich, ein weiterer Push an sie (etwa das Umschalten
        gleich nach dem Speichern) ginge mit ihr verloren und darf in _push()
        nicht als erreicht zaehlen."""
        if not await self._send_or_drop(ws, msg or {"t": "reload"}):
            return False
        if ws in self.conn_info:
            self.conn_info[ws]["neuLaden"] = True
        return True

    async def _broadcast_tick(self) -> None:
        await self._einrichtung_melden()
        await self._verbindung_melden()
        await self.geste_fahrten()   # Jalousien nach einer Geste: Stellung live an die Einblendung
        if self.vorschau_geraet:   # Vorschau am Geraet abgelaufen: zurueck zur vorigen Ansicht
            jetzt = time.time()
            for dev in [d for d, e in self.vorschau_geraet.items() if jetzt > e["bis"]]:
                await self.vorschau_beenden(dev)
        if self._pending_ring is not None:
            rid, self._pending_ring = self._pending_ring, None
            log.info("Klingel → Popup: %s", rid)
            self._spawn(self.display_drivers(True))   # Kiosk-Apps ueber HTTP wecken
            # Die Haustuer klingelt auf jedem Panel, auch einem, dessen Ansicht nur
            # andere Raeume zeigt; nur wer die Tuersprechanlage ausblendet (hide),
            # bekommt nichts
            for ws in list(self.conn_route):
                if self._shown(rid, self.conn_prof.get(ws)):
                    await self._send_or_drop(ws, {"t": "ring", "id": rid})
        while self._pending_alarm:
            ev = self._pending_alarm.pop(0)
            log.info("Wecker %s → %s", "an" if ev["on"] else "aus", ev["id"])
            # Der Weckton nur, wo die Ansicht den Wecker zeigt (Raum, Kategorie,
            # hide), und nur deren Display geht an (Kiosk-App ueber HTTP); "aus"
            # an alle, sonst toente ein Panel, das waehrenddessen die Ansicht
            # gewechselt hat, weiter
            geweckt: set[str] = set()
            for ws in list(self.conn_route):
                if ev["on"] and not self._sichtbar(ev["id"], self.conn_prof.get(ws)):
                    continue
                await self._send_or_drop(ws, {"t": "alarm", "id": ev["id"], "on": ev["on"]})
                dev = self.conn_dev.get(ws)
                if ev["on"] and dev and dev not in geweckt:
                    geweckt.add(dev)
                    self._spawn(self.display_drivers(True, dev))
        if self._presence_quelle[0] is not self.devices or self._presence_quelle[1] is not self.controls:
            self._presence_rebuild()   # Geraete oder Struktur ersetzt, ohne neu zu koppeln
        ereignisse, self._pending_presence = self._pending_presence, []
        for ev in ereignisse:
            # Nur an das Geraet mit diesem Praesenzmelder: seine Visu haelt das
            # Display (presence) bzw. schaltet es ueber die Kiosk-App, die
            # Display-Treiber (Fully Remote Admin, WallPanel) schalten mit.
            # Einmal durch die Liste (pop(0) waere quadratisch); was waehrend
            # des Sendens dazukommt, laeuft im naechsten Takt.
            log.info("Präsenz %s: %s → Display %s", ev["dev"],
                     "jemand da" if ev["presence"] else "Raum leer", "an" if ev["on"] else "aus")
            if ((self.devices.get(ev["dev"]) or {}).get("display")):
                self._spawn(self.display_drivers(ev["on"], ev["dev"]))
            for ws, info in list(self.conn_info.items()):
                if info.get("dev") == ev["dev"]:
                    await self._send_or_drop(ws, {"t": "display", "on": ev["on"],
                                                  "presence": ev["presence"]})
        if self._front_dirty:
            # Front (Kalender/Wetter) an alle Panels. Neu verbundene bekommen den
            # aktuellen Stand ausserdem direkt beim Verbinden (ws_handler).
            self._front_dirty = False
            if self._front is not None:
                for ws in list(self.conn_route):
                    await self._send_or_drop(ws, self._front)
        if self._pending_reload:
            # Loxone-Struktur hat sich geaendert (Config) -> Panels neu laden, damit
            # neue/umbenannte Controls erscheinen. Nur bei echter Aenderung gesetzt.
            self._pending_reload = False
            for ws in list(self.conn_route):
                await self._neu_laden(ws)
        if self._last_sent:
            # Merkzettel von Verbindungen befreien, die es nicht mehr gibt.
            # Selbstheilend, damit nicht an jeder der vier Stellen, die eine
            # Verbindung schliessen, daran gedacht werden muss.
            for _tot in [w for w in self._last_sent if w not in self.conn_route]:
                del self._last_sent[_tot]
        for _tot in [w for w in self._render_spur if w not in self.conn_route]:
            del self._render_spur[_tot]
        night = self._night_now()
        if night != self._night_on:
            # Nur beim Wechsel senden — die Panels halten den Zustand selbst.
            self._night_on = night
            log.info("Nachtmodus %s", "an" if night else "aus")
            for ws in list(self.conn_route):
                await self._send_or_drop(ws, {"t": "night", "on": night})
        # Neu gerendert wird je Verbindung nur, was betroffen ist (_neu_rendern):
        # _dirty heisst "ausserhalb der States hat sich etwas geaendert" (Struktur,
        # Theme, Audioserver, Verlaeufe ...) und rendert alle neu, _on_value
        # sammelt die geaenderten States in _geaendert.
        alles, self._dirty = self._dirty, False
        geaendert, self._geaendert = self._geaendert, set()
        if self.conn_route:
            jetzt = time.monotonic()
            for ws, route in list(self.conn_route.items()):
                if "reihe" not in route:
                    # Seite vor Struktur oder States aufgerufen (Neustart des
                    # Servers): Reihenfolge nachtragen, sobald sie feststeht
                    nachgetragen = self.aufruf_route(route)
                    if "reihe" in nachgetragen:
                        route = self.conn_route[ws] = nachgetragen
                prof = self.conn_prof.get(ws)
                schluessel = (dict(route), self.conn_player.get(ws), self.conn_energy.get(ws),
                              self.conn_chart.get(ws), self.conn_camera.get(ws), self.conn_status.get(ws))
                if not (alles or self._neu_rendern(self._render_spur.get(ws), prof, schluessel,
                                                   geaendert, jetzt)):
                    continue
                # Rendern ist synchron: solange es laeuft, liest es die States
                # ueber die Spur, und nichts anderes kommt dazwischen
                lesen = _Lesespur(self.states)
                self.states = lesen
                try:
                    teile = self._rendern(ws, route, prof)
                finally:
                    self.states = lesen.quelle
                self._render_spur[ws] = {"prof": prof, "schluessel": schluessel, "zeit": jetzt,
                                         "liest": None if lesen.alles else lesen.gelesen}
                if teile is None:
                    continue
                msg, player_msg, energy_msg, chart_msg, _chart, camera_msg, status_msg = teile
                # Nur senden, was sich seit der letzten Zustellung an DIESE
                # Verbindung geaendert hat. Der Tick laeuft, sobald sich
                # irgendein Wert im Haus bewegt — meist betrifft das die
                # Ansicht dieses Panels gar nicht, und das Panel wuerde
                # dieselbe Ansicht erneut bekommen und komplett neu zeichnen.
                last = self._last_sent.setdefault(ws, {})
                if msg != last.get("view"):
                    if not await self._send_or_drop(ws, msg):
                        self._last_sent.pop(ws, None)
                        continue
                    last["view"] = msg
                if player_msg is not None and player_msg != last.get("player"):
                    if await self._send_or_drop(ws, player_msg):
                        last["player"] = player_msg
                    else:
                        self._last_sent.pop(ws, None)
                        continue
                if energy_msg is not None and energy_msg != last.get("energy"):
                    if await self._send_or_drop(ws, energy_msg):
                        last["energy"] = energy_msg
                    else:
                        self._last_sent.pop(ws, None)
                        continue
                # Hat das Panel waehrend der Sendungen oben einen anderen Stapel
                # gewaehlt, hat setchart den neuen schon geschickt; chart_msg ist
                # dann veraltet und wuerde ihn in der Pane wieder ersetzen.
                if (chart_msg is not None and chart_msg != last.get("chart")
                        and self.conn_chart.get(ws) == _chart):
                    if await self._send_or_drop(ws, chart_msg):
                        last["chart"] = chart_msg
                    else:
                        self._last_sent.pop(ws, None)
                        continue
                if camera_msg is not None and camera_msg != last.get("camera"):
                    if await self._send_or_drop(ws, camera_msg):
                        last["camera"] = camera_msg
                    else:
                        self._last_sent.pop(ws, None)
                        continue
                if status_msg is not None and status_msg != last.get("svstatus"):
                    if await self._send_or_drop(ws, status_msg):
                        last["svstatus"] = status_msg
                    else:
                        self._last_sent.pop(ws, None)

    @staticmethod
    def _neu_rendern(spur: dict | None, prof, schluessel: tuple, geaendert: set, jetzt: float) -> bool:
        """Muss diese Verbindung neu rendern? Ja, wenn sie es noch nie getan hat,
        Profil, Seite oder Bereiche gewechselt haben, ihr letztes Rendern einen
        der geaenderten States gelesen hat (oder die States im Ganzen) oder es
        RENDER_SPAETESTENS_S her ist."""
        return (spur is None or spur["prof"] is not prof or spur["schluessel"] != schluessel
                or jetzt - spur["zeit"] >= RENDER_SPAETESTENS_S
                or spur["liest"] is None or not spur["liest"].isdisjoint(geaendert))

    def _rendern(self, ws, route: dict, prof) -> tuple | None:
        """Ansicht und Bereiche (Player, Energiefluss, Verlauf, Kamera,
        Statusspalte) einer Verbindung rechnen -> (view, player, energy,
        chart, Verlaufs-Auswahl, camera, svstatus); None, wenn die Ansicht
        selbst scheitert. Ein Bereich, der scheitert, fehlt nur (None)."""
        try:
            msg = self.render(route, prof)
        except Exception:
            # EINE fehlerhafte Kachel/Route darf NIEMALS die Live-Update-
            # Schleife killen. Fehler loggen, diese Verbindung ueberspringen.
            log.exception("render() fehlgeschlagen (route=%s) — uebersprungen", route)
            return None
        # Split-Layout: Player-Pane des aktiven Tabs mitrendern (Zone kommt
        # vom Client via setplayer -> conn_player). Fehler isolieren.
        player_msg = None
        _zone = self.conn_player.get(ws)
        if _zone:
            try:
                pb = self.player_blocks(_zone)
                player_msg = self._pane_msg("player", _zone, pb) if pb is not None else None
            except Exception:
                log.exception("player_blocks fehlgeschlagen (%s)", _zone)
        # Split-Layout: Energiefluss-Pane des aktiven Tabs mitrendern (Kachel
        # kommt vom Client via setenergy -> conn_energy). Fehler isolieren.
        energy_msg = None
        _euid = self.conn_energy.get(ws)
        if _euid:
            try:
                eb = self.energy_blocks(_euid)
                energy_msg = {"t": "energy", **eb} if eb is not None else None
            except Exception:
                log.exception("energy_blocks fehlgeschlagen (%s)", _euid)
        # Split-Layout: Verlaufs-Pane (chart:<uuid>) des aktiven Tabs
        # mitrendern (kommt vom Client via setchart -> conn_chart).
        chart_msg = None
        _chart = self.conn_chart.get(ws)
        if _chart:
            try:
                chart_msg = {"t": "chart", **self.chart_stack(*_chart)}
            except Exception:
                log.exception("chart_stack fehlgeschlagen (%s)", _chart)
        # Split-Layout: Kamera-Pane (Intercom-Vollansicht) des aktiven Tabs
        # mitrendern (kommt vom Client via setcamera -> conn_camera).
        camera_msg = None
        _cuid = self.conn_camera.get(ws)
        if _cuid:
            try:
                ib = self.intercom_blocks(_cuid)
                camera_msg = self._pane_msg("camera", _cuid, ib) if ib is not None else None
            except Exception:
                log.exception("intercom_blocks fehlgeschlagen (%s)", _cuid)
        # Screensaver-Statusspalte: frei gewaehlte Bausteine dieses
        # Panels (kommt vom Client via setsvstatus -> conn_status).
        status_msg = None
        _suu = self.conn_status.get(ws)
        if _suu:
            try:
                status_msg = {"t": "svstatus", "items": self.status_blocks(_suu)}
            except Exception:
                log.exception("status_blocks fehlgeschlagen")
        return msg, player_msg, energy_msg, chart_msg, _chart, camera_msg, status_msg

    def _einrichtung_info(self) -> dict | None:
        """Stand der Ersteinrichtung, solange der Server keine Struktur vom
        Miniserver hat: "kein_zugang" (nichts eingetragen), "fehler" (letzter
        Versuch gescheitert, mit Grund) oder "verbindet" (erster Versuch
        laeuft). Mit Struktur None. Der Konfigurator fuehrt damit zuerst zum
        Miniserver (/api/settings), die Panels zeigen ihre Karte daraus
        (_einrichtung_stand). Billig genug fuer jeden Broadcast-Takt."""
        if self.controls:
            return None
        if not self.host:
            return {"stand": "kein_zugang"}
        if self._ms_fehler:
            return {"stand": "fehler", "host": self.host, "fehler": self._ms_fehler}
        return {"stand": "verbindet", "host": self.host}

    def _einrichtung_stand(self) -> tuple | None:
        """(Titel, Grund) fuer die Karte der Panels nach _einrichtung_info,
        aber nicht waehrend des ersten Verbindungsversuchs: Beim normalen
        Start soll nichts aufblitzen. Sonst None."""
        info = self._einrichtung_info()
        if info is None or info["stand"] == "verbindet":
            return None
        if info["stand"] == "kein_zugang":
            return ("Miniserver einrichten", "Noch kein Miniserver eingetragen.")
        return ("Keine Verbindung zum Miniserver", f"{info['host']}: {info['fehler']}")

    def _einrichtung_msg(self, stand: tuple | None) -> dict:
        """Nachricht an die Panels zum Stand aus _einrichtung_stand. Die Adresse
        des Konfigurators setzt das Panel zusammen: die, ueber die es die Visu
        geladen hat, oder - bei 127.0.0.1 - eine aus "adressen"."""
        if stand is None:
            return {"t": "einrichtung", "aktiv": False}
        titel, grund = stand
        return {"t": "einrichtung", "aktiv": True, "titel": titel, "grund": grund,
                "hinweis": "Konfigurator im Browser eines Computers oder Handys im selben Netz öffnen:",
                "pfad": "/config", "adressen": _lan_adressen(),
                "unbekannt": "Die Adresse dieses Geräts steht in seinen WLAN-Einstellungen."}

    async def _einrichtung_melden(self, neu=None) -> None:
        """Einrichtungshinweis an alle Panels, wenn sich der Stand geaendert
        hat; sonst nur an das neu verbundene Panel `neu`. Beides an einer
        Stelle, damit nie ein Panel einen Stand hat, den der Broadcaster nicht
        als gemeldet kennt (sonst bliebe die Karte nach der Rueckkehr zum
        alten Stand stehen)."""
        stand = self._einrichtung_stand()
        if stand != self._einrichtung_gemeldet:
            self._einrichtung_gemeldet = stand
            ziele = list(self.conn_route)
        else:
            ziele = [neu] if neu is not None else []
        if ziele:
            msg = self._einrichtung_msg(stand)
            for ws in ziele:
                await self._send_or_drop(ws, msg)

    def _verbindung_stand(self) -> tuple[bool, float | None, float | None]:
        """(Miniserver erreichbar, seit wann nicht, wann zuletzt von ihm
        gehoert) als Unix-Sekunden. Ohne Struktur gilt er als erreichbar: dann
        zeigen die Panels die Einrichtungskarte (_einrichtung_stand), und es
        gibt keine Werte, die veralten koennten."""
        if self._ms_weg_seit is None or not self.controls:
            return (True, None, None)
        return (False, self._ms_weg_seit, self._ms_bestaetigt)

    @staticmethod
    def _verbindung_msg(stand: tuple) -> dict:
        """Nachricht an die Panels zum Stand aus _verbindung_stand, Zeiten in
        Millisekunden (Date der Visu), dazu Takt, Fristen und Texte der Leiste."""
        ok, seit, bestaetigt = stand
        return {"t": "verbindung", "ms": ok,
                "seit": round(seit * 1000) if seit is not None else None,
                "stand": round(bestaetigt * 1000) if bestaetigt is not None else None,
                "takt": VERBINDUNG_TAKT, "stumm": VERBINDUNG_STUMM,
                "hinweis": VERBINDUNG_HINWEIS, "texte": VERBINDUNG_TEXTE}

    async def _verbindung_melden(self, neu=None) -> None:
        """Verbindungszustand an alle Panels, wenn er sich geaendert hat oder
        die letzte Meldung VERBINDUNG_TAKT s her ist (Lebenszeichen, an dem die
        Visu einen still verschwundenen Server erkennt); sonst nur an das neu
        verbundene Panel `neu`."""
        stand = self._verbindung_stand()
        jetzt = time.monotonic()
        if stand != self._verbindung_gemeldet or jetzt - self._verbindung_zuletzt >= VERBINDUNG_TAKT:
            if self._verbindung_gemeldet is not None and stand[0] != self._verbindung_gemeldet[0]:
                log.info("Panels: Miniserver %s", "wieder erreichbar" if stand[0] else "nicht erreichbar")
            self._verbindung_gemeldet, self._verbindung_zuletzt = stand, jetzt
            ziele = list(self.conn_route)
        else:
            ziele = [neu] if neu is not None else []
        if ziele:
            msg = self._verbindung_msg(stand)
            for ws in ziele:
                await self._send_or_drop(ws, msg)

    async def broadcaster(self) -> None:
        # Diese Schleife darf NIEMALS sterben — sonst bekommen ALLE Panels keine
        # Live-Updates mehr (Symptom: Aktion wird ausgefuehrt, aber erst nach
        # Weg-/Zurueck-Navigieren angezeigt). Der ganze Tick ist deshalb gekapselt.
        while True:
            await asyncio.sleep(0.3)
            try:
                await self._broadcast_tick()
            except asyncio.CancelledError:
                raise
            except Exception:
                log.exception("broadcaster-Tick fehlgeschlagen — Schleife laeuft weiter")
