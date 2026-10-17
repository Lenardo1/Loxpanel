// LoxPanel-Visu, Teil 3 von 12: Verlaufsdiagramme und Mini-Verlaeufe, Kachelfaktor, Kachel einpassen, Detailseite (renderPanel, updatePanel).
// Die Teile laden nacheinander aus panel.html (script src), alle Funktionen sind global;
// was beim Laden ausgefuehrt wird, darf nur Funktionen frueherer Teile rufen.

// ---- Verlaufs-Diagramme (Block k:'chart'). Die Daten stammen aus den
// Statistik-Dateien des Miniservers und kommen fertig aufbereitet vom Server.
// Zeitstempel sind Wanduhr-Sekunden der Anlage, als UTC gefuehrt: mit getUTC*
// formatiert zeigt jedes Panel dieselbe Uhrzeit wie der Miniserver, egal in
// welcher Zeitzone der Browser laeuft. Farben per style, weil var() in
// SVG-Praesentationsattributen nicht ueberall greift.
const CH_COLORS=['var(--accent)','var(--glow)','var(--crit)','var(--muted)'];
function chNum(v,dec){ return (+v).toFixed(dec).replace('.',','); }
function chTime(t,span){ const d=new Date(t*1000), p=n=>String(n).padStart(2,'0');
  return span<=129600 ? p(d.getUTCHours())+':'+p(d.getUTCMinutes()) : p(d.getUTCDate())+'.'+p(d.getUTCMonth()+1)+'.'; }
function chDur(sec){ const h=Math.floor(sec/3600), m=Math.round(sec%3600/60);
  return h ? h+' h'+(m?' '+m+' min':'') : m+' min'; }
