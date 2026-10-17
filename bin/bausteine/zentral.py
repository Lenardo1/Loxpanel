"""Bausteine der Visu, Familie Zentralbausteine (Typen mit Praefix Central): nur die Kachel, die Detailseite ist die Gruppe.

Kachel (@kachel) und Detailseite (@detail) je Typ, siehe bausteine/__init__.py.
Die Helfer (app._state, app._fmt_num ...) sind Mixins: die allgemeinen in helfer.py,
die dieser Familie in der Klasse unten; App erbt sie ueber bausteine.BausteinHelfer."""
from __future__ import annotations

from bausteine import kachel_praefix
from bausteine.gemeinsam import LIGHT


@kachel_praefix("Central")
def kachel_zentralbaustein(app, uuid, c, it):
    t = c.get("type")
    n = app._zentral_an(c)
    # Einzahl bei genau einem: "Spielt in 1 Raum", nicht "in 1 Räumen"
    if t == "CentralLightController":
        it["sublabel"] = f"In {n} {'Raum' if n == 1 else 'Räumen'} aktiv" if n else "Aus"
    elif t == "CentralAudioZone":
        it["sublabel"] = f"Spielt in {n} {'Raum' if n == 1 else 'Räumen'}" if n else "Aus"
    elif t in ("CentralGate", "CentralWindow"):
        it["sublabel"] = f"{n} offen" if n else "Alle geschlossen"
    elif t == "CentralJalousie":
        # Auf/Ab direkt auf der Kachel wie bei einer Jalousie; ein Tipp
        # oeffnet die Detailseite mit allen Zentralbefehlen
        ua = c.get("uuidAction")
        it.update(sublabel="Alle Jalousien", subInfo=True,
                  controls=[{"icon": "triup", "cmd": {"uuid": ua, "cmd": "FullUp"}},
                            {"icon": "tridown", "cmd": {"uuid": ua, "cmd": "FullDown"}}])
    elif t == "CentralAlarm":
        it.update(sublabel="Alarmzentrale", subInfo=True)
    if "sublabel" not in it:
        it.update(sublabel="Zentral", subInfo=True)
    jal = t == "CentralJalousie"
    it.update(icon="blind" if jal else "central", on=(n > 0),
              nav={"view": "control", "id": uuid} if jal else {"view": "group", "kind": "central", "id": uuid})


class ZentralHelfer:
    """Helfer der Familie Zentral fuer Kachel, Detailseite und Unterseiten. Mixin: App erbt sie
    ueber bausteine.BausteinHelfer, gerufen wird ueber self bzw. app."""

    def _zentral_an(self, c: dict) -> int:
        """Wie viele Mitglieder eines Zentral-Bausteins (details.controls) an
        sind: Lichtsteuerungen mit aktiver Stimmung, Audio-Zonen, die spielen,
        Tore und Fenster, die offen stehen. Andere Zentralen: 0. Dieselbe Zahl
        zeigen seine Kachel und die Schnellaktion der Hausseite."""
        t = c.get("type")
        muuids = [m.get("uuid") for m in ((c.get("details") or {}).get("controls") or [])
                  if m.get("uuid") in self.controls]
        if t == "CentralLightController":
            return sum(1 for mu in muuids if LIGHT.render(self._with_uuid(mu), self.states)["on"])
        if t == "CentralAudioZone":
            return sum(1 for mu in muuids if self._state(self.controls[mu], "playState") == 2)
        if t in ("CentralGate", "CentralWindow"):
            return sum(1 for mu in muuids if (self._state(self.controls[mu], "position") or 0) > 0)
        return 0
