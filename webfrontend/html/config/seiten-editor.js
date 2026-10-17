// LoxPanel-Konfigurator, Teil 6 von 11: Seiten-Editor: Zeichnen, Bedienung, Ziehen.
// Die Teile laden nacheinander aus config.html (script src), alle Funktionen sind global;
// was beim Laden ausgefuehrt wird, darf nur Funktionen frueherer Teile rufen.

// ---- Seiten-Editor (Punkt 10) ----
// Ordnet eine freie Seite auf einer Arbeitsflaeche in Geraeteform: Bausteine
// aus der Palette ziehen, Kacheln verschieben (Maus, Finger, in der Liste am
// Griff; oder antippen und Pfeiltasten), Groesse 1x1, 2x1 oder 2x2, ein
// Widget daneben oder die Kopfzeile darueber. Die Flaeche zeigt, was die Visu
// am gewaehlten Geraet baut: dasselbe Raster aus raster.js (Automatik mit den
// Kacheln der Seite samt Wachsen und Schrumpfen, sonst fest mit Verdopplung
// durch den Split), dieselbe Lage (rasterLage) und dieselbe Folge wie der
// Server (_view_tab): ausgeblendete Bausteine fallen weg, auf einer Seite mit
// Werteleiste wandern die Anzeige-Bausteine in die Leiste, und mit „Nach
// Raeumen gruppieren" (byRoom, Standard an) stehen die Kacheln nach Raum.
// Eine Seite traegt picks (was drauf ist) und layout [{id, w, h}] (Folge und
// Groesse); der Editor schreibt immer beides (seSchreiben), damit der Server
// beim Speichern nichts verwerfen muss.
// Zwei Aufrufer, je mit eigenem Kontext: der Reiter „Seiten-Editor" im
// Panel-Editor (seKontextReiter).
const SE_WIDGETS=[['weather','Wetter'],['calendar','Kalender'],['audio','Audio'],['energy','Energiefluss'],
  ['camera','Kamera'],['chart','Verlauf'],['header','Kopfzeile']];
const SE_PANE_NAMEN={weather:'Wetter', calendar:'Kalender', player:'Audio', energy:'Energiefluss',
  camera:'Kamera', chart:'Verlauf', status:'Werte', header:'Kopfzeile', haus:'Hausübersicht'};
const SE_GRIFF='<svg viewBox="0 0 10 16" width="10" height="16" aria-hidden="true"><g fill="currentColor">'+
  '<circle cx="2.5" cy="3" r="1.4"/><circle cx="7.5" cy="3" r="1.4"/><circle cx="2.5" cy="8" r="1.4"/>'+
  '<circle cx="7.5" cy="8" r="1.4"/><circle cx="2.5" cy="13" r="1.4"/><circle cx="7.5" cy="13" r="1.4"/></g></svg>';
const SE_MAX=60;              // derselbe Deckel wie der Server
const SE_ZUSTAND={};          // je Seite (ctx.key): Auswahl, Blatt; je Panel (ctx.pkey): Filter, Meldung
const SE_VORSCHAU={};         // Kennung -> gewaehltes Vorschaugeraet {quelle, name}
let SE_ZIEHEN=null;           // laufendes Ziehen (Pointer-Events)
function seZustand(k){ return SE_ZUSTAND[k]||(SE_ZUSTAND[k]={sel:null, blatt:0, folgen:null, raum:'', q:'', meldung:''}); }
let _seCtrlQuelle=null, _seCtrlMap=null;
function seCtrl(u){ const cs=(META&&META.controls)||[];
  if(_seCtrlQuelle!==cs){ _seCtrlQuelle=cs; _seCtrlMap=new Map(cs.map(c=>[c.uuid,c])); }
  return _seCtrlMap.get(u); }
// Breite ohne Eintrag im Layout: tiles[uuid].w, sonst nach Typ (KACHEL_BREIT_TYPEN) wie _control_item()
function seStdBreite(tiles, u){ const t=(tiles||{})[u], w=t?parseInt(t.w):NaN;
  if(w===1||w===2) return w;
  return (META.kachelBreit||[]).indexOf((seCtrl(u)||{}).type)>-1 ? 2 : 1; }
// Folge einer Seite, wie der Server sie liest (_layout_mit_picks): die
// Layout-Eintraege der picks in ihrer Folge, dahinter die picks ohne Eintrag
// mit ihrer Standardbreite. Hoch ist immer auch breit.
function seFolge(pg, tiles){
  const picks=(pg&&Array.isArray(pg.picks))?pg.picks:[], drin=new Set(picks), da=new Set(), out=[];
  ((pg&&Array.isArray(pg.layout))?pg.layout:[]).forEach(e=>{
    if(!e || typeof e.id!=='string' || !drin.has(e.id) || da.has(e.id)) return;
    da.add(e.id); const h=(+e.h===2)?2:1;
    out.push({id:e.id, w:(h===2 || +e.w===2)?2:1, h:h}); });
  picks.forEach(u=>{ if(typeof u==='string' && !da.has(u)){ da.add(u); out.push({id:u, w:seStdBreite(tiles,u), h:1}); } });
  return out;
}
function seSchreiben(pg, folge){
  pg.picks=folge.map(e=>e.id);
  if(folge.length) pg.layout=folge.map(e=>({id:e.id, w:e.w, h:e.h})); else delete pg.layout;
}
// Was die Visu von der Seite zeigt (_view_tab): ohne ausgeblendete und
// unbekannte Bausteine; mit Werteleiste ohne die Anzeige-Bausteine, ausser die
// Seite bestuende nur aus ihnen (_leiste_trennen); mit byRoom nach Raum in der
// Folge des ersten Bausteins je Raum, Bausteine ohne bekannten Raum hinten.
function seAnsicht(ctx){
  const pg=ctx.seiteLesen()||{}, folge=seFolge(pg, ctx.tiles()), hide=new Set(ctx.hide());
  let raster=folge.filter(e=>!hide.has(e.id) && seCtrl(e.id)), leiste=[];
  if(ctx.ui().werteLeiste){
    const typen=new Set(META.werteLeiste||[]), l=raster.filter(e=>typen.has(seCtrl(e.id).type));
    if(l.length && l.length<raster.length){ const weg=new Set(l.map(e=>e.id)); leiste=l; raster=raster.filter(e=>!weg.has(e.id)); }
  }
  const nachRaum=pg.byRoom!==false;
  if(nachRaum){
    const bekannt=new Set((META.rooms||[]).map(r=>r.uuid)), gruppen=new Map(), vorn=[], hinten=[];
    raster.forEach(e=>{ const c=seCtrl(e.id), r=(c.room==null)?'\u0000':String(c.room);
      if(!gruppen.has(r)) gruppen.set(r,[]); gruppen.get(r).push(e); });
    gruppen.forEach((es,r)=>{ (bekannt.has(r)?vorn:hinten).push(...es); });
    raster=vorn.concat(hinten);
  }
  return {pg:pg, folge:folge, raster:raster, leiste:leiste, nachRaum:nachRaum};
}
function sePaneArt(v){ if(!v) return ''; const i=v.indexOf(':'); return i>0?v.slice(0,i):v; }
// Zeigt die Visu das Hinweis-Symbol der Gesten (Vorgaben und Ansicht gemischt,
// ohne Eintrag der Standard aus /api/meta)? Dann reserviert sie die Fusszeile
// unter dem Kachelfeld (raster.js fussH), die Vorrechnung zieht sie genauso ab.
function gestenHinweisGilt(u){
  const an=(k, std)=>typeof u[k]==='boolean' ? u[k] : !!(META||{})[std];
  return an('gesten', 'gestenStandard') && an('gestenHinweis', 'gestenHinweisStandard');
}
// Raster am Vorschaugeraet, wie rasterFuer()/autoRaster() der Visu es rechnen.
// Widget nur mit Split (die Kopfzeile ist keines: sie nimmt eine Zeile Hoehe);
// waagerechte Seiten mit Punkten wie seitenQuer(): Split und kein quadratischer Schirm.
function seRaster(ctx, a){
  const u=ctx.ui(), g=ctx.geraet(), M=LoxRaster.VISU_MASSE, art=sePaneArt(u.pane);
  const kopf=art==='header', widget=u.split && !!art && !kopf, leiste=a.leiste.length>0;
  const quer=u.split && !LoxRaster.quadratisch(g.vw, g.vh), lm=leisteMasse(u.tileSet, g.vw, g.vh);
  const basis={art:art, kopf:kopf, widget:widget, leiste:leiste, quer:quer, hoch:g.vh>g.vw, tabLeiste:lm};
  if(u.auto){
    const r=LoxRaster.autoRaster(Object.assign({}, M, lm, {w:g.vw, h:g.vh, ziel:u.ziel, wachsen:kachelZiel().wachsen||1,
      widget:widget, paneCols:u.paneCols||0, paneShare:(META.paneCols||{}).anteil||0, seitenQuer:quer,
      fussH:LoxRaster.fussH(u.hinweis, quer, g.vw, M.hinweisH),
      breiten:a.raster.map(e=>({w:e.w, h:e.h})),
      kopfH:kopf?(ks=>Math.round(LoxRaster.KOPF_H*ks)):null, leisteH:leiste?(ks=>Math.round(LoxRaster.LEISTE_H*ks)):null}));
    return Object.assign(basis, r, {auto:true});
  }
  const [c, rw]=LoxRaster.festesRaster({cols:u.cols, rows:u.rows, w:g.vw, h:g.vh, split:u.split, widget:widget});
  return Object.assign(basis, {cols:c, rows:rw, k:1, p:widget?1:0, ks:1, auto:false});
}
// Flaechen der Visu am Geraet in Geraete-Pixeln: Tab-Leiste unten (Kachel-Set:
// oben oder als Seitenleiste links), Widget rechts (hochkant darunter) mit den
// Anteilen k:p der Automatik (fest: halb und halb wie .screen.split),
// Kopfzeile und Werteleiste ueber dem Raster, die Seitenpunkte darunter.
function seGeometrie(r, g, seiten){
  const lm=r.tabLeiste||leisteMasse('', g.vw, g.vh), M=Object.assign({}, LoxRaster.VISU_MASSE, {gap:lm.gap, pad:lm.pad}), ks=r.ks||1;
  const kopfH=r.kopf?Math.round(LoxRaster.KOPF_H*ks):0, leisteH=r.leiste?Math.round(LoxRaster.LEISTE_H*ks):0;
  const punkteH=(r.quer && seiten>1)?M.punkteH:0;
  const rs=lm.rahmenX/2, x0=lm.railW+rs, y0=(lm.art==='oben')?lm.tabsH:0;
  let w=g.vw-lm.railW-lm.rahmenX, h=g.vh-lm.tabsH-lm.rahmenY, pane=null;
  if(r.widget){
    if(r.hoch){ const ph=r.pPx ? r.pPx : h*r.p/(r.k+r.p); pane={x:x0, y:y0+h-ph, w:w, h:ph}; h-=ph; }
    else { const pw=w*r.p/(r.k+r.p); pane={x:x0+w-pw, y:y0, w:pw, h:h}; w-=pw; }
  }
  const raster={x:x0, y:y0+kopfH+leisteH, w:w, h:Math.max(1, h-kopfH-leisteH-punkteH)};
  const tabs=lm.railW ? {x:0, y:0, w:lm.railW, h:g.vh} : {x:rs, y:(lm.art==='oben')?0:g.vh-lm.tabsH, w:g.vw-lm.rahmenX, h:lm.tabsH};
  return {M:M, pane:pane, raster:raster,
    kopf:kopfH?{x:x0, y:y0, w:w, h:kopfH}:null, leiste:leisteH?{x:x0, y:y0+kopfH, w:w, h:leisteH}:null,
    punkte:punkteH?{x:x0, y:raster.y+raster.h, w:w, h:punkteH}:null, tabs:tabs,
    cw:(raster.w-2*M.pad-(r.cols-1)*M.gap)/r.cols, ch:(raster.h-2*M.pad-(r.rows-1)*M.gap)/r.rows};
}
function seZelle(geo, z, s, w, h){ const M=geo.M;
  return {x:geo.raster.x+M.pad+s*(geo.cw+M.gap), y:geo.raster.y+M.pad+z*(geo.ch+M.gap),
          w:w*geo.cw+(w-1)*M.gap, h:h*geo.ch+(h-1)*M.gap}; }
