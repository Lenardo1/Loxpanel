#!/bin/bash
# LoxBerry-Plugin-Widget: leitet auf die LoxPanel-Weboberflaeche (Port 8099)
# weiter. LoxPanel bringt seine eigene Konfig-/Einstellungen-Oberflaeche mit
# (/config und /settings), daher ist hier keine eigene UI noetig.
echo "Content-type: text/html; charset=utf-8"
echo ""
HOST=$(echo "${HTTP_HOST:-localhost}" | cut -d: -f1)
URL="http://${HOST}:8099/config"
cat <<EOF
<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta http-equiv="refresh" content="0; url=${URL}">
<title>LoxPanel</title>
<style>body{font-family:sans-serif;background:#16181c;color:#e7e9ec;display:grid;place-items:center;height:100vh;margin:0}
a{color:#e0a24d}</style>
</head>
<body>
<div style="text-align:center">
<p>LoxPanel wird geöffnet …</p>
<p>Falls nicht automatisch: <a href="${URL}">${URL}</a></p>
<p style="color:#9aa0a8;font-size:13px">Startet der Container gerade erst, kann es einen Moment dauern.</p>
</div>
</body>
</html>
EOF
