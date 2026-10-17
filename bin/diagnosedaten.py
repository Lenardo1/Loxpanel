"""Was der Server ueber sich und die Anlage meldet: die Angaben fuers
Diagnosepaket (diagnose_daten, das Paket baut diagnose.py) und die Uebersicht
der Bausteintypen fuer /api/types (types_overview) samt Wetterserver.

Die Methoden sind ein Mixin (Diagnosedaten): App erbt sie und arbeitet mit ihnen auf ihrem
Zustand (self ist die App). Importiert webvisu nicht."""
from __future__ import annotations

import logging
import math
import platform
import time
from datetime import datetime

import loxone_weather
import version_info
from bausteine.gemeinsam import _clean

log = logging.getLogger("loxpanel.webvisu")   # derselbe Logger wie der Server: die Methoden gehoeren zu App


# Welcher Stand laeuft (Seitenleiste des Konfigurators); einmal beim Start gelesen
VERSION = version_info.lesen()

# Bausteintypen, die nur teilweise umgesetzt sind (Anzeige ohne volle Bedienung);
# Grundlage fuer den Status in /api/types. Vollstaendig = Kachel hat nav/cmd/
# controls/sublabel, unbekannt = nichts davon (tote Kachel).
# Intercom und IntercomV2 bleiben im Browser ohne Gegensprechen. Die native
# Android-Bruecke ergaenzt Audio nur fuer Intercom (Gen-1); SIP-Zugang und
# Pruefung der Tuerstation bleiben unter Settings -> SIP (/api/sip).
PARTIAL_TYPES = {"AudioZone", "Intercom", "IntercomV2", "TextInput", "Ventilation"}