function seGeraeteListe(p){
  const l=[...geraeteMitGroesse(), dieserBrowser(), ...geraeteKatalog()], d=(p&&p.device)||{};
  if(d.name && d.vw && d.vh && !l.some(x=>x.quelle==='geraet' && x.name===d.name))
    l.unshift({quelle:'geraet', name:d.name, vw:d.vw, vh:d.vh});
  return l;
}
// Vorschaugeraet im Reiter: das gewaehlte, sonst das Zielgeraet des Profils
// (Reiter Titel), sonst das erste mit gemeldeter Groesse, sonst dieser Browser
function seGeraetReiter(p){
  const l=seGeraeteListe(p), w=SE_VORSCHAU[cur], find=(q,n)=>l.find(x=>x.quelle===q && x.name===n);
  return (w && find(w.quelle, w.name)) || ((p.device||{}).name && find('geraet', p.device.name))
    || l.find(x=>x.quelle==='geraet') || l.find(x=>x.quelle==='browser');
}
function seKontextReiter(){
  const p=PANELS[cur]; if(!p || p.__global) return null;
  const tab=()=>pickKey(curPickIdx);
  return {key:'r:'+cur+':'+curPickIdx, pkey:'r:'+cur, panel:p,
    seiten:()=>{ const t=p.pickTabs; return (Array.isArray(t)&&t.length) ? t : [{name:p.pickName||'', picks:p.picks||[]}]; },
    idx:()=>curPickIdx,
    setIdx:i=>{ curPickIdx=i; renderPick(p); seReiterZeichnen(); },
    neueSeite:()=>{ pickAddTab(p); seReiterZeichnen(); },
    // Hausuebersicht mit einem Tipp: in der eigenen Auswahl eine fertige
    // Seite, in der klassischen Leiste der Tab "haus" (eine freie Seite
    // zeigte die Visu dort nicht). Nur solange noch keine da ist und Platz ist.
    hausMoeglich:()=>tabMode(p)==='pick'
      ? ensurePickTabs(p).length<4 && !ensurePickTabs(p).some(x=>x.widget==='haus')
      : (p.tabs||[]).indexOf('haus')<0 && (p.tabs||[]).length<4,
    hausDazu:()=>{
      if(tabMode(p)==='pick') pickAddTab(p, {name:T('Haus'), widget:'haus'});
      else { p.tabs=(p.tabs||[]).concat(['haus']); markDirty(); renderChips(p); renderPanes(p); }
      seReiterZeichnen(); },
    seiteWeg:i=>{ pickDelTab(p, i); seReiterZeichnen(); },
    seiteLesen:()=>{ const t=p.pickTabs; if(Array.isArray(t)&&t[curPickIdx]) return t[curPickIdx];
      return curPickIdx===0 ? {name:p.pickName||'', picks:p.picks||[]} : null; },
    seite:()=>curPT(p), tab:tab,
    ui:()=>{ const u=Object.assign({}, ((PANELS.__global__||{}).ui)||{}, p.ui||{}), g=seGeraetReiter(p);
      // Zielkachel wie effective_grid_auto(): die des Geraets (Displays) vor der des Profils
      const dz=(g && g.quelle==='geraet' && DEV[g.name]) ? (parseInt(DEV[g.name].tileTarget)||0) : 0;
      return {auto:u.grid==='auto', cols:u.cols==3?3:2, rows:u.rows==3?3:2, split:u.split!==false,
        ziel:dz||tileSizeWert(u.tileSize)||kachelZiel().std, paneCols:parseInt(u.paneCols)||0,
        pane:(u.panes||{})[tab()]||'', werteLeiste:Array.isArray(u.valueBar) && u.valueBar.indexOf(tab())>-1,
        tileSet:u.tileSet||'', klassisch:u.tileLayout==='classic' && !u.tileSet, hinweis:gestenHinweisGilt(u)}; },
    hide:()=>p.hide||[], tiles:()=>p.tiles||{},
    setPane:k=>{ const v=k?paneWert(k):''; p.ui=p.ui||{}; p.ui.panes=p.ui.panes||{};
      if(v) p.ui.panes[tab()]=v; else delete p.ui.panes[tab()];
      if(!Object.keys(p.ui.panes).length) delete p.ui.panes;
      markDirty(); renderPanes(p); },
    setPaneRoh:v=>{ p.ui=p.ui||{}; p.ui.panes=p.ui.panes||{}; p.ui.panes[tab()]=v; markDirty(); renderPanes(p); },
    geraete:()=>seGeraeteListe(p), geraet:()=>seGeraetReiter(p),
    setGeraet:x=>{ SE_VORSCHAU[cur]={quelle:x.quelle, name:x.name}; },
    geaendert:()=>{ markDirty(); pickRefresh(); },
    gestalten:u=>{ tileSel=u; subPconf='aussehen'; renderSubtabs(); showSub('aussehen'); renderTileList(); renderTileEditor();
      const k=$('#tiles'); if(k) k.scrollIntoView({block:'nearest'}); }};
}
// ---- Aenderungen an der Seite (alle ueber seSchreiben) ----
// Neue Rasterfolge -> Seite: dahinter, was die Visu nicht im Raster zeigt
// (Werteleiste, ausgeblendet), in seiner bisherigen Folge.
function seNeueFolge(ctx, a, raster){ const drin=new Set(raster.map(e=>e.id));
  seSchreiben(ctx.seite(), raster.concat(a.folge.filter(e=>!drin.has(e.id)))); ctx.geaendert(); }
function seVerschieben(ctx, id, nach){
  const a=seAnsicht(ctx), r=a.raster.slice(), i=r.findIndex(e=>e.id===id); if(i<0) return;
  const [e]=r.splice(i,1); r.splice(Math.max(0, Math.min(nach, r.length)), 0, e); seNeueFolge(ctx, a, r); }
function seEinfuegen(ctx, id, nach){
  const a=seAnsicht(ctx);
  if(a.folge.some(e=>e.id===id)){ seVerschieben(ctx, id, nach); return true; }
  if(a.folge.length>=SE_MAX){ seZustand(ctx.pkey).meldung=T('Mehr als 60 Bausteine passen nicht auf eine Seite.'); return false; }
  const r=a.raster.slice(); r.splice(Math.max(0, Math.min(nach, r.length)), 0, {id:id, w:seStdBreite(ctx.tiles(), id), h:1});
  seNeueFolge(ctx, a, r); return true; }
function seEntfernen(ctx, id){ const a=seAnsicht(ctx); seSchreiben(ctx.seite(), a.folge.filter(e=>e.id!==id)); ctx.geaendert(); }
function seUmschalten(ctx, id){ const a=seAnsicht(ctx);
  if(a.folge.some(e=>e.id===id)) seEntfernen(ctx, id); else if(seEinfuegen(ctx, id, a.raster.length)) seZustand(ctx.key).folgen=id; }
