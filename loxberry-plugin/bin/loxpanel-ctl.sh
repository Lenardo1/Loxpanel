#!/bin/bash
# LoxPanel Docker-Steuerung.  Nutzung: loxpanel-ctl.sh start|stop|restart|check|backup|restore <datei>|keep
#   start   pullt das aktuelle Image und startet den Container
#   stop    stoppt den Container (merkt sich das -> check startet ihn NICHT neu)
#   restart stop + start  (zieht dabei das neueste Image = manuelles Update)
#   check   startet den Container, falls er (unerwartet) nicht laeuft
#           (fuer Boot-daemon und 5-Minuten-Cron; ein bewusst gestopptes
#            Panel wird NICHT wieder gestartet, waehrend backup/restore
#            wartet die Pruefung auf den naechsten Lauf)
#   backup  sichert die Konfiguration (Panels/Theme/Miniserver) als tar.gz
#   restore <datei>  spielt ein Backup zurueck (sichert vorher den Ist-Stand)
#   keep    gibt aus, wie viele Backups behalten werden (KEEP, fuer das Widget)
# REPLACELBPCONFIGDIR / REPLACELBPDATADIR werden beim Install durch echte Pfade ersetzt.
# LOXPANEL_CTL_CONFIGDIR / LOXPANEL_CTL_DATADIR ersetzen sie nur zum Testen
# ausserhalb eines LoxBerry, im Betrieb gelten die Pfade der Installation.

CONFIGDIR="${LOXPANEL_CTL_CONFIGDIR:-REPLACELBPCONFIGDIR}"
COMPOSE="$CONFIGDIR/docker-compose.yml"
STOPPED="$CONFIGDIR/loxpanel_stopped.cfg"
# Konfig-Daten liegen im gemounteten Volume (panels.json, theme.json,
# loxpanel.cfg) und gehoeren root (der Container schreibt als root). Backup/
# Restore laufen deshalb als root IM Container (sonst darf der Widget-Benutzer
# loxberry die root-Dateien nicht ueberschreiben -> "tar: Cannot open: File
# exists"). Sicherungen liegen in data/backups; pre-/postroot.sh tragen
# config/ und backups/ ueber Plugin-Updates (LoxBerry loescht dabei den
# Datenordner).
DATADIR="${LOXPANEL_CTL_DATADIR:-REPLACELBPDATADIR}"
CONFIGDATA="$DATADIR/config"
BACKUPDIR="$DATADIR/backups"
# So viele Archive behalten, aeltere werden entfernt (Sicherungen vor einem
# Restore eingeschlossen). 20: jede Wiederherstellung legt selbst eins an, so
# bleiben auch nach mehreren Versuchen genug fruehere Staende; ein Archiv hat
# nur wenige KB. Das Widget liest die Zahl ueber "loxpanel-ctl.sh keep".
KEEP=20
# Dateien, die LoxPanel in config/ schreibt (CFG_FILE, PANELS_FILE, THEME_FILE
# in bin/webvisu.py). Ein Backup ohne eine davon ist keine LoxPanel-Konfiguration.
KONFIG_DATEIEN="loxpanel.cfg panels.json theme.json"
NICHTS=3                # Status von _sichern: config/ fehlt oder ist leer
# backup und restore nie gleichzeitig (zweites Fenster, Doppelklick im Widget),
# check nie waehrend eines der beiden
SPERRE="$DATADIR/.loxpanel-ctl.lock"
# Zeitzone des LoxBerry fuer den Container (start): dessen /etc/localtime nur
# lesend an einen eigenen Pfad, TZ=":<pfad>" - glibc liest die Zone aus der
# Datei, keine Zone steht fest im Plugin. Nicht nach /etc/localtime im
# Container: dort liegt ein Symlink auf Etc/UTC, Docker folgte ihm und
# ueberschriebe die UTC-Zone selbst (icalendar laese "Z" dann falsch).
# LOXPANEL_CTL_LOCALTIME ersetzt /etc/localtime nur zum Testen ausserhalb
# eines LoxBerry.
LOCALTIME="${LOXPANEL_CTL_LOCALTIME:-/etc/localtime}"
TZ_ZIEL="/run/loxberry-localtime"
ZEITZONE="$CONFIGDIR/docker-compose.zeitzone.yml"

