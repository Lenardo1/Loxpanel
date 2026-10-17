// LoxPanel-Visu, Teil 4 von 12: Tabs, Seiten blaettern, Kategorien, Split-Pane, Kopfzeile, Werteleiste, applyPane.
// Die Teile laden nacheinander aus panel.html (script src), alle Funktionen sind global;
// was beim Laden ausgefuehrt wird, darf nur Funktionen frueherer Teile rufen.

function activeTab(){ const b=stack[0]; return b && b.view==='tab' ? b.tab : null; }
// Anker-Kontext: der (einzige) Profil-Tab traegt eine Seite, deren untere
// Leiste Sprungmarken statt Seiten zeigt - ein Raum (Kategorien des Raums) oder
// die freie Auswahl (Raeume der Auswahl). Dann bleiben in ALLEN Ansichten (auch
// Detail) diese Tabs + mittiger Zurueck-Button unten stehen. roomCatTabs merkt
// sie sich fuer Ansichten ohne eigene catTabs. Der Name bleibt roomCatTabs bzw.
// isRoomPanel, damit sich kuenftige Upstream-Merges nicht daran reiben.
function isRoomPanel(){ const t = String(tabsCfg[0]||'');
  return tabsCfg.length===1 && (t.indexOf('room:')===0 || isPick(t)); }
let roomCatTabs=null, pendingCatScroll=null;
// Sprungmarken im Filter-Modus (Profil ui.catFilter): ein Tipp zeigt nur die
// Kacheln dieser Gruppe (Kategorie im Raum-Panel, Raum in der freien Auswahl),
// ein zweiter Tipp wieder alle. katFilter = aktive Gruppe oder null.
let themeCatFilter=false, katFilter=null;