function seGroesse(ctx, id, w, h){ const a=seAnsicht(ctx);
  seSchreiben(ctx.seite(), a.folge.map(e=>e.id===id ? {id:e.id, w:h===2?2:w, h:h} : e)); ctx.geaendert(); }
function seWidget(ctx, k){ const cur=sePaneArt(ctx.ui().pane), neu=sePaneArt(paneWert(k));
  ctx.setPane(cur===neu ? '' : k); }

// ---- Zeichnen ----
function sePct(v, b){ return (100*v/b).toFixed(3)+'%'; }
function seKasten(o, g){ return 'left:'+sePct(o.x,g.vw)+';top:'+sePct(o.y,g.vh)+';width:'+sePct(o.w,g.vw)+';height:'+sePct(o.h,g.vh)+';'; }
// Breite Kachel mit Tasten im neuen Aufbau: die Visu zeigt rechts Cover und
// Tasten (spielerKachel() in panel.html), der Editor ebenso
function seSpieler(c, gr, ui){
  return !!c && gr.w===2 && (c.tasten||0)>0 && !(ui||{}).klassisch;
}
function seIcon(c){ return (c && c.iconUrl) ? '<span class="tico" style="--u:url(\''+esc(c.iconUrl)+'\')"></span>' : '<span class="tico gen"></span>'; }
// Seitenleiste (nur im Panel-Editor): wechseln, hinzufuegen, entfernen
function seLeisteHtml(ctx){
  if(!ctx.setIdx) return '';
  const ss=ctx.seiten();
  return '<div class="se-seiten">'+ss.map((s,i)=>'<button type="button" class="ptb'+(i===ctx.idx()?' on':'')+'" data-se-seite="'+i+'">'+
    esc((s.name||'').trim()||(T('Seite')+' '+(i+1)))+
    (ss.length>1?'<span class="ptx" data-se-seite-weg="'+i+'" title="'+esc(T('Seite entfernen'))+'">✕</span>':'')+'</button>').join('')+
    (ss.length<4?'<button type="button" class="ptadd" data-se-neu title="'+esc(T('Seite hinzufügen'))+'">＋</button>':'')+
    // Hausuebersicht mit einem Tipp (ctx.hausMoeglich/hausDazu, nur im Panel-Editor)
    (ctx.hausMoeglich && ctx.hausMoeglich()?'<button type="button" class="ptadd" data-se-neu-haus title="'+
      esc(T('Hausübersicht als Seite hinzufügen'))+'">＋ '+T('Haus')+'</button>':'')+'</div>';
}
// Seiteninhalt: Bausteine (Kacheln) ODER ein Widget ueber die ganze Flaeche,
// mit seiner Wahl (Musikzone, Baustein, Werte/Verlauf gestapelt)
function seInhaltHtml(w){
  const k=wKind(w), arg=wArg(w);
  const opt=(v,n)=>'<option value="'+v+'"'+(k===v?' selected':'')+'>'+T(n)+'</option>';
  let h='<div class="field"><label class="lbl">'+T('Seiteninhalt')+'</label>'+
    '<select data-se-inhalt>'+
      '<option value=""'+(k===''?' selected':'')+'>'+T('Bausteine (Kacheln)')+'</option>'+opt('haus','Hausübersicht')+
      '<optgroup label="'+esc(T('Widget (Vollbild)'))+'">'+opt('weather','Wetter')+opt('calendar','Kalender')+
        (firstAudioZone()?opt('player','Audio'):'')+(firstEnergyControl()?opt('energy','Energiefluss'):'')+
        (firstCamera()?opt('camera','Kamera'):'')+(statControls().length?opt('chart','Verlauf'):'')+opt('status','Werte')+
      '</optgroup></select></div>';
  if(k==='player') h+='<div class="field"><label class="lbl">'+T('Musikzone')+'</label><select data-se-warg>'+audioZoneOptions(arg)+'</select></div>';
  else if(k==='energy') h+='<div class="field"><label class="lbl">'+T('Baustein')+'</label><select data-se-warg>'+energyControlOptions(arg)+'</select></div>';
  else if(k==='camera') h+='<div class="field"><label class="lbl">'+T('Baustein')+'</label><select data-se-warg>'+cameraOptions(arg)+'</select></div>';
  else if(k==='chart' || k==='status'){
    const uu=arg?arg.split(',').filter(Boolean):[];
    h+='<div class="field se-werte-wahl"><label class="lbl">'+T('Bausteine')+'</label>'+
      (k==='chart' ? '<select data-se-wneu="chart">'+chartAddOptions()+'</select>'
                   : '<select data-se-wneu="status"><option value="">'+T('＋ hinzufügen …')+'</option>'+controlOptions()+'</select>')+
      ((svMax()&&uu.length>=svMax())?'<span class="ccmut">'+T('Mehr passt nicht auf die Seite.')+'</span>':'')+
      '<div class="picked">'+(uu.length
        ? uu.map(u=>{ const c=(META.controls||[]).find(x=>x.uuid===u);
            return '<span class="chip on" data-se-wweg="'+esc(u)+'">'+esc(c?c.name:u)+
              '<span class="rm">'+esc((c&&c.roomName)||'')+'</span><span class="x">×</span></span>'; }).join('')
        : '<span class="none">'+T('Noch nichts gewählt – oben hinzufügen.')+'</span>')+'</div></div>';
  }
  return h;
}
// Bereich "Seite": Name, Seiteninhalt, Icon. seZeichnen() schreibt ihn nicht neu,
// damit das Namensfeld beim Tippen den Fokus behaelt und die Icon-Bibliothek
// ihre Suche; das Raster der Bibliothek fuellt sich erst beim Aufklappen.
function seEigenHtml(ctx){
  if(!ctx.panel) return '';
  const e=ctx.seiteLesen()||{};
  return '<div class="se-eigen">'+
    '<div class="field"><label class="lbl">'+T('Name der Seite')+'</label>'+
      '<input type="text" maxlength="40" data-se-name value="'+esc(e.name||'')+'" placeholder="'+esc(T('Auswahl'))+'"></div>'+
    seInhaltHtml(e.widget||'')+
    '<details class="se-icon" data-se-icon><summary>'+T('Icon der Seite')+' <span data-se-icon-jetzt>'+seIconJetzt(e.icon)+'</span></summary>'+
      '<input class="pgi-search" oninput="pickIcoFilter(this.value, this.parentNode)" placeholder="'+esc(T('Icon suchen…'))+'">'+
      '<div class="picogrid" data-se-icons></div></details></div>';
}
function seIconJetzt(ic){ return ic ? '<span class="loxi" style="--u:url(\''+esc(icoUrl(ic))+'\')"></span>' : '<span class="muted">'+T('kein')+'</span>'; }
function seEigenNeu(host){ const el=host.querySelector('[data-se-eigen]'); if(el) el.innerHTML=seEigenHtml(host._se); }
// Icon-Bibliothek beim Aufklappen fuellen; kommt die Loxone-Bibliothek nach,
// nur das Raster neu (die Suche bleibt stehen)
function seIconsFuellen(host){
  const d=host.querySelector('[data-se-icon]'), g=d && d.querySelector('[data-se-icons]'); if(!g || !d.open) return;
  g.innerHTML=icoGridBody((host._se.seiteLesen()||{}).icon||'');
  const q=d.querySelector('.pgi-search'); if(q && q.value) pickIcoFilter(q.value, d);
  if(LOXLIB===null) loadLoxlib(()=>{ if(document.body.contains(g)) seIconsFuellen(host); });
}
function seIconSetzen(host, v){
  const ctx=host._se, e=ctx.seite();
  if(v) e.icon=v; else delete e.icon;
  host.querySelectorAll('[data-se-icons] .pgi').forEach(b=>b.classList.toggle('on', b.dataset.pic===v));
  const j=host.querySelector('[data-se-icon-jetzt]'); if(j) j.innerHTML=seIconJetzt(v);
  ctx.geaendert();
}
// Inhalt der Seite setzen: Kacheln ('') oder ein Widget mit seiner Vorgabe
function seInhalt(ctx, k){
  const e=ctx.seite();
  if(!k) delete e.widget;
  else if(k==='weather'||k==='calendar'||k==='haus') e.widget=k;
  else if(k==='player') e.widget='player:'+(firstAudioZone()||'');
  else if(k==='energy') e.widget='energy:'+(firstEnergyControl()||'');
  else if(k==='camera') e.widget='camera:'+(firstCamera()||'');
  else if(k==='chart') e.widget='chart:'+(firstChartControl()||'');
  else if(k==='status') e.widget=(wKind(e.widget||'')==='status'?e.widget:'status:');
  ctx.geaendert();
}
// Werte- und Verlauf-Widget: Bausteine gestapelt, hoechstens svMax()
function seWidgetWerte(ctx, u, dazu){
  const e=ctx.seite(), art=wKind(e.widget||''), uu=wArg(e.widget||'').split(',').filter(Boolean);
  if(art!=='status' && art!=='chart') return;
  let neu;
  if(dazu){ if(!u || uu.indexOf(u)>-1 || (svMax() && uu.length>=svMax())) return; neu=uu.concat([u]); }
  else neu=uu.filter(x=>x!==u);
  e.widget=art+':'+neu.join(','); ctx.geaendert();
}
function seKopfHtml(ctx, a){
  let h='';
  const g=ctx.geraet();
  h+='<div class="se-wahl">';
  if(ctx.geraete){
    const l=ctx.geraete();
    h+='<div class="field"><label class="lbl">'+T('Vorschau für')+'</label><select data-se-geraet>'+l.map((x,i)=>
      '<option value="'+i+'"'+(x.quelle===g.quelle && x.name===g.name?' selected':'')+'>'+esc(x.name+' · '+x.vw+' × '+x.vh+
        (x.quelle==='geraet'?' · '+T('gemeldet'):''))+'</option>').join('')+'</select></div>';
  } else h+='<p class="hint">'+esc(T('Vorschau für')+' '+g.name+' · '+g.vw+' × '+g.vh)+'</p>';
  if(!a.pg.widget) h+='<label class="chk se-raum"><input type="checkbox" data-se-raum'+(a.nachRaum?' checked':'')+'> '+T('Nach Räumen gruppieren')+'</label>';
  return h+'</div>'+(a.pg.widget?'':'<p class="hint">'+(a.nachRaum
    ? T('Die Visu ordnet die Kacheln nach Räumen, ein Raum steht dort, wo sein erster Baustein steht; Verschieben ordnet innerhalb eines Raums oder rückt einen ganzen Raum nach vorn. Ohne Gruppierung gilt genau diese Anordnung, ohne Sprungmarken.')
    : T('Die Visu zeigt genau diese Anordnung, ohne Sprungmarken.'))+'</p>');
}
function seFlaecheHtml(ctx, st, a, r, lage){
  const g=ctx.geraet(), R=Math.max(1, r.rows), seiten=lage.seiten;
  st.blatt=Math.max(0, Math.min(st.blatt, seiten-1));
  const geo=seGeometrie(r, g, seiten), st0=st.blatt*R;
  let h='';
  for(let z=0; z<R; z++) for(let s=0; s<r.cols; s++)
    h+='<div class="se-zelle" style="'+seKasten(seZelle(geo, z, s, 1, 1), g)+'"></div>';
  a.raster.forEach((e,i)=>{
    const z=lage.zeile[i]; if(Math.floor(z/R)!==st.blatt) return;
    const gr=LoxRaster.groesse(e, r.cols, r.rows), c=seCtrl(e.id), an=st.sel===e.id;
    const mass=(gr.w>1||gr.h>1)?'<span class="se-mass">'+gr.w+' × '+gr.h+'</span>':'';
    const spieler=seSpieler(c, gr, ctx.ui());
    const play=spieler ? '<span class="se-play">'+(c.cover?'<img src="'+esc(c.cover)+'" alt="">':'')+
      '<span class="se-tasten">'+'<i></i>'.repeat(c.tasten)+'</span></span>' : '';
    h+='<button type="button" class="se-t'+(an?' sel':'')+(spieler?' se-spieler':'')+'" data-se-t="'+esc(e.id)+'" aria-pressed="'+an+'" style="'+
      seKasten(seZelle(geo, z-st0, lage.spalte[i], gr.w, gr.h), g)+'" title="'+esc(c.name+(c.roomName?' · '+c.roomName:''))+'">'+
      seIcon(c)+'<span class="se-tn">'+esc(c.name)+'</span>'+(c.roomName?'<span class="se-tr">'+esc(c.roomName)+'</span>':'')+mass+play+'</button>';
  });
  if(!a.raster.length) h+='<div class="se-leer" style="'+seKasten(geo.raster, g)+'">'+T('Bausteine aus der Liste hierher ziehen oder antippen')+'</div>';
  if(geo.kopf) h+='<div class="se-band" style="'+seKasten(geo.kopf, g)+'">'+T('Kopfzeile')+' · '+
    esc([T('Uhr, Wetter')].concat(seKopfWerte(ctx.ui().pane).map(u=>(seCtrl(u)||{}).name).filter(Boolean)).join(', '))+'</div>';
  if(geo.leiste) h+='<div class="se-band se-werte" style="'+seKasten(geo.leiste, g)+'">'+
    a.leiste.map(e=>'<span>'+esc(seCtrl(e.id).name)+'</span>').join('')+'</div>';
  if(geo.pane) h+='<div class="se-pane" style="'+seKasten(geo.pane, g)+'"><b>'+esc(T('Widget')+' · '+T(SE_PANE_NAMEN[r.art]||r.art))+'</b>'+
    '<button type="button" class="minibtn" data-se-pane-weg>'+T('Entfernen')+'</button></div>';
  if(geo.punkte) h+='<div class="se-punkte" style="'+seKasten(geo.punkte, g)+'">'+
    Array.from({length:seiten}, (_,k)=>'<i'+(k===st.blatt?' class="on"':'')+'></i>').join('')+'</div>';
  h+='<div class="se-tabs" style="'+seKasten(geo.tabs, g)+'"></div><div class="se-marke" hidden></div>';
  // hoechstens 440 px hoch (hochkant), nie breiter als die Spalte
  return '<div class="se-geraet" data-se-flaeche style="aspect-ratio:'+g.vw+' / '+g.vh+';width:min(100%, '+Math.round(440*g.vw/g.vh)+'px)">'+h+'</div>';
}
function seInfoText(ctx, st, r, lage){
  const g=ctx.geraet();
  const neben=r.widget ? ' '+(r.hoch?T('über dem Widget'):T('neben dem Widget')) : '';
  return (r.auto ? T('Raster am')+' '+g.name+': '+r.cols+' × '+r.rows+neben+' · '+T('Kacheln')+' '+Math.round(r.kb)+' px'
                 : T('Festes Raster am')+' '+g.name+': '+r.cols+' × '+r.rows+neben)+
    ' · '+T('Seite')+' '+(st.blatt+1)+' '+T('von')+' '+lage.seiten;
}
function seMitteHtml(ctx, st, a, r, lage){
  if(a.pg.widget==='haus') return '<p class="note">'+T('Diese Seite zeigt die Hausübersicht: Räume, was gerade an ist, Audio, Uhr, Wetter und Energie. Sie stellt sich aus der Anlage selbst zusammen, hier gibt es nichts anzuordnen.')+'</p>';
  if(a.pg.widget) return '<p class="note">'+T('Diese Seite zeigt ein Widget über die ganze Fläche statt Kacheln. Für Kacheln den Seiteninhalt auf „Bausteine (Kacheln)“ stellen.')+'</p>';
  const nav=lage.seiten>1 ? '<span class="se-blatt"><button type="button" class="minibtn" data-se-blatt="-1"'+(st.blatt?'':' disabled')+' aria-label="'+esc(T('Seite zurück'))+'">‹</button>'+
    '<button type="button" class="minibtn" data-se-blatt="1"'+(st.blatt<lage.seiten-1?'':' disabled')+' aria-label="'+esc(T('Seite vor'))+'">›</button></span>' : '';
  return '<div class="se-info"><span data-se-info>'+esc(seInfoText(ctx, st, r, lage))+'</span>'+nav+'</div>'+
    seFlaecheHtml(ctx, st, a, r, lage)+
    (r.auto?'':'<p class="hint">'+T('Feste Raster: die Kachelgröße hängt am Kasten der Visu und an der Skalierung, die Fläche zeigt Spalten, Zeilen und Lage.')+'</p>')+
    '<p class="hint">'+T('Ziehen mit Maus oder Finger, in der Liste am Griff. Ohne Ziehen: Kachel antippen, dann mit den Pfeiltasten verschieben, Entf nimmt sie von der Seite.')+'</p>'+
    (ctx.panel ? '<p class="hint">'+T('„Vorschau“ unten zeigt die Seite in der echten Visu, auch ungespeichert, und zieht Änderungen nach.')+'</p>' : '');
}
function seFeldHtml(ctx, st, a, r){
  const e=a.raster.find(x=>x.id===st.sel), m=seZustand(ctx.pkey).meldung;
  let h='<div class="grph">'+T('Ausgewählt')+'</div>'+(m?'<p class="hint se-meldung">'+esc(m)+'</p>':'');
  if(!e) return h+'<p class="hint">'+T('Kachel antippen, um Größe und Reihenfolge zu ändern.')+'</p>';
  const c=seCtrl(e.id), i=a.raster.indexOf(e), eff=LoxRaster.groesse(e, r.cols, r.rows);
  h+='<p class="se-name"><b>'+esc(c.name)+'</b><span>'+esc([c.roomName, c.type].filter(Boolean).join(' · '))+'</span></p>'+
    '<label class="lbl">'+T('Größe')+'</label><div class="seg se-groesse">'+[[1,1],[2,1],[2,2]].map(([w,hh])=>{
      const an=e.w===w && e.h===hh;
      return '<button type="button" data-se-gr="'+w+','+hh+'" aria-pressed="'+an+'"'+(an?' class="on"':'')+'>'+w+' × '+hh+'</button>'; }).join('')+'</div>'+
    ((eff.w!==e.w||eff.h!==e.h)?'<p class="hint">'+esc(T('Auf diesem Gerät zeigt die Visu sie')+' '+eff.w+' × '+eff.h+' – '+T('dafür fehlen Spalten oder Zeilen.'))+'</p>':'')+
    '<label class="lbl">'+T('Reihenfolge')+'</label><div class="se-knoepfe">'+
      '<button type="button" class="minibtn" data-se-mv="-1"'+(i>0?'':' disabled')+'>'+T('nach vorn')+'</button>'+
      '<button type="button" class="minibtn" data-se-mv="1"'+(i<a.raster.length-1?'':' disabled')+'>'+T('nach hinten')+'</button></div>'+
    '<div class="se-knoepfe"><button type="button" class="minibtn" data-se-weg>'+T('Von der Seite nehmen')+'</button>'+
      (ctx.gestalten?'<button type="button" class="minibtn" data-se-gest>'+T('Kachel gestalten')+'</button>':'')+'</div>';
  return h;
}
function sePalFilterHtml(ctx){
  const st=seZustand(ctx.pkey);
  return '<div class="grph">'+T('Bausteine')+'</div>'+
    '<div class="se-filter"><select data-se-raumf aria-label="'+esc(T('Raum'))+'"><option value="">'+T('Alle Räume')+'</option>'+
      (META.rooms||[]).map(r=>'<option value="'+esc(r.uuid)+'"'+(st.raum===r.uuid?' selected':'')+'>'+esc(r.name)+'</option>').join('')+'</select>'+
    '<input type="text" data-se-q value="'+esc(st.q)+'" placeholder="'+esc(T('Baustein suchen…'))+'"></div>';
}
function sePalListeHtml(ctx, a){
  const st=seZustand(ctx.pkey), auf=new Set(a.folge.map(e=>e.id)), hide=new Set(ctx.hide()), q=st.q.trim().toLowerCase();
  const alle=META.controls||[], l=alle.filter(c=>(!st.raum || c.room===st.raum) &&
    (!q || c.name.toLowerCase().includes(q) || (c.roomName||'').toLowerCase().includes(q)));
  return '<div class="se-liste">'+(l.length ? l.slice(0,400).map(c=>{ const an=auf.has(c.uuid);
    return '<button type="button" class="se-p'+(an?' auf':'')+'" data-se-p="'+esc(c.uuid)+'" aria-pressed="'+an+'">'+
      '<span class="se-grip">'+SE_GRIFF+'</span>'+seIcon(c)+'<span class="se-pn">'+esc(c.name)+'</span>'+
      '<span class="se-pr">'+esc(hide.has(c.uuid)?T('ausgeblendet'):(c.roomName||''))+'</span></button>'; }).join('')
    : '<div class="muted">'+T('nichts gefunden')+'</div>')+'</div>'+
    '<p class="hint">'+auf.size+' '+T('von')+' '+alle.length+' '+T('auf dieser Seite')+' · '+T('abgeblendet = schon platziert')+'</p>';
}
// Werte der Kopfzeile ("header:<uuid>,..."), wie in paneListe()
function seKopfWerte(pane){ return sePaneArt(pane)==='header' ? wArg(pane).split(',').filter(Boolean) : []; }
function seKopfWerteHtml(ctx){
  const uu=seKopfWerte(ctx.ui().pane);
  return '<div class="se-kopfwerte"><label class="lbl">'+T('Werte der Kopfzeile')+'</label>'+
    '<select data-se-kopf-neu><option value="">'+T('＋ hinzufügen …')+'</option>'+controlOptions()+'</select>'+
    ((svMax()&&uu.length>=svMax())?'<span class="ccmut">'+T('Mehr passt nicht in die Zeile.')+'</span>':'')+
    '<div class="picked">'+(uu.length
      ? uu.map(u=>{ const c=seCtrl(u);
          return '<span class="chip on" data-se-kopf-weg="'+esc(u)+'">'+esc(c?c.name:u)+
            '<span class="rm">'+esc((c&&c.roomName)||'')+'</span><span class="x">×</span></span>'; }).join('')
      : '<span class="none">'+T('Ohne Werte zeigt die Kopfzeile Uhr und Wetter.')+'</span>')+'</div></div>';
}
function seKopfWert(ctx, u, dazu){
  const uu=seKopfWerte(ctx.ui().pane);
  let neu;
  if(dazu){ if(!u || uu.indexOf(u)>-1 || (svMax() && uu.length>=svMax())) return; neu=uu.concat([u]); }
  else neu=uu.filter(x=>x!==u);
  ctx.setPaneRoh(neu.length ? 'header:'+neu.join(',') : 'header');
}
function seWidHtml(ctx){
  const u=ctx.ui(), cur=sePaneArt(u.pane);
  return '<div class="grph">'+T('Widgets')+'</div><div class="se-wl">'+SE_WIDGETS.filter(([k])=>!!paneWert(k)).map(([k,n])=>{
      const an=sePaneArt(paneWert(k))===cur, aus=!u.split && k!=='header';
      return '<button type="button" class="se-w'+(an?' on':'')+'" data-se-w="'+k+'" aria-pressed="'+an+'"'+(aus?' disabled':'')+'>'+
        '<span class="se-grip">'+SE_GRIFF+'</span>'+esc(T(n))+'</button>'; }).join('')+'</div>'+
    '<p class="hint">'+(u.split
      ? T('Ein Widget steht quer rechts neben den Kacheln, hochkant darunter; die Kopfzeile liegt über ihnen. Antippen oder auf die Fläche ziehen, noch einmal antippen nimmt es weg.')
      : T('Split ist aus: ein Widget daneben gibt es nicht, die Kopfzeile über den Kacheln schon.'))+'</p>'+
    ((cur==='header' && ctx.setPaneRoh) ? seKopfWerteHtml(ctx) : '');
}
// Ganzer Editor in host. Die Filterzeile der Palette steht fest (Fokus und
// Cursor im Suchfeld bleiben), alles andere zeichnet seZeichnen() neu.
function seRender(host, ctx){
  if(!host || !ctx) return;
  host._se=ctx; seBinden(host);
  host.innerHTML='<div data-se-leiste></div><div data-se-eigen></div><div data-se-kopf></div><div class="se-spalten">'+
    '<div class="se-pal"><div data-se-wid></div>'+sePalFilterHtml(ctx)+'<div data-se-liste></div></div>'+
    '<div class="se-mitte" data-se-mitte></div><div class="se-feld" data-se-feld></div></div>';
  seEigenNeu(host);
  seZeichnen(host);
}
function seZeichnen(host){
  const ctx=host._se, st=seZustand(ctx.key), a=seAnsicht(ctx);
  if(st.sel && !a.raster.some(e=>e.id===st.sel)) st.sel=null;
  const teil=k=>host.querySelector('[data-se-'+k+']');
  teil('leiste').innerHTML=seLeisteHtml(ctx);
  teil('kopf').innerHTML=seKopfHtml(ctx, a);
  host.querySelector('.se-pal').hidden=!!a.pg.widget;
  teil('liste').innerHTML=a.pg.widget?'':sePalListeHtml(ctx, a);
  teil('wid').innerHTML=a.pg.widget?'':seWidHtml(ctx);
  if(a.pg.widget){ teil('mitte').innerHTML=seMitteHtml(ctx, st, a, null, null); teil('feld').innerHTML=''; host._seLage=null; return; }
  const r=seRaster(ctx, a), lage=LoxRaster.rasterLage(a.raster, r.cols, r.rows);
  if(st.folgen){ const i=a.raster.findIndex(e=>e.id===st.folgen); if(i>-1) st.blatt=Math.floor(lage.zeile[i]/Math.max(1,r.rows)); st.folgen=null; }
  teil('mitte').innerHTML=seMitteHtml(ctx, st, a, r, lage);
  teil('feld').innerHTML=seFeldHtml(ctx, st, a, r);
  host._seLage={a:a, r:r, lage:lage, geo:seGeometrie(r, ctx.geraet(), lage.seiten)};
  if(window.I18N && I18N.applyChrome) I18N.applyChrome(host);
}
function seFokus(host, id){ const t=host.querySelector('[data-se-t="'+CSS.escape(id)+'"]'); if(t) t.focus(); }
// Reiter „Seiten-Editor": steht keine freie Seite in der Leiste, zeigt das
// Panel sie nicht - der Hinweis fuehrt zu Tabs, bearbeiten laesst sie sich trotzdem
function seReiterZeichnen(){
  const h=$('#seHost'), p=PANELS[cur]; if(!h || !p || p.__global) return;
  const hw=$('#seHinweis');
  if(hw){ hw.innerHTML=(p.tabs||[]).some(isPick) ? '' : '<p class="hint">'+
      T('Freie Seiten zeigt die Visu erst, wenn sie in der Leiste stehen: unter Inhalt „Eigene Auswahl“ wählen oder die Auswahl als Button in die klassische Leiste nehmen.')+
      ' <button type="button" class="minibtn" id="seZuTabs">'+T('Zu Inhalt')+'</button></p>';
    const zt=$('#seZuTabs'); if(zt) zt.onclick=()=>{ subPconf='inhalt'; renderSubtabs(); showSub('inhalt'); }; }
  seRender(h, seKontextReiter());
  sePaneZeichnen(p);
}