// Runde Zeitpunkte fuer die Zeitachse: der kleinste Abstand aus der Liste, der
// hoechstens 5 Beschriftungen ergibt (24 h -> alle 6 h, 7 Tage -> jeden 2. Tag,
// 30 Tage -> woechentlich). Die Sekunden sind Wanduhrzeit, t % Tag = 0 ist also
// Mitternacht; Wochen beginnen am Montag (der 1.1.1970 war ein Donnerstag).
function chTicks(t0,t1){
  const H=3600, D=86400;
  for(const st of [H,3*H,6*H,12*H,D,2*D,7*D]){
    const off=st===7*D?4*D:0, first=Math.ceil((t0-off)/st)*st+off;
    if(Math.floor((t1-first)/st)+1<=5){ const out=[]; for(let t=first;t<=t1;t+=st) out.push(t); return {ticks:out, day:st>=D}; }
  }
  return {ticks:[t0,t1], day:true};
}
let chSeq=0;
function paintChart(box,b){
  box.querySelectorAll('[data-rng]').forEach(c=>c.classList.toggle('on',c.dataset.rng===b.range));
  const body=box.querySelector('.chbody'); if(!body) return;
  if(b.state!=='ok'){
    body.innerHTML='<div class="chmsg">'+(b.state==='loading'?'Verlauf wird geladen …'
      :b.state==='error'?'Verlauf nicht abrufbar':'Keine Aufzeichnung in diesem Zeitraum')+'</div>';
    return; }
  const W=440,H=150,pL=36,pR=10,pT=10,pB=22, t0=b.t0, t1=b.t1, span=Math.max(1,t1-t0);
  const unit=b.unit?(' '+b.unit):'', dec=Math.max(0,...b.series.map(s=>s.dec||0));
  const vals=b.series.flatMap(s=>s.pts.map(p=>p[1]));
  let lo=vals.length?Math.min(...vals):0, hi=vals.length?Math.max(...vals):1, mn, mx;
  if(b.kind==='digital'){ mn=-0.08; mx=1.08; }
  else if(b.kind==='counter'){ lo=0; if(hi<=0) hi=1; mn=0; mx=hi*1.08; }
  else { if(hi-lo<1e-9){ lo-=1; hi+=1; } const pd=(hi-lo)*0.1; mn=lo-pd; mx=hi+pd; }
  const X=t=>pL+(t-t0)*(W-pL-pR)/span, Y=v=>pT+(mx-v)*(H-pT-pB)/(mx-mn), f=n=>n.toFixed(1);
  const id='chg'+(++chSeq), c0=CH_COLORS[0];
  let s='<defs><linearGradient id="'+id+'" x1="0" y1="0" x2="0" y2="1"><stop offset="0" style="stop-color:'+c0+';stop-opacity:.28"/>'+
        '<stop offset="1" style="stop-color:'+c0+';stop-opacity:0"/></linearGradient></defs>';
  const yt=b.kind==='digital'?[[0,'Aus'],[1,'Ein']]:[lo,(lo+hi)/2,hi].map(v=>[v,chNum(v,dec)]);
  yt.forEach(([v,l])=>{ s+='<line class="chgrid" x1="'+pL+'" x2="'+(W-pR)+'" y1="'+f(Y(v))+'" y2="'+f(Y(v))+'"/>'+
    '<text class="chax" x="2" y="'+f(Y(v)+4)+'" text-anchor="start">'+esc(l)+'</text>'; });
  const tk=chTicks(t0,t1);
  tk.ticks.forEach(t=>{ const x=X(t), a=x<pL+18?'start':(x>W-pR-18?'end':'middle');
    s+='<line class="chvgrid" x1="'+f(x)+'" x2="'+f(x)+'" y1="'+pT+'" y2="'+(H-pB)+'"/>'+
       '<text class="chax" x="'+f(x)+'" y="'+(H-6)+'" text-anchor="'+a+'">'+chTime(t,tk.day?Infinity:0)+'</text>'; });
  const leg=[];
  b.series.forEach((se,si)=>{
    const col=CH_COLORS[si%CH_COLORS.length], p=se.pts; if(!p.length) return;
    let info='';
    if(b.kind==='counter'){           // Verbrauch je Stunde/Tag als Balken, mehrere Reihen nebeneinander
      const nS=b.series.length;
      p.forEach(([t,v],i)=>{ const x0=X(t), x1=i+1<p.length?X(p[i+1][0]):W-pR, g=Math.min(3,(x1-x0)*0.15),
          bw=Math.max(1,(x1-x0-2*g)/nS), y=Y(v);
        s+='<rect x="'+f(x0+g+si*bw)+'" y="'+f(y)+'" width="'+f(bw)+'" height="'+f(Math.max(0,Y(0)-y))+
           '" rx="2" style="fill:'+col+'"/>'; });
      info='Summe <b>'+chNum(p.reduce((a,q)=>a+q[1],0),se.dec)+unit+'</b>';
    } else if(b.kind==='digital'){    // Stufen, dazu die Ein-Dauer im Zeitraum
      let d='M'+f(X(p[0][0]))+' '+f(Y(p[0][1])), on=0;
      p.forEach(([t,v],i)=>{ const tn=i+1<p.length?p[i+1][0]:t1;
        if(v>=0.5) on+=Math.max(0,tn-t);
        d+=' H'+f(X(tn))+(i+1<p.length?' V'+f(Y(p[i+1][1])):''); });
      s+='<path d="'+d+' V'+f(Y(0))+' H'+f(X(p[0][0]))+' Z" style="fill:'+col+';opacity:.22"/>'+
         '<path d="'+d+'" style="fill:none;stroke:'+col+';stroke-width:2;stroke-linejoin:round"/>';
      info='Ein <b>'+chDur(on)+'</b>';
    } else {                          // Linie, erste Reihe mit Verlaufsflaeche
      const line=p.map(([t,v])=>f(X(t))+','+f(Y(v))).join(' ');
      if(si===0) s+='<polygon points="'+f(X(p[0][0]))+','+f(Y(mn))+' '+line+' '+f(X(p[p.length-1][0]))+','+f(Y(mn))+'" fill="url(#'+id+')"/>';
      s+='<polyline points="'+line+'" style="fill:none;stroke:'+col+';stroke-width:2.2;stroke-linejoin:round;stroke-linecap:round"/>';
      const q=p[p.length-1]; s+='<circle cx="'+f(X(q[0]))+'" cy="'+f(Y(q[1]))+'" r="3.5" style="fill:'+col+'"/>';
      const vs=p.map(q=>q[1]);
      info='min <b>'+chNum(Math.min(...vs),se.dec)+'</b> · max <b>'+chNum(Math.max(...vs),se.dec)+unit+'</b>';
    }
    leg.push('<span><span class="chdot" style="background:'+col+'"></span>'+esc(se.name)+' · '+info+'</span>');
  });
  body.innerHTML='<svg viewBox="0 0 '+W+' '+H+'" preserveAspectRatio="none">'+s+'</svg><div class="chleg">'+leg.join('')+'</div>';
}
// Rahmen eines Diagramms (Detailseite und Verlaufs-Pane); die Zeitraum-Knoepfe
// traegt nur das erste Diagramm einer Seite (b.ranges).
function chartBoxHtml(b,withRange){
  if(withRange===undefined) withRange=true;   // Stapel-Pane zeigt die Knoepfe nur einmal oben
  return '<div class="chart" data-chart>'+((withRange&&b.ranges)?'<div class="chrng">'+
    b.ranges.map(r=>'<button type="button" class="chip" data-rng="'+esc(r[0])+'">'+esc(r[1])+'</button>').join('')+
    '</div>':'')+'<div class="chbody"></div></div>';
}
// Verlaufs-Pane im Split-Layout: Name und aktueller Wert, darunter die Diagramme
// wie auf der Detailseite. Neu aufgebaut nur, wenn sich Baustein oder Aufbau
// aendern, sonst nur neu gezeichnet. Die Zeitraum-Knoepfe melden den Zeitraum
// dem Server neu (setchart), statt wie auf der Detailseite die Route zu ersetzen:
// links bleibt die Kachelseite stehen.
function renderChartPane(elc){ if(!elc) return;
  // Verlaufs-Pane zeigt einen oder mehrere Bausteine gestapelt (Server:
  // {t:'chart', charts:[{control,name,value,blocks}], range, ranges}). Welche
  // Bausteine, meldet applyPane() dem Server per setchart; der Push landet in
  // chartData. Ab zwei Bausteinen scrollt die Pane (.stack), sonst "fit" wie bisher.
  const d=(chartData && Array.isArray(chartData.charts)) ? chartData : null;
  const charts=d ? d.charts : [];
  const multi=charts.length>1;
  const sig=(d?d.controls.join(','):'-')+'|'+(d?d.range:'')+'|'+
            charts.map(c=>(c.blocks||[]).length).join('.');
  let page=elc.querySelector('.fp-page.cpage');
  if(!page || page.dataset.sig!==sig){
    const rngRow=(d && d.ranges && d.ranges.length)
      ? '<div class="chrng cpr">'+d.ranges.map(r=>'<button type="button" class="chip'+
          (r[0]===d.range?' on':'')+'" data-rng="'+esc(r[0])+'">'+esc(r[1])+'</button>').join('')+'</div>'
      : '';
    const body=!d
      ? '<div class="chmsg">Verlauf wird geladen …</div>'
      : (charts.length
        ? charts.map(c=>'<div class="cpsec"><div class="cphead"><div class="cpname"></div>'+
            '<div class="cpval"></div></div>'+
            (c.blocks||[]).map(b=>chartBoxHtml(b,false)).join('')+'</div>').join('')
        : '<div class="chmsg">Kein Baustein mit Aufzeichnung gewählt.</div>');
    elc.innerHTML='<div class="fp-page cpage solo'+(multi?' stack':'')+'">'+rngRow+'<div class="cpbody">'+body+'</div></div>';
    page=elc.querySelector('.fp-page.cpage'); page.dataset.sig=sig;
    page.querySelectorAll('.cpr [data-rng]').forEach(btn=>btn.addEventListener('pointerdown',ev=>{ ev.preventDefault();
      chartRange=btn.dataset.rng; applyPane(); }));
  }
  if(d){
    const secs=page.querySelectorAll('.cpsec');
    charts.forEach((c,i)=>{ const s=secs[i]; if(!s) return;
      const nm=s.querySelector('.cpname'), vl=s.querySelector('.cpval');
      if(nm) nm.textContent=c.name||''; if(vl) vl.textContent=c.value||''; });
    paintChartStack(page,charts);
  }
}
// Alle Diagramme des Stapels in DOM-Reihenfolge zeichnen (ein [data-chart]-Kasten
// je Block, Bloecke je Baustein hintereinander - wie chartBoxHtml sie ausgibt).
function paintChartStack(page,charts){
  const els=[...page.querySelectorAll('[data-chart]')]; let i=0;
  charts.forEach(c=>(c.blocks||[]).forEach(b=>{ if(b.k==='chart'&&els[i]) paintChart(els[i],b); i++; }));
}
// Mini-Verlauf in einer Kachel (it.spark, je Kachel im Konfigurator gewaehlt). Drei
// Stile, gezeichnet in der echten Pixelgroesse der freien Kachelmitte (paintSpark),
// damit Beschriftungen scharf und unverzerrt bleiben:
//   trend    Verlauf: Linie mit Tiefst-/Hoechstwert und Jetzt-Punkt, Digitalwert
//            als Stufen, Zaehlerstand als Verbrauchsbalken
//   pattern  Tagesmuster: 7 Tage (Zeilen, heute unten) x 24 Stunden, Deckkraft = Wert
//   span     Tagesspanne: je Tag ein Balken Tiefst- bis Hoechstwert, Strich = Mittel
// Ein Farbton (Akzent) fuer alle Werte, Beschriftung in der Textfarbe (--muted).
function sparkSvg(sp,W,H){
  if(!sp || sp.state!=='ok' || W<SPARK_MIN_W || H<18) return '';
  const f=n=>n.toFixed(1), dec=sp.dec||0, acc='var(--accent)';
  const txt=(x,y,t,anc,extra)=>'<text class="mm" x="'+f(x)+'" y="'+f(y)+'" text-anchor="'+(anc||'middle')+'"'+(extra||'')+'>'+esc(t)+'</text>';
  let s='';
  if(sp.style==='pattern'){
    const c=sp.cells||[], vs=c.filter(v=>v!=null); if(!vs.length) return '';
    let mn=sp.kind==='line'?Math.min(...vs):0, mx=Math.max(...vs); if(mx-mn<1e-9) mx=mn+1;
    const lab=H>=58?11:0, gap=W<150?.75:1.5, cw=(W-23*gap)/24, ch=Math.max(2,(H-lab-6*gap)/7);
    c.forEach((v,i)=>{ const d=Math.floor(i/24), h=i%24, x=h*(cw+gap), y=d*(ch+gap);
      s+= v==null
        ? '<rect x="'+f(x+.5)+'" y="'+f(y+.5)+'" width="'+f(cw-1)+'" height="'+f(ch-1)+'" rx="1.5" style="fill:none;stroke:var(--line)"/>'
        : '<rect x="'+f(x)+'" y="'+f(y)+'" width="'+f(cw)+'" height="'+f(ch)+'" rx="1.5" style="fill:'+acc+';opacity:'+(0.08+0.92*(v-mn)/(mx-mn)).toFixed(3)+'"/>'; });
    if(lab){ const y=H-1; s+=txt(0,y,'0 h','start')+txt(12*(cw+gap)-gap/2,y,'12 h')+txt(W,y,'24 h','end'); }
  } else if(sp.style==='span'){
    const sp7=sp.spans||[], ok=sp7.filter(Boolean); if(!ok.length) return '';
    let mn=Math.min(...ok.map(r=>r[0])), mx=Math.max(...ok.map(r=>r[1])); if(mx-mn<1e-9){ mn-=1; mx+=1; }
    const n=sp7.length, col=W/n, lab=(H>=48 && col>=16)?11:0, bw=Math.min(16,col*0.58), top=2, bot=H-lab-2;
    const Y=v=>bot-(v-mn)*(bot-top)/(mx-mn);
    sp7.forEach((r,i)=>{ const x=i*col+(col-bw)/2, today=i===n-1;
      if(r){ const y1=Y(r[1]), y0=Y(r[0]);
        s+='<rect x="'+f(x)+'" y="'+f(y1)+'" width="'+f(bw)+'" height="'+f(Math.max(3,y0-y1))+'" rx="'+f(Math.min(4,bw/2))+'" style="fill:'+acc+';opacity:'+(today?1:.3)+'"/>';
        if(r[2]!=null) s+='<line x1="'+f(x+2)+'" x2="'+f(x+bw-2)+'" y1="'+f(Y(r[2]))+'" y2="'+f(Y(r[2]))+'" style="stroke:'+(today?'var(--tile)':'var(--ink)')+';stroke-width:1.5;opacity:.75"/>'; }
      if(lab) s+=txt(i*col+col/2,H-1,(sp.days||[])[i]||'','middle',today?' style="fill:var(--ink);font-weight:600"':''); });
  } else {
    const p=sp.pts||[]; if(!p.length) return '';
    const t0=sp.t0, t1=sp.t1, span=Math.max(1,t1-t0), ln=sp.kind==='line';
    const vs=p.map(q=>q[1]); let mn=Math.min(...vs), mx=Math.max(...vs);
    if(sp.lo) mn=Math.min(mn,sp.lo[1]); if(sp.hi) mx=Math.max(mx,sp.hi[1]);
    if(!ln) mn=Math.min(0,mn); if(mx-mn<1e-9) mx=mn+1;
    const labs=ln&&H>=48, pt=labs?13:6, pb=labs?13:6, pl=ln?4:0, pr=ln?6:0;
    const X=t=>pl+(t-t0)*(W-pl-pr)/span, Y=v=>H-pb-(v-mn)*(H-pt-pb)/(mx-mn);
    if(sp.kind==='counter'){
      p.forEach(([t,v],i)=>{ const x=X(t), w=Math.max(1,(i+1<p.length?X(p[i+1][0]):W)-x-1.5), y=Y(v);
        s+='<rect x="'+f(x)+'" y="'+f(y)+'" width="'+f(w)+'" height="'+f(Math.max(0,Y(0)-y))+'" rx="1.5" style="fill:'+acc+';opacity:.85"/>'; });
    } else if(sp.kind==='digital'){
      let d='M'+f(X(p[0][0]))+' '+f(Y(p[0][1]));
      p.forEach(([t,v],i)=>{ const tn=i+1<p.length?p[i+1][0]:t1; d+=' H'+f(X(tn))+(i+1<p.length?' V'+f(Y(p[i+1][1])):''); });
      s='<path d="'+d+' V'+f(Y(0))+' H'+f(X(p[0][0]))+' Z" style="fill:'+acc+';opacity:.22"/>'+
        '<path d="'+d+'" style="fill:none;stroke:'+acc+';stroke-width:2"/>';
    } else {
      const line=p.map(([t,v])=>f(X(t))+','+f(Y(v))).join(' ');
      s='<polygon points="'+f(X(p[0][0]))+','+f(H)+' '+line+' '+f(X(p[p.length-1][0]))+','+f(H)+'" style="fill:'+acc+';opacity:.12"/>'+
        '<polyline points="'+line+'" style="fill:none;stroke:var(--muted);stroke-width:1.6;stroke-linejoin:round;stroke-linecap:round"/>';
      const mark=(q,above)=>{ const x=X(q[0]), y=Y(q[1]), a=x<18?'start':(x>W-18?'end':'middle');
        return '<circle cx="'+f(x)+'" cy="'+f(y)+'" r="3" style="fill:var(--tile);stroke:var(--ink);stroke-width:1.4"/>'+
               (labs?txt(x,above?y-5.5:y+12,chNum(q[1],dec),a):''); };
      if(sp.hi) s+=mark(sp.hi,true);
      if(sp.lo && (!sp.hi || sp.lo[0]!==sp.hi[0])) s+=mark(sp.lo,false);
      const q=p[p.length-1];
      s+='<circle cx="'+f(X(q[0]))+'" cy="'+f(Y(q[1]))+'" r="4.5" style="fill:'+acc+';stroke:var(--tile);stroke-width:2"/>';
    }
  }
  return '<svg viewBox="0 0 '+f(W)+' '+f(H)+'" width="'+f(W)+'" height="'+f(H)+'" aria-hidden="true">'+s+'</svg>';
}
// Mini-Verlauf in seinen Platz zeichnen; nur neu, wenn sich Daten oder Groesse aendern.
const SPARK_MIN_H=36;   // px: niedrigere Mitte -> Verlauf in die Kopfzeile (enge Kachel)
// Schmaler zeichnet sparkSvg() keinen Verlauf: sieben Tagesbalken auf 27 px
// waeren Rauschen (so breit blieb der Kopf einer 120-px-Kachel bei Faktor 0,85,
// vorher unter 24 px -> keiner). Absolute Pixel wie SPARK_MIN_H.
const SPARK_MIN_W=40;
// ---- Kachelfaktor ----
// Der Inhalt einer Kachel waechst mit ihrer Breite: Faktor = Breite / KACHEL_REF,
// begrenzt auf KS_MIN..KS_MAX, als --ks am .screen (CSS multipliziert damit
// Symbol, Schrift, Tasten, Innenabstand, Ring, Mini-Verlauf und Kopfzeile).
// Vorher standen 16-px-Schrift und 38-px-Symbol auf jeder Kachel, ob 122 oder
// 628 px breit. Im automatischen Raster kommt die Breite aus autoRaster(),
// beim festen Raster aus der ersten Kachel nach dem Aufbau (kachelBreiteGemessen).
const {KACHEL_REF, KACHEL_REF_H, KS_MIN, KS_MAX, KOPF_H, LEISTE_H}=LoxRaster;   // raster.js, gemeinsam mit dem Konfigurator
// Standardgroessen je Kachel-Aufbau, wie GROESSEN_STANDARD im Server (gelten,
// wenn der Kasten keine --ico-size usw. traegt)
const GROESSEN_STANDARD = {neu: {iconSize: 38, nameSize: 16, subSize: 14, roomSize: 13},
                           classic: {iconSize: 38, nameSize: 18, subSize: 15, roomSize: 12}};
