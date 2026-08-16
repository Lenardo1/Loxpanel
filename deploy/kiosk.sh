#!/bin/bash
# LoxPanel Chromium-Kiosk fuers Linux-Wandpanel (z.B. Linero / PX30, 480x480).
# Server-Adresse + Panel-ID kommen aus einer KONFIG-DATEI (nicht im Befehl hart
# verdrahtet) -> IP/Server aendern, ohne den Autostart anzufassen.
#
# Konfig (erste gefundene gewinnt): $LOXPANEL_KIOSK_CONF,
#   <dieses-verzeichnis>/loxpanel-kiosk.conf, /etc/loxpanel/kiosk.conf
# Inhalt (siehe loxpanel-kiosk.conf.example):
#   SERVER=host:port    # Adresse des LoxPanel-Servers (LoxBerry oder PC)
#   PANEL=<profil-id>   # Panel-Profil (leer = Standard)

for f in "$LOXPANEL_KIOSK_CONF" "$(dirname "$0")/loxpanel-kiosk.conf" /etc/loxpanel/kiosk.conf; do
  [ -n "$f" ] && [ -f "$f" ] && { . "$f"; break; }
done
SERVER="${SERVER:-localhost:8099}"     # Fallback: Server laeuft auf dem Panel selbst
PANEL="${PANEL:-}"
URL="http://${SERVER}/"
[ -n "$PANEL" ] && URL="${URL}?panel=${PANEL}"

export DISPLAY="${DISPLAY:-:0}"

# X-eigenen Blank-Screensaver aus (Browser-Screensaver uebernimmt). Die
# Display-Abschaltung (Backlight) NICHT hart deaktivieren, sondern per DPMS_OFF
# (Sekunden) steuern — sonst laeuft nur der Web-Screensaver und das Panel wird
# heiss. DPMS_OFF leer/0 = nie abschalten.
xset s off 2>/dev/null; xset s noblank 2>/dev/null
if [ "${DPMS_OFF:-0}" -gt 0 ] 2>/dev/null; then
  xset +dpms 2>/dev/null; xset dpms 0 0 "${DPMS_OFF}" 2>/dev/null
else
  xset -dpms 2>/dev/null
fi
# Mauszeiger verstecken (falls unclutter installiert). Die Visu blendet den
# Cursor selbst per CSS aus (Touch); unclutter ist nur Zusatz fuer X11. Kein
# -root (bricht bei unclutter-xfixes); Fehler unterdruecken.
command -v unclutter >/dev/null && unclutter -idle 0.5 >/dev/null 2>&1 &

# Chromium-Binary finden (heisst je nach Distro chromium oder chromium-browser)
CHROME="$(command -v chromium || command -v chromium-browser)"
[ -z "$CHROME" ] && { echo "Chromium nicht gefunden - bitte installieren"; exit 1; }

# Absturz-Wiederherstellungs-Dialog unterdruecken (im Wegwerf-Profil)
PROFILE="/tmp/kiosk_profile"
mkdir -p "$PROFILE/Default"
sed -i 's/"exited_cleanly":false/"exited_cleanly":true/; s/"exit_type":"Crashed"/"exit_type":"Normal"/' \
    "$PROFILE/Default/Preferences" 2>/dev/null || true

echo "LoxPanel-Kiosk -> $URL"
exec "$CHROME" --kiosk \
  --user-data-dir="$PROFILE" \
  --noerrdialogs --disable-infobars --disable-session-crashed-bubble \
  --disable-pinch --overscroll-history-navigation=0 \
  --check-for-update-interval=31536000 \
  --force-device-scale-factor=1 \
  --autoplay-policy=no-user-gesture-required \
  --disable-features=HttpsUpgrades,HttpsFirstBalancedMode,HttpsFirstModeV2,Translate,TranslateUI \
  --no-first-run \
  "$URL"