// ---- Bedienung: Tippen, Aendern, Tasten ----
function seBinden(host){
  if(host._seGebunden) return; host._seGebunden=true;
  host.addEventListener('click', ev=>seKlick(host, ev));
  host.addEventListener('change', ev=>seAenderung(host, ev));
  host.addEventListener('input', ev=>{
    if(ev.target.matches('[data-se-q]')){ seZustand(host._se.pkey).q=ev.target.value; seZeichnen(host); }
    else if(ev.target.matches('[data-se-name]')){ host._se.seite().name=ev.target.value; host._se.geaendert(); seZeichnen(host); } });
  // toggle steigt nicht auf: in der Capture-Phase abfangen (Icon-Bibliothek aufgeklappt)
  host.addEventListener('toggle', ev=>{ if(ev.target.matches && ev.target.matches('[data-se-icon]')) seIconsFuellen(host); }, true);
  host.addEventListener('keydown', ev=>seTaste(host, ev));
  host.addEventListener('pointerdown', ev=>seDown(host, ev));
}
function seKlick(host, ev){
  if(host._seSperre){ host._seSperre=false; ev.preventDefault(); return; }   // Klick nach dem Ziehen
  const ctx=host._se;
  // Marken in Knoepfen und Chips zuerst: Seite entfernen, Baustein aus dem Werte-/Verlauf-Widget
  const weg=ev.target.closest('[data-se-seite-weg]');
  if(weg && ctx.seiteWeg){ ev.stopPropagation(); ctx.seiteWeg(Number(weg.dataset.seSeiteWeg)); return; }
  const kw=ev.target.closest('[data-se-kopf-weg]');
  if(kw){ seKopfWert(ctx, kw.dataset.seKopfWeg, false); seZeichnen(host); return; }
  const ww=ev.target.closest('[data-se-wweg]');
  if(ww){ seWidgetWerte(ctx, ww.dataset.seWweg, false); seEigenNeu(host); seZeichnen(host); return; }
  const b=ev.target.closest('button'); if(!b || !host.contains(b) || b.disabled) return;
  const st=seZustand(ctx.key), d=b.dataset;
  if(d.pic!==undefined && b.closest('[data-se-icons]')){ seIconSetzen(host, d.pic); return; }
  seZustand(ctx.pkey).meldung='';
  if(d.seT!==undefined) st.sel=d.seT;
  else if(d.seP!==undefined) seUmschalten(ctx, d.seP);
  else if(d.seW!==undefined) seWidget(ctx, d.seW);
  else if(d.seGr){ const [w,h]=d.seGr.split(',').map(Number); seGroesse(ctx, st.sel, w, h); st.folgen=st.sel; }
  else if(d.seMv){ const a=seAnsicht(ctx), i=a.raster.findIndex(e=>e.id===st.sel); seVerschieben(ctx, st.sel, i+Number(d.seMv)); st.folgen=st.sel; }
  else if(d.seWeg!==undefined){ seEntfernen(ctx, st.sel); st.sel=null; }
  else if(d.seGest!==undefined){ ctx.gestalten(st.sel); return; }
  else if(d.seBlatt) st.blatt+=Number(d.seBlatt);
  else if(d.sePaneWeg!==undefined) ctx.setPane('');
  else if(d.seSeite!==undefined){ ctx.setIdx(Number(d.seSeite)); return; }
  else if(d.seNeu!==undefined){ ctx.neueSeite(); return; }
  else if(d.seNeuHaus!==undefined){ ctx.hausDazu(); return; }
  else return;
  const fokus=(d.seT!==undefined) ? d.seT : null;
  seZeichnen(host); if(fokus) seFokus(host, fokus);
}
function seAenderung(host, ev){
  const t=ev.target, ctx=host._se;
  if(t.matches('[data-se-geraet]')){ const x=ctx.geraete()[Number(t.value)]; if(x) ctx.setGeraet(x); }
  else if(t.matches('[data-se-raum]')){ const pg=ctx.seite(); if(t.checked) delete pg.byRoom; else pg.byRoom=false; ctx.geaendert(); }
  else if(t.matches('[data-se-raumf]')) seZustand(ctx.pkey).raum=t.value;
  else if(t.matches('[data-se-inhalt]')){ seInhalt(ctx, t.value); seEigenNeu(host); if(host.id==='seHost') sePaneZeichnen(PANELS[cur]); }
  else if(t.matches('[data-se-warg]')){ const e=ctx.seite(); e.widget=wKind(e.widget||'')+':'+t.value; ctx.geaendert(); }
  else if(t.matches('[data-se-wneu]')){ seWidgetWerte(ctx, t.value, true); seEigenNeu(host); }
  else if(t.matches('[data-se-kopf-neu]')) seKopfWert(ctx, t.value, true);
  else return;
  seZeichnen(host);
}
// Pfeiltasten verschieben die gewaehlte Kachel (links/rechts um eine Stelle,
// hoch/runter um eine Zeile), Entf nimmt sie von der Seite. Nur auf den
// Kacheln der Flaeche, kein globaler Tasten-Handler.
function seTaste(host, ev){
  const t=ev.target.closest && ev.target.closest('[data-se-t]'); if(!t || !host._seLage) return;
  const ctx=host._se, st=seZustand(ctx.key), id=t.dataset.seT, {a, r}=host._seLage, i=a.raster.findIndex(e=>e.id===id);
  if(i<0) return;
  const schritt={ArrowLeft:-1, ArrowRight:1, ArrowUp:-r.cols, ArrowDown:r.cols}[ev.key];
  if(ev.key==='Delete' || ev.key==='Backspace'){ ev.preventDefault(); seEntfernen(ctx, id); st.sel=null; seZeichnen(host);
    const n=host.querySelector('[data-se-t]'); if(n) n.focus(); return; }
  if(!schritt) return;
  ev.preventDefault();
  const n=Math.max(0, Math.min(a.raster.length-1, i+schritt));
  st.sel=id;
  if(n!==i){ seVerschieben(ctx, id, n); st.folgen=id; }
  seZeichnen(host); seFokus(host, id);
}

