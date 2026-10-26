// LoxPanel-Visu, Teil 8 von 12: Uhr, Screensaver-Inhalte, Kalender, Wetter, Energie, Kamera, Pane 2.
// Die Teile laden nacheinander aus panel.html (script src), alle Funktionen sind global;
// was beim Laden ausgefuehrt wird, darf nur Funktionen frueherer Teile rufen.

// ---- Screensaver: Uhr als Startseite, Tippen -> Favoriten ----
const SAVER_IDLE_MS = 60000;   // nach 60 s Inaktivitaet zurueck zur Uhr
let idleTimer=null;
// Minute, in der tickClock die Hausuebersicht zuletzt neu gezeichnet hat
let hsMinute='';
function tickClock(){
  const d=new Date();
  const t=el('svTime'), dd=el('svDate');
  if(t) t.textContent=d.toLocaleTimeString(LANG,{hour:'2-digit',minute:'2-digit'});
  if(dd) dd.textContent=d.toLocaleDateString(LANG,{weekday:'long',day:'numeric',month:'long',year:'numeric'});
  const nu=el('nuZeit');                       // Nacht-Uhr
  if(nu) nu.textContent=d.toLocaleTimeString(LANG,{hour:'2-digit',minute:'2-digit'});
  const kt=el('kzTime'), kd=el('kzDate');   // Kopfzeile (Widget "header")
  if(kt) kt.textContent=d.toLocaleTimeString(LANG,{hour:'2-digit',minute:'2-digit'});
  if(kd) kd.textContent=d.toLocaleDateString(LANG,{weekday:'short',day:'numeric',month:'short'});
  const ht=el('hsTime'), hd=el('hsDate');   // Kopf der Hausuebersicht
  if(ht) ht.textContent=d.toLocaleTimeString(LANG,{hour:'2-digit',minute:'2-digit'});
  if(hd) hd.textContent=d.toLocaleDateString(LANG,{weekday:'short',day:'numeric',month:'long'});
  // Termine in "Auf einen Blick" (hsTermine) laufen mit der Uhr ab; updateHaus
  // tauscht nur, was sich geaendert hat, und ruft tickClock in derselben Minute
  const minute=d.toDateString()+' '+d.getHours()+':'+d.getMinutes();
  if(minute!==hsMinute){ hsMinute=minute; if(document.querySelector('#grid.haus .hs-blick')) hausNeu(); }
}
// ---- Front-Extras (Kalender/Wetter) auf dem Screensaver ----
// Daten kommen vom Server ({t:'front', weather, events, calName}); das Panel
// zeigt nur an. Wetter-Icons im gleichen Strichstil wie die uebrigen Icons.
let frontData=null;
const WXI={
  sun:'<circle cx="12" cy="12" r="4"/><path d="M12 2v2.4M12 19.6V22M2 12h2.4M19.6 12H22M4.9 4.9l1.7 1.7M17.4 17.4l1.7 1.7M19.1 4.9l-1.7 1.7M6.6 17.4l-1.7 1.7"/>',
  cloud:'<path d="M17.5 19a4.5 4.5 0 0 0 0-9 6 6 0 0 0-11.6 1.5A4 4 0 0 0 6.5 19z"/>',
  rain:'<path d="M17.5 15a4.5 4.5 0 0 0 0-9 6 6 0 0 0-11.6 1.5A4 4 0 0 0 6.5 15z"/><path d="M8 18v2M12 18v2.6M16 18v2"/>',
  drizzle:'<path d="M17.5 15a4.5 4.5 0 0 0 0-9 6 6 0 0 0-11.6 1.5A4 4 0 0 0 6.5 15z"/><path d="M9 18v1.4M13 18v1.4M15 18v1.4"/>',
  snow:'<path d="M17.5 15a4.5 4.5 0 0 0 0-9 6 6 0 0 0-11.6 1.5A4 4 0 0 0 6.5 15z"/><path d="M8 19h.01M12 20h.01M16 19h.01"/>',
  fog:'<path d="M17.5 14a4.5 4.5 0 0 0 0-9 6 6 0 0 0-11.6 1.5A4 4 0 0 0 6.5 14z"/><path d="M6 18h12M8 21h8"/>',
  storm:'<path d="M17.5 14a4.5 4.5 0 0 0 0-9 6 6 0 0 0-11.6 1.5A4 4 0 0 0 6.5 14z"/><path d="m13 14-3 4h3.5l-2.5 4"/>',
};
function wxSvg(k){ return svg(WXI[k]||WXI.cloud); }
// ---- Kalenderfarben (mehrere iCal-Abos) ----
// Der Server schickt je Termin Name und Farbe seines Kalenders mit; `calColors`
// schaltet die Farben ab (schlichte Anzeige, nur noch der Name als Tag).
function calDot(d,e){
  return (d && d.calColors!==false && e && e.color)
    ? '<span class="cdot" style="background:'+esc(e.color)+'"></span>' : '';
}
// Tag am Termin: der Kalender, aus dem er kommt. Bei nur einem Abo bleibt es
// die Ueberschrift — sonst stuende an jedem Termin dasselbe Wort.
function evTag(d,e){
  const n=(Array.isArray(d.cals)?d.cals.length:0);
  if(n>1) return (e&&e.cal)||'';
  return (d&&d.calName)||'';
}
function svCount(d){ const n=parseInt(d&&d.svEvents); return (n>=1&&n<=10)?n:3; }
// Die eingestellte Zahl ist eine OBERGRENZE — den Rest entscheidet der Schirm.
// Auf dem 480x480-Panel passen neben Wetter und Uhr etwa drei Termine; mehr
// wuerde oben das Wetter und unten die Termine abschneiden. Darum nach dem
// Zeichnen messen und von unten so lange Zeilen wegnehmen, bis es passt.
function svFit(){
  const saver=el('saver');
  if(!saver) return;
  const platz=saver.clientHeight;
  const wrap=saver.querySelector('.sv-wrap');
  if(!platz||!wrap) return;                      // versteckt/noch nicht gemessen
  // Hoehe fuer Energiefluss/Kamera rechts (nur dort gelesen, siehe .tall): die
  // Uhr steht dann links, der Grafik gehoert die ganze Hoehe bis auf den Rand.
  // Der Rand ist derselbe Anteil wie seitlich (Breite 94 % -> je 3 %), damit
  // sie nicht wie zuvor mit 4 px an Ober- und Unterkante klebt.
  const rand=Math.round(platz*0.03), frei=Math.max(120,platz-2*rand);
  wrap.style.setProperty('--sv-frei', frei+'px');
  // Bleibt bei dieser Hoehe im Kasten Platz ueber und unter dem Inhalt
  // (svKastenLeer), kuerzt er sich darum (--sv-kasten) und steht mittig neben
  // Uhr und Wetter, statt weit ueber sie hinauszuragen. Hochkant gilt eigenes
  // (.hoch): der Kasten nimmt, was unter Uhr und Wetter bleibt.
  wrap.style.removeProperty('--sv-kasten');
  const leer=(wrap.classList.contains('tall') && !saver.classList.contains('hoch'))
    ? svKastenLeer(saver.querySelector('#svBox.solo')) : 0;
  if(leer>0) wrap.style.setProperty('--sv-kasten', (frei-leer)+'px');
  // Von unten wegnehmen, bis es passt — erst die Werte, dann die Termine. Bei
  // beiden ist die letzte Zeile die, die am wenigsten fehlt. Energiefluss und
  // Kamera haben keine solchen Zeilen und bleiben unangetastet.
  [el('svBox'), el('svCal')].forEach(c=>{
    if(!c||c.hidden) return;
    const zeilen=[...c.querySelectorAll('.sv-st,.sv-ev')];
    // offsetHeight, nicht getBoundingClientRect: platz ist eine Layout-Hoehe,
    // und bei skalierter Visu waere die sichtbare Hoehe k-mal groesser - dann
    // fielen Termine weg, die in Wahrheit passen.
    for(let i=zeilen.length-1; i>=1 && wrap.offsetHeight>platz; i--){
      zeilen[i].remove();
    }
  });
}
// Leerer Platz im Kasten der zweiten Spalte (svFit), in Layout-px; 0, wenn
// nichts frei ist. Energiefluss: die quadratische Grafik (Seitenverhaeltnis aus
// ihrer viewBox) ist in hohen Fenstern durch die Spaltenbreite begrenzt, der
// Rest bleibt ueber und unter ihr (gemessen bei 1457x900: Kasten 846 px,
// Grafik 418 px breit in 784 px Hoehe). Am 960x480-Panel begrenzt die Hoehe.
// Kamera: das Bild hat sein Seitenverhaeltnis aus dem CSS (.video,
// aspect-ratio), Tasten, Gegensprechen und Werte ihre Hoehe; die Seite
// zentriert sie, der Rest bleibt darueber und darunter. Beim Gegensprechen
// streckt sich das Bild in die Hoehe (flex-grow), gezaehlt wird es mit der
// Hoehe aus seinem Seitenverhaeltnis.
function svKastenLeer(box){
  if(!box) return 0;
  const ew=box.querySelector('.ewrap'), esvg=ew && ew.querySelector('svg');
  const vb=esvg && esvg.viewBox && esvg.viewBox.baseVal;
  if(vb && vb.width>0 && vb.height>0) return Math.floor(ew.clientHeight - ew.clientWidth*vb.height/vb.width);
  const seite=box.querySelector('.campage');
  if(!seite) return 0;
  const cs=getComputedStyle(seite), px=v=>parseFloat(v)||0;
  const teile=[...seite.children].map(e=>[e, getComputedStyle(e)]).filter(([, s])=>s.display!=='none');
  if(!teile.length) return 0;
  let inhalt=px(cs.rowGap)*(teile.length-1);
  for(const [e, s] of teile){
    const vh=/([\d.]+)\s*\/\s*([\d.]+)/.exec(s.aspectRatio||'');
    inhalt+=(vh && +vh[1]>0 ? e.clientWidth*vh[2]/vh[1] : e.offsetHeight) + px(s.marginTop) + px(s.marginBottom);
  }
  return Math.floor(seite.clientHeight - px(cs.paddingTop) - px(cs.paddingBottom) - inhalt);
}
// Legende: nur wenn es mehrere Kalender gibt UND die Farben an sind.
function fpLegendHTML(d){
  const cals=Array.isArray(d.cals)?d.cals:[];
  if(d.calColors===false || cals.length<2) return '';
  return '<div class="fp-leg">'+cals.map(c=>
    '<span><i style="background:'+esc(c.color||'')+'"></i>'+esc(c.name||'')+'</span>').join('')+'</div>';
}
function fmtTemp(t){ if(t==null||isNaN(t)) return '–'; return Number(t).toLocaleString(LANG,{minimumFractionDigits:1,maximumFractionDigits:1}); }
function tdeg(v){ return v==null?'–':(Math.round(v)+'°'); }
function renderFront(){
  const wxEl=el('svWx'); if(!wxEl) return;   // die zweite Spalte prueft renderSvSide selbst
  const d=frontData||{}, w=d.weather;
  if(w){
    const fc=Array.isArray(w.forecast)?w.forecast:[];
    wxEl.style.setProperty('--fc', Math.max(1,Math.min(7,fc.length))||4);
    let html='<div class="now"><span class="ico '+esc(w.icon||'cloud')+'">'+wxSvg(w.icon)+'</span>'+
      '<span class="t">'+fmtTemp(w.temp)+'°</span>'+
      '<span class="meta"><span class="cond">'+esc(w.cond||'')+'</span>';
    if(w.hi!=null||w.lo!=null) html+='<span class="hl">Heute '+tdeg(w.hi)+' / '+tdeg(w.lo)+'</span>';
    html+='</span></div>';
    if(fc.length) html+='<div class="fore">'+fc.map(f=>
      '<div class="fc"><span class="d">'+esc(f.day||'')+'</span>'+
      '<span class="ico '+esc(f.icon||'cloud')+'">'+wxSvg(f.icon)+'</span>'+
      '<span class="tt"><span class="mx">'+tdeg(f.hi)+'</span> <span class="mn">'+tdeg(f.lo)+'</span></span></div>').join('')+'</div>';
    wxEl.innerHTML=html; wxEl.hidden=false;
  } else { wxEl.hidden=true; wxEl.innerHTML=''; }
  // Wie viele Termine auf die Uhr-Seite passen, sagt die Einstellung — mit
  // mehreren Kalendern sind drei schnell zu wenig, um den Tag zu sehen.
  const evs=(Array.isArray(d.events)?d.events:[]).slice(0,svCount(d));
  const zweite=renderSvSide(evs);   // Termine, Wetter, Energie, Kamera oder Werte
  // Kompakt-Layout aktivieren, sobald Wetter oder eine zweite Spalte da ist.
  const wrap=document.querySelector('.sv-wrap');
  if(wrap){ wrap.classList.toggle('rich', !!w || zweite);
    wrap.classList.toggle('solo', !zweite);
    // Energiefluss/Kamera rechts: Uhr nach links, Grafik bekommt die volle Hoehe.
    const box=el('svBox');
    wrap.classList.toggle('tall', !!box && !box.hidden && box.classList.contains('solo'));
    wrap.classList.toggle('verlauf', wrap.classList.contains('tall') && svKind(svSideRaw())==='chart'); }
  svFit();
}
// ---- Rechte Spalte der Uhr-Seite ----
// Was dort steht, sagt die Einstellung je Panel (svPaneCfg, vom Server):
// "" = Automatik (Termine, und sobald keine anstehen die Wetter-Details),
// "off" = keine zweite Spalte, sonst "calendar" | "weather" | "energy:<uuid>"
// | "camera:<uuid>" | "status:<uuid>,...".
// Sie greift NUR im geteilten Screensaver (quer rechts, hochkant unten, s.
// applySaverSplit) — einspaltig (4"-Panel) gibt es keine Flaeche, die
// ungenutzt bliebe, dort bleibt es bei Wetter/Uhr/Terminen.
function svKind(v){ const i=v.indexOf(':'); return i>0?v.slice(0,i):v; }
// Kamera-Widget: "camera:<uuid>[,<uuid>...]|<uuid>,<uuid>" - Kameras vor (mehrere =
// blaetterbare Seiten), Werte hinter dem Strich
function camPaneUuids(arg){ return (arg||'').split('|')[0].split(',').map(x=>x.trim()).filter(Boolean); }
function camPaneWerte(arg){ const i=(arg||'').indexOf('|'); return i<0?'':arg.slice(i+1); }
function svArg(v){ const i=v.indexOf(':'); return i>0?v.slice(i+1):''; }
function svSideOn(){ const s=el('saver');   // Nacht-Uhr: die zweite Spalte ruht (keine Kamera die ganze Nacht)
  return !!s && !s.classList.contains('hidden') && s.classList.contains('split') && !s.classList.contains('nacht'); }
