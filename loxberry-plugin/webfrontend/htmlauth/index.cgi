#!/usr/bin/perl
# LoxBerry-Plugin-Seite fuer LoxPanel – laeuft im LoxBerry-Rahmen (lbheader/
# lbfooter) und LoxBerry-Design (Bootstrap-Klassen).
#  - zeigt den Container-Status
#  - Miniserver-Zugang -> wird an den laufenden Container weitergereicht
#    (POST http://localhost:8099/api/settings/miniserver)
#  - Buttons zur vollen Oberflaeche (/config, /settings) und Container-Steuerung
use strict;
use warnings;
use CGI;
use JSON qw(encode_json decode_json);
use LWP::UserAgent;
use POSIX qw(strftime);
use LoxBerry::System;
use LoxBerry::Web;

my $cgi     = CGI->new;
my $version = LoxBerry::System::pluginversion() // "";
my $api     = "http://localhost:8099";
my $ctl     = "REPLACELBPBINDIR/loxpanel-ctl.sh";
my $log     = "REPLACELBPDATADIR/last_action.log";   # Verlauf der letzten Container-Aktion
my $bdir    = "REPLACELBPDATADIR/backups";           # Konfig-Sicherungen (ueberleben Plugin-Updates)
my $lbhost  = LoxBerry::System::get_localip() // "localhost";