# Image aus der Compose-Datei lesen (Fallback fest).
_img() {
	local i
	i=$(sed -n 's/^[[:space:]]*image:[[:space:]]*//p' "$COMPOSE" | head -1)
	[ -n "$i" ] && echo "$i" || echo "ghcr.io/lenardo1/loxpanel:latest"
}

# Einen sh-Befehl als root im Container ausfuehren. $DATADIR wird nach /data
# gemountet -> config=/data/config, backups=/data/backups. Weitere Argumente
# stehen im Befehl als $1, $2 ... (Dateinamen nie in den Befehlstext).
_indocker() {
	local cmd=$1; shift
	sudo docker run --rm -v "$DATADIR":/data "$(_img)" sh -c "$cmd" sh "$@"
}

running() {
	[ -n "$(sudo docker ps --filter 'name=^/loxpanel$' --filter status=running -q 2>/dev/null)" ]
}

# Sperre auf fd 9 nicht-blockierend nehmen: 0 = gesperrt, 1 = ein anderer Lauf
# haelt sie, 2 = Sperrdatei nicht zu oeffnen. Nur lesend oeffnen: flock braucht
# kein Schreibrecht, so sperrt auch eine Datei, die ein Lauf als root (sudo
# loxpanel-ctl.sh ...) angelegt hat und die loxberry nicht schreiben darf.
_sperre() {
	[ -e "$SPERRE" ] || : >"$SPERRE"
	exec 9<"$SPERRE" || return 2
	flock -n 9 || return 1
}

# Sperre fuer backup/restore: ein zweiter Lauf bricht sofort ab, statt auf
# halbe Zwischenstaende des ersten zu treffen. Danach Reste abgebrochener Laeufe
# (Stromausfall, kill) wegraeumen - unter der Sperre laeuft sonst keiner.
_sperren() {
	local reste
	_sperre
	case $? in
		1) echo "Es läuft schon eine Sicherung oder Wiederherstellung, oder die Prüfung startet gerade das Panel – bitte warten und erneut versuchen."; exit 1 ;;
		2) echo "Sperrdatei $SPERRE lässt sich nicht anlegen – nichts geändert."; exit 1 ;;
	esac
	shopt -s nullglob
	reste=("$DATADIR"/.restore.* "$BACKUPDIR"/*.part)
	shopt -u nullglob
	[ ${#reste[@]} -eq 0 ] && return
	echo "Räume Reste eines abgebrochenen Laufs weg: ${reste[*]##*/}"
	_indocker 'cd /data && rm -rf -- "$@"' "${reste[@]#"$DATADIR"/}"
}

# Config-Ordner als backups/$1 sichern: erst unter $1.part schreiben, ganz
# zuruecklesen (tar -tzf prueft dabei die gzip-Pruefsumme), auf die Platte
# bringen und erst dann umbenennen. Ein halbes Archiv (Datentraeger voll,
# Abbruch) liegt so nie unter einem Namen, den das Widget anbietet; ein
# vorhandenes Archiv wird nie ersetzt. Status 0, $NICHTS oder Fehler.
_sichern() {
	_indocker 'cd /data/config 2>/dev/null && [ -n "$(ls -A)" ] || exit "$2"
z=/data/backups/$1
[ ! -e "$z" ] || { echo "$1 gibt es schon." >&2; exit 1; }
tar -czf "$z.part" . && tar -tzf "$z.part" >/dev/null && sync && mv "$z.part" "$z" && exit 0
rm -f "$z.part"; exit 1' "$1" "$NICHTS"
}

# Freier Archivname loxpanel-config-<Zeit>$1.tar.gz; in derselben Sekunde mit
# laufender Nummer, ein vorhandenes Archiv wird nie ersetzt (unter der Sperre
# legt sonst niemand eins an).
_freier_name() {
	local ts f n=1
	ts=$(date +%Y%m%d-%H%M%S)
	f="loxpanel-config-$ts$1.tar.gz"
	while [ -e "$BACKUPDIR/$f" ]; do n=$((n+1)); f="loxpanel-config-$ts-$n$1.tar.gz"; done
	echo "$f"
}