function svSideRaw(){ return svSideOn() ? (svPaneCfg||'') : ''; }
// Terminliste — aus renderFront herausgeloest, seit sie nicht mehr die einzige
// moegliche Fuellung der Spalte ist.
function svCalHTML(d,evs){
  return '<div class="lbl">Nächste Termine</div>'+evs.map(e=>{
    const tag=evTag(d,e);
    return '<div class="sv-ev"><span class="when"><span class="day">'+esc(e.day||'')+'</span>'+
    '<span class="tm">'+esc(e.time||'')+'</span></span>'+
    '<span class="ttl">'+calDot(d,e)+esc(e.title||'')+'</span>'+
    (tag?'<span class="tag">'+esc(tag)+'</span>':'')+'</div>'; }).join('');
}
// Wetter fuer die zweite Spalte: Stundenverlauf und die Detailwerte. Bewusst
// NICHT noch einmal die Tagesvorschau — die steht schon in der linken Spalte.
function svWeatherHTML(w){
  if(!w) return '';
  const hh=Array.isArray(w.hourly)?w.hourly:[];
  const kurve=(hh.length>=2)?'<div class="fp-curve">'+fpCurve(hh)+'</div>':'';
  const det=fpWeatherDetailHTML(w);
  return (kurve||det) ? '<div class="lbl">Wetter</div>'+kurve+det : '';
}
// Frei gewaehlte Bausteine: Name, Raum, Wert — nur lesen. Die Kacheln baut der
// Server ueber dieselbe Kette wie jede andere Kachel (status_blocks).
function renderSvStatus(box){ box.innerHTML='<div class="lbl">Werte</div>'+svStatusZeilen(); }
// Werte als Pane 2: gerahmt wie die anderen Widgets, die Zeilen teilen sich die
// Hoehe. Sind es wenige, wachsen Symbol und Schrift mit (--zh = Zeilenhoehe,
// werteEinpassen); reicht die Hoehe nicht, scrollt die Pane wie bisher.
function renderWertePane(box){
  box.innerHTML='<div class="fp-page werte"><div class="fp-h">Werte</div>'+svStatusZeilen()+'</div>';
  werteEinpassen(box);
}
// Werte: ab dieser Zeilenhoehe (px) duerfen lange Namen umbrechen
const WERTE_HOCH = 80;
function werteEinpassen(box){
  const s=box && (box.classList.contains('werte') ? box : box.querySelector('.werte')); if(!s || !s.clientHeight) return;
  const z=s.querySelector('.sv-st');
  if(z){ s.style.removeProperty('--zh'); s.classList.remove('hoch');
    const zh=z.offsetHeight; s.style.setProperty('--zh', zh+'px'); s.classList.toggle('hoch', zh>=WERTE_HOCH); }
}
// Zeilen der gewaehlten Werte (Uhr-Seite und Pane 2), ohne Werte ein Hinweis.
function svStatusZeilen(){
  const items=Array.isArray(svStatusData)?svStatusData:[];
  if(!items.length)
    return '<div class="fp-empty">'+(svStatusData===null?'Werte werden geladen …':'Keine Werte gewählt.')+'</div>';
  return items.map(it=>{
    const ton=(it.tone==='good')?' good':((it.tone==='crit')?' crit':(it.on?' on':''));
    const ico = it.iconUrl ? '<span class="ico img" style="--u:url(\''+esc(it.iconUrl)+'\')"></span>'
      : '<span class="ico">'+svg(ICONS[it.icon]||ICONS.info)+'</span>';
    return '<div class="sv-st'+ton+'"'+(it.color?' style="--ico:'+esc(it.color)+'"':'')+'>'+ico+
      '<span class="nm">'+esc(it.label||'')+
      (it.room?'<span class="rm">'+esc(it.room)+'</span>':'')+'</span>'+
      '<span class="vl">'+esc(it.sublabel||'')+'</span></div>'; }).join('');
}
// Audio als zweite Uhr-Spalte: passive "Now Playing"-Karte (Cover, Titel,
// Interpret) — ohne Transport/Lautstaerke, die Uhr-Seite ist zum Ansehen da.
function renderSvPlayer(box){
  const b=Array.isArray(playerData)?playerData:[];
  const title=b.find(x=>x.k==='title'), cover=b.find(x=>x.k==='cover');
  const hasT=title&&(title.text||title.sub);
  if(!b.length || !hasT){
    box.innerHTML='<div class="lbl">Audio</div><div class="fp-empty">'+
      (playerData===null?'Wird geladen …':'Nichts gewählt oder keine Wiedergabe.')+'</div>';
    return;
  }
  const src=(cover&&cover.src)||'';
  box.innerHTML='<div class="fp-page solo svplayer">'+
    '<div class="svp-cover">'+(src?'<img src="'+esc(src)+'" alt="">':'<span class="coverph">'+svg(ICONS.music)+'</span>')+'</div>'+
    '<div class="svp-title">'+esc(title.text||'')+'</div>'+
    '<div class="svp-sub">'+esc(title.sub||'')+'</div></div>';
}
// Liefert true, wenn rechts (bzw. einspaltig: unten) ueberhaupt etwas steht.
function renderSvSide(evs){
  const cal=el('svCal'), box=el('svBox');
  if(!cal||!box) return false;
  const d=frontData||{}, zwei=svSideOn(), raw=svSideRaw(), k=svKind(raw);
  // Termine: einspaltig wie bisher unter der Uhr, zweispaltig bei "calendar"
  // und in der Automatik — solange ueberhaupt welche anstehen.
  const zeigeCal = evs.length>0 && (!zwei || k==='calendar' || k==='');
  if(zeigeCal){ cal.innerHTML=svCalHTML(d,evs); cal.hidden=false; }
  else { cal.hidden=true; cal.innerHTML=''; }
  // Ist die Kamera nicht (mehr) gemeint, muss ihr <img> weg — es haengt direkt
  // an /mjpeg und streamt sonst weiter, auch unsichtbar.
  if(k!=='camera' && box.dataset.cam!==undefined){
    box.innerHTML=''; delete box.dataset.cam; delete box.dataset.camsig; }
  let inhalt=false;
  if(zwei && k!=='off' && k!=='calendar'){
    if(k==='energy'){ renderEnergyPane(box); inhalt=true; }
    else if(k==='camera'){ renderCameraPane(box); inhalt=true; }
    else if(k==='chart'){ renderChartPane(box); inhalt=true; }
    else if(k==='status'){ renderSvStatus(box); inhalt=true; }
    else if(k==='player'){ renderSvPlayer(box); inhalt=true; }
    else if(k==='weather' || (k==='' && !zeigeCal)){
      // Automatik: sobald die Termine die Spalte nicht fuellen, uebernimmt das
      // Wetter sie — sonst bliebe die halbe Flaeche leer.
      const h=svWeatherHTML(d.weather);
      if(h){ box.innerHTML=h; inhalt=true; }
    }
  }
  if(!inhalt && k!=='camera') box.innerHTML='';
  // Energiefluss und Kamera fuellen eine Seite und brauchen die Hoehengrenze
  // oben; Termine, Wetter und Werte sind Listen und duerfen wachsen (svFit
  // nimmt ihnen notfalls die unterste Zeile).
  box.classList.toggle('solo', inhalt && (k==='energy'||k==='camera'||k==='chart'||k==='player'));
  box.hidden=!inhalt;
  return zeigeCal || inhalt;
}
// ---- Ausfuehrliche "Wetter & Kalender"-Ansicht (fuer eigene Seite / Split-Pane) ----
// Zeichnet den Stunden-Temperaturverlauf als Inline-SVG (Regenband + Kurve),
// Vorschaukarten mit Regenwahrscheinlichkeit und die Termine als Tages-Agenda.
// W x H: Groesse der Zeichnung. Ohne Angabe 700 x 150, die das SVG auf seine
// Breite skaliert (Uhr-Seite, Wetter-Tab). Pane 2 zeichnet in der Groesse
// ihres Platzes, dann sind die Zahlen echte 11 px (wetterEinpassen).
function fpCurve(hourly, W=700, H=150){
  const pts=hourly.filter(h=>h && h.temp!=null);
  if(pts.length<2) return '';
  const padT=24,padB=32,padX=12,n=pts.length;
  const temps=pts.map(p=>p.temp);
  let mn=Math.min(...temps), mx=Math.max(...temps);
  if(mx-mn<4){ const c=(mx+mn)/2; mn=c-2; mx=c+2; }
  const X=i=> padX + i*(W-2*padX)/(n-1);
  const Y=t=> padT + (mx-t)*(H-padT-padB)/(mx-mn);
  const barW=Math.max(3,(W-2*padX)/n*0.55);
  // Beschriftet ist jeder dritte Punkt, auf schmaler Zeichnung seltener: eine
  // Zahl braucht gut 26 px. Der letzte Punkt nur, wenn er so weit vom vorigen
  // beschrifteten entfernt ist.
  const dx=(W-2*padX)/(n-1), jede=Math.max(3, Math.ceil(26/dx));
  const bars=pts.map((p,i)=>{ if(p.pop==null||p.pop<=0) return '';
    const bh=(p.pop/100)*(H-padB-padT)*0.55;
    return '<rect x="'+(X(i)-barW/2).toFixed(1)+'" y="'+(H-padB-bh).toFixed(1)+'" width="'+barW.toFixed(1)+'" height="'+bh.toFixed(1)+'" rx="1.5" fill="#7fb2e6" opacity=".2"/>'; }).join('');
  const line=pts.map((p,i)=>X(i).toFixed(1)+','+Y(p.temp).toFixed(1)).join(' ');
  const area=X(0).toFixed(1)+','+(H-padB)+' '+line+' '+X(n-1).toFixed(1)+','+(H-padB);
  let lbl='';
  pts.forEach((p,i)=>{ if(i%jede===0 || (i===n-1 && (i%jede)*dx>=26)){
    lbl+='<text x="'+X(i).toFixed(1)+'" y="'+(H-12)+'" text-anchor="middle" class="fpx">'+p.h+'</text>';
    lbl+='<text x="'+X(i).toFixed(1)+'" y="'+(Y(p.temp)-9).toFixed(1)+'" text-anchor="middle" class="fpt">'+p.temp+'°</text>'; }});
  return '<svg viewBox="0 0 '+W+' '+H+'">'+
    '<defs><linearGradient id="fpgrad" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="currentColor" stop-opacity=".22"/><stop offset="1" stop-color="currentColor" stop-opacity="0"/></linearGradient></defs>'+
    bars+
    '<polygon points="'+area+'" fill="url(#fpgrad)"/>'+
    '<polyline points="'+line+'" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linejoin="round" stroke-linecap="round"/>'+
    '<circle cx="'+X(0).toFixed(1)+'" cy="'+Y(pts[0].temp).toFixed(1)+'" r="4" fill="currentColor"/>'+
    lbl+'</svg>';
}
// Windeinheit: der Server schickt sie mit (Open-Meteo km/h, der Loxone-
// Wetterserver das, was die Anlage in ihren Formatstrings fuehrt).
function wUnit(w){ return (w&&w.wind_unit)?w.wind_unit:'km/h'; }
function windDir(deg){ const C=['N','NO','O','SO','S','SW','W','NW']; return (deg==null)?'':(C[Math.round(deg/45)%8]||''); }
// Seite 1 (fuellt die 2x2-Kachelhoehe): Aktuell + Kurve + Vorschau.
function fpWeatherMainHTML(w){
  if(!w) return '';
  return '<div class="fp-h" data-i18n>Wetter</div>'+fpNowHTML(w)+fpCurveHTML(w)+fpForeHTML(w);
}
// Teile der Wetteransicht: Pane und Screensaver setzen sie untereinander, die
// Wetter-Seite (renderFrontTab) auf zwei Spalten verteilt.
function fpNowHTML(w){
  return '<div class="fp-now"><span class="ico '+esc(w.icon||'cloud')+'">'+wxSvg(w.icon)+'</span>'+
    '<span class="t">'+fmtTemp(w.temp)+'°</span><span class="meta">'+
    '<span class="cond">'+esc(w.cond||'')+'</span>'+
    '<span class="sub">'+(w.feels!=null?'Gefühlt '+tdeg(w.feels):'')+(w.wind!=null?' · Wind '+w.wind+' '+wUnit(w):'')+'</span>'+
    '<span class="sub heute">Heute '+tdeg(w.hi)+' / '+tdeg(w.lo)+'</span></span></div>';
}
function fpCurveHTML(w){
  const hh=Array.isArray(w.hourly)?w.hourly:[];
  return hh.length>=2 ? '<div class="fp-curve">'+fpCurve(hh)+'</div>' : '';
}
function fpForeHTML(w){
  const fc=Array.isArray(w.forecast)?w.forecast:[];
  return fc.length ? '<div class="fp-fore" style="--fc:'+Math.max(1,Math.min(7,fc.length))+'">'+fc.map(f=>
    '<div class="fp-fc"><span class="d">'+esc(f.day||'')+'</span>'+
    '<span class="ico '+esc(f.icon||'cloud')+'">'+wxSvg(f.icon)+'</span>'+
    '<span class="tt"><span class="mx">'+tdeg(f.hi)+'</span> <span class="mn">'+tdeg(f.lo)+'</span></span>'+
    (f.pop!=null?'<span class="pop">'+f.pop+'%</span>':'')+'</div>').join('')+'</div>' : '';
}
// Seite 2: Detailkacheln (nur vorhandene Werte).
function fpWeatherDetailHTML(w){
  if(!w) return '';
  const det=[];
  if(w.humidity!=null) det.push(['Luftfeuchte', w.humidity+' %']);
  if(w.wind!=null) det.push(['Wind', w.wind+' '+wUnit(w)+(w.wind_dir!=null?' '+windDir(w.wind_dir):'')]);
  if(w.sunrise&&w.sunset) det.push(['Sonne', w.sunrise+' – '+w.sunset]);
  if(w.uv!=null) det.push(['UV-Index', String(w.uv)]);
  if(w.precip_sum!=null) det.push(['Niederschlag', String(w.precip_sum).replace('.',',')+' mm']);
  if(w.pressure!=null) det.push(['Luftdruck', w.pressure+' hPa']);
  return det.length ? '<div class="fp-det">'+det.map(x=>'<div><span>'+esc(x[0])+'</span><b>'+esc(x[1])+'</b></div>').join('')+'</div>' : '';
}
function fpWeatherHTML(w){ if(!w) return ''; return fpWeatherMainHTML(w)+fpWeatherDetailHTML(w);
}
let calMonthOff=0, calSel='';   // Kalender-Pane: Monatsverschiebung + gewaehlter Tag (ISO)
function isoDay(dt){ const p=n=>String(n).padStart(2,'0'); return dt.getFullYear()+'-'+p(dt.getMonth()+1)+'-'+p(dt.getDate()); }
function evRow(d,e){
  // Sind die Farben abgeschaltet, sagt sonst nichts mehr, aus welchem Kalender
  // der Termin kommt — dann traegt die Zeile den Namen, wie es die Einstellung
  // ankuendigt ("nur der Kalendername steht daneben").
  const n=(Array.isArray(d.cals)?d.cals.length:0);
  const nam=(d.calColors===false && n>1 && e.cal)
    ? '<span class="cal">'+esc(e.cal)+'</span>' : '';
  return '<div class="fp-ev"><span class="tm'+(e.allday?' all':'')+'">'+esc(e.time||'')+'</span>'+
    '<span class="ttl">'+calDot(d,e)+esc(e.title||'')+nam+
    (e.note?'<span class="note">'+esc(e.note)+'</span>':'')+'</span></div>'; }
