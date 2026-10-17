#!/usr/bin/env python3
"""Sonde fuer Loxone-Tree-Turbo-Geraete im eigenen Netz: Welche Geraete tauchen
auf, welche Ports oeffnen sie, und was verraten sie ohne Anmeldung?

Tree Turbo ist laut Loxone eine IP-basierte Powerline-Verbindung: die Geraete
(Stereo Extension, Install Speaker Master, Sub, Satellite ...) haengen an einer
Tree-Turbo-Schnittstelle des Audioservers bzw. Miniserver Compact und holen sich
per DHCP eine IP im normalen Heimnetz. Sie sind damit im LAN erreichbar wie jedes
andere Geraet. Diese Sonde sucht sie dort und schaut nach, was sie anbieten.

Laeuft im LoxPanel-Container, weil dort aiohttp vorhanden ist und der Server die
Adressen (Miniserver + Audioserver) aus der Struktur kennt. Solange die Datei
noch nicht im Image steckt, per Pipe:

    curl -fsSL <url dieser datei> | docker exec -i LoxPanel python3 -u - [argumente]

sonst direkt:

    docker exec -i LoxPanel python3 -u bin/treeturbo_probe.py [argumente]

Argumente (kombinierbar mit `full`):
    (ohne)          Adressen aus Panel und Struktur lesen, die zugehoerigen
                    /24-Netze absuchen, alle antwortenden Geraete mit Namen
                    auflisten und die mit offenen Loxone-Ports genauer abfragen.
    host <ip>       Nur diese eine Adresse (oder diesen Namen) abfragen.
    net <cidr>      Dieses Netz absuchen, z.B. net 192.168.1.0/24.
    full            Je abgefragtem Geraet die Ports 1-10000 statt nur der
                    bekannten pruefen (dauert je Geraet bis zu ~30 s).

Ein Geraet gilt als vorhanden, sobald es auf einen Verbindungsversuch reagiert,
auch mit Ablehnung (Port zu). So werden auch Geraete ohne offenen Loxone-Port
gefunden. Geraete, die Verbindungsversuche stumm verwerfen, bleiben unsichtbar;
deren IP zeigt der Router in seiner Geraeteliste, dann `host <ip> full`.

Es wird nur gelesen. Nichts wird veraendert, keine Anmeldung versucht. Der
Zugang zum Miniserver (fuer die Adressliste aus der Struktur) ist derselbe wie
im Server: loxpanel.cfg (Settings) vor LOXPANEL_MS_*.
"""
import asyncio
import ipaddress
import json
import os
import re
import socket
import sys
from pathlib import Path

import aiohttp

PANEL = "http://127.0.0.1:8099"
APP_DIR = Path(__file__).resolve().parent.parent if "__file__" in globals() else Path("/app")

# Ports mit bekannter Bedeutung. Belegt aus dem LoxPanel-Code: 7091 Audioserver-
# Protokoll (audioserver_events.py), 7090 REST von Sonn/Audioserver4Home und 7092
# Cover-Proxy des Audioservers (webvisu.py). Dazu die ueblichen Web-Ports.
KNOWN_PORTS = {
    80:   "HTTP",
    443:  "HTTPS",
    7090: "REST /api/v1 (Sonn/Audioserver4Home)",
    7091: "Audioserver-Protokoll (WebSocket, remotecontrol)",
    7092: "Audioserver Cover-Proxy",
    8080: "HTTP (alternativ)",
}
FULL_RANGE = range(1, 10001)   # Portbereich fuer `full`

SCAN_TIMEOUT = 0.8      # Sekunden je TCP-Verbindungsversuch
SCAN_CONCURRENCY = 300  # gleichzeitige Verbindungsversuche
DNS_TIMEOUT = 2.0       # Sekunden je Namensaufloesung

_ARGS = sys.argv[1:]
FULL = any(a.lower() == "full" for a in _ARGS)
_REST = [a for a in _ARGS if a.lower() != "full"]
MODE = _REST[0].lower() if _REST else ""
TARGET = _REST[1].strip() if len(_REST) > 1 else ""


def cut(s, n=400):
    s = str(s).replace("\n", " ").replace("\r", " ")
    return s if len(s) <= n else s[:n] + " …"


