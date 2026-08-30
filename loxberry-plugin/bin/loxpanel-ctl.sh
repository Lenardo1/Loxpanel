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
# loxpanel.cfg) und gehoeren root (der Container schreibt als root). Backup/
# Restore laufen deshalb als root IM Container (sonst darf der Widget-Benutzer
# loxberry die root-Dateien nicht ueberschreiben -> "tar: Cannot open: File
# exists"). Sicherungen liegen in data/backups und ueberleben Plugin-Updates
# (pre-/postroot.sh sichern die Konfiguration ueber das Update hinweg).
DATADIR="REPLACELBPDATADIR"
CONFIGDATA="REPLACELBPDATADIR/config"
BACKUPDIR="REPLACELBPDATADIR/backups"
KEEP=20                 # so viele Backups behalten, aeltere werden entfernt

# Image aus der Compose-Datei lesen (Fallback fest).
_img() {
	local i
	i=$(sed -n 's/^[[:space:]]*image:[[:space:]]*//p' "$COMPOSE" | head -1)
	[ -n "$i" ] && echo "$i" || echo "ghcr.io/lenardo1/loxpanel:latest"
}

# Einen sh-Befehl als root im Container ausfuehren. $DATADIR wird nach /data
# gemountet -> config=/data/config, backups=/data/backups.
_indocker() {
	sudo docker run --rm -v "$DATADIR":/data "$(_img)" sh -c "$1"
}

running() {
	[ -n "$(sudo docker ps --filter 'name=^/loxpanel$' --filter status=running -q 2>/dev/null)" ]
}

backup() {
	mkdir -p "$BACKUPDIR"     # als loxberry -> Verzeichnis bleibt loxberry-eigen (Loeschen moeglich)
	local ts f
	ts=$(date +%Y%m%d-%H%M%S)
	f="loxpanel-config-$ts.tar.gz"
	if _indocker "cd /data/config 2>/dev/null && tar -czf /data/backups/$f . 2>/dev/null"; then
		echo "Backup erstellt: $f ($(du -h "$BACKUPDIR/$f" 2>/dev/null | cut -f1))"
	else
		echo "Backup fehlgeschlagen (Konfiguration vorhanden?)."; exit 1
	fi
	# aelteste ueber KEEP hinaus loeschen (Sicherungen vor Restore eingeschlossen)
	ls -1t "$BACKUPDIR"/loxpanel-config-*.tar.gz 2>/dev/null | tail -n +$((KEEP+1)) | xargs -r rm -f
}

restore() {
	local bn ts
	bn=$(basename "$1")     # nur Dateiname, keine Pfad-Tricks
	[ -f "$BACKUPDIR/$bn" ] || { echo "Backup nicht gefunden: $bn"; exit 1; }
	mkdir -p "$BACKUPDIR"
	ts=$(date +%Y%m%d-%H%M%S)
	# Ist-Stand vor dem Ueberschreiben sichern (Rueckweg offen halten)
	_indocker "cd /data/config 2>/dev/null && tar -czf /data/backups/loxpanel-config-$ts-vor-restore.tar.gz . 2>/dev/null" \
		&& echo "Aktuellen Stand gesichert (loxpanel-config-$ts-vor-restore.tar.gz)."
	echo "Spiele $bn ein..."
	# config leeren und Backup als root einspielen (ueberschreibt root-Dateien)
	if _indocker "mkdir -p /data/config && cd /data/config && rm -rf ./* && tar -xzf /data/backups/$bn -C /data/config"; then
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
