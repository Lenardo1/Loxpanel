#!/usr/bin/perl
# LoxBerry-Plugin-Seite fuer LoxPanel – laeuft im LoxBerry-Rahmen (lbheader/
# lbfooter) und LoxBerry-Design (Bootstrap-Klassen).
#  - zeigt den Container-Status (gestoppt, Port belegt ...)
#  - Miniserver-Zugang -> wird an den laufenden Container weitergereicht
#    (POST http://localhost:<port>/api/settings/miniserver), aber nur, wenn
#    dort wirklich LoxPanel antwortet
#  - Buttons zur vollen Oberflaeche (/config, /settings) und Container-Steuerung
#  - Port am LoxBerry einstellen (loxpanel-ctl.sh port, loxpanel_plugin.cfg)
use strict;
use warnings;
use CGI;
use Encode qw(encode_utf8);
use JSON qw(encode_json decode_json);
use LWP::UserAgent;
use POSIX qw(strftime);
use LoxBerry::System;
use LoxBerry::Web;

my $cgi     = CGI->new;
my $version = LoxBerry::System::pluginversion() // "";
my $ctl     = "REPLACELBPBINDIR/loxpanel-ctl.sh";
my $log     = "REPLACELBPDATADIR/last_action.log";   # Verlauf der letzten Container-Aktion
my $bdir    = "REPLACELBPDATADIR/backups";           # Konfig-Sicherungen (pre-/postroot.sh nehmen sie ueber Plugin-Updates mit)
my $lbhost  = LoxBerry::System::get_localip() // "localhost";

