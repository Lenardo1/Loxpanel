"""
Front-Info: Kalender (iCal-Abo) + Wetter (Open-Meteo) fuer die Panel-Front.

Eigenstaendig, ohne Abhaengigkeit zu Fremdprojekten. Der Server ruft `load_front()`
periodisch auf und schickt das Ergebnis per WebSocket an die Panels; die Uhr-
Startseite (Screensaver) zeigt Wetter oben und die naechsten Termine unten an.

Kalender: laedt die .ics (`webcal://` -> `https://`), parst die VEVENTs, loest
Serientermine (RRULE) auf und liefert die naechsten Tage.
Wetter: Open-Meteo (kostenlos, KEIN API-Key) per Koordinaten; `timezone=auto`
richtet sich nach dem Standort.

Alle Anzeige-Texte (Wochentage, "Heute"/"Morgen"/"ganztägig", Wetterlage) entstehen
HIER — das Panel zeigt nur an (LoxPanel-Konvention: Panel-Texte stehen im Server).
Zahlen (Temperaturen) gehen als Zahl an das Panel, das sie deutsch formatiert.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, date, time, timedelta

import aiohttp

log = logging.getLogger("loxpanel.front")

# icalendar/dateutil sind optional: fehlen sie, bleibt der Kalender leer statt zu
# crashen (Wetter funktioniert unabhaengig davon weiter).
try:
    from icalendar import Calendar
    HAVE_ICAL = True
except ImportError:
    HAVE_ICAL = False

try:
    from dateutil.rrule import rrulestr
    HAVE_RRULE = True
except ImportError:
    HAVE_RRULE = False

WD = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]
OPEN_METEO = "https://api.open-meteo.com/v1/forecast"

# WMO-Wettercode -> deutsche Lage (Open-Meteo liefert diese Codes).
WMO_TEXT = {
    0: "Klar", 1: "Überwiegend klar", 2: "Teils bewölkt", 3: "Bedeckt",
    45: "Nebel", 48: "Reifnebel",
    51: "Leichter Niesel", 53: "Niesel", 55: "Starker Niesel",
    56: "Gefrierender Niesel", 57: "Gefrierender Niesel",
    61: "Leichter Regen", 63: "Regen", 65: "Starker Regen",
    66: "Gefrierender Regen", 67: "Gefrierender Regen",
    71: "Leichter Schnee", 73: "Schnee", 75: "Starker Schnee", 77: "Schneegriesel",
    80: "Regenschauer", 81: "Regenschauer", 82: "Starke Regenschauer",
    85: "Schneeschauer", 86: "Starke Schneeschauer",
    95: "Gewitter", 96: "Gewitter mit Hagel", 99: "Gewitter mit Hagel",
}


def wmo_icon(code) -> str:
    """WMO-Code -> Icon-Schluessel fuer das Panel (dort als SVG gezeichnet)."""
    try:
        code = int(code)
    except (TypeError, ValueError):
        return "cloud"
    if code in (0, 1):
        return "sun"
    if code in (2, 3):
        return "cloud"
    if code in (45, 48):
        return "fog"
    if code in (51, 53, 55, 56, 57):
        return "drizzle"
    if code in (61, 63, 65, 66, 67, 80, 81, 82):
        return "rain"
    if code in (71, 73, 75, 77, 85, 86):
        return "snow"
    if code in (95, 96, 99):
        return "storm"
    return "cloud"


def normalize_ical_url(url) -> str:
    """`webcal://` / `webcals://` -> `https://` (Apple/iCloud teilt webcal-Links)."""
    url = (url or "").strip()
    if url.startswith("webcal://"):
        return "https://" + url[len("webcal://"):]
    if url.startswith("webcals://"):
        return "https://" + url[len("webcals://"):]
    return url


def _day_label(d: date, today: date) -> str:
    """`date` -> "Heute" / "Morgen" / "Sa 12.9." (Wochentag + Tag.Monat)."""
    delta = (d - today).days
    if delta == 0:
        return "Heute"
    if delta == 1:
        return "Morgen"
    return f"{WD[d.weekday()]} {d.day}.{d.month}."


def _local_naive(dt: datetime) -> datetime:
    """Zeitzone in ORTSZEIT umrechnen und danach entfernen; naive Zeiten bleiben.

    Nicht einfach `tzinfo` abschneiden: Google-Feeds liefern Einzeltermine als UTC
    (`...T120000Z`), die sonst um den UTC-Abstand falsch am Panel stehen.
    """
    return dt.astimezone().replace(tzinfo=None) if dt.tzinfo is not None else dt


def _occurrences(component, range_start: date, range_end: date):
    """Auftreten eines VEVENT im Zeitraum (loest RRULE-Serien auf).

    Liefert Tupel (Zeitpunkt, all_day): bei Ganztagsterminen ein `date`, sonst ein
    naives `datetime` in ORTSZEIT (die Wanduhrzeit, die das Panel anzeigt).
    """
    dtstart_prop = component.get("dtstart")
    if not dtstart_prop:
        return
    dtstart = dtstart_prop.dt
    all_day = not isinstance(dtstart, datetime)

    if all_day:
        base = datetime.combine(dtstart, time.min)
    else:
        # Aware bleibt aware: dateutil loest die Serie dann in der Original-
        # Zeitzone auf, also ueber Sommer-/Winterzeit hinweg korrekt.
        base = dtstart

    range_start_dt = datetime.combine(range_start, time.min)
    range_end_dt = datetime.combine(range_end, time.max)
    if base.tzinfo is not None:
        # Grenzen sind naive Ortszeit -> in dieselbe (aware) Welt heben, sonst
        # vergleicht dateutil aware mit naiv und wirft TypeError.
        range_start_dt = range_start_dt.astimezone()
        range_end_dt = range_end_dt.astimezone()
    rrule = component.get("rrule")

    if rrule and HAVE_RRULE:
        try:
            rule = rrulestr(rrule.to_ical().decode(), dtstart=base)
            for occ in rule.between(range_start_dt, range_end_dt, inc=True):
                occ_local = _local_naive(occ)
                yield (occ_local.date() if all_day else occ_local, all_day)
        except Exception as e:                       # kaputte RRULE nicht fatal
            log.warning("RRULE nicht lesbar: %s", e)
    elif not rrule:
        if all_day:
            d = dtstart if isinstance(dtstart, date) and not isinstance(dtstart, datetime) else dtstart.date()
            if range_start <= d <= range_end:
                yield (d, True)
        else:
            if range_start_dt <= base <= range_end_dt:
                yield (_local_naive(base), False)


def _parse_events(ics_bytes: bytes, days: int) -> list:
    """ICS-Bytes -> sortierte, anzeigefertige Terminliste fuer die naechsten `days`."""
    cal = Calendar.from_ical(ics_bytes)
    today = date.today()
    range_end = today + timedelta(days=max(1, int(days)) - 1)

    raw = []
    for comp in cal.walk():
        if comp.name != "VEVENT":
            continue
        title = str(comp.get("summary", "Termin")).strip() or "Termin"
        uid = str(comp.get("uid", ""))
        for occ, all_day in _occurrences(comp, today, range_end):
            if all_day:
                d = occ if isinstance(occ, date) and not isinstance(occ, datetime) else occ.date()
                raw.append((f"{uid}_{d.isoformat()}", d, None, True, title))
            else:
                raw.append((f"{uid}_{occ.isoformat()}", occ.date(), occ.time(), False, title))

    seen = set()
    out = []
    for key, d, t, all_day, title in raw:
        if key in seen:
            continue
        seen.add(key)
        sort_time = "00:00" if all_day else f"{t.hour:02d}:{t.minute:02d}"
        out.append({
            "day": _day_label(d, today),
            "date": d.isoformat(),          # ISO-Datum (fuer das Monatsraster im Pane)
            "time": "ganztägig" if all_day else f"{t.hour}:{t.minute:02d}",
            "title": title,
            "allday": all_day,
            "_sort": (d.isoformat(), sort_time),
        })
    out.sort(key=lambda e: e["_sort"])
    for e in out:
        e.pop("_sort", None)
    return out


async def fetch_events(session: aiohttp.ClientSession, url: str, days: int) -> list:
    """iCal-Abo laden (async) und parsen (Parsen im Thread, blockiert die Loop nicht)."""
    url = normalize_ical_url(url)
    if not url:
        return []
    if not HAVE_ICAL:
        raise RuntimeError("Bibliothek 'icalendar' nicht installiert")
    async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as r:
        r.raise_for_status()
        data = await r.read()
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _parse_events, data, days)


def _iso(s):
    """ISO-Zeitstring von Open-Meteo -> datetime (oder None)."""
    try:
        return datetime.fromisoformat(s)
    except (ValueError, TypeError):
        return None


def _hhmm(s):
    """ISO-Zeitstring -> "HH:MM" (oder None)."""
    d = _iso(s)
    return f"{d.hour:02d}:{d.minute:02d}" if d else None


async def fetch_weather(session: aiohttp.ClientSession, lat: float, lon: float, fore_days: int) -> dict:
    """Aktuelles Wetter + Tagesvorhersage von Open-Meteo (kein API-Key).

    Liefert zusaetzlich die naechsten Stunden (`hourly`: Temperaturverlauf +
    Regenwahrscheinlichkeit) fuer die ausfuehrliche Ansicht (Split-Pane); die
    Felder temp/cond/icon/hi/lo/forecast bleiben fuer den kompakten Screensaver.
    """
    fore_days = max(1, min(7, int(fore_days)))
    params = {
        "latitude": lat,
        "longitude": lon,
        "current": "temperature_2m,relative_humidity_2m,apparent_temperature,is_day,"
                   "weather_code,wind_speed_10m,wind_direction_10m,pressure_msl",
        "hourly": "temperature_2m,precipitation_probability,weather_code,apparent_temperature",
        "daily": "temperature_2m_max,temperature_2m_min,weathercode,precipitation_probability_max,"
                 "precipitation_sum,sunrise,sunset,uv_index_max",
        "timezone": "auto",
        "forecast_days": fore_days,
    }
    async with session.get(OPEN_METEO, params=params, timeout=aiohttp.ClientTimeout(total=12)) as r:
        r.raise_for_status()
        j = await r.json()

    cur = j.get("current") or {}
    daily = j.get("daily") or {}
    dates = daily.get("time") or []
    tmax = daily.get("temperature_2m_max") or []
    tmin = daily.get("temperature_2m_min") or []
    codes = daily.get("weathercode") or []
    pmax = daily.get("precipitation_probability_max") or []
    psum = daily.get("precipitation_sum") or []
    sunr = daily.get("sunrise") or []
    suns = daily.get("sunset") or []
    uvmx = daily.get("uv_index_max") or []
    today = date.today()

    forecast = []
    for i in range(len(dates)):
        try:
            dd = date.fromisoformat(dates[i])
        except (ValueError, TypeError):
            dd = None
        forecast.append({
            "day": _day_label(dd, today) if dd else "",
            "icon": wmo_icon(codes[i] if i < len(codes) else 0),
            "hi": round(tmax[i]) if i < len(tmax) and tmax[i] is not None else None,
            "lo": round(tmin[i]) if i < len(tmin) and tmin[i] is not None else None,
            "pop": int(pmax[i]) if i < len(pmax) and pmax[i] is not None else None,
        })

    # Stundenverlauf ab der aktuellen Stunde (max. 24 Werte) fuer Kurve + Regenband.
    hourly = j.get("hourly") or {}
    h_time = hourly.get("time") or []
    h_temp = hourly.get("temperature_2m") or []
    h_pop = hourly.get("precipitation_probability") or []
    h_code = hourly.get("weather_code") or []
    h_feel = hourly.get("apparent_temperature") or []
    ref = _iso(cur.get("time")) or datetime.now()
    ref = ref.replace(minute=0, second=0, microsecond=0)
    start = 0
    for i, ts in enumerate(h_time):
        d = _iso(ts)
        if d and d >= ref:
            start = i
            break
    hourly_out = []
    for i in range(start, min(start + 24, len(h_time))):
        d = _iso(h_time[i])
        hourly_out.append({
            "h": d.hour if d else None,
            "temp": round(h_temp[i]) if i < len(h_temp) and h_temp[i] is not None else None,
            "pop": int(h_pop[i]) if i < len(h_pop) and h_pop[i] is not None else None,
            "icon": wmo_icon(h_code[i]) if i < len(h_code) else "cloud",
        })
    def _r(v):
        return round(v) if isinstance(v, (int, float)) else None

    code = cur.get("weather_code", 0)
    feels = _r(cur.get("apparent_temperature"))
    if feels is None:   # Fallback aus dem Stundenwert
        feels = (round(h_feel[start]) if start < len(h_feel) and h_feel[start] is not None else None)
    return {
        "temp": cur.get("temperature_2m"),
        "cond": WMO_TEXT.get(int(code) if code is not None else 0, "—"),
        "icon": wmo_icon(code),
        "hi": forecast[0]["hi"] if forecast else None,
        "lo": forecast[0]["lo"] if forecast else None,
        "feels": feels,
        "wind": _r(cur.get("wind_speed_10m")),
        "wind_dir": cur.get("wind_direction_10m"),
        "humidity": _r(cur.get("relative_humidity_2m")),
        "pressure": _r(cur.get("pressure_msl")),
        "is_day": cur.get("is_day"),
        "sunrise": _hhmm(sunr[0]) if sunr else None,
        "sunset": _hhmm(suns[0]) if suns else None,
        "uv": _r(uvmx[0]) if uvmx else None,
        "precip_sum": (round(psum[0], 1) if psum and isinstance(psum[0], (int, float)) else None),
        "forecast": forecast,
        "hourly": hourly_out,
    }


async def load_front(session: aiohttp.ClientSession, cfg: dict) -> dict:
    """Kalender + Wetter gemaess Config laden. Ein Fehler in einem Teil laesst den
    anderen unberuehrt. Rueckgabe: {weather, events, calName, meta}."""
    cfg = cfg or {}
    name = (cfg.get("name") or "Family").strip() or "Family"
    out = {
        "weather": None,
        "events": [],
        "holidays": {},                 # ISO-Datum -> Feiertagsname (2. iCal, optional)
        "calName": name,
        "meta": {"cal_configured": False, "cal_count": 0, "cal_error": None,
                 "wx_configured": False, "wx_error": None,
                 "hol_configured": False, "hol_count": 0, "hol_error": None},
    }

    url = (cfg.get("ical_url") or "").strip()
    if url:
        out["meta"]["cal_configured"] = True
        try:
            days = int(cfg.get("days") or 14)
        except (TypeError, ValueError):
            days = 14
        try:
            out["events"] = await fetch_events(session, url, days)
            out["meta"]["cal_count"] = len(out["events"])
        except Exception as e:
            out["meta"]["cal_error"] = str(e)
            log.warning("Kalender laden fehlgeschlagen: %s", e)

    # Feiertage aus einem zweiten, optionalen iCal (ganztaegige Eintraege). Weit
    # nach vorn geladen (fuer die Monatsnavigation), Rueckgabe als {Datum: Name}.
    hol_url = (cfg.get("holiday_url") or "").strip()
    if hol_url:
        out["meta"]["hol_configured"] = True
        try:
            hev = await fetch_events(session, hol_url, 400)
            out["holidays"] = {e["date"]: e["title"] for e in hev if e.get("date")}
            out["meta"]["hol_count"] = len(out["holidays"])
        except Exception as e:
            out["meta"]["hol_error"] = str(e)
            log.warning("Feiertage laden fehlgeschlagen: %s", e)

    lat, lon = cfg.get("lat"), cfg.get("lon")
    if lat not in (None, "") and lon not in (None, ""):
        out["meta"]["wx_configured"] = True
        try:
            fore = int(cfg.get("fore_days") or 4)
        except (TypeError, ValueError):
            fore = 4
        try:
            out["weather"] = await fetch_weather(session, float(lat), float(lon), fore)
        except Exception as e:
            out["meta"]["wx_error"] = str(e)
            log.warning("Wetter laden fehlgeschlagen: %s", e)

    return out