// legende=false: die Legende steht schon unter dem Monat (Kalender in Pane 2)
function fpCalHTML(d, legende=true){
  const evs=Array.isArray(d.events)?d.events:[], hol=d.holidays||{};
  if(calSel){   // ein Tag gewaehlt -> nur dessen Termine (+ Feiertag)
    let dt; try{ dt=new Date(calSel+'T00:00'); }catch(e){ dt=new Date(); }
    const lbl=dt.toLocaleDateString(LANG,{weekday:'long',day:'numeric',month:'long'});
    let html='<div class="fp-h"><span>'+esc(lbl)+'</span><button class="fp-allbtn" data-calall="1">Alle ›</button></div>';
    if(hol[calSel]) html+='<div class="fp-ev holi"><span class="tm all">Feiertag</span><span class="ttl">'+esc(hol[calSel])+'</span></div>';
    const day=evs.filter(e=>e.date===calSel);
    if(day.length) html+=day.map(e=>evRow(d,e)).join('');
    else if(!hol[calSel]) html+='<div class="fp-empty">Keine Termine an diesem Tag.</div>';
    return html;
  }
  let html='<div class="fp-h">'+esc(d.calName||'Termine')+'</div>'+(legende?fpLegendHTML(d):'');
  if(evs.length){
    html+='<div class="fp-cal">'; let curDay=null;
    evs.forEach(e=>{ if(e.day!==curDay){ curDay=e.day; html+='<div class="fp-day">'+esc(e.day||'')+'</div>'; } html+=evRow(d,e); });
    html+='</div>';
  } else { html+='<div class="fp-empty" data-i18n>Keine Termine.</div>'; }
  return html;
}
// Vollseite (Test ?front=1): Wetter + Kalender kombiniert.
function renderFrontRich(elc){ if(!elc) return; const d=frontData||{}; elc.innerHTML=fpWeatherHTML(d.weather)+fpCalHTML(d); }
// Split-Panes: je eine eigene Pane.
// Energiefluss-Pane (Radial, Loxone-Standard): Daten vom Server ({t:'energy'});
// das Panel zeichnet Knoten + animierte Fluss-Punkte. Zahlen deutsch, W/kW auto.
function fmtPower(w){ if(w==null) return '–'; const a=Math.abs(w);
  return a<1000 ? Math.round(w)+' W' : (w/1000).toFixed(1).replace('.',',')+' kW'; }
