"""Gesten wie auf den Loxone-Tastern (docs/TODO.md §9): zwei Finger bedienen
den Raum der Seite, Mitte Licht (dimmen, Stimmung weiter), links
Beschattung, rechts Musik; Tipp, Doppel- und Dreifachtipp schalten die
Taster der Ansicht. geste() nimmt die Nachricht der Visu ({t:"geste"}) und
schickt die Befehle, gesten_hilfe() beschreibt sie fuer das Hinweis-Symbol,
die *_optionen() fuellen die Auswahl im Konfigurator.

Die Methoden sind ein Mixin (Gesten): App erbt sie; sie arbeiten mit dem
Zustand der App. Importiert webvisu nicht."""
from __future__ import annotations

import asyncio

from adapters import LightControllerV2Adapter
from bausteine.gemeinsam import _clean, LIGHT
from haus import HAUS_AUS

# Raum verlassen und Haus aus loesen einen Taster aus Loxone Config aus. Laut
# Strukturdoku nimmt nur der Taster (Pushbutton, virtueller Eingang) einen
# Impuls (`pulse`); ein Schalter kennt nur on/off.
GESTEN_TASTER_TYPEN = ("Pushbutton",)

# Lichtgruppen eines Raums: jede Lichtsteuerung mit ihren Lichtkreisen und
# jeder einzelne Dimmer. Gedimmt werden die Kreise selbst, nicht die
# Master-Helligkeit: wie sie sich nach einem Stimmungswechsel verhaelt, sagt
# weder die Strukturdoku noch die Wissensdatenbank, die Stimmung dagegen setzt
# jeden Kreis wieder aus ihren eigenen Werten.
GESTEN_LICHT_TYPEN = ("LightControllerV2",)

GESTEN_DIMMER_TYPEN = ("Dimmer", "EIBDimmer")

GESTEN_AUDIO_TYPEN = ("AudioZone", "AudioZoneV2")

GESTEN_BESCHATTUNG_TYPEN = ("Jalousie",)


