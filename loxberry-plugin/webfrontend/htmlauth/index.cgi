#!/bin/bash
# LoxBerry-Plugin-Seite fuer LoxPanel.
#  - zeigt den Container-Status
#  - Miniserver-Zugang eingeben (wird an den laufenden Container weitergereicht:
#    POST http://localhost:8099/api/settings/miniserver -> speichert + verbindet)
#  - Buttons zur vollen Oberflaeche (/config, /settings) und Container-Steuerung
# Der Container-Port 8099 ist auf dem LoxBerry-Host gemappt -> localhost erreichbar.

API="http://localhost:8099"
CTL="REPLACELBPBINDIR/loxpanel-ctl.sh"
HOST=$(echo "${HTTP_HOST:-localhost}" | cut -d: -f1)

hesc() { local s="$1"; s="${s//&/&amp;}"; s="${s//</&lt;}"; s="${s//>/&gt;}"; s="${s//\"/&quot;}"; printf '%s' "$s"; }
jesc() { local s="$1"; s="${s//\\/\\\\}"; s="${s//\"/\\\"}"; printf '%s' "$s"; }
urldec() { local d="${1//+/ }"; printf '%b' "${d//%/\\x}"; }

MSG=""
# --- POST: Container-Steuerung oder Miniserver speichern ---
if [ "$REQUEST_METHOD" = "POST" ]; then
	POST=$(head -c "${CONTENT_LENGTH:-0}")
	declare -A F
	IFS='&' read -ra PAIRS <<< "$POST"
	for p in "${PAIRS[@]}"; do F["${p%%=*}"]=$(urldec "${p#*=}"); done

	case "${F[action]}" in
		start)   "$CTL" start   >/dev/null 2>&1; MSG="<div class='ok'>LoxPanel gestartet.</div>" ;;
		stop)    "$CTL" stop    >/dev/null 2>&1; MSG="<div class='ok'>LoxPanel gestoppt.</div>" ;;
		restart) "$CTL" restart >/dev/null 2>&1; MSG="<div class='ok'>LoxPanel neu gestartet (Image aktualisiert).</div>" ;;
		miniserver)
			TLS=false; [ "${F[tls]}" = "on" ] && TLS=true
			JSON=$(printf '{"host":"%s","user":"%s","pass":"%s","port":%s,"verify_tls":%s}' \
				"$(jesc "${F[host]}")" "$(jesc "${F[user]}")" "$(jesc "${F[pass]}")" "${F[port]:-443}" "$TLS")
			RESP=$(curl -s -m 25 -X POST -H "Content-Type: application/json" -d "$JSON" "$API/api/settings/miniserver" 2>/dev/null)
			if printf '%s' "$RESP" | grep -q '"ok"[: ]*true'; then
				N=$(printf '%s' "$RESP" | grep -oE '"nControls"[: ]*[0-9]+' | grep -oE '[0-9]+')
				MSG="<div class='ok'>✓ Verbunden – ${N:-0} Controls geladen.</div>"
			else
				ERR=$(printf '%s' "$RESP" | sed -nE 's/.*"error"[: ]*"([^"]*)".*/\1/p')
				[ -z "$RESP" ] && ERR="Container nicht erreichbar (läuft er? Start unten)."
				MSG="<div class='err'>Fehler: $(hesc "${ERR:-unbekannt}")</div>"
			fi ;;
	esac
fi

# --- aktuellen Status vom Container holen ---
ST=$(curl -s -m 5 "$API/api/settings" 2>/dev/null)
if [ -z "$ST" ]; then
	RUNNING=0; CONN=0; MHOST=""; MUSER=""; MPORT="443"; HASPASS=0
else
	RUNNING=1
	echo "$ST" | grep -q '"connected"[: ]*true' && CONN=1 || CONN=0
	MHOST=$(printf '%s' "$ST" | sed -nE 's/.*"host"[: ]*"([^"]*)".*/\1/p')
	MUSER=$(printf '%s' "$ST" | sed -nE 's/.*"user"[: ]*"([^"]*)".*/\1/p')
	MPORT=$(printf '%s' "$ST" | grep -oE '"port"[: ]*[0-9]+' | grep -oE '[0-9]+' | head -1)
	echo "$ST" | grep -q '"hasPass"[: ]*true' && HASPASS=1 || HASPASS=0
