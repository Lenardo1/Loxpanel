// LoxPanel-Visu, Teil 6 von 12: Gesten wie auf den Loxone-Tastern, auch im Dunkeln.
// Die Teile laden nacheinander aus panel.html (script src), alle Funktionen sind global;
// was beim Laden ausgefuehrt wird, darf nur Funktionen frueherer Teile rufen.

// ---- Gesten wie auf den Loxone-Tastern (docs/TODO.md §9) ----
// Zwei Finger bedienen den Raum der Seite, auf der Hausuebersicht den der
// Raumkarte unter den Fingern: Mitte Licht (hoch/runter dimmt, quer
// vorige/naechste Stimmung, ein Tipp schaltet ein bzw. zur naechsten
// Stimmung), links Beschattung (hoch/runter auf/ab, quer Lamellen, Tipp
// beschatten), rechts Musik (hoch/runter Lautstaerke, quer Sender, Tipp
// Wiedergabe); Doppeltipp Raum verlassen, Dreifachtipp Haus aus. Die Visu erkennt nur
// die Geste - welche Bausteine sie trifft und welche Befehle gehen, entscheidet
// der Server ({t:'geste'}, App.geste). Touch-Events statt Pointer-Events: nur
// touchstart/touchmove mit preventDefault halten Scrollen und Klick an. Ein
// Finger bleibt, wie er war: Kacheln, Scrollen, Blaettern, "zurueck". Was
// geschieht, zeigt die ganze Flaeche (gesteBild): Licht und Musik fuellen sich
// von unten, die Jalousie faehrt von oben ins Bild, live mit ihrer Stellung.
const GESTE_SPALTEN=[1/3, 2/3];   // Grenzen links | Mitte | rechts als Anteil der Breite, wie am Taster
const GESTE_MINDESTWEG=0.04;      // ab diesem Weg (Anteil der Hoehe) wischen zwei Finger statt zu tippen;
                                  // quer zaehlt der Weg ueber die ganze Breite wie hoch/runter ueber die Hoehe
const GESTE_KNEIFEN=0.5;          // aendert sich der Fingerabstand um mehr als diesen Anteil des Wegs: Kneifen
const GESTE_TIPP_MS=400;          // laenger liegen zwei Finger fuer einen Tipp nicht
const GESTE_MEHRFACH_MS=350;      // so lange wartet ein Tipp auf den naechsten (Doppel-, Dreifachtipp)
const GESTE_TAKT_MS=150;          // beim Dimmen hoechstens so oft einen Zwischenwert schicken
const GESTE_KLICKSPERRE_MS=400;   // nach einer Geste so lange keinen Klick auf Kacheln durchlassen
const GESTE_ANZEIGE_MS=1500;      // Einblendung nach dem Ende so lange stehen lassen
const GESTE_FAHRT_STILL_MS=8000;  // faehrt die Jalousie, bleibt die Einblendung so lange ohne neue Stellung vom Server
// Symbol der Einblendung je Art (ICONS)
const GESTE_ICO={licht:'bulb', stimmung:'bulb', stimmungwechsel:'bulb', beschattung:'blind', beschatten:'blind',
                 lamellen:'lamelle', musik:'vol', sender:'music', wiedergabe:'music'};
const GESTE_TITEL={licht:'Licht', musik:'Musik', beschattung:'Beschattung', stimmung:'Licht',
                   stimmungwechsel:'Licht', beschatten:'Beschattung', lamellen:'Lamellen', wiedergabe:'Musik',
                   sender:'Musik', verlassen:'Raum verlassen', hausaus:'Haus aus'};