// ---- Ziehen (Pointer-Events: Maus, Stift, Finger) ----
// Kacheln der Flaeche lassen sich direkt ziehen (touch-action: none), in der
// Palette nimmt der Finger den Griff, damit die Liste scrollbar bleibt. Ziel
// ist die Stelle in der Rasterfolge unter dem Zeiger; die Marke zeigt genau
// die Zellen, die die Kachel dort belegen wuerde (rasterLage mit der neuen
// Folge). Zurueck in die Palette gezogen nimmt sie von der Seite, ein Widget
// auf die Flaeche gezogen setzt es neben die Kacheln.
function seDown(host, ev){
  if(ev.button>0 || SE_ZIEHEN) return;
  const q=ev.target.closest('[data-se-t],[data-se-p],[data-se-w]'); if(!q || q.disabled || !host._seLage) return;
  const art=q.hasAttribute('data-se-t')?'flaeche':(q.hasAttribute('data-se-p')?'palette':'widget');
  if(art!=='flaeche' && ev.pointerType==='touch' && !ev.target.closest('.se-grip')) return;
  SE_ZIEHEN={host:host, art:art, id:q.dataset.seT||q.dataset.seP||q.dataset.seW, x0:ev.clientX, y0:ev.clientY,
    aktiv:false, ziel:null, geist:null, name:(q.querySelector('.se-tn,.se-pn')||q).textContent, blattUhr:null};
  document.addEventListener('pointermove', seMove);
  document.addEventListener('pointerup', seUp);
  document.addEventListener('pointercancel', seAbbruch);
}
function seMove(ev){
  const z=SE_ZIEHEN; if(!z) return;
  if(!z.aktiv){
    if(Math.hypot(ev.clientX-z.x0, ev.clientY-z.y0)<6) return;
    z.aktiv=true; z.host.classList.add('se-zieht');
    z.geist=document.createElement('div'); z.geist.className='se-geist'; z.geist.textContent=z.name;
    document.body.appendChild(z.geist);
  }
  ev.preventDefault();
  z.geist.style.left=(ev.clientX+10)+'px'; z.geist.style.top=(ev.clientY+10)+'px';
  z.ziel=seZiel(z, ev.clientX, ev.clientY);
  seMarke(z);
}
// Wohin fiele die Kachel? {art:'stelle', i} (Index in der Rasterfolge ohne die
// gezogene), {art:'palette'}, {art:'widget'} oder null
function seZiel(z, x, y){
  const host=z.host, unter=document.elementFromPoint(x, y), fl=host.querySelector('[data-se-flaeche]');
  clearTimeout(z.blattUhr); z.blattUhr=null;
  if(!unter || !host.contains(unter)) return null;
  const blatt=unter.closest('[data-se-blatt]');
  if(blatt && !blatt.disabled && z.art!=='widget'){   // ueber dem Blaetterknopf kurz verweilen: Seite wechseln
    z.blattUhr=setTimeout(()=>{ if(SE_ZIEHEN!==z) return; seZustand(host._se.key).blatt+=Number(blatt.dataset.seBlatt);
      seZeichnen(host); }, 450);
    return null; }
  if(unter.closest('.se-pal')) return z.art==='flaeche' ? {art:'palette'} : null;
  if(!fl || !fl.contains(unter)) return null;
  if(z.art==='widget') return {art:'widget'};
  const {a, r, lage, geo}=host._seLage, g=host._se.geraet(), rect=fl.getBoundingClientRect();
  const dx=(x-rect.left)/rect.width*g.vw, dy=(y-rect.top)/rect.height*g.vh, M=geo.M, R=Math.max(1, r.rows);
  const s=Math.max(0, Math.min(r.cols-1, Math.floor((dx-geo.raster.x-M.pad+M.gap/2)/(geo.cw+M.gap))));
  const zr=Math.max(0, Math.min(R-1, Math.floor((dy-geo.raster.y-M.pad+M.gap/2)/(geo.ch+M.gap))));
  const zeile=seZustand(host._se.key).blatt*R+zr;
  let i=a.raster.findIndex((e,k)=>{ const gr=LoxRaster.groesse(e, r.cols, r.rows);
    return zeile>=lage.zeile[k] && zeile<lage.zeile[k]+gr.h && s>=lage.spalte[k] && s<lage.spalte[k]+gr.w; });
  if(i>-1){ const gr=LoxRaster.groesse(a.raster[i], r.cols, r.rows), mitte=geo.raster.x+M.pad+(lage.spalte[i]+gr.w/2)*(geo.cw+M.gap);
    if(dx>mitte) i++; }
  else i=a.raster.filter((e,k)=>lage.zeile[k]<zeile || (lage.zeile[k]===zeile && lage.spalte[k]<s)).length;
  const alt=a.raster.findIndex(e=>e.id===z.id);
  if(alt>-1 && alt<i) i--;
  return {art:'stelle', i:i};
}
// Marke: wo die Kachel mit der neuen Folge stuende (nur auf dem sichtbaren Blatt)
function seMarke(z){
  const host=z.host, m=host.querySelector('.se-marke'), fl=host.querySelector('[data-se-flaeche]');
  host.querySelectorAll('.se-pal.drop').forEach(n=>n.classList.remove('drop'));
  if(fl) fl.classList.toggle('drop', !!z.ziel && z.ziel.art==='widget');
  if(z.ziel && z.ziel.art==='palette') host.querySelector('.se-pal').classList.add('drop');
  if(!m) return;
  if(!z.ziel || z.ziel.art!=='stelle'){ m.hidden=true; return; }
  const {a, r, geo}=host._seLage, g=host._se.geraet(), R=Math.max(1, r.rows), st=seZustand(host._se.key);
  const neu=a.raster.filter(e=>e.id!==z.id), e=a.raster.find(x=>x.id===z.id) || {id:z.id, w:seStdBreite(host._se.tiles(), z.id), h:1};
  neu.splice(z.ziel.i, 0, e);
  const l=LoxRaster.rasterLage(neu, r.cols, r.rows), k=z.ziel.i, gr=LoxRaster.groesse(e, r.cols, r.rows);
  if(Math.floor(l.zeile[k]/R)!==st.blatt){ m.hidden=true; return; }
  m.setAttribute('style', seKasten(seZelle(geo, l.zeile[k]-st.blatt*R, l.spalte[k], gr.w, gr.h), g)); m.hidden=false;
}
function seEnde(){
  const z=SE_ZIEHEN; SE_ZIEHEN=null;
  document.removeEventListener('pointermove', seMove);
  document.removeEventListener('pointerup', seUp);
  document.removeEventListener('pointercancel', seAbbruch);
  if(!z) return null;
  clearTimeout(z.blattUhr);
  if(z.geist) z.geist.remove();
  z.host.classList.remove('se-zieht');
  return z;
}
function seAbbruch(){ const z=seEnde(); if(z && z.aktiv) seZeichnen(z.host); }
function seUp(){
  const z=seEnde(); if(!z || !z.aktiv) return;
  z.host._seSperre=true; setTimeout(()=>{ z.host._seSperre=false; }, 0);
  const ctx=z.host._se, st=seZustand(ctx.key), zi=z.ziel;
  seZustand(ctx.pkey).meldung='';
  if(zi && zi.art==='stelle'){
    if(z.art==='flaeche') seVerschieben(ctx, z.id, zi.i); else seEinfuegen(ctx, z.id, zi.i);
    st.sel=z.id; st.folgen=z.id;
  }
  else if(zi && zi.art==='palette'){ seEntfernen(ctx, z.id); if(st.sel===z.id) st.sel=null; }
  else if(zi && zi.art==='widget'){ if(sePaneArt(ctx.ui().pane)!==sePaneArt(paneWert(z.id))) ctx.setPane(z.id); }
  seZeichnen(z.host);
}

