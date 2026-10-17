"""Geraete und Agenten: welche Ansicht ein Geraet zeigt (Zuordnung, Betriebsmodus,
Vorschau am Geraet, Entwurf aus dem Konfigurator), Kopplungscode fuer neue
Geraete, Anwesenheit, Display (Abschalten, Nacht, Neuladen, Skalierung,
Displaytreiber am Agenten), Agenten-Befehle und die Geraeteliste fuer den
Konfigurator; panels.json schreiben.

Die Methoden sind ein Mixin (Geraete): App erbt sie und arbeitet mit ihnen auf ihrem
Zustand (self ist die App). Importiert webvisu nicht."""
from __future__ import annotations

import asyncio
import json
import logging
import re
import secrets
import socket
import time
from datetime import datetime
from urllib.parse import quote

import aiohttp

from bausteine.gemeinsam import _clean
from konfig import (
    _atomic_write, _clean_kachelziel, _clean_scale, _kachel_vorschlag, load_panels, NACHT_STANDARD,
    NACHT_UHR_HELL_MIN, PANELS_FILE)

log = logging.getLogger("loxpanel.webvisu")   # derselbe Logger wie der Server: die Methoden gehoeren zu App


# Ziel, ueber das das Betriebssystem nach draussen routen wuerde (RFC 5737,
# TEST-NET-1: im Internet nie vergeben). connect() auf einem UDP-Socket sendet
# nichts, legt aber die Quelladresse fest - das ist die Adresse im Heimnetz.
_ROUTEN_PROBE = ("192.0.2.1", 9)


