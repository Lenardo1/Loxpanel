"""Gen-2-Audioserver-Event-Client (Loxone-Audioprotokoll ueber WebSocket 7091).

Der Loxone-Audioserver (Original ODER Nachbau wie Sonn/Audioserver4Home) sendet
Now-Playing und Favoriten NICHT ueber die Miniserver-Struktur-States, sondern
ueber einen eigenen Event-Kanal: die App verbindet sich direkt per WebSocket zum
Audioserver (Port 7091, unverschluesselt, OHNE Auth) und bekommt beim Connect +
bei jeder Aenderung `audio_event`-Push-Nachrichten fuer alle Zonen. So bekommen
AudioZoneV2-Zonen im Panel Cover/Titel/Interpret/Status — universell, egal
welcher Audioserver, mit Live-Push statt Polling.

Nachrichtenformate (verifiziert gegen Sonn 4.0.0-beta.20 / LWSS API 1.6):
  Banner (kein JSON):  "LWSS V 17.1.05.05 | ~API:1.6~ | Session-Token: ..."
  Push:  {"audio_event":[{playerid,name,title,artist,album,coverurl,station,
                          mode(play/pause/stop),volume,plrepeat,plshuffle,...}]}
  Abruf: audio/<id>/status            -> {"status_result":[{...wie audio_event}]}
         audio/cfg/getroomfavs/<id>   -> {"getroomfavs_result":[{id,items:[
                                          {slot,name,title,coverurl,type,...}]}]}

Steuerung (play/pause/next/volume/roomfav) laeuft weiter ueber den Miniserver
(`sps/io/<uuid>/<cmd>` -> `audio/<id>/<cmd>`), nicht ueber dieses Modul.
"""
from __future__ import annotations

import asyncio
import json
import logging

import aiohttp

try:
    from . import audioserver_auth as _auth  # type: ignore
except ImportError:  # als Skript ohne Paketkontext geladen
    import audioserver_auth as _auth

log = logging.getLogger("loxpanel.audioevents")


