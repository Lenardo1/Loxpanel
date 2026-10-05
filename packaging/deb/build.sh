#!/bin/sh
# Baut das LoxPanel-Server .deb. Auszufuehren auf einem Debian-Host (dpkg-deb).
# Nimmt den Code aus dem Repo (bin/webfrontend/config), Config OHNE echte
# Zugangsdaten (nur .example/Schema). Ergebnis-.deb liegt im Repo-Wurzel.
# Commit fuer die Versionsanzeige: LOXPANEL_COMMIT, sonst Git (siehe unten).
set -e

HERE=$(cd "$(dirname "$0")" && pwd)     # packaging/deb
REPO=$(cd "$HERE/../.." && pwd)         # Repo-Wurzel
# Version aus der gemeinsamen Projektquelle loxberry-plugin/plugin.cfg (wie
# APK, Docker-Image und LoxBerry-Plugin), nicht aus control. Muster wie in
# bin/version_info.py: VERSION=x.y.z, jede Stelle mindestens eine Ziffer;
# Windows-Zeilenenden (CR) stoeren nicht.
VERSION=$(tr -d '\r' < "$REPO/loxberry-plugin/plugin.cfg" \
    | sed -n 's/^VERSION=\([0-9][0-9]*\.[0-9][0-9]*\.[0-9][0-9]*\)[[:space:]]*$/\1/p' | head -n 1)
if [ -z "$VERSION" ]; then
    echo "loxberry-plugin/plugin.cfg: keine Zeile VERSION=x.y.z" >&2
    exit 1
fi
STAGE=$(mktemp -d)
trap 'rm -rf "$STAGE"' EXIT             # auch bei Abbruch aufraeumen
trap 'exit 1' HUP INT TERM
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

# --- Stand fuer die Anzeige im Konfigurator ---
# bin/version_info.py liest Version, Commit und Bauzeit aus bin/version.json;
# ohne die Datei faellt es auf loxberry-plugin/plugin.cfg und Git zurueck, die
# beide nicht im Paket sind ("Version unbekannt"). Geschrieben ohne Python (der
# Bau-Host braucht keins, das Paket holt es erst bei der Installation), im
# Format von version_info.schreiben(); ersetzt eine veraltete bin/version.json
# aus dem Arbeitsbaum. Commit: LOXPANEL_COMMIT (deb.yml setzt github.sha), sonst
# HEAD des Repos, sonst leer. In die Datei kommt nur eine Hex-Kennung mit 7 bis
# 40 Zeichen (wie loxCommit in android/app/build.gradle.kts).
ist_commit() {
    case $1 in
        ''|*[!0123456789abcdefABCDEF]*) return 1 ;;
    esac
    [ "${#1}" -ge 7 ] && [ "${#1}" -le 40 ]
}
COMMIT=${LOXPANEL_COMMIT-}
COMMIT=${COMMIT#"${COMMIT%%[![:space:]]*}"}     # Leerraum vorn ...
COMMIT=${COMMIT%"${COMMIT##*[![:space:]]}"}     # ... und hinten weg
# leer gesetzt zaehlt wie nicht gesetzt, alles andere muss eine Kennung sein
if [ -n "${LOXPANEL_COMMIT-}" ] && ! ist_commit "$COMMIT"; then
    echo "LOXPANEL_COMMIT ist keine Commit-Kennung (7 bis 40 Hex-Zeichen), wird nicht verwendet" >&2
    COMMIT=
fi
# HEAD nur, wenn das Repo selbst ein Git-Checkout ist (in einem Worktree ist
# .git eine Datei), nie der eines umgebenden Repos; wie version_info.git_commit
if [ -z "$COMMIT" ] && [ -e "$REPO/.git" ]; then
    COMMIT=$(git -C "$REPO" rev-parse HEAD 2>/dev/null) || COMMIT=
    ist_commit "$COMMIT" || COMMIT=
fi
GEBAUT=$(date -u +%Y-%m-%dT%H:%M:%SZ)  # UTC, Format wie version_info
case $GEBAUT in
    [0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]Z) ;;
    *) echo "date: Bauzeit nicht im Format JJJJ-MM-TTThh:mm:ssZ" >&2; exit 1 ;;
esac
VJSON="$PKG/opt/loxpanel/app/bin/version.json"
rm -f "$VJSON"                          # veraltete weg; durch einen Symlink nie hindurch
printf '{"version": "%s", "commit": "%s", "gebaut": "%s"}\n' \
    "$VERSION" "$COMMIT" "$GEBAUT" > "$VJSON"

# --- Control + Maintainer-Skripte ---
# control traegt keine eigene Version: sie wird hier hinter Package: eingesetzt
# und geprueft (genau eine Zeile Version:, die aus plugin.cfg).
awk -v v="$VERSION" '{print} /^Package:/{print "Version: " v}' "$HERE/control" > "$PKG/DEBIAN/control"
if [ "$(grep '^Version:' "$PKG/DEBIAN/control")" != "Version: $VERSION" ]; then
    echo "packaging/deb/control: braucht eine Zeile Package: und keine eigene Zeile Version: (die Version kommt aus loxberry-plugin/plugin.cfg)" >&2
    exit 1
fi
cp "$HERE/conffiles" "$PKG/DEBIAN/"
for s in postinst prerm postrm; do
    cp "$HERE/$s" "$PKG/DEBIAN/$s"; chmod 0755 "$PKG/DEBIAN/$s"
done

# --- systemd + Kiosk + Display-Abschaltung + Conf ---
cp "$HERE/loxpanel-server.service"  "$PKG/usr/lib/systemd/system/"
cp "$HERE/loxpanel-display.service" "$PKG/usr/lib/systemd/system/"
cp "$HERE/loxpanel-kiosk"   "$PKG/usr/bin/loxpanel-kiosk";   chmod 0755 "$PKG/usr/bin/loxpanel-kiosk"
cp "$HERE/loxpanel-display" "$PKG/usr/bin/loxpanel-display"; chmod 0755 "$PKG/usr/bin/loxpanel-display"
cp "$HERE/browser.conf"     "$PKG/etc/loxpanel/browser.conf"
cp "$HERE/display.conf"     "$PKG/etc/loxpanel/display.conf"

OUT="$REPO/loxpanel-server_${VERSION}_all.deb"
# -Zgzip erzwingen: neuere dpkg-deb (Ubuntu/Debian 12) komprimieren sonst mit
# zstd, das aeltere Ziel-dpkg (Debian 11 bullseye = dpkg 1.20, kein zst) nicht
# installieren koennen ("unknown compression for member 'control.tar.zst'").
# gzip ist auf allen unterstuetzten Panels lesbar.
dpkg-deb -Zgzip --root-owner-group --build "$PKG" "$OUT"
echo "Fertig: $OUT"
