"""Intercom ausserhalb der Kachel: der SIP-Zugang (intercom_sip, fuers
Gegensprechen ueber den Server und die SIP-Pruefung), die Kamera fuer den
MJPEG-Proxy (intercom_video, eingetragen in loxpanel.cfg oder aus den
gesicherten Details des Miniservers) und die Bloecke der Kamera-Pane
(intercom_blocks). Kachel und Detailseite stehen in bausteine/intercom.py.

Die Methoden sind ein Mixin (Intercomdienst): App erbt sie und arbeitet mit ihnen
auf ihrem Zustand (self ist die App). Importiert webvisu nicht."""
from __future__ import annotations

import logging
from urllib.parse import urlsplit

from bausteine.gemeinsam import INTERCOM_TYPES
from bausteine.intercom import KEIN_VIDEO
from miniserver import KEIN_SIP, OhneGesicherteDetails, ZugangFehler

log = logging.getLogger("loxpanel.webvisu")   # derselbe Logger wie der Server: die Methoden gehoeren zu App


def _sip_zugang(details: dict) -> dict | None:
    """SIP-Zugang aus den gesicherten Details einer Intercom (audioInfo: host,
    user und bei Loxone-Intercoms pass; Strukturdoku 16.0 und 17.0, Intercom).
    -> {"host", "user", "pass"}; None, wenn kein host darin steht."""
    ai = details.get("audioInfo")
    host = str(ai.get("host") or "").strip() if isinstance(ai, dict) else ""
    if not host:
        return None
    return {"host": host, "user": str(ai.get("user") or "").strip(), "pass": str(ai.get("pass") or "")}


def _gesichert_felder(details: dict) -> dict:
    """Aufbau gesicherter Details ohne Werte: je Abschnitt die Felder und ob sie
    gefuellt sind, etwa {"videoInfo": {"streamUrl": True}, "audioInfo": {}}.
    Fuer die Diagnose im Reiter SIP; Werte und Passwoerter bleiben im Server."""
    return {k: ({f: bool(w) for f, w in v.items()} if isinstance(v, dict) else bool(v))
            for k, v in details.items()}


def _mit_miniserver(teile, host: str, port=None) -> str:
    """netloc einer streamUrl mit dem Miniserver als Host: Anmeldedaten in der
    Adresse bleiben, der Port ist der uebergebene oder der aus der Adresse."""
    auth = teile.netloc.rsplit("@", 1)[0] + "@" if "@" in teile.netloc else ""
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"               # IPv6
    p = teile.port if port is None else port
    return auth + host + (f":{p}" if p else "")


def _kamera_aus_details(details: dict, ms_host: str = "", ms_port=None) -> dict:
    """Kamera einer Intercom aus ihren gesicherten Details (videoInfo:
    streamUrl, user, pass; Strukturdoku 16.0 und 17.0, Intercom).
    -> {"url", "user", "pass"} oder {"grund"} fuer die Intercom-Seite.
    Steht statt Host oder IP ein Platzhalter in der streamUrl, ersetzt ihn
    LoxPanel wie die Loxone-App (Strukturdoku 17.0, Intercom, streamUrl):
    "cloudDNS" durch die Adresse des Miniservers (Port bleibt),
    "remoteConnect" durch Host UND Port des Miniservers mit https - der
    Miniserver leitet das Bild der Kamera weiter. Ohne Miniserver-Adresse
    (ms_host) bleibt so eine Kamera ohne Video. Eine Adresse ohne Schema (so
    wie sie in Loxone Config eingetragen wurde) wird mit http:// angesprochen."""
    vi = details.get("videoInfo")
    url = str(vi.get("streamUrl") or "").strip() if isinstance(vi, dict) else ""
    if not url:
        return {"grund": KEIN_VIDEO}
    if "://" not in url:
        url = "http://" + url
    try:
        teile = urlsplit(url)
        host = (teile.hostname or "").lower()
        teile.port                       # prueft die Port-Angabe mit
    except ValueError:                   # etwa eine kaputte IPv6-Angabe
        return {"grund": KEIN_VIDEO}
    if host in ("clouddns", "remoteconnect"):
        if not ms_host:
            return {"grund": KEIN_VIDEO}
        if host == "clouddns":
            url = teile._replace(netloc=_mit_miniserver(teile, ms_host)).geturl()
        else:
            url = teile._replace(scheme="https", netloc=_mit_miniserver(teile, ms_host, ms_port or 443)).geturl()
    return {"url": url, "user": str(vi.get("user") or "").strip(), "pass": str(vi.get("pass") or "")}


