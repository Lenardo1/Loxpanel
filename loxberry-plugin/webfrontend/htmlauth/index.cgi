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
use LoxBerry::System;
use LoxBerry::Web;

my $cgi     = CGI->new;
my $version = LoxBerry::System::pluginversion() // "";
my $api     = "http://localhost:8099";
my $ctl     = "REPLACELBPBINDIR/loxpanel-ctl.sh";
my $lbhost  = LoxBerry::System::get_localip() // "localhost";

sub h { my $s = shift; $s = "" unless defined $s; $s =~ s/&/&amp;/g; $s =~ s/</&lt;/g; $s =~ s/>/&gt;/g; $s =~ s/"/&quot;/g; return $s; }

# ---- POST verarbeiten (vor jeder Ausgabe) ----
my $msg = "";
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
    system($ctl, $1);
    $msg = "<div class='alert alert-success'>Aktion &bdquo;$1&ldquo; ausgef&uuml;hrt.</div>";
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
HTML

LoxBerry::Web::lbfooter();