// Die drei Spalten von links (Grenzen GESTE_SPALTEN): was zwei Finger dort
// bedienen, ihr Symbol (Nacht-Uhr, Hilfe des Hinweises), die Art fuer
// hoch/runter (art), quer (quer, dabei: wert = Regler wie beim Dimmen, sonst
// ein Schritt vor/zurueck beim Loslassen) und Tipp (tipp), dazu die Hilfe.
// Umgesetzt wird es in App.geste().
const GESTE_ARTEN=[
  {spalte:'links', art:'beschattung', quer:'lamellen', querWert:true, tipp:'beschatten', ico:'blind',
   hilfe:'Hoch: auf · Runter: ab · Fährt sie, hält sie an · Quer: Lamellen · Tipp: beschatten'},
  {spalte:'mitte', art:'licht', quer:'stimmungwechsel', tipp:'stimmung', ico:'bulb',
   hilfe:'Hoch/runter: dimmen, ganz unten aus · Quer: vorige/nächste Stimmung · Tipp: an bzw. nächste Stimmung'},
  {spalte:'rechts', art:'musik', quer:'sender', tipp:'wiedergabe', ico:'music',
   hilfe:'Hoch: lauter · Runter: leiser · Quer: voriger/nächster Sender · Tipp: Play/Pause'}];
// Arten, die beim Wischen einen Wert stellen (Startwert vom Server, Zwischenwerte im Takt)
const GESTE_WERT_ARTEN=['licht', 'musik', 'lamellen'];
let gestenAn=false;        // kommt mit dem theme (Vorgaben/Ansicht)
let gestenHinweis=false;   // ... mit Hinweis-Symbol unter dem Kachelfeld
let geste=null;            // laufende Beruehrung mit zwei Fingern
let gesteSequenz=false;    // seit zwei Finger lagen, bis alle oben sind: kein Scrollen, kein "zurueck"
let gesteNach=null;        // Wisch zu Ende, bevor der Server den Startwert schickte
let gesteLetzte=null;      // zuletzt beendete Geste mit Wert: ihr gilt der Text, den der Server danach schickt
let gesteTipps=0, gesteTippT=null, gesteTippSpalte='', gesteTippKarte='';
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
// karte: Raum der Raumkarte unter den Fingern (Hausuebersicht), der Server prueft ihn
function gesteSenden(m, karte){
  if(verbindungGesperrt()){ verbindungZeigen(true); return false; }
  send({t:'geste', ...m, ...(karte ? {raum:karte} : {})}); return true; }
// Raumkarte der Hausuebersicht an dieser Stelle (data-hb "r:<Raum>"), sonst ''
function gesteKarte(x, y){
  if(!view || view.layout!=='haus') return '';
  const e=document.elementFromPoint(x, y), k=e && e.closest('[data-hb^="r:"]');
  return k ? k.dataset.hb.slice(2) : ''; }
