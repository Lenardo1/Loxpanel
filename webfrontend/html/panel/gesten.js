// LoxPanel-Visu, Teil 6 von 12: Gesten wie auf den Loxone-Tastern, auch im Dunkeln.
// Die Teile laden nacheinander aus panel.html (script src), alle Funktionen sind global;
// was beim Laden ausgefuehrt wird, darf nur Funktionen frueherer Teile rufen.

// ---- Gesten wie auf den Loxone-Tastern (docs/TODO.md §9) ----
// Zwei Finger bedienen den Raum der Seite: Mitte Licht (hoch/runter dimmt, ein
// Tipp schaltet ein bzw. zur naechsten Stimmung), links Beschattung, rechts
// Musik; Doppeltipp Raum verlassen, Dreifachtipp Haus aus. Die Visu erkennt nur
// die Geste - welche Bausteine sie trifft und welche Befehle gehen, entscheidet
// der Server ({t:'geste'}, App.geste). Touch-Events statt Pointer-Events: nur
// touchstart/touchmove mit preventDefault halten Scrollen und Klick an. Ein
// Finger bleibt, wie er war: Kacheln, Scrollen, Blaettern, "zurueck".
const GESTE_SPALTEN=[1/3, 2/3];   // Grenzen links | Mitte | rechts als Anteil der Breite, wie am Taster
const GESTE_MINDESTWEG=0.04;      // ab diesem Weg (Anteil der Hoehe) wischen zwei Finger statt zu tippen
const GESTE_KNEIFEN=0.5;          // aendert sich der Fingerabstand um mehr als diesen Anteil des Wegs: Kneifen
const GESTE_TIPP_MS=400;          // laenger liegen zwei Finger fuer einen Tipp nicht
const GESTE_MEHRFACH_MS=350;      // so lange wartet ein Tipp auf den naechsten (Doppel-, Dreifachtipp)
const GESTE_TAKT_MS=150;          // beim Dimmen hoechstens so oft einen Zwischenwert schicken
const GESTE_KLICKSPERRE_MS=400;   // nach einer Geste so lange keinen Klick auf Kacheln durchlassen
const GESTE_ANZEIGE_MS=1500;      // Einblendung nach dem Ende so lange stehen lassen
const GESTE_TITEL={licht:'Licht', musik:'Musik', beschattung:'Beschattung', stimmung:'Licht',
                   verlassen:'Raum verlassen', hausaus:'Haus aus'};
// Die drei Spalten von links (Grenzen GESTE_SPALTEN): was zwei Finger dort
// bedienen, ihr Symbol (Nacht-Uhr, Hilfe des Hinweises) und was hoch/runter
// und ein Tipp dort tun (Hilfe). Umgesetzt wird es in App.geste().
const GESTE_ARTEN=[
  {spalte:'links', art:'beschattung', ico:'blind', hilfe:'Hoch: auf · Runter: ab · Fährt sie, hält sie an'},
  {spalte:'mitte', art:'licht', ico:'bulb', hilfe:'Hoch/runter: dimmen, ganz unten aus · Tipp: an bzw. nächste Stimmung'},
  {spalte:'rechts', art:'musik', ico:'music', hilfe:'Hoch: lauter · Runter: leiser'}];