class Gesten:
    """Gesten der Visu; Mixin der App (self ist die App)."""

    def geste_taster_optionen(self) -> list:
        """Taster, die "Raum verlassen" und "Haus aus" ausloesen koennen
        (GESTEN_TASTER_TYPEN, ohne Visu-PIN): [{uuid, name, room}]."""
        out = []
        for u, c in self.controls.items():
            name = _clean(c.get("name"))
            if c.get("type") in GESTEN_TASTER_TYPEN and not c.get("isSecured") and name:
                out.append({"uuid": u, "name": name,
                            "room": _clean((self.rooms.get(c.get("room")) or {}).get("name"))})
        return sorted(out, key=lambda d: (d["room"], d["name"]))

    def licht_stimmung_optionen(self) -> list:
        """Lichtsteuerungen mit ihren Stimmungen fuer "Stimmung beim Einschalten"
        je Geraet: [{uuid, name, room, moods: [{id, name}]}]."""
        out = []
        for u, c in self.controls.items():
            if c.get("type") not in GESTEN_LICHT_TYPEN:
                continue
            out.append({"uuid": u, "name": _clean(c.get("name")),
                        "room": _clean((self.rooms.get(c.get("room")) or {}).get("name")),
                        "moods": [{"id": m, "name": n} for m, n in self._geste_stimmungen(u)]})
        return sorted(out, key=lambda d: (d["room"], d["name"]))

    # ---- Gesten (Loxone-Standard wie auf den Tastern, docs/TODO.md §9) ----
    def geste_raum(self, route: dict | None, prof: dict | None) -> str | None:
        """Raum, den eine Geste trifft: der der Seite (Raum-Tab oder Raum unter
        "Raeume"), sonst der feste Raum der Ansicht (gestenRaum). None, wenn es
        keinen gibt oder der Miniserver ihn nicht kennt."""
        r = route or {}
        ru = None
        if r.get("view") == "group" and r.get("kind") == "room":
            ru = r.get("id")
        elif r.get("view") == "tab" and isinstance(r.get("tab"), str) and r["tab"].startswith("room:"):
            ru = r["tab"][5:]
        if not ru:
            ru = (prof or {}).get("gestenRaum")
        return ru if isinstance(ru, str) and ru in self.rooms else None

    def gesten_hilfe(self, route: dict | None, prof: dict | None) -> dict | None:
        """Was zwei Finger auf dieser Seite tun, fuer das Hinweis-Symbol der Visu
        und seine Hilfe: der Raum der Seite (geste_raum), Doppel- und
        Dreifachtipp mit den Tastern aus den Vorgaben, so wie geste() sie
        ausloest. None, wo Gesten oder ihr Hinweis aus sind oder kein Raum gilt."""
        if not (prof or {}).get("gesten") or not (prof or {}).get("gestenHinweis"):
            return None
        ru = self.geste_raum(route, prof)
        if not ru:
            return None
        ui = self.theme.get("ui") or {}
        raum = _clean(self.rooms[ru].get("name")) or "diesem Raum"

        def taster(uuid) -> str:
            c = self.controls.get(uuid or "")
            ok = c and c.get("type") in GESTEN_TASTER_TYPEN and not c.get("isSecured")
            return f"Taster „{_clean(c.get('name')) or uuid}“" if ok else "Taster nicht gefunden"
        verlassen = (ui.get("raumVerlassen") or {}).get(ru)
        haus = ui.get("hausAus")
        return {"raum": raum,
                "doppel": f"{raum} verlassen: " + (taster(verlassen) if verlassen
                                                    else "aus, was an ist und sich abschalten lässt"),
                "dreifach": "Haus aus: " + (taster(haus) if haus else "nicht eingerichtet (Vorgaben → Verhalten)")}

    def _geste_bausteine(self, ru: str, prof: dict | None, typen: tuple) -> list:
        """Bausteine dieser Typen im Raum, so wie seine Raumseite sie zeigt
        (Kategorie-Filter und Ausblendungen der Ansicht). Gesicherte bleiben
        aussen vor: eine PIN-Abfrage mitten in einer Geste geht nicht."""
        return [u for u, c in self.controls.items()
                if c.get("room") == ru and c.get("type") in typen and not c.get("isSecured")
                and self._cat_ok(u, prof) and self._shown(u, prof)]

    def _geste_kreis(self, d: dict, uuid: str) -> dict | None:
        """Dimmbarer Kreis (Dimmer oder Lichtkreis einer Lichtsteuerung) mit den
        States der Strukturdoku: {ziel, wert, min, max}; None ohne Stellung."""
        wert = self._endlich(d, "position")
        if wert is None:
            return None
        mn = self._endlich(d, "min")
        mx = self._endlich(d, "max")
        mn = 0.0 if mn is None else mn
        mx = 100.0 if mx is None or mx <= mn else mx
        return {"ziel": d.get("uuidAction") or uuid, "wert": wert, "min": mn, "max": mx}

    def licht_gruppen(self, ru: str, prof: dict | None) -> list:
        """Lichtgruppen eines Raums: jede Lichtsteuerung mit ihren dimmbaren
        Lichtkreisen (Unterbausteine vom Typ Dimmer ohne die Master-Helligkeit,
        details.masterValue) und jeder einzelne Dimmer als Gruppe mit einem
        Kreis. So gelten dieselben Regeln fuer eine Lichtsteuerung mit vielen
        Kreisen, mehrere in einem offenen Raum und lauter einzelne Dimmer.
        Je Gruppe: {uuid, typ, an, kreise}."""
        out = []
        for u in self._geste_bausteine(ru, prof, GESTEN_LICHT_TYPEN + GESTEN_DIMMER_TYPEN):
            c = self.controls[u]
            if c.get("type") in GESTEN_LICHT_TYPEN:
                master = (c.get("details") or {}).get("masterValue")
                kreise = [self._geste_kreis(s, su) for su, s in (c.get("subControls") or {}).items()
                          if isinstance(s, dict) and s.get("type") in GESTEN_DIMMER_TYPEN
                          and master not in (su, s.get("uuidAction"))]
                an = LIGHT.render(self._with_uuid(u), self.states)["on"]
            else:
                kreise = [self._geste_kreis(c, u)]
                an = None
            kreise = [k for k in kreise if k]
            out.append({"uuid": u, "typ": c.get("type"), "kreise": kreise,
                        "an": any(k["wert"] > 0 for k in kreise) if an is None else an})
        return out

    def _geste_stimmungen(self, uuid: str) -> list:
        """Stimmungen einer Lichtsteuerung ohne "Aus", in der Folge ihrer
        moodList: [(id, name)]."""
        out = []
        for m in LIGHT.moods(self._with_uuid(uuid), self.states):
            try:
                mid = int(m.get("id"))
            except (TypeError, ValueError):
                continue
            if mid != LightControllerV2Adapter.OFF_MOOD:
                out.append((mid, _clean(m.get("name")) or str(mid)))
        return out

    def _geste_lichtsteuerung(self, gruppen: list, dev: str) -> tuple:
        """Lichtsteuerung des Geraets und ihre Stimmung beim Einschalten
        (devices[dev].lichtStart), wenn sie in diesem Raum liegt, sonst die
        erste des Raums mit ihrer ersten Stimmung: (gruppe, stimmungs_id) oder
        (None, None)."""
        lcs = [g for g in gruppen if g["typ"] in GESTEN_LICHT_TYPEN]
        start = (self.devices.get(dev) or {}).get("lichtStart") if dev else None
        for g in lcs:
            if start and g["uuid"] == start.get("lc"):
                ids = [m for m, _n in self._geste_stimmungen(g["uuid"])]
                return g, (start.get("mood") if start.get("mood") in ids else (ids[0] if ids else None))
        if lcs:
            ids = [m for m, _n in self._geste_stimmungen(lcs[0]["uuid"])]
            return lcs[0], (ids[0] if ids else None)
        return None, None

    async def _geste_befehle(self, befehle: list) -> int:
        """Befehle einer Geste gleichzeitig schicken; Zahl der fehlgeschlagenen."""
        codes = await asyncio.gather(*(self.command(u, c) for u, c in befehle))
        return sum(1 for code in codes if code != "200")

    async def _geste_taster(self, uuid: str, text: str, fehlt: str) -> dict:
        """Taster aus Loxone Config ausloesen (pulse): Raum verlassen, Haus aus."""
        c = self.controls.get(uuid or "")
        if not c or c.get("type") not in GESTEN_TASTER_TYPEN or c.get("isSecured"):
            return {"fehler": fehlt}
        if await self._geste_befehle([(c.get("uuidAction") or uuid, "pulse")]):
            return {"fehler": "Miniserver hat nicht ausgelöst"}
        return {"text": text}

    async def geste(self, ws, data: dict) -> dict | None:
        """Geste der Visu ausfuehren ({t:"geste", art, ...}) und die Antwort fuer
        ihre Einblendung liefern ({t:"geste", art, raum, wert|text|fehler}).
        None: nichts zu melden (Zwischenwert beim Dimmen) oder Gesten aus.

        art: "licht" und "musik" mit phase start/wert/ende (Mitte bzw. rechts
        hoch/runter), "stimmung" (Tipp Mitte), "beschattung" mit richtung
        auf/ab (links hoch/runter), "verlassen" (Doppeltipp), "hausaus"
        (Dreifachtipp)."""
        prof = self.conn_prof.get(ws) or {}
        art = str(data.get("art") or "")
        if not prof.get("gesten"):
            return None
        if art == "hausaus":
            ziel = (self.theme.get("ui") or {}).get("hausAus")
            if not ziel:
                return {"t": "geste", "art": art,
                        "fehler": "„Haus aus“ ist nicht eingerichtet (Vorgaben → Verhalten)"}
            return {"t": "geste", "art": art, **await self._geste_taster(
                ziel, "Haus aus", "Taster für „Haus aus“ nicht gefunden")}
        ru = self.geste_raum(self.conn_route.get(ws), prof)
        if not ru:
            return {"t": "geste", "art": art, "fehler": "Kein Raum auf dieser Seite"}
        antwort = {"t": "geste", "art": art, "raum": _clean(self.rooms[ru].get("name"))}
        raum = antwort["raum"] or "diesem Raum"
        if art in ("licht", "musik"):
            phase = data.get("phase")
            if phase == "start":
                lauf, start = (self._geste_licht_start(ru, prof, self.conn_dev.get(ws, ""))
                               if art == "licht" else self._geste_musik_start(ru, prof))
                if not lauf:
                    self.conn_geste.pop(ws, None)
                    return {**antwort, "fehler": start}
                self.conn_geste[ws] = lauf
                return {**antwort, "phase": "start", **start}
            lauf = self.conn_geste.get(ws)
            if not lauf or lauf["art"] != art:
                return None
            try:
                wert = max(0.0, min(100.0, float(data.get("wert"))))
            except (TypeError, ValueError):
                return None
            if phase == "ende":
                self.conn_geste.pop(ws, None)
            text = await self._geste_wert(lauf, wert, phase == "ende")
            return {**antwort, "text": text} if text else None
        if art == "stimmung":
            return {**antwort, **await self._geste_stimmung(ru, prof, self.conn_dev.get(ws, ""), raum)}
        if art == "beschattung":
            jal = self._geste_bausteine(ru, prof, GESTEN_BESCHATTUNG_TYPEN)
            if not jal:
                return {**antwort, "fehler": f"Keine Beschattung in {raum}"}
            fahrend = [u for u in jal if any(self._jal_fahrt(self.controls[u])[:2])]
            if fahrend:
                befehle = [(self.controls[u].get("uuidAction") or u, "Stop") for u in fahrend]
                text = "Beschattung gestoppt"
            else:
                auf = data.get("richtung") == "auf"
                befehle = [(self.controls[u].get("uuidAction") or u, "FullUp" if auf else "FullDown") for u in jal]
                text = "Beschattung auf" if auf else "Beschattung ab"
            fehl = await self._geste_befehle(befehle)
            return {**antwort, **({"fehler": f"{fehl} von {len(befehle)} Befehlen nicht ausgeführt"}
                                  if fehl else {"text": text})}
        if art == "verlassen":
            ziel = ((self.theme.get("ui") or {}).get("raumVerlassen") or {}).get(ru)
            if ziel:
                return {**antwort, **await self._geste_taster(
                    ziel, f"{raum} verlassen", f"Taster für „{raum} verlassen“ nicht gefunden")}
            # Ohne Taster aus Loxone: aus, was im Raum an ist und sich abschalten
            # laesst (wie "Gerade aktiv"). Das Raumklima bleibt unberuehrt.
            befehle = []
            for u in self._geste_bausteine(ru, prof, tuple(HAUS_AUS)):
                aus = self._haus_aus(u)
                if aus and self._control_item(u, prof).get("on"):
                    befehle.append((aus["uuid"], aus["cmd"]))
            if not befehle:
                return {**antwort, "text": f"In {raum} ist nichts an"}
            fehl = await self._geste_befehle(befehle)
            return {**antwort, **({"fehler": f"{fehl} von {len(befehle)} Befehlen nicht ausgeführt"}
                                  if fehl else {"text": f"{raum}: {len(befehle)} aus"})}
        return None

    def _geste_licht_start(self, ru: str, prof: dict | None, dev: str) -> tuple:
        """Beginn von Mitte hoch/runter: (lauf, antwort) oder (None, fehler).
        Leuchtet etwas, wird es anteilig gedimmt (Startwert der hellste Kreis).
        Ist alles aus, schaltet die Bewegung nach oben die Stimmung des Geraets
        ein (lichtStart) bzw. setzt die einzelnen Dimmer des Raums."""
        gruppen = self.licht_gruppen(ru, prof)
        an = [(g, k) for g in gruppen for k in g["kreise"] if k["wert"] > 0]
        if an:
            start = max(k["wert"] for _g, k in an)
            return ({"art": "licht", "modus": "dimmen", "start": start,
                     "kreise": [dict(k) for _g, k in an],
                     "lcs": sorted({g["uuid"] for g, _k in an if g["typ"] in GESTEN_LICHT_TYPEN}),
                     "gesendet": {}},
                    {"wert": round(start)})
        g, mood = self._geste_lichtsteuerung(gruppen, dev)
        if g and not g["an"] and mood is not None:
            name = dict(self._geste_stimmungen(g["uuid"])).get(mood, "")
            return ({"art": "licht", "modus": "stimmung", "lc": g["uuid"], "mood": mood, "name": name,
                     "gesendet": {}},
                    {"wert": 0, "text": name})
        kreise = [k for gr in gruppen if gr["typ"] in GESTEN_DIMMER_TYPEN for k in gr["kreise"]]
        if kreise:
            return ({"art": "licht", "modus": "neu", "kreise": kreise, "gesendet": {}}, {"wert": 0})
        return None, "Kein dimmbares Licht in " + (_clean(self.rooms[ru].get("name")) or "diesem Raum")

    def _geste_musik_start(self, ru: str, prof: dict | None) -> tuple:
        """Beginn von rechts hoch/runter: Lautstaerke der Audio-Zonen des Raums,
        Startwert die der ersten, die spielt (sonst der ersten)."""
        zonen = self._geste_bausteine(ru, prof, GESTEN_AUDIO_TYPEN)
        if not zonen:
            return None, "Keine Musik in " + (_clean(self.rooms[ru].get("name")) or "diesem Raum")
        erste = next((u for u in zonen if self._state(self.controls[u], "playState") == 2), zonen[0])
        start = self._endlich(self.controls[erste], "volume") or 0.0
        return ({"art": "musik", "zonen": [self.controls[u].get("uuidAction") or u for u in zonen],
                 "gesendet": {}},
                {"wert": round(start)})

    async def _geste_wert(self, lauf: dict, wert: float, ende: bool) -> str:
        """Zwischen- oder Endwert einer laufenden Geste umsetzen; Text fuer die
        Einblendung, wenn es einen gibt. Jeder Kreis bekommt nur einen Befehl,
        wenn sich sein Wert aendert."""
        befehle = []
        danach = []     # erst, wenn die Befehle davor beim Miniserver angekommen sind
        text = ""
        if lauf["art"] == "musik":
            v = round(wert)
            befehle = [(z, f"volume/{v}") for z in lauf["zonen"] if lauf["gesendet"].get(z) != v]
            for z, _c in befehle:
                lauf["gesendet"][z] = v
        elif lauf["modus"] == "stimmung":
            # Erst die Bewegung nach oben schaltet ein, genau einmal; weiter
            # gedimmt wird mit der naechsten Geste, wenn die Kreise leuchten
            if wert > 0 and not lauf["gesendet"]:
                lauf["gesendet"]["mood"] = lauf["mood"]
                befehle = [(self.controls[lauf["lc"]].get("uuidAction") or lauf["lc"],
                            f"changeTo/{lauf['mood']}")]
                text = lauf["name"]
        else:
            # Anteilig: jeder Kreis um denselben Faktor, das Verhaeltnis (das
            # Lichtbild der Stimmung) bleibt. "neu": alle auf den Wert.
            faktor = wert / lauf["start"] if lauf["modus"] == "dimmen" else None
            for k in lauf["kreise"]:
                v = round(k["wert"] * faktor) if faktor is not None else round(wert)
                v = 0 if v <= 0 else max(round(k["min"]), min(round(k["max"]), v))
                if lauf["gesendet"].get(k["ziel"]) != v:
                    lauf["gesendet"][k["ziel"]] = v
                    befehle.append((k["ziel"], str(v)))
            if ende and wert <= 0:
                # Ganz unten: Lichtsteuerungen sauber auf "Aus", statt mit
                # dunklen Kreisen auf "Manuell" stehen zu bleiben. Erst nach den
                # Kreisen: _geste_befehle schickt gleichzeitig (je Befehl eine
                # HTTP-Anfrage), und ein Kreis, der nach dem "Aus" ankommt,
                # stellte die Lichtsteuerung wieder auf "Manuell".
                danach = [(self.controls[u].get("uuidAction") or u,
                           f"changeTo/{LightControllerV2Adapter.OFF_MOOD}") for u in lauf.get("lcs", ())]
                text = "Aus"
        fehl = await self._geste_befehle(befehle) if befehle else 0
        if danach:
            fehl += await self._geste_befehle(danach)
        return "Nicht alle Befehle ausgeführt" if fehl else text

    async def _geste_stimmung(self, ru: str, prof: dict | None, dev: str, raum: str) -> dict:
        """Tipp Mitte: aus -> Stimmung beim Einschalten, an -> naechste Stimmung
        derselben Lichtsteuerung (changeTo, "Aus" uebersprungen). Ohne
        Lichtsteuerung schaltet er die einzelnen Dimmer ein."""
        gruppen = self.licht_gruppen(ru, prof)
        g, mood = self._geste_lichtsteuerung(gruppen, dev)
        if g:
            stimmungen = self._geste_stimmungen(g["uuid"])
            if not stimmungen:
                return {"fehler": f"Keine Stimmungen in {raum}"}
            ids = [m for m, _n in stimmungen]
            if g["an"]:
                aktiv = [m for m in LIGHT.active_moods(self._with_uuid(g["uuid"]), self.states) if m in ids]
                mood = ids[(ids.index(aktiv[0]) + 1) % len(ids)] if aktiv else ids[0]
            ua = self.controls[g["uuid"]].get("uuidAction") or g["uuid"]
            if await self._geste_befehle([(ua, f"changeTo/{mood}")]):
                return {"fehler": "Miniserver hat nicht umgeschaltet"}
            return {"text": dict(stimmungen)[mood]}
        dimmer = [gr for gr in gruppen if gr["typ"] in GESTEN_DIMMER_TYPEN]
        if not dimmer:
            return {"fehler": f"Kein Licht in {raum}"}
        if any(gr["an"] for gr in dimmer):
            return {"text": "Licht ist an"}
        befehle = [(k["ziel"], "on") for gr in dimmer for k in gr["kreise"]]
        if await self._geste_befehle(befehle):
            return {"fehler": "Nicht alle Befehle ausgeführt"}
        return {"text": "Licht an"}