def _lan_adressen() -> list[str]:
    """IPv4-Adresse dieses Rechners im Netz (ohne 127.x), fuer den
    Einrichtungshinweis eines Panels, das die Visu ueber 127.0.0.1 laedt
    (die App auf dem Panel selbst). Leer, wenn es keine Route gibt."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(_ROUTEN_PROBE)
            adresse = s.getsockname()[0]
    except OSError:
        return []
    return [] if adresse.startswith("127.") or adresse == "0.0.0.0" else [adresse]


# Kiosk-Apps, die die Visu beim Verbinden meldet (?kiosk=): Fully Kiosk und die
# LoxPanel-App. Beide schalten das Display aus der Seite heraus (JS-Schnittstelle).
KIOSK_APPS = ("fully", "loxpanel")

# Panel-Agent (agent/loxpanel-agent.py): meldet sich alle AGENT_MELDETAKT s
# (time.sleep in announce_loop). Online heisst hoechstens drei Meldungen in
# Folge verpasst: eine verlorene Meldung (WLAN, Server kurz beschaeftigt) macht
# ein Panel nicht offline. Nur einem Agenten, der online ist, gilt ein Wechsel.
AGENT_MELDETAKT = 15

AGENT_ONLINE = 4 * AGENT_MELDETAKT

# s: Zeitlimit fuer Befehle an den Agenten (/start, /reload, /stop). Er wartet in
# stop_kiosk bis zu 5 s auf das alte Chromium, bevor er es abschiesst und das
# neue startet; 3 s Reserve dafuer und fuer die Antwort auf einem langsamen PX30.
AGENT_BEFEHL_TIMEOUT = 8

# Faehigkeit im Announce (features): der Agent uebernimmt "panel" aus der
# Antwort ohne Chromium-Neustart. Aeltere Agenten bekommen stattdessen /start.
AGENT_KANN_PANEL = "panel"

# Nachtmodus: Rueckfall-Fenster, wenn keine Sonnenzeiten vorliegen (kein Wetter
# konfiguriert). Sobald Sonnenauf-/-untergang bekannt sind, gelten die.
NIGHT_FROM, NIGHT_TO = "22:00", "06:00"

# Neuladen gegen Einfrieren ohne Agent (Android, Tablet): Ist reloadHours nicht
# eingestellt, laedt die Visu einmal je Nacht ab dieser Stunde neu, sobald ihre
# Uhr-Seite steht. Einzige Quelle: die theme-Nachricht bringt sie der Visu,
# /api/meta dem Konfigurator.
NEULADEN_STUNDE = 3

# Entwuerfe (Punkt 10 Teil 3): ein Profil, das der Konfigurator noch nicht
# gespeichert hat, laesst sich in der echten Visu ansehen (?entwurf=<Token>).
# Er liegt nur im Speicher: so viele gleichzeitig, so lange nach der letzten
# Nutzung; Speichern verwirft sie alle (die Visu laedt dabei neu).
ENTWURF_MAX = 8

ENTWURF_DAUER = 3600

# Vorschau am Geraet (Punkt 12): so lange zeigt ein Geraet einen Entwurf, wenn der
# Konfigurator ihn nicht mehr auffrischt - dann geht es zur vorigen Ansicht zurueck.
VORSCHAU_GERAET_DAUER = 900

# Kopplungscode eines Browsers ohne Geraetekennung: der Server vergibt ihn
# beim Verbinden (die Visu merkt ihn sich und schickt ihn beim naechsten
# Verbinden als ?code= zurueck), das Panel zeigt ihn unter "Dieses Geraet
# einrichten", Displays listet ihn, "Namen vergeben" trifft damit genau dieses
# Geraet (mehrere hinter einer IP). Alphabet ohne 0/O und 1/I.
KOPPLUNG_ZEICHEN = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"

KOPPLUNG_LAENGE = 4

_KOPPLUNG_RE = re.compile(r"^[A-HJ-NP-Z2-9]{4,8}$")


class Geraete:
    """Geraete, Agenten und Display; Mixin der App (self ist die App)."""

    def entwurf_ablegen(self, pid: str, roh: dict, token: str = "") -> tuple[str, list]:
        """Entwurf eines Profils (UI-Form, wie der Konfigurator es speichert)
        im Speicher ablegen -> (Token, nicht uebernommene Angaben). Geprueft wird
        wie beim Speichern (_sanitize_panels), geschrieben wird nichts. Mit dem
        Token eines vorhandenen Entwurfs desselben Profils wird dieser ersetzt,
        sonst entsteht ein neuer; ist der Platz voll, geht der aelteste."""
        clean = self._sanitize_panels({pid: roh})
        if pid not in clean:
            raise ValueError("Ansicht nicht brauchbar (leere oder mit _ beginnende Kennung?)")
        weg = self._panels_verworfen({pid: roh}, clean,
                                     {u: _clean(c.get("name")) or u for u, c in self.controls.items()})
        now = time.time()
        for t in [t for t, e in self.entwuerfe.items() if now - e["ts"] > ENTWURF_DAUER]:
            del self.entwuerfe[t]
        alt = self.entwuerfe.get(token)
        if not alt or alt["id"] != pid:
            token = secrets.token_urlsafe(9)
            while len(self.entwuerfe) >= ENTWURF_MAX:
                del self.entwuerfe[min(self.entwuerfe, key=lambda t: self.entwuerfe[t]["ts"])]
        self.entwuerfe[token] = {"id": pid, "panel": clean[pid], "ts": now}
        return token, weg

    def entwurf_profil(self, token: str, pid: str | None) -> dict | None:
        """Der Entwurf zu Token und Profil-Kennung, sonst None (unbekannt,
        abgelaufen oder fuer ein anderes Profil). Jede Nutzung verlaengert ihn."""
        e = self.entwuerfe.get(token or "")
        now = time.time()
        if not e or e["id"] != (pid or "") or now - e["ts"] > ENTWURF_DAUER:
            return None
        e["ts"] = now
        return e["panel"]

    def vorschau_zurueck(self, device: str) -> str:
        """Profil, zu dem ein Geraet nach der Vorschau zurueckkehrt: das, was es vor
        der ersten Vorschau zeigte (bleibt bei jeder weiteren Vorschau gleich)."""
        alt = self.vorschau_geraet.get(device)
        if alt:
            return alt["zurueck"]
        return next((p.get("id", "") for ws, p in self.conn_prof.items()
                     if self.conn_dev.get(ws) == device and not p.get("entwurf")), "")

    async def vorschau_beenden(self, device: str) -> int:
        """Die Vorschau am Geraet beenden: es kehrt zum Profil davor zurueck
        ({t:"switch"} ohne Entwurf). Nur Verbindungen, die den Entwurf noch zeigen -
        wurde das Geraet inzwischen anders umgeschaltet, bleibt es dabei. Zeigt ihn
        gerade keine (die Seite laedt noch neu, oder das Geraet ist offline), merkt
        sich der Server das Ende ohne Frist: ws_handler schickt die naechste Verbindung
        des Geraets mit diesem Token zurueck, auch nach einem langen WLAN-Ausfall.
        -> Anzahl (ein vorgemerktes Ende zaehlt mit)."""
        e = self.vorschau_geraet.pop(device, None)
        self.vorschau_ende.pop(device, None)
        if not e:
            return 0
        n, unterwegs = 0, False
        for ws, info in list(self.conn_info.items()):
            if info.get("dev") != device:
                continue
            if info.get("entwurf") == e["token"]:
                if await self._neu_laden(ws, {"t": "switch", "panel": e["zurueck"], "entwurf": ""}):
                    n += 1
            elif info.get("entwurfKommt") == e["token"]:
                unterwegs = True
        if unterwegs or not n:
            self.vorschau_ende[device] = {"token": e["token"], "zurueck": e["zurueck"]}
            n += 1
        return n

    def ansicht_wirksam(self, pid: str | None) -> str:
        """Die Ansicht, die die Visu fuer `pid` tatsaechlich zeigt (wie resolve_profile):
        eine leere, geloeschte oder vertippte Kennung zeigt das Standardprofil."""
        return pid if pid and pid in self.panels else "default"

    def _ui_roh(self, pid: str | None, roh: dict | None) -> dict:
        """ui des Profils `pid` aus der Datei, bei einem Entwurf (`roh`) aus ihm. Eine
        unbekannte Kennung gilt wie in der Visu als Standardprofil (ansicht_wirksam):
        sonst bekaeme ein Agent mit ?panel= leer oder geloescht nur die Vorgaben."""
        if roh is None:
            roh = self.panels.get(self.ansicht_wirksam(pid)) or {}
        return roh.get("ui") or {}

    def panel_dpms(self, pid: str | None, roh: dict | None = None, dev: str = ""):
        """Display-Abschaltzeit (Sek.) fuer ein Panel: am Geraet (devices[name].dpmsOff,
        Einrichtung Schritt 4: Display-Regeln stehen in den Vorgaben und am Geraet),
        sonst aus dem Profil (ein aelterer Eintrag ui.dpmsOff gilt weiter), sonst die
        Vorgabe (0=nie, None=nicht gesetzt -> Agent nutzt seinen kiosk.conf-Default).
        Wird dem Panel-Agenten in der Announce-Antwort mitgegeben (er fuehrt xset aus)."""
        d = self.devices.get(dev) if dev else None
        if isinstance(d, dict) and isinstance(d.get("dpmsOff"), (int, float)) and not isinstance(d.get("dpmsOff"), bool):
            return max(0, min(3600, int(d["dpmsOff"])))
        ui = {**self.theme.get("ui", {}), **self._ui_roh(pid, roh)}
        v = ui.get("dpmsOff")
        return max(0, min(3600, int(v))) if isinstance(v, (int, float)) else None

    def panel_night(self, pid: str | None, roh: dict | None = None, dev: str = "") -> dict:
        """Nachtmodus je Panel: `dim` = Abdunklung in Prozent (0 = aus), `wake` =
        Sekunden, die eine Beruehrung wieder voll aufhellt (0 = nicht aufhellen).
        Wie panel_dpms(): am Geraet (devices[name].nightDim/nightWake, Einrichtung
        Schritt 4b), sonst ein aelterer Eintrag des Profils, sonst die Vorgabe.
        Die Nacht-Uhr hat keinen Wert je Geraet."""
        ui = {**self.theme.get("ui", {}), **self._ui_roh(pid, roh)}
        d = self.devices.get(dev) if dev else None
        if isinstance(d, dict):
            ui = {**ui, **{k: d[k] for k in ("nightDim", "nightWake")
                           if isinstance(d.get(k), (int, float)) and not isinstance(d.get(k), bool)}}

        def _num(key, lo, hi, default):
            v = ui.get(key)
            return max(lo, min(hi, int(v))) if isinstance(v, (int, float)) else default

        uhr = ui.get("nightClock")
        return {"dim": _num("nightDim", 0, 90, NACHT_STANDARD["nightDim"]),
                "wake": _num("nightWake", 0, 300, NACHT_STANDARD["nightWake"]),
                # Nacht-Uhr statt der Uhr-Seite und ihre Helligkeit in Prozent
                "uhr": uhr if isinstance(uhr, bool) else NACHT_STANDARD["nightClock"],
                "uhrHell": _num("nightClockBright", NACHT_UHR_HELL_MIN, 100, NACHT_STANDARD["nightClockBright"])}

    def night_control_options(self) -> list:
        """Bausteine, die als Nacht-Ausloeser oder Praesenzmelder eines Geraets
        taugen: alles mit einem `active`-State
        (Switch, InfoOnlyDigital, PresenceDetector ...). Damit laesst sich auch ein
        Loxone-Betriebsmodus nutzen, sobald er in der Visu auf so einem Baustein
        liegt — der Modus selbst steht nicht in der Struktur (s. ARCHITEKTUR.md)."""
        out = []
        for u, c in self.controls.items():
            if not (c.get("states") or {}).get("active"):
                continue
            name = _clean(c.get("name"))
            if not name:
                continue
            out.append({"uuid": u, "name": name, "type": c.get("type"),
                        "room": _clean((self.rooms.get(c.get("room")) or {}).get("name"))})
        return sorted(out, key=lambda d: (d["room"], d["name"]))

    def _sun_minutes(self) -> tuple[int, int] | None:
        """Sonnenauf-/-untergang als Minuten seit Mitternacht (Ortszeit).

        Rangfolge: zuerst der MINISERVER (globalStates `sunrise`/`sunset` liefern
        genau dieses Format), sonst der Wetterdienst aus den Front-Daten ("HH:MM").
        None, wenn keine Quelle brauchbare Werte hat."""
        gs = self.global_states or {}
        ms = []
        for key in ("sunrise", "sunset"):
            u = gs.get(key)
            v = self.states.get(u) if isinstance(u, str) else None
            ms.append(int(v) if isinstance(v, (int, float)) and 0 <= v < 1440 else None)
        if ms[0] is not None and ms[1] is not None:
            return ms[0], ms[1]
        w = (self._front or {}).get("weather") or {}
        out = []
        for key in ("sunrise", "sunset"):
            hm = w.get(key)
            if not (isinstance(hm, str) and ":" in hm):
                return None
            h, _, m = hm.partition(":")
            try:
                out.append(int(h) * 60 + int(m))
            except ValueError:
                return None
        return out[0], out[1]

    def _night_now(self) -> bool:
        """Ist gerade Nacht?

        Rangfolge: ein in den Einstellungen gewaehlter Baustein (sein `active`-State
        = Nacht), sonst die Sonnenzeiten nach _sun_minutes() (Miniserver vor
        Wetterdienst), zuletzt NIGHT_FROM..NIGHT_TO. Ein gewaehlter, aber nicht
        (mehr) vorhandener Baustein faellt still auf die Sonnenzeiten zurueck."""
        u = (self.night_cfg or {}).get("control")
        if u:
            c = self.controls.get(u)
            if c:
                return bool(self._state(c, "active"))
        now = datetime.now()
        sun = self._sun_minutes()
        if sun:
            cur = now.hour * 60 + now.minute
            return cur >= sun[1] or cur < sun[0]
        hm = now.strftime("%H:%M")
        return hm >= NIGHT_FROM or hm < NIGHT_TO

    def panel_reload(self, pid: str | None, roh: dict | None = None):
        """Auto-Neustart-Intervall (Stunden) fuer ein Panel aus dem Profil, 0 =
        aus. Gegen Einfrieren: der Agent startet Chromium periodisch neu, ohne
        Agent laedt sich die Visu neu. None = nicht eingestellt: Der Agent nimmt
        seinen Wert aus der kiosk.conf, die Visu laedt nachts neu
        (NEULADEN_STUNDE). Geht in die Announce-Antwort und die theme-Nachricht."""
        ui = {**self.theme.get("ui", {}), **self._ui_roh(pid, roh)}
        v = ui.get("reloadHours")
        return max(0, min(168, float(v))) if isinstance(v, (int, float)) else None

    def _has_agent(self, name: str) -> bool:
        """True, wenn zu einer Geraetekennung (?device=) ein Panel-Agent bekannt
        ist, der sich in den letzten 10 Minuten gemeldet hat. Dann schaltet der
        Agent das Display und startet Chromium neu; die Visu haelt sich mit
        eigener Abschaltung und eigenem Reload zurueck."""
        if not name:
            return False
        now = time.time()
        return any(a.get("name") == name and (now - a.get("ts", 0)) < 600
                   for a in self.agents.values())

    def _agenten_der_visu(self, dev: str, ip: str) -> list[dict]:
        """Agenten mit AGENT_KANN_PANEL hinter einer Visu, die als Geraet `dev`
        von `ip` verbindet. Vorrang hat der Agent mit dieser IP, auch wenn
        seine letzte Meldung aelter ist: Sein Chromium verbindet gerade, das
        Panel lebt (etwa gleich nach dem Booten). Meldet er eine andere Adresse
        (NAT), gelten alle mit dem Namen, die online sind, wie in switch_mode."""
        now = time.time()
        gleich = [a for a in self.agents.values() if a["name"] == dev]
        gleich = ([a for a in gleich if a["ip"] == ip]
                  or [a for a in gleich if now - a["ts"] < AGENT_ONLINE])
        return [a for a in gleich if AGENT_KANN_PANEL in a.get("features", ())]

    def geraet_ansicht(self, dev: str) -> str | None:
        """Die dem Geraet zugeordnete Ansicht (devices[dev].panel, Einrichtung
        Schritt 2), wirksam wie in der Visu (eine geloeschte zeigt das
        Standardprofil); None, wenn dem Geraet keine zugeordnet ist."""
        pid = (self.devices.get(dev) or {}).get("panel") if dev else None
        return self.ansicht_wirksam(pid) if pid else None

    def ansicht_fuer_geraet(self, dev: str) -> str | None:
        """Was ein Geraet zeigen soll, aus einer Stelle: laeuft ein Betriebsmodus
        mit Zuordnung fuer das Geraet (und hat niemand seitdem ausdruecklich
        gewaehlt), dessen Profil, sonst die zugeordnete Ansicht; None, wenn
        weder noch (dann gilt, was die Visu mit ?panel= verlangt)."""
        if not dev:
            return None
        cfg = self.devices.get(dev) or {}
        if self.last_mode and dev not in self.ansicht_gewaehlt and cfg.get("auto", True):
            mapped = (cfg.get("modes") or {}).get(self.last_mode)
            if mapped:
                return self.ansicht_wirksam(mapped)
        return self.geraet_ansicht(dev)

    def geraet_zuordnen(self, dev: str, panel: str) -> None:
        """Ansicht `panel` dem Geraet zuordnen und speichern (leer = Standard-
        ansicht, der Schluessel faellt weg). Die uebrigen Einstellungen des
        Geraets bleiben; ein Geraet ohne andere Einstellungen entsteht damit."""
        devices = {n: dict(c) for n, c in self.devices.items()}
        cfg = devices.setdefault(dev, {"auto": True, "modes": {}})
        if panel:
            cfg["panel"] = panel
        else:
            cfg.pop("panel", None)
        self._write_devices(self._sanitize_devices(devices, set(self.panels)))

    def effective_scale(self, prof: dict | None, dev: str) -> str | float:
        """Wirksame Skalierung eines Panels: die des Geraets, falls dort eine
        gesetzt ist, sonst die des Profils (resolve_profile() hat dort schon
        die globale eingemischt). So lassen sich zwei Displays mit demselben
        Profil unterschiedlich einstellen."""
        d = self.devices.get(dev) if dev else None
        if isinstance(d, dict):
            sc = _clean_scale(d.get("scale"))
            if sc is not None:
                return sc
        return (prof or {}).get("scale") or "off"

    def effective_grid_auto(self, prof: dict | None, dev: str) -> int:
        """Zielkachel des automatischen Rasters fuer ein Panel: die des Geraets
        (devices[name].tileTarget), falls dort eine steht, sonst die des
        Profils - wie bei der Skalierung. Nur im Kachel-Layout "Automatisch"
        (gridAuto > 0): ein festes Raster bleibt fest, auch wenn das Geraet
        eine Zielkachel traegt."""
        g = int((prof or {}).get("gridAuto") or 0)
        d = self.devices.get(dev) if dev else None
        if g and isinstance(d, dict):
            z = _clean_kachelziel(d.get("tileTarget"))
            if z is not None:
                return z
        return g

    def device_list(self) -> dict:
        """Alle bekannten Anzeigegeraete, zusammengefuehrt ueber den Namen:
        Panel-Agenten (Announce), verbundene Browser (?device=) und die in
        panels.json konfigurierten Geraete (Betriebsmodus-Automatik). Browser
        ohne Namen stehen getrennt unter `anonymous` (nach IP) und koennen
        aus den Einstellungen benannt werden (`/api/device/name`)."""
        now = time.time()
        devs: dict[str, dict] = {}

        def entry(name: str) -> dict:
            return devs.setdefault(name, {
                "name": name, "agent": None, "connections": 0, "online": False,
                "profile": "", "kiosk": "", "ip": "", "lastSeen": 0.0, "configured": False,
                "zugeordnet": "", "screen": {}, "presence": None, "vorschau": None})

        for a in self.agents.values():
            if (now - a["ts"]) >= 600:
                continue
            e = entry(a["name"])
            e["agent"] = {"ip": a["ip"], "port": a["port"], "kiosk": a["kiosk"],
                          "panel": a["panel"], "online": (now - a["ts"]) < AGENT_ONLINE}
            e["ip"] = a["ip"]
            e["lastSeen"] = max(e["lastSeen"], a["ts"])
            e["online"] = e["online"] or e["agent"]["online"]
        anonymous = []
        for ws, info in list(self.conn_info.items()):
            prof = (self.conn_prof.get(ws) or {}).get("id", "")
            if not info.get("dev"):
                if info.get("vorschau"):   # Vorschaufenster des Konfigurators: kein Geraet
                    continue
                anonymous.append({"ip": info.get("ip", ""), "code": info.get("code", ""), "profile": prof,
                                  "kiosk": info.get("kiosk", ""), "since": info.get("ts", 0),
                                  "screen": info.get("screen") or {}})
                continue
            e = entry(info["dev"])
            e["connections"] += 1
            e["online"] = True
            e["profile"] = prof
            e["kiosk"] = info.get("kiosk") or e["kiosk"]
            e["ip"] = e["ip"] or info.get("ip", "")
            e["lastSeen"] = max(e["lastSeen"], info.get("ts", 0))
            if info.get("screen"):
                e["screen"] = info["screen"]   # zuletzt gemeldete Groesse (bei mehreren Fenstern das letzte)
        for name, cfg in self.devices.items():
            e = entry(name)
            e["configured"] = True
            e["zugeordnet"] = cfg.get("panel") or ""   # die eine Stelle: was das Geraet zeigen soll
        for name, on in self._presence_on.items():
            entry(name)["presence"] = on   # nur Geraete mit gekoppeltem Praesenzmelder
        for name, v in self.vorschau_geraet.items():   # Geraet zeigt einen Entwurf (Punkt 12)
            if name in devs:
                devs[name]["vorschau"] = {"id": v["id"], "bis": v["bis"]}
        for e in devs.values():
            e["type"] = "agent" if e["agent"] else (e["kiosk"] if e["kiosk"] in KIOSK_APPS else "browser")
            e["tileSuggest"] = _kachel_vorschlag(e["screen"])   # Zielkachel aus der gemeldeten Groesse
            if e["agent"] and not e["profile"]:
                # was die Visu des Agenten zeigt: eine geloeschte Ansicht ist dort das Standardprofil
                e["profile"] = self.ansicht_wirksam(e["agent"]["panel"])
        anonymous.sort(key=lambda a: (a["ip"], a["code"]))
        return {"devices": sorted(devs.values(), key=lambda e: e["name"].lower()),
                "anonymous": anonymous, "profiles": sorted(self.panels)}

    def kopplungscode(self, wunsch: str) -> str:
        """Code fuer einen Browser ohne Namen: der mitgeschickte, wenn er
        gueltig ist (die Visu hat ihn sich beim letzten Verbinden gemerkt),
        sonst ein neuer, der gerade keiner anderen Verbindung gehoert."""
        wunsch = (wunsch or "").strip().upper()
        if _KOPPLUNG_RE.fullmatch(wunsch):
            return wunsch
        vergeben = {i.get("code") for i in self.conn_info.values()}
        while True:
            code = "".join(secrets.choice(KOPPLUNG_ZEICHEN) for _ in range(KOPPLUNG_LAENGE))
            if code not in vergeben:
                return code

    @staticmethod
    def _kopplung_msg(code: str, karte: bool) -> dict:
        """Nachricht an einen Browser ohne Namen: sein Code, und ob er die
        Karte "Dieses Geraet einrichten" zeigen soll (ohne ?panel= und ohne
        Namen hat niemand dieses Geraet eingerichtet). Die Adresse des
        Konfigurators setzt das Panel wie beim Einrichtungshinweis zusammen."""
        return {"t": "kopplung", "code": code, "karte": karte,
                "titel": "Dieses Gerät einrichten",
                "hinweis": "Der Konfigurator meldet dieses Gerät von selbst – dort Namen vergeben und einrichten:",
                "pfad": "/config", "adressen": _lan_adressen(),
                "unbekannt": "Die Adresse dieses Geräts steht in seinen WLAN-Einstellungen.",
                "weg": "Tippen blendet die Karte bis zum nächsten Laden aus."}

    def _presence_rebuild(self) -> None:
        """Praesenzmelder der Geraete (devices[name].presence) auf den active-State
        ihres Bausteins abbilden. Laeuft nach dem Einlesen der Struktur und nach
        dem Speichern der Geraete; wer devices oder controls sonst ersetzt (z. B.
        das Einspielen einer Sicherung), dem holt der Broadcaster das im
        naechsten Takt nach (_presence_quelle). Aendert sich dabei der Stand eines Geraets
        (Melder gewaehlt, waehrend jemand da ist, oder wieder entfernt), erfahren
        es seine Panels als Wecken, nie als Abschalten: aus schaltet nur der
        Melder selbst, wenn der Raum leer wird (_on_value). Ein Baustein, den es
        in der Struktur nicht (mehr) gibt, koppelt nichts."""
        self._presence_quelle = (self.devices, self.controls)
        pmap: dict[str, list[str]] = {}
        for name, cfg in (self.devices or {}).items():
            u = cfg.get("presence") if isinstance(cfg, dict) else None
            su = ((self.controls.get(u) or {}).get("states") or {}).get("active") if u else None
            if su:
                pmap.setdefault(su, []).append(name)
        self.presence_map = pmap
        jetzt = {n: bool(self.states.get(su)) for su, names in pmap.items() for n in names}
        for name in set(self._presence_on) | set(jetzt):
            neu = jetzt.get(name, False)
            if neu != self._presence_on.get(name, False):
                self._pending_presence.append({"dev": name, "on": True, "presence": neu})
        self._presence_on = jetzt
        if jetzt:
            log.info("Präsenz: %d Gerät(e) an einen Präsenzmelder gekoppelt", len(jetzt))

    async def display_drivers(self, on: bool, device: str = "", panel: str = "") -> list:
        """Display ueber die HTTP-Schnittstelle der Kiosk-App schalten (Fully
        Kiosk Remote Admin, WallPanel). Betroffen sind Geraete mit `display`-
        Treiber in panels.json: bei `device` genau dieses, bei `panel` die, die
        das Profil gerade zeigen, sonst alle. Liefert je Geraet ein Ergebnis."""
        showing = {}
        for ws, info in list(self.conn_info.items()):
            if info.get("dev"):
                showing[info["dev"]] = (self.conn_prof.get(ws) or {}).get("id", "")
        out = []
        # Ein bestimmtes Geraet direkt nachschlagen: der Praesenzmelder ruft das
        # je Geraet auf, ueber alle Geraete waere es quadratisch.
        geraete = ({device: self.devices[device]} if device in self.devices else {}) if device \
            else self.devices
        for name, cfg in geraete.items():
            disp = cfg.get("display") if isinstance(cfg, dict) else None
            if not disp:
                continue
            if panel and not device and showing.get(name) != panel:
                continue
            out.append(await self._drive_display(name, disp, on))
        return out

    async def _drive_display(self, name: str, disp: dict, on: bool) -> dict:
        sess = self._drv_session
        if sess is None or sess.closed:
            sess = self._drv_session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=6))
        drv = disp.get("driver")
        res = {"device": name, "driver": drv, "on": on}
        pw = str(disp.get("password") or "")

        def von_gegenstelle(text: str) -> str:
            # Gibt die Gegenstelle die Anfrage wieder (Echo, Fehlerseite), stuende
            # das Kennwort im Klartext darin. Nur hier ersetzen: In selbst
            # gebildeten Meldungen ("Cannot connect to host h:port") verriete die
            # Ersetzung ueber den frei waehlbaren Port, ob er das Kennwort enthaelt.
            return text.replace(pw, "***") if pw else text
        try:
            if drv == "fully":
                # Fully Kiosk Browser, Remote Admin: GET /?cmd=screenOn|screenOff&password=...
                url = (f"http://{disp['host']}:{disp['port']}/?cmd="
                       f"{'screenOn' if on else 'screenOff'}&type=json"
                       f"&password={quote(str(disp.get('password') or ''), safe='')}")
                async with sess.get(url) as r:
                    txt = (await r.text())[:300]
                    ok = r.status == 200
                    try:
                        j = json.loads(txt)
                        if isinstance(j, dict) and str(j.get("status", "")).lower() == "error":
                            ok, txt = False, str(j.get("statustext") or txt)
                    except ValueError:
                        pass
            else:
                # WallPanel: POST /api/command {"wake": true|false}. false gibt nur
                # den Bildschirmschoner von WallPanel frei (eigene Abschaltzeit dort).
                url = f"http://{disp['host']}:{disp['port']}/api/command"
                async with sess.post(url, json={"wake": bool(on)}) as r:
                    txt = (await r.text())[:300]
                    ok = r.status == 200
            if not ok:
                res["error"] = f"HTTP {r.status}: {von_gegenstelle(txt)}".strip()
        except (aiohttp.ClientError, asyncio.TimeoutError, OSError, ValueError) as err:
            # ValueError: Host, den die Namensaufloesung nicht annimmt
            # ("tablet..home", Label ueber 63 Zeichen) - sonst bricht die
            # Schleife in display_drivers fuer alle folgenden Geraete ab
            ok = False
            # Ohne die Adresse: InvalidURL und ClientResponseError nennen sie
            # ganz, bei Fully samt Kennwort.
            if isinstance(err, aiohttp.InvalidURL):
                res["error"] = f"ungültige Adresse {disp['host']}:{disp['port']}"
            elif isinstance(err, aiohttp.ClientResponseError):
                res["error"] = f"HTTP {err.status}: {von_gegenstelle(err.message)}"
            else:
                res["error"] = str(err) or err.__class__.__name__
        res["ok"] = ok
        if not ok:
            # Das Kennwort so, wie es verschickt wurde (yarl kodiert anders als
            # quote()): aus einem Echo der Anfrage oder einer Meldung mit der
            # ganzen Adresse (Zeitueberschreitung beim Verbinden). Ersetzt den
            # ganzen Wert, das Ergebnis haengt also nicht vom Kennwort ab.
            res["error"] = re.sub(r"password=[^&\s]*", "password=***", res["error"])
            log.warning("Display-Treiber %s (%s): %s", name, drv, res["error"])
        return res

    async def _agent_start(self, agent: dict, profile: str) -> bool:
        """Startet den Kiosk eines Panel-Agenten mit einem Profil (Fernbefehl).
        Das Profil ersetzt eine offene Wahl. Ein Agent mit AGENT_KANN_PANEL
        behaelt es als Wahl, bis er es meldet: Scheitert der Befehl (Zeitlimit,
        Port gesperrt), uebernimmt er es so mit seiner naechsten Meldung."""
        if AGENT_KANN_PANEL in agent.get("features", ()):
            self.agent_wunsch[agent["ip"]] = profile
        else:
            self.agent_wunsch.pop(agent["ip"], None)
        url = f"http://{agent['ip']}:{agent['port']}/start"
        try:
            async with aiohttp.ClientSession() as s:
                async with s.post(url, json={"panel": profile},
                                  timeout=aiohttp.ClientTimeout(total=AGENT_BEFEHL_TIMEOUT)) as r:
                    return r.status == 200
        except Exception as err:
            log.warning("Agent %s Start(%s) fehlgeschlagen: %s",
                        agent.get("name"), profile, err)
            return False

    async def switch_mode(self, mode: str) -> list:
        """Betriebsmodus-Wechsel (von Loxone via /api/mode): jedes Panel mit
        aktiver Automatik und einer Zuordnung fuer diesen Modus auf sein Profil
        umschalten. Zwei Wege je Panel (adressiert ueber seinen Namen):
        1. geraeteunabhaengig: offene Browser-Verbindung mit `?device=<name>`
           bekommt per WS ein `{t:'switch'}` -> laedt sich mit neuem Profil neu
           (funktioniert auf jedem Browser/Kiosk, kein Agent noetig);
        2. Fallback: Linux-Panel-Agent per Fernstart (`?device=` nicht gesetzt),
           nur wenn er online ist; einen anderen zieht ws_handler beim
           Verbinden seines Chromium nach.
        Ein Agent, der das kann (AGENT_KANN_PANEL), uebernimmt das Profil im
        ersten Fall mit seiner naechsten Meldung (Abschaltzeit, Neustart-
        intervall, naechster Kiosk-Start). Ausdrueckliche Wahlen unter
        Displays gelten ab hier nicht mehr. Zeigt die Zuordnung auf eine Ansicht,
        die es nicht (mehr) gibt, gilt wie in der Visu das Standardprofil; die
        Zuordnung selbst bleibt (`statt` nennt sie im Ergebnis).
        """
        mode = (mode or "").strip()
        results: list = []
        if not mode:
            return results
        self.last_mode = mode   # merken -> frisch verbundene Geraete ziehen darauf nach
        self.ansicht_gewaehlt.clear()
        now = time.time()
        by_name = {a["name"]: a for a in self.agents.values() if (now - a["ts"]) < AGENT_ONLINE}
        for name, cfg in self.devices.items():
            if not cfg.get("auto", True):
                continue
            zugeordnet = (cfg.get("modes") or {}).get(mode)
            if not zugeordnet:
                continue
            profile = self.ansicht_wirksam(zugeordnet)
            statt = {} if profile == zugeordnet else {"statt": zugeordnet}
            ws_targets = [ws for ws, dev in self.conn_dev.items() if dev == name]
            if ws_targets:
                self.vorschau_geraet.pop(name, None)   # der Modus schaltet um: eine Vorschau endet damit
                self.vorschau_ende.pop(name, None)
                sent = 0
                for ws in ws_targets:
                    p = self.conn_prof.get(ws) or {}
                    if p.get("id") == profile and not p.get("entwurf"):
                        sent += 1            # zeigt bereits das richtige Profil (ein Entwurf davon nicht)
                        continue
                    if await self._send_or_drop(ws, {"t": "switch", "panel": profile}):
                        sent += 1
                for a in self.agents.values():
                    if (a["name"] == name and AGENT_KANN_PANEL in a.get("features", ())
                            and (now - a["ts"]) < AGENT_ONLINE):
                        self.agent_wunsch[a["ip"]] = profile
                results.append({"panel": name, "profile": profile,
                                "ok": sent > 0, "via": "ws", **statt})
                continue
            agent = by_name.get(name)
            if agent:
                ok = await self._agent_start(agent, profile)
                results.append({"panel": name, "profile": profile,
                                "ok": ok, "via": "agent", **statt})
            else:
                results.append({"panel": name, "profile": profile,
                                "ok": False, "error": "Gerät nicht online", **statt})
        return results

    def _persist_panels_file(self, panels: dict, devices: dict) -> None:
        """Schreibt config/panels.json (Profile + Geraete-Automatik) in einem Rutsch."""
        doc = self._panels_doc(panels, devices)
        # Eine Generation Sicherung: die aktuelle (funktionierende) panels.json
        # vor dem Ueberschreiben nach panels.json.bak kopieren (best effort; ein
        # fehlgeschlagenes Backup darf das Speichern nicht blockieren).
        try:
            if PANELS_FILE.is_file():
                _atomic_write(PANELS_FILE.with_name(PANELS_FILE.name + ".bak"),
                              PANELS_FILE.read_text(encoding="utf-8"))
        except (OSError, ValueError) as err:   # ValueError = UnicodeDecodeError bei kaputtem UTF-8
            log.warning("panels.json.bak nicht geschrieben: %s", err)
        _atomic_write(PANELS_FILE,
                      json.dumps(doc, indent=2, ensure_ascii=False) + "\n")

    def _write_panels(self, panels: dict) -> None:
        self._persist_panels_file(panels, self.devices)
        self.panels = load_panels()
        self.entwuerfe.clear()   # gespeichert: die Entwuerfe sind erledigt (die Visu laedt neu)
        self.vorschau_geraet.clear()   # ... auch am Geraet: es zeigt jetzt das gespeicherte Profil

    def _write_devices(self, devices: dict) -> None:
        # Erst schreiben, dann uebernehmen: scheitert das Schreiben, laeuft der
        # Server mit dem Stand der Datei weiter
        self._persist_panels_file(self.panels, devices)
        self.devices = devices
        self._presence_rebuild()
