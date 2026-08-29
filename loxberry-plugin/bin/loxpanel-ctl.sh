#!/bin/bash
# LoxPanel Docker-Steuerung.  Nutzung: loxpanel-ctl.sh start|stop|restart|check|update
#   start   pullt das aktuelle Image und startet den Container
#   stop    stoppt den Container (merkt sich das -> check startet ihn NICHT neu)
#   restart stop + start
#   check   startet den Container, falls er (unerwartet) nicht laeuft
#           (fuer Boot-daemon und 5-Minuten-Cron; ein bewusst gestopptes
#            Panel wird NICHT wieder gestartet)
#   update  zieht ein neues App-Image und uebernimmt es (fuer cron.daily) -
#           uebersprungen, wenn bewusst gestoppt ODER Auto-Update abgewaehlt.
# REPLACELBPCONFIGDIR / REPLACELBPDATADIR werden beim Install durch echte Pfade ersetzt.

COMPOSE="REPLACELBPCONFIGDIR/docker-compose.yml"
STOPPED="REPLACELBPCONFIGDIR/loxpanel_stopped.cfg"
# Auto-Update-Schalter: liegt im persistenten data/-Ordner (ueberlebt Updates,
# da pre-/postupgrade.sh data/ sichern). Datei existiert = Auto-Update AUS.
AUTOUPDATE_OFF="REPLACELBPDATADIR/autoupdate_off"

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

update() {
	# Automatischer App-Update-Pull (cron.daily). Nichts tun, wenn das Panel
	# bewusst gestoppt ist oder Auto-Update in der Plugin-Seite abgewaehlt wurde.
	[ -f "$STOPPED" ] && exit 0
	[ -f "$AUTOUPDATE_OFF" ] && exit 0
	sudo docker compose -f "$COMPOSE" pull 2>&1
	# up -d erkennt ein neu gezogenes Image und ersetzt den Container nur dann.
	sudo docker compose -f "$COMPOSE" up -d 2>&1
}

case "$1" in
	start)   start ;;
	stop)    stop ;;
	restart) stop; start ;;
	check)
		[ -f "$STOPPED" ] && exit 0     # bewusst gestoppt -> nichts tun
		running || start
		;;
	update)  update ;;
	*) echo "Nutzung: $0 start|stop|restart|check|update"; exit 1 ;;
esac
exit 0
