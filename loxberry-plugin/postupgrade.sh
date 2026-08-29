#!/bin/sh
# Nach dem Update die gesicherten Nutzerdaten zurueckspielen.
# Args: <TEMPFOLDER> <NAME> <FOLDER> <VERSION> <BASEFOLDER>
ARGV1=$1
ARGV3=$3
ARGV5=$5
if [ -d "/tmp/${ARGV1}_lpupgrade" ]; then
	cp -a "/tmp/${ARGV1}_lpupgrade/." "$ARGV5/data/plugins/$ARGV3/" 2>/dev/null
	rm -rf "/tmp/${ARGV1}_lpupgrade"
fi
exit 0