let gestenAn=false;        // kommt mit dem theme (Vorgaben/Ansicht)
let gestenHinweis=false;   // ... mit Hinweis-Symbol unter dem Kachelfeld
let geste=null;            // laufende Beruehrung mit zwei Fingern
let gesteSequenz=false;    // seit zwei Finger lagen, bis alle oben sind: kein Scrollen, kein "zurueck"
let gesteNach=null;        // Wisch zu Ende, bevor der Server den Startwert schickte
let gesteTipps=0, gesteTippT=null, gesteTippSpalte='';
let gesteKlickSperre=0;
const gesteFlaeche=document.querySelector('.screen');
function gesteErlaubt(){
  // Auch auf der Uhr-Seite (Gesten im Dunkeln): sie gelten der Seite darunter,
  // nach der Ruhe der Startseite
  if(!gestenAn || !view || !view.route) return false;
  if(view.route.view!=='tab' && view.route.view!=='group') return false;   // Detailseiten nicht
  if(g.classList.contains('scheme') || g.classList.contains('panel')) return false;   // Grundriss zoomt mit zwei Fingern
  return !gesteFlaeche.querySelector('.pinov, .menuov, .ghilfe');
}
// Fusszeile mit Hinweis-Symbol (raster.js fussH): Gesten und Hinweis an,
// waagerechte Seiten, kein schmaler Schirm. Das Raster zieht sie ab.
function hinweisFuss(){ return LoxRaster.fussH(gestenAn && gestenHinweis, seitenQuer(), vpSize().w, 1)>0; }
// Hilfe zum Hinweis-Symbol: was zwei Finger in welcher Spalte tun und was
// Doppel- und Dreifachtipp hier ausloesen (view.gestenHilfe vom Server)
function gestenHilfeZeigen(){
  const h=view && view.gestenHilfe; if(!h) return;
  gestenHilfeWeg();
  const grenzen=[0, ...GESTE_SPALTEN, 1], n=document.createElement('div');
  n.className='ghilfe'; n.id='gestenHilfe';
  n.innerHTML='<div class="gh-spalten">'+GESTE_ARTEN.map((a, i)=>
      '<div class="gh-sp" style="width:'+((grenzen[i+1]-grenzen[i])*100)+'%"><div class="gh-flaeche"><div class="gh-karte">'+
      svg(ICONS[a.ico])+'<div class="gh-titel">'+esc(GESTE_TITEL[a.art])+'</div><div class="gh-text">'+esc(a.hilfe)+'</div>'+
      '</div></div></div>').join('')+
    '</div><div class="gh-flaeche gh-unten"><div class="gh-tipps"><b>'+esc('Zwei Finger in '+h.raum)+'</b>'+
      '<span>'+esc(h.doppel)+'</span><span>'+esc(h.dreifach)+'</span></div></div>';
  n.addEventListener('click', e=>{ e.stopPropagation(); gestenHilfeWeg(); });
  gesteFlaeche.appendChild(n);
}
function gestenHilfeWeg(){ const n=el('gestenHilfe'); if(n) n.remove(); }
function gesteFinger(t){
  return {x:(t[0].clientX+t[1].clientX)/2, y:(t[0].clientY+t[1].clientY)/2,
          d:Math.hypot(t[0].clientX-t[1].clientX, t[0].clientY-t[1].clientY)}; }
function gesteSenden(m){
  if(verbindungGesperrt()){ verbindungZeigen(true); return false; }
  send({t:'geste', ...m}); return true; }
function gesteZeigen(titel, text, wert, fehler){
  let n=el('geste');
  if(!n){ n=document.createElement('div'); n.id='geste'; n.className='geste hidden';
    n.innerHTML='<div class="gs-titel"></div><div class="gs-wert"></div><div class="gs-balken"><i></i></div>';
    gesteFlaeche.appendChild(n); }
  n.querySelector('.gs-titel').textContent=titel||'';
  n.querySelector('.gs-wert').textContent=text||'';
  const b=n.querySelector('.gs-balken'); b.hidden=(wert==null);
  if(wert!=null) b.firstChild.style.width=Math.max(0,Math.min(100,wert))+'%';
  n.classList.toggle('fehl', !!fehler); n.classList.toggle('leise', imDunkeln());
  n.classList.remove('hidden'); clearTimeout(n._t);
}
function gesteAusblenden(){ const n=el('geste'); if(!n) return; clearTimeout(n._t);
  n._t=setTimeout(()=>n.classList.add('hidden'), GESTE_ANZEIGE_MS); }
