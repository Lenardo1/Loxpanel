// LoxPanel-Visu, Teil 5 von 12: Kachel-Darstellung, Raster und render(), Anlagenschema, Fenster, Wischen im Kachelfeld.
// Die Teile laden nacheinander aus panel.html (script src), alle Funktionen sind global;
// was beim Laden ausgefuehrt wird, darf nur Funktionen frueherer Teile rufen.

function tileVarStyle(it){
  const sv=[]; const ts=it.style||{};
  if(it.colorFixed){ sv.push('--ico:'+it.colorFixed); sv.push('--ico-fixed:'+it.colorFixed); }
  else if(it.color) sv.push('--ico:'+it.color);
  if(ts.bg) sv.push('background:'+ts.bg);
  if(ts.border) sv.push('border-color:'+ts.border);
  if(ts.txt){ sv.push('color:'+ts.txt); sv.push('--tile-txt:'+ts.txt); }
  if(ts.font) sv.push('font-family:'+ts.font);
  // Neuer Aufbau: Fett/Kursiv gelten auch fuer den Zustand, wenn er vorn steht
  if(ts.weight) sv.push('--tile-fw:'+ts.weight);
  if(ts.italic) sv.push('--tile-fst:italic');
  if(ts.ovFill!=null) sv.push('--ov-fill:'+ts.ovFill);
  if(ts.ovBord!=null) sv.push('--ov-bord:'+ts.ovBord);
  if(ts.ovBw!=null) sv.push('--ov-bw:'+ts.ovBw+'px');
  if(ts.tileBord!=null) sv.push('--tile-bord:'+ts.tileBord);
  if(ts.tileBw!=null) sv.push('--tile-bw:'+ts.tileBw+'px');
  if(ts.ringOp!=null) sv.push('--posring-op:'+ts.ringOp);
  if(ts.ringTrk!=null) sv.push('--posring-trk:'+ts.ringTrk);
  if(ts.ringW!=null) sv.push('--posring-w:'+ts.ringW);
  return sv.join(';');
}
function tileTone(it){ return it.tone==='good'?' good':(it.tone==='crit'?' crit':(it.on?' on':'')); }
// Neuer Kachel-Aufbau (.lx): Standard, ausser das Profil waehlt "classic". Die
// Listen-Ansicht behaelt ihren Aufbau.
function kachelNeu(){ return tileLayout!=='classic' && !(view && view.layout==='list'); }
// Zeile zum Namen. Zeigt die Kachel einen Messwert gross (it.big), wiederholt
// die Zeile ihn nicht (it.bigSub).
function subText(it){
  if(!kachelNeu()) return it.sublabel||'';
  const s=(it.big!=null && it.bigSub!=null) ? it.bigSub : (it.sublabel||'');
  // Breite Kachel (zwei Spalten): die Teile bleiben nebeneinander, dafuer hat
  // sie die Breite - untereinander kosteten sie auf einer 126-px-Kachel die
  // Hoehe und die Eng-Stufe kappte den zweiten Teil.
  if(it.w===2 && gridCols>=2) return s;
  return s.replace(/ · /g,'\n');   // Teile untereinander (white-space:pre-line)
}
// Zustand vorn: der Zustand steht gross, der Name klein darunter. Nicht bei
// Kacheln, die direkt schalten (dort zeigt die Hervorhebung den Zustand) -
// ausser mit Kachel-Set, dort steht auch "An"/"Aus" vorn -, und nicht, wenn
// die Zeile nur beschreibt (it.subInfo, etwa "Tuersprechanlage").
function zustandVorn(it){ return kachelNeu() && (!it.cmd || !!kachelAufbau) && !it.subInfo && !!subText(it); }
// Klassen des neuen Aufbaus fuer render() und updateGrid(): Zustand vorn (zv),
// zweite Zeile ist nur eine Beschreibung (bi, weicht in enger Kachel zuerst),
// Messwert an Stelle des Symbols (bigk)
function aufbauKlassen(it){
  if(!kachelNeu()) return '';
  const bigk=it.big!=null ? ' bigk' : '';   // Messwert an Stelle des Symbols (Aufbau "kreis": breite Kachel)
  if(kachelAufbau==='mitte') return bigk;   // "mitte" ordnet seine Texte selbst (kachelTexte)
  return (zustandVorn(it)?' zv':'')+(it.subInfo && subText(it)?' bi':'')+bigk;
}
// Texte der Kachel fuer render() und updateGrid(): Haupttext (.name) und
// Zweitzeile (.sub). Aufbau "mitte" (Kachel-Set): Haupttext ist der Zustand
// (neben einem Messwert der, den der Server dazu nennt: "Soll 22,0°"), sonst
// der Name; die Zweitzeile nennt "Name · Raum" ohne den Teil, der schon
// Haupttext ist. Beschreibt die Zeile nur (subInfo), bleibt der Name vorn.
function kachelTexte(it){
  const sub=subText(it);
  if(kachelAufbau!=='mitte' || !kachelNeu()) return {name:it.label, sub:sub};
  const zustand=(!it.subInfo && sub) ? sub : '';
  const zweit=zustand ? [it.label, it.room] : [sub ? sub.replace(/\n/g,' · ') : '', it.room];
  // jeder Teil einmal: heisst die Kachel wie ihr Raum, steht er nicht doppelt da
  return {name:zustand||it.label, sub:[...new Set(zweit.filter(Boolean))].join(' · ')};
}
// Messwert: ganze Zahl gross, Nachkommastellen und Einheit klein ("25" ",4°")
function bigHtml(v){ const m=/^(-?\d+)(.*)$/.exec(String(v)); return m ? esc(m[1])+'<small>'+esc(m[2])+'</small>' : esc(v); }
// Positionsring: EINE Quelle fuer Vollrender und In-place-Patch. Vorher stand
// der Umfang zweimal als Zahl im Render-Zweig; sobald der Patch dazukam, waere
// er die dritte Stelle gewesen, an der sich derselbe Wert aendern muss.
const RING_U = 289.03;                      // Umfang bei r=46 im viewBox 0..100
function ringPos(it){
  return (typeof it.pos === 'number' && isFinite(it.pos))
    ? Math.max(0, Math.min(100, it.pos)) : null;
}
function ringDash(posv){ return (posv/100*RING_U).toFixed(2)+' '+RING_U; }
// Live-Update der Kachel-Ansicht OHNE Neuaufbau: aktualisiert nur die
// veraenderlichen Teile (Zustand/Farben/Sublabel/Steuer-Icons) der bestehenden
// Kacheln. Verhindert das Flackern (Icons/Cover werden nicht neu geladen).
// Gibt false zurueck, wenn sich die Struktur geaendert hat -> voller render().
// Positionsring live nachziehen (Rollladen/Tor/Fenster/Dimmer): updateGrid()
// baute den Ring frueher NICHT mit -> der Bogen fror auf dem Stand vom letzten
// vollen Render ein (Text sagte 95 %, Ring zeigte noch 20 %). Gibt false zurueck,
// wenn sich die Ring-STRUKTUR aendert (Ring kommt/geht) -> voller render().
function updateTileRing(n,it){
  const posv=ringPos(it);
  const ring=n.querySelector('.posring');
  if(posv===null) return !ring;          // Ring war da, ist aber weg -> Struktur
  if(!ring) return false;                // Ring soll da sein, ist aber nicht -> Struktur
  const grp=ring.querySelector('g'); let val=ring.querySelector('.val');
  if(posv>0){
    if(!val){ val=document.createElementNS('http://www.w3.org/2000/svg','circle');
      val.setAttribute('class','val'); val.setAttribute('cx','50'); val.setAttribute('cy','50'); val.setAttribute('r','46');
      if(grp) grp.appendChild(val); }
    const d=ringDash(posv); if(val.getAttribute('stroke-dasharray')!==d) val.setAttribute('stroke-dasharray',d);
  } else if(val){ val.remove(); }        // 0 %: nur die Spur bleibt
  return true;
}
function updateGrid(items){
  const g=el('grid');
  if(g.classList.contains('panel')) return false;
  if(g.classList.contains('lx')!==kachelNeu()) return false;   // Kachel-Aufbau gewechselt
  if((g.dataset.aufbau||'')!==kachelAufbau) return false;       // ... oder der des Kachel-Sets
  const quer=seitenQuer();
  if(g.classList.contains('hpages')!==quer) return false;      // Blaetterrichtung gewechselt (Drehen)
  const nodes=[...g.querySelectorAll('.tile[data-id]')];
  if(nodes.length!==items.length || !nodes.length) return false;
  const groessen=items.map(kachelGroesse), lage=rasterLage(groessen, gridCols, gridRows);
  const seiteVon=i=>Math.floor(lage.zeile[i]/Math.max(1,gridRows));
  const byId=new Map(nodes.map(n=>[n.dataset.id, n]));
  if(quer){
    // Waagerechte Seiten: dieselben Kacheln auf denselben Seiten in derselben
    // Reihenfolge je Seite (der dichte Fluss haengt an der Reihenfolge). Im
    // DOM steht eine schmale Kachel, die in eine Luecke rueckte, vor einer
    // breiten auf der naechsten Seite - darum je Seite vergleichen.
    const pages=[...g.querySelectorAll('.page')];
    if(pages.length!==lage.seiten) return false;
    const soll=pages.map(()=>[]);
    items.forEach((it,i)=>soll[seiteVon(i)].push(String(it.id)));
    for(let k=0;k<pages.length;k++){
      const ist=[...pages[k].querySelectorAll('.tile[data-id]')].map(n=>n.dataset.id);
      if(ist.join('\n')!==soll[k].join('\n')) return false;
    }
  } else {
    for(let i=0;i<items.length;i++){ if(String(items[i].id)!==nodes[i].dataset.id) return false; }
  }
  const snapAt=i=> quer ? false : (view.layout==='list' ? (i%4===0) : lage.snaps.has(i));
  g._zeile=lage.zeile;
  g.classList.toggle('snapy', !quer && (view.layout==='list' ? items.length>4 : lage.seiten>1));
  let ok=true;
  items.forEach((it,i)=>{
    const n=quer ? byId.get(String(it.id)) : nodes[i];
    n._it=it;
    // Klassen, die tastenEinpassen()/fitTile()/paintSpark() nach dem Messen
    // setzen, bleiben stehen: sonst verloere eine enge Kachel bei jedem
    // Zustandswechsel, der ihren Text nicht aendert (Player: Pause), ihre Stufen.
    const cls='tile'+tileTone(it)+aufbauKlassen(it)+kachelKlassen(groessen[i])+spielerKlasse(it, groessen[i])+(snapAt(i)?' snap':'')+
      [...n.classList].filter(c=>c.startsWith('spark')||c==='ohnetasten'||c==='ohnecover'||c==='spbreit'||/^(eng|kst)\d$/.test(c)).map(c=>' '+c).join('');
    // Spieler-Spalte: kommt sie oder ihr Cover hinzu oder fallen sie weg, aendert
    // sich der Aufbau der Kachel; sonst nur das Bild nachziehen
    const spieler=spielerKachel(it, groessen[i]), coverEl=n.querySelector('.tcover');
    if(spieler!==n.classList.contains('spieler') || (spieler && !!it.cover!==!!coverEl)) ok=false;
    else if(coverEl && coverEl.getAttribute('src')!==it.cover) coverEl.setAttribute('src', it.cover);
    if(n.className!==cls) n.className=cls;
    // Style der Kachel (Farben, Rahmen): verglichen mit dem zuletzt gesetzten
    // Text, nicht dem Attribut - dort steht auch der eigene Faktor der Kachel
    // (--ks aus tastenEinpassen), den der Browser beim Setzen mit umschreibt.
    const stStr=kachelStil(it, lage, groessen, i, quer);
    if(n._stStr!==stStr){ n.setAttribute('style',stStr); n._stStr=stStr; if(n._kt) n.style.setProperty('--ks', String(n._kt)); }
    const body=n.querySelector('.body');
    if(body){ let subEl=body.querySelector('.sub'); const tx=kachelTexte(it), sub=tx.sub;
      const nameEl=body.querySelector('.name');   // Aufbau "mitte": dort steht der Zustand
      if(nameEl && nameEl.textContent!==tx.name) nameEl.textContent=tx.name;
      if(sub){ if(!subEl){ subEl=document.createElement('div'); subEl.className='sub'; body.appendChild(subEl); }
        if(subEl.textContent!==sub) subEl.textContent=sub; }
      else if(subEl){ subEl.remove(); } }
    // Messwert an Stelle des Symbols: kommt oder geht er, aendert sich der Kopf
    const bigEl=n.querySelector('.bigv'), mitBig=kachelNeu() && it.big!=null;
    if(!!bigEl!==mitBig) ok=false;
    else if(bigEl){ const h=bigHtml(it.big); if(bigEl.innerHTML!==h) bigEl.innerHTML=h; }
    if(it.controls){ const tbs=n.querySelectorAll('.tctrls .tb');
      if(tbs.length===it.controls.length) it.controls.forEach((c,ci)=>{ const b=tbs[ci]; if(!b) return;
        b._cmd=c.cmd; b._secured=it.secured;
        const nh=svgF(ICONS[c.icon]||ICONS.info); if(b.innerHTML!==nh) b.innerHTML=nh; });
      tastenEinpassen(n); }
    fitTile(n);
    if(!updateTileRing(n,it)) ok=false;   // Positionsring live nachziehen
    // Mini-Verlauf: dazu oder weg -> neu aufbauen, sonst nur bei Aenderung neu zeichnen
    const spEl=n.querySelector('.tspark'), bdEl=n.querySelector(kachelNeu()?'.tsline':'.tsbadge'), bd=it.spark&&it.spark.badge;
    if(!!it.spark!==!!spEl || !!bd!==!!bdEl) ok=false;
    else if(spEl){ paintSpark(spEl,it.spark);
      n.querySelectorAll('.tsbadge,.tsline').forEach(e=>{ if(e.textContent!==bd) e.textContent=bd; }); }
  });
  return ok;
}
// "Screen fuellen" (kein Widget in Pane 2): die KACHELZAHL wird verdoppelt
// (GLEICHE Kachelgroesse, nur mehr Kacheln), unabhaengig vom Zoom ("Bildschirm
// fuellen"). Quer nach rechts: aus 2x2 wird 2x2|2x2 = 4x2 (2-Pane-Tablet).
// Hochkant nach unten: aus 2x2 wird 2x4 - aber nur, wenn das Raster dadurch
// besser zur Fensterform passt (Seitenverhaeltnis Spalten:Zeilen naeher am
// Fenster). Die Grenze liegt beim geometrischen Mittel zwischen einfachem und
// doppeltem Raster: 2x2, 3x2 und 3x3 werden auf einem Hochkant-Tablet
// verdoppelt, 2x3 ist schon ein Hochformat-Raster und bleibt. Das quadratische
// 4"-Panel bleibt in jedem Fall bei seinem Raster.
// Sichtbare Flaeche. innerWidth/innerHeight sind beim Start einer iOS-Web-App
// (Lesezeichen "Als Web-App oeffnen") und in manchen Kiosk-Browsern kurz 0 oder
// die Groesse des Safari-Fensters; dann rechnete das Raster 1 Zeile (Kacheln
// ueber den Schirm, "Uhr-Kachel") und blieb so haengen, weil kein resize
// mehr kam. Darum: innerWidth/innerHeight, sonst der sichtbare Viewport des
// Geraets, sonst das Wurzelelement. Null gibt es nicht mehr.
function vpSize(){
  let w=window.innerWidth, h=window.innerHeight;
  const vv=window.visualViewport, de=document.documentElement;
  if(!(w>0)||!(h>0)){ if(vv&&vv.width>0&&vv.height>0){ w=vv.width; h=vv.height; }
    else { w=de.clientWidth; h=de.clientHeight; } }
  return {w:Math.max(1,w), h:Math.max(1,h)};
}
// Schmaler Schirm (raster.js SCHMAL_UNTER): .schmal am Kasten. Ein
// Kachel-Set nimmt dort seine Masse mit "-schmal" (CSS --k-*), die
// Seitenleiste zeigt nur Symbole. Vor jeder Rasterrechnung, weil Leiste,
// Rahmen und Abstaende daran haengen.
// Niedrig (breit genug, Hoehe darunter, raster.js leisteSchmal): .niedrig,
// dort nimmt nur die Tab-Leiste die "-schmal"-Masse.
function schmalEinrichten(){
  const sc=document.querySelector('.screen'); if(!sc) return;
  const {w,h}=vpSize(), s=LoxRaster.schmal(w);
  sc.classList.toggle('schmal', s);
  sc.classList.toggle('niedrig', !s && LoxRaster.leisteSchmal(w, h));
  // Leiste und Pille mit der Hoehe (Set nennt --leiste-voll-ab), dieselbe
  // Rechnung wie der Konfigurator; sonst gelten die Regeln am Kasten
  for(const [mass, k] of LoxRaster.LEISTE_ANTEILIG.map(n=>[n, n==='--tabs-hoehe'?'--k-tabs-h':'--k-pille-h'])){
    if(kachelMasse['--leiste-voll-ab'] && kachelMasse[mass] && !s) sc.style.setProperty(k, LoxRaster.leisteMass(kachelMasse, mass, w, h, 0)+'px');
    else sc.style.removeProperty(k);
  }
}
function rasterFuer(widget){
  const {w,h}=vpSize();
  if(gridAuto){ const r=autoRaster(widget); return [r.cols, r.rows]; }
  // Split aus -> nie Verdopplung (raster.js, wie im Assistenten vorgerechnet)
  return LoxRaster.festesRaster({cols:profCols, rows:profRows, w:w, h:h, split:themeSplit, widget:widget});
}
// Automatisches Raster (Profil "Automatisch", Tablet): Spalten und Zeilen aus
// der freien Flaeche und der Zielgroesse einer Kachel (gridAuto, vom Server).
// Ein groesserer Schirm zeigt mehr Kacheln statt groesserer, die Zeilen machen
// die Kacheln etwa quadratisch. Ein Widget (Pane 2) belegt ganze Kachelspalten
// (quer) bzw. -zeilen (hochkant): paneCols davon, wenn das Profil eine feste
// Breite nennt, sonst rund den Anteil paneShare (beides vom Server, mit der
// theme-Nachricht); so bleiben die Kacheln mit und ohne Widget gleich gross.
// k und p sind die Anteile von Kacheln und Widget an der Aufteilung (CSS
// --auto-k/--auto-p).
// Die Automatik kennt die Kacheln der Seite (_lastBreiten: 1 oder 2 Spalten
// je Kachel, aus render()): passen alle auf eine Seite, wachsen die Kacheln,
// bis die Seite voll ist, hoechstens auf gridGrow * Zielgroesse
// (KACHEL_WACHSEN vom Server, mit der theme-Nachricht). Mehr Kacheln als
// Platz -> Zielgroesse und Blaettern wie bisher. Neben einem Widget mit
// Anteil wachsen sie nicht: mit weniger Spalten liesse sich der Anteil nicht
// halten (2 von 5 Spalten sind 40 %, 2 von 4 schon 50 %). Mit fester Breite
// (paneCols) wachsen sie, das Widget bleibt dabei so viele Kachelspalten breit
// und waechst mit.
// Umgekehrt (Punkt 16): bleibt bei mehreren Seiten die letzte mehr als ein
// Drittel leer, werden die Kacheln kleiner, sobald das eine Seite spart -
// hoechstens so weit unter die Zielgroesse, wie sie darueber wachsen duerfen
// (Zielgroesse / gridGrow). iPad quer mit 26 belegten Zellen: 6 x 4 gaebe
// 24 + 2, mit 7 Spalten passt alles auf eine Seite. Wie das Wachsen nur ohne
// Widget oder neben einem mit fester Breite.
let _lastBreiten = [];
// Lage der Kacheln im Raster, wie CSS sie setzt (grid-auto-flow: row dense):
// je Kachel ihre Zeile. Breite Kacheln (w = 2) belegen zwei Spalten, eine
// Luecke davor fuellt die naechste schmale Kachel. Daraus die Seitenzahl und
// die Rastpunkte (jede Kachel in der ersten Zeile einer Seite).
function rasterLage(groessen, cols, rows){ return LoxRaster.rasterLage(groessen, cols, rows); }
// Groesse einer Kachel im Raster (Punkt 10): breit nur, wo zwei Spalten da sind,
// hoch (immer auch breit) nur, wo zwei Zeilen da sind; Listen kennen beides nicht
function kachelGroesse(it){
  if(view && view.layout==='list') return {w:1, h:1};
  return LoxRaster.groesse({w:it.w===2?2:1, h:it.h===2?2:1}, gridCols, gridRows);
}
function kachelKlassen(g){ return (g.w===2?' w2':'')+(g.h===2?' h2':''); }
// Breite Kachel mit Tasten im neuen Aufbau: rechts die Spieler-Spalte (Cover
// und Tasten, CSS .spieler), nicht in der Liste und nicht im klassischen Aufbau
function spielerKachel(it, g){ return kachelNeu() && view.layout!=='list' && g.w===2 && !!(it.controls && it.controls.length); }
function spielerKlasse(it, g){ return spielerKachel(it, g) ? ' spieler' : ''; }
// Feste Stelle einer Kachel, sobald die Seite eine hohe traegt (lage.hoch): der
// dichte Fluss des Browsers kennt die Seitengrenzen nicht und zoege eine hohe
// Kachel in der letzten Zeile ueber zwei Seiten. Waagerecht zaehlt die Zeile
// in ihrer Seite.
function kachelPlatz(lage, groessen, i, quer){
  if(!lage.hoch) return '';
  const g=groessen[i], z=quer ? lage.zeile[i]%Math.max(1,gridRows) : lage.zeile[i];
  return 'grid-row:'+(z+1)+' / span '+g.h+';grid-column:'+(lage.spalte[i]+1)+' / span '+g.w;
}
// style einer Kachel: ihre Farben (tileVarStyle, ohne Schluss-Semikolon) und
// ihre feste Stelle als eigene Angaben - aneinandergehaengt schluckte die
// letzte Farbe grid-row. Derselbe Text in render() und updateGrid().
function kachelStil(it, lage, groessen, i, quer){
  return [tileVarStyle(it), kachelPlatz(lage, groessen, i, quer)].filter(Boolean).join(';');
}
// Die Rechnung steht in raster.js (gemeinsam mit dem Assistenten im
// Konfigurator); hier misst die Visu, was sie braucht: sichtbare Flaeche,
// Abstand und Innenrand des Rasters, Hoehe der Seitenpunkte und der
// Tab-Leiste, Kopfzeile und Werteleiste zum jeweiligen Kachelfaktor, die
// Kacheln der Seite und ob sie waagerecht blaettert.
function autoRaster(widget){
  const cs=getComputedStyle(el('grid')), tabs=el('tabs'), vp=vpSize(), links=kachelLeiste==='links';
  // Kachel-Set: die Seitenleiste ("links") nimmt Breite statt Hoehe, ein
  // Rahmen um das Feld ("oben") Breite und Hoehe - beides als Innenabstand
  // des Kastens; die Leiste "links" ist dessen linker Teil.
  const sc=document.querySelector('.screen'), scs=sc ? getComputedStyle(sc) : null, px=v=>parseFloat(v)||0;
  const railW=links&&tabs ? tabs.offsetWidth : 0;
  return LoxRaster.autoRaster({w:vp.w, h:vp.h, ziel:gridAuto, wachsen:gridGrow,
    gap:parseFloat(cs.getPropertyValue('--gap'))||0, pad:parseFloat(cs.getPropertyValue('--pad'))||0,
    punkteH:parseFloat(cs.getPropertyValue('--punkte-h'))||0,
    fussH:LoxRaster.fussH(gestenAn && gestenHinweis, seitenQuer(), vp.w, parseFloat(cs.getPropertyValue('--hinweis-h'))||0),
    tabsH:links ? 0 : (tabs?tabs.offsetHeight:0), railW:railW,
    rahmenX:scs ? px(scs.paddingLeft)+px(scs.paddingRight)-railW : 0, rahmenY:scs ? px(scs.paddingTop)+px(scs.paddingBottom) : 0,
    kopfH:kopfHoehe, leisteH:leisteHoehe, widget:widget, paneCols:paneCols, paneShare:paneShare,
    breiten:_lastBreiten, seitenQuer:seitenQuer()});
}
// Lage + Raster als Vergleichswert fuer den resize-Nachzug (s. render()).
// Dazu die Blaetterrichtung (seitenQuer): ein Fenster, das quer ueber die
// Quadrat-Schwelle waechst (520x480 -> 560x480), aendert weder Lage noch
// Raster, muss aber von senkrecht auf waagerechte Seiten umbauen.
// Masse des automatischen Rasters als CSS-Variablen. Ein Hochkant-Widget hat eine Hoehe in px
// (pPx), die mit dem Fenster waechst und schrumpft, auch wenn Spalten, Zeilen, k und p bleiben
// (rasterKey also gleich): fensterGeaendert setzt sie dann ohne Neuaufbau nach.
function autoMasseSetzen(a){
  const sc=document.querySelector('.screen'); if(!sc) return;
  sc.style.setProperty('--auto-k', a.pPx ? 'minmax(0,1fr)' : a.k+'fr');
  sc.style.setProperty('--auto-p', a.pPx ? Math.round(a.pPx)+'px' : a.p+'fr');
}
function rasterKey(widget){
  const {w,h}=vpSize(), a=gridAuto ? autoRaster(widget) : null;
  return (w>h?'quer':(h>w?'hoch':'quadrat'))+':'+rasterFuer(widget).join('x')+(a ? ':'+a.k+'/'+a.p+(a.hoch?':unter':'') : '')
    +(seitenQuer()?':seiten':'');
}
function render(){
  if(!view) return;
  const _k = themeSplit ? paneKind(paneForTab(activeTab())) : null;   // Split aus -> nie Pane/Verdopplung
  const _widget = (_k==='player'||_k==='weather'||_k==='calendar'||_k==='energy'||_k==='camera'||_k==='chart'||_k==='status');
  // Entscheidung merken: beim Kiosk-Start / Auto-Reload meldet das Fenster
  // kurz eine falsche Groesse (etwa quer), bevor die echte Flaeche steht. Der
  // resize-Handler rendert neu, sobald Lage oder Raster kippen (sonst bliebe
  // das 4"-Panel in der Startmessung 4x2 statt 2x2 haengen - dasselbe Muster
  // wie beim Screensaver).
  _lastWidget = _widget;
  // Kacheln der Seite mit ihrer Breite (fuer das Wachsen im automatischen
  // Raster): keine auf Widget-, Front- und Listenseiten
  _lastBreiten = (!view.widget && !view.front && view.layout!=='list') ? katSichtbar(view.items||[]).map(it=>({w:it.w===2?2:1, h:it.h===2?2:1})) : [];
  schmalEinrichten();   // Masse fuer schmale Schirme (Kachel-Set) vor der Rasterrechnung
  _lastRaster = rasterKey(_widget);
  [gridCols, gridRows] = rasterFuer(_widget);
  document.documentElement.style.setProperty('--cols', gridCols);
  document.documentElement.style.setProperty('--rows', gridRows);
  if(gridAuto){ const a=autoRaster(_widget);
    autoMasseSetzen(a);
    setzeFaktor(a.ks); }   // Kachelfaktor aus der Spaltenbreite, vor dem Aufbau
  reportScreen();   // Raster der Kachelansicht melden (entprellt, nur bei Aenderung)
  renderLeiste();   // Werteleiste ueber dem Raster (oder weg) - vor dem Bauen und Messen der Kacheln
  stopVideo();
  closeMenu();
  setMore(null);
  // Widget-Seite: ganzer Tab = ein Widget (Vollbild). Kein Kachelgrid; die
  // Flaeche bleibt beim Profil-Standard (nicht verdoppeln). applyPane (ueber
  // renderTabs) zeichnet das Widget und meldet seinen Datenkanal an.
  if(view.widget){
    if(!gridAuto){ gridCols=profCols; gridRows=profRows; }   // automatisch: der Kasten ist ohnehin der Schirm
    document.documentElement.style.setProperty('--cols', gridCols);
    document.documentElement.style.setProperty('--rows', gridRows);
    el('grid').classList.remove('panel','bigpage','anchorbot','scheme','list','fronttab','lx','hpages','punkte','fuss','haus');
    renderTabs();
    return;
  }
  if(view.layout==='haus'){ renderHaus(); return; }
  el('grid').classList.remove('panel','bigpage','anchorbot','scheme','fronttab','haus');
  if(view.front){ renderFrontTab(); return; }
  el('grid').classList.toggle('list', view.layout==='list');
  el('grid').classList.toggle('lx', kachelNeu());
  const items = katSichtbar(view.items || []);   // Filter-Modus der Sprungmarken
  const g = el('grid');
  if(!items.length){ g.classList.remove('hpages','punkte','fuss'); g.innerHTML='<div class="empty">nichts hier</div>'; renderTabs(); return; }
  // Lage im Raster: Rastpunkt auf die erste Kachel jeder Seite (Liste: jede
  // 4.), breite Kacheln (w2) nur, wo zwei Spalten da sind. Waagerechte
  // Seiten (Tablet): je Seite ein eigenes Raster, Rastpunkt ist die Seite.
  const groessen=items.map(kachelGroesse), lage=rasterLage(groessen, gridCols, gridRows);
  const quer=seitenQuer();
  const snapAt=i=> quer ? false : (view.layout==='list' ? (i%4===0) : lage.snaps.has(i));
  g._zeile=lage.zeile;
  const seiten=quer ? Array.from({length:lage.seiten}, ()=>'') : null;
  let html='';
  let _i=-1;
  for(const it of items){
    _i++;
    const icoHtml = it.iconImg
      ? '<span class="ico"><img class="rawico" src="'+esc(it.iconImg)+'" alt=""></span>'
      : it.iconUrl
      ? '<span class="ico img" style="--u:url(\''+esc(it.iconUrl)+'\')"></span>'
      : '<span class="ico">'+svg(ICONS[it.icon]||ICONS.info)+'</span>';
    // Positionsring: nur fuer Bausteine, die eine Stellung haben. Bei 0 %
    // bleibt allein die Spur stehen - ein runder Abschluss auf der Laenge null
    // wuerde sonst als Punkt erscheinen und wie ein Fehler aussehen.
    const posv = ringPos(it);
    const icoCell = posv===null ? icoHtml
      : '<span class="icowrap"><svg class="posring" viewBox="0 0 100 100" aria-hidden="true">'+
          '<g transform="rotate(-90 50 50)">'+
            '<circle class="trk" cx="50" cy="50" r="46"/>'+
            (posv>0 ? '<circle class="val" cx="50" cy="50" r="46" stroke-dasharray="'+
              ringDash(posv)+'"/>' : '')+
          '</g></svg>'+icoHtml+'</span>';
    const lx = kachelNeu(), tx = kachelTexte(it), sub = tx.sub;
    // Aufbau "kreis" (Kachel-Set): das Symbol steht in einem Kreis
    const kopf = (lx && it.big!=null) ? '<span class="bigv">'+bigHtml(it.big)+'</span>'
      : (lx && kachelAufbau==='kreis') ? '<span class="kreis">'+icoCell+'</span>' : icoCell;
    const chev = (!lx && it.nav && !it.controls) ? '<span class="chev">'+svg('<path d="m9 6 6 6-6 6"/>')+'</span>' : '';
    const tasten = it.controls ? '<div class="tctrls">'+it.controls.map((c,i)=>'<span class="tb" data-c="'+i+'">'+svgF(ICONS[c.icon]||ICONS.info)+'</span>').join('')+'</div>' : '';
    const ctrls = spielerKachel(it, groessen[_i])
      ? '<div class="tplay">'+(it.cover?'<img class="tcover" src="'+esc(it.cover)+'" alt="">':'')+tasten+'</div>' : tasten;
    const tone = tileTone(it);
    const ts=it.style||{};
    const stStr = kachelStil(it, lage, groessen, _i, quer);
    const st = stStr?' style="'+esc(stStr)+'"':'';
    const nsv=[];
    if(ts.txt) nsv.push('color:'+ts.txt);
    if(ts.font) nsv.push('font-family:'+ts.font);
    if(ts.weight) nsv.push('font-weight:'+ts.weight);
    if(ts.italic) nsv.push('font-style:italic');
    const nst = nsv.length?' style="'+esc(nsv.join(';'))+'"':'';
    // Neuer Aufbau: Raum im Kopf rechts, die Angabe zum Mini-Verlauf als Zeile
    // im Text (im Kopf stuende sie neben dem Raum).
    const kachel = '<div class="tile'+tone+aufbauKlassen(it)+kachelKlassen(groessen[_i])+spielerKlasse(it, groessen[_i])+(snapAt(_i)?' snap':'')+'" data-id="'+esc(it.id)+'"'+(it.catKey?' data-cat="'+esc(it.catKey)+'"':'')+st+'>'+
              '<div class="head">'+kopf+(!lx&&it.spark&&it.spark.badge?'<span class="tsbadge">'+esc(it.spark.badge)+'</span>':'')+
                (lx&&it.room&&kachelAufbau!=='mitte'?'<span class="room">'+esc(it.room)+'</span>':'')+chev+'</div>'+
              (it.spark?'<div class="tspark"></div>':'')+
              '<div class="body">'+
              (!lx&&it.room?'<div class="room">'+esc(it.room)+'</div>':'')+
              (it.spark&&it.spark.badge?'<div class="room tsline">'+esc(it.spark.badge)+'</div>':'')+
              '<div class="name"'+nst+'>'+esc(tx.name)+'</div>'+
              (sub?'<div class="sub">'+esc(sub)+'</div>':'')+'</div>'+
              ctrls+
            '</div>';
    if(seiten) seiten[Math.floor(lage.zeile[_i]/Math.max(1,gridRows))] += kachel; else html += kachel;
  }
  const fuss=quer && hinweisFuss();
  if(seiten){
    html = '<div class="punkte">'+(lage.seiten>1 ? seiten.map((_,k)=>'<i'+(k===0?' class="on"':'')+'></i>').join('') : '')+
           (fuss ? '<b class="ghinweis" role="button" aria-label="Gesten"'+(view.gestenHilfe ? '' : ' hidden')+'>'+
                   svg(ICONS.zweiFinger)+'</b>' : '')+'</div>'+
           seiten.map(h=>'<div class="page">'+h+'</div>').join('');
  }
  g.classList.toggle('hpages', quer);
  g.classList.toggle('punkte', quer && lage.seiten>1);
  g.classList.toggle('fuss', fuss);
  g.dataset.aufbau = kachelAufbau;   // updateGrid baut neu, wenn das Kachel-Set einen anderen Aufbau bringt
  g.innerHTML = html;
  if(quer){ g.querySelectorAll('.punkte i').forEach((d,k)=>d.onclick=()=>seiteZu(k)); punkteNachziehen(); }
  { const gh=g.querySelector('.ghinweis'); if(gh) gh.onclick=e=>{ e.stopPropagation(); gestenHilfeZeigen(); }; }
  g.classList.toggle('snapy', !quer && (view.layout==='list' ? items.length>4 : lage.seiten>1));   // Snapping erst ab >1 Seite
  // Erst die Leiste und damit applyPane() (Split, Kopfzeile): dann hat das
  // Raster seine endgueltige Breite, und die Kacheln messen sich richtig ein.
  renderTabs();
  if(!gridAuto) faktorEinmessen();   // festes Raster: aus der ersten Kachel, mit Kopfzeile bis es steht
  g.querySelectorAll('.tile[data-id]').forEach(n=>{
    const it = items.find(x=>String(x.id)===n.dataset.id);
    n._it = it;   // aktuelle Daten am Knoten -> updateGrid kann sie in-place ersetzen
    n._stStr = kachelStil(it, lage, groessen, items.indexOf(it), quer);   // Vergleichswert fuer updateGrid (s. dort)
    if(it && it.spark) paintSpark(n.querySelector('.tspark'), it.spark);   // erst jetzt ist die Groesse bekannt
    if(it.controls){
      n.querySelectorAll('.tctrls .tb').forEach(b=>{
        b._cmd = it.controls[+b.dataset.c].cmd; b._secured = it.secured;
        // Erst beim Tippen (click: Aufsetzen und Loslassen ohne Wischen), nicht
        // schon beim Aufsetzen: ein Wischer, der auf der Taste beginnt, scrollt
        // das Raster, statt den Befehl zu senden.
        b.addEventListener('click', ()=>{
          if(b._cmd) sendCmd(b._cmd.uuid,b._cmd.cmd,b._secured); });
      });
      tastenEinpassen(n);
    }
    fitTile(n);
    _kachelM=kachelMass();   // fuer faktorNachziehen: neu einpassen, wenn sich das Mass aendert
    n.onclick=(e)=>{ if(e.target.closest('.tctrls')) return; const t=n._it||it;
      if(t.nav) nav(t.nav); else if(t.cmd) sendCmd(t.cmd.uuid,t.cmd.cmd,(view&&view.secured)||t.secured); };
  });
  // Eine LEERE Liste ist eine Aussage ("diese Seite hat keine Sprungmarken"),
  // kein fehlender Wert: sie muss die gemerkten loeschen. Sonst blieben nach
  // einer Auswahl mit mehreren Raeumen Marken stehen, die ins Leere zeigen,
  // sobald nur noch ein Raum uebrig ist. Nur Ansichten OHNE den Schluessel
  // (Detailansichten) greifen auf die gemerkten zurueck.
  if(Array.isArray(view.catTabs)) roomCatTabs = view.catTabs.length ? view.catTabs : null;
  // Aus einem Detail zurueck in den Raum gesprungen? Jetzt zur Kategorie scrollen.
  if(pendingCatScroll){ const k=pendingCatScroll; pendingCatScroll=null;
    requestAnimationFrame(()=>{ const d=g.querySelector('.tile[data-cat="'+k+'"]'); if(d){ springeZu(d); leuchte(k); } }); }
}