class AudioEventClient:
    """Haelt per WebSocket (7091) den Live-Zustand aller Audioserver-Zonen.

    now:  playerid -> Now-Playing-Dict {title,artist,album,cover,playing,volume,name}
    favs: playerid -> [ {slot,name,cover} ]

    Zuordnung Control->Zone laeuft ueber die playerid (aus control.details.
    playerid), NICHT ueber den Namen — das ist eindeutig und kollisionsfrei.
    """

    PAIRED_ERROR = "not allowed when paired"
    # s: Pause vor dem naechsten Verbindungsversuch und, solange die Kopplung
    # unklar ist, vor der naechsten Pruefung. 5 s war schon immer die Pause
    # beim Neuverbinden: Cover und Titel sind nach einem Neustart des
    # Audioservers bald wieder da, und eine kleine HTTP-Anfrage alle 5 s
    # belastet ihn nicht. loxpanel.cfg: audiometa.retry_interval.
    NEU_VERSUCH_S = 5
    # s: Zeitlimit der Kopplungspruefung (HTTP audio/cfg/all), der bisherige
    # Wert. Im LAN antwortet der Audioserver in Millisekunden; 6 s lassen einem
    # ausgelasteten Geraet Luft und halten den Verbindungsaufbau nicht laenger
    # auf als der WebSocket-Aufbau selbst (8 s). audiometa.response_timeout.
    PRUEF_ZEITLIMIT_S = 6
    # HTTP-Status, die nur "gerade nicht" heissen (dazu 5xx): sagen nichts
    # ueber die Kopplung.
    STATUS_UNKLAR = (408, 429)

    def __init__(self, host: str, port: int = 7091, user: str = "", token_provider=None,
                 neu_versuch_s: float | None = None, pruef_zeitlimit_s: float | None = None):
        self.host = host
        self.port = port
        self.neu_versuch_s = self.NEU_VERSUCH_S if neu_versuch_s is None else neu_versuch_s
        self.pruef_zeitlimit_s = self.PRUEF_ZEITLIMIT_S if pruef_zeitlimit_s is None else pruef_zeitlimit_s
        # user + token_provider (async oder sync, liefert das aktuelle Miniserver-
        # JWT) erlauben die Anmeldung am gekoppelten Audioserver wie die Loxone-App.
        self.user = user
        self._token_provider = token_provider
        self.now: dict[int, dict] = {}
        self.favs: dict[int, list] = {}
        # None = unklar (noch nicht oder ohne Ergebnis geprueft), gilt wie
        # gekoppelt ohne Anmeldung; True = gekoppelter Loxone-Audioserver, der
        # unangemeldete Befehle ablehnt und die Verbindung schliesst; False =
        # Nachbau (Sonn/AudioServer4Home), Befehle ohne Anmeldung ok.
        self.paired: bool | None = None
        # True, sobald secure/authenticate auf dieser Verbindung erfolgreich war.
        self.authed = False
        self._ws: aiohttp.ClientWebSocketResponse | None = None
        self._session: aiohttp.ClientSession | None = None
        self._on_change = None
        self._stop = False
        self._unklar_gemeldet = False
        self._sofort_neu = False     # Verbindung absichtlich geschlossen: ohne Pause neu

    @property
    def url(self) -> str:
        return f"ws://{self.host}:{self.port}/"

    def _apply_event(self, entries) -> bool:
        changed = False
        for e in entries or []:
            if not isinstance(e, dict):
                continue
            pid = e.get("playerid")
            if pid is None:
                continue
            np = {
                "name": (e.get("name") or "").strip(),
                "title": e.get("title") or "",
                "artist": e.get("artist") or "",
                "album": e.get("album") or e.get("station") or "",
                "cover": e.get("coverurl") or "",
                "playing": (e.get("mode") == "play"),
                "volume": e.get("volume"),
            }
            if self.now.get(pid) != np:
                self.now[pid] = np
                changed = True
        return changed

    def _apply_favs(self, results) -> bool:
        changed = False
        for grp in results or []:
            if not isinstance(grp, dict):
                continue
            pid = grp.get("id")
            items = []
            for it in (grp.get("items") or []):
                if not isinstance(it, dict) or it.get("slot") is None:
                    continue
                # Abspiel-Index: manche Server (Sonn/Audioserver4Home) erwarten die
                # numerische Item-`id` (2,3,4), der Loxone-Musikserver dagegen den
                # `slot` (1,2,3). Regel: ganzzahlige `id` bevorzugen, sonst `slot`.
                try:
                    play = int(it.get("id"))
                except (TypeError, ValueError):
                    play = it.get("slot")
                items.append({
                    "slot": it.get("slot"),
                    "play": play,
                    "name": it.get("name") or it.get("title") or f"Favorit {it.get('slot')}",
                    "cover": it.get("coverurl") or "",
                })
            if self.favs.get(pid) != items:
                self.favs[pid] = items
                changed = True
        return changed

    def _handle(self, data: str) -> bool:
        try:
            msg = json.loads(data)
        except (ValueError, TypeError):
            return False   # Banner o.ae. -> ignorieren
        if not isinstance(msg, dict):
            return False
        if "audio_event" in msg:
            return self._apply_event(msg.get("audio_event"))
        if "status_result" in msg:
            return self._apply_event(msg.get("status_result"))
        if "getroomfavs_result" in msg:
            return self._apply_favs(msg.get("getroomfavs_result"))
        return False

    async def _send(self, cmd: str) -> bool:
        """-> gesendet? Ohne offene Verbindung oder bei einem Fehler False (nur
        debug; ob das eine Meldung wert ist, entscheidet der Aufrufer)."""
        ws = self._ws
        if ws is None or ws.closed:
            log.debug("audioevents send %s: keine Verbindung", cmd)
            return False
        try:
            await ws.send_str(cmd)
        except Exception as err:
            log.debug("audioevents send %s: %s", cmd, err)
            return False
        return True

    async def request_favs(self, playerid: int) -> None:
        """Raumfavoriten einer Zone anfordern (Ergebnis kommt async im Reader).

        Die Range-Form `.../<start>/<count>` ist zwingend: ohne sie liefert der
        Server die Favoriten mit `slot: null` (nicht abspielbar). Mit Range
        kommen echte Slot-Nummern (1..N) fuer roomfav/play/<slot>.

        Bei einem gekoppelten Loxone-Audioserver ohne Anmeldung (und solange
        die Kopplung unklar ist) wird nichts gesendet: jeder Befehl auf dem
        Kanal beendet dort die Verbindung, und die Ereignisse (Cover/Titel)
        waeren weg.
        """
        if playerid is None:
            return
        if not (self.paired is False or self.authed):
            return
        await self._send(f"audio/cfg/getroomfavs/{int(playerid)}/0/50")

    async def _favs_anfordern(self) -> None:
        """Favoriten aller bekannten Zonen anfordern, sobald der Kanal sie
        liefern darf; eine schon offene Musikauswahl bekaeme sie sonst erst
        beim naechsten Oeffnen."""
        for pid in list(self.now):
            await self.request_favs(pid)

    async def play_roomfav(self, playerid: int, favid) -> bool:
        """Einen Raumfavoriten abspielen (Feld `play`/`id` des Favoriten, siehe
        _apply_favs). Bei einem gekoppelten Audioserver nur ueber eine angemeldete
        Verbindung; sonst wuerde er die Verbindung schliessen. -> gesendet?"""
        if playerid is None or not (self.paired is False or self.authed):
            return False
        ok = await self._send(f"audio/{int(playerid)}/roomfav/play/{favid}")
        if not ok:
            log.warning("Audioserver %s: Raumfavorit %s fuer Zone %s nicht gesendet (Verbindung weg)",
                        self.host, favid, playerid)
        return ok

    def _kopplung_unklar(self, grund: str) -> None:
        """Pruefung ohne Ergebnis, der bisherige Wert bleibt. Ist die Kopplung
        noch unbekannt, einmal als Info melden, danach debug: die Pruefung
        wiederholt sich alle neu_versuch_s Sekunden."""
        if self.paired is None and not self._unklar_gemeldet:
            self._unklar_gemeldet = True
            log.info("Audioserver %s: Kopplung unklar (%s), Befehle ueber den Miniserver; "
                     "neue Pruefung alle %s s", self.host, grund, self.neu_versuch_s)
        else:
            log.debug("Audioserver %s: audio/cfg/all %s", self.host, grund)

    async def _check_paired(self) -> None:
        """Per HTTP pruefen, ob der Audioserver Befehle ohne Anmeldung annimmt.
        Laeuft vor jedem Verbinden, solange er nicht als gekoppelt erkannt ist;
        so heilt ein falsches "nicht gekoppelt" (ein gekoppelter Server schliesst
        den Kanal beim ersten Befehl ohne Anmeldung). Ein erkanntes "gekoppelt"
        bleibt fuer die Lebensdauer des Clients: Es entsteht nur aus dem
        Kopplungstext, und eine Antwort beim Hochfahren des Audioservers (404,
        leer) wuerde es sonst kippen, Befehle gingen dann ohne Anmeldung an 7091.
          - Antwort mit "command not allowed when paired" -> gekoppelt (True),
            egal mit welchem HTTP-Status (der der echten Ablehnung ist nicht
            dokumentiert).
          - 5xx, 408, 429, Zeitlimit, Verbindungsfehler heissen nur "gerade
            nicht" -> der bisherige Wert bleibt (None = unklar, run() prueft
            spaeter erneut).
          - Jede andere Antwort -> nicht gekoppelt (False). Nachbauten und
            Musikserver Gen 1 antworten nicht einheitlich (auch 404, leer,
            mit BOM), deshalb kein strengeres Kriterium."""
        if self.paired is True:
            return
        try:
            async with self._session.get(f"http://{self.host}:{self.port}/audio/cfg/all",
                                         timeout=aiohttp.ClientTimeout(total=self.pruef_zeitlimit_s)) as r:
                status, text = r.status, await r.text(errors="replace")
        except Exception as err:
            self._kopplung_unklar(f"nicht abfragbar: {str(err) or type(err).__name__}")
            return
        if self.PAIRED_ERROR in text:
            paired = True
        elif status >= 500 or status in self.STATUS_UNKLAR:
            self._kopplung_unklar(f"HTTP {status}")
            return
        else:
            paired = False
        self._unklar_gemeldet = False
        if paired == self.paired:
            return
        self.paired = paired
        if paired:
            log.info("Audioserver %s: mit dem Miniserver gekoppelt, Kanal nur zum Hoeren (Cover/Titel); "
                     "Favoriten/Befehle ueber Port 7091 nur nach Anmeldung", self.host)
            return
        # Nur zur Diagnose: JSON oder nicht (BOM und NUL wie beim Miniserver weg)
        try:
            json.loads(text.lstrip("\ufeff").strip("\x00"))
            art = "JSON"
        except ValueError:
            art = "kein JSON"
        log.info("Audioserver %s: nimmt Befehle auf Port 7091 an (Favoriten moeglich; "
                 "audio/cfg/all: HTTP %s, %s)", self.host, status, art)

    async def _kopplung_nachholen(self, ws) -> None:
        """Kopplung beim Verbinden unklar: Die Verbindung dient nur zum Hoeren,
        die Pruefung wiederholt sich alle neu_versuch_s Sekunden. Gekoppelt ->
        Verbindung schliessen, run() verbindet ohne Pause neu und meldet sich
        an (die Anmeldung liest selbst und darf nicht neben dem Leser laufen).
        Nicht gekoppelt -> Favoriten anfordern und neu zeichnen."""
        while self.paired is None and not ws.closed and not self._stop:
            await asyncio.sleep(self.neu_versuch_s)
            await self._check_paired()
        if ws.closed or self._stop:
            return
        if self.paired:
            self._sofort_neu = True
            await ws.close()
        else:
            await self._favs_anfordern()
            if self._on_change:
                self._on_change()

    async def _get_jwt(self) -> str:
        """Aktuelles Miniserver-JWT vom Server holen (fuer die Anmeldung)."""
        if self._token_provider is None:
            return ""
        tok = self._token_provider()
        if asyncio.iscoroutine(tok):
            tok = await tok
        return tok or ""

    async def _authenticate(self, ws) -> None:
        """Am gekoppelten Audioserver anmelden wie die Loxone-App: Banner ->
        Session-Token, audio/cfg/getkey -> RSA-Schluessel, dann
        secure/authenticate. Ereignisse waehrend des Handshakes werden normal
        verarbeitet. Setzt self.authed. Fehler werden nur geloggt, die
        Verbindung bleibt zum Hoeren bestehen."""
        self.authed = False
        if not _auth.HAVE_CRYPTO:
            log.warning("Audioserver %s: Paket 'cryptography' fehlt, keine Anmeldung "
                        "(Favoriten/Steuerung ueber 7091 nicht moeglich)", self.host)
            return
        user = self.user
        jwt = await self._get_jwt()
        if not (user and jwt):
            log.debug("Audioserver %s: kein Benutzer/Token fuer die Anmeldung", self.host)
            return

        async def read_until(key, secs):
            loop = asyncio.get_event_loop(); end = loop.time() + secs
            while loop.time() < end:
                try:
                    m = await asyncio.wait_for(ws.receive(), timeout=max(0.1, end - loop.time()))
                except asyncio.TimeoutError:
                    return None
                if m.type != aiohttp.WSMsgType.TEXT:
                    return None
                greet = _auth.parse_greeting(m.data)
                if greet:
                    return {"__greeting__": greet}
                try:
                    data = json.loads(m.data)
                except (ValueError, TypeError):
                    continue
                if key in data:
                    return data
                # Ereignisse (Cover/Titel) nicht verlieren
                if self._handle(m.data) and self._on_change:
                    self._on_change()
            return None

        greet = await read_until("__greeting__", 4)
        token = (greet or {}).get("__greeting__", {}).get("token") if greet else None
        if not token:
            log.warning("Audioserver %s: kein Banner mit Session-Token", self.host); return
        await ws.send_str("audio/cfg/getkey")
        gk = await read_until("getkey_result", 5)
        pubkey = _auth.public_key_from_getkey(gk) if gk else None
        if pubkey is None:
            log.warning("Audioserver %s: kein RSA-Schluessel (getkey)", self.host); return
        try:
            cmd = _auth.build_authenticate(user, jwt, token, pubkey)
        except Exception as err:
            log.warning("Audioserver %s: Anmeldebefehl nicht baubar: %s", self.host, err); return
        await ws.send_str(cmd)
        res = await read_until("authenticate_result", 6)
        result = _auth.auth_result(res) if res else None
        self.authed = (result == _auth.AUTH_OK)
        log.info("Audioserver %s: Anmeldung %s", self.host,
                 "erfolgreich (Favoriten/Steuerung ueber 7091)" if self.authed
                 else f"fehlgeschlagen ({result!r})")

    async def run(self, on_change=None) -> None:
        """Verbindungs-/Lese-Schleife mit Auto-Reconnect. `on_change` wird bei
        jeder Zustandsaenderung aufgerufen (setzt im Server _dirty)."""
        self._on_change = on_change
        while not self._stop:
            nachholen = None
            try:
                if self._session is None or self._session.closed:
                    self._session = aiohttp.ClientSession()
                await self._check_paired()
                # PFLICHT: Das Unterprotokoll "remotecontrol" anfordern (wie die
                # Loxone-App / der Miniserver-WS). Ohne es nimmt der ECHTE Loxone-
                # Audioserver die Verbindung zwar an, schweigt aber vollstaendig —
                # dann kaemen nie audio_event-Push-Nachrichten. Nachbauten (Sonn)
                # funktionieren mit und ohne, deshalb universell sicher.
                async with self._session.ws_connect(
                        self.url, timeout=8, heartbeat=30,
                        protocols=("remotecontrol",)) as ws:
                    self._ws = ws
                    log.info("Audioserver-Events verbunden (remotecontrol): %s", self.url)
                    # Gekoppelter Audioserver: erst anmelden, dann sind
                    # getroomfavs/roomfav-play auf dieser Verbindung moeglich.
                    if self.paired:
                        await self._authenticate(ws)
                        if self.authed:
                            await self._favs_anfordern()
                            if self._on_change:
                                self._on_change()   # Ansicht ggf. mit Favoriten neu rendern
                    elif self.paired is None:
                        # Kopplung unklar: nur hoeren, Pruefung nachholen
                        nachholen = asyncio.create_task(self._kopplung_nachholen(ws))
                    async for m in ws:
                        if m.type == aiohttp.WSMsgType.TEXT:
                            if self._handle(m.data) and self._on_change:
                                self._on_change()
                        elif m.type in (aiohttp.WSMsgType.CLOSED,
                                        aiohttp.WSMsgType.ERROR):
                            break
            except Exception as err:
                log.debug("Audioserver-Events (%s): %s", self.url, err)
            finally:
                if nachholen is not None:
                    nachholen.cancel()
            self._ws = None
            self.authed = False
            if self._stop:
                break
            if self._sofort_neu:
                self._sofort_neu = False
                continue
            await asyncio.sleep(self.neu_versuch_s)

    async def close(self) -> None:
        self._stop = True
        try:
            if self._ws is not None and not self._ws.closed:
                await self._ws.close()
        except Exception:
            pass
        try:
            if self._session is not None and not self._session.closed:
                await self._session.close()
        except Exception:
            pass