sub h { my $s = shift; $s = "" unless defined $s; $s =~ s/&/&amp;/g; $s =~ s/</&lt;/g; $s =~ s/>/&gt;/g; $s =~ s/"/&quot;/g; return $s; }

# Eine Auskunft von loxpanel-ctl.sh (port, keep, zustand) als Zeilen. Was das
# Plugin einstellt, steht nur dort; das Widget fragt es ab.
sub ctl_auskunft {
    my @zeilen;
    if (-x $ctl && open(my $fh, '-|', $ctl, @_)) {
        @zeilen = <$fh>;
        close $fh;
    }
    chomp @zeilen;
    return @zeilen;
}

# Port am LoxBerry, unter dem LoxPanel laeuft (loxpanel_plugin.cfg, sonst der
# Standard des Skripts)
my ($port) = grep { /^\d+$/ } ctl_auskunft('port');
my $api    = defined $port ? "http://localhost:$port" : undef;

# Antwortet unter $api LoxPanel? -> Einstellungen (Hash) oder undef. Erkannt an
# /api/settings mit "miniserver" und "version" (api_settings in webvisu.py): Belegt
# ein anderes Programm den Port, bekommt es keine Zugangsdaten.
sub loxpanel_einstellungen {
    return undef unless $api;
    my $r = LWP::UserAgent->new(timeout => 5)->get("$api/api/settings");
    return undef unless $r->is_success;
    my $j = eval { decode_json($r->decoded_content) };
    return (ref($j) eq 'HASH' && ref($j->{miniserver}) eq 'HASH' && ref($j->{version}) eq 'HASH') ? $j : undef;
}

# Warum LoxPanel nicht antwortet, aus "loxpanel-ctl.sh zustand": (Text, Art der
# Meldung). Gestoppt und Port belegt nennen den Weg zurueck.
sub nicht_erreichbar {
    my %z = map { /^(\w+)=(.*)$/ ? ($1 => $2) : () } ctl_auskunft('zustand');
    my $p = h($z{port} // $port // '');
    return ("Port&nbsp;$p am LoxBerry ist belegt (" . h($z{belegt}) . ") &ndash; LoxPanel kann so nicht starten. "
          . "Unten unter &bdquo;Port am LoxBerry&ldquo; einen freien Port einstellen.", 'danger') if ($z{belegt} // '') ne '';
    return ("LoxPanel ist gestoppt (&bdquo;Stoppen&ldquo; am " . h($z{gestoppt}) . ") &ndash; startet wieder mit "
          . "&bdquo;Starten&ldquo; oder beim n&auml;chsten Neustart des LoxBerry.", 'warning') if ($z{gestoppt} // '') ne '';
    return ("Container l&auml;uft, LoxPanel antwortet aber (noch) nicht auf Port&nbsp;$p &ndash; "
          . "kurz nach dem Start normal, sonst &bdquo;Jetzt updaten / Neu starten&ldquo;.", 'warning') if ($z{laeuft} // '') eq '1';
    return ("Container nicht erreichbar &ndash; l&auml;uft er? (unten &bdquo;Starten&ldquo;)", 'danger');
}

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

# LoxBerry-Zugangsdaten robust auslesen: bevorzugt die dekodierte *_RAW-Variante,
# sonst die (moeglicherweise URL-kodierte) Standardvariante selbst dekodieren.
sub _lox_cred {
    my ($raw, $enc) = @_;
    return $raw if defined $raw && $raw ne '';
    $enc = '' unless defined $enc;
    $enc =~ s/\+/ /g;
    $enc =~ s/%([0-9A-Fa-f]{2})/chr(hex($1))/ge;
    return $enc;
}

# Port des Miniservers aus der LoxBerry-Konfiguration: bei "HTTPS bevorzugen"
# (PreferHttps) der HTTPS-Port, sonst der HTTP-Port. Das Schema waehlt der
# Server am Port (80 = HTTP, sonst HTTPS: _ms_https in webvisu.py).
# PreferHttps kommt je nach LoxBerry als JSON-Wahrheitswert oder als Text.
sub _lox_port {
    my ($m) = @_;
    my $https = $m->{PreferHttps};
    $https = ref($https) ? ($https ? 1 : 0)
           : (defined $https && $https =~ /^\s*(?:1|true|on|yes)\s*$/i ? 1 : 0);
    my $p = ($https && ($m->{PortHttps} // '') =~ /^\s*\d+\s*$/) ? $m->{PortHttps} : $m->{Port};
    return int($p || 443);
}

# Miniserver-Zugang an den Container weiterreichen und Ergebnis-HTML liefern.
# Antwort von /api/settings/miniserver: "error" ist ein fester Text, der Fehler
# des Miniservers steht getrennt in "fehler". "gespeichert" = Miniserver nicht
# erreichbar, Zugang trotzdem gespeichert -> Warnung statt Fehler. Fehlende
# Eingaben kommen als 400 mit JSON: der Container laeuft also.
# decode_json liefert Zeichen, die Seite geht aber ohne Kodierungsschicht als
# UTF-8-Bytes hinaus (der Text unten steht als Bytes im Skript, lbheader setzt
# nur charset=utf-8): die Texte des Servers deshalb selbst nach UTF-8, sonst
# kommt "Port ungueltig" als Latin-1 an.
sub apply_miniserver {
    my ($data) = @_;
    unless (loxpanel_einstellungen()) {
        my ($text, $art) = nicht_erreichbar();
        return "<div class='alert alert-$art'>Zugang nicht gesendet: $text</div>";
    }
    my $ua = LWP::UserAgent->new(timeout => 25);
    my $r  = $ua->post("$api/api/settings/miniserver",
        'Content-Type' => 'application/json', Content => encode_json($data));
    my $j = eval { decode_json($r->decoded_content) };
    if (ref($j) ne 'HASH') {
        return "<div class='alert alert-danger'>Fehler: ung&uuml;ltige Antwort</div>" if $r->is_success;
        return "<div class='alert alert-danger'>Container nicht erreichbar &ndash; l&auml;uft er? (unten &bdquo;Starten&ldquo;)</div>";
    }
    return "<div class='alert alert-success'>Verbunden &ndash; " . ($j->{nControls} // 0) . " Controls geladen.</div>"
        if $j->{ok};
    my $text = h(encode_utf8($j->{error} // 'unbekannt'));
    $text .= "<br><small>" . h(encode_utf8($j->{fehler})) . "</small>" if defined $j->{fehler} && $j->{fehler} ne '';
    return $j->{gespeichert} ? "<div class='alert alert-warning'>$text</div>"
                             : "<div class='alert alert-danger'>Fehler: $text</div>";
}

# ---- POST verarbeiten (vor jeder Ausgabe) ----
my $msg = "";
my $refresh = 0;   # nach einer Aktion die Seite per GET nachladen (Live-Verlauf)
my $action = $cgi->param('action') // '';

if ($action eq 'miniserver') {
    $msg = apply_miniserver({
        host       => scalar($cgi->param('host')) // '',
        user       => scalar($cgi->param('user')) // '',
        pass       => scalar($cgi->param('pass')) // '',
        port       => int((scalar($cgi->param('port')) || 443)),
        verify_tls => ($cgi->param('tls') ? JSON::true : JSON::false),
    });
}
elsif ($action eq 'fromlox') {
    # Miniserver-Zugang aus der zentralen LoxBerry-Konfiguration uebernehmen
    # (erster/niedrigster Miniserver). Admin_RAW/Pass_RAW sind die dekodierten
    # Zugangsdaten.
    my %ms = LoxBerry::System::get_miniservers();
    my $m;
    for my $k (sort { $a <=> $b } keys %ms) { $m = $ms{$k}; last; }
    my $user = $m ? _lox_cred($m->{Admin_RAW}, $m->{Admin}) : '';
    if ($m && ($m->{IPAddress} // '') ne '' && $user eq '') {
        $msg = "<div class='alert alert-danger'>In LoxBerry ist f&uuml;r den Miniserver kein Benutzer eingetragen (Hauptmen&uuml; &rarr; Miniserver).</div>";
    } elsif ($m && ($m->{IPAddress} // '') ne '') {
        $msg = apply_miniserver({
            host       => $m->{IPAddress},
            user       => $user,
            pass       => _lox_cred($m->{Pass_RAW},  $m->{Pass}),
            port       => _lox_port($m),
            verify_tls => JSON::false,
        });
    } else {
        $msg = "<div class='alert alert-danger'>In LoxBerry ist kein Miniserver konfiguriert (Hauptmen&uuml; &rarr; Miniserver).</div>";
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
elsif ($action eq 'port') {
    my $neu = scalar($cgi->param('lbport')) // '';
    $neu =~ s/^\s+|\s+$//g;
    if ($neu =~ /^\d{1,5}$/) {       # nur Ziffern -> shell-sicher, den Bereich prueft loxpanel-ctl.sh
        launch_bg("Port am LoxBerry ($neu)", $ctl, "port", $neu);
        $msg = "<div class='alert alert-info'>Port wird umgestellt &hellip; ein laufendes LoxPanel startet dabei neu. Verlauf unten.</div>";
        $refresh = 1;
    } else {
        $msg = "<div class='alert alert-danger'>&bdquo;" . h($neu) . "&ldquo; ist kein Port &ndash; nur Ziffern (1&ndash;65535).</div>";
    }
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
my $j = loxpanel_einstellungen();
if ($j) {
    $running = 1;
    $conn = $j->{connected} ? 1 : 0;
    my $m = $j->{miniserver};
    $mhost = $m->{host} // ''; $muser = $m->{user} // '';
    $mport = $m->{port} // 443; $haspass = $m->{hasPass} ? 1 : 0;
}
my $stat = $running
    ? ($conn ? "<span style='color:#3c763d'>l&auml;uft &middot; Miniserver verbunden</span>"
             : "<span style='color:#8a6d3b'>l&auml;uft &middot; noch kein Miniserver</span>")
    : "<span style='color:#a94442'>Container l&auml;uft nicht</span>";
# Laeuft LoxPanel nicht, steht der Grund im Status-Feld (ausser eine Aktion
# meldet gerade selbst etwas)
if (!$running && $msg eq '') {
    my ($text, $art) = nicht_erreichbar();
    $msg = "<div class='alert alert-$art'>$text</div>";
}

my ($hh, $hu, $hp) = (h($mhost), h($muser), h($mport));
my $lbport = h($port // '');
my $links = defined $port
    ? "<a class=\"lpbtn lpgreen\" href=\"http://$lbhost:$lbport/config\" target=\"_blank\">Panels &amp; Kacheln &ouml;ffnen</a>\n"
    . "      <a class=\"lpbtn lpgreen\" href=\"http://$lbhost:$lbport/settings\" target=\"_blank\">Settings &ouml;ffnen</a>"
    : "<p style='color:#a94442;margin:0'>Port am LoxBerry unbekannt &ndash; $ctl antwortet nicht.</p>";
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
# Wie viele Sicherungen behalten werden, legt nur loxpanel-ctl.sh fest (KEEP).
my ($keep) = ctl_auskunft('keep');
$keep //= '';
my $keep_html = $keep =~ /^\d+$/ ? " Behalten werden die letzten $keep." : "";
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
  .lpfields{display:flex;gap:10px;flex-wrap:wrap;margin-top:4px}
  .lpfields .lpf{display:flex;flex-direction:column;gap:3px;min-width:120px}
  .lpfields label{font-size:12px;color:#777;margin:0;font-weight:600}
  .lpfields .form-control{width:100%}
</style>
<div class="panel panel-default">
  <div class="panel-heading"><b>Status:</b> $stat</div>
  <div class="panel-body">$msg</div>
</div>

<div class="panel panel-default">
  <div class="panel-heading">Miniserver-Zugang</div>
  <div class="panel-body">
    <form method="post" id="msform">
      <input type="hidden" name="action" value="miniserver">
      <div class="lpfields">
        <div class="lpf" style="flex:2"><label>Host / IP</label><input class="form-control" name="host" value="$hh" placeholder="192.168.1.50"></div>
        <div class="lpf" style="flex:1.4"><label>Benutzer</label><input class="form-control" name="user" value="$hu" autocomplete="off"></div>
        <div class="lpf" style="flex:1.4"><label>Passwort</label><input type="password" class="form-control" name="pass" placeholder="$passph"></div>
        <div class="lpf" style="flex:.6;min-width:80px"><label>Port</label><input class="form-control" name="port" value="$hp"></div>
      </div>
      <p style="color:#777;font-size:12px;margin:7px 0 8px">Schema automatisch: <b>Port&nbsp;443</b> = HTTPS (Gen2), <b>Port&nbsp;80</b> = HTTP (Gen1). „Zertifikat pr&uuml;fen" nur bei g&uuml;ltigem Zertifikat aktivieren.</p>
      <div class="checkbox" style="margin:2px 0 12px"><label>
        <input type="checkbox" name="tls"> Zertifikat pr&uuml;fen (Gen2 selbstsigniert: aus)
      </label></div>
    </form>
    <div class="lprow" style="margin-top:0">
      <button class="lpbtn lpblue" type="submit" form="msform">Verbinden &amp; Speichern</button>
      <form method="post"><input type="hidden" name="action" value="fromlox"><button class="lpbtn lpgrey" type="submit">Aus LoxBerry &uuml;bernehmen</button></form>
    </div>
    <hr>
    <div class="lprow">
      $links
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
    <p style="color:#777;font-size:12px;margin:7px 0 0">&bdquo;Stoppen&ldquo; h&auml;lt LoxPanel bis &bdquo;Starten&ldquo; oder bis zum n&auml;chsten Neustart des LoxBerry an; die 5-Minuten-Pr&uuml;fung startet es so lange nicht.</p>
    <hr>
    <form method="post" id="portform">
      <input type="hidden" name="action" value="port">
      <div class="lpfields">
        <div class="lpf" style="flex:.6;min-width:110px"><label>Port am LoxBerry</label><input class="form-control" name="lbport" value="$lbport" inputmode="numeric"></div>
      </div>
    </form>
    <p style="color:#777;font-size:12px;margin:7px 0 8px">Unter diesem Port erreichen Oberfl&auml;che, Panels und die App LoxPanel. Belegt ihn ein anderes Plugin, hier einen freien eintragen; ein laufendes LoxPanel startet damit neu. Der Port bleibt bei Updates erhalten, Panels und App brauchen danach die neue Adresse.</p>
    <div class="lprow" style="margin-top:0">
      <button class="lpbtn lpgrey" type="submit" form="portform">Port &uuml;bernehmen</button>
    </div>
  </div>
</div>

<div class="panel panel-default">
  <div class="panel-heading">Panels sichern &amp; wiederherstellen</div>
  <div class="panel-body">
    <p style="color:#777;margin-top:0">Sichert die komplette Konfiguration (Panels, Kacheln, Theme &amp; Miniserver-Zugang) als Archiv unter <code>$bdir</code>. Plugin-Updates nehmen diese Sicherungen mit; gelingt das nicht, meldet LoxBerry es beim Update.$keep_html</p>
    <form method="post" style="margin-bottom:12px"><input type="hidden" name="action" value="backup"><button class="lpbtn lpgreen" type="submit">Backup jetzt erstellen</button></form>
    $backups_html
  </div>
</div>
$log_html
$refresh_html
HTML

LoxBerry::Web::lbfooter();