# Zwischenordner von restore loeschen (als root, der Inhalt gehoert root).
_wegraeumen() {
	_indocker 'rm -rf -- "/data/$1"' "$1"
}

# Den fuer restore angehaltenen Container wieder starten (ohne pull). restart
# statt start: Hat ihn in der Luecke jemand gestartet (Widget "Starten"), liest
# der Server die Konfiguration so trotzdem neu ein, statt den alten Stand im
# Speicher zu behalten und beim naechsten Speichern zurueckzuschreiben.
_wieder_starten() {
	[ "$1" = 1 ] || running || { echo "Panel ist gestoppt – die Konfiguration gilt beim nächsten Start."; return; }
	if sudo docker restart loxpanel >/dev/null; then echo "Panel neu gestartet."
	else echo "Panel ließ sich nicht starten – die 5-Minuten-Prüfung versucht es weiter."; fi
}

backup() {
	mkdir -p "$BACKUPDIR"     # als loxberry -> Verzeichnis bleibt loxberry-eigen (Loeschen moeglich)
	_sperren
	local f rc
	f=$(_freier_name "")
	_sichern "$f"; rc=$?
	case $rc in
		0) echo "Backup erstellt: $f ($(du -h "$BACKUPDIR/$f" 2>/dev/null | cut -f1))" ;;
		"$NICHTS") echo "Keine Konfiguration vorhanden – nichts zu sichern."; exit 1 ;;
		*) echo "Backup fehlgeschlagen – es wurde kein Archiv angelegt."; exit 1 ;;
	esac
	# aelteste ueber KEEP hinaus loeschen (Sicherungen vor Restore eingeschlossen)
	ls -1t "$BACKUPDIR"/loxpanel-config-*.tar.gz 2>/dev/null | tail -n +$((KEEP+1)) | xargs -r rm -f
}

# Erst pruefen, dann tauschen: config/ aendert sich erst, wenn das Backup
# vollstaendig entpackt und als LoxPanel-Konfiguration erkannt und der
# Ist-Stand gesichert ist. Scheitert ein Schritt, bleibt alles, wie es war.
restore() {
	local bn tmp vor rc lief=0
	bn=$(basename "$1")     # nur Dateiname, keine Pfad-Tricks
	[ -f "$BACKUPDIR/$bn" ] || { echo "Backup nicht gefunden: $bn"; exit 1; }
	_sperren
	# 1. In einen Zwischenordner neben config/ entpacken (gleiches Dateisystem ->
	#    der Tausch unten ist nur Umbenennen) und pruefen. Der Container laeuft
	#    dabei weiter.
	tmp=$(mktemp -d "$DATADIR/.restore.XXXXXX") || { echo "Kein Zwischenordner möglich – nichts geändert."; exit 1; }
	tmp=${tmp##*/}
	echo "Prüfe $bn …"
	if ! _indocker 'mkdir "/data/$2/neu" && tar -xzf "/data/backups/$1" -C "/data/$2/neu" || exit 1
for n in $3; do [ -f "/data/$2/neu/$n" ] && sync && exit 0; done
echo "Keine LoxPanel-Konfiguration ($3) im Archiv." >&2; exit 1' "$bn" "$tmp" "$KONFIG_DATEIEN"; then
		_wegraeumen "$tmp"
		echo "Backup nicht eingespielt: Es ließ sich nicht vollständig entpacken oder enthält keine LoxPanel-Konfiguration (Grund steht darüber) – nichts geändert."; exit 1
	fi
	# 2. Container anhalten, sonst schreibt der Server womoeglich zwischen
	#    Vorher-Sicherung und Tausch (Speichern im Konfigurator).
	if running; then
		lief=1
		sudo docker stop loxpanel >/dev/null || {
			_wegraeumen "$tmp"; echo "Panel ließ sich nicht anhalten – nichts geändert."; exit 1; }
	fi
	# 3. Ist-Stand sichern - Pflicht, ausser es gibt keinen.
	vor=$(_freier_name "-vor-restore")
	_sichern "$vor"; rc=$?
	case $rc in
		0) echo "Aktuellen Stand gesichert ($vor)." ;;
		"$NICHTS") echo "Keine aktuelle Konfiguration – nichts vorher zu sichern."; vor="" ;;
		*) _wegraeumen "$tmp"; _wieder_starten "$lief"
		   echo "Aktuellen Stand nicht sichern können – nichts geändert."; exit 1 ;;
	esac
	# 4. Tauschen: Ist-Stand nach alt/, Backup nach config/. Scheitert ein
	#    Schritt, kommt der Ist-Stand zurueck (find meldet jeden Fehler von mv).
	echo "Spiele $bn ein …"
	if _indocker 'c=/data/config; t="/data/$1"