def miniserver_config() -> dict:
    """Zugang wie der Server: loxpanel.cfg (Settings) vor Umgebungsvariablen."""
    for base in (APP_DIR / "config", Path("/app/config")):
        f = base / "loxpanel.cfg"
        if f.is_file():
            try:
                ms = json.loads(f.read_text(encoding="utf-8")).get("miniserver", {})
            except ValueError:
                ms = {}
            if ms.get("host"):
                return ms
    env = os.environ
    if env.get("LOXPANEL_MS_HOST"):
        return {"host": env["LOXPANEL_MS_HOST"], "user": env.get("LOXPANEL_MS_USER", ""),
                "pass": env.get("LOXPANEL_MS_PASS", ""), "port": int(env.get("LOXPANEL_MS_PORT") or "443"),
                "verify_tls": env.get("LOXPANEL_MS_VERIFY_TLS", "false").lower() in ("1", "true", "yes")}
    return {}


async def panel_audio_hosts() -> list:
    """Audioserver-Adressen aus dem laufenden Panel (/api/settings)."""
    hosts = []
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(f"{PANEL}/api/settings", timeout=aiohttp.ClientTimeout(total=6)) as r:
                data = await r.json()
        for hp in (data.get("audiometa", {}) or {}).get("servers", []) or []:
            host = str(hp).partition(":")[0].strip()
            if host:
                hosts.append(host)
    except Exception as err:
        print(f"  Panel /api/settings nicht lesbar: {cut(err, 120)}")
    return hosts


async def structure_hosts() -> list:
    """mediaServer-Adressen aus der Miniserver-Struktur (braucht Zugang). Das
    sind die Audioserver; die Tree-Turbo-Geraete haengen im selben Subnetz."""
    for d in (str(APP_DIR / "bin"), "/app/bin"):
        if d not in sys.path:
            sys.path.insert(0, d)
    ms = miniserver_config()
    if not ms.get("host"):
        return []
    try:
        from loxone_api import LoxoneClient
    except ImportError:
        return []
    port = int(ms.get("port", 443))
    c = LoxoneClient(host=ms["host"], user=ms.get("user", ""), password=ms.get("pass", ""),
                     port=port, verify_tls=bool(ms.get("verify_tls", False)))
    if port == 80:
        c.base_url = f"http://{ms['host']}:{port}/"
    hosts = []
    try:
        async with c:
            await c.getkey2()
            await c.authenticate()
            st = await c.load_structure()
        for v in (st.get("mediaServer") or {}).values():
            h = (v or {}).get("host", "") if isinstance(v, dict) else ""
            h = str(h).partition(":")[0].strip()
            if h:
                hosts.append(h)
    except Exception as err:
        print(f"  Struktur nicht lesbar ({cut(err, 100)}) — nur Panel-Adressen")
    return hosts


async def resolve_ipv4(host: str) -> str:
    """IPv4-Adresse zu einem Namen (oder die Adresse selbst); leer, wenn nicht
    aufloesbar."""
    try:
        ip = ipaddress.ip_address(host)
        return str(ip) if ip.version == 4 else ""
    except ValueError:
        pass
    loop = asyncio.get_running_loop()
    try:
        infos = await asyncio.wait_for(loop.getaddrinfo(host, None, family=socket.AF_INET), DNS_TIMEOUT)
    except (asyncio.TimeoutError, OSError, ValueError):   # UnicodeError bei "192.168..20"
        return ""
    return infos[0][4][0] if infos else ""


async def reverse_dns(ip: str) -> str:
    """Name zur IP aus dem DNS des Routers (dort stehen meist die DHCP-Namen)."""
    loop = asyncio.get_running_loop()
    try:
        name = await asyncio.wait_for(loop.run_in_executor(None, socket.gethostbyaddr, ip), DNS_TIMEOUT)
    except (asyncio.TimeoutError, OSError):
        return ""
    return name[0] if name and name[0] != ip else ""


