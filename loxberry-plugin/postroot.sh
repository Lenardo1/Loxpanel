#!/bin/bash
# Laeuft als ROOT NACH der Installation.
# Args: <TEMPFOLDER> <NAME> <FOLDER> <VERSION> <BASEFOLDER>
ARGV3=$3
ARGV5=$5
BINDIR="$ARGV5/bin/plugins/$ARGV3"

chmod +x "$BINDIR/loxpanel-ctl.sh" 2>/dev/null

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

exit 0