fi

if [ "$RUNNING" = 0 ]; then
	STATTXT="<b class='bad'>Container läuft nicht</b>"
elif [ "$CONN" = 1 ]; then
	STATTXT="<b class='good'>läuft · Miniserver verbunden</b>"
else
	STATTXT="<b class='warn'>läuft · noch kein Miniserver</b>"
fi

echo "Content-type: text/html; charset=utf-8"
echo ""
cat <<EOF
<!DOCTYPE html>
<html lang="de"><head><meta charset="utf-8">
<style>
  body{font-family:sans-serif;color:#e7e9ec;background:#16181c;margin:0;padding:18px}
  .card{background:#1c1f24;border:1px solid #2a2e35;border-radius:12px;padding:16px 18px;margin:0 0 16px;max-width:560px}
  h2{margin:0 0 10px;font-size:17px} label{display:block;font-size:13px;color:#9aa0a8;margin:10px 0 4px}
  input{width:100%;box-sizing:border-box;background:#16181c;border:1px solid #2a2e35;color:#e7e9ec;border-radius:8px;padding:9px 11px;font:inherit}
  .row{display:flex;gap:12px} .row>div{flex:1}
  .btn{border:none;border-radius:9px;padding:10px 18px;font:inherit;font-weight:600;cursor:pointer;background:#e0a24d;color:#1a1205;margin-top:12px}
  .btn.ghost{background:#212530;color:#e7e9ec;border:1px solid #2a2e35}
  a.btn{display:inline-block;text-decoration:none}
  .good{color:#52b881}.warn{color:#e0a24d}.bad{color:#e2695f}
  .ok{color:#52b881;margin:6px 0}.err{color:#e2695f;margin:6px 0}
  .chk{display:flex;align-items:center;gap:8px;margin-top:10px;font-size:13px;color:#9aa0a8}
  .chk input{width:auto}
</style></head><body>

<div class="card">
  <h2>LoxPanel &mdash; Status: ${STATTXT}</h2>
  ${MSG}
  <a class="btn" href="http://${HOST}:8099/config" target="_blank">Panels &amp; Kacheln öffnen ↗</a>
  <a class="btn ghost" href="http://${HOST}:8099/settings" target="_blank">Einstellungen öffnen ↗</a>
</div>

<div class="card">
  <h2>Miniserver-Zugang</h2>
  <form method="post">
    <input type="hidden" name="action" value="miniserver">
    <label>Host / IP</label><input name="host" value="$(hesc "$MHOST")" placeholder="192.168.1.50">
    <div class="row">
      <div><label>Benutzer</label><input name="user" value="$(hesc "$MUSER")" autocomplete="off"></div>
      <div><label>Port</label><input name="port" value="$(hesc "${MPORT:-443}")"></div>
    </div>
    <label>Passwort</label><input type="password" name="pass" placeholder="$([ "$HASPASS" = 1 ] && echo 'unverändert lassen' || echo 'Passwort eingeben')">
    <label class="chk"><input type="checkbox" name="tls"> Zertifikat prüfen (Gen2 selbstsigniert: aus)</label>
    <button class="btn" type="submit">Verbinden &amp; Speichern</button>
  </form>
</div>

<div class="card">
  <h2>Container</h2>
  <form method="post" style="display:inline"><input type="hidden" name="action" value="restart"><button class="btn ghost" type="submit">Neu starten / Update</button></form>
  <form method="post" style="display:inline"><input type="hidden" name="action" value="start"><button class="btn ghost" type="submit">Starten</button></form>
  <form method="post" style="display:inline"><input type="hidden" name="action" value="stop"><button class="btn ghost" type="submit">Stoppen</button></form>
</div>

</body></html>
EOF
