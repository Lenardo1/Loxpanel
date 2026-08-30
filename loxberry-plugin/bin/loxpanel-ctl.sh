#!/bin/bash
# LoxPanel Docker-Steuerung.  Nutzung: loxpanel-ctl.sh start|stop|restart|check|backup|restore <datei>
#   start   pullt das aktuelle Image und startet den Container
#   stop    stoppt den Container (merkt sich das -> check startet ihn NICHT neu)
#   restart stop + start  (zieht dabei das neueste Image = manuelles Update)
#   check   startet den Container, falls er (unerwartet) nicht laeuft
#           (fuer Boot-daemon und 5-Minuten-Cron; ein bewusst gestopptes
#            Panel wird NICHT wieder gestartet)
#   backup  sichert die Konfiguration (Panels/Theme/Miniserver) als tar.gz
#   restore <datei>  spielt ein Backup zurueck (sichert vorher den Ist-Stand)
# REPLACELBPCONFIGDIR / REPLACELBPDATADIR werden beim Install durch echte Pfade ersetzt.

COMPOSE="REPLACELBPCONFIGDIR/docker-compose.yml"
STOPPED="REPLACELBPCONFIGDIR/loxpanel_stopped.cfg"
# Konfig-Daten liegen im gemounteten Volume (panels.json, theme.json,
# loxpanel.cfg). Backups daneben in data/ -> ueberleben Plugin-Updates, weil
# pre-/postupgrade.sh das ganze data/-Verzeichnis sichern.
CONFIGDATA="REPLACELBPDATADIR/config"
BACKUPDIR="REPLACELBPDATADIR/backups"
KEEP=20                 # so viele Backups behalten, aeltere werden entfernt

running() {
	[ -n "$(sudo docker ps --filter 'name=^/loxpanel$' --filter status=running -q 2>/dev/null)" ]
}

backup() {
	[ -d "$CONFIGDATA" ] || { echo "Kein Konfig-Verzeichnis gefunden: $CONFIGDATA"; exit 1; }
	mkdir -p "$BACKUPDIR"
	local ts f
	ts=$(date +%Y%m%d-%H%M%S)
	f="$BACKUPDIR/loxpanel-config-$ts.tar.gz"
	if tar -czf "$f" -C "$CONFIGDATA" . 2>/dev/null; then
		echo "Backup erstellt: $(basename "$f") ($(du -h "$f" 2>/dev/null | cut -f1))"
	else
		echo "Backup fehlgeschlagen."; exit 1
	fi
	# aelteste ueber KEEP hinaus loeschen (Sicherungen vor Restore eingeschlossen)
	ls -1t "$BACKUPDIR"/loxpanel-config-*.tar.gz 2>/dev/null | tail -n +$((KEEP+1)) | xargs -r rm -f
}

restore() {
	local bn src ts
	bn=$(basename "$1")     # nur Dateiname, keine Pfad-Tricks
	src="$BACKUPDIR/$bn"
	[ -f "$src" ] || { echo "Backup nicht gefunden: $bn"; exit 1; }
	mkdir -p "$CONFIGDATA"
	# Ist-Stand vor dem Ueberschreiben sichern (Rueckweg offen halten)
	ts=$(date +%Y%m%d-%H%M%S)
	tar -czf "$BACKUPDIR/loxpanel-config-$ts-vor-restore.tar.gz" -C "$CONFIGDATA" . 2>/dev/null \
		&& echo "Aktuellen Stand gesichert (loxpanel-config-$ts-vor-restore.tar.gz)."
	echo "Spiele $bn ein..."
	if tar -xzf "$src" -C "$CONFIGDATA" 2>&1; then
		echo "Konfiguration wiederhergestellt."
	else
		echo "Wiederherstellung fehlgeschlagen."; exit 1
	fi
	# Container neu starten, damit die App die Panels frisch einliest (ohne pull)
	sudo docker restart loxpanel 2>&1 && echo "Panel neu gestartet."
}

start() {
	rm -f "$STOPPED"
	# Erst pullen, dann up -d: 'up' nutzt sonst ein evtl. veraltetes lokales
	# Image (der :latest-Tag ist rollend).
	sudo docker compose -f "$COMPOSE" pull 2>&1
	sudo docker compose -f "$COMPOSE" up -d 2>&1
}

stop() {
	touch "$STOPPED"
	sudo docker compose -f "$COMPOSE" down 2>&1
}

case "$1" in
	start)   start ;;
	stop)    stop ;;
	restart) stop; start ;;
	check)
		[ -f "$STOPPED" ] && exit 0     # bewusst gestoppt -> nichts tun
		running || start
		;;
	backup)  backup ;;
	restore) restore "$2" ;;
	*) echo "Nutzung: $0 start|stop|restart|check|backup|restore <datei>"; exit 1 ;;
esac
exit 0
