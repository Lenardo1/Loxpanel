"""Verbindung zum Miniserver: Anmeldung mit Token und Erneuerung, der Dauer-Loop
mit wachsender Wartezeit (stream_task, reconnect), die Struktur (LoxAPP3.json)
uebernehmen und vergleichen, Werte aus dem WebSocket (_on_value), Befehle an
Bausteine (command, auch gesichert mit Visu-PIN), HTTP an den Miniserver
(_ms_http, _ms_jdev) und die gesicherten Details (secured_details, etwa der
SIP-Zugang der Intercom).

Die Methoden sind ein Mixin (Miniserver): App erbt sie und arbeitet mit ihnen auf ihrem
Zustand (self ist die App). Importiert webvisu nicht."""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import ssl as _ssl
import time
from urllib.parse import quote

import aiohttp
from loxone_api import LoxoneClient

import loxone_secure
from bausteine.gemeinsam import INTERCOM_TYPES
from konfig import (
    _config, _intercom_config, _ms_antwortfrist, MS_CMD_TIMEOUT, _ms_keepalive_abstand)
from loxone_ws import LoxoneWS, ms_ssl_kontext

log = logging.getLogger("loxpanel.webvisu")   # derselbe Logger wie der Server: die Methoden gehoeren zu App


def _ms_https(port) -> bool:
    """Schema-Wahl fuer den Miniserver: Loxone Gen1 spricht nur HTTP (Port 80),
    Gen2+ nutzt HTTPS/TLS (443, …). Port 80 -> HTTP/ws, sonst HTTPS/wss."""
    try:
        return int(port) != 80
    except (TypeError, ValueError):
        return True


def _make_client(host, user, password, port, verify_tls) -> LoxoneClient:
    """LoxoneClient bauen und bei Gen1 (Port 80) auf HTTP umstellen – die
    loxone_api setzt die Basis-URL sonst fest auf https://…"""
    c = LoxoneClient(host=host, user=user, password=password, port=port, verify_tls=verify_tls)
    if not _ms_https(port):
        c.base_url = f"http://{host}:{port}/"
    return c


TOKEN_RENEW_MIN = 60     # s: nicht oefter neu anmelden (401 kann auch fehlende Rechte heissen)

MS_RETRY = (5, 10, 20, 40, 60)   # s: Wartezeiten zwischen Verbindungsversuchen zum Miniserver

EINRICHTUNG_FEHLER_MAX = 160     # Zeichen des Verbindungsfehlers im Einrichtungshinweis (Panel 480 px)

# msInfo.miniserverType laut Strukturdoku (Structure File 17.1, msInfo)
MS_TYPEN = {0: "Miniserver (Gen 1)", 1: "Miniserver Go (Gen 1)", 2: "Miniserver (Gen 2)",
            3: "Miniserver Go (Gen 2)", 4: "Miniserver Compact"}


def _ms_unerreichbar(err: BaseException) -> bool:
    """Scheiterte die Pruefung eines Zugangs, weil der Miniserver nicht
    antwortete (Zeitlimit, Verbindung, Namensaufloesung)? Dann ist offen, ob
    der Zugang stimmt. Hat er geantwortet und abgelehnt (Kennwort, Benutzer,
    Zertifikat, keine Loxone-Antwort), steht fest, dass er so nicht geht."""
    if isinstance(err, (aiohttp.ClientSSLError, _ssl.SSLError)):
        return False
    return isinstance(err, (asyncio.TimeoutError, aiohttp.ClientConnectionError, OSError))


class ZugangFehler(Exception):
    """Gesicherte Details (Zugangsdaten) nicht zu bekommen; der Text nennt den
    Grund so, dass ihn der Konfigurator anzeigen kann."""


KEIN_SIP = "Die Intercom nennt keinen SIP-Zugang"

KEINE_GESICHERTEN = "Der Baustein hat keine gesicherten Details"


class OhneGesicherteDetails(ZugangFehler):
    """Der Miniserver hat fuer den Baustein keine gesicherten Details, es liegt
    also nicht an Verbindung oder Rechten."""

    def __init__(self):
        super().__init__(KEINE_GESICHERTEN)


