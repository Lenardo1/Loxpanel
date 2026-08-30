#!/bin/bash
# LoxPanel Docker-Steuerung.  Nutzung: loxpanel-ctl.sh start|stop|restart|check
#   start   pullt das aktuelle Image und startet den Container
#   stop    stoppt den Container (merkt sich das -> check startet ihn NICHT neu)
#   restart stop + start  (zieht dabei das neueste Image = manuelles Update)
#   check   startet den Container, falls er (unerwartet) nicht laeuft
#           (fuer Boot-daemon und 5-Minuten-Cron; ein bewusst gestopptes
#            Panel wird NICHT wieder gestartet)
# REPLACELBPCONFIGDIR wird beim Install durch echte Pfade ersetzt.

COMPOSE="REPLACELBPCONFIGDIR/docker-compose.yml"
STOPPED="REPLACELBPCONFIGDIR/loxpanel_stopped.cfg"

running() {
	[ -n "$(sudo docker ps --filter 'name=^/loxpanel$' --filter status=running -q 2>/dev/null)" ]
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
	*) echo "Nutzung: $0 start|stop|restart|check"; exit 1 ;;
esac
exit 0
