#!/bin/sh
# Baut das LoxPanel-Server .deb. Auszufuehren auf einem Debian-Host (dpkg-deb).
# Nimmt den Code aus dem Repo (bin/webfrontend/config), Config OHNE echte
# Zugangsdaten (nur .example/Schema). Ergebnis-.deb liegt im Repo-Wurzel.
set -e

HERE=$(cd "$(dirname "$0")" && pwd)     # packaging/deb
REPO=$(cd "$HERE/../.." && pwd)         # Repo-Wurzel
VERSION=$(awk -F': ' '/^Version:/{print $2; exit}' "$HERE/control")
STAGE=$(mktemp -d)
PKG="$STAGE/loxpanel-server_${VERSION}_all"

install -d "$PKG/DEBIAN" "$PKG/opt/loxpanel/app/config" \
          "$PKG/usr/lib/systemd/system" "$PKG/usr/bin" "$PKG/etc/loxpanel"

# --- App-Code aus dem Repo ---
cp -r "$REPO/bin"          "$PKG/opt/loxpanel/app/bin"
cp -r "$REPO/webfrontend"  "$PKG/opt/loxpanel/app/webfrontend"
[ -d "$REPO/deploy" ] && cp -r "$REPO/deploy" "$PKG/opt/loxpanel/app/deploy" || true
cp "$REPO/requirements.txt" "$PKG/opt/loxpanel/app/requirements.txt"
# Config credential-frei: nur Vorlagen/Schema, keine echten Daten
for f in "$REPO"/config/*.example* "$REPO"/config/*.schema.json; do
    [ -e "$f" ] && cp "$f" "$PKG/opt/loxpanel/app/config/"
done

# --- Control + Maintainer-Skripte ---
cp "$HERE/control" "$HERE/conffiles" "$PKG/DEBIAN/"
for s in postinst prerm postrm; do
    cp "$HERE/$s" "$PKG/DEBIAN/$s"; chmod 0755 "$PKG/DEBIAN/$s"
done

# --- systemd + Kiosk + Conf ---
cp "$HERE/loxpanel-server.service" "$PKG/usr/lib/systemd/system/"
cp "$HERE/loxpanel-kiosk"          "$PKG/usr/bin/loxpanel-kiosk"; chmod 0755 "$PKG/usr/bin/loxpanel-kiosk"
cp "$HERE/browser.conf"            "$PKG/etc/loxpanel/browser.conf"

OUT="$REPO/loxpanel-server_${VERSION}_all.deb"
dpkg-deb --root-owner-group --build "$PKG" "$OUT"
echo "Fertig: $OUT"
rm -rf "$STAGE"
