#!/bin/sh
# Vor einem Update die Nutzerdaten (panels.json, theme.json, loxpanel.cfg im
# Docker-Volume unter data/) sichern, damit sie ein Update sicher ueberleben.
# Args: <TEMPFOLDER> <NAME> <FOLDER> <VERSION> <BASEFOLDER>
ARGV1=$1
ARGV3=$3
ARGV5=$5
mkdir -p "/tmp/${ARGV1}_lpupgrade"
cp -a "$ARGV5/data/plugins/$ARGV3/." "/tmp/${ARGV1}_lpupgrade/" 2>/dev/null
exit 0