sub h { my $s = shift; $s = "" unless defined $s; $s =~ s/&/&amp;/g; $s =~ s/</&lt;/g; $s =~ s/>/&gt;/g; $s =~ s/"/&quot;/g; return $s; }

# Eine Steuer-Aktion nicht-blockierend im Hintergrund starten (Ausgabe -> $log,
# das unten live angezeigt wird). Alle drei Standard-Fds umleiten, damit Apache
# die Anfrage sofort abschliesst (sonst Timeout/Fehler 500 bei laengeren Docker-
# Aktionen). Argumente muessen vorab geprueft/shell-sicher sein.
sub launch_bg {
    my ($label, @args) = @_;
    my $q = join(' ', map { "'$_'" } @args);
    my $sh = "{ date '+[%d.%m %H:%M:%S] $label gestartet'; $q; "
           . "date '+[%d.%m %H:%M:%S] $label abgeschlossen'; } "
           . "> '$log' 2>&1 < /dev/null &";
    system("/bin/bash", "-c", $sh);
}

# ---- POST verarbeiten (vor jeder Ausgabe) ----
my $msg = "";
my $refresh = 0;   # nach einer Aktion die Seite per GET nachladen (Live-Verlauf)
my $action = $cgi->param('action') // '';

if ($action eq 'miniserver') {
    my $data = {
        host       => scalar($cgi->param('host')) // '',
        user       => scalar($cgi->param('user')) // '',
        pass       => scalar($cgi->param('pass')) // '',
        port       => int((scalar($cgi->param('port')) || 443)),
        verify_tls => ($cgi->param('tls') ? JSON::true : JSON::false),
    };
    my $ua = LWP::UserAgent->new(timeout => 25);
    my $r  = $ua->post("$api/api/settings/miniserver",
        'Content-Type' => 'application/json', Content => encode_json($data));
    if ($r->is_success) {
        my $j = eval { decode_json($r->decoded_content) };
        if ($j && $j->{ok}) {
            $msg = "<div class='alert alert-success'>Verbunden &ndash; " . ($j->{nControls} // 0) . " Controls geladen.</div>";
        } else {
            $msg = "<div class='alert alert-danger'>Fehler: " . h($j ? ($j->{error} // 'unbekannt') : 'ungueltige Antwort') . "</div>";
        }
    } else {
        $msg = "<div class='alert alert-danger'>Container nicht erreichbar &ndash; l&auml;uft er? (unten &bdquo;Starten&ldquo;)</div>";
    }
}
elsif ($action =~ /^(start|stop|restart)$/) {
    my $act = $1;   # durch Regex begrenzt -> shell-sicher
    launch_bg("Aktion \"$act\"", $ctl, $act);
    $msg = "<div class='alert alert-info'>Aktion &bdquo;$act&ldquo; l&auml;uft &hellip; "
         . "bei einem Update wird das Image geladen (kann 1&ndash;2&nbsp;Min dauern). "
         . "Der Verlauf erscheint unten unter &bdquo;Letzte Aktion&ldquo; und aktualisiert sich automatisch.</div>";
    $refresh = 1;
}
elsif ($action eq 'backup') {
    launch_bg("Backup", $ctl, "backup");
    $msg = "<div class='alert alert-info'>Backup wird erstellt &hellip; Ergebnis unten unter &bdquo;Letzte Aktion&ldquo;.</div>";
    $refresh = 1;
}
elsif ($action eq 'restore') {
    my $file = scalar($cgi->param('file')) // '';
    $file =~ s{.*[\\/]}{};   # nur Basename, keine Pfad-Tricks
    if ($file =~ /^loxpanel-config-[\w.\-]+\.tar\.gz$/ && -f "$bdir/$file") {
        launch_bg("Wiederherstellen ($file)", $ctl, "restore", $file);
        $msg = "<div class='alert alert-info'>Wiederherstellung l&auml;uft &hellip; das Panel startet dabei neu. Verlauf unten.</div>";
        $refresh = 1;
    } else {
        $msg = "<div class='alert alert-danger'>Ung&uuml;ltiger oder unbekannter Backup-Name.</div>";
    }
}
elsif ($action eq 'delete_backup') {
    my $file = scalar($cgi->param('file')) // '';
    $file =~ s{.*[\\/]}{};
    if ($file =~ /^loxpanel-config-[\w.\-]+\.tar\.gz$/ && -f "$bdir/$file") {
        unlink "$bdir/$file";
        $msg = "<div class='alert alert-success'>Backup gel&ouml;scht: " . h($file) . "</div>";
    } else {
        $msg = "<div class='alert alert-danger'>Backup nicht gefunden.</div>";
    }
}

# ---- Status vom Container holen ----
my ($running, $conn, $mhost, $muser, $mport, $haspass) = (0, 0, '', '', 443, 0);
my $sr = LWP::UserAgent->new(timeout => 5)->get("$api/api/settings");
if ($sr->is_success) {
    $running = 1;
    my $j = eval { decode_json($sr->decoded_content) };
    if ($j) {
        $conn = $j->{connected} ? 1 : 0;
        my $m = $j->{miniserver} // {};
        $mhost = $m->{host} // ''; $muser = $m->{user} // '';
        $mport = $m->{port} // 443; $haspass = $m->{hasPass} ? 1 : 0;
    }
}
my $stat = !$running ? "<span style='color:#a94442'>Container l&auml;uft nicht</span>"
    : $conn ? "<span style='color:#3c763d'>l&auml;uft &middot; Miniserver verbunden</span>"
    : "<span style='color:#8a6d3b'>l&auml;uft &middot; noch kein Miniserver</span>";

my ($hh, $hu, $hp) = (h($mhost), h($muser), h($mport));
my $passph = $haspass ? "unver&auml;ndert lassen" : "Passwort eingeben";

# ---- Verlauf der letzten Aktion (Tail) ----
my ($logtail, $busy) = ("", 0);
if (open(my $lf, '<', $log)) {
    my @lines = <$lf>;
    close $lf;
    # "busy", solange die Abschluss-Zeile noch fehlt -> Seite pollt dann weiter.
    my $last = @lines ? $lines[-1] : '';
    $busy = ($last !~ /abgeschlossen/) ? 1 : 0;
    @lines = splice(@lines, -25) if @lines > 25;
    $logtail = h(join('', @lines));
}
# Waehrend eine Aktion laeuft (frisch angestossen ODER Log noch offen) die Seite
# per GET nachladen (kein erneutes POST -> keine Doppel-Aktion).
my $poll = ($refresh || $busy) ? 1 : 0;
my $refresh_html = $poll
    ? "<script>setTimeout(function(){location.replace(location.pathname);},4000);</script>"
    : "";

my $log_html = "";
if ($logtail ne "") {
    my $spin = $busy ? " &middot; l&auml;uft&hellip;" : "";
    $log_html = <<"LOGH";
<div class="panel panel-default">
  <div class="panel-heading">Letzte Aktion$spin</div>
  <div class="panel-body">
    <pre style="max-height:260px;overflow:auto;background:#1e1e1e;color:#d4d4d4;padding:10px;border-radius:6px;font-size:12px;line-height:1.45;white-space:pre-wrap">$logtail</pre>
    <a class="lpbtn lpgrey" href="#" onclick="location.replace(location.pathname);return false;">Aktualisieren</a>
  </div>
</div>
LOGH
}

# ---- Vorhandene Backups auflisten (neueste zuerst) ----
my @backups;
if (opendir(my $dh, $bdir)) {
    @backups = sort { $b cmp $a }
               grep { /^loxpanel-config-.*\.tar\.gz$/ } readdir($dh);
    closedir($dh);
}
my $blist = "";
for my $b (@backups) {
    my @st  = stat("$bdir/$b");
    my $kb  = @st ? int(($st[7] + 1023) / 1024) : 0;
    my $when= @st ? strftime("%d.%m.%Y %H:%M", localtime($st[9])) : "";
    my $hb  = h($b);
    $blist .= "<tr>"
        . "<td style='padding:5px 8px;font-family:monospace;font-size:12px'>$hb</td>"
        . "<td style='padding:5px 8px;color:#777;white-space:nowrap'>$when</td>"
        . "<td style='padding:5px 8px;color:#777;white-space:nowrap'>${kb}&nbsp;KB</td>"
        . "<td style='padding:5px 8px;white-space:nowrap'>"
          . "<form method='post' style='display:inline;margin:0' "
          . "onsubmit=\"return confirm('Diesen Stand wiederherstellen? Die aktuellen Panels werden ersetzt (der jetzige Stand wird vorher automatisch gesichert). Das Panel startet neu.');\">"
          . "<input type='hidden' name='action' value='restore'>"
          . "<input type='hidden' name='file' value='$hb'>"
          . "<button class='lpbtn lpblue' style='padding:5px 12px;font-size:13px' type='submit'>Wiederherstellen</button></form> "
          . "<form method='post' style='display:inline;margin:0' "
          . "onsubmit=\"return confirm('Dieses Backup l&#246;schen?');\">"
          . "<input type='hidden' name='action' value='delete_backup'>"
          . "<input type='hidden' name='file' value='$hb'>"
          . "<button class='lpbtn lpgrey' style='padding:5px 10px;font-size:13px' type='submit'>&#215;</button></form>"
        . "</td></tr>";
}
my $backups_html = $blist
    ? "<div style='overflow-x:auto'><table style='width:100%;border-collapse:collapse'>"
      . "<tr style='text-align:left;color:#999;font-size:12px'><th style='padding:4px 8px'>Datei</th>"
      . "<th style='padding:4px 8px'>Datum</th><th style='padding:4px 8px'>Gr&ouml;&szlig;e</th><th></th></tr>"
      . "$blist</table></div>"
    : "<p style='color:#777;margin:6px 0 0'>Noch keine Sicherung vorhanden.</p>";

# ---- Ausgabe im LoxBerry-Rahmen ----
LoxBerry::Web::lbheader("LoxPanel V$version", "https://github.com/Lenardo1/Loxpanel", "");

print <<"HTML";
<style>
  .lpbtn{display:inline-block;padding:11px 20px;border-radius:6px;text-decoration:none;
    font-weight:600;font-size:14px;border:none;cursor:pointer;text-align:center;box-sizing:border-box;line-height:1.4}
  .lpgreen{background:#5cb85c;color:#000 !important}        .lpgreen:hover{background:#4cae4c;color:#000 !important}
  .lpblue{background:#337ab7;color:#fff}         .lpblue:hover{background:#2e6da4;color:#fff}
  .lpgrey{background:#f2f2f2;color:#333;border:1px solid #ccc}  .lpgrey:hover{background:#e6e6e6;color:#333}
  .lprow{display:flex;gap:10px;flex-wrap:wrap;margin-top:6px}
  .lprow .lpbtn,.lprow form{flex:1;min-width:170px}
  .lprow form{margin:0}  .lprow form .lpbtn{width:100%}
</style>
<div class="panel panel-default">
  <div class="panel-heading"><b>Status:</b> $stat</div>
  <div class="panel-body">$msg</div>
</div>

<div class="panel panel-default">
  <div class="panel-heading">Miniserver-Zugang</div>
  <div class="panel-body">
    <form method="post" class="form-horizontal">
      <input type="hidden" name="action" value="miniserver">
      <div class="form-group">
        <label class="col-sm-3 control-label">Host / IP</label>
        <div class="col-sm-6"><input class="form-control" name="host" value="$hh" placeholder="192.168.1.50"></div>
      </div>
      <div class="form-group">
        <label class="col-sm-3 control-label">Benutzer</label>
        <div class="col-sm-6"><input class="form-control" name="user" value="$hu" autocomplete="off"></div>
      </div>
      <div class="form-group">
        <label class="col-sm-3 control-label">Passwort</label>
        <div class="col-sm-6"><input type="password" class="form-control" name="pass" placeholder="$passph"></div>
      </div>
      <div class="form-group">
        <label class="col-sm-3 control-label">Port</label>
        <div class="col-sm-3"><input class="form-control" name="port" value="$hp"></div>
      </div>
      <div class="form-group">
        <div class="col-sm-offset-3 col-sm-6"><div class="checkbox"><label>
          <input type="checkbox" name="tls"> Zertifikat pr&uuml;fen (Gen2 selbstsigniert: aus)
        </label></div></div>
      </div>
      <div class="form-group">
        <div class="col-sm-offset-3 col-sm-6"><button class="lpbtn lpblue" type="submit">Verbinden &amp; Speichern</button></div>
      </div>
    </form>
    <hr>
    <div class="lprow">
      <a class="lpbtn lpgreen" href="http://$lbhost:8099/config" target="_blank">Panels &amp; Kacheln &ouml;ffnen</a>
      <a class="lpbtn lpgreen" href="http://$lbhost:8099/settings" target="_blank">Settings &ouml;ffnen</a>
    </div>
  </div>
</div>

<div class="panel panel-default">
  <div class="panel-heading">Container &amp; Updates</div>
  <div class="panel-body">
    <div class="lprow">
      <form method="post"><input type="hidden" name="action" value="restart"><button class="lpbtn lpgrey" type="submit">Jetzt updaten / Neu starten</button></form>
      <form method="post"><input type="hidden" name="action" value="start"><button class="lpbtn lpgrey" type="submit">Starten</button></form>
      <form method="post"><input type="hidden" name="action" value="stop"><button class="lpbtn lpgrey" type="submit">Stoppen</button></form>
    </div>
  </div>
</div>

<div class="panel panel-default">
  <div class="panel-heading">Panels sichern &amp; wiederherstellen</div>
  <div class="panel-body">
    <p style="color:#777;margin-top:0">Sichert die komplette Konfiguration (Panels, Kacheln, Theme &amp; Miniserver-Zugang) als Archiv unter <code>$bdir</code>. Diese Sicherungen bleiben auch bei Plugin-Updates erhalten; nur die letzten 20 werden behalten.</p>
    <form method="post" style="margin-bottom:12px"><input type="hidden" name="action" value="backup"><button class="lpbtn lpgreen" type="submit">Backup jetzt erstellen</button></form>
    $backups_html
  </div>
</div>
$log_html
$refresh_html
HTML

LoxBerry::Web::lbfooter();