class Intercomdienst:
    """SIP-Zugang, Kamera und Kamera-Pane der Intercom; Mixin der App (self ist die App)."""

    async def intercom_sip(self, uuid: str) -> dict:
        """SIP-Zugang einer Intercom aus ihren gesicherten Details (_sip_zugang).
        -> {"host", "user", "pass"}; ZugangFehler, wenn sie keinen nennt."""
        sip = _sip_zugang(await self.secured_details(uuid))
        if sip is None:
            raise ZugangFehler(KEIN_SIP)
        return sip

    async def _talk_credentials(self, uuid: str) -> dict:
        """Nur Gen-1 (Door Controller); Gen-2 ist der eigene Typ IntercomV2."""
        if (self.controls.get(uuid) or {}).get("type") != "Intercom":
            raise ValueError("Gegensprechen unterstützt nur die Intercom Gen-1")
        try:
            return await self.intercom_sip(uuid)
        except ZugangFehler as err:
            raise ValueError(str(err)) from err

    async def intercom_video(self, uuid: str) -> dict | None:
        """Kamera einer Intercom fuer /mjpeg: {"url", "user", "pass"}. Eine in
        LoxPanel eingetragene Adresse (loxpanel.cfg intercom) hat Vorrang, sonst
        die aus den gesicherten Details des Miniservers (_kamera_aus_details),
        gemerkt in ms_video bis zur naechsten Struktur. Scheitert die Anfrage
        (Verbindung, Rechte), wird nichts gemerkt und beim naechsten Mal neu
        gefragt. None ohne nutzbare Kamera."""
        ent = self.intercom_cfg.get(uuid)
        if isinstance(ent, str):
            ent = {"url": ent}
        if isinstance(ent, dict) and isinstance(ent.get("url"), str) and ent["url"].strip():
            return {"url": ent["url"].strip(), "user": str(ent.get("user") or ""), "pass": str(ent.get("pass") or "")}
        c = self.controls.get(uuid) or {}
        if c.get("type") not in INTERCOM_TYPES or not c.get("securedDetails"):
            return None
        async with self._video_sperre:   # zwei Panels zugleich: einmal fragen
            cam = self.ms_video.get(uuid)
            if cam is None:
                try:
                    cam = _kamera_aus_details(await self.secured_details(uuid), self.host, self.port)
                except OhneGesicherteDetails:
                    cam = {"grund": KEIN_VIDEO}
                except ZugangFehler as err:
                    log.warning("Kamera der Intercom %s vom Miniserver: %s", uuid, err)
                    return None
                self.ms_video[uuid] = cam
                self._dirty = True       # Intercom-Seite neu: Bild oder Grund
        return cam if cam.get("url") else None

    def intercom_blocks(self, uuid: str):
        """Volle Intercom-Ansicht (Video + Tuer-/Ausgang-Buttons + Klingel-Banner)
        einer Intercom-UUID fuer die Kamera-Pane. Gleiche Bloecke wie die
        Detailansicht -> das Bild wird wie beim Baustein direkt geladen (robust,
        auch wo ein nacktes MJPEG-<img> nicht anzeigt). None, wenn kein Intercom.
        Was nur auf die Detailseite gehoert (Klingel-Zeile, Geraetezustand,
        Antworten und Stumm der v2), bleibt draussen."""
        c = self.controls.get(uuid or "")
        if not c or c.get("type") not in INTERCOM_TYPES:
            return None
        try:
            v = self._view_control_inner(uuid)
        except Exception:
            log.exception("intercom_blocks fehlgeschlagen (%s)", uuid)
            return None
        return [b for b in (v.get("blocks") or [])
                if b.get("k") != "more" and b.get("id") not in ("klingel", "zustand", "antworten", "stumm")]