const EICONS={
  pv:'<circle cx="12" cy="8" r="3.2"/><path d="M12 1.6v1.6M6.7 3.3l1 1M17.3 3.3l-1 1M4.5 8h1.4M18.1 8h1.4"/><path d="M6 14l1.6 6.4h8.8L18 14z"/><path d="M7.4 17.2h9.2M11 14v6.4"/>',
  grid:'<path d="M12 2 5.5 22M12 2l6.5 20M8 15h8M9.3 9h5.4"/>',
  battery:'<rect x="2" y="7" width="16" height="11" rx="2.4"/><path d="M21 11v3"/>',
  load:'<path d="M13 2 4 14h7l-1 8 10-12h-7z"/>'
};
// Knoten-Icon: echtes Loxone-Icon (in Flussfarbe eingefaerbt), sonst das
// eingebaute Symbol als Fallback. So gibt der Miniserver Icon UND Name vor
// (siehe energy_blocks/_node_icon_url im Server).
// Einfaerben rein in SVG: das Bild ist Alpha-Maske eines Rechtecks in
// Rollenfarbe. KEIN foreignObject mit CSS-mask: WebKit (Safari, iPad,
// Panel-WebViews) legt HTML mit eigener Render-Ebene im foreignObject ohne
// die translate() der Knotengruppe ab -> alle Icons landeten oben links.
// Masken-IDs sind dokumentweit eindeutig (Pane, Detailansicht und
// Screensaver koennen das Radial gleichzeitig zeigen).
let eMaskSeq=0;
function eIconMarkup(n,cls,i){
  const tag='data-ic="'+i+'"';
  if(n && n.iconUrl){
    const u=esc(String(n.iconUrl)), id='emk'+(++eMaskSeq);
    return '<mask id="'+id+'" maskUnits="userSpaceOnUse" maskContentUnits="userSpaceOnUse" '+
      'x="-13" y="-13" width="26" height="26" style="mask-type:alpha">'+
      '<image href="'+u+'" xlink:href="'+u+'" x="-13" y="-13" width="26" height="26" preserveAspectRatio="xMidYMid meet"/></mask>'+
      '<rect '+tag+' class="emask '+cls+'" x="-13" y="-13" width="26" height="26" mask="url(#'+id+')"/>';
  }
  const icon=EICONS[n&&n.icon]||EICONS.load;
  return '<g '+tag+' class="eic '+cls+'" transform="translate(-12,-12)">'+icon+'</g>';
}
// Farbe nach ROLLE (kind vom Server): prod=Quelle gruen, grid=Netzbezug ROT,
// load=Verbraucher orange, idle=0 W grau. (Fallback aus flow, falls kein kind.)
function eColorCls(n){ const k=n.kind||(n.flow==='out'?'load':(n.flow==='in'?'prod':'idle'));
  return k==='grid'?'grid':(k==='load'?'cons':(k==='prod'?'prod':'idle')); }