function tileOv(){ const p=PANELS[cur]; p.tiles=p.tiles||{}; p.tiles[tileSel]=p.tiles[tileSel]||{}; return p.tiles[tileSel]; }
function pruneTile(){ const p=PANELS[cur]; if(p.tiles&&p.tiles[tileSel]&&!Object.keys(p.tiles[tileSel]).length) delete p.tiles[tileSel]; }
function setTile(k,v){ const ov=tileOv(); if(v==null||v==='') delete ov[k]; else ov[k]=v; pruneTile(); markDirty(); drawPrev(); renderTileList(); }
function setTileIcon(ic){ const ov=tileOv(); if(ic) ov.icon=ic; else delete ov.icon; pruneTile(); markDirty(); drawPrev(); renderTileList(); }
// Mini-Diagramm der Kachel: Stil und (nur beim Trend) Zeitraum. Tagesmuster
// und Tagesspanne zeigen immer die letzten 7 Tage, die Spanne gibt es nur bei
// Messwerten (bei Zaehlern und Ein/Aus hat ein Tag kein Tief und Hoch).
// Der Trend zeichnet je Art etwas anderes, der Hinweis sagt es genauso.
const CHART_TREND_HINT={line:'Kurve mit Tief, Hoch und Änderung',
                        counter:'Verbrauch als Balken, dazu die Summe',
                        digital:'Ein/Aus als Stufen, dazu die Einschaltdauer'};