// ---- Anlagenschema (SystemScheme) ----
// Hintergrundbild + Live-Werte als Overlay. Der Viewport zeigt das Schema
// fit-to-width; Pinch/Pan zoomt und verschiebt. Antippbare Werte (nav)
// springen zur Detailansicht des Bausteins.
let schemeFit=null;
function schemeValHtml(it,i){
  const w=it.w||120, h=it.h||30;
  const cls='schemeval'+(it.on?' on':'')+(it.nav?' tap':'')+(it.tone==='crit'?' crit':'');
  return '<div class="'+cls+'" data-i="'+i+'" style="left:'+it.x+'px;top:'+it.y+'px;width:'+w+'px;height:'+h+'px">'+
    '<span>'+esc(it.text||'')+'</span></div>';
}
function renderScheme(v){
  const g=el('grid');
  g.classList.remove('panel','list','bigpage','anchorbot','snapy','fronttab','lx','hpages','punkte','fuss','haus');
  g.classList.add('scheme');
  const sw=v.sw||1300, sh=v.sh||866, items=v.items||[];
  let html='<div class="schemetitle">'+esc(v.title||'')+'</div>'+
    '<div class="schemeview" id="schemeView"><div class="schemestage" id="schemeStage" '+
    'style="width:'+sw+'px;height:'+sh+'px">';
  if(v.image) html+='<img class="schemeimg" src="'+esc(v.image)+'" alt="" draggable="false">';
  html+=items.map(schemeValHtml).join('')+'</div><div class="schemehint">Ziehen · 2 Finger zoomen</div></div>';
  g.innerHTML=html;
  const viewEl=el('schemeView'), stage=el('schemeStage');
  stage.querySelectorAll('.schemeval.tap').forEach(n=>{
    n.onclick=()=>{ const it=items[+n.dataset.i]; if(it&&it.nav) nav(it.nav); };
  });
  setupSchemeZoom(viewEl, stage, sw, sh);
  renderTabs();
}
function updateScheme(v){
  const stage=el('schemeStage'); if(!stage) return false;
  const nodes=stage.querySelectorAll('.schemeval');
  const items=v.items||[];
  if(nodes.length!==items.length) return false;   // Struktur anders -> voller Neuaufbau
  items.forEach((it,i)=>{
    const n=nodes[i], sp=n.querySelector('span');
    if(sp && sp.textContent!==(it.text||'')) sp.textContent=it.text||'';
    const cls='schemeval'+(it.on?' on':'')+(it.nav?' tap':'')+(it.tone==='crit'?' crit':'');
    if(n.className!==cls){ n.className=cls;
      n.onclick=it.nav?(()=>{ if(it.nav) nav(it.nav); }):null; }
  });
  return true;
}
function setupSchemeZoom(viewEl, stage, sw, sh){
  let scale=1, tx=0, ty=0, minScale=0.05;
  const apply=()=>{ stage.style.transform='translate('+tx+'px,'+ty+'px) scale('+scale+')'; };
  const clamp=()=>{ const vw=viewEl.clientWidth, vh=viewEl.clientHeight, cw=sw*scale, ch=sh*scale;
    if(cw<=vw) tx=(vw-cw)/2; else tx=Math.min(0,Math.max(vw-cw,tx));
    if(ch<=vh) ty=(vh-ch)/2; else ty=Math.min(0,Math.max(vh-ch,ty)); };
  const fit=()=>{ const vw=viewEl.clientWidth, vh=viewEl.clientHeight; if(!vw||!vh) return;
    minScale=Math.min(vw/sw, vh/sh);              // "contain": ganzes Schema sichtbar
    scale=minScale;                               // Start: komplett eingepasst (Hoehe & Breite)
    tx=(vw-sw*scale)/2; ty=(vh-sh*scale)/2; clamp(); apply(); };
  const pts=new Map(); let lastDist=0;
  viewEl.onpointerdown=e=>{ viewEl.setPointerCapture(e.pointerId);
    pts.set(e.pointerId,{x:e.clientX,y:e.clientY}); lastDist=0; };
  viewEl.onpointermove=e=>{ if(!pts.has(e.pointerId)) return;
    const prev=pts.get(e.pointerId); pts.set(e.pointerId,{x:e.clientX,y:e.clientY});
    // Pointer-Koordinaten sind sichtbare Pixel, tx/ty Layout-Pixel: bei
    // skalierter Visu liefe das Bild dem Finger sonst davon.
    const k=visScale(viewEl);
    if(pts.size===1){ tx+=(e.clientX-prev.x)/k; ty+=(e.clientY-prev.y)/k; clamp(); apply(); }
    else if(pts.size>=2){ const a=[...pts.values()], dist=Math.hypot(a[0].x-a[1].x,a[0].y-a[1].y);
      const rect=viewEl.getBoundingClientRect(), cx=((a[0].x+a[1].x)/2-rect.left)/k, cy=((a[0].y+a[1].y)/2-rect.top)/k;
      if(lastDist){ const ns=Math.max(minScale,Math.min(6,scale*(dist/lastDist)));
        tx=cx-(cx-tx)*(ns/scale); ty=cy-(cy-ty)*(ns/scale); scale=ns; clamp(); apply(); }
      lastDist=dist; } };
  const up=e=>{ pts.delete(e.pointerId); lastDist=0; };
  viewEl.onpointerup=up; viewEl.onpointercancel=up;
  // Doppeltipp: zwischen fit-to-width und 2.5x umschalten
  let lastTap=0;
  viewEl.addEventListener('click',e=>{ if(e.target.closest('.schemeval.tap')) return;
    const now=Date.now(); if(now-lastTap<300){ const vw=viewEl.clientWidth;
      // Doppeltipp: von "ganz sichtbar" auf fit-to-width (lesbar) zoomen, sonst zurueck
      if(scale>minScale*1.15){ fit(); } else { const rect=viewEl.getBoundingClientRect(), k=visScale(viewEl);
        const cx=(e.clientX-rect.left)/k, cy=(e.clientY-rect.top)/k, ns=Math.min(6,Math.max(vw/sw,minScale*2.5));
        tx=cx-(cx-tx)*(ns/scale); ty=cy-(cy-ty)*(ns/scale); scale=ns; clamp(); apply(); } }
    lastTap=now; });
  schemeFit=fit;
  // Bild kann nach dem Layout erst die richtige Groesse liefern -> nach Frame fitten
  requestAnimationFrame(fit); const img=stage.querySelector('.schemeimg'); if(img) img.onload=fit;
}
// Laeuft bei jeder Groessenaenderung. Nicht nur bei 'resize': eine iOS-Web-App
// meldet die echte Flaeche erst mit 'pageshow' oder ueber visualViewport, und
// beim Drehen kommt 'orientationchange' teils ohne resize.
function fensterGeaendert(){
  schmalEinrichten();   // Masse fuer schmale Schirme (Kachel-Set), etwa die Seitenleiste
  applyHoch();   // Split beim Drehen zwischen nebeneinander und uebereinander umstellen
  if(el('grid').classList.contains('scheme')&&schemeFit) schemeFit();
  // Screensaver-Spaltigkeit nachziehen, wenn das Fenster (Kiosk-Start, Rotation,
  // Auto-Reload) erst spaet die echte Groesse meldet -> kein Haengenbleiben in 2-spaltig.
  if(saverOn()){ applySaverSplit(); applyPane(); renderFront(); }
  // Kachel-Grid nur neu rendern, wenn Lage (quer/hoch/quadratisch) oder Raster
  // tatsaechlich kippen (kein Neuzeichnen bei jedem Pixel) -> 4"-Panel bleibt
  // 2x2 statt in der Startmessung 4x2 haengenzubleiben.
  // Hausuebersicht: Lage (Spieler als Spalte oder Leiste, Spalten) neu
  // rechnen; nur wenn sie kippt, baut renderHaus neu
  if(view && view.layout==='haus' && el('grid').classList.contains('haus')){ if(!updateHaus()) render(); }
  else if(view && !el('grid').classList.contains('scheme')){
    if(rasterKey(_lastWidget) !== _lastRaster) render();
    else if(gridAuto) autoMasseSetzen(autoRaster(_lastWidget));   // gleiches Raster, andere Pixel (Hochkant-Widget)
  }
  panelEinpassen();
  kopfEinpassen();
  faktorNachziehen();   // Kachelbreite geaendert, Raster nicht: Inhalt nachziehen
}
window.addEventListener('resize', fensterGeaendert);
window.addEventListener('orientationchange', ()=>setTimeout(fensterGeaendert, 50));
window.addEventListener('pageshow', fensterGeaendert);
if(window.visualViewport) window.visualViewport.addEventListener('resize', fensterGeaendert);