function gesteTitel(art, raum){ return (GESTE_TITEL[art]||'')+(raum?' · '+raum:''); }
// Wert aus dem Weg seit Beginn des Wischens: die ganze Hoehe sind 0 -> 100 %
function gesteWert(gs, y){ return Math.max(0, Math.min(100, gs.start+(gs.yWisch-y)/gs.h*100)); }
function gesteWertZeigen(gs){
  const w=Math.round(gs.wert);
  const text=(gs.art==='licht' && gs.stimmung) ? (w>0 ? gs.stimmung : '▲ '+gs.stimmung)
           : (gs.art==='licht' && w<=0 ? 'Aus' : w+' %');
  gesteZeigen(gesteTitel(gs.art, gs.raum), text, gs.stimmung?null:gs.wert);
}
function gesteWertSchicken(gs, phase){
  clearTimeout(gs.timer); gs.timer=null; gs.zuletzt=Date.now();
  gesteSenden({art:gs.art, phase, wert:Math.round(gs.wert)});
}
function gesteBewegt(gs, y){
  if(gs.start==null) return;   // Startwert vom Server steht noch aus
  gs.wert=gesteWert(gs, y); gesteWertZeigen(gs);
  const warte=GESTE_TAKT_MS-(Date.now()-(gs.zuletzt||0));
  if(warte<=0) gesteWertSchicken(gs, 'wert');
  else if(!gs.timer) gs.timer=setTimeout(()=>{ if(geste===gs) gesteWertSchicken(gs, 'wert'); }, warte);
}
function gesteTipp(spalte){
  gesteTipps++; if(gesteTipps===1) gesteTippSpalte=spalte;
  clearTimeout(gesteTippT);
  const los=()=>{ const n=gesteTipps, sp=gesteTippSpalte; gesteTipps=0; gesteTippT=null;
    const art = n>=3 ? 'hausaus' : (n===2 ? 'verlassen' : (sp==='mitte' ? 'stimmung' : ''));
    if(art && gesteSenden({art})) gesteZeigen(GESTE_TITEL[art], '…'); };
  // Mehr als drei gibt es nicht: der dritte Tipp loest sofort aus
  if(gesteTipps>=3) los(); else gesteTippT=setTimeout(los, GESTE_MEHRFACH_MS);
}
// Ende der Geste: der erste Finger ist oben (oder ein dritter kam dazu)
function gesteFertig(gs){
  geste=null; clearTimeout(gs.timer);
  if(gs.wisch && !gs.abgebrochen){
    if(gs.art==='beschattung') gesteSenden({art:'beschattung', richtung: gs.dy<0 ? 'auf' : 'ab'});
    else if(gs.start!=null){ gesteWertSchicken(gs, 'ende'); gesteAusblenden(); }
    else gesteNach=gs;          // der Startwert kommt noch: dann das Ende schicken
  } else if(!gs.wisch && !gs.abgebrochen && Date.now()-gs.t0<=GESTE_TIPP_MS){
    gesteTipp(gs.spalte);
  } else if(gs.wisch){
    gesteAusblenden();          // abgebrochen (dritter Finger): Einblendung weg
  }
}
gesteFlaeche.addEventListener('touchstart', e=>{
  if(geste && e.touches.length>2){ geste.abgebrochen=true; gesteFertig(geste); return; }
  if(e.touches.length!==2 || geste || !gesteErlaubt()) return;
  // Scrollt der erste Finger schon, laesst sich das nicht mehr anhalten:
  // dann keine Geste statt einer halben
  if(!e.cancelable) return;
  e.preventDefault();
  const f=gesteFinger(e.touches), r=gesteFlaeche.getBoundingClientRect(), anteil=(f.x-r.left)/(r.width||1);
  geste={x0:f.x, y0:f.y, d0:f.d, t0:Date.now(), h:r.height||window.innerHeight||1, dy:0,
         spalte: anteil<GESTE_SPALTEN[0] ? 'links' : (anteil>GESTE_SPALTEN[1] ? 'rechts' : 'mitte'),
         art:'', wisch:false, abgebrochen:false, start:null, wert:null, raum:'', stimmung:'', timer:null, zuletzt:0};
  gesteSequenz=true;
  weckenAbsagen();   // im Dunkeln: zwei Finger wecken nicht
}, {passive:false});
gesteFlaeche.addEventListener('touchmove', e=>{
  if(gesteSequenz && e.cancelable) e.preventDefault();
  const gs=geste; if(!gs || gs.abgebrochen || e.touches.length!==2) return;
  const f=gesteFinger(e.touches), dx=f.x-gs.x0, dy=f.y-gs.y0, weg=Math.hypot(dx, dy);
  gs.dy=dy; gs.yLetzt=f.y;
  if(!gs.wisch){
    if(weg<GESTE_MINDESTWEG*gs.h) return;
    // Kneifen oder waagerecht: keine Geste (waagerecht ist nicht belegt)
    if(Math.abs(f.d-gs.d0)>GESTE_KNEIFEN*weg || Math.abs(dx)>Math.abs(dy)){ gs.abgebrochen=true; return; }
    gs.wisch=true; gs.yWisch=f.y;
    clearTimeout(gesteTippT); gesteTipps=0;   // ein Wisch beendet eine Tippfolge
    gs.art = GESTE_ARTEN.find(a=>a.spalte===gs.spalte).art;
    if(gs.art==='beschattung') gesteZeigen(GESTE_TITEL.beschattung, dy<0 ? '▲' : '▼');
    else if(gesteSenden({art:gs.art, phase:'start'})) gesteZeigen(GESTE_TITEL[gs.art], '…');
    else gs.abgebrochen=true;
    return;
  }
  if(gs.art==='beschattung') gesteZeigen(GESTE_TITEL.beschattung, dy<0 ? '▲' : '▼');
  else gesteBewegt(gs, f.y);
}, {passive:false});
function gesteLos(e){
  if(!gesteSequenz) return;
  if(e.cancelable) e.preventDefault();   // aus zwei Fingern wird kein Klick
  if(geste && e.touches.length<2) gesteFertig(geste);
  if(e.touches.length===0){ gesteSequenz=false; gesteKlickSperre=Date.now()+GESTE_KLICKSPERRE_MS; }
}
gesteFlaeche.addEventListener('touchend', gesteLos, {passive:false});
gesteFlaeche.addEventListener('touchcancel', gesteLos, {passive:false});
// ---- Gesten im Dunkeln (Stufe 5) ----
// Auf der Uhr-Seite und im abgedunkelten Nachtmodus weckt ein Finger wie bisher,
// zwei Finger sind eine Geste, die das Panel dunkel laesst (keine Uhr weg, kein
// Aufhellen). Ob ein zweiter kommt, steht erst kurz nach dem ersten fest: so
// lange wartet das Wecken. Wird der Finger vorher losgelassen, weckt er sofort.
// Ohne Gesten weckt jede Beruehrung wie bisher ohne Wartezeit. Dieselbe Zeit
// nimmt die LoxPanel-App (SchonerBeruehrung.WARTE_MS): Sie gibt Beruehrungen im
// Schoner erst an die Visu weiter, wenn ein zweiter Finger kommt.
const GESTE_ZWEITER_FINGER_MS=120;
let weckenWartet=null;     // {wecken, timer}: aufgeschobenes Wecken des ersten Fingers
function imDunkeln(){ return saverOn() || nachtGedimmt(); }
function gestenImDunkeln(e){ return gestenAn && !!e && e.pointerType==='touch' && imDunkeln() && gesteErlaubt(); }
function weckenAufschieben(wecken){
  if(weckenWartet) return;   // weiterer Finger derselben Beruehrung: es wartet schon
  weckenWartet={wecken, timer:setTimeout(weckenJetzt, GESTE_ZWEITER_FINGER_MS)}; }
