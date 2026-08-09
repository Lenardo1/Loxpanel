<?php
/*
 * LoxHASP - Designer-Frontend (Phase 1)
 * Zeigt den aus LoxAPP3.json importierten Raum/Kategorie/Control-Baum.
 * Das eigentliche Zusammenklicken (Kachel-Zuordnung, Layout, Icon-Wahl)
 * folgt in Phase 4.
 */

require_once "loxberry_system.php";
require_once "loxberry_web.php";

$template_title = "LoxHASP - Designer";
$helplink = "https://github.com/"; // TODO: echte Doku-URL
$helptemplate = "help.html";

// $lbpdatadir / $lbpbindir werden von loxberry_system.php gesetzt.
$structure_file = "$lbpdatadir/structure.json";

LBWeb::lbheader($template_title, $helplink, $helptemplate);
?>
<style>
  .lox-toolbar { display:flex; gap:12px; align-items:center; margin:10px 0 18px; }
  .lox-room { border:1px solid #ccc; border-radius:10px; margin:10px 0; padding:12px 14px; }
  .lox-room h3 { margin:0 0 8px; }
  .lox-ctl { display:flex; justify-content:space-between; padding:6px 8px; border-top:1px solid #eee; }
  .lox-ctl .type { font-family:monospace; color:#666; font-size:.85em; }
  .lox-empty { padding:16px; background:#fff8e1; border:1px solid #ffe082; border-radius:8px; }
</style>

<div class="lox-toolbar">
  <form method="post" action="importer.php" style="margin:0">
    <button type="submit" name="action" value="import" class="ui-btn ui-shadow ui-corner-all">
      Struktur vom Miniserver importieren
    </button>
  </form>
</div>

<?php
if (!file_exists($structure_file)) {
    echo '<div class="lox-empty"><b>Noch keine Struktur importiert.</b><br>'
       . 'Fuehre den Importer aus (Button oben) oder auf der Shell: '
       . '<code>python3 ' . htmlspecialchars($lbpbindir) . '/importer.py</code></div>';
    LBWeb::lbfooter();
    exit;
}

$tree = json_decode(file_get_contents($structure_file), true);
if (!is_array($tree)) {
    echo '<div class="lox-empty">structure.json konnte nicht gelesen werden.</div>';
    LBWeb::lbfooter();
    exit;
}

echo '<p>Miniserver: <b>' . htmlspecialchars($tree["miniserver"] ?? "?") . '</b> &middot; '
   . count($tree["rooms"] ?? []) . ' Raeume</p>';

foreach (($tree["rooms"] ?? []) as $room) {
    echo '<div class="lox-room">';
    echo '<h3>' . htmlspecialchars($room["name"]) . ' '
       . '<small>(' . intval($room["controlCount"] ?? 0) . ')</small></h3>';
    foreach (($room["controls"] ?? []) as $c) {
        echo '<div class="lox-ctl">'
           . '<span>' . htmlspecialchars($c["name"]) . '</span>'
           . '<span class="type">' . htmlspecialchars($c["type"]) . '</span>'
           . '</div>';
    }
    echo '</div>';
}

LBWeb::lbfooter();
