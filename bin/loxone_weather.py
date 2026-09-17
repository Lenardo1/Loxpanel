"""Wetter vom Loxone-Wetterserver statt von Open-Meteo.

Hat die Anlage den Loxone-Wetterdienst, schickt der Miniserver das Wetter ueber
den WebSocket als eigene Binaertabelle (Kennung 7, zerlegt in `loxone_ws.py`).
Dieses Modul rechnet die rohen Eintraege in genau die Form um, die
`front_info.fetch_weather()` liefert — das Panel merkt vom Wechsel der Quelle
nichts.

Grundsatz: nur anzeigen, was der Miniserver eindeutig hergibt.

* Die **Wetterlage** steht als Text in SEINER Struktur (`weatherServer.
  weatherTypeTexts`, in der Sprache der Anlage). Hier liegt also keine Tabelle
  mit Loxone-Wettercodes — die Nummern sind je nach Quelle unterschiedlich
  dokumentiert, der Miniserver selbst ist die verlaessliche Auskunft.
* Die **Einheiten** stehen als Formatstrings in `weatherServer.format`
  ("%.1f km/h"). Laesst sich eine Einheit nicht bestimmen, faellt der Wert weg —
  lieber eine Kachel weniger als eine falsch beschriftete Zahl.
* Laesst sich das Wetter gar nicht beschriften oder sind die Zeitstempel
  unplausibel, liefert `build()` None und der Aufrufer bleibt bei Open-Meteo.

Was der Wetterdienst nicht liefert, bleibt leer: Regenwahrscheinlichkeit und
UV-Index gibt es dort nicht (`solarRadiation` ist Einstrahlung in W/m², kein
UV-Index). Das Panel blendet leere Werte von sich aus aus.
"""
from __future__ import annotations

import logging
import math
import re
from datetime import date, datetime, timedelta, timezone

import front_info

log = logging.getLogger("loxpanel.wetter")

# Loxone zaehlt Sekunden seit dem 01.01.2009 in UTC. Belegt an einer Anlage in
# Oesterreich (CEST): die Stundenwerte lagen durchgaengig 2 h vor der Ortszeit,
# also genau um den UTC-Abstand. Umgerechnet wird je Eintrag einzeln, damit die
# Sommerzeit-Umstellung mitten in der Vorhersage nicht verrutscht.
LOX_EPOCH = datetime(2009, 1, 1, tzinfo=timezone.utc)

# Toleranz der Plausibilitaetspruefung: liegt der aktuelle Messwert weiter weg,
# stimmt an der Zeitrechnung etwas nicht und die Daten bleiben ungenutzt.
MAX_RUECK = timedelta(hours=36)
MAX_VOR = timedelta(days=16)

# Reihenfolge entscheidet: "Schneeregen" enthaelt "regen", "wolkenlos" enthaelt
# "wolken". Der erste Treffer gewinnt. Verglichen wird kleingeschrieben und ohne
# Umlaute (siehe _schluessel), die Begriffe decken Deutsch und Englisch ab.
ICON_WORTE = (
    ("storm",   ("gewitter", "thunder", "blitz")),
    ("snow",    ("schnee", "snow", "flocken", "graupel", "hagel", "hail", "sleet")),
    ("drizzle", ("niesel", "drizzle", "spruehregen")),
    ("rain",    ("regen", "rain", "schauer", "shower", "niederschlag")),
    ("fog",     ("nebel", "fog", "mist", "dunst", "haze")),
    ("sun",     ("wolkenlos", "klar", "clear", "sonnig", "sunny", "heiter", "fair")),
    ("cloud",   ("bewoelkt", "wolkig", "wolke", "cloud", "overcast", "bedeckt", "trueb")),
)

# Je hoeher, desto eher steht das Symbol fuer den Tag (bei Gleichstand).
ICON_GEWICHT = {"storm": 6, "snow": 5, "rain": 4, "drizzle": 3, "fog": 2, "cloud": 1, "sun": 0}

# Schreibweisen, unter denen eine Groesse im `format`-Block stehen kann. Die
# erste Variante ist der Feldname aus der Wetter-Tabelle selbst.
FORMAT_KEYS = {
    "temp": ("temperature", "temp"),
    "wind": ("windSpeed", "wind_speed", "windspeed", "wind"),
    "precip": ("precipitation", "precip", "rain"),
    "pressure": ("barometricPressure", "barometric_pressure", "pressure"),
}