function weckenJetzt(){ const w=weckenWartet; if(!w) return; weckenWartet=null; clearTimeout(w.timer); w.wecken(); }
function weckenAbsagen(){ if(weckenWartet){ clearTimeout(weckenWartet.timer); weckenWartet=null; } }
// Losgelassen, bevor die Zeit um ist: jetzt wecken. Capture und vor der Sperre
// der Uhr-Seite (saverGeste) registriert, damit sie das Loslassen schon schluckt.
window.addEventListener('pointerup', ()=>{ if(weckenWartet && !geste) weckenJetzt(); }, true);
// Ein Klick, den der Browser trotzdem aus der Geste macht, erreicht keine Kachel
document.addEventListener('click', e=>{
  if(Date.now()<gesteKlickSperre){ e.preventDefault(); e.stopPropagation(); } }, true);
// Antwort des Servers: Startwert zum Dimmen, Text (Stimmung, "Raum verlassen") oder Fehler
function gesteAntwort(msg){
  const gs = (geste && geste.art===msg.art) ? geste : ((gesteNach && gesteNach.art===msg.art) ? gesteNach : null);
  if(msg.fehler){
    if(gs) gs.abgebrochen=true;
    if(gs===gesteNach) gesteNach=null;
    gesteZeigen(gesteTitel(msg.art, msg.raum), msg.fehler, null, true); gesteAusblenden(); return; }
  if(msg.phase==='start' && gs && gs.start==null){
    gs.start=+msg.wert||0; gs.raum=msg.raum||''; gs.stimmung=msg.text||'';
    gs.wert=(gs.yLetzt!=null && gs.yWisch!=null) ? gesteWert(gs, gs.yLetzt) : gs.start;   // Weg bis hierher zaehlt
    if(gs===gesteNach){ gesteNach=null; gesteWertSchicken(gs, 'ende'); gesteWertZeigen(gs); gesteAusblenden(); return; }
    gesteWertZeigen(gs); return; }
  // Waehrend des Wischens (Stimmung eingeschaltet, Befehl fehlgeschlagen): Text, die Geste laeuft weiter
  if(gs && gs===geste && gs.wisch && msg.text){ gesteZeigen(gesteTitel(msg.art, msg.raum), msg.text); return; }
  gesteZeigen(gesteTitel(msg.art, msg.raum), msg.text||'');
  if(!geste) gesteAusblenden();
}