// Wisch nach rechts = zurueck (vertikales Scrollen bleibt unberuehrt). Mit
// waagerechten Seiten blaettert der Wisch ab Seite 2 zurueck zur vorigen
// Seite (der Browser scrollt, eingerastet); nur auf der ersten Seite heisst
// er "zurueck" wie am 4"-Panel.
let sx=null, sy=null, sl=0;
const g=el('grid');
g.addEventListener('touchstart',e=>{sx=e.touches[0].clientX;sy=e.touches[0].clientY;sl=g.scrollLeft;},{passive:true});
g.addEventListener('touchend',e=>{
  if(gesteSequenz){ sx=null; return; }   // zwei Finger: eine Geste, kein "zurueck"
  if(sx==null)return; const dx=e.changedTouches[0].clientX-sx, dy=e.changedTouches[0].clientY-sy; sx=null;
  if(g.classList.contains('scheme')) return;   // im Schema pant der Finger, kein "zurueck"
  if(g.classList.contains('hpages') && sl>0) return;   // Seite zurueckgeblaettert, nicht die Ansicht
  if(dx>60 && Math.abs(dy)<45) back();
});
// Seitenpunkte folgen dem Scrollen; das Mausrad (Browser am PC, iPad mit
// Trackpad) blaettert senkrecht gedreht eine Seite weiter, waagerechte
// Bewegungen scrollt der Browser selbst (eingerastet).
g.addEventListener('scroll', ()=>{ if(g.classList.contains('hpages')) punkteNachziehen(); }, {passive:true});
let _radSperre=null;
g.addEventListener('wheel', e=>{
  if(!g.classList.contains('hpages') || Math.abs(e.deltaY)<=Math.abs(e.deltaX)) return;
  e.preventDefault();
  if(_radSperre) return;
  _radSperre=setTimeout(()=>{ _radSperre=null; }, 450);
  const n=g.querySelectorAll('.page').length;
  seiteZu(Math.max(0, Math.min(n-1, seiteAktuell()+(e.deltaY>0?1:-1))));
}, {passive:false});

