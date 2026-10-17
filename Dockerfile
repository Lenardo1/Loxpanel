# LoxPanel — Web-Touch-Visu fuer Loxone (Server + Frontend)
FROM python:3.12-slim

WORKDIR /app

# Abhaengigkeiten (loxone-api zieht aiohttp mit; cryptography fuer die
# Audioserver-Anmeldung). Auf 32-bit-ARM (linux/arm/v7) gibt es kein fertiges
# cffi-Paket -> Compiler + libffi/libc nur zum Bauen installieren und danach
# wieder entfernen, damit das Image schlank bleibt (amd64/arm64 nutzen Wheels).
COPY requirements.txt .
RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends gcc libc6-dev libffi-dev; \
    pip install --no-cache-dir -r requirements.txt; \
    apt-get purge -y --auto-remove gcc libc6-dev libffi-dev; \
    rm -rf /var/lib/apt/lists/*

# App-Code + Standard-Frontend/Config (Beispiele/Defaults)
COPY bin/ ./bin/
COPY webfrontend/ ./webfrontend/
COPY config/ ./config/
COPY deploy/ ./deploy/
COPY agent/ ./agent/

# Welcher Stand im Image steckt: bin/version.json fuer die Anzeige im
# Konfigurator (bin/version_info.py); die Version steht in plugin.cfg, den
# Commit reicht der Workflow herein (docker-image.yml). Ohne ihn
# (docker compose up --build; .git kommt nicht ins Image) kennzeichnet ein
# Pruefwert ueber den kopierten Code den Stand, damit offene Seiten nach einem
# Update neu laden. Darum erst nach den COPY-Zeilen oben.
ARG LOXPANEL_COMMIT=""
COPY loxberry-plugin/plugin.cfg ./loxberry-plugin/plugin.cfg
RUN python bin/version_info.py schreiben "$LOXPANEL_COMMIT"

# Laufzeit-Config (loxpanel.cfg, panels.json, theme.json) wird als Volume
# unter /app/config gemountet; Miniserver-Zugang kann auch per Env kommen.
ENV LOXPANEL_PORT=8099
EXPOSE 8099

# Zustand fuer Docker/Unraid (Docker-Tab: healthy/unhealthy). /api/health meldet
# 503, wenn eine Hintergrund-Aufgabe des Servers beendet ist. Ein nicht
# erreichbarer Miniserver macht den Container NICHT ungesund (Neustart hilft da
# nicht, der Server verbindet selbst neu). Python statt curl: slim hat kein curl.
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
  CMD ["python", "-c", "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:%s/api/health' % os.environ.get('LOXPANEL_PORT', '8099'), timeout=4)"]

CMD ["python", "bin/webvisu.py"]