def _schluessel(text: str) -> str:
    """Kleinbuchstaben ohne Umlaute — Vergleichsform fuer die Icon-Zuordnung."""
    t = str(text).lower()
    for a, b in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss")):
        t = t.replace(a, b)
    return t


def icon_for(text) -> str | None:
    """Wetterlage-Text des Miniservers -> Icon-Schluessel des Panels.

    None, wenn kein Begriff passt (z.B. weil die Anlage eine Sprache spricht,
    die hier nicht hinterlegt ist). Dann wird nichts angezeigt, statt ein
    beliebiges Symbol zu zeigen."""
    if not text:
        return None
    t = _schluessel(text)
    for icon, worte in ICON_WORTE:
        if any(w in t for w in worte):
            return icon
    return None


def unit_of(fmt) -> str | None:
    """Einheit aus einem Loxone-Formatstring: "%.1f km/h" -> "km/h".

    Nimmt auch `{"format": "..."}` entgegen. None, wenn kein Platzhalter mit
    angehaengter Einheit erkennbar ist."""
    if isinstance(fmt, dict):
        fmt = fmt.get("format") or fmt.get("unit")
    if not isinstance(fmt, str):
        return None
    m = re.search(r"%[-+ #0-9.']*[a-zA-Z]", fmt)
    rest = (fmt[m.end():] if m else fmt).strip()
    rest = rest.replace("%%", "%")
    return rest or None


def _fmt_unit(fmt_block: dict, feld: str) -> str | None:
    """Einheit einer Groesse aus dem `format`-Block der Struktur."""
    for key in FORMAT_KEYS.get(feld, ()):
        if key in fmt_block:
            u = unit_of(fmt_block[key])
            if u:
                return u
    return None


def _zahl(v):
    """Endliche Zahl oder None (die Tabelle kann NaN fuer "kein Wert" liefern)."""
    return v if isinstance(v, (int, float)) and math.isfinite(v) else None


def _zeit(ts) -> datetime | None:
    """Loxone-Zeitstempel -> Ortszeit ohne Zeitzonen-Angabe."""
    try:
        return (LOX_EPOCH + timedelta(seconds=int(ts))).astimezone().replace(tzinfo=None)
    except (TypeError, ValueError, OverflowError, OSError):
        return None


def _volle_stunde(t: datetime) -> datetime:
    return t.replace(minute=0, second=0, microsecond=0)


def weather_texts(cfg: dict) -> dict:
    """`weatherTypeTexts` der Struktur -> {Wettertyp-Nummer: Text}.

    Der Miniserver liefert das je nach Firmware als Zuordnung oder als Liste;
    beides wird angenommen, alles andere ergibt eine leere Zuordnung."""
    roh = (cfg or {}).get("weatherTypeTexts")
    out: dict[int, str] = {}
    if isinstance(roh, dict):
        paare = roh.items()
    elif isinstance(roh, list):
        paare = [(e.get("id"), e.get("text") or e.get("name") or e.get("desc"))
                 for e in roh if isinstance(e, dict)]
    else:
        return out
    for k, v in paare:
        if isinstance(v, dict):
            v = v.get("text") or v.get("name")
        if not isinstance(v, str) or not v.strip():
            continue
        try:
            out[int(k)] = v.strip()
        except (TypeError, ValueError):
            continue
    return out


def _tagesicon(eintraege: list, texte: dict) -> str | None:
    """Symbol eines Tages: das haeufigste der einordenbaren Symbole, bei
    Gleichstand das wettermaessig kraeftigere (Gewitter vor Sonne)."""
    zaehler: dict[str, int] = {}
    for _t, e in eintraege:
        ic = icon_for(texte.get(_typ(e)))
        if ic:
            zaehler[ic] = zaehler.get(ic, 0) + 1
    if not zaehler:
        return None
    return max(zaehler.items(), key=lambda kv: (kv[1], ICON_GEWICHT.get(kv[0], 0)))[0]


def _typ(e: dict):
    try:
        return int(e.get("type"))
    except (TypeError, ValueError):
        return None


def _spannen(eintraege: list) -> list:
    """Stundenabstand je Eintrag — der Wetterdienst liefert spaetere Tage
    groeber als stuendlich, sonst waere die Niederschlagssumme zu klein."""
    out = []
    for i, (t, _e) in enumerate(eintraege):
        if i + 1 < len(eintraege):
            h = (eintraege[i + 1][0] - t).total_seconds() / 3600.0
        else:
            h = out[-1] if out else 1.0
        out.append(h if 0 < h <= 6 else 1.0)
    return out


