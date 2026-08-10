#!/usr/bin/env python3
"""LoxPanel Runtime-Daemon - Geruest (Phase 1).

Bruecke Loxone <-> Panels. Aktuell nur das Grundgeruest: Config laden, MQTT
verbinden, sauberer Lebenszyklus. Die eigentliche Sync-Logik (Loxone-WebSocket,
Binding-Map, Dispatch, LMS, SIP) wird in den Folgephasen ergaenzt.

LoxBerry startet und ueberwacht dieses Skript ueber den daemon/-Mechanismus.
"""
from __future__ import annotations

import json
import logging
import os
import signal
import sys
import time
from pathlib import Path

try:
    import paho.mqtt.client as mqtt
except ImportError:  # Standalone ohne MQTT-Lib
    mqtt = None

log = logging.getLogger("loxpanel.daemon")
_running = True


def _stop(*_):  # SIGTERM/SIGINT
    global _running
    _running = False
    log.info("Stop-Signal empfangen")


def config_path() -> Path:
    lbpconfig = os.environ.get("LBPCONFIG")
    if lbpconfig:
        return Path(lbpconfig) / "loxpanel" / "loxpanel.cfg"
    return Path(__file__).resolve().parent.parent / "config" / "loxpanel.cfg.example"


def load_config() -> dict:
    path = config_path()
    if path.is_file():
        return json.loads(path.read_text(encoding="utf-8"))
    log.warning("Keine Config gefunden (%s) - nutze leere Defaults", path)
    return {}


def connect_mqtt(cfg: dict):
    if mqtt is None:
        log.warning("paho-mqtt nicht installiert - MQTT deaktiviert")
        return None
    m = cfg.get("mqtt", {})
    client = mqtt.Client(client_id="loxpanel-daemon")
    if m.get("user"):
        client.username_pw_set(m["user"], m.get("pass", ""))

    base = m.get("base_topic", "hasp")

    def on_connect(cl, _ud, _flags, rc):
        log.info("MQTT verbunden (rc=%s)", rc)
        # Panel-Events abonnieren (openHASP: hasp/<plate>/state/#)
        cl.subscribe(f"{base}/+/state/#")

    def on_message(_cl, _ud, msg):
        # TODO: Event -> Binding-Map -> Loxone-Befehl (Phase 2)
        log.debug("MQTT rx %s = %s", msg.topic, msg.payload[:120])

    client.on_connect = on_connect
    client.on_message = on_message
    try:
        client.connect(m.get("host", "127.0.0.1"), int(m.get("port", 1883)), keepalive=30)
        client.loop_start()
        return client
    except OSError as err:
        log.error("MQTT-Verbindung fehlgeschlagen: %s", err)
        return None


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)

    cfg = load_config()
    log.info("LoxPanel-Daemon startet")

    client = connect_mqtt(cfg)

    # TODO Phase 2:
    #   - Loxone-WebSocket verbinden (loxone_client.LoxoneWebSocket) -> Live-Werte
    #   - Binding-Map laden (vom Generator aus visu.json erzeugt)
    #   - Loxone-Zustand -> MQTT command an Panel-Objekt
    #   - MQTT-Event  -> Loxone-Befehl
    #   - LMS-JSON-RPC-Poll/Subscribe fuer Player-Seiten
    #   - SIP-Companion (baresip) fuer Intercom steuern

    while _running:
        time.sleep(1)

    if client is not None:
        client.loop_stop()
        client.disconnect()
    log.info("LoxPanel-Daemon beendet")
    return 0


if __name__ == "__main__":
    sys.exit(main())