function chartStyles(c){
  const st=[['','Aus',''],['trend','Trend',CHART_TREND_HINT[c.statKind]||CHART_TREND_HINT.line],
            ['pattern','Tagesmuster','7 Tage × 24 Stunden als Farbraster']];
  if(c.statKind==='line') st.push(['span','Tagesspanne','Tief bis Hoch je Tag, 7 Tage']);
  return st;
}
function curChartStyle(ov){ return ov.chart ? (ov.chartStyle||'trend') : ''; }
function chartStyleRows(c,ov){
  const cur=curChartStyle(ov), st=chartStyles(c), hint=(st.find(o=>o[0]===cur)||st[0])[2];
  let h='<div class="frow"><label class="lbl">Verlauf</label><select id="tChartStyle">'+
    st.map(o=>'<option value="'+esc(o[0])+'"'+(cur===o[0]?' selected':'')+'>'+esc(o[1])+'</option>').join('')+
    '</select>'+(hint?'<span class="hint">'+esc(hint)+'</span>':'')+'</div>';
  if(cur==='trend') h+='<div class="frow"><label class="lbl">Zeitraum</label><select id="tChartRange">'+
    (META.statRanges||[]).map(o=>'<option value="'+esc(o[0])+'"'+(ov.chart===o[0]?' selected':'')+'>'+esc(o[1])+'</option>').join('')+
    '</select></div>';
  return h;
}
function setChartStyle(v){
  // Der Zeitraum bleibt beim Stilwechsel erhalten; Muster und Spanne rechnet
  // der Server unabhaengig davon ueber 7 Tage.
  const ov=tileOv(), first=((META.statRanges||[])[0]||[])[0];
  if(!v){ delete ov.chart; delete ov.chartStyle; }
  else { if(!ov.chart) ov.chart=first; if(v==='trend') delete ov.chartStyle; else ov.chartStyle=v; }
  pruneTile(); markDirty(); renderTileEditor(); renderTileList();
}
function renderTileEditor(){
  const host=$('#tileEditor'); if(!host) return;
  if(!tileSel){ host.innerHTML=''; return; }
  const c=(META.controls||[]).find(x=>x.uuid===tileSel);
  if(!c){ host.innerHTML=''; return; }
  const ov=((PANELS[cur].tiles||{})[tileSel])||{};
  host.innerHTML=
   '<div class="tedit"><div class="tprev" id="tprev"></div>'+
    '<div class="tctrl">'+
      colorRow('Hintergrund','bg',ov)+colorRow('Rahmen','border',ov)+
      colorRow('Icon-Farbe','iconColor',ov)+colorRow('Textfarbe','textColor',ov)+
      '<div class="frow"><label class="lbl">Schrift</label>'+
        '<select id="tfontSel">'+FONTS.map(f=>'<option value="'+esc(f.v)+'"'+(sameFont(ov.font,f.v)?' selected':'')+'>'+esc(f.label)+'</option>').join('')+
          '<option value="__custom"'+(customFont(ov.font)?' selected':'')+'>Eigene…</option></select>'+
        '<span class="tgl'+(ov.bold?' on':'')+'" id="tBold" title="Fett">B</span>'+
        '<span class="tgl it'+(ov.italic?' on':'')+'" id="tItalic" title="Kursiv">I</span></div>'+
      '<div class="frow" id="tfontCustomRow"'+(customFont(ov.font)?'':' style="display:none"')+'>'+
        '<label class="lbl"></label><input type="text" id="tfontCustom" value="'+esc(customFont(ov.font)?ov.font:'')+'" placeholder="z. B. Pacifico, cursive" style="flex:1"></div>'+
      '<div class="frow"><label class="lbl">Icon</label><div class="itabs">'+
        '<span class="itab on" data-src="builtin">Eingebaut</span>'+
        '<span class="itab" data-src="loxone">Loxone ('+(((META.icons||{}).loxone)||[]).length+')</span>'+
        (((META.icons||{}).loxlib)?'<span class="itab" data-src="loxlib">'+T('Bibliothek')+' ('+META.icons.loxlib+')</span>':'')+
        '<span class="itab dis" title="folgt in Stufe 2/3">Google · Upload</span></div></div>'+
      '<div class="ipick" id="ipick"></div>'+
      '<div class="frow" style="margin-top:8px"><label class="lbl">Aktiv-Overlay</label>'+
        '<span class="tgl'+(ov.overlay?' on':'')+'" id="tOvOn" title="Für diese Kachel abweichend">◐</span>'+
        '<span style="color:var(--muted);font-size:12.5px">abweichend von der Ansicht</span></div>'+
      '<div class="ovwrap" id="tOvBox"'+(ov.overlay?'':' style="display:none"')+'>'+
        '<div class="ovprev"><div class="ovtile on" id="tovPrev">An</div>'+
          '<div class="ovtile off" id="tovPrevOff">Aus</div></div>'+
        '<div class="ovctrl">'+overlayFields(ov.overlay,'tov_')+'</div></div>'+
      (c.stat?chartStyleRows(c,ov):'')+
      breiteRow(c,ov)+
      '<div class="frow" style="margin-top:4px"><button class="minibtn" id="tileReset">Kachel zurücksetzen</button></div>'+
    '</div></div>';
  bindColor('bg'); bindColor('border'); bindColor('iconColor'); bindColor('textColor');
  const fsel=$('#tfontSel'), fcustRow=$('#tfontCustomRow'), fcust=$('#tfontCustom');
  fsel.onchange=()=>{ if(fsel.value==='__custom'){ fcustRow.style.display=''; setTile('font', fcust.value.trim()); }
                      else { fcustRow.style.display='none'; setTile('font', fsel.value); } };
  fcust.oninput=()=>setTile('font', fcust.value.trim());
  $('#tBold').onclick=()=>{ const ov=tileOv(); if(ov.bold)delete ov.bold; else ov.bold=true; pruneTile(); $('#tBold').classList.toggle('on'); markDirty(); drawPrev(); renderTileList(); };
  $('#tItalic').onclick=()=>{ const ov=tileOv(); if(ov.italic)delete ov.italic; else ov.italic=true; pruneTile(); $('#tItalic').classList.toggle('on'); markDirty(); drawPrev(); renderTileList(); };
  host.querySelectorAll('.itab[data-src]').forEach(t=>t.onclick=()=>{
    host.querySelectorAll('.itab').forEach(x=>x.classList.remove('on')); t.classList.add('on'); renderIconPick(t.dataset.src); });
  bindOverlay('tov_', ()=>{ const o=tileOv(); o.overlay=o.overlay||{}; return o.overlay; },
              ()=>{ ovPreview('tovPrev', tileOv().overlay); pruneTile(); markDirty(); renderTileList(); });
  ovPreview('tovPrev', ov.overlay);
  { const tg=$('#tOvOn'); if(tg) tg.onclick=()=>{ const o=tileOv();
      if(o.overlay) delete o.overlay; else o.overlay={}; pruneTile(); renderTileEditor(); renderTileList(); markDirty(); }; }
  { const ts=$('#tChartStyle'); if(ts) ts.onchange=()=>setChartStyle(ts.value); }
  { const tw=$('#tWidth'); if(tw) tw.onchange=()=>setTile('w', tw.value?parseInt(tw.value):null); }
  { const tr=$('#tChartRange'); if(tr) tr.onchange=()=>setTile('chart', tr.value); }
  $('#tileReset').onclick=()=>{ if(PANELS[cur].tiles) delete PANELS[cur].tiles[tileSel]; renderTileEditor(); renderTileList(); markDirty(); };
  renderIconPick('builtin'); drawPrev();
}
// Breite der Kachel in Spalten: zwei fuer Audio, Raumregelung und Energiefluss
// (Standard nach Typ, Liste vom Server: META.kachelBreit), je Kachel uebersteuerbar
function breiteRow(c,ov){
  const breit=(META.kachelBreit||[]).indexOf(c.type)>=0, cur=ov.w?String(ov.w):'';
  const opts=[['',T('Standard')+' ('+(breit?T('breit'):T('schmal'))+')'],['1',T('1 Spalte')],['2',T('2 Spalten (breit)')]];
  return '<div class="frow" style="margin-top:4px"><label class="lbl">'+T('Breite')+'</label>'+
    '<select id="tWidth">'+opts.map(o=>'<option value="'+o[0]+'"'+(cur===o[0]?' selected':'')+'>'+esc(o[1])+'</option>').join('')+'</select></div>';
}
function colorRow(label,key,ov){
  const v=ov[key]||'';
  return '<div class="crow"><label class="lbl">'+label+'</label>'+
    '<input type="color" data-ck="'+key+'" value="'+(v&&v[0]==='#'?esc(v):'#888888')+'">'+
    '<span class="cval" data-cv="'+key+'">'+esc(v||'Standard')+'</span>'+
    '<button class="minibtn" data-cc="'+key+'">Standard</button></div>';
}
function bindColor(key){
  const inp=document.querySelector('[data-ck="'+key+'"]'), clr=document.querySelector('[data-cc="'+key+'"]'),
        cv=document.querySelector('[data-cv="'+key+'"]');
  if(inp) inp.oninput=()=>{ setTile(key,inp.value); if(cv)cv.textContent=inp.value; };
  if(clr) clr.onclick=()=>{ setTile(key,null); if(cv)cv.textContent='Standard'; };
}
function drawPrev(){
  const el=$('#tprev'); if(!el) return;
  const c=(META.controls||[]).find(x=>x.uuid===tileSel)||{};
  const ov=((PANELS[cur].tiles||{})[tileSel])||{};
  const sv=[]; if(ov.bg)sv.push('background:'+ov.bg); if(ov.border)sv.push('border-color:'+ov.border);
  el.setAttribute('style', sv.join(';'));
  const nsv=[]; if(ov.textColor)nsv.push('color:'+ov.textColor); if(ov.font)nsv.push('font-family:'+ov.font);
  if(ov.bold)nsv.push('font-weight:700'); if(ov.italic)nsv.push('font-style:italic');
  const nst=nsv.length?' style="'+esc(nsv.join(';'))+'"':'';
  const col=ov.iconColor||'var(--accent)', ic=ov.icon; let ih;
  if(ic&&ic.src==='builtin') ih='<span class="pico" style="color:'+col+'">'+svg(BICONS[ic.id]||BICONS.info)+'</span>';
  else if(ic&&ic.src==='loxone') ih='<span class="pico img" style="--u:url(\'/icon?p='+encodeURIComponent(ic.p)+'\');background:'+col+'"></span>';
  else if(ic&&ic.src==='loxlib') ih='<span class="pico img" style="--u:url(\'/loxlib?n='+encodeURIComponent(ic.name)+'\');background:'+col+'"></span>';
  else if(c.iconUrl) ih='<span class="pico img" style="--u:url(\''+esc(c.iconUrl)+'\');background:'+col+'"></span>';
  else ih='<span class="pico" style="color:'+col+'">'+svg(BICONS.info)+'</span>';
  el.innerHTML=ih+'<div class="pnm"'+nst+'>'+esc(c.name||'')+'</div>';
}
function renderIconPick(src){
  const box=$('#ipick'); if(!box) return; box.innerHTML='';
  const ov=((PANELS[cur].tiles||{})[tileSel])||{}, cic=ov.icon||{};
  const clr=document.createElement('span'); clr.className='iopt clear'+(!ov.icon?' sel':''); clr.title='Standard-Icon'; clr.textContent='✕';
  clr.onclick=()=>{ setTileIcon(null); renderIconPick(src); }; box.appendChild(clr);
  if(src==='builtin'){
    Object.keys(BICONS).forEach(id=>{
      const b=document.createElement('span'); b.className='iopt'+(cic.src==='builtin'&&cic.id===id?' sel':''); b.title=id;
      b.innerHTML=svg(BICONS[id]);
      b.onclick=()=>{ setTileIcon({src:'builtin',id}); renderIconPick(src); }; box.appendChild(b);
    });
  } else if(src==='loxone'){
    ((((META.icons||{}).loxone))||[]).forEach(p=>{
      const b=document.createElement('span'); b.className='iopt'+(cic.src==='loxone'&&cic.p===p?' sel':''); b.title=p;
      b.innerHTML='<span class="loxi" style="--u:url(\'/icon?p='+encodeURIComponent(p)+'\')"></span>';
      b.onclick=()=>{ setTileIcon({src:'loxone',p}); renderIconPick(src); }; box.appendChild(b);
    });
  } else if(src==='loxlib'){
    // Loxone-Bibliothek (LoxoneIcons-Plugin, ~550 SVGs): lazy laden + Suchfeld,
    // damit nicht hunderte Icons auf einmal geladen werden.
    const f=document.createElement('input'); f.type='search';
    f.placeholder=T('Suchen… z. B. light, blind, alarm'); f.value=loxlibFilter;
    f.style.cssText='grid-column:1/-1;padding:6px 8px;border:1px solid var(--line);border-radius:4px;background:transparent;color:var(--fg);font-size:13px';
    f.oninput=()=>{ loxlibFilter=f.value; paintLoxlib(box); };
    box.appendChild(f);
    loadLoxlib(()=>{ if(document.body.contains(box)) paintLoxlib(box); });
  }
}
let LOXLIB=null, loxlibFilter='';
function loadLoxlib(cb){
  if(LOXLIB!==null){ cb(); return; }
  fetch('/api/loxicons').then(r=>r.json()).then(j=>{ LOXLIB=(j&&j.icons)||[]; cb(); }).catch(()=>{ LOXLIB=[]; cb(); });
}
function paintLoxlib(box){
  box.querySelectorAll('.iopt:not(.clear),.lxnote').forEach(n=>n.remove());
  const cic=((PANELS[cur].tiles||{})[tileSel]||{}).icon||{};
  const q=(loxlibFilter||'').trim().toLowerCase();
  const all=LOXLIB||[];
  const list=q?all.filter(n=>n.toLowerCase().indexOf(q)>=0):all;
  list.slice(0,300).forEach(n=>{
    const b=document.createElement('span'); b.className='iopt'+(cic.src==='loxlib'&&cic.name===n?' sel':''); b.title=n;
    b.innerHTML='<span class="loxi" style="--u:url(\'/loxlib?n='+encodeURIComponent(n)+'\')"></span>';
    b.onclick=()=>{ setTileIcon({src:'loxlib',name:n}); paintLoxlib(box); }; box.appendChild(b);
  });
  const note=t=>{ const m=document.createElement('div'); m.className='lxnote';
    m.style.cssText='grid-column:1/-1;color:var(--muted);font-size:12px;padding:2px'; m.textContent=t; box.appendChild(m); };
  if(!all.length) note(T('Keine Loxone-Bibliothek gefunden — LoxoneIcons-Plugin installiert und gemountet?'));
  else if(list.length>300) note((list.length-300)+' '+T('weitere — Suche eingrenzen'));
  else if(!list.length) note(T('Nichts gefunden.'));
}