class Miniserver:
    """Verbindung, Struktur und Befehle; Mixin der App (self ist die App)."""

    def _ssl_ctx(self) -> _ssl.SSLContext:
        return ms_ssl_kontext(self.verify_tls)

    def _apply_structure(self, st: dict) -> None:
        self.controls = st.get("controls", {})
        self.rooms = st.get("rooms", {})
        self.cats = st.get("cats", {})
        # Audioserver-Adressen fuer den Gen-2-Event-Kanal: {serverUUID: "host:port"}
        ms = st.get("mediaServer") or {}
        self.mediaservers = {u: (v or {}).get("host", "")
                             for u, v in ms.items() if isinstance(v, dict) and (v or {}).get("host")}
        # Standort des Miniservers (Loxone setzt latitude/longitude immer, fuer
        # Astro/Sonnenstand) -> Wetter ohne Konfiguration (Fallback fuer loxpanel.cfg).
        info = st.get("msInfo") or {}
        try:
            self.ms_lat = float(info["latitude"]) if info.get("latitude") not in (None, "") else None
            self.ms_lon = float(info["longitude"]) if info.get("longitude") not in (None, "") else None
        except (TypeError, ValueError, KeyError):
            self.ms_lat = self.ms_lon = None
        self.ms_location = str(info.get("location") or "").strip()
        # Fuer das Diagnosepaket: was die Struktur ueber den Miniserver sagt
        # (msInfo laut Strukturdoku; eine Firmware-Version nennt sie nicht)
        self.ms_struktur = {"typ": MS_TYPEN.get(info.get("miniserverType"), info.get("miniserverType")),
                            "name": info.get("msName") or "", "projekt": info.get("projectName") or "",
                            "stand": st.get("lastModified") or ""}
        self.rooms_with = sorted(
            {c.get("room") for c in self.controls.values() if c.get("room") in self.rooms},
            key=lambda r: self.rooms[r].get("name", ""))
        self.cats_with = sorted(
            {c.get("cat") for c in self.controls.values() if c.get("cat") in self.cats},
            key=lambda c: self.cats[c].get("name", ""))
        self.bell_map = {}
        self.alarm_map = {}
        # Betriebsarten (id -> Name) fuer die Wecker-Wiederholung: die `modes`
        # eines Eintrags verweisen hierauf (z.B. Wochentage Mo-So).
        self.op_modes = {str(k): v for k, v in (st.get("operatingModes") or {}).items()}
        # Globale States der Anlage (Name -> UUID): u.a. Sonnenauf-/-untergang und
        # die aktiven Betriebsmodi. Die Werte kommen ueber den WS-Stream in
        # self.states. Roh uebernehmen, die Belegung ist je Anlage verschieden.
        self.global_states = dict(st.get("globalStates") or {})
        # Loxone-Wetterdienst: nur vorhanden, wenn die Anlage ihn gebucht hat.
        # Enthaelt die State-UUIDs (actual/forecast), die Wetterlage-Texte und
        # die Formatstrings mit den Einheiten. Der Wetterpuffer gehoert zu diesen
        # UUIDs und wird mit der Struktur zusammen verworfen.
        wsrv = st.get("weatherServer")
        self.weather_cfg = wsrv if isinstance(wsrv, dict) else {}
        self._lox_wx = {}
        # Neue Struktur heisst meist: in Loxone Config gespeichert. Die Kamera
        # der Intercoms kann sich geaendert haben, also neu fragen.
        self.ms_video = {}
        self.playerid_by_action = {}
        self.audiohost_by_action = {}
        for _u, _c in self.controls.items():
            if _c.get("type") in INTERCOM_TYPES:
                _bu = (_c.get("states") or {}).get("bell")
                if _bu:
                    self.bell_map[_bu] = _u
            elif _c.get("type") == "AlarmClock":
                _au = (_c.get("states") or {}).get("isAlarmActive")
                if _au:
                    self.alarm_map[_au] = _u
            elif _c.get("type") in ("AudioZone", "AudioZoneV2"):
                # Beide Zonentypen werden direkt am Audioserver (7091) gesteuert:
                # AudioZone -> Musikserver, AudioZoneV2 -> Audioserver Gen2 (Sonn).
                # Der Umweg ueber den Miniserver (sps/io) reicht roomfav/play NICHT
                # zuverlaessig durch; der Direktkanal (auch beim Sonn, ohne Token
                # getestet) funktioniert fuer play/pause/next/volume/roomfav.
                _det = _c.get("details") or {}
                _pid = _det.get("playerid")
                _ua = _c.get("uuidAction")
                if _ua and _pid is not None:
                    self.playerid_by_action[_ua] = int(_pid)
                    _hp = self.mediaservers.get(_det.get("server"))
                    if _hp:
                        self.audiohost_by_action[_ua] = _hp.split(":")[0].strip()
        self._presence_rebuild()
        log.info("Struktur: %d Controls, %d Räume, %d Kategorien, %d Intercom-Klingeln, %d Wecker, %d AudioZones",
                 len(self.controls), len(self.rooms_with), len(self.cats_with),
                 len(self.bell_map), len(self.alarm_map), len(self.playerid_by_action))

    @staticmethod
    def _structure_sig(st: dict) -> str:
        """Signatur der Loxone-Struktur (Controls/Raeume/Kategorien). Aendert sich
        nur bei Config-Aenderungen (Namen, neue/entfernte Controls …), nicht bei
        State-Werten – die kommen separat ueber den WS-Stream."""
        try:
            rel = {"controls": st.get("controls", {}), "rooms": st.get("rooms", {}),
                   "cats": st.get("cats", {})}
            raw = json.dumps(rel, sort_keys=True, ensure_ascii=False, default=str)
            return hashlib.md5(raw.encode("utf-8")).hexdigest()
        except (TypeError, ValueError):
            return ""

    def _adopt_structure(self, st: dict) -> bool:
        """Struktur anwenden und melden, ob sie sich seit der letzten Verbindung
        geaendert hat (Grundlage fuer den Panel-Reload). Beim allerersten Anwenden
        (`_struct_sig` noch None) gilt sie nie als 'geaendert' — frisch verbundene
        Panels holen sich die Ansichten ohnehin neu."""
        sig = self._structure_sig(st)
        changed = bool(self._struct_sig and sig and sig != self._struct_sig)
        self._apply_structure(st)
        self._struct_sig = sig
        return changed

    async def _refresh_structure(self) -> bool:
        """Struktur neu vom Miniserver laden und anwenden, WENN sie sich geaendert
        hat (Loxone-Config geaendert). Gibt True bei Aenderung zurueck. Rein lesend;
        Fehler werden vom Aufrufer isoliert, damit die Verbindungs-Schleife lebt."""
        if self.client is None:
            return False
        st = await self.client.load_structure()
        if not self._adopt_structure(st):
            return False                      # unveraendert -> nichts tun (kein Panel-Reload)
        self.states = {}                      # nach Struktur-Wechsel States frisch (MS sendet neu)
        self._dirty = True
        return True

    async def start(self) -> None:
        try:
            self.client = _make_client(self.host, self.user, self.password,
                                       self.port, self.verify_tls)
            await self.client.__aenter__()
            self.alg = (await self.client.getkey2()).hashAlg
            self._set_token(await self.client.authenticate())
            self._ms_pubkey = None
            st = await self.client.load_structure()
            # Reconnect nach Miniserver-Reboot (z.B. Loxone-Config hochgeladen):
            # hat sich die Struktur geaendert, Panels neu laden lassen. Beim
            # allerersten Start ist _struct_sig None -> kein Reload.
            if self._adopt_structure(st):
                self._pending_reload = True
            self.icon_session = aiohttp.ClientSession(
                connector=aiohttp.TCPConnector(ssl=await asyncio.to_thread(self._ssl_ctx)))
            await self._connect_ws()
            log.info("Mit Miniserver verbunden (%s).", self.host)
        except Exception:
            await self._close_conn()   # sauber zuruecksetzen, damit Retry neu aufbaut
            raise

    async def _close_conn(self) -> None:
        for c in (self.ws, self.icon_session, self.client):
            try:
                if c:
                    await c.close()
            except Exception:
                pass
        self.ws = self.icon_session = self.client = None

    def _zugang_setzen(self, ms: dict) -> None:
        """Zugang fuer die naechste Anmeldung uebernehmen (verbindet nicht)."""
        self.host, self.port = ms["host"], ms.get("port", 443)
        self.user, self.password = ms["user"], ms["pass"]
        self.verify_tls = ms.get("verify_tls", False)
        self._zugang_neu = None

    async def reconnect(self, ms: dict | None = None) -> int:
        """Verbindung mit (ge-aenderter) Config neu aufbauen, mit `ms` statt
        _config(), wenn ein Zugang erst geprueft wird (api_settings_ms). Gibt
        Control-Anzahl zurueck; wirft bei falschen Zugangsdaten, TimeoutError,
        wenn die Anmeldung laenger als _ms_antwortfrist() braucht. Alte
        Verbindung bleibt bei Fehler bestehen (neuer Client wird nur bei Erfolg
        uebernommen)."""
        ms = _config() if ms is None else ms
        missing = [k for k in ("host", "user", "pass") if not ms.get(k)]
        if missing:
            raise ValueError(
                "Miniserver-Konfiguration unvollstaendig (fehlt: "
                + ", ".join(missing) + "). Bitte unter Einstellungen -> "
                "Miniserver Host, Benutzer und Passwort eintragen.")
        frist = _ms_antwortfrist()
        newc = _make_client(ms["host"], ms["user"], ms["pass"],
                            ms.get("port", 443), ms.get("verify_tls", False))
        try:
            await newc.__aenter__()
            alg = (await asyncio.wait_for(newc.getkey2(), frist)).hashAlg
            jwt = await asyncio.wait_for(newc.authenticate(), frist)
            st = await newc.load_structure()
            # Kontext der icon_session schon hier (CAs laden blockiert -> Thread),
            # damit die Uebernahme unten ohne await durchlaeuft.
            ssl_ctx = await asyncio.to_thread(ms_ssl_kontext, ms.get("verify_tls", False))
        except Exception as err:
            try:
                await newc.close()
            except Exception:
                pass
            if isinstance(err, asyncio.TimeoutError) and not str(err):   # Frist von wait_for
                raise TimeoutError(f"keine Antwort innerhalb von {frist:g} s") from err
            raise
        # Erfolg -> uebernehmen
        self._zugang_setzen(ms)
        old_client, self.client = self.client, newc
        self.alg = alg
        self._set_token(jwt)
        self._ms_pubkey = None
        # Anderer/geaenderter Miniserver -> Struktur evtl. anders, dann Panels neu laden.
        if self._adopt_structure(st):
            self._pending_reload = True
        self.states = {}
        old_is, self.icon_session = self.icon_session, \
            aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=ssl_ctx))
        self.icon_cache, self.bell_cache = {}, {}
        self.stat_cache, self.stat2_cache, self.stat_memo = {}, {}, {}   # anderer Miniserver -> andere Verlaeufe
        self.stat_gen += 1
        old_ws, self.ws = self.ws, None   # stream_task baut WS mit neuen Daten neu auf
        self.intercom_cfg = _intercom_config()
        self._dirty = True
        for closer in (old_client, old_is, old_ws):
            try:
                if closer:
                    await closer.close()
            except Exception:
                pass
        return len(self.controls)

    async def _connect_ws(self) -> None:
        self.ws = LoxoneWS(host=self.host, port=self.port, user=self.user, jwt=self.jwt,
                           hash_alg=self.alg, verify_tls=self.verify_tls,
                           secure=_ms_https(self.port), antwortfrist=_ms_antwortfrist(),
                           keepalive_abstand=_ms_keepalive_abstand())
        await self.ws.connect()

    def _set_token(self, jwt: str) -> None:
        self.jwt = jwt
        self._auth_gen += 1
        self._auth_at = time.monotonic()

    async def _reauth(self) -> None:
        # Token erneuern (kann nach langer Laufzeit ablaufen)
        if self.client:
            self._set_token(await self.client.authenticate())

    async def _renew_token(self, seen_gen: int) -> bool:
        """Nach einem 401 neu anmelden. Hat eine parallele Anfrage das schon
        getan (Zaehler weiter als seen_gen), genuegt es, erneut zu senden. Innerhalb
        von TOKEN_RENEW_MIN nach der letzten Anmeldung nicht noch einmal: dann liegt
        der 401 nicht am Token. -> True, wenn sich ein Neuversuch lohnt."""
        async with self._auth_lock:
            if self._auth_gen != seen_gen:
                return True
            if not self.client or time.monotonic() - self._auth_at < TOKEN_RENEW_MIN:
                return False
            self._auth_at = time.monotonic()     # auch ein Fehlversuch sperrt fuer TOKEN_RENEW_MIN
            try:
                self._set_token(await self.client.authenticate())
            except Exception as err:            # z. B. Passwort geaendert, Miniserver startet neu
                log.warning("Neuanmeldung am Miniserver fehlgeschlagen: %s", err or type(err).__name__)
                return False
            log.info("Miniserver-Token abgelaufen -> neu angemeldet")
            return True

    async def _ms_http(self, path: str, timeout: float, renew: bool = True) -> tuple[int, bytes, str]:
        """GET an den Miniserver mit dem aktuellen Token; bei 401 (und renew)
        einmal neu anmelden und wiederholen. -> (HTTP-Status, Inhalt, Content-Type). Wirft
        ConnectionError ohne Verbindung, sonst aiohttp.ClientError/TimeoutError."""
        async def once() -> tuple[int, bytes, str]:
            if self.icon_session is None:
                raise ConnectionError("keine Verbindung zum Miniserver")
            scheme = "https" if _ms_https(self.port) else "http"
            headers = {"Authorization": f"Bearer {self.jwt}"} if self.jwt else {}
            async with self.icon_session.get(f"{scheme}://{self.host}:{self.port}/{path.lstrip('/')}",
                                             headers=headers,
                                             timeout=aiohttp.ClientTimeout(total=timeout)) as r:
                return r.status, await r.read(), r.headers.get("Content-Type", "")
        gen = self._auth_gen
        res = await once()
        if res[0] == 401 and renew and await self._renew_token(gen):
            res = await once()
        return res

    async def _ms_jdev(self, path: str, timeout: float = MS_CMD_TIMEOUT,
                       renew: bool = True) -> tuple[str, object]:
        """jdev-Befehl ueber _ms_http. -> (Code, LL.value); Code ist der
        LL-Code der Antwort, ohne lesbares JSON der HTTP-Status."""
        status, body, _ = await self._ms_http("jdev/" + path.lstrip("/"), timeout, renew)
        try:
            ll = json.loads(body.decode("utf-8", "replace").lstrip("\ufeff").strip("\x00")).get("LL") or {}
        except (ValueError, AttributeError):
            ll = {}
        code = ll.get("Code") or ll.get("code")
        return (str(code) if code is not None else str(status)), ll.get("value")

    async def secured_details(self, uuid: str) -> dict:
        """Gesicherte Details eines Bausteins (securedDetails), etwa Kamera- und
        SIP-Zugang einer Intercom. Der Miniserver gibt sie nur auf einen
        verschluesselten Befehl heraus (loxone_secure), die Anmeldung steckt im
        Befehl. Lehnt er ab (HTTP 401: Schluessel nicht mehr gueltig, oder LL-Code
        401: Token abgelaufen), einmal mit frischem Schluessel und Token.
        Gefragt wird nur, wenn der Baustein in der Struktur das Kennzeichen
        securedDetails traegt (Strukturdoku, Controls: "indicates that there is
        sensitive information available").
        -> dict; wirft ZugangFehler mit einem Grund fuer den Konfigurator."""
        if not loxone_secure.HAVE_CRYPTO:
            raise ZugangFehler("Paket 'cryptography' fehlt")
        for versuch in range(2):
            if self.icon_session is None or not self.jwt:
                raise ZugangFehler("Keine Verbindung zum Miniserver")
            if not (self.controls.get(uuid) or {}).get("securedDetails"):
                raise OhneGesicherteDetails()
            gen = self._auth_gen
            try:
                if self._ms_pubkey is None:
                    code, wert = await self._ms_jdev("sys/getPublicKey")
                    self._ms_pubkey = loxone_secure.public_key_from_pem(wert)
                    if self._ms_pubkey is None:
                        raise ZugangFehler(f"Der Miniserver liefert keinen Schlüssel (Code {code})")
                code, key_hex = await self._ms_jdev("sys/getkey")
                if code != "200" or not isinstance(key_hex, str):
                    raise ZugangFehler(f"Der Miniserver liefert keinen Anmeldeschlüssel (Code {code})")
                cmd = (f"jdev/sps/io/{uuid}/securedDetails?autht="
                       f"{loxone_secure.token_hash(key_hex, self.jwt, self.alg)}&user={quote(self.user or '', safe='')}")
                enc = loxone_secure.encrypt_command(cmd, self._ms_pubkey)
                status, body, _ = await self._ms_http(enc.pfad, MS_CMD_TIMEOUT, renew=False)
            except ZugangFehler:
                raise
            except (aiohttp.ClientError, asyncio.TimeoutError, ConnectionError, ValueError) as err:
                raise ZugangFehler(f"Miniserver nicht erreichbar ({err or type(err).__name__})") from err
            if status == 401:
                self._ms_pubkey = None
                if versuch == 0:
                    await self._renew_token(gen)
                    continue
                raise ZugangFehler("Der Miniserver lehnt die verschlüsselte Anfrage ab")
            if status != 200:
                raise ZugangFehler(f"Der Miniserver antwortet mit HTTP {status}")
            try:
                ll = json.loads(loxone_secure.decrypt_response(body, enc.key, enc.iv).lstrip("\ufeff")).get("LL") or {}
            except (ValueError, AttributeError) as err:
                raise ZugangFehler("Die Antwort des Miniservers lässt sich nicht entschlüsseln") from err
            code = str(ll.get("Code") or ll.get("code") or "")
            if code == "401" and versuch == 0 and await self._renew_token(gen):
                continue
            if code == "401":
                raise ZugangFehler("Der Miniserver lehnt die Anmeldung von LoxPanel ab (Code 401)")
            if code == "403":
                raise ZugangFehler("Der Benutzer von LoxPanel darf diese Zugangsdaten nicht lesen "
                                   "(Rechte in Loxone Config)")
            if code != "200":
                raise ZugangFehler(f"Der Miniserver antwortet mit Code {code or '?'}")
            wert = ll.get("value")
            if isinstance(wert, str):
                try:
                    wert = json.loads(wert)
                except ValueError as err:
                    raise ZugangFehler("Die gesicherten Details sind kein JSON") from err
            if not isinstance(wert, dict):
                raise OhneGesicherteDetails()
            return wert
        raise ZugangFehler("Der Miniserver lehnt die verschlüsselte Anfrage ab")

    async def command(self, uuid: str, cmd: str, pin: str | None = None) -> str | None:
        """Fuehrt einen Befehl aus. Mit pin: gesicherter Befehl (Visu-Passwort)."""
        if not (self.client and uuid and cmd):
            return None
        try:
            if pin is not None:
                return await self._secured_command(uuid, cmd, pin)
            # AudioZone-Steuerung: Ein mit dem Miniserver GEKOPPELTER Loxone-
            # Audioserver lehnt Befehle auf Port 7091 OHNE Anmeldung ab
            # ("command not allowed when paired") und schliesst die Verbindung.
            # Transportbefehle (play/pause/next/prev/volume/{n}) laufen bei ihm
            # deshalb ueber den Miniserver (sps/io/{uuid}/{cmd}), wie in
            # audioserver_events.py dokumentiert und an der echten Anlage
            # (LWSS 17.2) verifiziert. Nur ein NACHWEISLICH nicht gekoppelter
            # Audioserver (Nachbau Sonn/MS4H bzw. Musikserver Gen 1, paired=False)
            # nimmt Direktbefehle an -> dann direkt an Port 7091
            # (audio/{playerid}/{cmd}, schneller, und roomfav/play laeuft dort
            # ohne Anmeldung). Ist der Kopplungsstatus (noch) unbekannt
            # (Event-Client noch nicht gesondet, HTTP-Probe fehlgeschlagen oder
            # audiometa aus), wird sicher ueber den Miniserver geleitet. Ausnahme
            # roomfav/get: immer ueber den Miniserver, sie befuellt den
            # sourceList-State fuer die Anzeige.
            pid = self.playerid_by_action.get(uuid)
            host = self.audiohost_by_action.get(uuid)
            acl = self.audio_clients.get(host) if host else None
            # Direkt an den Audioserver nur bei positiv bekanntem Nachbau
            # (acl.paired is False). None (unbekannt) / kein Event-Client /
            # gekoppelt -> Miniserver.
            direct_ok = acl is not None and acl.paired is False
            # Raumfavorit abspielen: bei einem gekoppelten Audioserver ueber die
            # angemeldete Ereignis-Verbindung (der Direktkanal ohne Anmeldung
            # wuerde die Verbindung schliessen). Nachbauten (authed=False)
            # ueberspringen das und spielen unten direkt ab (direct_ok).
            if pid is not None and cmd.startswith("roomfav/play/"):
                if acl is not None and acl.authed:
                    ok = await acl.play_roomfav(pid, cmd.rsplit("/", 1)[-1])
                    return "200" if ok else None
            if pid is not None and not cmd.startswith("roomfav/get") and direct_ok:
                backend = self._audio_backend_for(uuid)
                if backend:
                    ok = await backend.command(pid, cmd)
                    return "200" if ok else None
                log.warning("AudioZone-Befehl ohne Audio-Backend (uuid=%s, cmd=%s)", uuid, cmd)
                return None
            # Miniserver: gekoppelte Zonen (Transport + roomfav-Fallback),
            # unbekannter Kopplungsstatus, roomfav/get und Nicht-Audio-Befehle.
            code, _ = await self._ms_jdev(f"sps/io/{uuid}/{cmd}")
            if code == "200":
                log.info("cmd %s/%s", uuid, cmd)
            else:
                log.warning("cmd %s/%s -> Code %s", uuid, cmd, code)
            return code
        except Exception as err:  # Befehl darf den Server nicht killen
            log.warning("cmd %s/%s fehlgeschlagen: %s", uuid, cmd, err or type(err).__name__)
            return None

    async def _secured_command(self, uuid: str, cmd: str, pin: str) -> str | None:
        """Loxone secured-command: getvisusalt -> Hash(visuPw:salt) -> HMAC(key) -> ios."""
        # Ein abgelaufenes Token faellt hier auf (und wird erneuert), nicht erst
        # beim ios-Aufruf: dort hiesse ein Fehler "Visu-Passwort falsch".
        _, val = await self._ms_jdev(f"sys/getvisusalt/{quote(self.user)}")
        val = val if isinstance(val, dict) else {}
        key, salt = val.get("key", ""), val.get("salt", "")
        alg = (val.get("hashAlg") or "SHA1").upper()
        digest = hashlib.sha256 if alg == "SHA256" else hashlib.sha1
        pwhash = digest(f"{pin}:{salt}".encode()).hexdigest().upper()
        h = hmac.new(bytes.fromhex(key), pwhash.encode(), digest).hexdigest()
        # Der Hash gilt nur einmal, und ein Fehler hier heisst meist falsches
        # Visu-Passwort -> nicht neu anmelden (das Token war eben noch gueltig).
        code, _ = await self._ms_jdev(f"sps/ios/{h}/{uuid}/{cmd}", renew=False)
        log.info("secured cmd %s/%s -> Code %s", uuid, cmd, code)
        return code

    def _on_value(self, uuid: str, value: object) -> None:
        self.states[uuid] = value
        self._dirty = True
        if uuid in self.bell_map:
            if value and not self._bell_prev.get(uuid):
                self._pending_ring = self.bell_map[uuid]
            self._bell_prev[uuid] = value
        if uuid in self.alarm_map:
            now = bool(value)
            if now != bool(self._alarm_prev.get(uuid)):
                # Beide Flanken pushen: 0->1 startet den Weckton, 1->0 (z.B. in
                # Loxone/App oder am Panel quittiert) stoppt ihn wieder.
                self._pending_alarm.append({"id": self.alarm_map[uuid], "on": now})
            self._alarm_prev[uuid] = value
        if uuid in self.presence_map:
            # Praesenzmelder: jemand kommt -> Display an und halten, Raum leer
            # -> aus. Nur bei echtem Wechsel, damit der Neuversand aller States
            # nach einem Reconnect nichts schaltet.
            on = bool(value)
            for name in self.presence_map[uuid]:
                if on != self._presence_on.get(name, False):
                    self._presence_on[name] = on
                    self._pending_presence.append({"dev": name, "on": on, "presence": on})

    async def stream_task(self) -> None:
        # Dauer-Loop: Erstverbindung + Reconnect zum Miniserver. Bricht NIEMALS
        # den HTTP-Server ab — auch wenn der Miniserver (noch) nicht erreichbar
        # oder das Passwort falsch ist (dann bleibt /settings bedienbar).
        # Wartezeit zwischen Versuchen waechst (MS_RETRY). Von vorn beginnt sie
        # erst, wenn eine Verbindung mindestens so lange Daten lieferte wie die
        # laengste Wartezeit (LoxoneWS.lebenszeit()) - sonst liefe ein
        # Miniserver, der sofort wieder trennt, in eine Anmeldung alle paar
        # Sekunden. Offen sein allein genuegt nicht: Eine stumme Verbindung
        # endet erst nach keepalive_interval + response_timeout, im Betrieb
        # laenger als MS_RETRY[-1].
        retry, verbunden = 0, None
        while True:
            try:
                if self._zugang_neu is not None and self.client is None:
                    self._zugang_setzen(self._zugang_neu)   # beim Speichern nicht erreichbar gewesen
                if not self.host:
                    # Noch kein Miniserver konfiguriert -> auf /settings warten
                    # (kein Verbindungsversuch, kein Log-Spam).
                    await asyncio.sleep(5)
                    continue
                if self.client is None:
                    await self.start()          # Erstverbindung / nach hartem Reset
                elif self.ws is None:
                    # Reiner WS-Neuaufbau (z.B. nach Miniserver-Reboot durch eine
                    # Loxone-Config-Aenderung): Struktur mitziehen, damit neue/
                    # umbenannte Controls ohne LoxPanel-Neustart erscheinen. Fehler
                    # isoliert -> Reconnect scheitert nie an der Struktur.
                    try:
                        if await self._refresh_structure():
                            self._pending_reload = True   # Panels neu laden lassen
                            log.info("Loxone-Struktur geaendert -> uebernommen, Panels werden neu geladen")
                    except Exception:
                        log.exception("Struktur-Refresh beim Reconnect uebersprungen")
                    await self._connect_ws()    # WS neu (Settings-Reconnect / nach Abriss)
                verbunden = self.ws
                self._ms_fehler = ""
                self._ms_weg_seit = None   # angemeldet, der Voll-Dump kommt gleich
                self._ms_verbunden_seit = time.time()
                await self.ws.stream(self._on_value, self._on_weather)
                raise ConnectionError("WS-Stream regulär beendet")
            except asyncio.CancelledError:
                raise
            except Exception as err:
                if verbunden is not None and verbunden.lebenszeit() >= MS_RETRY[-1]:
                    retry = 0
                if verbunden is not None and verbunden.letzte_nachricht is not None:
                    # letzte Nachricht (monotone Uhr) als Uhrzeit fuer die Panels
                    self._ms_bestaetigt = time.time() - (time.monotonic() - verbunden.letzte_nachricht)
                if self._ms_weg_seit is None:
                    self._ms_weg_seit = time.time()
                self._ms_verbunden_seit = None
                verbunden = None
                wait = MS_RETRY[min(retry, len(MS_RETRY) - 1)]
                retry += 1
                log.warning("Miniserver nicht verbunden (%s) — neuer Versuch in %ss", err, wait)
                text = " ".join(str(err).split()) or err.__class__.__name__
                self._ms_fehler = text if len(text) <= EINRICHTUNG_FEHLER_MAX \
                    else text[:EINRICHTUNG_FEHLER_MAX] + " …"
                try:
                    if self.ws:
                        await self.ws.close()
                except Exception:
                    pass
                self.ws = None
                try:
                    if self.client and self._zugang_neu is not None:
                        await self._close_conn()    # neuer Zugang gespeichert -> damit neu aufbauen
                    elif self.client:
                        await self._reauth()    # Token erneuern, Client behalten
                except Exception:
                    await self._close_conn()    # Client kaputt -> harter Reset (start() baut neu)
                await asyncio.sleep(wait)