// Animationsrichtung nach ECHTEM Fluss (flow), entkoppelt von der Farbe:
// in = zur Mitte, out = nach aussen (in den Knoten, z.B. Einspeisung).
function eDirCls(n){ return n.flow==='in'?' fin':(n.flow==='out'?' fout':''); }
function nodeLabel(n){ return (n.name||'')+(n.soc!=null?' · '+Math.round(n.soc)+' %':''); }
// Nur Werte, die der Server kennt: unbekannter Verbrauch (null) fehlt, statt "0 W".
function efooter(tt){ const t=[];
  if(tt.prod!=null) t.push('Erzeugung <b>'+esc(fmtPower(tt.prod))+'</b>');
  if(tt.cons!=null) t.push('Verbrauch <b>'+esc(fmtPower(tt.cons))+'</b>');
  return t.join(' · '); }
// Baut das Radial als HTML-String (fuer Pane UND Detailansicht). Knoten tragen
// data-Attribute, damit updateEnergyPane() nur Werte/Farben aendert und die
// Fluss-Punkte NICHT neu erzeugt werden (Animation laeuft sonst nie durch).
function energyInner(d){
  d=d||{};
  const nodes=(d.nodes||[]).slice(0,9), N=nodes.length;
  if(!N) return '<div class="epane"><div class="ebot">Energiefluss lädt …</div></div>';
  const C=240,R=140,rn=(N>6?34:40), spokes=[],dots=[],ng=[],txts=[];   // C=240 in 480er-viewBox -> Rand fuer Beschriftung ausserhalb der Ringe
  nodes.forEach((n,i)=>{
    const ang=-Math.PI/2 + i*2*Math.PI/N, nx=C+R*Math.cos(ang), ny=C+R*Math.sin(ang);
    const col=eColorCls(n), dir=eDirCls(n), tx=nx.toFixed(1), ty=ny.toFixed(1);
    spokes.push('<line class="spoke" x1="'+C+'" y1="'+C+'" x2="'+tx+'" y2="'+ty+'"/>');
    const dx=((nx-C)*0.72).toFixed(1), dy=((ny-C)*0.72).toFixed(1);
    for(let k=0;k<2;k++) dots.push('<circle data-nd="'+i+'-'+k+'" class="edot '+col+dir+'" cx="'+C+'" cy="'+C+'" r="4.5" style="--dx:'+dx+'px;--dy:'+dy+'px;animation-delay:'+(k*1.3)+'s'+(n.flow?'':';display:none')+'"/>');
    ng.push('<g transform="translate('+tx+','+ty+')"><circle class="ering '+col+'" data-ri="'+i+'" r="'+rn+'"/>'+eIconMarkup(n,col,i)+'</g>');
    const above=ny<C-4, nm=esc(nodeLabel(n));
    const val=esc(n.flow?fmtPower(n.w):'0 W'), vcls='enval'+(col==='idle'?' idle':'');
    txts.push(above
      ? '<text class="'+vcls+'" data-vv="'+i+'" x="'+tx+'" y="'+(ny-74).toFixed(1)+'">'+val+'</text><text class="enlab" data-vl="'+i+'" x="'+tx+'" y="'+(ny-56).toFixed(1)+'">'+nm+'</text>'
      : '<text class="enlab" data-vl="'+i+'" x="'+tx+'" y="'+(ny+56).toFixed(1)+'">'+nm+'</text><text class="'+vcls+'" data-vv="'+i+'" x="'+tx+'" y="'+(ny+76).toFixed(1)+'">'+val+'</text>');
  });
  // "dicht": ab sieben Knoten stehen die Ringe so eng (rn 34 statt 40), dass
  // die Beschriftungen der Seitenknoten schon jetzt in die Nachbarringe laufen.
  // Wer die Schrift vergroessert (Screensaver), muss diesen Fall aussparen.
  return '<div class="epane'+(N>6?' dicht':'')+'"><div class="etop"><span class="ettl">'+esc(d.name||'Energiefluss')+'</span></div>'+
    '<div class="ewrap"><svg viewBox="0 0 480 480" preserveAspectRatio="xMidYMid meet">'+
    spokes.join('')+dots.join('')+'<circle class="ehub" cx="'+C+'" cy="'+C+'" r="13"/>'+ng.join('')+txts.join('')+
    '</svg></div><div class="ebot">'+efooter(d.totals||{})+'</div></div>';
}
// Struktur-Signatur: nur bei Aenderung (Knotensatz/Icons) neu zeichnen.
function energySig(d){ return ((d.nodes||[]).map(n=>(n.name||'')+'§'+(n.icon||'')+'§'+(n.iconUrl||'')).join('¦'))+'#'+((d.nodes||[]).length); }
function updateEnergyPane(elc,d){
  (d.nodes||[]).slice(0,9).forEach((n,i)=>{
    const col=eColorCls(n), dir=eDirCls(n);
    const ring=elc.querySelector('.ering[data-ri="'+i+'"]'); if(ring){ const w='ering '+col; if(ring.getAttribute('class')!==w) ring.setAttribute('class',w); }
    const ic=elc.querySelector('[data-ic="'+i+'"]'); if(ic){ const base=ic.classList.contains('emask')?'emask':'eic'; const w=base+' '+col; if(ic.getAttribute('class')!==w) ic.setAttribute('class',w); }
    const vv=elc.querySelector('[data-vv="'+i+'"]'); if(vv){ const t=n.flow?fmtPower(n.w):'0 W'; if(vv.textContent!==t) vv.textContent=t; const w='enval'+(col==='idle'?' idle':''); if(vv.getAttribute('class')!==w) vv.setAttribute('class',w); }
    const vl=elc.querySelector('[data-vl="'+i+'"]'); if(vl){ const t=nodeLabel(n); if(vl.textContent!==t) vl.textContent=t; }
    for(let k=0;k<2;k++){ const dot=elc.querySelector('.edot[data-nd="'+i+'-'+k+'"]'); if(dot){ const w='edot '+col+dir; if(dot.getAttribute('class')!==w) dot.setAttribute('class',w); const disp=n.flow?'':'none'; if(dot.style.display!==disp) dot.style.display=disp; } }
  });
  const bot=elc.querySelector('.ebot'); if(bot){ const h=efooter(d.totals||{}); if(bot.innerHTML!==h) bot.innerHTML=h; }
}
// Zeichnet in elc: nur bei Strukturaenderung Neuaufbau, sonst in-place -> Punkte laufen weiter.
function paintEnergy(elc,d){
  d=d||{};
  const sig=energySig(d);
  if(elc._esig===sig && elc.querySelector('.ewrap svg')){ updateEnergyPane(elc,d); return; }
  elc._esig=sig;
  elc.innerHTML=energyInner(d);
}
function renderEnergyPane(elc){ if(!elc) return;
  // Energiefluss in denselben gerahmten .fp-page-Block wie Wetter/Kalender (eine Seite).
  let page=elc.querySelector('.fp-page.epage');
  if(!page){ elc.innerHTML='<div class="fp-page epage solo"></div>'; page=elc.querySelector('.fp-page.epage'); }
  paintEnergy(page, energyData||{}); }