function renderTabs(){
  // Raum-Panel: die untere Leiste zeigt die im Raum vorkommenden Kategorien
  // (vom Server als view.catTabs) als SCROLL-Tabs - ein Tipp scrollt zur Gruppe,
  // statt die Seite zu wechseln. Design bleibt: 4 Tabs + Zurueck-Button mittig.
  // In Detailansichten (kein view.catTabs) die gemerkten Tabs weiterzeigen.
  // Sprungmarken ERSETZEN die ganze Leiste. Das darf nur geschehen, wenn das
  // Panel ueberhaupt nur diese eine Seite hat: sonst waeren die uebrigen Tabs
  // nicht mehr antippbar, und der Zurueck-Knopf hilft nicht, weil die Seite
  // die unterste im Stapel ist. Frueher hing das daran, dass nur die
  // room:-Ansicht catTabs lieferte - steht ein room:-Tab in einer klassischen
  // Leiste, greift dieselbe Falle auch ohne die freie Auswahl.
  const anker = isRoomPanel();
  const ct = !anker ? null
           : (view && Array.isArray(view.catTabs))
             ? (view.catTabs.length ? view.catTabs : null)
             : (roomCatTabs && roomCatTabs.length ? roomCatTabs : null);
  // Seitenleiste (Kachel-Set "links"): Symbol und Name, Zurueck steht unten.
  // Mit Kachel-Set ist Zurueck ein Symbol wie die Tabs, ohne den Kreis.
  const links = kachelLeiste==='links';
  const nm = t => links ? '<span class="tnm">'+esc(t||'')+'</span>' : '';
  const backHtml = '<div class="tabback'+(stack.length>1?' on':'')+'" id="tabback">'+
    (kachelLeiste ? svg('<path d="M15 5l-7 7 7 7"/>')+nm('Zurück') : '‹')+'</div>';
  let items;
  if(ct){
    const tabsHtml = ct.map(c => {
      // Ohne Bild den NAMEN zeigen, nicht den Kategorie-Wuerfel: sonst sehen
      // mehrere Sprungmarken identisch aus und man kann nichts treffen.
      // Kategorien aus Loxone bringen fast immer ein Bild mit, Raeume selten.
      const ico = c.iconUrl
        ? '<span class="tico" style="--u:url(\''+esc(c.iconUrl)+'\')"></span>'
        : '<span class="tlbl">'+esc(c.label||'')+'</span>';
      return '<div class="tab'+(katFilter===c.key?' active':'')+'" data-cat="'+esc(c.key)+'" title="'+esc(c.label||'')+'">'+ico+nm(c.label)+'</div>';
    });
    // Zurueck-Button IMMER mittig: links ceil(N/2), rechts floor(N/2) Tabs; die
    // fehlende Zelle rechts mit einem leeren Spacer auffuellen, damit beide
    // Seiten gleich breit sind (1->links, 2->je einer, 3->2+1, 4->symmetrisch).
    const N=tabsHtml.length, leftN=Math.ceil(N/2), pad=leftN-(N-leftN);
    if(links) items = tabsHtml.concat([backHtml]);
    else {
      items = tabsHtml.slice(0,leftN).concat([backHtml]).concat(tabsHtml.slice(leftN));
      for(let s=0;s<pad;s++) items.push('<div class="tabspacer" aria-hidden="true"></div>');
    }
  } else {
    const at = activeTab();
    items = tabsCfg.map(tk => {
      const cls = 'tab'+(tk===at?' active':'');
      const t = TABS.find(x => x.tab===tk);
      if(t) return '<div class="'+cls+'" data-tab="'+esc(tk)+'" title="'+esc(t.label)+'">'+svg(t.icon)+nm(t.label)+'</div>';
      const m = tabMeta[tk]; if(!m) return '';   // dynamischer Tab (Kategorie/Raum)
      // Ohne Bild aus Loxone: Raum bekommt das Raum-Symbol, Kategorie den Wuerfel -
      // sonst sehen ein Raum- und ein Kategorie-Tab identisch aus.
      const fallback = m.haus
        // freie Seite mit der Hausuebersicht: dasselbe Haus wie der Tab "haus"
        ? TABS.find(x => x.tab==='haus').icon
        : isPick(tk)
        // Checkliste: klar unterscheidbar von Favoriten-Stern, Haus, Raum und
        // Kategorie-Wuerfel. Die freie Auswahl hat kein Bild aus Loxone, weil
        // sie weder Raum noch Kategorie ist - dieses Symbol gilt immer.
        ? '<path d="M9 6h11"/><path d="M9 12h11"/><path d="M9 18h11"/>'
          +'<path d="m3 6 1.4 1.4L7 4.9"/><path d="m3 12 1.4 1.4L7 10.9"/>'
          +'<path d="m3 18 1.4 1.4L7 16.9"/>'
        : tk.indexOf('room:')===0
        ? '<rect x="4" y="4" width="16" height="16" rx="2"/><path d="M14 4v16"/>'
        : '<path d="m12 3 8 4.5v9L12 21l-8-4.5v-9z"/>';
      const ico = m.iconUrl
        ? '<span class="tico" style="--u:url(\''+esc(m.iconUrl)+'\')"></span>'
        : svg(fallback);
      return '<div class="'+cls+'" data-tab="'+esc(tk)+'" title="'+esc(m.label||'')+'">'+ico+nm(m.label)+'</div>';
    }).filter(Boolean);
    items.splice(links ? items.length : Math.floor(items.length/2), 0, backHtml);
  }
  el('tabs').innerHTML = items.join('');
  el('tabs').style.setProperty('--tab-n', items.length);   // Pille so breit wie ihre Eintraege (--pille-tab-breite)
  if(ct) el('tabs').querySelectorAll('.tab[data-cat]').forEach(n => n.onclick=()=>katTipp(n.dataset.cat));
  else   el('tabs').querySelectorAll('.tab').forEach(n => n.onclick=()=>goTab(n.dataset.tab));
  const tb = el('tabs').querySelector('#tabback'); if(tb) tb.onclick = back;
  applyPane();
}
// Waagerechte Seiten (Tablet) oder senkrechtes Einrasten (4"-Panel)? Auf
// einem Tablet mit Split wischt man Seiten wie in der Loxone-App zur Seite,
// mit Punkten darunter; das quadratische 4"-Panel und ein Profil mit Split
// "aus" blaettern weiter senkrecht. Listen (layout "list") bleiben immer
// senkrecht. Quadratisch: Breite und Hoehe weniger als ein Zehntel auseinander.
function quadratisch(){ const {w,h}=vpSize(); return LoxRaster.quadratisch(w, h); }
function seitenQuer(v){
  v=v||view;
  return !!(v && themeSplit && !v.widget && !v.front && v.layout!=='list' && !quadratisch());
}
function seiteAktuell(){ const g=el('grid'); return g.clientWidth>0 ? Math.round(g.scrollLeft/g.clientWidth) : 0; }
function seiteZu(k){ const g=el('grid'); g.scrollTo({left:Math.max(0,k)*g.clientWidth, behavior:'smooth'}); }
function punkteNachziehen(){
  const g=el('grid'), s=seiteAktuell();
  g.querySelectorAll('.punkte i').forEach((d,k)=>d.classList.toggle('on', k===s));
}
// Zur SEITE springen, auf der die Kachel steht. Die Kachelflaeche rastet
// seitenweise ein (scroll-snap mandatory, Rastpunkt = erste Kachel jeder
// Seite). Ein Sprung direkt auf eine Kachel im unteren Teil einer Seite
// landete am naechstgelegenen Rastpunkt - oft schon auf der FOLGENDEN Seite,
// und die Zielkachel verschwand oben (gemessen 2x2 und 2x3: 199 bzw. 210 px
// ueber dem sichtbaren Bereich). Waagerechte Seiten: zur Seite der Kachel.
function springeZu(d){
  const g=el('grid'), tiles=[...g.querySelectorAll('.tile[data-id]')];
  if(g.classList.contains('hpages')){
    const p=d.closest('.page'); if(p) seiteZu([...g.querySelectorAll('.page')].indexOf(p));
    return;
  }
  const i=tiles.indexOf(d);
  let ziel=d;
  if(i>=0 && g.classList.contains('snapy')){
    if(view && view.layout==='list') ziel=tiles[Math.floor(i/4)*4];
    else {   // erste Kachel in der ersten Zeile der Seite (Lage aus rasterLage, breite Kacheln mitgerechnet)
      const z=g._zeile||[], start=Math.floor((z[i]||0)/gridRows)*gridRows, j=z.findIndex(r=>r===start);
      if(j>=0) ziel=tiles[j]; }
  }
  ziel.scrollIntoView({behavior:'smooth', block:'start'});
}
// Kacheln der Gruppe kurz hervorheben: auch wenn nichts scrollt (die Gruppe
// steht schon im Bild), sieht man so, welche Bausteine gemeint sind.
let _leuchtTimer=null;
function leuchte(key){
  // Die vorige Gruppe zuerst abraeumen: bei schnellem Tippen loescht der neue
  // Timer den alten, dessen Kacheln behielten sonst die Klasse.
  el('grid').querySelectorAll('.tile.katleucht').forEach(n=>n.classList.remove('katleucht'));
  const ns=[...el('grid').querySelectorAll('.tile[data-id]')].filter(n=>n._it && n._it.grp===key);
  ns.forEach(n=>{ n.classList.remove('katleucht'); void n.offsetWidth; n.classList.add('katleucht'); });
  clearTimeout(_leuchtTimer);
  _leuchtTimer=setTimeout(()=>ns.forEach(n=>n.classList.remove('katleucht')), 1600);
}
// Tipp auf eine Sprungmarke: springen (Standard) oder filtern (ui.catFilter).
function katTipp(key){
  if(!themeCatFilter){ scrollToCat(key); return; }
  katFilter=(katFilter===key) ? null : key;   // zweiter Tipp auf dieselbe Marke: wieder alle
  // Auf der Seite mit den Marken neu zeichnen; aus einer Detailansicht zurueck
  // in den Raum - dort greift der Filter beim Rendern.
  if(view && Array.isArray(view.catTabs)){ render(); el('grid').scrollTop=0; el('grid').scrollLeft=0; }
  else { const rt=tabsCfg[0]; if(rt) goTab(rt); }
}
// Kacheln, die im Filter-Modus sichtbar sind. Nur auf der Seite mit den Marken
// (view.catTabs), nicht in Detailansichten. Gibt es die Gruppe nicht mehr
// (Konfiguration geaendert), faellt der Filter weg, statt eine leere Seite zu zeigen.
function katSichtbar(items){
  if(!katFilter || !view || !Array.isArray(view.catTabs)) return items;
  const f=items.filter(it=>it.grp===katFilter);
  if(!f.length){ katFilter=null; return items; }
  return f;
}
// Raum-Panel: zur ersten Kachel einer Kategorie scrollen. Sind wir in einer
// Detailansicht (die Kachel ist gerade nicht da), erst zurueck in den Raum und
// nach dem Rendern dorthin scrollen (pendingCatScroll, s. render()).
function scrollToCat(key){
  const d = el('grid').querySelector('.tile[data-cat="'+key+'"]');
  if(d){ springeZu(d); leuchte(key); return; }
  pendingCatScroll = key;
  const rt = tabsCfg[0]; if(rt) goTab(rt);
}
// ---- Split-Pane pro Tab: entscheidet je aktuellem Tab, was in Pane 2 steht (quer rechts, hochkant unten) ----
// Wert je Tab: "weather" | "calendar" | "player:<zone>" | "energy:<uuid>" | "camera:<uuid>" | "chart:<uuid>" | "status:<uuid>,...".
function paneForTab(tk){ return tk ? (panesCfg[tk]||null) : null; }
// Split hochkant (Widget unter den Kacheln) oder quer (daneben). Im automatischen Raster
// entscheidet raster.js nach der Flaeche des Rasters, ohne Seitenleiste und Rahmen eines
// Kachel-Sets; das CSS muss dieselbe Achse nehmen (900 x 750 mit Seitenleiste ist ein Raster
// von 692 x 750, also hochkant). Sonst nach dem Fenster, wie festesRaster().
function splitHoch(){
  if(gridAuto) return autoRaster(_lastWidget).hoch;
  const vp=vpSize(); return vp.h > vp.w;
}
// Split im Hochformat: Visu und Pane 2 uebereinander (CSS .screen.split.hoch).
// Eigene Funktion, weil sie auch beim Drehen laufen muss - dort wird nicht in
// jedem Fall neu gerendert (z.B. Anlagenschema, Screensaver oben).
function applyHoch(){
  const sc=document.querySelector('.screen'); if(!sc) return;
  sc.classList.toggle('hoch', sc.classList.contains('split') && splitHoch());
}
// Der aktuell gezeigte Pane-Wert: eine Widget-Seite (Vollbild-Tab, view.widget)
// ODER die Pane 2 des aktiven Tabs (nur im 2-Pane-Betrieb). Damit finden die
// Push-Handler (energy/camera/chart/status) auch das Widget eines Widget-Tabs.
function paneRawNow(){ if(view && view.widget) return view.widget;
  // Die Hausuebersicht bringt Kopf und Spieler selbst mit: keine Pane, keine Kopfzeile
  if(view && view.layout==='haus') return null;
  const v=paneForTab(activeTab());
  // Die Kopfzeile ist keine Pane: sie gilt auch mit Split "Aus" (4"-Panel),
  // ein Widget daneben nur im 2-Pane-Betrieb.
  return (themeSplit || paneKind(v)==='header') ? v : null; }
