#!/bin/bash
# Laeuft als ROOT NACH der Installation.
# Args: <TEMPFOLDER> <NAME> <FOLDER> <VERSION> <BASEFOLDER>
ARGV3=$3
ARGV5=$5
BINDIR="$ARGV5/bin/plugins/$ARGV3"

chmod +x "$BINDIR/loxpanel-ctl.sh" 2>/dev/null

# Vor dem Start die in preroot.sh gesicherte Panel-Konfiguration zurueckspielen
# (als root -> keine Rechteprobleme). Muss VOR dem Container-Start passieren.
# Die Zwischenkopie verschwindet erst, wenn sie ganz zurueckgespielt ist;
# sonst exit 1 am Ende (LoxBerry meldet es) und sie bleibt fuer einen
# zweiten Versuch liegen. Pfade wie in preroot.sh.
LPTMP="${LOXPANEL_UPGRADE_TMP:-/tmp}"
LPBK="$LPTMP/loxpanel-upgrade-backup"
LPARCH="$LPTMP/loxpanel-upgrade-archive"
DATADIR="$ARGV5/data/plugins/$ARGV3"
RC=0
if [ -d "$LPBK" ] && [ -n "$(ls -A "$LPBK" 2>/dev/null)" ]; then
	mkdir -p "$DATADIR/config"
	if cp -a "$LPBK/." "$DATADIR/config/"; then
		rm -rf "$LPBK"
		echo "<OK> Panel-Konfiguration wiederhergestellt (Update-sicher)."
	else
		echo "<ERROR> Panel-Konfiguration nicht vollständig zurückgespielt – die Kopie liegt in $LPBK."
		RC=1
	fi
fi
# Archive aus dem Widget zurueck; backups/ muss loxberry gehoeren (Loeschen im
# Widget und Rotation in loxpanel-ctl.sh laufen als loxberry).
if [ -d "$LPARCH" ] && [ -n "$(ls -A "$LPARCH" 2>/dev/null)" ]; then
	mkdir -p "$DATADIR/backups"
	if cp -a "$LPARCH/." "$DATADIR/backups/"; then
		rm -rf "$LPARCH"
		echo "<OK> Sicherungen (Archive) wiederhergestellt (Update-sicher)."
	else
		echo "<ERROR> Sicherungen nicht vollständig zurückgespielt – die Kopie liegt in $LPARCH."
		RC=1
	fi
	chown loxberry:loxberry "$DATADIR/backups" 2>/dev/null
fi

# Reste eines alten Containers entfernen (Daten liegen im Volume -> verlustfrei).
docker rm -f loxpanel > /dev/null 2>&1

# LoxPanel starten – aber nur, wenn Docker schon verfuegbar ist. Beim Erst-
# Install wird Docker erst nach dem Reboot installiert; dann startet der
# daemon (Boot) das Panel automatisch.
if which docker > /dev/null 2>&1; then
	echo "<INFO> Starte LoxPanel..."
	su -s /bin/bash loxberry -c "$BINDIR/loxpanel-ctl.sh start"
	echo "<OK> LoxPanel laeuft – Oberflaeche: http://<LoxBerry-IP>:8099/config"
else
	echo "<INFO> Docker wird beim Neustart installiert – LoxPanel startet danach automatisch."
fi

exit $RC
