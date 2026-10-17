"""Bilder fuer die Visu: Adressen der Icons (Loxone-Icons, eigene Symbole,
Energiefluss-Knoten), Icons und Klingelbilder vom Miniserver mit Cache, Cover
ueber den Proxy und die Liste der Loxone-Icons fuer den Konfigurator.

Die Methoden sind ein Mixin (Medien): App erbt sie und arbeitet mit ihnen auf ihrem
Zustand (self ist die App). Importiert webvisu nicht."""
from __future__ import annotations

import asyncio
from urllib.parse import quote

import aiohttp

ICON_CACHE_MAX = 500     # Icons im Speicher (Loxone-SVGs, je wenige KB)

COVER_TIMEOUT = 10       # s: Albumcover vom Audioserver/aus dem Netz (sonst haengt die Anfrage offen)

BELL_CACHE_MAX = 30      # Bilder verpasster Klingeln im Speicher (JPEG, je um 100 KB)

BELL_TIMEOUT = 10        # s: ein Klingel-Bild vom Miniserver


class Medien:
    """Icons, Cover und Klingelbilder; Mixin der App (self ist die App)."""

    @staticmethod
    def _icon_url(image: str | None) -> str | None:
        if image and (image.endswith(".svg") or image.endswith(".png")):
            return f"/icon?p={quote(image)}"
        return None

    def _control_icon_url(self, c: dict) -> str | None:
        """Echtes Loxone-Icon eines Controls. Reihenfolge wie in der Loxone-App:
        control-eigenes Bild -> `defaultIcon` (hier legt Loxone das pro Control
        gewaehlte/GEAENDERTE Icon ab, auch eigene Uploads) -> Kategorie-Icon."""
        di = (c.get("details") or {}).get("image")
        if isinstance(di, str):
            img = di
        elif isinstance(di, dict):
            img = di.get("on") or di.get("off")
        else:
            img = None
        if not img:
            img = c.get("defaultIcon")      # pro-Control gewaehltes Icon (inkl. Aenderung/Upload)
        if not img:
            img = (self.cats.get(c.get("cat")) or {}).get("image")   # Kategorie als Fallback
        return self._icon_url(img)

    def _node_icon_url(self, nd: dict) -> str | None:
        """Echtes Loxone-Icon eines EFM-Knotens (Verbraucher/Quelle). Die Icons
        gibt der Miniserver pro Knoten vor; das Feld heisst je nach Firmware
        unterschiedlich, deshalb erst die von Controls bekannten Felder, dann
        notfalls irgendein Bildpfad (.svg/.png) im Knoten. `image` kann ein Pfad
        oder ein {on/off}-Objekt sein (wie bei Controls)."""
        if not isinstance(nd, dict):
            return None
        cands = [nd.get("image"), nd.get("defaultIcon"), nd.get("icon"),
                 nd.get("iconSrc")] + list(nd.values())
        for v in cands:
            if isinstance(v, dict):
                v = v.get("on") or v.get("off")
            u = self._icon_url(v) if isinstance(v, str) else None
            if u:
                return u
        return None

    def _loxone_icons(self) -> list:
        """Alle im Struktur-Baum referenzierten Loxone-Icon-Pfade (für den Picker)."""
        paths = set()
        for c in self.controls.values():
            di = (c.get("details") or {}).get("image")
            if isinstance(di, str):
                paths.add(di)
            elif isinstance(di, dict):
                for v in (di.get("on"), di.get("off")):
                    if isinstance(v, str):
                        paths.add(v)
        for table in (self.cats, self.rooms):
            for v in table.values():
                im = v.get("image")
                if isinstance(im, str):
                    paths.add(im)
        return sorted(p for p in paths if p.endswith(".svg") or p.endswith(".png"))

    async def fetch_icon(self, path: str) -> tuple[bytes, str] | None:
        if path in self.icon_cache:
            hit = self.icon_cache.pop(path)       # neu einsortieren = zuletzt benutzt
            self.icon_cache[path] = hit
            return hit
        try:
            status, body, ctype = await self._ms_http(path, 6)
        except (aiohttp.ClientError, asyncio.TimeoutError, ConnectionError):
            return None
        if status != 200:
            return None
        ctype = ctype or "application/octet-stream"
        self.icon_cache[path] = (body, ctype)
        while len(self.icon_cache) > ICON_CACHE_MAX:
            self.icon_cache.pop(next(iter(self.icon_cache)))   # am laengsten unbenutzt
        return self.icon_cache[path]

    async def fetch_bell_image(self, ua: str, ts: str) -> tuple[bytes, str] | None:
        """Bild einer verpassten Klingel vom Miniserver: laut Strukturdoku
        camimage/{uuidAction}/{Zeitstempel}, Bearer-Token wie bei den Icons.
        Zu einem Zeitstempel aendert sich das Bild nicht, darum ein kleiner
        Zwischenspeicher (zuletzt benutzte zuletzt verdraengt)."""
        pfad = f"camimage/{ua}/{ts}"
        if pfad in self.bell_cache:
            hit = self.bell_cache.pop(pfad)
            self.bell_cache[pfad] = hit
            return hit
        try:
            status, body, ctype = await self._ms_http(pfad, BELL_TIMEOUT)
        except (aiohttp.ClientError, asyncio.TimeoutError, ConnectionError):
            return None
        if status != 200 or not body:
            return None
        self.bell_cache[pfad] = (body, ctype or "image/jpeg")
        while len(self.bell_cache) > BELL_CACHE_MAX:
            self.bell_cache.pop(next(iter(self.bell_cache)))
        return self.bell_cache[pfad]

    async def fetch_cover(self, url: str) -> tuple[bytes, str] | None:
        if not self.icon_session:
            return None
        try:
            async with self.icon_session.get(url, timeout=aiohttp.ClientTimeout(total=COVER_TIMEOUT)) as r:
                if r.status != 200:
                    return None
                return (await r.read(), r.headers.get("Content-Type", "image/jpeg"))
        except (aiohttp.ClientError, asyncio.TimeoutError):
            return None
