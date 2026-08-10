# LoxPanel — Web-Touch-Visu fuer Loxone (Server + Frontend)
FROM python:3.12-slim

WORKDIR /app

# Abhaengigkeiten (loxone-api zieht aiohttp mit)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# App-Code + Standard-Frontend/Config (Beispiele/Defaults)
COPY bin/ ./bin/
COPY webfrontend/ ./webfrontend/
COPY config/ ./config/

# Laufzeit-Config (loxpanel.cfg, panels.json, theme.json) wird als Volume
# unter /app/config gemountet; Miniserver-Zugang kann auch per Env kommen.
ENV LOXPANEL_PORT=8099
EXPOSE 8099

CMD ["python", "bin/webvisu.py"]
