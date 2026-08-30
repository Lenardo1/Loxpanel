#!/bin/bash
# Laeuft als ROOT VOR der Installation.
# Args: <TEMPFOLDER> <NAME> <FOLDER> <VERSION> <BASEFOLDER>
ARGV3=$3   # Plugin-Ordnername
ARGV5=$5   # LoxBerry-Basisordner

# Docker-Repo vorbereiten, falls Docker noch fehlt (Installation der Pakete aus
# dpkg/apt erledigt LoxBerry danach selbst; erst nach dem Reboot verfuegbar).
if ! which docker > /dev/null 2>&1; then
	echo "<INFO> Bereite Docker-Installation vor (offizielles Docker-Repo)..."
	install -m 0755 -d /etc/apt/keyrings
	curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc
	chmod a+r /etc/apt/keyrings/docker.asc
	echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/debian $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
		| tee /etc/apt/sources.list.d/docker.list > /dev/null
	echo "<OK> Docker-Repo hinzugefuegt."
else
	echo "<OK> Docker ist bereits installiert."
fi

# Laufenden Container vor dem (Neu-)Installieren stoppen (belegt sonst Port 8099).
CONFIGDIR="$ARGV5/config/plugins/$ARGV3"
if [ -f "$CONFIGDIR/docker-compose.yml" ]; then
	echo "<INFO> Stoppe laufendes LoxPanel..."
	sudo docker compose -f "$CONFIGDIR/docker-compose.yml" down 2>/dev/null
fi
sudo docker rm -f loxpanel > /dev/null 2>&1

# Panel-Konfiguration (panels.json/theme.json/loxpanel.cfg) VOR dem Update
# sichern – als root, damit die root-eigenen Volume-Dateien lesbar sind.
# LoxBerry entfernt gleich danach den Datenordner; postroot.sh spielt die
# Konfiguration nach der Installation wieder zurueck.
LPBK="/tmp/loxpanel-upgrade-backup"
CFGDATA="$ARGV5/data/plugins/$ARGV3/config"
if [ -d "$CFGDATA" ] && [ -n "$(ls -A "$CFGDATA" 2>/dev/null)" ]; then
	rm -rf "$LPBK"; mkdir -p "$LPBK"
	if cp -a "$CFGDATA/." "$LPBK/" 2>/dev/null; then
		echo "<INFO> Panel-Konfiguration gesichert (Update-sicher)."
	fi
fi

# Besitzrechte der Daten-/Config-Ordner auf loxberry setzen.
chown -R loxberry:loxberry "$ARGV5/data/plugins/$ARGV3/" 2>/dev/null
chown -R loxberry:loxberry "$ARGV5/config/plugins/$ARGV3/" 2>/dev/null

exit 0