async def tcp_state(host: str, port: int):
    """"open" = Port offen, "closed" = Verbindung abgewiesen (Geraet da, Port zu),
    None = keine Antwort (kein Geraet oder es verwirft stumm)."""
    try:
        _reader, writer = await asyncio.wait_for(asyncio.open_connection(host, port), timeout=SCAN_TIMEOUT)
    except ConnectionRefusedError:
        return "closed"
    except (asyncio.TimeoutError, OSError):
        return None
    writer.close()
    try:
        await writer.wait_closed()
    except Exception:
        pass
    return "open"


async def sweep_host(host: str, sem: asyncio.Semaphore) -> tuple:
    """(vorhanden, offene bekannte Ports) fuer eine Adresse."""
    async def one(port):
        async with sem:
            return port, await tcp_state(host, port)
    res = await asyncio.gather(*(one(p) for p in KNOWN_PORTS))
    open_ports = sorted(p for p, st in res if st == "open")
    return any(st is not None for _, st in res), open_ports


async def scan_ports(host: str, ports, sem: asyncio.Semaphore) -> list:
    """Liste der offenen Ports aus `ports` an `host`."""
    async def one(port):
        async with sem:
            return port if await tcp_state(host, port) == "open" else None
    res = await asyncio.gather(*(one(p) for p in ports))
    return sorted(p for p in res if p is not None)


async def http_banner(host: str, port: int) -> str:
    """Status, Server-Header und <title> der Startseite, zur Geraeteerkennung."""
    scheme = "https" if port == 443 else "http"
    try:
        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False)) as s:
            async with s.get(f"{scheme}://{host}:{port}/", timeout=aiohttp.ClientTimeout(total=6)) as r:
                status = r.status
                server = r.headers.get("Server", "")
                text = await r.text(errors="replace")
    except Exception as err:
        return f"nicht abrufbar ({cut(err, 80) or type(err).__name__})"
    m = re.search(r"<title[^>]*>(.*?)</title>", text, re.I | re.S)
    title = (m.group(1).strip() if m else "")[:120]
    parts = [f"HTTP {status}"]
    if server:
        parts.append(f"Server: {server}")
    if title:
        parts.append(f"Titel: {title}")
    return " | ".join(parts)


async def audio_banner(host: str, port: int = 7091) -> str:
    """Audioserver-Protokoll: mit Unterprotokoll remotecontrol verbinden und das
    Begruessungsbanner (LWSS V ... | ~API:...~) einsammeln. Es wird kein Befehl
    gesendet, nur zugehoert. Das Session-Timeout begrenzt den Handshake (ein
    float-`timeout` an ws_connect gilt bei aiohttp nur fuers Schliessen, der
    Handshake liefe sonst bis 300 s); nach dem Upgrade setzt aiohttp das
    Lese-Timeout zurueck, das Zuhoeren begrenzt die Schleife selbst."""
    timeout = aiohttp.ClientTimeout(total=None, sock_connect=5, sock_read=8)
    try:
        async with aiohttp.ClientSession(timeout=timeout) as s:
            async with s.ws_connect(f"ws://{host}:{port}/", protocols=("remotecontrol",)) as ws:
                proto = ws.protocol or "(keins)"
                loop = asyncio.get_running_loop()
                end = loop.time() + 4
                first = ""
                while loop.time() < end:
                    try:
                        m = await asyncio.wait_for(ws.receive(), timeout=max(0.1, end - loop.time()))
                    except asyncio.TimeoutError:
                        break
                    if m.type != aiohttp.WSMsgType.TEXT:
                        break
                    if m.data.startswith("LWSS"):
                        first = m.data.strip()
                        break
                    if not first:
                        first = cut(m.data, 160)
    except Exception as err:
        return f"WebSocket nicht moeglich ({cut(err, 80) or type(err).__name__})"
    return f"WebSocket verbunden (Unterprotokoll {proto})" + \
        (f", erste Nachricht: {cut(first, 200)}" if first else ", in 4 s keine Nachricht")