function gesteKnoten(){
  let n=el('geste');
  if(n) return n;
  n=document.createElement('div'); n.id='geste'; n.className='geste hidden';
  const ebene=k=>'<div class="gs-ebene'+k+'"><div class="gs-titel"></div><div class="gs-ico"></div>'+
    '<div class="gs-wert"></div><div class="gs-sub"></div></div>';
  n.innerHTML='<div class="gs-fuell"></div><div class="gs-vorhang"></div><div class="gs-lamellen"></div>'+ebene('')+ebene(' gs-auf');
  // Ueber das ganze Display, nicht nur die Flaeche der Visu (.screen ist
  // hoechstens so gross wie ihre Kacheln und skaliert); die Nacht-Auflage
  // (#nightdim) liegt weiter darueber
  document.body.appendChild(n);
  return n;
}
// Einblendung ueber die ganze Flaeche (#geste). b: {art, titel, zahl | text,
// sub, form, wert, fehler}. form "pegel" fuellt von unten (Licht in --glow,
// Musik in --accent), "vorhang" faehrt von oben (Jalousie), "lamellen" kippt
// sie (0 waagrecht .. 100 senkrecht); wert 0..100 dazu. zahl steht gross mit
// "%", text als Wort. Zwei Ebenen Schrift: ueber der Fuellung die des Themes,
// auf ihr die zur Fuellfarbe, die Kante teilt auch die Ziffern. Im Dunkeln
// gedaempft auf Schwarz (leise). Die Farben rechnet der Server
// (theme_colors.geste_farben, --geste-*).
function gesteBild(b){
  const n=gesteKnoten(), form=b.form||'', w=Math.max(0, Math.min(100, +b.wert||0));
  n.className='geste'+(form?' '+form:'')+(b.art==='musik' || b.art==='sender' ? ' musik' : '')+
    (b.fehler?' fehl':'')+(imDunkeln()?' leise':'');
  n.querySelector('.gs-fuell').style.height=(form==='pegel' ? w : 0)+'%';
  n.querySelector('.gs-vorhang').style.height=(form==='vorhang' ? w : 0)+'%';
  n.style.setProperty('--gs-kippung', (form==='lamellen' ? w/100 : 0).toFixed(3));
  const ico=!b.fehler && GESTE_ICO[b.art], zahl=b.zahl!=null;
  n.querySelectorAll('.gs-ebene').forEach((e, i)=>{
    // die zweite Ebene nur auf der Fuellung; ohne Fuellung traegt die erste alles
    e.style.clipPath = form==='pegel' ? (i ? 'inset('+(100-w)+'% 0 0 0)' : 'inset(0 0 '+w+'% 0)')
                                      : (i ? 'inset(100% 0 0 0)' : 'none');
    e.querySelector('.gs-titel').textContent=b.titel||'';
    e.querySelector('.gs-ico').innerHTML=ico ? svg(ICONS[ico]) : '';
    const wt=e.querySelector('.gs-wert');
    wt.classList.toggle('zahl', zahl);
    if(zahl) wt.innerHTML=esc(String(b.zahl))+'<span class="gs-einheit"> %</span>';
    else wt.textContent=b.text||'';
    e.querySelector('.gs-sub').textContent=b.sub||'';
  });
  clearTimeout(n._t);
}
function gesteAusblenden(){ const n=el('geste'); if(!n) return; clearTimeout(n._t);
  n._t=setTimeout(()=>n.classList.add('hidden'), GESTE_ANZEIGE_MS); }
// Faehrt die Jalousie: stehen lassen, bis der Server das Ende meldet; bleibt
// er stumm (Verbindung weg), nach GESTE_FAHRT_STILL_MS ausblenden
function gesteFahrtHalten(){ const n=el('geste'); if(!n) return; clearTimeout(n._t);
  n._t=setTimeout(()=>n.classList.add('hidden'), GESTE_FAHRT_STILL_MS); }
function gesteTitel(art, raum){ return (GESTE_TITEL[art]||'')+(raum?' · '+raum:''); }
// Wert aus dem Weg seit Beginn des Wischens: die ganze Hoehe (hoch = mehr)
// bzw. quer die ganze Breite (nach rechts = mehr) sind 0 -> 100 %
function gesteWert(gs, p){
  const weg = gs.achse==='x' ? (p-gs.pWisch)/gs.w : (gs.pWisch-p)/gs.h;
  return Math.max(0, Math.min(100, gs.start+weg*100)); }
function gesteWertZeigen(gs){
  const w=Math.round(gs.wert), titel=gesteTitel(gs.art, gs.raum), form=gs.art==='lamellen' ? 'lamellen' : 'pegel';
  // Licht war aus: die Bewegung nach oben schaltet die Stimmung ein, gezeigt wird ihr Name
  if(gs.art==='licht' && gs.stimmung) return gesteBild({art:gs.art, titel, text: w>0 ? gs.stimmung : '▲ '+gs.stimmung, sub:gs.sub});
  if(gs.art==='licht' && w<=0) return gesteBild({art:gs.art, titel, text:'Aus', form, wert:0, sub:gs.sub});
  gesteBild({art:gs.art, titel, zahl:w, form, wert:gs.wert, sub:gs.sub});
}
function gesteWertSchicken(gs, phase){
  clearTimeout(gs.timer); gs.timer=null; gs.zuletzt=Date.now();
  gesteSenden({art:gs.art, phase, wert:Math.round(gs.wert)}, gs.karte);
}
function gesteBewegt(gs, p){
  if(gs.start==null) return;   // Startwert vom Server steht noch aus
  gs.wert=gesteWert(gs, p); gesteWertZeigen(gs);
  const warte=GESTE_TAKT_MS-(Date.now()-(gs.zuletzt||0));
  if(warte<=0) gesteWertSchicken(gs, 'wert');
  else if(!gs.timer) gs.timer=setTimeout(()=>{ if(geste===gs) gesteWertSchicken(gs, 'wert'); }, warte);
}
// Schritt-Gesten zeigen beim Wischen nur die Richtung: Beschattung hoch/runter,
// Stimmung und Sender quer
function gesteRichtungZeigen(gs){
  const vor=gs.dx>0;
  const sub = gs.art==='beschattung' ? (gs.dy<0 ? 'Loslassen: ganz auf' : 'Loslassen: ganz ab')
            : (gs.art==='sender' ? (vor ? 'Loslassen: nächster Sender' : 'Loslassen: voriger Sender')
                                 : (vor ? 'Loslassen: nächste Stimmung' : 'Loslassen: vorige Stimmung'));
  gesteBild({art:gs.art, titel:GESTE_TITEL[gs.art], text: gs.achse==='x' ? (vor ? '▶' : '◀') : (gs.dy<0 ? '▲' : '▼'), sub}); }