// Kamera-Pane: VOLLE Intercom-Ansicht (Klingel-Banner + Video + Tür-/Ausgang-Buttons),
// gleiche Blöcke wie der Baustein (kommen per {t:'camera'}-Push vom Server). Das Video
// wird wie beim Baustein direkt geladen (kein onload-Gate -> zeigt auch in Browsern, die
// ein nacktes MJPEG-<img> nicht rendern). Struktur nur bei Änderung neu bauen, sonst nur
// Buttons/Klingel in-place aktualisieren -> der Video-Stream läuft ununterbrochen weiter.
// Mehrere Kameras (camera:a,b,c) in der Pane: je Kamera eine blaetterbare Seite.
// Der Server streamt je Verbindung nur EINE Kamera, darum zeigt nur die sichtbare
// (camCamIdx) Bild, Tasten und Werte; die uebrigen Seiten sind Platzhalter. Auf
// der Uhr-Seite (svBox) gibt es kein Blaettern, dort steht die erste.
function camPageTo(idx){ if(idx===camCamIdx) return; camCamIdx=idx; applyPane(); }
function renderCameraPane(elc){ if(!elc) return;
  const n=(elc.id==='frontpane' && !svSideOn()) ? Math.max(1,camList.length) : 1;
  // Geruest nur bei geaenderter Anzahl neu bauen, sonst bleiben Scrollposition
  // und laufender Stream erhalten
  let pages=[...elc.children].filter(x=>x.classList.contains('campage'));
  if(pages.length!==n || elc.dataset.camn!==String(n)){
    elc.dataset.camn=String(n);
    elc.innerHTML=Array.from({length:n},(_,i)=>'<div class="fp-page solo campage'+(n>1?' paged':'')+'" data-camidx="'+i+'"></div>').join('');
    pages=[...elc.children];
    if(n>1) requestAnimationFrame(()=>syncPager(camPageTo));
  }
  // Andere Kamera gemeldet (applyPane loescht camsig): alle Seiten neu
  if(elc.dataset.camsig===undefined){ pages.forEach(pg=>{ delete pg.dataset.cam; delete pg.dataset.camsig; }); elc.dataset.camsig='1'; }
  elc.dataset.cam='1';   // Kennzeichen fuers Aufraeumen (applyPane, Uhr-Seite)
  const idx=(n>1) ? Math.min(camCamIdx, n-1) : 0;
  pages.forEach((pg,i)=>{ if(i!==idx && pg.dataset.cam!=='idle'){
    pg.dataset.cam='idle'; delete pg.dataset.camsig; pg.className='fp-page solo campage paged';
    pg.innerHTML='<div class="camwait">'+svg(ICONS.cam)+'<span>Kamera '+(i+1)+'</span></div>'; } });
  renderCameraSeite(elc, pages[idx], n>1);
}
// Inhalt EINER Kamera-Seite (der sichtbaren): Zustand je Seite in page.dataset
function renderCameraSeite(elc, page, paged){ if(!page) return;
  const cls='fp-page solo campage'+(paged?' paged':'');
  const blocks=cameraData&&cameraData.blocks ? intercomBlocks(cameraData.blocks) : null;
  if(blocks===null){   // Push noch nicht da -> Platzhalter
    if(page.dataset.cam!=='wait'){ page.dataset.cam='wait'; delete page.dataset.camsig; page.className=cls;
      page.innerHTML='<div class="camwait">'+svg(ICONS.cam)+'<span>Kamera lädt …</span></div>'; }
    return;
  }
  const video=blocks.find(b=>b.k==='video'), row=blocks.find(b=>b.k==='row');
  const bell=blocks.find(b=>b.k==='astat'), nostat=blocks.find(b=>b.k==='status');
  const talk=blocks.find(b=>b.k==='intercom-talk');
  const baseSig=(video?'v':'')+'|'+(row?row.cells.length:0)+'|'+(nostat?nostat.text:'')+'|'+(camPaneWerte(qargCamNow())?'w':'')+'|';
  const sig=baseSig+(talk?talk.uuid:'');
  if(talk && page.dataset.camsig===baseSig){   // Gegensprechen kommt dazu: vor die Werte unter dem Bild
    const werte=page.querySelector('.camwerte');
    if(werte) werte.insertAdjacentHTML('beforebegin',intercomTalkHtml(talk));
    else page.insertAdjacentHTML('beforeend',intercomTalkHtml(talk));
    page.classList.add('intercom-page'); page.dataset.camsig=sig;
  }
  if(page.dataset.camsig!==sig){          // Struktur -> Neuaufbau
    page.dataset.camsig=sig; page.dataset.cam='1';
    let html='<div class="cambell astat crit" hidden></div>';
    html+= video ? '<div class="video"><img alt=""></div>'
                 : '<div class="status">'+esc(nostat?nostat.text:'Kein Video')+'</div>';
    if(row) html+='<div class="brow'+(row.wrap?' wraprow':'')+'">'+row.cells.map(cellHtml).join('')+'</div>';
    if(talk) html+=intercomTalkHtml(talk);
    if(camPaneWerte(qargCamNow())) html+='<div class="camwerte werte"></div>';   // Werte unter dem Bild
    page.className=cls+(talk?' intercom-page':''); page.innerHTML=html;
    renderCameraWerte(elc);
    const vimg=page.querySelector('.video img'); if(vimg&&video) vimg.src=video.src;   // direkt, KEIN onload-Gate
    if(row){ const btns=page.querySelectorAll('.brow [data-c]');
      row.cells.forEach((c,i)=>{ const btn=btns[i]; if(!btn)return;
        btn.addEventListener('pointerdown',ev=>{ ev.preventDefault(); if(c.cmd) sendCmd(c.cmd.uuid,c.cmd.cmd,!!(cameraData&&cameraData.secured)); }); }); }
  } else {                                // gleiche Struktur -> nur Buttons und Werte aktualisieren (Video unangetastet)
    if(row){ const btns=page.querySelectorAll('.brow [data-c]');
      row.cells.forEach((c,i)=>{ const btn=btns[i]; if(btn){ btn.textContent=c.label||''; btn.className='btn'+(c.on?' on':''); } }); }
    // Werte unter dem Bild: auch hier nachziehen - auf der Uhr-Seite kommt ein
    // Werte-Push ueber renderFront() hier an, nicht ueber renderCameraWerte()
    renderCameraWerte(elc);
  }
  const be=page.querySelector('.cambell'); if(be){ if(bell){ be.textContent=bell.text||''; be.hidden=false; } else be.hidden=true; }
  intercomBind(page);
}
// Der Kamera-Wert der aktiven Pane (Tab-Pane oder Widget-Seite), ohne "camera:"
// Kamera-Angabe der gerade gezeichneten Pane: auf der Uhr-Seite die des
// Screensavers (svPane), sonst die des Tabs - wie die Anmeldung in applyPane()
function qargCamNow(){ const raw=(svSideOn() ? svSideRaw() : paneRawNow())||''; return raw.indexOf('camera:')===0 ? raw.slice(7) : ''; }
// Werte unter dem Kamerabild: nur dieser Block wird neu gezeichnet (bei jedem
// {t:'svstatus'}-Push), das Video und die Tasten bleiben stehen.
function renderCameraWerte(elc){
  const box=elc && elc.querySelector('.campage .camwerte'); if(!box) return;
  box.innerHTML=svStatusZeilen();
  werteEinpassen(box);
}
function renderWeatherPane(elc){ if(!elc) return; const d=frontData||{}, w=d.weather;
  if(!w){ elc.innerHTML='<div class="fp-empty">Kein Wetter konfiguriert.</div>'; return; }
  // Seite 1 = Aktuell, Kurve, Vorschau und die Details, so hoch wie die Flaeche.
  // Passen die Details nicht mit darauf, haengt wetterEinpassen sie auf Seite 2.
  const det=fpWeatherDetailHTML(w);
  elc.innerHTML='<div class="fp-page wx">'+fpWeatherMainHTML(w)+det+'</div>'
    +(det?'<div class="fp-page wxdet" hidden></div>':'');
  wetterEinpassen(elc); }
