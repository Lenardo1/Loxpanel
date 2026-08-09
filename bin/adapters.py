"""Control-Adapter: bilden Loxone-Controls auf Kachel-Zustand + Befehle ab.

Pro Loxone-Control-Typ eine Klasse. Jeder Adapter sagt,
  - welche State-UUIDs zu abonnieren sind (state_uuids),
  - wie aus den aktuellen State-Werten der Anzeige-Zustand wird (render),
  - welcher Control-Befehl zu einer Aktion gehoert (command).

Die Adapter arbeiten auf dem rohen LoxAPP3.json-Control-Dict
(structure["controls"][uuid]) - das enthaelt "uuidAction", "type", "name",
"states" (Name -> State-UUID).
"""
from __future__ import annotations

import json
from typing import Any


def _parse_json_state(value: Any) -> Any:
    if isinstance(value, str):
        try:
            return json.loads(value)
        except ValueError:
            return value
    return value


class ControlAdapter:
    type: str | None = None

    def _state_uuid(self, control: dict, name: str) -> str | None:
        return (control.get("states") or {}).get(name)

    def state_uuids(self, control: dict) -> list[str]:
        return []

    def render(self, control: dict, states: dict[str, Any]) -> dict:
        return {}

    def command(self, control: dict, action: str, states: dict[str, Any]) -> tuple[str, str] | None:
        """Gibt (control_uuidAction, befehl) zurueck oder None."""
        return None


class LightControllerV2Adapter(ControlAdapter):
    type = "LightControllerV2"
    OFF_MOOD = 778

    def state_uuids(self, control: dict) -> list[str]:
        return [u for u in (self._state_uuid(control, "activeMoods"),
                            self._state_uuid(control, "moodList")) if u]

    def _active(self, control: dict, states: dict) -> list:
        val = _parse_json_state(states.get(self._state_uuid(control, "activeMoods")))
        return val if isinstance(val, list) else []

    def _moods(self, control: dict, states: dict) -> list[dict]:
        val = _parse_json_state(states.get(self._state_uuid(control, "moodList")))
        return val if isinstance(val, list) else []

    def render(self, control: dict, states: dict) -> dict:
        active = self._active(control, states)
        names = {m.get("id"): m.get("name") for m in self._moods(control, states)}
        on = bool(active) and active != [self.OFF_MOOD]
        label = ", ".join(str(names.get(i, i)) for i in active if i != self.OFF_MOOD) or "Aus"
        return {"on": on, "label": label, "activeMoods": active}

    def moods(self, control: dict, states: dict) -> list[dict]:
        """Oeffentlich: verfuegbare Stimmungen [{id,name,...}]."""
        return self._moods(control, states)

    def active_moods(self, control: dict, states: dict) -> list:
        """Oeffentlich: Liste der aktiven Mood-IDs."""
        return self._active(control, states)

    def _first_on_mood(self, control: dict, states: dict) -> int:
        for m in self._moods(control, states):
            if m.get("id") != self.OFF_MOOD:
                return int(m["id"])
        return 1

    def command(self, control: dict, action: str, states: dict) -> tuple[str, str] | None:
        uuid = control.get("uuidAction") or control.get("uuid")
        if not uuid:
            return None
        if action == "off":
            return (uuid, f"changeTo/{self.OFF_MOOD}")
        if action == "on":
            return (uuid, f"changeTo/{self._first_on_mood(control, states)}")
        if action == "toggle":
            on = self.render(control, states)["on"]
            return self.command(control, "off" if on else "on", states)
        return None


class JalousieAdapter(ControlAdapter):
    """Rollladen/Jalousie: Position 0..1 (0=offen/oben, 1=zu/unten)."""
    type = "Jalousie"

    def state_uuids(self, control: dict) -> list[str]:
        s = control.get("states") or {}
        return [u for u in (s.get("position"), s.get("shadePosition")) if u]

    def _position(self, control: dict, states: dict):
        su = (control.get("states") or {}).get("position")
        v = states.get(su) if su else None
        try:
            return float(v)
        except (TypeError, ValueError):
            return None

    def render(self, control: dict, states: dict) -> dict:
        p = self._position(control, states)
        if p is None:
            return {"on": False, "label": "–", "pct": None}
        pct = round(p * 100)
        return {"on": p > 0.02, "label": ("Offen" if pct <= 0 else f"{pct}% zu"), "pct": pct}


_ADAPTERS: dict[str, ControlAdapter] = {
    a.type: a for a in (LightControllerV2Adapter(), JalousieAdapter())
}


def get_adapter(control_type: str) -> ControlAdapter | None:
    return _ADAPTERS.get(control_type)
