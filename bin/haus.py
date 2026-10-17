"""Hausuebersicht (Tab "haus"): die Seite mit Raumkarten, "Gerade aktiv",
Schnellaktionen ueber die Zentral-Bausteine, Hinweisen, Spieler mit Sendern
und Energie, in den Aufbauten "Status zuerst", "Raeume direkt" und "Spalte
links" (ui.hausAufbau). Server-Seite der Visu-Teile panel/haus.js.

Die Methoden sind ein Mixin (Haus): App erbt sie und ruft _view_haus() aus
render(); sie arbeiten mit dem Zustand der App. Importiert webvisu nicht."""
from __future__ import annotations

import asyncio
import math
import time

from adapters import LightControllerV2Adapter
from bausteine.gemeinsam import _clean, PROZENT_SCHRITT
from konfig import _is_pick, _pick_index, _pick_tabs, HAUS_AUFBAU_STANDARD, HAUS_AUFBAUTEN, HAUS_TAB

HAUS_TITEL = "Haus"

# Aus-Befehl je Bausteintyp (Loxone-Strukturdoku) und die Beschriftung seiner
# Taste. Nur was hier steht, zaehlt unter "Gerade aktiv": ein Geraet, das an
# ist UND sich abschalten laesst. Die Lueftung (Ventilation) hat keinen
# Aus-Befehl, sie bleibt Anzeige.
HAUS_AUS = {
    "Switch": ("off", "Aus"),
    "TimedSwitch": ("off", "Aus"),
    "Dimmer": ("off", "Aus"),
    "EIBDimmer": ("off", "Aus"),
    "LightControllerV2": (f"changeTo/{LightControllerV2Adapter.OFF_MOOD}", "Aus"),
    "AudioZone": ("pause", "Pause"),
    "AudioZoneV2": ("pause", "Pause"),
    "Sauna": ("off", "Aus"),
}

# Schnellaktionen der Hausseite: ein Befehl an den Zentral-Baustein der
# Anlage, Art -> (Typ, Beschriftung, Befehl). Befehle laut Strukturdoku
# (Central Objects): CentralLightController kennt "on" und "reset", "reset"
# ist der Eingang "Off" des Bausteins ("Outputs are reset / switched off",
# Wissensdatenbank "Licht Zentral"); CentralAudioZone "pause". Ohne den
# Baustein gibt es die Taste nicht.
HAUS_SCHNELL = {
    "licht": ("CentralLightController", "Alle Lichter aus", "reset"),
    "audio": ("CentralAudioZone", "Alle Zonen aus", "pause"),
}

# Symbole je Raumkarte (schaltbare zuerst)
HAUS_SYMBOLE = 4

# Aufbau "raeume": Ein-Befehl je Bausteintyp laut Strukturdoku, aus schaltet
# HAUS_AUS. Der Treppenlichtschalter (TimedSwitch) startet seinen Ablauf
# (pulse) statt dauerhaft (on). Die Lichtsteuerung schaltet ihre erste
# Stimmung ein (_haus_ein). Was beides nicht hat, bekommt keine Taste.
HAUS_EIN = {
    "Switch": "on",
    "TimedSwitch": "pulse",
    "Dimmer": "on",
    "EIBDimmer": "on",
    "AudioZone": "play",
    "AudioZoneV2": "play",
    "Sauna": "on",
}

# ... vor dem Einschalten fragt die Taste nach (erst der zweite Tipp schaltet)
HAUS_RUECKFRAGE = {"Sauna": "Einschalten?"}

# ... und so viele Tasten hat eine Raumkarte hoechstens
HAUS_TASTEN = 3

# Hinweise der Hausseite (_haus_hinweise): was Aufmerksamkeit braucht, in
# dieser Folge. "dringend" und "warnung" folgen dem Ton der Kachel
# (HINWEIS_TON, ihr Zustand ist der Text), "an" meldet, dass etwas da ist
# (Post). Eine Kachel nennt ihren Hinweis selbst (hinweis: stufe, text, dazu
# symbol und zusatz), wo ihr Zustand ihn nicht benennt.
HINWEIS_STUFEN = ("dringend", "warnung", "an")