// ---- Pane 2 nutzt ihre Flaeche (Wetter, Kalender, Werte) ----
// Wie gross die Flaeche ist, steht erst nach dem Layout fest (Split, Raster,
// Drehen). Darum misst die Visu nach dem Zeichnen und bei jeder
// Groessenaenderung von #frontpane nach und setzt Stufen, wie fitTile() bei
// den Kacheln. Container-Queries kaemen ohne JS aus, aber erst ab Chrome 105.
// Breiter als hoch um diesen Faktor: Lage und Kurve nebeneinander (Wetter),
// Monat und Termine nebeneinander (Kalender).
const PANE_BREIT = 1.45;
// Wetter: schmaler als das (px), steht die Beschreibung unter der Temperatur
// und die Vorschau laesst sich seitlich wischen, statt sich zu quetschen.
const WX_SCHMAL = 380;
// Wetter: so hoch (px) soll die Kurve mindestens werden. Fehlt der Platz,
// wandern erst die Details auf Seite 2, dann rueckt der Rest zusammen ("eng").
const WX_KURVE_MIN = 96, WX_KURVE_KNAPP = 64;
// Kalender: so hoch (px) soll die Terminliste unter dem Monat mindestens werden
// (gut drei Termine), so breit eine Spalte, wenn Monat und Termine
// nebeneinander stehen.
const KAL_LISTE_MIN = 160, KAL_SPALTE_MIN = 220;
function inhaltsBox(e){ const cs=getComputedStyle(e);
  return { w: e.clientWidth-parseFloat(cs.paddingLeft)-parseFloat(cs.paddingRight),
           h: e.clientHeight-parseFloat(cs.paddingTop)-parseFloat(cs.paddingBottom) }; }
