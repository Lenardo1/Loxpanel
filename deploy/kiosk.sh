#!/bin/bash
# LoxPanel Chromium-Kiosk fuer das PX30-Panel (480x480).
# In den vorhandenen X11-Autostart einhaengen (ersetzt die alte Loxone-App).
# URL anpassen: localhost, wenn der Server auf dem Panel selbst laeuft,
#               sonst http://<loxberry-oder-server-ip>:8099
URL="http://localhost:8099"

# Bildschirmschoner / Energiesparen aus
xset s off; xset -dpms; xset s noblank
# Mauszeiger verstecken (falls unclutter installiert)
command -v unclutter >/dev/null && unclutter -idle 0.5 -root &

# Chromium-Binary finden (heisst je nach Distro chromium oder chromium-browser)
CHROME="$(command -v chromium || command -v chromium-browser)"
[ -z "$CHROME" ] && { echo "Chromium nicht gefunden - bitte installieren"; exit 1; }

# Absturz-Wiederherstellungs-Dialog unterdruecken
PROFILE="$HOME/.config/chromium"
sed -i 's/"exited_cleanly":false/"exited_cleanly":true/; s/"exit_type":"Crashed"/"exit_type":"Normal"/' \
    "$PROFILE/Default/Preferences" 2>/dev/null || true

exec "$CHROME" \
  --kiosk --app="$URL" \
  --noerrdialogs --disable-infobars --disable-session-crashed-bubble \
  --disable-pinch --overscroll-history-navigation=0 \
  --check-for-update-interval=31536000 \
  --force-device-scale-factor=1 \
  --autoplay-policy=no-user-gesture-required
