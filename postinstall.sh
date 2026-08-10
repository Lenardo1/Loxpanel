#!/bin/bash
# LoxPanel postinstall - laeuft nach der Installation als root.
# LoxBerry uebergibt Argumente (Version, Basisordner, Name, Ordner ...). Wir nutzen
# hier die LoxBerry-Umgebungsvariablen, die zur Laufzeit gesetzt sind.
set -e

echo "<INFO> LoxPanel postinstall gestartet"

# Datenverzeichnisse sicherstellen (LBPDATA / LBPLOG werden von LoxBerry gesetzt).
DATADIR="${LBPDATA}/loxpanel"
LOGDIR="${LBPLOG}/loxpanel"
mkdir -p "${DATADIR}/icons" "${DATADIR}/covers" "${LOGDIR}" 2>/dev/null || true

# Standard-Config anlegen, falls noch keine existiert.
if [ ! -f "${LBPCONFIG}/loxpanel/loxpanel.cfg" ] && [ -f "${LBPCONFIG}/loxpanel/loxpanel.cfg.example" ]; then
    cp "${LBPCONFIG}/loxpanel/loxpanel.cfg.example" "${LBPCONFIG}/loxpanel/loxpanel.cfg" || true
fi

# Skripte ausfuehrbar machen.
chmod +x "${LBPBIN}/loxpanel/importer.py" 2>/dev/null || true
chmod +x "${LBPHTMLAUTH}/../../daemon/loxpanel-daemon.py" 2>/dev/null || true

echo "<OK> LoxPanel postinstall fertig"
exit 0