function paneKind(v){ if(!v) return null;
  for(const k of ['player','energy','camera','chart','status','header']) if(v.indexOf(k+':')===0) return k;
  return v; }
// ---- Kopfzeile (Widget "header") ----
// Uhr, Wetter kurz und bis zu SV_STATUS_MAX Werte in einer Zeile ueber dem
// Kachelraster. Kein Split: der Kasten bekommt nur eine Zeile mehr. Die Werte
// kommen wie bei "status" per {t:'svstatus'} (setsvstatus in applyPane), das
// Wetter aus {t:'front'}, die Uhr tickt mit tickClock().
function kopfAktiv(){ return paneKind(paneRawNow())==='header'; }
function kopfHoehe(ks){ return kopfAktiv() ? Math.round(KOPF_H*(ks||kachelFaktor)) : 0; }
// Ein Wert als Chip (Symbol, Wert, Name) - Kopfzeile und Werteleiste; attrs:
// weitere Attribute (data-i, data-id der Werteleiste). Als Wert der Messwert, den
// die Kachel gross zeigt (big, etwa die Ist-Temperatur der Raumregelung), sonst
// die Zweitzeile: "21,0°" passt in die Zeile, "21,0° → 22,5° · heizt" oft nicht.
function kopfWertHtml(it, attrs){
  const ton=(it.tone==='good')?' good':((it.tone==='crit')?' crit':(it.on?' on':''));
  const ico = it.iconUrl ? '<span class="ico img" style="--u:url(\''+esc(it.iconUrl)+'\')"></span>'
    : '<span class="ico">'+svg(ICONS[it.icon]||ICONS.info)+'</span>';
  return '<div class="kz-w'+ton+'"'+(attrs||'')+(it.color?' style="--ico:'+esc(it.color)+'"':'')+'>'+ico+
    '<span class="vl">'+esc(it.big||it.sublabel||'')+'</span><span class="nm">'+esc(it.label||'')+'</span></div>';
}
function kopfWerteHtml(items){ return items.map(it=>kopfWertHtml(it)).join(''); }
function renderKopfzeile(){
  const kz=el('kopfzeile'); if(!kz || !kopfAktiv()) return;
  const d=frontData||{}, w=d.weather;
  let html='<div class="kz-uhr"><span class="t" id="kzTime">--:--</span><span class="d" id="kzDate"></span></div>';
  if(w){ html+='<div class="kz-wx"><span class="ico">'+wxSvg(w.icon)+'</span><span class="t">'+tdeg(w.temp)+'</span>'+
    '<span class="m"><span class="c">'+esc(w.cond||'')+'</span>'+
    ((w.hi!=null||w.lo!=null)?'<span>Heute '+tdeg(w.hi)+' / '+tdeg(w.lo)+'</span>':'')+'</span></div>'; }
  // Werte nur, wenn die Kopfzeile welche nennt ("header:<uuid>,…") und der
  // Server sie schon geschickt hat; solange nicht, steht dort nichts.
  const items=(svArg(paneRawNow()||'') && Array.isArray(svStatusData)) ? svStatusData : [];
  if(items.length) html+='<div class="kz-werte">'+kopfWerteHtml(items)+'</div>';
  kz.innerHTML=html; tickClock(); kopfEinpassen();
}
// Was rechts nicht mehr in die Zeile passt, bleibt weg - lieber drei ganze
// Werte als vier angeschnittene. Die gewaehlten Werte gehen dem Wettertext vor
// (Lage, Hoch/Tief): fiele sonst ein Wert weg, bleiben vom Wetter Symbol und
// Temperatur.
function kopfEinpassen(){
  const kz=el('kopfzeile'); if(!kz || kz.hidden) return;
  const box=kz.querySelector('.kz-werte'); if(!box) return;
  const wxText=kz.querySelector('.kz-wx .m');
  const passen=()=>{ const rechts=box.getBoundingClientRect().right;
    [...box.children].forEach(c=>{ c.hidden=false; });
    let weg=false;
    [...box.children].forEach(c=>{ if(c.getBoundingClientRect().right > rechts+1){ c.hidden=true; weg=true; } });
    return weg; };
  if(wxText) wxText.hidden=false;
  if(passen() && wxText){ wxText.hidden=true; passen(); }
}
// ---- Werteleiste (ui.valueBar, view.leiste) ----
// Die Anzeige-Bausteine einer Seite (Messwerte, Zaehler, Texte, Ein/Aus-
// Anzeigen) als Kette von Werten in EINER Zeile ueber dem Raster statt als
// Kacheln; der Server trennt sie (_leiste_trennen), das Raster bleibt dem
// Bedienbaren. Dieselben Chips wie die Werte der Kopfzeile, ein Tipp oeffnet
// wie die Kachel die Wertseite. Was nicht in die Zeile passt, scrollt
// waagerecht - nicht ausblenden wie dort: diese Werte haben keine Kachel mehr.
function leisteAktiv(){ return !!(view && !view.widget && !view.front && Array.isArray(view.leiste) && view.leiste.length); }
function leisteHoehe(ks){ return leisteAktiv() ? Math.round(LEISTE_H*(ks||kachelFaktor)) : 0; }
function leisteChip(it,i){ return kopfWertHtml(it, ' data-i="'+i+'" data-id="'+esc(String(it.id))+'"'); }
function renderLeiste(){
  const lz=el('werteleiste'), sc=document.querySelector('.screen'); if(!lz || !sc) return;
  const an=leisteAktiv();
  sc.classList.toggle('leiste', an); lz.hidden=!an;
  if(!an){ lz.innerHTML=''; return; }
  lz.innerHTML=view.leiste.map(leisteChip).join('');
  lz.querySelectorAll('.kz-w').forEach(n=>{ n.onclick=()=>{ const it=view.leiste[+n.dataset.i]; if(it&&it.nav) nav(it.nav); }; });
}
// Gleiche Seite, neue Werte: nur Zustand, Symbol und Texte der Chips nachziehen,
// die Zeile bleibt stehen (Scroll-Lage, keine neuen Elemente). Andere Werte
// oder eine andere Anzahl -> false, dann baut render() neu.
function updateLeiste(items){
  const lz=el('werteleiste'); if(!lz) return false;
  const neu=Array.isArray(items)?items:[];
  const nodes=lz.hidden?[]:[...lz.querySelectorAll('.kz-w')];
  if(nodes.length!==neu.length) return false;
  for(let i=0;i<neu.length;i++){ if(String(neu[i].id)!==nodes[i].dataset.id) return false; }
  neu.forEach((it,i)=>{
    const n=nodes[i], tmp=document.createElement('div'); tmp.innerHTML=leisteChip(it,i);
    const soll=tmp.firstChild;
    if(n.className!==soll.className) n.className=soll.className;
    if((n.getAttribute('style')||'')!==(soll.getAttribute('style')||'')) n.setAttribute('style', soll.getAttribute('style')||'');
    ['.ico','.vl','.nm'].forEach(q=>{ const a=n.querySelector(q), b=soll.querySelector(q); if(a&&b&&a.outerHTML!==b.outerHTML) a.outerHTML=b.outerHTML; });
  });
  return true;
}
// Mausrad ueber der Zeile scrollt sie waagerecht (am Touch-Panel wischt man)
{ const lz=el('werteleiste'); if(lz) lz.addEventListener('wheel', e=>{
    if(Math.abs(e.deltaY)>Math.abs(e.deltaX) && lz.scrollWidth>lz.clientWidth){ lz.scrollLeft+=e.deltaY; e.preventDefault(); } }, {passive:false}); }