let kachelFaktor=1;
// Breite UND Hoehe zaehlen (Rechnung in raster.js): eine flache Kachel (2x3 auf
// dem 4"-Panel: 225 x 128) traegt sonst die Schrift ihrer Breite und laeuft unten ueber.
function kachelFaktorFuer(breite, hoehe){ return LoxRaster.kachelFaktorFuer(breite, hoehe); }
function setzeFaktor(ks){
  const sc=document.querySelector('.screen'); if(!sc) return;
  kachelFaktor=ks;
  sc.style.setProperty('--ks', ks.toFixed(3));
  sc.style.setProperty('--ksg', ks.toFixed(3));   // Faktor der Seite fuer die Tasten, auch wo eine Kachel --ks selbst setzt
  sc.style.setProperty('--kst-min', ks>=1 ? '1' : '0.6');   // Untergrenze der Textstufen (s. fitTile)
  sc.style.setProperty('--kopf-h', Math.round(KOPF_H*ks)+'px');
  sc.style.setProperty('--leiste-h', Math.round(LEISTE_H*ks)+'px');   // Werteleiste waechst mit
  kopfEinpassen();   // Schrift und Hoehe der Kopfzeile haengen am Faktor: neu einpassen
}
function kachelGemessen(){ const g=el('grid');
  const t=g.querySelector('.tile[data-id]:not(.w2)')||g.querySelector('.tile[data-id]');
  if(!t) return kachelFaktor;
  // nur breite Kacheln auf der Seite: eine misst sich als die schmale, die sie ersetzt
  const gap=parseFloat(getComputedStyle(g).getPropertyValue('--gap'))||0;
  return kachelFaktorFuer(t.classList.contains('w2') ? (t.clientWidth-gap)/2 : t.clientWidth, t.clientHeight); }