class Diagnosedaten:
    """Diagnose und Typuebersicht; Mixin der App (self ist die App)."""

    def diagnose_daten(self, geraet: str = "", aufgaben: dict | None = None,
                       gestartet: float | None = None) -> tuple[dict, set]:
        """Angaben fuer das Diagnosepaket (diagnose.paket) -> (daten, Werte, die
        zusaetzlich geschwaerzt werden: Kennwort und Token im Speicher). Mit
        `geraet` dessen Zustand und Ansicht, sonst alle Geraete in Kurzform.
        KeyError, wenn es das Geraet nicht gibt. Zeiten als Unix-Sekunden."""
        liste = self.device_list()["devices"]
        ok, seit, bestaetigt = self._verbindung_stand()
        daten = {
            "erstellt": datetime.now().isoformat(timespec="seconds"),
            "version": dict(VERSION),
            "server": {"python": platform.python_version(), "system": platform.platform(),
                       "laufzeit_s": round(time.monotonic() - gestartet) if gestartet is not None else None,
                       "aufgaben": aufgaben or {}, "panels": len(self.conn_route),
                       "log_level": logging.getLevelName(logging.getLogger().level)},
            "miniserver": {"host": self.host, "port": self.port, "benutzer": self.user,
                           "verbunden": self._ms_verbunden_seit is not None,
                           "verbunden_seit": self._ms_verbunden_seit,
                           "weg_seit": seit, "bestaetigt": bestaetigt, "fehler": self._ms_fehler,
                           "struktur": bool(self.controls), "bausteine": len(self.controls),
                           "raeume": len(self.rooms), "kategorien": len(self.cats), **self.ms_struktur},
            "audioserver": [{"host": h, "port": c.port, "verbunden": c.verbunden,
                             "gekoppelt": c.paired, "angemeldet": c.authed}
                            for h, c in sorted(self.audio_clients.items())],
        }
        if geraet:
            e = next((x for x in liste if x["name"] == geraet), None)
            if e is None:
                raise KeyError(geraet)
            daten["geraet"] = {"name": e["name"], "typ": e["type"], "online": e["online"],
                               "ansicht": e["profile"], "verbindungen": e["connections"], "ip": e["ip"],
                               "zuletzt": e["lastSeen"] or None, "bildschirm": e["screen"],
                               "agent": e["agent"], "praesenz": e["presence"],
                               "eingerichtet": e["configured"], "einstellungen": self.devices.get(geraet) or {}}
            roh = self.panels.get(e["profile"]) if e["profile"] else None
            if roh is not None:
                exp = self._panel_export(roh)
                ui = exp.get("ui") or {}
                daten["ansicht"] = {"id": e["profile"], "titel": exp.get("title") or "", "tabs": exp.get("tabs"),
                                    "kachelSet": ui.get("tileSet") or "", "farbton": ui.get("tileHue"),
                                    "aktiv": ui.get("tileActive"), "raster": ui.get("grid") or
                                    ([ui.get("cols"), ui.get("rows")] if ui.get("cols") else None)}
                daten["ansicht_einstellungen"] = exp
        else:
            daten["geraete"] = [{"name": e["name"], "typ": e["type"], "online": e["online"],
                                 "ansicht": e["profile"]} for e in liste]
        return daten, {g for g in (self.password, self.jwt) if g}

    def types_overview(self) -> dict:
        """Diagnose fuer /api/types: alle Bausteintypen der geladenen Anlage mit
        Anzahl, Beispielnamen, Unterstuetzungsstatus (full / partial / none),
        den State-Namen und details-Schluesseln je Typ, dazu die Liste der
        Controls, die als tote Kachel enden. Der Status wird nicht aus einer
        Liste geraten, sondern aus dem Rendering: `_control_item()` liefert
        fuer unterstuetzte Typen nav, cmd, controls oder sublabel."""
        types: dict[str, dict] = {}
        for uuid, c in self.controls.items():
            t = str(c.get("type") or "?")
            e = types.setdefault(t, {"type": t, "count": 0, "examples": [], "states": set(),
                                     "details": set(), "supported": False, "controls": []})
            e["count"] += 1
            name = _clean(c.get("name"))
            if name and len(e["examples"]) < 3:
                e["examples"].append(name)
            e["states"].update(k for k in (c.get("states") or {}) if isinstance(k, str))
            e["details"].update(k for k in (c.get("details") or {}) if isinstance(k, str))
            room = _clean((self.rooms.get(c.get("room")) or {}).get("name"))
            e["controls"].append({"uuid": uuid, "name": name, "room": room})
            if not e["supported"]:
                try:
                    it = self._control_item(uuid)
                except Exception as err:  # Diagnose darf nie an einem Baustein scheitern
                    log.warning("types_overview: %s (%s): %s", name, t, err)
                    it = {}
                if any(k in it for k in ("nav", "cmd", "controls", "sublabel")):
                    e["supported"] = True
        out, dead = [], []
        for t in sorted(types, key=str.lower):
            e = types[t]
            status = "none" if not e["supported"] else ("partial" if t in PARTIAL_TYPES else "full")
            if status == "none":
                dead.extend({**ctl, "type": t} for ctl in e["controls"])
            out.append({"type": t, "status": status, "count": e["count"], "examples": e["examples"],
                        "states": sorted(e["states"]), "details": sorted(e["details"])})
        counts = {s: sum(1 for e in out if e["status"] == s) for s in ("full", "partial", "none")}
        # Diagnose Energiefluss: rohe Knotenstruktur + aktuelle Werte je EFM/EM2.
        # Damit laesst sich die Rolle/Richtung je Knoten belegen (statt raten).
        energy = []
        for uuid, c in self.controls.items():
            if c.get("type") in ("EFM", "EnergyManager2"):
                det = c.get("details") or {}
                energy.append({
                    "uuid": uuid, "name": _clean(c.get("name")), "type": c.get("type"),
                    "actualFormat": det.get("actualFormat"), "storageFormat": det.get("storageFormat"),
                    "Ppwr": self._state(c, "Ppwr"), "Gpwr": self._state(c, "Gpwr"),
                    "Spwr": self._state(c, "Spwr"), "Ssoc": self._state(c, "Ssoc"),
                    "nodes": det.get("nodes"),
                    "actuals": {f"actual{i}": self._state(c, f"actual{i}") for i in range(6)},
                })
        # Diagnose globale States (Sonnenzeiten, aktive Betriebsmodi ...): Name,
        # UUID und aktueller Wert. Sonst nirgends sichtbar; Grundlage dafuer, die
        # Nacht-Erkennung an den Miniserver zu haengen statt an einen Wetterdienst.
        gstates = []
        for _n, _ref in (self.global_states or {}).items():
            if isinstance(_ref, str):
                gstates.append({"name": _n, "uuid": _ref, "value": self.states.get(_ref)})
            else:
                gstates.append({"name": _n, "raw": _ref})
        return {"connected": self.client is not None, "controls": len(self.controls),
                "typeCount": len(out), "typesByStatus": counts, "types": out,
                "energyDetails": energy,
                "globalStates": sorted(gstates, key=lambda g: g["name"]),
                "operatingModes": self.op_modes,
                "weatherServer": self._weather_diag(),
                "unsupportedControls": sorted(dead, key=lambda d: (d["room"], d["name"]))}

    def _weather_diag(self) -> dict:
        """Diagnose zum Loxone-Wetterserver: was die Anlage meldet und was davon
        ankommt. Sonst nirgends sichtbar — und die einzige verlaessliche Auskunft
        darueber, unter welchen Namen und in welchen Einheiten diese Anlage ihre
        Wetterwerte fuehrt."""
        cfg = self.weather_cfg or {}
        states = cfg.get("states") if isinstance(cfg.get("states"), dict) else {}
        eintraege = {rolle: len(self._lox_wx.get(u) or [])
                     for rolle, u in states.items() if isinstance(u, str)}
        akt = (self._lox_wx.get(states.get("actual")) or [None])[0]
        if isinstance(akt, dict):
            # NaN/Inf wuerde ungueltiges JSON ergeben — die Tabelle kann beides fuehren.
            akt = {k: (v if isinstance(v, int) or (isinstance(v, float) and math.isfinite(v)) else None)
                   for k, v in akt.items()}
        return {
            "vorhanden": bool(cfg),
            "quelle": self._wx_source,
            "states": states,
            "eintraege": eintraege,
            "aktuellerEintrag": akt,      # Rohwerte: zeigt Einheiten und Groessenordnung
            "wetterlagen": loxone_weather.weather_texts(cfg),
            "format": cfg.get("format"),
            "feldtypen": cfg.get("weatherFieldTypes"),
        }