function gesteTipp(spalte, karte){
  gesteTipps++; if(gesteTipps===1){ gesteTippSpalte=spalte; gesteTippKarte=karte; }
  clearTimeout(gesteTippT);
  const los=()=>{ const n=gesteTipps, sp=gesteTippSpalte, k=gesteTippKarte; gesteTipps=0; gesteTippT=null;
    const art = n>=3 ? 'hausaus' : (n===2 ? 'verlassen' : (GESTE_ARTEN.find(a=>a.spalte===sp)||{}).tipp);
    if(art && gesteSenden({art}, k)) gesteBild({art, titel:GESTE_TITEL[art], text:'…'}); };
  // Mehr als drei gibt es nicht: der dritte Tipp loest sofort aus
  if(gesteTipps>=3) los(); else gesteTippT=setTimeout(los, GESTE_MEHRFACH_MS);
}
// Ende der Geste: der erste Finger ist oben (oder ein dritter kam dazu)
function gesteFertig(gs){
  geste=null; clearTimeout(gs.timer);
  if(GESTE_WERT_ARTEN.includes(gs.art)) gesteLetzte=gs;
  if(gs.wisch && !gs.abgebrochen){
    if(gs.art==='beschattung') gesteSenden({art:'beschattung', richtung: gs.dy<0 ? 'auf' : 'ab'}, gs.karte);
    else if(!GESTE_WERT_ARTEN.includes(gs.art))   // quer ein Schritt: Stimmung, Sender
      gesteSenden({art:gs.art, richtung: gs.dx>0 ? 'vor' : 'zurueck'}, gs.karte);
    else if(gs.start!=null){ gesteWertSchicken(gs, 'ende'); gesteAusblenden(); }
    else gesteNach=gs;          // der Startwert kommt noch: dann das Ende schicken
  } else if(!gs.wisch && !gs.abgebrochen && Date.now()-gs.t0<=GESTE_TIPP_MS){
    gesteTipp(gs.spalte, gs.karte);
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
  geste={x0:f.x, y0:f.y, d0:f.d, t0:Date.now(), h:r.height||window.innerHeight||1, w:r.width||window.innerWidth||1,
         dx:0, dy:0, spalte: anteil<GESTE_SPALTEN[0] ? 'links' : (anteil>GESTE_SPALTEN[1] ? 'rechts' : 'mitte'),
         karte:gesteKarte(f.x, f.y), achse:'y',
         art:'', wisch:false, abgebrochen:false, start:null, wert:null, raum:'', stimmung:'', timer:null, zuletzt:0};
  gesteSequenz=true;
  weckenAbsagen();   // im Dunkeln: zwei Finger wecken nicht
}, {passive:false});
gesteFlaeche.addEventListener('touchmove', e=>{
  if(gesteSequenz && e.cancelable) e.preventDefault();
  const gs=geste; if(!gs || gs.abgebrochen || e.touches.length!==2) return;
  const f=gesteFinger(e.touches), dx=f.x-gs.x0, dy=f.y-gs.y0, weg=Math.hypot(dx, dy);
  gs.dx=dx; gs.dy=dy;
  if(!gs.wisch){
    if(weg<GESTE_MINDESTWEG*gs.h) return;
    // Kneifen: keine Geste
    if(Math.abs(f.d-gs.d0)>GESTE_KNEIFEN*weg){ gs.abgebrochen=true; return; }
    const a=GESTE_ARTEN.find(x=>x.spalte===gs.spalte);
    gs.wisch=true; gs.achse = Math.abs(dx)>Math.abs(dy) ? 'x' : 'y';
    gs.pWisch = gs.achse==='x' ? f.x : f.y;
    clearTimeout(gesteTippT); gesteTipps=0;   // ein Wisch beendet eine Tippfolge
    gs.art = gs.achse==='x' ? a.quer : a.art;
    if(!GESTE_WERT_ARTEN.includes(gs.art)) gesteRichtungZeigen(gs);
    else if(gesteSenden({art:gs.art, phase:'start'}, gs.karte)) gesteBild({art:gs.art, titel:GESTE_TITEL[gs.art], text:'…'});
    else gs.abgebrochen=true;
    gs.pLetzt=gs.pWisch;
    return;
  }
  gs.pLetzt = gs.achse==='x' ? f.x : f.y;
  if(!GESTE_WERT_ARTEN.includes(gs.art)) gesteRichtungZeigen(gs);
  else gesteBewegt(gs, gs.pLetzt);
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
// Antwort des Servers: Startwert zum Dimmen, Text (Stimmung, "Raum verlassen"),
// Stellung der Jalousie oder Fehler
function gesteAntwort(msg){
  const gs = (geste && geste.art===msg.art) ? geste : ((gesteNach && gesteNach.art===msg.art) ? gesteNach : null);
  const titel=gesteTitel(msg.art, msg.raum);
  if(msg.fehler){
    if(gs) gs.abgebrochen=true;
    if(gs===gesteNach) gesteNach=null;
    gesteBild({art:msg.art, titel, text:msg.fehler, fehler:true}); gesteAusblenden(); return; }
  if(msg.phase==='start' && gs && gs.start==null){
    gs.start=+msg.wert||0; gs.raum=msg.raum||''; gs.stimmung=msg.text||'';
    gs.wert=(gs.pLetzt!=null && gs.pWisch!=null) ? gesteWert(gs, gs.pLetzt) : gs.start;   // Weg bis hierher zaehlt
    if(gs===gesteNach){ gesteNach=null; gesteWertSchicken(gs, 'ende'); gesteWertZeigen(gs); gesteAusblenden(); return; }
    gesteWertZeigen(gs); return; }
  // Jalousie nach einer Geste: der Vorhang folgt der Stellung, die der Server
  // aus dem Miniserver meldet (phase "wert"), bis die Fahrt endet ("ende")
  if(msg.wert!=null && (msg.art==='beschattung' || msg.art==='beschatten')){
    gesteBild({art:msg.art, titel, zahl:Math.round(+msg.wert), form:'vorhang', wert:+msg.wert, sub:msg.text||''});
    if(msg.phase==='ende') gesteAusblenden(); else gesteFahrtHalten();
    return; }
  // Text zu einer Geste mit Wert (waehrend des Wischens: Stimmung eingeschaltet,
  // Befehl fehlgeschlagen; nach dem Loslassen: was ankam): der Wert bleibt, der Text steht darunter
  const wg = gs || (gesteLetzte && gesteLetzte.art===msg.art ? gesteLetzte : null);
  if(wg && wg.start!=null && GESTE_WERT_ARTEN.includes(msg.art)){
    if(msg.text && msg.text!==wg.stimmung) wg.sub=msg.text;
    gesteWertZeigen(wg);
    if(!geste) gesteAusblenden();
    return; }
  gesteBild({art:msg.art, titel, text:msg.text||''});
  if(!geste) gesteAusblenden();
}