async def inspect_host(host: str, sem: asyncio.Semaphore, label: str = "") -> None:
    """Ein Geraet genauer abfragen: offene Ports, HTTP-Banner, Audio-Banner."""
    ports = list(KNOWN_PORTS)
    if FULL:
        ports += [p for p in FULL_RANGE if p not in KNOWN_PORTS]
    head = f"\n===== {host}" + (f" ({label})" if label else "")
    print(f"{head}: pruefe {len(ports)} Ports ...")
    open_ports = await scan_ports(host, ports, sem)
    if not open_ports:
        print("  kein gepruefter Port offen")
        return
    for p in open_ports:
        print(f"  {p:>5} offen  {KNOWN_PORTS.get(p, 'unbekannt')}")
    for p in open_ports:
        if p in (80, 443, 8080):
            print(f"  -> :{p} {await http_banner(host, p)}")
    if 7091 in open_ports:
        print(f"  -> :7091 {await audio_banner(host, 7091)}")


async def collect_seeds() -> dict:
    """Bekannte Adressen (IPv4 -> Rolle) aus Konfiguration, Panel und Struktur."""
    print("Adressen aus Konfiguration, Panel und Miniserver-Struktur lesen ...")
    roles = {}
    ms = miniserver_config()
    named = []
    if ms.get("host"):
        named.append((str(ms["host"]).partition(":")[0].strip(), "Miniserver"))
    for h in await panel_audio_hosts() + await structure_hosts():
        named.append((h, "Audioserver"))
    for h, role in named:
        ip = await resolve_ipv4(h) if h else ""
        if not ip:
            print(f"  {h}: keine IPv4-Adresse ermittelbar")
            continue
        roles.setdefault(ip, role)
    print("  Bekannt: " + (", ".join(f"{ip} ({r})" for ip, r in roles.items()) or "nichts"))
    return roles


async def main():
    sem = asyncio.Semaphore(SCAN_CONCURRENCY)

    if MODE == "host":
        if not TARGET:
            print("Aufruf: host <ip oder name> [full]")
            return
        ip = await resolve_ipv4(TARGET)
        if not ip:
            print(f"{TARGET}: keine IPv4-Adresse ermittelbar")
            return
        name = await reverse_dns(ip)
        await inspect_host(ip, sem, label=name)
        return

    roles = {}
    if MODE == "net":
        try:
            nets = [ipaddress.ip_network(TARGET, strict=False)]
        except ValueError as err:
            print(f"Aufruf: net <cidr> [full], z.B. net 192.168.1.0/24 ({err})")
            return
    elif MODE:
        print(f"Unbekanntes Argument {MODE!r}. Moeglich: host <ip>, net <cidr>, full")
        return
    else:
        roles = await collect_seeds()
        nets = []
        for ip in roles:
            net = ipaddress.ip_network(f"{ip}/24", strict=False)
            if net not in nets:
                nets.append(net)
        if not nets:
            print("\nKeine Adresse bekannt. Laeuft das Panel, ist der Miniserver eingetragen?\n"
                  "Sonst das Netz direkt angeben: net 192.168.1.0/24")
            return

    to_inspect = []
    for net in nets:
        addrs = [str(ip) for ip in net.hosts()]
        print(f"\nSuche in {net} ({len(addrs)} Adressen) ...")
        results = await asyncio.gather(*(sweep_host(a, sem) for a in addrs))
        alive = [(a, ports) for a, (ok, ports) in zip(addrs, results) if ok]
        names = await asyncio.gather(*(reverse_dns(a) for a, _ in alive))
        print(f"  {len(alive)} Geraete antworten:")
        print(f"  {'IP':<16} {'Name':<32} {'Rolle':<12} offene bekannte Ports")
        for (a, ports), name in zip(alive, names):
            print(f"  {a:<16} {(name or '-')[:32]:<32} {roles.get(a, ''):<12} "
                  f"{', '.join(str(p) for p in ports) or '-'}")
            if ports:
                to_inspect.append((a, name or roles.get(a, "")))

    if to_inspect:
        print(f"\n{len(to_inspect)} Geraet(e) mit offenen bekannten Ports werden genauer abgefragt ...")
    for a, label in to_inspect:
        await inspect_host(a, sem, label=label)

    print("\nFertig. Die Stereo Extension ist ein Geraet ohne Rolle in der Liste oben;\n"
          "der Name (falls der Router ihn kennt) hilft beim Zuordnen, sonst die\n"
          "Geraeteliste des Routers. Fuer alle Ports dieses Geraets:  host <ip> full")


if __name__ == "__main__":
    asyncio.run(main())