def build(cfg: dict, actual: list, forecast: list, *,
          sunrise: str | None = None, sunset: str | None = None,
          fore_days: int = 4, now: datetime | None = None) -> dict | None:
    """Wetter-Block fuer die Front bauen — oder None, wenn die Daten nicht
    tragfaehig sind (dann bleibt der Aufrufer bei Open-Meteo).

    `cfg` ist der `weatherServer`-Block der Struktur, `actual`/`forecast` sind
    die Eintragslisten aus `loxone_ws.LoxoneWS._parse_weather`. Sonnenzeiten
    kommen von aussen (der Miniserver fuehrt sie als globale States), damit die
    Kachel „Sonne" dieselbe Quelle nutzt wie der Nachtmodus."""
    now = now or datetime.now()
    texte = weather_texts(cfg)
    if not texte:
        log.info("Wetterserver: keine Wetterlage-Texte in der Struktur — Open-Meteo bleibt")
        return None

    cur = actual[0] if actual and isinstance(actual[0], dict) else None
    if cur is None:
        return None
    t_roh = _zeit(cur.get("ts"))
    if t_roh is None:
        return None
    # Der aktuelle Messwert IST "jetzt" — der Miniserver stempelt ihn auf die
    # laufende Stunde. Bleibt danach ein voller Stundenversatz, rechnet diese
    # Anlage in einer anderen Zeitzone als hier angenommen; der Abstand wird
    # gemessen und auf alle Eintraege angewandt, statt ihn zu raten. Ohne das
    # rutschen Stunden ueber die Tagesgrenze und "heute" bekommt fremde Werte.
    versatz = _volle_stunde(now) - _volle_stunde(t_roh)
    if abs(versatz) > MAX_RUECK:
        log.warning("Wetterserver: Zeitstempel unplausibel (%s statt ~%s) — Open-Meteo bleibt",
                    t_roh, now.replace(microsecond=0))
        return None
    if versatz:
        log.info("Wetterserver: Zeitstempel um %+d h gegen die Ortszeit verschoben — wird ausgeglichen",
                 round(versatz.total_seconds() / 3600))
    t_jetzt = t_roh + versatz

    fmt = cfg.get("format") if isinstance(cfg.get("format"), dict) else {}
    # Temperatur wird als Grad Celsius gelesen; nur eine ausdrueckliche
    # Fahrenheit-Angabe laesst die Quelle ausfallen (das Panel schreibt "°").
    t_unit = _fmt_unit(fmt, "temp") or ""
    if "f" in t_unit.lower().replace("°", ""):
        log.warning("Wetterserver liefert Temperatur in %s — Open-Meteo bleibt", t_unit)
        return None

    cond = texte.get(_typ(cur))
    icon = icon_for(cond)
    if not icon:
        log.info("Wetterserver: Wetterlage %r nicht einordenbar - Open-Meteo bleibt", cond)
        return None

    # Vorhersage nach Tagen buendeln (nur plausible Zeitstempel).
    tage: dict[date, list] = {}
    for e in forecast or []:
        if not isinstance(e, dict):
            continue
        t = _zeit(e.get("ts"))
        if t is None:
            continue
        t += versatz
        if not (now - MAX_RUECK <= t <= now + MAX_VOR):
            continue
        tage.setdefault(t.date(), []).append((t, e))
    if not tage:
        log.info("Wetterserver: keine brauchbare Vorhersage — Open-Meteo bleibt")
        return None
    for liste in tage.values():
        liste.sort(key=lambda p: p[0])

    heute = now.date()
    fore_days = max(1, min(7, int(fore_days or 4)))
    ab_heute = sorted(k for k in tage if k >= heute)[:fore_days]
    vorschau = []
    t_cur = _zahl(cur.get("temp"))
    for d in ab_heute:
        temps = [x for x in (_zahl(e.get("temp")) for _t, e in tage[d]) if x is not None]
        # Heute zaehlt der aktuelle Messwert mit: die Vorhersage beginnt bei der
        # laufenden Stunde, ohne ihn kann das Tageshoch UNTER der jetzigen
        # Temperatur liegen. Die Loxone-App rechnet genauso.
        if d == heute and t_cur is not None:
            temps.append(t_cur)
        vorschau.append({
            "day": front_info.day_label(d, heute),
            "icon": _tagesicon(tage[d], texte),
            "hi": round(max(temps)) if temps else None,
            "lo": round(min(temps)) if temps else None,
            "pop": None,            # Regenwahrscheinlichkeit liefert der Dienst nicht
        })

    # Niederschlagssumme heute: mm/h mal Stundenabstand des jeweiligen Eintrags.
    # Einheit des Niederschlags: "mm", "mm/h" oder — so fuehrt der Loxone-
    # Wetterdienst ihn — "l/m²/h". 1 l/m² ist 1 mm, die Summe stimmt also in
    # beiden Faellen; das Panel schreibt "mm".
    p_unit = (_fmt_unit(fmt, "precip") or "").lower().replace(" ", "")
    precip_sum = None
    if p_unit.startswith("mm") or p_unit.startswith("l/m"):
        heute_eintraege = tage.get(heute) or []
        spannen = _spannen(heute_eintraege)
        summe = 0.0
        for (_t, e), h in zip(heute_eintraege, spannen):
            p = _zahl(e.get("precip"))
            if p and p > 0:
                summe += p * h
        precip_sum = round(summe, 1)

    # Stundenverlauf ab der laufenden Stunde, hoechstens 24 Werte.
    ab = _volle_stunde(now)
    stunden = sorted((p for liste in tage.values() for p in liste if p[0] >= ab),
                     key=lambda p: p[0])[:24]
    hourly = [{"h": t.hour,
               "temp": (round(_zahl(e.get("temp"))) if _zahl(e.get("temp")) is not None else None),
               "pop": None,
               "icon": icon_for(texte.get(_typ(e)))}
              for t, e in stunden]

    # Wind nur mit bekannter Einheit; m/s wird auf km/h gebracht, damit beide
    # Quellen dasselbe anzeigen.
    wind = _zahl(cur.get("wind"))
    w_unit = _fmt_unit(fmt, "wind")
    if wind is None or not w_unit:
        wind, w_unit = None, None
    elif w_unit.lower().replace(" ", "") in ("m/s", "ms", "mps"):
        wind, w_unit = wind * 3.6, "km/h"

    pressure = _zahl(cur.get("pressure"))
    if pressure is not None and (_fmt_unit(fmt, "pressure") or "").lower() not in ("hpa", "mbar"):
        pressure = None          # ohne belegte Einheit nicht als hPa ausgeben

    # Hoch/Tief oben gilt fuer heute — nur, wenn heute auch in der Vorschau steht
    # (kurz nach Mitternacht kann der aelteste Eintrag schon von gestern sein).
    heute_vorschau = vorschau[0] if ab_heute and ab_heute[0] == heute else None
    feels = _zahl(cur.get("feels"))
    hum = _zahl(cur.get("humidity"))
    return {
        "temp": _zahl(cur.get("temp")),
        "cond": cond,
        "icon": icon,
        "hi": heute_vorschau["hi"] if heute_vorschau else None,
        "lo": heute_vorschau["lo"] if heute_vorschau else None,
        "feels": round(feels) if feels is not None else None,
        "wind": round(wind) if wind is not None else None,
        "wind_unit": w_unit,
        # Windrichtung in Grad, unveraendert durchgereicht: das Feld heisst beim
        # Wetterdienst "DD" und wird damit wie ueblich als Richtung gelesen, AUS
        # der der Wind weht — dieselbe Lesart wie bei Open-Meteo. Der Rohwert
        # steht in der Diagnose, falls das an einer Anlage nachzumessen ist.
        "wind_dir": _zahl(cur.get("wind_dir")),
        "humidity": round(hum) if hum is not None else None,
        "pressure": round(pressure) if pressure is not None else None,
        "is_day": _ist_tag(now, sunrise, sunset),
        "sunrise": sunrise,
        "sunset": sunset,
        "uv": None,                 # der Wetterdienst liefert Einstrahlung, keinen UV-Index
        "precip_sum": precip_sum,
        "forecast": vorschau,
        "hourly": hourly,
    }


def _ist_tag(now: datetime, sunrise: str | None, sunset: str | None):
    """1/0 zwischen Sonnenauf- und -untergang, None ohne Sonnenzeiten."""
    def _min(hm):
        try:
            h, _, m = str(hm).partition(":")
            return int(h) * 60 + int(m)
        except (TypeError, ValueError):
            return None
    a, b = _min(sunrise), _min(sunset)
    if a is None or b is None:
        return None
    jetzt = now.hour * 60 + now.minute
    return 1 if a <= jetzt < b else 0
