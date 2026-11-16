// LoxPanel-Visu, Teil 12 von 12: Start: Uhren, Uhr-Seite, Verbindung.
// Die Teile laden nacheinander aus panel.html (script src), alle Funktionen sind global;
// was beim Laden ausgefuehrt wird, darf nur Funktionen frueherer Teile rufen.

setInterval(neuladenPruefen, 60*1000);
// Server-Ereignis, das Aufmerksamkeit braucht: Display an, Uhr weg, Timer neu.
function wake(){ screenOn(); nightWake(); hideSaver(); resetIdle(); }
setInterval(tickClock, 1000);
// Alle 10 s: der App melden, dass die Seite lebt (steht sie, baut die App die
// Anzeige neu auf), und selbst pruefen, ob die Ruhezeit um ist - falls der
// einzelne Zeitgeber aus resetIdle verloren ging.
setInterval(()=>{
  try{ const n=window.LoxKioskNative; if(n && typeof n.lebt==='function') n.lebt(); }catch(e){}
  if(!ENTWURF && !saverOn() && Date.now()-letzteBedienung>SAVER_IDLE_MS+5000) nachRuhe();
}, 10000);
// Startseite = Uhr; ein Vorschaufenster (?entwurf=, Konfigurator "Geraet einrichten"
// und Editor) zeigt gleich den Inhalt - dort will jemand die Ansicht sehen, nicht die Uhr
if(ENTWURF) hideSaver(); else showSaver();
resetIdle();

connect();
