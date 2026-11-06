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
LPEIN="$LPTMP/loxpanel-upgrade-plugin.cfg"
DATADIR="$ARGV5/data/plugins/$ARGV3"
CONFIGDIR="$ARGV5/config/plugins/$ARGV3"
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

# Einstellungen des Plugins (Port am LoxBerry) zurueck, vor dem Start; die
# Datei muss loxberry gehoeren ("loxpanel-ctl.sh port" schreibt sie im Widget).
if [ -f "$LPEIN" ]; then
	mkdir -p "$CONFIGDIR"
	if cp "$LPEIN" "$CONFIGDIR/loxpanel_plugin.cfg"; then
		rm -f "$LPEIN"
		chown loxberry:loxberry "$CONFIGDIR/loxpanel_plugin.cfg" 2>/dev/null
		echo "<OK> Plugin-Einstellungen (Port am LoxBerry) wiederhergestellt (Update-sicher)."
	else
		echo "<ERROR> Plugin-Einstellungen nicht zurückgespielt – die Kopie liegt in $LPEIN."
		RC=1
	fi
fi

# Reste eines alten Containers entfernen (Daten liegen im Volume -> verlustfrei).
docker rm -f loxpanel > /dev/null 2>&1

# LoxPanel starten – aber nur, wenn Docker schon laeuft. Ist Docker nach dem
# Erst-Install noch nicht bereit, fordern wir den Neustart an (plugin.cfg hat
# REBOOT=false, damit Updates ohne Neustart auskommen); nach dem Neustart
# startet der daemon (Boot) das Panel automatisch. Scheitert der Start (etwa:
# Port am LoxBerry belegt), steht der Grund in der Ausgabe darueber.
if which docker > /dev/null 2>&1 && docker info > /dev/null 2>&1; then
	echo "<INFO> Starte LoxPanel..."
	PORT=$(su -s /bin/bash loxberry -c "$BINDIR/loxpanel-ctl.sh port")
	if su -s /bin/bash loxberry -c "$BINDIR/loxpanel-ctl.sh start"; then
		echo "<OK> LoxPanel laeuft – Oberflaeche: http://<LoxBerry-IP>:$PORT/config"
	else
		echo "<WARNING> LoxPanel ist nicht gestartet (Grund steht darüber). Im LoxBerry-Widget prüfen, etwa einen freien „Port am LoxBerry“ einstellen."
		RC=1
	fi
else
	# Wie plugininstall.pl bei REBOOT=true: LoxBerry::System::reboot_required()
	# schreibt nach log/system_tmpfs/reboot.required, die Oberflaeche zeigt dann
	# "Neustart erforderlich". Ohne die Perl-Lib dieselbe Datei direkt.
	LPREBOOT="LoxPanel: Neustart nötig, damit Docker bereit ist."
	if ! perl -I "$ARGV5/libs/perllib" -MLoxBerry::System -e 'LoxBerry::System::reboot_required($ARGV[0])' "$LPREBOOT" 2>/dev/null; then
		echo "$LPREBOOT" >> "$ARGV5/log/system_tmpfs/reboot.required"
		chown loxberry:loxberry "$ARGV5/log/system_tmpfs/reboot.required" 2>/dev/null
	fi
	echo "<INFO> Docker ist noch nicht bereit – bitte LoxBerry neu starten, LoxPanel startet danach automatisch."
fi

exit $RC
