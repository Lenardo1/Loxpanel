#!/bin/bash
# Laeuft als ROOT VOR der Installation.
# Args: <TEMPFOLDER> <NAME> <FOLDER> <VERSION> <BASEFOLDER>
ARGV3=$3   # Plugin-Ordnername
ARGV5=$5   # LoxBerry-Basisordner
# Zwischenablage ueber das Update (postroot.sh liest dieselben Pfade).
# LOXPANEL_UPGRADE_TMP ersetzt /tmp nur zum Testen ausserhalb eines LoxBerry.
LPTMP="${LOXPANEL_UPGRADE_TMP:-/tmp}"
LPBK="$LPTMP/loxpanel-upgrade-backup"      # config/
LPARCH="$LPTMP/loxpanel-upgrade-archive"   # backups/ (Archive aus dem Widget)
DATADIR="$ARGV5/data/plugins/$ARGV3"
RC=0

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

# Archive aus dem Widget (backups/) ueber das Update retten - LoxBerry loescht
# gleich den ganzen Datenordner. Steht VOR dem Stoppen: die Archive aendern sich
# nicht, und scheitert die Kopie, laeuft das Panel weiter. Dann nur warnen
# (exit 1 am Ende, LoxBerry meldet es) und weiter: ein Abbruch (exit 2) liesse
# die neue Version in der Plugin-Datenbank und die alten Dateien zurueck.
# Fehlt config/, ist ein frueheres Update nach dem Loeschen abgebrochen: dann
# bleibt dessen Kopie stehen, postroot.sh spielt sie zurueck.
BKDATA="$DATADIR/backups"
if [ -d "$BKDATA" ] && [ -n "$(ls -A "$BKDATA" 2>/dev/null)" ]; then
	rm -rf "$LPARCH"; mkdir -p "$LPARCH"
	if cp -a "$BKDATA/." "$LPARCH/"; then
		echo "<INFO> Sicherungen (Archive) gesichert (Update-sicher)."
	else
		rm -rf "$LPARCH"
		echo "<WARNING> Sicherungen (Archive in $BKDATA) ließen sich nicht mitnehmen – sie fehlen nach dem Update. Die Panel-Konfiguration bleibt erhalten."
		RC=1
	fi
elif [ -d "$DATADIR/config" ]; then
	rm -rf "$LPARCH"     # keine Archive mehr: alte Kopie darf nicht wieder auftauchen
elif [ -d "$LPARCH" ]; then
	echo "<INFO> Sicherungen aus einem abgebrochenen Update gefunden, werden zurückgespielt."
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
# Konfiguration nach der Installation wieder zurueck. Ohne Kopie ginge sie
# verloren -> abbrechen (exit 2), solange LoxBerry noch nichts geloescht hat,
# und keine halben Zwischenkopien liegen lassen.
CFGDATA="$DATADIR/config"
if [ -d "$CFGDATA" ] && [ -n "$(ls -A "$CFGDATA" 2>/dev/null)" ]; then
	rm -rf "$LPBK"; mkdir -p "$LPBK"
	if cp -a "$CFGDATA/." "$LPBK/"; then
		echo "<INFO> Panel-Konfiguration gesichert (Update-sicher)."
	else
		rm -rf "$LPBK" "$LPARCH"
		echo "<FAIL> Panel-Konfiguration ließ sich nicht sichern – Update abgebrochen, es wurde nichts gelöscht. LoxPanel startet über die 5-Minuten-Prüfung wieder."
		exit 2
	fi
fi

# Besitzrechte der Daten-/Config-Ordner auf loxberry setzen.
chown -R loxberry:loxberry "$ARGV5/data/plugins/$ARGV3/" 2>/dev/null
chown -R loxberry:loxberry "$ARGV5/config/plugins/$ARGV3/" 2>/dev/null

exit $RC