// eng: Datum der Vorschau, das nicht in seine Zelle passt, genau so weit
// verkleinern, wie die Zelle verlangt (die Breite haengt am Panel, ein festes
// Mass passt nicht ueberall). Ohne eng gilt wieder die Schrift aus dem CSS.
function vorschauDatumEinpassen(s){
  const eng=s.classList.contains('eng');
  s.querySelectorAll('.fp-fc .d').forEach(d=>{ d.style.fontSize='';
    if(!eng || d.scrollWidth<=d.clientWidth) return;
    const fs=parseFloat(getComputedStyle(d).fontSize);
    d.style.fontSize=Math.floor(fs*d.clientWidth/d.scrollWidth*10)/10+'px'; });
}
function wetterEinpassen(elc){
  const s=elc && elc.querySelector('.fp-page.wx'), w=(frontData||{}).weather;
  if(!s || !w || !s.clientHeight) return;    // nicht zu sehen: beim Einblenden (ResizeObserver)
  const box=inhaltsBox(s), kurve=s.querySelector('.fp-curve'), det=elc.querySelector('.fp-det');
  const s2=elc.querySelector('.fp-page.wxdet');
  s.classList.toggle('breit', box.w > box.h*PANE_BREIT);
  s.classList.toggle('schmal', box.w < WX_SCHMAL);
  s.classList.remove('eng');
  // Platz fuer die Kurve: sie nimmt, was die anderen Teile uebrig lassen
  const frei=()=> kurve ? kurve.clientHeight : Infinity;
  // passt: nichts ragt aus der Seite und kein Teil aus seinem Feld (nebeneinander
  // hat die Lage ein festes Feld, ein Ueberlauf laege mitten in der Seite)
  const passt=()=> s.scrollHeight <= s.clientHeight
    && ![...s.children].some(k=>!k.hidden && k.scrollHeight > k.clientHeight+1);
  // Die Details stehen einmal: unter der Vorschau, wenn die Kurve dann noch
  // genug Platz hat, sonst auf Seite 2.
  if(det){ s.appendChild(det); if(s2 && (frei()<WX_KURVE_MIN || !passt())) s2.appendChild(det); }
  if(s2) s2.hidden=!s2.children.length;
  if(frei()<WX_KURVE_KNAPP || !passt()) s.classList.add('eng');
  vorschauDatumEinpassen(s);
  if(kurve){ const hh=Array.isArray(w.hourly)?w.hourly:[];
    kurve.innerHTML=fpCurve(hh, kurve.clientWidth, kurve.clientHeight); }
}
function fpMonthHTML(events, holidays, colors){
  const base=new Date(); base.setDate(1); base.setMonth(base.getMonth()+calMonthOff);
  const y=base.getFullYear(), m=base.getMonth();
  const startDow=(new Date(y,m,1).getDay()+6)%7;    // 0 = Montag
  const dim=new Date(y,m+1,0).getDate();
  // Je Tag die Farben der Kalender sammeln, aus denen an ihm etwas ansteht —
  // jede Farbe nur einmal, damit fuenf Termine aus einem Abo nicht fuenf
  // gleiche Punkte ergeben.
  const evd=new Map();
  (events||[]).forEach(e=>{ if(!e||!e.date) return;
    const f=evd.get(e.date)||[]; if(e.color&&f.indexOf(e.color)<0) f.push(e.color);
    evd.set(e.date,f); });
  const hol=holidays||{}, todayISO=isoDay(new Date());
  const pad=n=>String(n).padStart(2,'0');
  const mn=new Date(y,m,1).toLocaleDateString(LANG,{month:'long',year:'numeric'});
  let html='<div class="fp-mon"><div class="fp-mon-h">'+
    '<span class="fp-mnav" data-mnav="-1">‹</span>'+
    '<span class="fp-mtitle">'+esc(mn)+'</span>'+
    '<span class="fp-mnav" data-mnav="1">›</span></div><div class="fp-mon-g">';
  html+=['Mo','Di','Mi','Do','Fr','Sa','So'].map((d,i)=>'<div class="fp-mon-wd'+(i===6?' sun':'')+'">'+d+'</div>').join('');
  for(let i=0;i<startDow;i++) html+='<div class="fp-mon-c empty"></div>';
  for(let d=1;d<=dim;d++){
    const iso=y+'-'+pad(m+1)+'-'+pad(d);
    const dow=(startDow+d-1)%7;                     // 5=Sa, 6=So
    const isHol=!!hol[iso];
    const farben=(colors!==false ? (evd.get(iso)||[]) : []).slice(0,3);
    const cls='fp-mon-c'+(dow===5?' sat':'')+((dow===6||isHol)?' sun':'')+(isHol?' holi':'')+
      (iso===todayISO?' today':'')+(evd.has(iso)?' ev':'')+(farben.length?' dots':'')+
      (iso===calSel?' sel':'');
    const punkte=farben.length
      ? '<span class="mdots">'+farben.map(c=>'<i style="background:'+esc(c)+'"></i>').join('')+'</span>' : '';
    html+='<div class="'+cls+'" data-day="'+iso+'"'+(isHol?(' title="'+esc(hol[iso])+'"'):'')+'>'+d+punkte+'</div>';
  }
  return html+'</div></div>';
}
function renderCalendarPane(elc, nachOben){ if(!elc) return; const d=frontData||{};
  // Eine Seite so hoch wie die Flaeche: oben der Monat, darunter die Termine,
  // die den Rest fuellen und fuer sich scrollen. Ein Tipp auf einen Tag zeigt
  // dessen Termine gleich darunter. Auf breiter Flaeche stehen Monat und
  // Termine nebeneinander (kalenderEinpassen). Die Legende steht unter dem
  // Monat: dort sind die Farbpunkte, die sie erklaert.
  // Die Liste behaelt ihre Stelle (neue Daten, anderer Monat - sie zeigt alle
  // kommenden Termine); ein gewaehlter Tag oder "Alle" beginnt oben.
  const alt=elc.querySelector('.kal-liste'), oben=(alt && !nachOben) ? alt.scrollTop : 0;
  elc.innerHTML='<div class="fp-page kal"><div class="kal-monat">'+fpMonthHTML(d.events, d.holidays, d.calColors)
      +fpLegendHTML(d)+'</div><div class="kal-liste">'+fpCalHTML(d, false)+'</div></div>';
  elc.querySelectorAll('[data-mnav]').forEach(b=>b.onclick=()=>{ calMonthOff+=parseInt(b.dataset.mnav)||0; renderCalendarPane(elc); });
  elc.querySelectorAll('[data-day]').forEach(c=>c.onclick=()=>{ calSel=(calSel===c.dataset.day?'':c.dataset.day); renderCalendarPane(elc, true); });
  elc.querySelectorAll('[data-calall]').forEach(b=>b.onclick=()=>{ calSel=''; renderCalendarPane(elc, true); });
  kalenderEinpassen(elc);
  const liste=elc.querySelector('.kal-liste'); if(liste && oben) liste.scrollTop=oben;
}
function kalenderEinpassen(elc){
  const s=elc && elc.querySelector('.fp-page.kal'); if(!s || !s.clientHeight) return;
  const box=inhaltsBox(s), liste=s.querySelector('.kal-liste'), monat=s.querySelector('.kal-monat');
  s.classList.remove('breit','eng','eng2');
  // Der Monat passt, wenn er weder aus der Seite noch aus seinem Feld ragt
  // (nebeneinander hat er ein festes Feld). Die Liste scrollt fuer sich.
  const passt=()=> s.scrollHeight <= s.clientHeight && monat.scrollHeight <= monat.clientHeight+1;
  // Nebeneinander, wenn die Flaeche breit ist oder unter dem Monat kaum Platz
  // fuer Termine bliebe - sofern zwei Spalten hineinpassen.
  if(box.w >= 2*KAL_SPALTE_MIN && (box.w > box.h*PANE_BREIT || liste.clientHeight < KAL_LISTE_MIN)) s.classList.add('breit');
  // Passt der Monat nicht oder bleibt untereinander zu wenig fuer die Termine,
  // ruecken die Tage zusammen, wenn noetig in zwei Stufen.
  const zuWenig=()=> !s.classList.contains('breit') && liste.clientHeight < KAL_LISTE_MIN;
  if(!passt() || zuWenig()) s.classList.add('eng');
  if(!passt() || zuWenig()) s.classList.add('eng2');
}
// Kalender-/Wetter-Seite (Tab "kalender"/"wetter", view.front): dieselben
// Bausteine wie die Split-Pane, aber auf der ganzen Kachelflaeche. Quer zwei
// Spalten, die je fuer sich scrollen (Kalender: Monat | alle Termine; Wetter:
// Lage, Kurve, Vorschau | Details), hoch/quadratisch untereinander.
function renderFrontTab(){
  const g=el('grid'), d=frontData||{}, art=view.front;
  const liste=g.querySelector('.ft-b'), oben=(g.classList.contains('fronttab') && liste) ? liste.scrollTop : 0;
  g.classList.remove('list','snapy','chartpage','lx','hpages','punkte','fuss','haus');
  g.classList.add('fronttab');
  if(art==='calendar'){
    g.innerHTML='<div class="ft ft-cal"><div class="ft-a">'+fpMonthHTML(d.events, d.holidays, d.calColors)
      +fpLegendHTML(d)+'</div><div class="ft-b">'+fpCalHTML(d)+'</div></div>';
    g.querySelectorAll('[data-mnav]').forEach(b=>b.onclick=()=>{ calMonthOff+=parseInt(b.dataset.mnav)||0; renderFrontTab(); });
    g.querySelectorAll('[data-day]').forEach(c=>c.onclick=()=>{ calSel=(calSel===c.dataset.day?'':c.dataset.day); renderFrontTab();
      const b=g.querySelector('.ft-b'); if(b) b.scrollTop=0; });
    g.querySelectorAll('[data-calall]').forEach(b=>b.onclick=()=>{ calSel=''; renderFrontTab(); });
  } else {
    const w=d.weather;
    g.innerHTML = w
      ? '<div class="ft ft-wx"><div class="ft-a"><div class="fp-h" data-i18n>Wetter</div>'+fpNowHTML(w)
        +fpWeatherDetailHTML(w)+'</div><div class="ft-b">'+fpCurveHTML(w)+fpForeHTML(w)+'</div></div>'
      : '<div class="ft ft-leer"><div class="fp-empty">Kein Wetter eingerichtet (Konfigurator → Einstellungen → Kalender &amp; Wetter).</div></div>';
  }
  const b=g.querySelector('.ft-b'); if(b && oben) b.scrollTop=oben;
  renderTabs();
}
