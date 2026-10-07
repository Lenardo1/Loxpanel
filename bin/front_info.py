"""
Front-Info: Kalender (iCal-Abo) + Wetter (Open-Meteo) fuer die Panel-Front.

Eigenstaendig, ohne Abhaengigkeit zu Fremdprojekten. Der Server ruft `load_front()`
periodisch auf und schickt das Ergebnis per WebSocket an die Panels; die Uhr-
Startseite (Screensaver) zeigt Wetter oben und die naechsten Termine unten an.

Kalender: laedt die .ics (`webcal://` -> `https://`), parst die VEVENTs, loest
Serientermine (RRULE, abzueglich abgesagter EXDATE) auf, verteilt mehrtaegige
Termine (Ferien, Urlaub) auf JEDEN ihrer Tage und liefert die naechsten Tage.
Einzeln verschobene, geaenderte oder abgesagte Termine einer Serie (eigenes
VEVENT mit RECURRENCE-ID) ersetzen ihr urspruengliches Auftreten.
Mehrere Abos (Apple, Google, Muellabfuhr, Geburtstage, ...) werden parallel
geladen und zu EINER nach Tag und Uhrzeit sortierten Liste zusammengefuehrt;
jeder Termin traegt Name und Farbe seiner Quelle mit.
Wetter: Open-Meteo (kostenlos, KEIN API-Key) per Koordinaten; `timezone=auto`
richtet sich nach dem Standort.

Alle Anzeige-Texte (Wochentage, "Heute"/"Morgen"/"ganztägig", Wetterlage) entstehen
HIER — das Panel zeigt nur an (LoxPanel-Konvention: Panel-Texte stehen im Server).
Zahlen (Temperaturen) gehen als Zahl an das Panel, das sie deutsch formatiert.
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import re
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
    from dateutil.tz import tzlocal
    HAVE_RRULE = True
except ImportError:
    HAVE_RRULE = False

WD = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]
OPEN_METEO = "https://api.open-meteo.com/v1/forecast"

# Vorschlagsfarben fuer neue Kalender. Die Einstellungsseite bietet sie an, je
# Kalender ist eine eigene Farbe waehlbar; `colors: false` in der Config zeigt
# am Panel wieder alles schlicht einfarbig. Bewusst gut unterscheidbar und auf
# dunklem WIE hellem Panel lesbar.
CAL_COLORS = ["#e0a24d", "#52b881", "#6aa9e0", "#c98ad4",
              "#e2695f", "#4fc3c3", "#b2c94a", "#9a8fe0"]

MAX_SOURCES = 8         # so viele iCal-Abos nimmt die Front entgegen
MAX_SPAN_DAYS = 400     # Schutzgrenze gegen ein kaputtes DTEND weit in der Zukunft
MAX_ICS_BYTES = 8 * 1024 * 1024   # so viel .ics nimmt der Server je Abo entgegen

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


# Pausen vor dem 2., 3. und 4. Versuch (wachsend). iClouds `pNNN-caldav`-Hosts
# sind bei bestehenden Abos teils minutenlang mit 503 zu; ein einzelner zweiter
# Versuch nach drei Sekunden faellt dann genauso hinein wie der erste.
_RETRY_PAUSEN = (3.0, 10.0, 25.0)

# Anbieter beantworten Abrufe ohne gebraeuchlichen Browser-Kopf teils mit 503 —
# iCloud ist dafuer bekannt. Der Abruf bleibt lesend und anonym; der Kopf sagt
# nur, womit gelesen wird und welches Format erwartet wird.
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/calendar, text/plain;q=0.9, */*;q=0.8",
    "Accept-Language": "de,en;q=0.8",
}


def _vorruebergehend(e: Exception) -> bool:
    """Ist der Fehler ein Aussetzer, den ein zweiter Versuch beheben kann?

    Ja bei Zeitueberschreitung, abgerissener Verbindung und den 5xx-Antworten
    des Servers (iCloud liefert bei bestehenden Abos immer wieder 503).
    Nein bei 4xx: 401/403/404 heisst falsche URL oder nicht mehr oeffentlich
    geteilt, das wird durch Wiederholen nicht besser.
    """
    if isinstance(e, (asyncio.TimeoutError, aiohttp.ClientConnectionError,
                      aiohttp.ClientPayloadError)):
        return True          # abgerissene Antwort ist auch nur ein Aussetzer
    status = getattr(e, "status", None)
    # 429 = gedrosselt, 408 = der Server selbst meldet Zeitueberschreitung:
    # beides geht nach einer Pause oft durch, anders als die uebrigen 4xx.
    return isinstance(status, int) and (status >= 500 or status in (408, 429))


def _retry_after(e: Exception) -> float | None:
    """Wartezeit in Sekunden, um die der Server per `Retry-After` bittet.

    None, wenn er keine nennt. Die Datumsform des Kopfes zaehlt als unendlich:
    sie steht fuer "spaeter", und fuer die Entscheidung in fetch_events()
    genuegt, dass sie praktisch immer laenger ist als die eigenen Pausen.
    """
    wert = (getattr(e, "headers", None) or {}).get("Retry-After")
    if wert is None:
        return None
    try:
        return max(0.0, float(str(wert).strip()))
    except ValueError:
        return float("inf")


def normalize_ical_url(url) -> str:
    """`webcal://` / `webcals://` -> `https://` (Apple/iCloud teilt webcal-Links)."""
    url = (url or "").strip()
    if url.startswith("webcal://"):
        return "https://" + url[len("webcal://"):]
    if url.startswith("webcals://"):
        return "https://" + url[len("webcals://"):]
    return url


def source_key(url) -> str:
    """Kurzer, stabiler Schluessel einer Quelle.

    Gehasht, damit die (oft private) Abo-URL nicht bis aufs Panel durchgereicht
    wird — der Server erkennt seine Quellen trotzdem wieder und kann den letzten
    guten Stand je Quelle halten.
    """
    return hashlib.sha1(normalize_ical_url(url).encode("utf-8")).hexdigest()[:8]


def clean_color(v, fallback: str) -> str:
    """Nur echte #rrggbb-Farben durchlassen.

    Hier und nicht erst beim Speichern: in die Config kann auch von Hand etwas
    eingetragen werden, und die Farbe landet unveraendert im style-Attribut des
    Panels. Was hier rausgeht, ist garantiert eine Farbe.
    """
    v = str(v or "").strip()
    return v if re.fullmatch(r"#[0-9a-fA-F]{6}", v) else fallback


def calendar_sources(cfg: dict) -> list:
    """Config -> Liste der Kalenderquellen [{key, name, url, color}].

    Neue Configs fuehren `sources` als Liste. Aeltere kennen nur die eine
    `ical_url` samt `name` — die wird als erste Quelle mitgelesen, damit ein
    Update nichts umzukonfigurieren verlangt.
    """
    cfg = cfg or {}
    out, gesehen = [], set()

    def _add(name, url, color):
        url = normalize_ical_url(url)
        if not url or url in gesehen or len(out) >= MAX_SOURCES:
            return
        gesehen.add(url)
        name = (str(name or "").strip() or f"Kalender {len(out) + 1}")[:40]
        color = clean_color(color, CAL_COLORS[len(out) % len(CAL_COLORS)])
        out.append({"key": source_key(url), "name": name, "url": url, "color": color})

    roh = cfg.get("sources")
    if isinstance(roh, list):
        for q in roh:
            if isinstance(q, dict):
                _add(q.get("name"), q.get("url"), q.get("color"))
            elif isinstance(q, str):
                _add("", q, "")
    if not out:                       # alte Config: die einzelne ical_url
        _add(cfg.get("name"), cfg.get("ical_url"), CAL_COLORS[0])
    return out


def event_sort_key(e: dict) -> tuple:
    """Sortierschluessel eines Termins: Tag, Uhrzeit, Titel, Quelle.

    Aus den ANZEIGEFELDERN rekonstruiert, damit auch der Server die Termine
    mehrerer Quellen in dieselbe Reihenfolge bringen kann, ohne ein
    Extra-Sortierfeld bis aufs Panel mitzuschleppen. Titel und Quelle als
    Tiebreaker: sonst wackelt die Reihenfolge zwischen zwei Abrufen und die
    Panels bekommen bei jedem Durchlauf ein sinnloses Update.
    """
    t = "00:00"
    if not e.get("allday"):
        h, sep, m = str(e.get("time") or "").partition(":")
        if sep and h.strip().isdigit() and m.strip().isdigit():
            t = f"{int(h):02d}:{int(m):02d}"
    return (str(e.get("date") or ""), t, str(e.get("title") or ""), str(e.get("ck") or ""))


def _int(v, default: int, lo: int, hi: int) -> int:
    """Ganzzahl aus der Config, auf den erlaubten Bereich begrenzt."""
    try:
        return max(lo, min(hi, int(v)))
    except (TypeError, ValueError):
        return default


def day_label(d: date, today: date) -> str:
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


def _event_span(component, dtstart, all_day: bool) -> int:
    """Wie viele Tage belegt der Termin? (1 = eintaegig)

    iCal fuehrt das Ende als DTEND (EXKLUSIV) oder als DURATION. Ferien, Urlaub
    und Messen stehen so als EIN Termin ueber viele Tage im Kalender und
    gehoeren an jedem ihrer Tage aufs Panel, nicht nur am ersten. Beispiel:
    Ferien vom 1.7. bis 10.9. stehen im ICS als DTEND;VALUE=DATE:20250911.
    """
    ende = None
    prop = component.get("dtend")
    if prop is not None:
        ende = getattr(prop, "dt", None)
    else:
        prop = component.get("duration")
        if prop is not None:
            try:
                ende = dtstart + prop.dt
            except (TypeError, AttributeError):
                ende = None
    if ende is None:
        return 1
    try:
        if all_day:
            tage = (ende - dtstart).days                 # beides `date`, DTEND exklusiv
        elif not isinstance(ende, datetime):
            tage = (ende - dtstart.date()).days          # Datum als Ende: ebenfalls exklusiv
        elif (ende.tzinfo is None) != (dtstart.tzinfo is None):
            return 1                                     # gemischt naiv/aware: nicht vergleichbar
        elif ende <= dtstart:
            return 1
        else:
            # Letzter belegter Tag: endet der Termin genau um Mitternacht,
            # zaehlt dieser Tag nicht mehr mit.
            letzter = ende - timedelta(microseconds=1)
            tage = (letzter.date() - dtstart.date()).days + 1
    except (TypeError, ValueError, OverflowError):
        return 1
    return max(1, min(MAX_SPAN_DAYS, tage))


def _exdates(component) -> tuple:
    """Abgesagte Termine einer Serie (EXDATE) als (Zeitpunkte, Tage).

    Termine mit Uhrzeit werden ZEITGENAU verglichen: eine Serie kann mehrmals
    am selben Tag auftreten (alle zwoelf Stunden, morgens und abends), und eine
    einzelne Absage darf die uebrigen nicht mitreissen. Ganztaegige EXDATE
    haben keine Uhrzeit und gelten weiter fuer den ganzen Tag.
    """
    roh = component.get("exdate")
    if not roh:
        return set(), set()
    zeiten, tage = set(), set()
    for p in (roh if isinstance(roh, list) else [roh]):
        for d in getattr(p, "dts", []):
            v = getattr(d, "dt", None)
            if isinstance(v, datetime):
                zeiten.add(_local_naive(v))
            elif isinstance(v, date):
                tage.add(v)
    return zeiten, tage


def _occurrences(component, range_start: date, range_end: date,
                 extra_ex: set | None = None):
    """Auftreten eines VEVENT im Zeitraum (loest RRULE-Serien auf).

    Liefert Tupel (Zeitpunkt, all_day, dauer_tage): bei Ganztagsterminen ein
    `date`, sonst ein naives `datetime` in ORTSZEIT (die Wanduhrzeit, die das
    Panel anzeigt). Ein mehrtaegiger Termin, der VOR dem Zeitraum begonnen hat
    und noch laeuft, kommt mit — sonst fehlen laufende Ferien ab Tag zwei.
    `extra_ex` sind zusaetzlich auszulassende Zeitpunkte: abgesagte oder
    einzeln geaenderte Termine der Serie (s. _cancelled_single()).
    """
    dtstart_prop = component.get("dtstart")
    if not dtstart_prop:
        return
    dtstart = dtstart_prop.dt
    all_day = not isinstance(dtstart, datetime)
    dauer = _event_span(component, dtstart, all_day)
    rrule = component.get("rrule")
    if rrule and _recurrence_id(component) is not None:
        # Eine Ausnahme ersetzt genau EIN Auftreten. RANGE=THISANDFUTURE (eine
        # eigene RRULE an der Ausnahme) wird bewusst nicht aufgeloest, sonst
        # stuende die Serie ab dort doppelt da: einmal alt, einmal neu.
        rrule = None
    rrule_txt = rrule.to_ical().decode() if rrule else ""

    if all_day:
        base = datetime.combine(dtstart, time.min)
    else:
        # Aware bleibt aware: dateutil loest die Serie dann in der Original-
        # Zeitzone auf, also ueber Sommer-/Winterzeit hinweg korrekt.
        base = dtstart
        # Google-Feeds schreiben oft DTSTART ohne Zeitzone, das UNTIL der RRULE
        # aber mit 'Z'. dateutil verweigert diese Mischung mit einem ValueError,
        # und ohne das hier fiele die GANZE Serie aus. Den Start als Ortszeit
        # kennzeichnen bringt beide Seiten in dieselbe Welt. tzlocal() statt
        # astimezone(): das setzte einen FESTEN Versatz (+02:00 im Sommer), und
        # nach der Zeitumstellung stand jedes Auftreten eine Stunde daneben.
        if HAVE_RRULE and base.tzinfo is None and re.search(r"UNTIL=[^;]*Z", rrule_txt, re.I):
            base = base.replace(tzinfo=tzlocal())

    # Um die Dauer nach hinten erweitert suchen: ein am 1.7. begonnener
    # Ferientermin muss am 21.9. noch gefunden werden.
    such_start = range_start - timedelta(days=dauer - 1)
    range_start_dt = datetime.combine(such_start, time.min)
    range_end_dt = datetime.combine(range_end, time.max)
    if base.tzinfo is not None:
        # Grenzen sind naive Ortszeit -> in dieselbe (aware) Welt heben, sonst
        # vergleicht dateutil aware mit naiv und wirft TypeError.
        range_start_dt = range_start_dt.astimezone()
        range_end_dt = range_end_dt.astimezone()
    ex_zeiten, ex_tage = _exdates(component)
    if extra_ex:
        ex_zeiten = ex_zeiten | {v for v in extra_ex if isinstance(v, datetime)}
        ex_tage = ex_tage | {v for v in extra_ex
                             if isinstance(v, date) and not isinstance(v, datetime)}

    def _faellt_aus(lokal: datetime) -> bool:
        return lokal in ex_zeiten or lokal.date() in ex_tage

    if rrule and HAVE_RRULE:
        try:
            rule = rrulestr(rrule_txt, dtstart=base)
            for occ in rule.between(range_start_dt, range_end_dt, inc=True):
                occ_local = _local_naive(occ)
                if _faellt_aus(occ_local):
                    continue
                yield (occ_local.date() if all_day else occ_local, all_day, dauer)
        except Exception as e:                       # kaputte RRULE nicht fatal
            log.warning("RRULE nicht lesbar: %s", e)
    elif not rrule:
        if all_day:
            d = dtstart if not isinstance(dtstart, datetime) else dtstart.date()
            if such_start <= d <= range_end and not _faellt_aus(datetime.combine(d, time.min)):
                yield (d, True, dauer)
        else:
            lokal = _local_naive(base)
            if range_start_dt <= base <= range_end_dt and not _faellt_aus(lokal):
                yield (lokal, False, dauer)


def _recurrence_id(component):
    """RECURRENCE-ID eines VEVENT, vergleichbar mit den Auftreten der Serie.

    Zeitpunkte wie in _occurrences() als naive ORTSZEIT (eine RECURRENCE-ID in
    UTC trifft so dasselbe Auftreten wie eine mit TZID), ganztaegige als `date`.
    None, wenn keine da ist oder der Feed sie kaputt liefert (mehrere Zeilen
    ergeben eine Liste ohne `dt`, einen unlesbaren Wert verwirft icalendar,
    ein Wert am Rand des Kalenders laesst sich nicht in Ortszeit umrechnen):
    Der Termin gilt dann wie bisher als eigenstaendig, statt die ganze Quelle
    abzuwerfen.
    """
    v = getattr(component.get("recurrence-id"), "dt", None)
    if isinstance(v, datetime):
        try:
            return _local_naive(v)
        except (OverflowError, ValueError, OSError):    # z. B. 99991231T235959Z
            return None
    return v if isinstance(v, date) else None


def _cancelled_single(cal) -> dict:
    """Abgesagte oder geaenderte EINZELtermine einer Serie: {UID -> Zeitpunkte}.

    Google und Apple sagen einen einzelnen Serientermin nicht per EXDATE ab,
    sondern schicken ein ZUSAETZLICHES VEVENT mit derselben UID, einer
    RECURRENCE-ID auf den betroffenen Termin und STATUS:CANCELLED. Dieses
    VEVENT zu ueberspringen genuegt nicht — die Serie erzeugt das Auftreten ja
    trotzdem. Also erst einsammeln, dann beim Aufloesen der Serie ausschliessen.
    Ein verschobener oder umbenannter Einzeltermin kommt genauso, nur ohne
    STATUS:CANCELLED; er steht dann mit seinen neuen Daten statt des Originals.
    """
    raus: dict = {}
    for comp in cal.walk():
        if comp.name != "VEVENT":
            continue
        uid = str(comp.get("uid", ""))
        v = _recurrence_id(comp)
        # Ohne UID gehoert die Ausnahme zu keiner Serie; sonst traefe sie eine
        # fremde Serie, die ebenfalls keine UID hat.
        if not uid or v is None:
            continue
        raus.setdefault(uid, set()).add(v)
    return raus


def _parse_events(ics_bytes: bytes, days: int, quelle: dict | None = None) -> list:
    """ICS-Bytes -> sortierte, anzeigefertige Terminliste fuer die naechsten `days`.

    Mehrtaegige Termine erscheinen an JEDEM ihrer Tage — Ferien stehen sonst nur
    am ersten Tag da, und ab Tag zwei sieht das Panel aus, als waere nichts.
    `note` sagt dazu, wie lange der Termin noch laeuft. `quelle` haengt Name,
    Farbe und Schluessel des Kalenders an jeden Termin, damit das Panel mehrere
    Abos auseinanderhalten kann.
    """
    cal = Calendar.from_ical(ics_bytes)
    today = date.today()
    range_end = today + timedelta(days=max(1, int(days)) - 1)
    q = quelle or {}
    q_name, q_color, q_key = q.get("name") or "", q.get("color") or "", q.get("key") or ""
    abgesagt_einzeln = _cancelled_single(cal)

    raw = []
    for comp in cal.walk():
        if comp.name != "VEVENT":
            continue
        # Abgesagte Termine gehoeren nicht aufs Panel — Google und Apple lassen
        # sie mit STATUS:CANCELLED im Feed stehen.
        if str(comp.get("status", "")).strip().upper() == "CANCELLED":
            continue
        title = str(comp.get("summary", "Termin")).strip() or "Termin"
        uid = str(comp.get("uid", ""))
        # Eine Ausnahme steht mit ihrem eigenen DTSTART da und darf sich nicht
        # ueber ihre RECURRENCE-ID selbst ausschliessen (gleiche Uhrzeit, nur
        # der Titel geaendert).
        rid = _recurrence_id(comp)
        rid_txt = "" if rid is None else rid.isoformat()
        ex = None if rid is not None else abgesagt_einzeln.get(uid)
        for occ, all_day, dauer in _occurrences(comp, today, range_end, ex):
            erster = occ if not isinstance(occ, datetime) else occ.date()
            letzter = erster + timedelta(days=dauer - 1)
            for n in range(dauer):
                d = erster + timedelta(days=n)
                if not (today <= d <= range_end):
                    continue
                # Tag 1 traegt die Uhrzeit, Folgetage laufen ganztaegig weiter.
                t = None if (all_day or n > 0) else occ.time()
                if dauer > 1:
                    note = ("letzter Tag" if d == letzter
                            else f"bis {WD[letzter.weekday()]} {letzter.day}.{letzter.month}.")
                else:
                    note = ""
                # Schluessel MIT Uhrzeit: eine Serie kann mehrmals am selben
                # Tag auftreten (alle 12 Stunden, zweimal taeglich ...). Nur
                # nach Tag entdoppelt faellt jedes weitere Auftreten weg. Die
                # RECURRENCE-ID gehoert dazu: Eine Ausnahme, die auf die Zeit
                # eines anderen Auftretens verlegt wurde, steht neben diesem.
                schl = f"{q_key}_{uid}_{rid_txt}_{d.isoformat()}_{'' if t is None else t.isoformat()}"
                raw.append((schl, d, t, title, note))

    seen = set()
    out = []
    for key, d, t, title, note in raw:
        if key in seen:
            continue
        seen.add(key)
        out.append({
            "day": day_label(d, today),
            "date": d.isoformat(),          # ISO-Datum (fuer das Monatsraster im Pane)
            "time": "ganztägig" if t is None else f"{t.hour}:{t.minute:02d}",
            "title": title,
            "note": note,                   # "bis Mi 10.9." / "letzter Tag" bei mehrtaegigen
            "allday": t is None,
            "cal": q_name,                  # Name der Quelle (Tag am Termin + Legende)
            "color": q_color,               # Farbe der Quelle
            "ck": q_key,                    # Schluessel der Quelle (Server: Stand je Quelle)
        })
    out.sort(key=event_sort_key)
    return out


_URL_RE = re.compile(r"(https?://[^/\s'\"]+)(/[^\s'\"]*)?")


def error_text(e) -> str:
    """Fehler lesbar machen — ohne den Pfad der (privaten) Abo-URL.

    aiohttp haengt die volle URL an seine Meldungen. Die stuende sonst im
    Klartext auf der Einstellungsseite und damit in jedem Screenshot davon,
    obwohl ein Abo-Link ohne weiteres Login den ganzen Kalender preisgibt.
    Der Host bleibt stehen — er sagt, WER gerade nicht antwortet.
    """
    txt = (str(e) or e.__class__.__name__).strip()
    return _URL_RE.sub(lambda m: m.group(1) + ("/…" if m.group(2) else ""), txt)


async def fetch_events(session: aiohttp.ClientSession, url: str, days: int,
                       quelle: dict | None = None) -> list:
    """iCal-Abo laden (async) und parsen (Parsen im Thread, blockiert die Loop nicht).

    Mehrere Versuche mit wachsender Pause bei VORUEBERGEHENDEN Fehlern: iClouds
    `pNNN-caldav`-Hosts antworten regelmaessig mit 503, obwohl das Abo in Ordnung
    ist, und sind das teils ein paar Minuten am Stueck. Ein 404 oder 401
    wiederholt sich dagegen nicht — dann ist die URL falsch oder das Abo nicht
    mehr oeffentlich, und weitere Abrufe kosten nur Zeit.

    Nennt der Server per `Retry-After` selbst eine Wartezeit, die laenger ist
    als die naechste eigene Pause, bleibt es bei diesem Versuch. iCloud
    antwortet einem Abrufer, der zu oft kommt, mit 503 und Retry-After 60;
    wer nach 3 s wiederkommt, haelt die Sperre nur aufrecht.
    """
    url = normalize_ical_url(url)
    if not url:
        return []
    if not HAVE_ICAL:
        raise RuntimeError("Bibliothek 'icalendar' nicht installiert")
    name = (quelle or {}).get("name") or "Kalender"
    data = None
    versuche = len(_RETRY_PAUSEN) + 1
    for nr in range(versuche):
        try:
            async with session.get(url, headers=_HEADERS,
                                   timeout=aiohttp.ClientTimeout(total=15)) as r:
                r.raise_for_status()
                # Begrenzt lesen: ein Panel-Server hat wenig Speicher, und was
                # ein fremder Host schickt, bestimmt nicht er allein. In Stuecken
                # bis zum Ende, denn read(n) gibt nur zurueck, was GERADE im
                # Puffer liegt - nicht die ersten n Bytes des Abos. Ein Kalender,
                # der nicht in einem Rutsch ankommt, kaeme damit abgeschnitten an
                # und liesse sich nicht mehr parsen.
                teile, gelesen = [], 0
                async for stueck in r.content.iter_chunked(64 * 1024):
                    gelesen += len(stueck)
                    if gelesen > MAX_ICS_BYTES:
                        raise RuntimeError(
                            f"Kalender ist groesser als {MAX_ICS_BYTES // (1024 * 1024)} MB")
                    teile.append(stueck)
                data = b"".join(teile)
            break
        except Exception as e:
            if nr == versuche - 1 or not _vorruebergehend(e):
                raise
            pause = _RETRY_PAUSEN[nr]
            bitte = _retry_after(e)
            if bitte is not None and bitte > pause:
                log.info("Kalender '%s': %s — Server bittet um %s, kein weiterer "
                         "Versuch in diesem Durchgang", name, error_text(e),
                         "eine laengere Pause" if bitte == float("inf") else f"{bitte:.0f} s Pause")
                raise
            log.info("Kalender '%s': %s — Versuch %d von %d in %.0f s",
                     name, error_text(e), nr + 2, versuche, pause)
            await asyncio.sleep(pause)
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _parse_events, data, days, quelle)


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
            "day": day_label(dd, today) if dd else "",
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
        "wind_unit": "km/h",        # Open-Meteo liefert km/h; das Panel schreibt die Einheit mit
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


async def load_front(session: aiohttp.ClientSession, cfg: dict,
                     skip_weather: bool = False) -> dict:
    """Kalender + Wetter gemaess Config laden. Ein Fehler in einem Teil laesst die
    anderen unberuehrt. Rueckgabe: {weather, events, holidays, calName, cals,
    colors, meta}.

    Alle Kalender werden PARALLEL geladen — acht Abos nacheinander abzufragen
    wuerde die Front bei einem lahmen Anbieter minutenlang blockieren. Faellt
    eine Quelle aus, liefern die anderen trotzdem; `meta.cal_sources` sagt je
    Quelle, was sie beigetragen hat oder woran sie gescheitert ist.

    `skip_weather` laesst Open-Meteo aus — der Aufrufer hat schon Wetter vom
    Loxone-Wetterserver und braucht die zweite Quelle nicht."""
    cfg = cfg or {}
    name = (cfg.get("name") or "Family").strip() or "Family"
    quellen = calendar_sources(cfg)
    out = {
        "weather": None,
        "events": [],
        "holidays": {},                 # ISO-Datum -> Feiertagsname (2. iCal, optional)
        "calName": name,
        # Legende fuer das Panel: Name + Farbe je Quelle (ohne die Abo-URL).
        "cals": [{"key": q["key"], "name": q["name"], "color": q["color"]} for q in quellen],
        "colors": bool(cfg.get("colors", True)),    # false = schlicht, ohne Kalenderfarben
        "sv_events": _int(cfg.get("sv_events"), 3, 1, 10),   # Termine auf der Uhr-Seite
        "meta": {"cal_configured": False, "cal_count": 0, "cal_error": None,
                 "cal_sources": [],
                 "wx_configured": False, "wx_error": None,
                 "hol_configured": False, "hol_count": 0, "hol_error": None},
    }

    # Feiertage gehoeren MIT in den einen parallelen Abruf. Haengen sie hinten
    # dran, addiert sich ihre Wartezeit auf die der Quellen — mit der Retry-Kette
    # sind das im schlimmsten Fall zwei volle Runden hintereinander.
    hol_url = (cfg.get("holiday_url") or "").strip()
    days = _int(cfg.get("days"), 14, 1, 60)   # auch aus der Datei begrenzen
    aufgaben = [fetch_events(session, q["url"], days, q) for q in quellen]
    if hol_url:
        out["meta"]["hol_configured"] = True
        aufgaben.append(fetch_events(session, hol_url, 400, {"name": "Feiertage"}))
    ergebnisse = list(await asyncio.gather(*aufgaben, return_exceptions=True)) if aufgaben else []

    if quellen:
        out["meta"]["cal_configured"] = True
        alle, status, fehler = [], [], []
        for q, r in zip(quellen, ergebnisse[:len(quellen)]):
            eintrag = {"key": q["key"], "name": q["name"], "color": q["color"],
                       "count": 0, "error": None}
            if isinstance(r, BaseException):
                eintrag["error"] = error_text(r)
                fehler.append(f"{q['name']}: {eintrag['error']}")
                log.warning("Kalender '%s' laden fehlgeschlagen: %s", q["name"], eintrag["error"])
            else:
                alle.extend(r)
                eintrag["count"] = len(r)
            status.append(eintrag)
        alle.sort(key=event_sort_key)   # Quellen einzeln sortiert -> gemeinsam neu ordnen
        out["events"] = alle
        out["meta"]["cal_sources"] = status
        out["meta"]["cal_count"] = len(alle)
        out["meta"]["cal_error"] = " · ".join(fehler) if fehler else None

    # Feiertage aus einem zweiten, optionalen iCal (ganztaegige Eintraege). Weit
    # nach vorn geladen (fuer die Monatsnavigation), Rueckgabe als {Datum: Name}.
    if hol_url:
        hev = ergebnisse[-1]
        if isinstance(hev, BaseException):
            out["meta"]["hol_error"] = error_text(hev)
            log.warning("Feiertage laden fehlgeschlagen: %s", out["meta"]["hol_error"])
        else:
            out["holidays"] = {e["date"]: e["title"] for e in hev if e.get("date")}
            out["meta"]["hol_count"] = len(out["holidays"])

    lat, lon = cfg.get("lat"), cfg.get("lon")
    if not skip_weather and lat not in (None, "") and lon not in (None, ""):
        out["meta"]["wx_configured"] = True
        try:
            fore = int(cfg.get("fore_days") or 4)
        except (TypeError, ValueError):
            fore = 4
        try:
            out["weather"] = await fetch_weather(session, float(lat), float(lon), fore)
        except Exception as e:
            out["meta"]["wx_error"] = error_text(e)
            log.warning("Wetter laden fehlgeschlagen: %s", out["meta"]["wx_error"])

    return out
