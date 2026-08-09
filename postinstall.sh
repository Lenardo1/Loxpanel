#!/bin/bash
# LoxHASP postinstall - laeuft nach der Installation als root.
# LoxBerry uebergibt Argumente (Version, Basisordner, Name, Ordner ...). Wir nutzen
# hier die LoxBerry-Umgebungsvariablen, die zur Laufzeit gesetzt sind.
set -e

echo "<INFO> LoxHASP postinstall gestartet"

# Datenverzeichnisse sicherstellen (LBPDATA / LBPLOG werden von LoxBerry gesetzt).
DATADIR="${LBPDATA}/loxhasp"
LOGDIR="${LBPLOG}/loxhasp"
mkdir -p "${DATADIR}/icons" "${DATADIR}/covers" "${LOGDIR}" 2>/dev/null || true

# Standard-Config anlegen, falls noch keine existiert.
if [ ! -f "${LBPCONFIG}/loxhasp/loxhasp.cfg" ] && [ -f "${LBPCONFIG}/loxhasp/loxhasp.cfg.example" ]; then
    cp "${LBPCONFIG}/loxhasp/loxhasp.cfg.example" "${LBPCONFIG}/loxhasp/loxhasp.cfg" || true
fi

# Skripte ausfuehrbar machen.
chmod +x "${LBPBIN}/loxhasp/importer.py" 2>/dev/null || true
chmod +x "${LBPHTMLAUTH}/../../daemon/loxhasp-daemon.py" 2>/dev/null || true

echo "<OK> LoxHASP postinstall fertig"
exit 0