function applyPane(){
  const sc=document.querySelector('.screen'); if(!sc) return;
  // Widget-Seite (Vollbild-Tab): das ganze Tab IST das Widget, kein Kachelgrid,
  // kein Split. Sonst die Pane 2 des aktiven Tabs (nur im 2-Pane-Betrieb).
  const wt = (view && view.widget) ? view.widget : null;
  const raw = paneRawNow();   // Widget-Seite, Pane 2 (nur mit Split) oder Kopfzeile (immer)
  const kind=paneKind(raw);
  const isPane=(kind==='player'||kind==='weather'||kind==='calendar'||kind==='energy'||kind==='camera'||kind==='chart'||kind==='status');   // Widget in Pane 2
  const isKopf=(kind==='header' && !wt);   // Kopfzeile ueber dem Raster, kein Split
  sc.classList.toggle('widgettab', !!wt);   // Widget fuellt die ganze Flaeche
  sc.classList.toggle('split', isPane && !wt);   // Widget in Pane 2 -> zweigeteilt
  sc.classList.toggle('kopf', isKopf);
  { const kz=el('kopfzeile'); if(kz){ kz.hidden=!isKopf; if(isKopf) renderKopfzeile(); else kz.innerHTML=''; } }
  applyHoch();
  sc.classList.toggle('fill', themeFill || gridAuto>0);  // "Bildschirm fuellen" fuellt Split UND Screen-fuellen
  sc.classList.toggle('auto', gridAuto>0);   // automatisches Raster: Widget auf ganzen Kachelspalten
  const pp=el('playerpane'), fp=el('frontpane');
  if(pp) pp.hidden=(kind!=='player');
  if(fp){
    fp.hidden=!(kind==='weather'||kind==='calendar'||kind==='energy'||kind==='camera'||kind==='chart'||kind==='status');
    fp.classList.toggle('cam', kind==='camera');
    // Kamera verlassen -> Video-Stream stoppen (Inhalt leeren), keine Hintergrund-Verbindung.
    // Auch, wenn der Screensaver darueber liegt: das <img> haengt direkt an
    // /mjpeg und streamt sonst unsichtbar weiter.
    if((kind!=='camera' || svSideOn()) && fp.dataset.cam!==undefined){ fp.innerHTML=''; delete fp.dataset.cam; delete fp.dataset.camsig; }
  }
  if(kind==='weather') renderWeatherPane(fp);
  else if(kind==='calendar') renderCalendarPane(fp);
  else if(kind==='energy') renderEnergyPane(fp);
  else if(kind==='camera' && !svSideOn()) renderCameraPane(fp);
  else if(kind==='chart') renderChartPane(fp);
  else if(kind==='status') renderWertePane(fp);   // frei gewaehlte Werte als Pane 2
  // Energiefluss und Kamera hat der Server je Verbindung nur EINMAL. Liegt der
  // Screensaver oben, gilt SEINE Wahl — die Pane darunter ist verdeckt, und ein
  // Kamerabild hinter dem Screensaver waere eine Dauerverbindung zur
  // Tuerstation, die niemand sieht. Sonst zaehlt die Pane des aktiven Tabs.
  const qraw = svSideOn() ? svSideRaw() : (raw||'');
  const qarg = (v,kopf)=> (v && v.indexOf(kopf)===0) ? v.slice(kopf.length) : '';
  // Energiefluss-Kachel dem Server melden (er pusht dann {t:'energy'}).
  const euid=qarg(qraw,'energy:');
  if(euid!==curEnergyUuid){ curEnergyUuid=euid; try{ send({t:'setenergy',uuid:euid}); }catch(e){} }
  // Kamera (Intercom) dem Server melden (er pusht dann {t:'camera'} mit Video+Buttons).
  // "camera:<uuid>|<uuid>,..." - hinter dem Strich stehen Werte unter dem Bild
  const camArg=qarg(qraw,'camera:'), cuid=camPaneUuid(camArg);
  if(cuid!==curCameraUuid){ curCameraUuid=cuid; cameraData=null;
    if(fp){ delete fp.dataset.cam; delete fp.dataset.camsig; }
    const sb=el('svBox'); if(sb){ delete sb.dataset.cam; delete sb.dataset.camsig; }
    try{ send({t:'setcamera',uuid:cuid}); }catch(e){}
    // Sofort einen Platzhalter zeigen, bis der Push kommt — je nachdem, wo die
    // Kamera gerade hingehoert.
    if(cuid){ if(svSideOn()) renderFront(); else if(kind==='camera') renderCameraPane(fp); }
  }
  // Verlaufs-Pane: Baustein und gewaehlten Zeitraum melden (er pusht dann
  // {t:'chart'}). Wie bei Energie/Kamera zaehlt der Screensaver, wenn er oben
  // liegt (chart als zweite Uhr-Spalte), sonst die Pane des aktiven Tabs.
  const chuid=qarg(qraw,'chart:');   // ein oder mehrere Bausteine, komma-getrennt
  const chkey=chuid ? chuid+'|'+chartRange : '';
  if(chkey!==curChartKey){ curChartKey=chkey; chartData=null;   // alten Stapel verwerfen, bis der neue Push kommt
    try{ send({t:'setchart',uuid:chuid,range:chartRange}); }catch(e){} }
  // Player-Zone (Audio) kontextabhaengig: liegt der Screensaver oben, seine Zone
  // (Audio als zweite Uhr-Spalte), sonst die Pane 2 des aktiven Tabs. Server
  // pusht {t:'player'} mit Cover/Titel/Transport.
  const zone=qarg(qraw,'player:');
  if(zone!==curPlayerZone){ curPlayerZone=zone; _playerBuilt=false; try{ send({t:'setplayer',zone:zone}); }catch(e){} }
  // Frei gewaehlte Werte (status) ebenso kontextabhaengig — Pane 2, Kopfzeile
  // ODER Uhr-Seite; die Kopfzeile nennt ihre Werte als "header:<uuid>,…", die
  // Kamera-Pane ihre Werte unter dem Bild als "camera:<uuid>|<uuid>,…".
  const suu = (svKind(qraw)==='status' || svKind(qraw)==='header') ? svArg(qraw)
            : ((svKind(qraw)==='camera') ? camPaneWerte(svArg(qraw)) : '');
  if(suu!==curSvStatus){ curSvStatus=suu; svStatusData=null;
    try{ send({t:'setsvstatus', uuids: suu?suu.split(','):[]}); }catch(e){} }
}

// Inline-Style (CSS-Variablen + Farben) einer Kachel — von render() und
// updateGrid() gemeinsam genutzt, liefert den ROHEN Style (ohne HTML-Escape).