HINWEIS_TON = {"crit": "dringend", "warn": "warnung"}

# Unterseiten der Hausseite (Route liste): alle aktiven Geraete, alle Hinweise
HAUS_LISTEN = ("aktiv", "hinweise")

# Spieler der Hausseite: so viele Favoriten der Zone schickt der Server mit
# (die Visu zeigt, was in eine Zeile passt, der Rest liegt hinter "Mehr" in der
# Musikauswahl), und wie oft er sie hoechstens anfordert, solange keine da sind
HAUS_SENDER = 8

HAUS_SENDER_NEU_S = 300


class Haus:
    """Die Hausuebersicht; Mixin der App (self ist die App)."""

    # ---- Hausuebersicht (Tab "haus") ----
    @staticmethod
    def _haus_seite(tab, prof: dict | None) -> bool:
        """Zeigt dieser Tab die Hausuebersicht? Der Tab "haus" der klassischen
        Leiste oder eine freie Seite, deren Inhalt sie ist (pickTabs[].widget)."""
        if tab == HAUS_TAB:
            return True
        if not _is_pick(tab):
            return False
        seiten, i = _pick_tabs(prof), _pick_index(tab)
        return 0 <= i < len(seiten) and seiten[i].get("widget") == HAUS_TAB

    def _haus_raeume(self, prof: dict | None) -> list:
        """Raeume der Hausseite mit ihren sichtbaren Bausteinen, in der Folge der
        Raumliste (rooms_with) und mit dem Raumfilter der Ansicht wie der Tab
        "Raeume": [(raum_uuid, [baustein_uuid, ...])]. Raeume ohne sichtbaren
        Baustein fallen weg."""
        ar = prof.get("rooms") if prof else None
        out = []
        for ru in self.rooms_with:
            if ar is not None and ru not in ar:
                continue
            uuids = [u for u, c in self.controls.items()
                     if c.get("room") == ru and self._cat_ok(u, prof) and self._shown(u, prof)]
            if uuids:
                out.append((ru, uuids))
        return out

    @staticmethod
    def _haus_hauptwert(items: list) -> tuple[str, str]:
        """Grosser Wert einer Raumkarte und die Zeile darunter, aus den Kacheln
        des Raums: die Ist-Temperatur (big) der ersten Raumregelung oder Sauna,
        sonst der Zustand des ersten Bausteins, der an ist, sonst der erste
        Zustand ueberhaupt. Beschreibende Zeilen (subInfo) zaehlen nicht."""
        for it in items:
            if it.get("big") is not None:
                return str(it["big"]), str(it.get("bigSub") or it.get("label") or "")
        for wahl in (lambda it: it.get("on"), lambda it: True):
            for it in items:
                if wahl(it) and it.get("sublabel") and not it.get("subInfo"):
                    return str(it["sublabel"]), str(it.get("label") or "")
        return "", ""

    @staticmethod
    def _haus_symbol(it: dict) -> dict:
        """Symbol einer Kachel fuer die Hausseite (eingebaut oder Loxone-Symbol,
        wie auf der Kachel)."""
        s = {"icon": it.get("icon") or "info"}
        if it.get("iconUrl"):
            s["iconUrl"] = it["iconUrl"]
        return s

    def _haus_aus(self, uuid: str) -> dict | None:
        """Aus-Befehl eines Bausteins fuer die Hausseite ({uuid, cmd, taste}) oder
        None, wenn sein Typ keinen hat (HAUS_AUS)."""
        c = self.controls.get(uuid) or {}
        e = HAUS_AUS.get(c.get("type"))
        if not e or not c.get("uuidAction"):
            return None
        return {"uuid": c["uuidAction"], "cmd": e[0], "taste": e[1]}

    def _haus_ein(self, uuid: str) -> dict | None:
        """Ein-Befehl eines Bausteins fuer die Tasten der Raumkarte (Aufbau
        "raeume", HAUS_EIN) oder None. Die Lichtsteuerung schaltet ihre erste
        Stimmung ohne "Aus" ein; ohne Stimmung hat sie keinen."""
        c = self.controls.get(uuid) or {}
        if not c.get("uuidAction"):
            return None
        if c.get("type") == "LightControllerV2":
            stimmungen = self._geste_stimmungen(uuid)
            return {"uuid": c["uuidAction"], "cmd": f"changeTo/{stimmungen[0][0]}"} if stimmungen else None
        cmd = HAUS_EIN.get(c.get("type"))
        return {"uuid": c["uuidAction"], "cmd": cmd} if cmd else None

    def _haus_tasten(self, uuids: list, items: list) -> list:
        """Tasten einer Raumkarte im Aufbau "raeume": die ersten HAUS_TASTEN
        Bausteine, die sich ab- und einschalten lassen (HAUS_AUS, _haus_ein),
        mit dem Befehl, der ihren Zustand umkehrt. Was HAUS_RUECKFRAGE nennt,
        fragt vor dem Einschalten nach (frage)."""
        out = []
        for u, it in zip(uuids, items):
            aus, ein = self._haus_aus(u), self._haus_ein(u)
            if not (aus and ein):
                continue
            an = bool(it.get("on"))
            t = {"id": u, "name": it.get("label") or "", "an": an, "zustand": it.get("sublabel") or "",
                 "cmd": {"uuid": aus["uuid"], "cmd": aus["cmd"]} if an else ein, **self._haus_symbol(it)}
            frage = HAUS_RUECKFRAGE.get(self.controls[u].get("type"))
            if frage and not an:
                t["frage"] = frage
            if it.get("secured"):
                t["secured"] = True
            out.append(t)
            if len(out) == HAUS_TASTEN:
                break
        return out

    def _haus_blick(self, uuids: list, items: list, raum: str, energie: str | None, hinweise: set) -> list:
        """"Auf einen Blick" im Aufbau "spalte": Bausteine, die einen Zustand
        melden, sich aber nicht abschalten lassen (nicht in HAUS_AUS, etwa
        Postkasten, Lueftung, Zentral-Bausteine). Was einen grossen Wert hat
        (Raumregelung, Sauna), steht schon auf der Raumkarte, der Energie-
        Baustein im Kopf der Spalte, ein Baustein mit Hinweis darueber unter
        den Hinweisen; beschreibende Zeilen (subInfo) zaehlen nicht. Ein Tipp
        oeffnet den Baustein."""
        out = []
        for u, it in zip(uuids, items):
            if self._haus_aus(u) or it.get("big") is not None or u == energie or u in hinweise \
                    or not it.get("sublabel") or it.get("subInfo"):
                continue
            b = {"id": u, "zustand": str(it["sublabel"]), "name": " · ".join(x for x in (it.get("label"), raum) if x),
                 **self._haus_symbol(it)}
            if it.get("nav"):
                b["nav"] = it["nav"]
            out.append(b)
        return out

    def _haus_hinweise(self, kacheln: list) -> list:
        """Hinweise der Hausseite aus den Kacheln ihrer Raeume [(uuid, kachel,
        raum)]: was die Kachel selbst nennt (hinweis), sonst ihr Ton
        (HINWEIS_TON) mit ihrem Zustand als Text. Nach Stufe (HINWEIS_STUFEN),
        innerhalb einer Stufe in der Folge der Raeume. Ein Tipp oeffnet den
        Baustein. Die Bedingung steht damit nur an der Kachel; die Seite kommt
        mit jeder Zustandsaenderung neu (broadcaster)."""
        out = []
        for u, it, raum in kacheln:
            h = it.get("hinweis") or {}
            stufe = h.get("stufe") or HINWEIS_TON.get(it.get("tone"))
            text = h.get("text") or it.get("sublabel")
            if stufe not in HINWEIS_STUFEN or not text:
                continue
            label = it.get("label") or ""
            wo = [label] + ([raum] if raum != label else []) + [h.get("zusatz")]
            x = {"id": u, "stufe": stufe, "titel": str(text), "wo": " · ".join(w for w in wo if w),
                 **({"icon": h["symbol"]} if h.get("symbol") else self._haus_symbol(it))}
            if it.get("nav"):
                x["nav"] = it["nav"]
            out.append(x)
        out.sort(key=lambda x: HINWEIS_STUFEN.index(x["stufe"]))
        return out

    def _haus_spieler(self, zonen: list, wahl, prof: dict | None) -> dict | None:
        """Spieler der Hausseite: die gewaehlte Zone (Route "zone"), sonst die
        erste, die spielt, sonst die erste. Inhalt aus den Bloecken der
        Detailseite (player_blocks: Cover, Titel, Transport, Lautstaerke), damit
        Befehle und Texte dieselben sind; dazu alle Zonen zum Umschalten,
        wie auf der Detailseite das ⋮ zur Musikauswahl (Route des more-Blocks)
        und die ersten HAUS_SENDER Favoriten der Zone (_haus_sender)."""
        if not zonen:
            return None
        kacheln = {u: self._control_item(u, prof) for u in zonen}
        spielt = {u: bool(kacheln[u].get("on")) for u in zonen}
        zone = wahl if wahl in zonen else next((u for u in zonen if spielt[u]), zonen[0])
        bloecke = self.player_blocks(zone, mehr=True) or []

        def block(k):
            return next((b for b in bloecke if b.get("k") == k), {})

        def zname(u):
            c = self.controls.get(u) or {}
            return _clean((self.rooms.get(c.get("room")) or {}).get("name")) or _clean(c.get("name"))
        titel, regler = block("title"), block("slider")
        sp = {"zone": zone, "name": zname(zone), "spielt": spielt[zone],
              "titel": str(titel.get("text") or ""), "sub": str(titel.get("sub") or ""),
              "cover": block("cover").get("src") or "",
              "tasten": [{"icon": z.get("icon"), "cmd": z.get("cmd")}
                         for z in (block("row").get("cells") or []) if z.get("cmd")],
              # je Zone, was sie spielt (Zustand ihrer Kachel), fuer die Zonenliste
              "zonen": [{"id": u, "name": zname(u), "spielt": spielt[u],
                         "titel": str(kacheln[u].get("sublabel") or "") if spielt[u] else ""} for u in zonen]}
        if regler.get("cmd"):
            sp["laut"] = {"wert": int(regler.get("value") or 0), "cmd": regler["cmd"],
                          "min": int(regler.get("min") or 0), "max": int(regler.get("max") or 100),
                          "schritt": PROZENT_SCHRITT}
        if block("more").get("route"):
            sp["mehr"] = block("more")["route"]
        sp["sender"] = self._haus_sender(zone, spielt[zone], (sp["titel"], sp["sub"]))
        if self._gesichert(zone):
            sp["secured"] = True
        return sp

    def _haus_sender(self, zone: str, spielt: bool, texte: tuple) -> list:
        """Favoriten der Zone fuer den Spieler der Hausseite, dieselben wie in
        der Musikauswahl (_zonen_favoriten): [{name, cover, cmd}], hoechstens
        HAUS_SENDER. Welcher laeuft (laeuft), sagt der Miniserver nicht; die
        Zone nennt nur Titel und Sender. Ein Favorit gilt als laufend, wenn
        die Zone spielt und er genau so heisst wie einer dieser Texte (oder
        der Name, den der Audioserver-Kanal meldet), sonst ist keiner markiert.
        Sind noch keine Favoriten da, fordert der Server sie an
        (_haus_sender_anfordern)."""
        favs, _ = self._zonen_favoriten(zone)
        if not favs:
            self._haus_sender_anfordern(zone)
            return []
        jetzt = self._laufende_namen(zone, texte) if spielt else set()
        out = []
        for f in favs[:HAUS_SENDER]:
            x = {"name": f["label"], "cover": f["cover"], "cmd": f["cmd"]}
            if str(f["label"]).strip().casefold() in jetzt:
                x["laeuft"] = True
            out.append(x)
        return out

    def _laufende_namen(self, zone: str, texte: tuple) -> set:
        """Namen, unter denen ein Favorit der Zone als laufend gilt: die Texte
        ihres Titels (Titel, Zweitzeile) und was der Audioserver-Kanal als
        Name bzw. Album meldet, ohne Gross-/Kleinschreibung. Der Miniserver
        sagt nicht, welcher Favorit laeuft."""
        sm = self._sonn_for(self.controls.get(zone) or {}) or {}
        return {str(t).strip().casefold() for t in (*texte, sm.get("name"), sm.get("album")) if t}

    def _haus_sender_anfordern(self, zone: str) -> None:
        """Favoriten einer Zone im Hintergrund anfordern (prime_favs), wie es
        die Musikauswahl beim Oeffnen tut: hoechstens alle HAUS_SENDER_NEU_S je
        Zone, denn die Hausseite wird bei jeder Zustandsaenderung neu
        gerechnet. Das Ergebnis kommt ueber _dirty mit dem naechsten Rendern.
        Ohne laufende Ereignisschleife (Aufruf ausserhalb des Servers) nichts."""
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return
        jetzt = time.monotonic()
        zuletzt = self._haus_sender_zeit.get(zone)
        if zuletzt is not None and jetzt - zuletzt < HAUS_SENDER_NEU_S:
            return
        self._haus_sender_zeit[zone] = jetzt
        self._spawn(self.prime_favs(zone))

    def _haus_energie(self, uuids: list, prof: dict | None) -> dict | None:
        """Energie fuer den Kopf der Hausseite: der erste Energieflussmonitor bzw.
        Energiemanager unter den Bausteinen der Seite, sonst der erste sichtbare
        der Anlage. Text wie auf seiner Kachel, dazu Erzeugung und Verbrauch in
        Watt wie im Energiefluss (energy_blocks); ein Tipp oeffnet ihn."""
        typen = ("EFM", "EnergyManager2")
        u = next((x for x in uuids if (self.controls.get(x) or {}).get("type") in typen), None)
        if u is None:
            u = next((x for x, c in self.controls.items() if c.get("type") in typen and self._shown(x, prof)), None)
        if u is None:
            return None
        it = self._control_item(u, prof)
        e = {"id": u, "label": it.get("label") or "", "wert": it.get("sublabel") or "",
             "nav": it.get("nav") or {"view": "control", "id": u}}
        summen = (self.energy_blocks(u) or {}).get("totals") or {}

        def watt(v):   # gerundet; unbekannt (None, NaN, unendlich) bleibt weg
            return round(v) if isinstance(v, (int, float)) and math.isfinite(v) else None
        cons, prod = watt(summen.get("cons")), watt(summen.get("prod"))
        if cons is not None:
            e["cons"] = cons
            if prod is not None:
                e["prod"] = prod
        return e

    def _haus_schnell(self, prof: dict | None) -> list:
        """Schnellaktionen der Hausseite (HAUS_SCHNELL): je Art der erste
        Zentral-Baustein der Anlage, den die Ansicht nicht ausblendet, mit
        seinem Befehl und wie viele seiner Mitglieder an sind (_zentral_an).
        Ohne den Baustein keine Taste. Die Anzahl kommt mit jeder
        Zustandsaenderung neu (broadcaster rendert die Seite), die Visu fragt
        nicht nach. Ein gesicherter Baustein (Visu-PIN) fragt in der Visu nach
        der PIN wie jede Taste."""
        out = []
        for art, (typ, label, cmd) in HAUS_SCHNELL.items():
            u = next((x for x, c in self.controls.items()
                      if c.get("type") == typ and c.get("uuidAction") and self._shown(x, prof)), None)
            if u is None:
                continue
            c = self.controls[u]
            s = {"art": art, "id": u, "label": label, "an": self._zentral_an(c),
                 "cmd": {"uuid": c["uuidAction"], "cmd": cmd}}
            if c.get("isSecured"):
                s["secured"] = True
            out.append(s)
        return out

    def _view_haus(self, route: dict, prof: dict | None = None) -> dict:
        """Hausuebersicht: je Raum eine Karte (Hauptwert, Symbole, wie viel an
        ist; ein Tipp oeffnet den Raum), "Gerade aktiv" (was an ist und sich
        abschalten laesst, mit Aus-Taste), die Schnellaktionen (_haus_schnell),
        der Spieler einer Audio-Zone und die Energie fuer den Kopf. Uhr, Wetter
        und Termine kommen in der Visu aus der Front. Route: zone (gewaehlte
        Zone), liste (HAUS_LISTEN: Unterseite mit allen aktiven Geraeten bzw.
        allen Hinweisen). Die Hinweise (_haus_hinweise) hat jeder Aufbau.
        Der Aufbau der Ansicht (HAUS_AUFBAUTEN) bringt dazu: "raeume" je
        Raumkarte ihre Tasten (_haus_tasten), "spalte" "Auf einen Blick"
        (_haus_blick)."""
        aufbau = (prof or {}).get("hausAufbau")
        aufbau = aufbau if aufbau in HAUS_AUFBAUTEN else HAUS_AUFBAU_STANDARD
        raeume, aktiv, zonen, alle, blick_roh, kacheln = [], [], [], [], [], []
        for ru, uuids in self._haus_raeume(prof):
            name = _clean(self.rooms[ru].get("name")) or "Raum"
            items = [self._control_item(u, prof, ohne_raum=name) for u in uuids]
            wert, sub = self._haus_hauptwert(items)
            schaltbar, sonst, an = [], [], 0
            for u, it in zip(uuids, items):
                alle.append(u)
                kacheln.append((u, it, name))
                t = self.controls[u].get("type")
                if t in ("AudioZone", "AudioZoneV2"):
                    zonen.append(u)
                aus = self._haus_aus(u)
                if it.get("big") is None:
                    # mit grossem Wert steht der Baustein schon als Hauptwert da
                    (schaltbar if aus else sonst).append(it)
                if aus and it.get("on"):
                    an += 1
                    a = {"id": u, "label": it.get("label") or "", "raum": name,
                         "zustand": it.get("sublabel") or "", "aus": {"uuid": aus["uuid"], "cmd": aus["cmd"]},
                         "taste": aus["taste"], **self._haus_symbol(it)}
                    if it.get("secured"):
                        a["secured"] = True
                    aktiv.append(a)
            symbole = [dict(self._haus_symbol(it), on=bool(it.get("on")))
                       for it in (schaltbar + sonst)[:HAUS_SYMBOLE]]
            raum = {"id": ru, "name": name, "wert": wert, "sub": sub, "an": an,
                    "anzahl": len(uuids), "symbole": symbole,
                    "nav": {"view": "group", "kind": "room", "id": ru}}
            if aufbau == "raeume":
                raum["tasten"] = self._haus_tasten(uuids, items)
            elif aufbau == "spalte":
                blick_roh.append((uuids, items, name))
            raeume.append(raum)
        energie = self._haus_energie(alle, prof)
        tab = (route or {}).get("tab") or HAUS_TAB
        if _is_pick(tab):
            # freie Seite: ihr Name ist der Titel
            seiten, i = _pick_tabs(prof), _pick_index(tab)
            titel = (seiten[i].get("name") if 0 <= i < len(seiten) else "") or HAUS_TITEL
        else:
            titel = HAUS_TITEL
        hinweise = self._haus_hinweise(kacheln)
        out = {"t": "view", "title": titel, "tab": tab, "route": route, "layout": "haus", "aufbau": aufbau,
               "raeume": raeume, "aktiv": aktiv, "hinweise": hinweise, "schnell": self._haus_schnell(prof),
               "spieler": self._haus_spieler(zonen, (route or {}).get("zone"), prof),
               "energie": energie}
        if aufbau == "spalte":
            eid, mit = (energie or {}).get("id"), {h["id"] for h in hinweise}
            out["blick"] = [b for uuids, items, name in blick_roh
                            for b in self._haus_blick(uuids, items, name, eid, mit)]
        if (route or {}).get("liste") in HAUS_LISTEN:
            out["liste"] = route["liste"]
        return out