mkdir -p "$c" "$t/alt" || exit 1
if find "$c" -mindepth 1 -maxdepth 1 -exec mv -t "$t/alt" -- {} +; then
	find "$t/neu" -mindepth 1 -maxdepth 1 -exec mv -t "$c" -- {} + && sync && exit 0
	find "$c" -mindepth 1 -maxdepth 1 -exec mv -t "$t/neu" -- {} +
fi
find "$t/alt" -mindepth 1 -maxdepth 1 -exec mv -t "$c" -- {} +
exit 1' "$tmp"; then
		_wegraeumen "$tmp"
		echo "Konfiguration wiederhergestellt."
		_wieder_starten "$lief"
	else
		_wieder_starten "$lief"
		echo "Wiederherstellung fehlgeschlagen – der bisherige Stand ist zurückgestellt${vor:+ und liegt zusätzlich in $vor}."
		exit 1
	fi
}

# Override-Datei fuer die Zeitzone bei jedem start neu schreiben (Status 0),
# aber nur, wenn /etc/localtime eine Datei ist ([ -f ] folgt dem Symlink): ein
# toter Symlink verhinderte den Start, eine fehlende Datei legte Docker am
# LoxBerry als Verzeichnis an. Sonst ohne Zeitzone (UTC) und warnen (Status 1).
_zeitzone() {
	if [ -f "$LOCALTIME" ]; then
		cat > "$ZEITZONE" <<EOF && return 0
# Von loxpanel-ctl.sh start geschrieben, nicht bearbeiten: Zeitzone des LoxBerry.
services:
  loxpanel:
    environment:
      TZ: ":$TZ_ZIEL"
    volumes:
      - "$LOCALTIME:$TZ_ZIEL:ro"
EOF
		echo "Warnung: $ZEITZONE ließ sich nicht schreiben – LoxPanel läuft in UTC."
	else
		echo "Warnung: $LOCALTIME fehlt oder zeigt ins Leere – LoxPanel läuft in UTC. Zeitzone im LoxBerry einstellen und LoxPanel neu starten."
	fi
	rm -f "$ZEITZONE"
	return 1
}

start() {
	local dateien=(-f "$COMPOSE")
	rm -f "$STOPPED"
	_zeitzone && dateien+=(-f "$ZEITZONE")
	# Erst pullen, dann up -d: 'up' nutzt sonst ein evtl. veraltetes lokales
	# Image (der :latest-Tag ist rollend).
	sudo docker compose "${dateien[@]}" pull 2>&1
	sudo docker compose "${dateien[@]}" up -d 2>&1
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
		# Nicht waehrend backup/restore: restore haelt den Container fuer den
		# Tausch an, ein Start hier liesse den Server mitten im Tausch laufen.
		# Die naechste Pruefung holt es nach. Die Sperre gilt bis zum Ende, sonst
		# begaenne ein restore mitten im Start. Ist die Sperrdatei nicht zu
		# oeffnen (2), trotzdem pruefen: ein Panel, das nie mehr startet, waere
		# schlimmer.
		_sperre
		[ $? = 1 ] && { echo "Sicherung oder Wiederherstellung läuft – Prüfung übersprungen."; exit 0; }
		running || start
		;;
	backup)  backup ;;
	restore) restore "$2" ;;
	keep)    echo "$KEEP" ;;
	*) echo "Nutzung: $0 start|stop|restart|check|backup|restore <datei>|keep"; exit 1 ;;
esac
exit 0
