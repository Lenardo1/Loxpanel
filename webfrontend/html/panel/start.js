// LoxPanel-Visu, Teil 12 von 12: Start: Uhren, Uhr-Seite, Verbindung.
// Die Teile laden nacheinander aus panel.html (script src), alle Funktionen sind global;
// was beim Laden ausgefuehrt wird, darf nur Funktionen frueherer Teile rufen.

setInterval(neuladenPruefen, 60*1000);
// Server-Ereignis, das Aufmerksamkeit braucht: Display an, Uhr weg, Timer neu.
function wake(){ screenOn(); nightWake(); hideSaver(); resetIdle(); }
setInterval(tickClock, 1000);
// Startseite = Uhr; ein Vorschaufenster (?entwurf=, Konfigurator "Geraet einrichten"
// und Editor) zeigt gleich den Inhalt - dort will jemand die Ansicht sehen, nicht die Uhr
if(ENTWURF) hideSaver(); else showSaver();
resetIdle();

connect();
