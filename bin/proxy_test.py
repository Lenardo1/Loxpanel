#!/usr/bin/env python3
"""Testet den MJPEG-Proxy des Servers."""
import requests

URL = "http://localhost:8099/mjpeg?id=9a8b4d56-cf47-11e1-a39daba260ecd863"
try:
    r = requests.get(URL, stream=True, timeout=8)
    first = next(r.iter_content(200), b"")
    print("Proxy:", r.status_code, r.headers.get("Content-Type"), "| first=", first[:24])
    r.close()
except Exception as e:
    print("Proxy-Fehler:", e)