// Festes Raster: Faktor aus der ersten Kachel. Mit Kopfzeile haengt die
// Kachelhoehe an --kopf-h und die wieder am Faktor (Codex-Befund: einmal
// gemessen hing der Faktor an der Seite davor, deren Faktor die Kopfzeile
// noch hatte). Darum nachmessen, bis er steht: die Kopfzeile wiegt
// KOPF_H * Faktor auf zwei oder drei Zeilen, zwei Durchgaenge reichen.
function faktorEinmessen(){
  for(let i=0;i<4;i++){
    const ks=kachelGemessen();
    if(Math.abs(ks-kachelFaktor)<0.005) return;
    setzeFaktor(ks);
  }
}
// Nach einer Groessenaenderung ohne neues Raster (Fenster, Split an/aus): Faktor
// neu, und die Kacheln messen sich mit den neuen Groessen noch einmal ein.
// Kachelhoehe beim letzten Einpassen: im festen, breitenbegrenzten Raster
// kann sie sich mit dem Fenster aendern, ohne dass der Faktor es tut
// (Codex-Befund an #128) - dann passen Tasten und Text trotzdem neu.
// Mass der ersten Kachel (Breite x Hoehe): aendert es sich, misst faktorNachziehen neu - auch
// bei reiner Breitenaenderung (Tasten der Spieler-Spalte, Textumbruch), wo Faktor und Hoehe bleiben
let _kachelM='';
function kachelMass(){ const t=el('grid').querySelector('.tile[data-id]'); return t ? t.clientWidth+'x'+t.clientHeight : ''; }
function faktorNachziehen(){
  if(!view || view.widget || el('grid').classList.contains('panel')) return;
  const vorher=kachelFaktor;
  if(gridAuto){ const ks=autoRaster(_lastWidget).ks; if(Math.abs(ks-vorher)>=0.01) setzeFaktor(ks); }
  else faktorEinmessen();
  if(Math.abs(kachelFaktor-vorher)>=0.01 || kachelMass()!==_kachelM) kachelnNeuMessen();
}
function kachelnNeuMessen(){
  _kachelM=kachelMass();
  el('grid').querySelectorAll('.tile[data-id]').forEach(n=>{
    n._fitText=null;
    if(n._it && n._it.controls) tastenEinpassen(n);
    if(n._it && n._it.spark){ const sp=n.querySelector('.tspark'); if(sp) paintSpark(sp, n._it.spark); }
    fitTile(n);
  });
}
function paintSpark(el,sp){
  if(!el) return;
  const tile=el.closest('.tile');
  placeSpark(el,sp,tile);
  // Angabe im Kopf abgeschnitten -> in die Raumzeile (nur ohne enge Kachel, dort steht sie ohnehin da).
  // Ohne Raumzeile kommt die Zeile dabei neu dazu oder faellt weg: dann hat
  // die Mitte eine andere Hoehe, Platz und Zeichnung also neu bestimmen.
  const bd=tile&&tile.querySelector('.tsbadge');
  if(bd){
    const vorher=tile.classList.contains('sparkbadge');
    tile.classList.remove('sparkbadge');
    if(!tile.classList.contains('sparktight') && bd.scrollWidth>bd.clientWidth+1) tile.classList.add('sparkbadge');
    if(vorher!==tile.classList.contains('sparkbadge')) placeSpark(el,sp,tile);
  }
}
// Freie Mitte fuer den Verlauf = Innenhoehe der Kachel minus alles ausser dem
// Verlauf (und seinem Rand). Gleich, ob der Verlauf gerade in der Mitte oder
// im Kopf steht: dort gibt das Symbol die Hoehe vor, er fuellt sie nur.
function sparkFrei(tile,el){
  const cs=getComputedStyle(tile);
  let free=tile.clientHeight-parseFloat(cs.paddingTop)-parseFloat(cs.paddingBottom)-10;
  for(const ch of tile.children) if(ch!==el) free-=ch.offsetHeight;
  return free;
}
// Verlauf in die Mitte oder (zu niedrige Mitte) in die Kopfzeile setzen und zeichnen.
function placeSpark(el,sp,tile){
  const head=tile&&tile.querySelector('.head');
  if(head){
    const tight=sparkFrei(tile,el)<SPARK_MIN_H;   // absolute Pixel: eine Kurve braucht Hoehe, nicht den Faktor
    if(tight!==tile.classList.contains('sparktight') || tight!==(el.parentNode===head)){
      tile.classList.toggle('sparktight',tight);
      if(tight) head.insertBefore(el,head.firstElementChild.nextSibling);
      else tile.insertBefore(el,head.nextSibling);
      el.innerHTML=''; el._key=null;
    }
  }
  const W=el.clientWidth, H=el.clientHeight, key=W+'x'+H+JSON.stringify(sp);
  if(el._key!==key){ el._key=key; el.innerHTML=sparkSvg(sp,W,H); }
}
// Tasten der Kachel (it.controls) nur, wenn die Kachel hoch genug ist - aus
// dem Faktor, nicht gemessen: Kopf, zwei Textzeilen, Abstaende und Innenrand
// brauchen TASTEN.text mal Faktor, die Tastenleiste TASTEN.leiste mal
// max(1, Faktor der Seite) - Touch-Ziele schrumpfen nie. Die Kachel nimmt den
// Faktor, bei dem beides in ihre Hoehe passt (hoechstens den der Seite; steht
// als --ks an der Kachel, die Tasten bleiben ueber --ksg in Seitengroesse).
// Liegt er unter KS_MIN, bleiben die Tasten weg, und der Tipp auf die Kachel
// oeffnet die Detailseite (nav). Das loest die flache Kachel (drei Zeilen am
// 4"-Panel) ohne Sonderfaelle: frueher rueckten die Tasten dort in den Kopf
// neben das Symbol (ctrltight) oder an seine Stelle (ctrlnarrow), je Text
// gemessen. Der Platz fuer Kopf und Text kommt aus den EINGESTELLTEN
// Groessen (Symbol, Haupt-, Zweit- und Raumtext: GROESSEN_STANDARD oder
// das Profil, als --ico-size usw. am Kasten, Codex-Befund an #128: ein
// Profil mit 80-px-Symbol braucht mehr), dazu die festen Anteile aus dem CSS
// bei Faktor 1 - neuer Aufbau: Innenrand 2 x 14, Kopf = Symbol (oder die
// Raumzeile daneben), Abstand 10, zwei Zeilen mit Zeilenhoehe 1,15 und 1,3,
// Abstand zur Leiste 10 (mit den Standardgroessen 130 vor 44 Leiste);
// klassisch: 2 x 16, Symbol, Raumzeile, zwei Zeilen, 6 (122 vor 34).
// Listen (Zonen einer Zentrale) haben ihre Tasten neben dem Text: immer.
const TASTEN = {lx: {rand: 55, leiste: 44}, classic: {rand: 30, leiste: 34}};
function tastenTextHoehe(tile){
  const cs=getComputedStyle(tile), px=(n,d)=>parseFloat(cs.getPropertyValue(n))||d;
  const lx=kachelNeu(), g=lx ? GROESSEN_STANDARD.neu : GROESSEN_STANDARD.classic;
  const name=px('--name-size',g.nameSize), sub=px('--sub-size',g.subSize), raum=px('--room-size',g.roomSize);
  // Aufbau "kreis" (Kachel-Set): der Kopf ist so hoch wie der Kreis um das Symbol
  const ico=Math.max(px('--ico-size',g.iconSize), kachelAufbau==='kreis' ? px('--k-kreis',0) : 0);
  return lx ? Math.max(ico, 1.2*raum) + 1.15*name + 1.3*sub + TASTEN.lx.rand
            : ico + 1.2*raum + 1.15*name + 1.3*sub + TASTEN.classic.rand;
}
function tastenFaktor(tile){
  const t = kachelNeu() ? TASTEN.lx : TASTEN.classic;
  return Math.min(kachelFaktor, (tile.clientHeight - t.leiste*Math.max(1, kachelFaktor)) / tastenTextHoehe(tile));
}
// Spieler-Spalte (.spieler): die Tasten stehen neben dem Text, die Kachel
// braucht nur die Hoehe einer Tastenleiste, das Cover darueber mindestens
// SPIELER_COVER_MIN mal Faktor, sonst faellt es weg (.ohnecover). Die Spalte
// ist die halbe Kachel; passen die Tasten dort nicht in ihrer Mindestbreite
// (TASTE_MIN wie .tctrls .tb, mal max(1, Faktor der Seite), dazu die Abstaende
// der Leiste), wird sie so breit wie noetig (.spbreit, --spw) - Touch-Ziele
// schrumpfen nie.
const SPIELER_COVER_MIN = 36, TASTE_MIN = 34;
function spielerEinpassen(tile, tc){
  tile._kt=null; tile.style.removeProperty('--ks');   // gemessen wird mit dem Faktor der Seite
  const cs=getComputedStyle(tile), pad=parseFloat(cs.paddingTop);
  const innen=tile.clientHeight-pad-parseFloat(cs.paddingBottom);
  const n=tc.querySelectorAll('.tb').length, abstand=parseFloat(getComputedStyle(tc).columnGap)||0;
  const noetig=n*TASTE_MIN*Math.max(1, kachelFaktor)+(n-1)*abstand, halb=tile.clientWidth/2-parseFloat(cs.paddingRight);
  tile.classList.toggle('spbreit', noetig>halb+0.5);
  if(noetig>halb+0.5) tile.style.setProperty('--spw', noetig.toFixed(1)+'px'); else tile.style.removeProperty('--spw');
  // Abstand zwischen Cover und Tasten, wie ihn die Spalte tatsaechlich hat: --spgap ist ein
  // calc() (10px mal Faktor), das parseFloat nicht liest - der aufgeloeste row-gap schon
  const sp=tile.querySelector('.tplay'), gap=sp ? (parseFloat(getComputedStyle(sp).rowGap)||0) : 0;
  const leiste=TASTEN.lx.leiste*Math.max(1, kachelFaktor);
  const an=innen>=leiste-0.5;
  tc.hidden=!an; tile.classList.toggle('ohnetasten', !an);
  tile.classList.toggle('ohnecover', !an || innen-leiste-gap < SPIELER_COVER_MIN*kachelFaktor);
}
function tastenEinpassen(tile){
  const tc=tile&&tile.querySelector('.tctrls'); if(!tc || !tile.clientHeight) return;
  if(view && view.layout==='list'){ tc.hidden=false; tile._kt=null; tile.style.removeProperty('--ks'); return; }
  if(tile.classList.contains('spieler')){ spielerEinpassen(tile, tc); return; }
  const kt=tastenFaktor(tile), an=kt>=KS_MIN-0.005;
  tc.hidden=!an; tile.classList.toggle('ohnetasten', !an);
  tile._kt = (an && kt<kachelFaktor-0.005) ? +kt.toFixed(3) : null;
  if(tile._kt) tile.style.setProperty('--ks', String(tile._kt)); else tile.style.removeProperty('--ks');
}
// Neuer Aufbau, enge Kachel: laeuft der Text unten aus der Kachel, weicht
// Stufe fuer Stufe das Unwichtigste - erst steht der Text einzeilig (eng1),
// dann faellt die Angabe zum Mini-Verlauf weg (eng2), zuletzt die zweite Zeile
// (eng3). Gemessen bei neuer Kachel, neuem Text, neuer Groesse oder neuem Faktor.
function fitTile(tile){
  if(!tile || !tile.clientHeight) return;
  const text=(tile.querySelector('.body')||{}).textContent, h=tile.clientHeight, w=tile.clientWidth;
  if(tile._fitText===text && tile._fitH===h && tile._fitW===w && tile._fitKs===kachelFaktor && tile._fitKt===tile._kt) return;
  tile._fitText=text; tile._fitH=h; tile._fitW=w; tile._fitKs=kachelFaktor; tile._fitKt=tile._kt;
  tile.classList.remove('eng1','eng2','eng3','kst1','kst2','kst3');
  // Textfaktor: passt eine Textzeile der Kachel (Name oder Zustand) nicht in
  // ihre Zeilen - gekappt durch line-clamp, im klassischen Aufbau mit "..." -,
  // bekommt der Text Stufe fuer Stufe weniger Faktor (kst1..kst3, CSS). Ueber
  // Faktor 1 geht es hoechstens auf 1 zurueck, den Stand ohne Faktor; auf
  // kleiner Kachel (Faktor unter 1) auch darunter: ein kleiner, ganzer Text
  // liest sich besser als ein grosser mit "...". Symbol und Tasten behalten
  // ihre Groesse.
  const texte=[...tile.querySelectorAll('.body .name, .body .sub')];
  const passt=()=>texte.every(e=>e.scrollHeight<=e.clientHeight+1 && e.scrollWidth<=e.clientWidth+1);
  const STUFEN=['kst1','kst2','kst3'];
  const setzeStufe=s=>{ tile.classList.remove(...STUFEN); if(s) tile.classList.add(s); };
  const textStufen=()=>{ if(!texte.length) return;
    setzeStufe(null);
    for(const stufe of STUFEN){
      if(passt()) break;
      setzeStufe(stufe);
    } };
  // Mini-Verlauf: ueber Faktor 1 gibt der Text seinen Zuwachs her (hoechstens
  // bis Faktor 1, s. --kst-min), wenn ein Zustand, der mit dem Faktor auf zwei
  // Zeilen ging ("4,200 kW • 9,1 MWh" auf der 200-px-Kachel), damit wieder in
  // EINE passt und der Verlauf so seine Mindesthoehe in der Mitte bekommt.
  // Eine Stufe, die nur die Schrift verkleinert, ohne eine Zeile zu loesen,
  // zaehlt nicht: sie braechte die Mitte hoechstens knapp ueber die Schwelle
  // und einen gequetschten Verlauf. Bringt keine Stufe eine Zeile zurueck,
  // bleibt der Text gross und placeSpark() setzt den Verlauf in den Kopf.
  const zeilen=()=>texte.reduce((n,e)=>{ const r=document.createRange(); r.selectNodeContents(e); return n+r.getClientRects().length; },0);
  const sparkStufen=()=>{
    const sp=tile.querySelector('.tspark');
    if(!sp || !tile.querySelector('.head') || kachelFaktor<=1 || sparkFrei(tile,sp)>=SPARK_MIN_H) return;
    const vorher=STUFEN.find(s=>tile.classList.contains(s))||null, z0=zeilen();
    for(let i=STUFEN.indexOf(vorher)+1; i<STUFEN.length; i++){
      setzeStufe(STUFEN[i]);
      if(zeilen()<z0 && sparkFrei(tile,sp)>=SPARK_MIN_H) return;
    }
    setzeStufe(vorher);
  };
  textStufen();
  if(kachelNeu()){
    for(const stufe of ['eng1','eng2','eng3']){
      if(tile.scrollHeight<=h+1) break;
      tile.classList.add(stufe);
    }
    textStufen();   // eng1 kappt den Text auf eine Zeile: dann lieber kleiner und ganz
  }
  sparkStufen();
  // Die Stufen aendern die Hoehe der Mitte: der Verlauf findet seinen Platz neu
  // (Mitte oder Kopf); ohne Aenderung zeichnet placeSpark() nichts neu.
  if(tile._it && tile._it.spark) paintSpark(tile.querySelector('.tspark'), tile._it.spark);
}
function paintCharts(g,blocks){
  const els=[...g.querySelectorAll('[data-chart]')];
  blocks.filter(b=>b.k==='chart').forEach((b,i)=>{ if(els[i]) paintChart(els[i],b); });
}
function renderPanel(blocks){
  blocks=intercomBlocks(blocks);
  stopVideo();
  closeMenu();
  document.querySelectorAll('.galov').forEach(o=>o.remove());
  setMore((blocks.find(b=>b.k==='more')||{}).route||null);
  el('grid').classList.add('panel');
  el('grid').classList.remove('list','snapy','scheme','fronttab','lx','hpages','punkte','fuss','haus');
  el('grid').classList.toggle('bigpage', blocks.some(b=>b.k==='big'));
  el('grid').classList.toggle('chartpage', blocks.some(b=>b.k==='chart'));
  el('grid').classList.toggle('intercom-page', blocks.some(b=>b.k==='intercom-talk'));
  const g=el('grid');
  // anchor:bottom -> Anzeige (big/status) oben zentriert, Bedienung unten
  // verankert; aufklappende Auswahl waechst dann nach oben ueber die festen Zeilen.
  const anchorBot = !!(view && view.anchor==='bottom');
  g.classList.toggle('anchorbot', anchorBot);
  const TOPK = {hero:1,cover:1,video:1,status:1,title:1,value:1,big:1,astat:1,eflow:1};
  const bh = b => {
    if(b.k==='eflow') return '<div class="epane-detail" data-eflow></div>';   // Radial; wird nach dem Einfuegen von paintEnergy gefuellt
    if(b.k==='hero'){ const hic = b.iconImg
        ? '<img class="rawico" src="'+esc(b.iconImg)+'" alt="">'
        : b.iconUrl
        ? '<span class="himg" style="--u:url(\''+esc(b.iconUrl)+'\')"></span>'
        : svg(ICONS[b.icon]||ICONS.info);
      return '<div class="hero"><div class="circle">'+hic+'</div></div>'; }
    if(b.k==='cover') return '<div class="cover"><div class="coverph">'+svg(ICONS.music)+'</div><img id="coverimg" alt=""></div>';
    if(b.k==='video') return '<div class="video"><img alt=""></div>';
    if(b.k==='web') return '<div class="webframe"><iframe src="'+esc(b.url||'')+'" referrerpolicy="no-referrer"></iframe></div>';
    if(b.k==='status') return '<div class="status">'+esc(b.text||'')+'</div>';
    if(b.k==='title') return '<div class="ptitle">'+esc(b.text||'')+'<div class="psub">'+esc(b.sub||'')+'</div></div>';
    if(b.k==='value') return '<div class="pbar">'+esc(b.text||'')+'</div>';
    if(b.k==='big') return '<div class="pbig'+(b.tone==='good'?' good':(b.tone==='crit'?' crit':''))+'">'+esc(b.text||'')+'</div>';
    if(b.k==='astat') return '<div class="astat'+(b.tone==='crit'?' crit':'')+'">'+esc(b.text||'')+(b.sub?'<div class="astatsub">'+esc(b.sub)+'</div>':'')+'</div>';
    if(b.k==='slider') return '<div class="srow"><span class="sico">'+svg(ICONS[b.icon]||ICONS.vol)+'</span><button type="button" class="sbtn" data-sd="dn">−</button><input type="range" class="sld" min="'+b.min+'" max="'+b.max+'"'+(b.step?' step="'+b.step+'"':'')+' value="'+b.value+'"><button type="button" class="sbtn" data-sd="up">+</button><span class="sval">'+b.value+'</span></div>';
    if(b.k==='row') return '<div class="brow'+(b.cells.some(c=>c.icon)?' transport':'')+(b.wrap?' wraprow':'')+(b.hidden?' collapsed':'')+'"'+(b.id?' data-rowid="'+esc(b.id)+'"':'')+'>'+b.cells.map(cellHtml).join('')+'</div>';
    if(b.k==='intercom-talk') return intercomTalkHtml(b);
    if(b.k==='head') return '<div class="phead">'+esc(b.text||'')+'</div>';
    if(b.k==='chart') return chartBoxHtml(b);   // Inhalt zeichnet paintChart nach dem Einfuegen
    if(b.k==='favs') return '<div class="favs'+(b.wrap?' wrap':'')+'">'+b.items.map((f,i)=>'<div class="fav" data-f="'+i+'"><div class="favc">'+(f.cover?'<img loading="lazy" src="'+esc(f.cover)+'" alt="">':svg(ICONS.music))+'</div><div class="favn">'+esc(f.label)+'</div></div>').join('')+'</div>';
    if(b.k==='alarmlist'){
      if(!b.entries||!b.entries.length) return '<div class="status alist-empty">Keine Weckzeiten angelegt</div>';
      return '<div class="alist">'+b.entries.map((e,i)=>
        '<div class="arow'+(e.active?'':' off')+(e.nav?' tap':'')+'" data-a="'+i+'">'+
          (e.cmd?'<span class="asw'+(e.active?' on':'')+'"></span>':'<span class="adot"></span>')+
          '<span class="anm">'+esc(e.name)+'</span>'+
          '<span class="atime">'+esc(e.hm)+'</span>'+
          (e.repeat?'<span class="arep">'+esc(e.repeat)+'</span>':'')+
        '</div>').join('')+'</div>';
    }
    if(b.k==='stepper') return '<div class="stp"><div class="stpl">'+esc(b.label||'')+
        (b.sub?'<div class="stps">'+esc(b.sub)+'</div>':'')+'</div>'+
        (b.cmd?'<button type="button" class="sbtn" data-st="-1">−</button>':'')+
        '<span class="stpv">'+esc(stpText(b,b.value))+'</span>'+
        (b.cmd?'<button type="button" class="sbtn" data-st="1">+</button>':'')+'</div>';
    if(b.k==='field') return '<label class="fld">'+esc(b.label||'')+
        '<input type="text" autocomplete="off" data-f="'+esc(b.name)+'" value="'+esc(b.value||'')+'"></label>';
    if(b.k==='timepick'){ const z=(+b.value||0)%86400, p=n=>String(n).padStart(2,'0');
      const teil=(u,v)=>'<div class="tpc" data-u="'+u+'"><button type="button" class="sbtn" data-d="1">'+svg(ICONS.up)+
        '</button><span class="tpv">'+p(v)+'</span><button type="button" class="sbtn" data-d="-1">'+svg(ICONS.down)+'</button></div>';
      return '<div class="tpk" data-f="'+esc(b.name)+'" data-v="'+z+'">'+teil('h',Math.floor(z/3600))+
        '<span class="tpsep">:</span>'+teil('m',Math.floor(z%3600/60))+'</div>'; }
    if(b.k==='chips') return '<div class="chipset" data-f="'+esc(b.name)+'"'+(b.multi?' data-multi="1"':'')+'>'+
        (b.items||[]).map(c=>'<div class="chp'+(c.on?' on':'')+'" data-v="'+esc(String(c.v))+'">'+esc(c.label)+'</div>').join('')+'</div>';
    if(b.k==='gallery') return '<div class="gal">'+(b.items||[]).map((it,i)=>'<figure class="gimg" data-g="'+i+'">'+
        '<img loading="lazy" alt="" src="'+esc(it.src)+'"><figcaption>'+esc(it.label||'')+'</figcaption></figure>').join('')+'</div>';
    return '';
  };
  if(anchorBot){
    let top='',bot='';
    for(const b of blocks){ if(b.k==='more')continue; if(TOPK[b.k]) top+=bh(b); else bot+=bh(b); }
    g.innerHTML='<div class="pantop">'+top+'</div><div class="panbot">'+bot+'</div>';
  } else {
    let html='';
    for(const b of blocks){ if(b.k!=='more') html+=bh(b); }
    g.innerHTML=html;
  }
  const efb=blocks.find(b=>b.k==='eflow'); if(efb){ const d=g.querySelector('[data-eflow]'); if(d) paintEnergy(d, efb.e); }   // Radial in der Detailansicht zeichnen
  paintCharts(g,blocks);
  // Zeitraum-Wahl: die aktuelle Seite mit anderem Zeitraum ERSETZEN, nicht
  // stapeln - sonst fuellte jeder Wechsel den Zurueck-Stapel.
  g.querySelectorAll('.chrng [data-rng]').forEach(btn=>btn.addEventListener('pointerdown',ev=>{ ev.preventDefault();
    const top=stack[stack.length-1]; if(!top) return;
    const r=Object.assign({},top,{range:btn.dataset.rng}); stack[stack.length-1]=r; send({t:'nav',route:r}); }));
  const cov=blocks.find(b=>b.k==='cover'); if(cov){const img=g.querySelector('#coverimg'); if(img){img.onload=()=>img.style.opacity='1'; img.onerror=()=>img.style.opacity='0'; img.src=cov.src;}}
  const vid=blocks.find(b=>b.k==='video'); const vimg=g.querySelector('.video img');
  if(vid&&vimg){ vimg.src=vid.src; }   // MJPEG-Stream: einmal laden, läuft live
  const sb=blocks.find(b=>b.k==='slider'); const sld=g.querySelector('.sld');
  if(sb&&sld){ sld._uuid=sb.cmd.uuid; sld._tmpl=sb.cmd.tmpl; sldFill(sld);
    // PIN abgebrochen: Regler wieder auf den Stand des Servers
    const zurueck=()=>{ if(view&&view.blocks&&el('grid').classList.contains('panel')) updatePanel(view.blocks); };
    sld.addEventListener('input',()=>{ sldDragging=true; sldFill(sld); const sv=g.querySelector('.sval'); if(sv)sv.textContent=sld.value; });
    sld.addEventListener('change',()=>{ sldDragging=false; sendCmd(sld._uuid,sld._tmpl.replace('{v}',sld.value),view&&view.secured,{abbruch:zurueck}); });
    const sdn=g.querySelector('.srow .sbtn[data-sd="dn"]'), sup=g.querySelector('.srow .sbtn[data-sd="up"]');
    const step=(sb.step&&+sb.step>0)?+sb.step:SLD_STEP;
    if(sdn) sdn.addEventListener('pointerdown',ev=>{ ev.preventDefault(); nudgeSld(sld,-step,g.querySelector('.sval'),view&&view.secured,zurueck); });
    if(sup) sup.addEventListener('pointerdown',ev=>{ ev.preventDefault(); nudgeSld(sld,step,g.querySelector('.sval'),view&&view.secured,zurueck); });
  }
  const rows=[...g.querySelectorAll('.brow')]; let ri=0;
  for(const b of blocks){ if(b.k!=='row') continue; const rowEl=rows[ri++];
    b.cells.forEach((c,ci)=>{ const btn=rowEl.querySelector('[data-c="'+ci+'"]'); if(!btn)return;
      bindCell(btn,c);
      btn._secured=!!c.secured;   // gesichertes Ziel (verlinkte Objekte): PIN wie auf seiner eigenen Seite
      btn.addEventListener('pointerdown',ev=>{ ev.preventDefault();
        if(btn._menu){ openMenu(btn,btn._menu); return; }
        if(btn._tippen) return;
        if(btn._cmd) sendCmd(btn._cmd.uuid,btn._cmd.cmd,(view&&view.secured)||btn._secured,(btn._hold&&btn._release)?{los:btn._release}:null);
      });
      btn.addEventListener('click',()=>{ if(btn._tippen && !btn._menu) zelleTippen(g,btn); });
    });
  }
  // Werte mit -/+, Formular (Weckzeit), Bilder, Weckzeiten-Liste
  const stps=[...g.querySelectorAll('.stp')];
  blocks.filter(b=>b.k==='stepper').forEach((b,i)=>{ if(stps[i]) stepperBind(stps[i],b); });
  formBind(g);
  const gb=blocks.find(b=>b.k==='gallery');
  if(gb) g.querySelectorAll('.gal .gimg').forEach(n=>{
    // Bild fehlt beim Miniserver: dunkle Flaeche statt Symbol fuer kaputtes Bild
    const img=n.querySelector('img'); if(img) img.addEventListener('error',()=>{ img.style.visibility='hidden'; });
    n.addEventListener('click',()=>{ const it=gb.items[+n.dataset.g]; if(it) bildZeigen(it); }); });
  const ab=blocks.find(b=>b.k==='alarmlist');
  if(ab&&ab.entries) g.querySelectorAll('.arow[data-a]').forEach(n=>{ const e=ab.entries[+n.dataset.a]; if(!e) return;
    const sw=n.querySelector('.asw');
    if(sw&&e.cmd) sw.addEventListener('click',ev=>{ ev.stopPropagation(); sw.classList.toggle('on');
      sendCmd(e.cmd.uuid,e.cmd.cmd,view&&view.secured,{abbruch:()=>sw.classList.toggle('on',!!e.active)}); });
    if(e.nav) n.addEventListener('click',()=>nav(e.nav)); });
  const fb=blocks.find(b=>b.k==='favs'); const fe=g.querySelector('.favs');
  if(fb&&fe){ fe.querySelectorAll('.fav').forEach(n=>{ const f=fb.items[+n.dataset.f]; if(!f)return;
    // Wie die Tasten auf der Kachel erst beim Tippen: die Favoriten liegen im
    // scrollenden Raster, ein Wischer darueber startet sonst einen Sender.
    n.addEventListener('click',()=>{ if(f.cmd) sendCmd(f.cmd.uuid,f.cmd.cmd,view&&view.secured,{ok:back}); }); }); }
  g.dataset.bsig=blockSig(blocks);   // Grundlage fuer den In-place-Abgleich in updatePanel
  intercomBind(g);
  renderTabs();
  panelEinpassen();
}
function panelEinpassen(){
  const g=el('grid'); if(!g.classList.contains('panel')) return;
  g.classList.remove('eng');
  if(g.scrollHeight>g.clientHeight+1) g.classList.add('eng');
}
function updatePanel(blocks){
  blocks=intercomBlocks(blocks);
  const g=el('grid');
  // Struktur anders als zuletzt gerendert (Zeile/Status/Favorit dazu oder weg,
  // Favoriten per roomfav/get nachgeliefert)? Dann komplett neu aufbauen.
  if(g.dataset.bsig!==blockSig(blocks)){ renderPanel(blocks); return; }
  const rowBlocks=blocks.filter(b=>b.k==='row');
  const rows=[...g.querySelectorAll('.brow')];
  // Ab hier ist die Struktur nachweislich identisch -> jeden Block an SEINER
  // Position patchen, nicht nur den ersten seiner Art: Detailseiten wie die
  // Sauna haben mehrere Status-Zeilen (Tuer, Wasser, Stoerung ...), die sonst
  // auf dem Stand des ersten Renderns einfrieren.
  const nth=(k,sel,fn)=>{ const es=[...g.querySelectorAll(sel)];
    blocks.filter(b=>b.k===k).forEach((b,i)=>{ if(es[i]) fn(es[i],b); }); };
  nth('status','.status:not(.alist-empty)',(e,b)=>{ e.textContent=b.text||''; });
  nth('value','.pbar',(e,b)=>{ e.textContent=b.text||''; });
  nth('big','.pbig',(e,b)=>{ e.textContent=b.text||''; e.className='pbig'+(b.tone==='good'?' good':(b.tone==='crit'?' crit':'')); });
  nth('title','.ptitle',(e,b)=>{ e.childNodes[0].nodeValue=b.text||''; const su=e.querySelector('.psub'); if(su)su.textContent=b.sub||''; });
  nth('astat','.astat',(e,b)=>{ e.childNodes[0].nodeValue=b.text||''; e.className='astat'+(b.tone==='crit'?' crit':''); const su=e.querySelector('.astatsub'); if(su)su.textContent=b.sub||''; });
  const cov=blocks.find(b=>b.k==='cover'); if(cov){const img=g.querySelector('#coverimg'); if(img&&img.getAttribute('src')!==cov.src){img.style.opacity='0'; img.onload=()=>img.style.opacity='1'; img.onerror=()=>img.style.opacity='0'; img.src=cov.src;}}
  const sb=blocks.find(b=>b.k==='slider'); if(sb){const sld=g.querySelector('.sld'); if(sld&&!sldDragging){ sld.value=sb.value; sldFill(sld); const sv=g.querySelector('.sval'); if(sv)sv.textContent=sb.value; }}
  const efb=blocks.find(b=>b.k==='eflow'); if(efb){ const d=g.querySelector('[data-eflow]'); if(d) paintEnergy(d, efb.e); }   // Radial live aktualisieren (in-place)
  paintCharts(g,blocks);   // Verlauf nachgeladen oder Fenster vorgerueckt: neu zeichnen, Knoepfe bleiben
  rowBlocks.forEach((b,ri)=>{ const rowEl=rows[ri]; if(!rowEl)return;
    b.cells.forEach((c,ci)=>{ const btn=rowEl.querySelector('[data-c="'+ci+'"]'); if(!btn)return;
      if(c.icon) btn.innerHTML=svgF(ICONS[c.icon]||ICONS.info);
      else if(btn._armed) btn._label=c.label;     // Rueckfrage bleibt stehen
      else btn.textContent=c.label;
      btn.className=cellCls(c)+(btn._armed?' arm':'');
      bindCell(btn,c);
    });
  });
  nth('stepper','.stp',(e,b)=>stepperUpdate(e,b));
  formPruefen(g);
  intercomBind(g);
}

