// LoxPanel-Konfigurator, Teil 2 von 11: Aktiv-Overlay, Kachel-Set, Gesten.
// Die Teile laden nacheinander aus config.html (script src), alle Funktionen sind global;
// was beim Laden ausgefuehrt wird, darf nur Funktionen frueherer Teile rufen.

// ---- Aktiv-Overlay (Rahmen/Füllung/Deckkraft) ----
const OV_DEF={mode:'both',fill:16,bord:55,bw:1,ibord:8,ibw:1,ring:100,rtrk:18,rw:6};
function ovVal(ov,k){ return (ov&&ov[k]!=null)?ov[k]:OV_DEF[k]; }
function pruneOverlay(host){ if(host&&host.overlay&&!Object.keys(host.overlay).length) delete host.overlay; }
function overlayFields(ov,pfx){
  const m=ovVal(ov,'mode'),fi=ovVal(ov,'fill'),bo=ovVal(ov,'bord'),bw=ovVal(ov,'bw'),
        ib=ovVal(ov,'ibord'),ibw=ovVal(ov,'ibw'),
        rg=ovVal(ov,'ring'),rt=ovVal(ov,'rtrk'),rw=ovVal(ov,'rw');
  const opt=(v,t)=>'<option value="'+v+'"'+(m===v?' selected':'')+'>'+t+'</option>';
  return '<div class="ovgrp">Aktive Kacheln</div>'+
    '<div class="frow"><label class="lbl">Darstellung</label><select id="'+pfx+'mode">'+
      opt('both','Rahmen + Füllung')+opt('border','Nur Rahmen')+opt('fill','Nur Füllung')+'</select></div>'+
    '<div class="frow"><label class="lbl">Füllung</label>'+
      '<input type="range" id="'+pfx+'fill" min="0" max="100" step="5" value="'+fi+'">'+
      '<span class="cval" id="'+pfx+'fillv">'+fi+' %</span></div>'+
    '<div class="frow"><label class="lbl">Rahmen</label>'+
      '<input type="range" id="'+pfx+'bord" min="0" max="100" step="5" value="'+bo+'">'+
      '<span class="cval" id="'+pfx+'bordv">'+bo+' %</span></div>'+
    '<div class="frow"><label class="lbl">Rahmenbreite</label><select id="'+pfx+'bw">'+
      [1,2,3,4].map(n=>'<option value="'+n+'"'+(bw===n?' selected':'')+'>'+n+' px</option>').join('')+'</select></div>'+
    '<div class="ovgrp">Inaktive Kacheln &amp; rechte Panes <span class="ovgrp-h">(Rahmen, z. B. für helle Displays)</span></div>'+
    '<div class="frow"><label class="lbl">Rahmen</label>'+
      '<input type="range" id="'+pfx+'ibord" min="0" max="100" step="5" value="'+ib+'">'+
      '<span class="cval" id="'+pfx+'ibordv">'+ib+' %</span></div>'+
    '<div class="frow"><label class="lbl">Rahmenbreite</label><select id="'+pfx+'ibw">'+
      [1,2,3,4].map(n=>'<option value="'+n+'"'+(ibw===n?' selected':'')+'>'+n+' px</option>').join('')+'</select></div>'+
    '<div class="ovgrp">Positionsring <span class="ovgrp-h">(Rollladen, Tor, Fenster, Dimmer)</span></div>'+
    '<div class="frow"><label class="lbl">Strichstärke</label>'+
      '<input type="range" id="'+pfx+'rw" min="1" max="12" step="1" value="'+rw+'">'+
      '<span class="cval" id="'+pfx+'rwv"></span></div>'+
    '<div class="frow"><label class="lbl">Bogen</label>'+
      '<input type="range" id="'+pfx+'ring" min="0" max="100" step="5" value="'+rg+'">'+
      '<span class="cval" id="'+pfx+'ringv">'+rg+' %</span></div>'+
    '<div class="frow"><label class="lbl">Spur</label>'+
      '<input type="range" id="'+pfx+'rtrk" min="0" max="100" step="2" value="'+rt+'">'+
      '<span class="cval" id="'+pfx+'rtrkv">'+rt+' %</span></div>';
}
// Der Ring ist so dick wie `rw` Prozent von (Icon-Größe + 18 px), die Icon-Linie
// dagegen 1,7/24 der Icon-Größe. Beides in Pixeln nebeneinander zu zeigen ist
// der einzige Weg, die eigentliche Ursache sichtbar zu machen: durch den festen
// 18-px-Sockel wird der Ring bei kleinen Icons dicker als die Linien, die er
// umschließt.
function ringHint(rw,ico){
  const s=Number(ico)||38;
  const ring=rw/100*(s+18), lin=1.7*(s/24);
  return ring.toFixed(1)+' px gegen '+lin.toFixed(1)+' px Iconlinie ('
    +(ring/lin).toFixed(2)+'×)';
}
function bindOverlay(pfx,getOv,onChange){
  const m=$('#'+pfx+'mode'),fi=$('#'+pfx+'fill'),bo=$('#'+pfx+'bord'),bw=$('#'+pfx+'bw'),
        fiv=$('#'+pfx+'fillv'),bov=$('#'+pfx+'bordv'),
        ib=$('#'+pfx+'ibord'),ibw=$('#'+pfx+'ibw'),ibv=$('#'+pfx+'ibordv'),
        rg=$('#'+pfx+'ring'),rgv=$('#'+pfx+'ringv'),
        rt=$('#'+pfx+'rtrk'),rtv=$('#'+pfx+'rtrkv'),
        rw=$('#'+pfx+'rw'),rwv=$('#'+pfx+'rwv');
  const set=(k,v)=>{ getOv()[k]=v; onChange(); };
  if(m) m.onchange=()=>set('mode',m.value);
  if(fi) fi.oninput=()=>{ fiv.textContent=fi.value+' %'; set('fill',Number(fi.value)); };
  if(bo) bo.oninput=()=>{ bov.textContent=bo.value+' %'; set('bord',Number(bo.value)); };
  if(bw) bw.onchange=()=>set('bw',Number(bw.value));
  if(ib) ib.oninput=()=>{ ibv.textContent=ib.value+' %'; set('ibord',Number(ib.value)); };
  if(ibw) ibw.onchange=()=>set('ibw',Number(ibw.value));
  // Die Icon-Größe steht im selben Formular; der Hinweis rechnet mit ihr, damit
  // das Verhältnis Ring zu Iconlinie beim Schieben direkt ablesbar ist.
  const icoJetzt=()=>{ const i=document.querySelector('input[data-ui="iconSize"]');
                       return Number(i&&(i.value||i.placeholder))||sizeStd('',true).iconSize; };
  const rwHint=()=>{ if(rwv&&rw) rwv.textContent=ringHint(Number(rw.value),icoJetzt()); };
  if(rw){ rwHint(); rw.oninput=()=>{ rwHint(); set('rw',Number(rw.value)); }; }
  if(rg) rg.oninput=()=>{ rgv.textContent=rg.value+' %'; set('ring',Number(rg.value)); };
  if(rt) rt.oninput=()=>{ rtv.textContent=rt.value+' %'; set('rtrk',Number(rt.value)); };
}
function ovPreview(elId,ov){
  const el=$('#'+elId);
  if(el){
    const m=ovVal(ov,'mode'); let fill=ovVal(ov,'fill')/100, bord=ovVal(ov,'bord')/100;
    if(m==='border') fill=0; if(m==='fill') bord=0;
    el.style.setProperty('--ov-fill',fill);
    el.style.setProperty('--ov-bord',bord);
    el.style.setProperty('--ov-bw',ovVal(ov,'bw')+'px');
  }
  const off=$('#'+elId+'Off');   // Vorschau der inaktiven Kachel
  if(off){
    off.style.setProperty('--tile-bord','rgba(255,255,255,'+(ovVal(ov,'ibord')/100)+')');
    off.style.setProperty('--tile-bw',ovVal(ov,'ibw')+'px');
  }
}

function bindAppearance(p){
  document.querySelectorAll('input[data-ui]').forEach(inp=>{
    inp.oninput=()=>{ p.ui=p.ui||{}; const k=inp.dataset.ui;
      if(inp.value==='') delete p.ui[k]; else p.ui[k]=Number(inp.value); markDirty(); }; });
  // An/Aus mit "leer = geerbt" (Nacht-Uhr): an -> true, aus -> false, leer -> fehlt
  document.querySelectorAll('select[data-ui-wahl]').forEach(sel=>{
    sel.onchange=()=>{ p.ui=p.ui||{}; const k=sel.dataset.uiWahl;
      if(sel.value==='an') p.ui[k]=true; else if(sel.value==='aus') p.ui[k]=false; else delete p.ui[k];
      markDirty(); erbtZeichnen(); }; });
  { const fs=$('#fFontSel'), fc=$('#fFontCustom');
    if(fs) fs.onchange=()=>{ p.ui=p.ui||{};
      if(fs.value==='__custom'){ fc.style.display=''; const v=fc.value.trim(); v?p.ui.font=v:delete p.ui.font; }
      else { fc.style.display='none'; fs.value?p.ui.font=fs.value:delete p.ui.font; } markDirty(); };
    if(fc) fc.oninput=()=>{ p.ui=p.ui||{}; const v=fc.value.trim(); v?p.ui.font=v:delete p.ui.font; markDirty(); }; }
  { const ci=$('#fTextColor'), cc=$('#fTextColorClr'), cv=$('#fTextColorVal');
    if(ci) ci.oninput=()=>{ p.ui=p.ui||{}; p.ui.textColor=ci.value; if(cv)cv.textContent=ci.value; markDirty(); };
    if(cc) cc.onclick=()=>{ if(p.ui) delete p.ui.textColor; if(cv)cv.textContent='Standard'; markDirty(); }; }
  { const b=$('#fBold'); if(b) b.onchange=e=>{ p.ui=p.ui||{}; e.target.value?p.ui.bold=true:delete p.ui.bold; markDirty(); }; }
  { const ls=$('#fLang'); if(ls) ls.onchange=()=>{ p.ui=p.ui||{}; ls.value?p.ui.lang=ls.value:delete p.ui.lang; markDirty(); }; }
  { const setBase=v=>{ p.ui=p.ui||{};
      if(v) p.ui.baseColor=v; else delete p.ui.baseColor;
      const cv=$('#fBaseVal'); if(cv) cv.textContent=v||T('Standard-Farbschema');
      document.querySelectorAll('.baseSw').forEach(b=>{
        const an=String(b.dataset.base||'').toLowerCase()===String(v||'').toLowerCase();
        b.setAttribute('aria-pressed', an?'true':'false');
        b.style.boxShadow = an ? '0 0 0 2px var(--panel),0 0 0 4px var(--accent)' : '';
      });
      markDirty(); };
    document.querySelectorAll('.baseSw').forEach(b=>{ b.onclick=()=>setBase(b.dataset.base); });
    { const c=$('#fBaseClr'); if(c) c.onclick=()=>setBase(''); }
    { const c=$('#fBaseCustom'); if(c) c.oninput=()=>setBase(c.value); } }
}
// Grundfarben fuer das Panel-Theme. Aus jeder faellt der ganze Satz ab; der
// Server rechnet ihn in bin/theme_colors.py aus und prueft ihn dabei nach.
const BASE_COLORS = [
  {v:'#1c1c1e',n:'Anthrazit'}, {v:'#dedfe0',n:'Hellgrau'},   {v:'#f7f5ec',n:'Creme'},
  {v:'#d9a83c',n:'Senfgelb'},  {v:'#b0344a',n:'Crimson'},    {v:'#f8e1e2',n:'Rosé'},
  {v:'#cedcdd',n:'Eisblau'},   {v:'#3e4468',n:'Marineblau'}, {v:'#3e5240',n:'Tannengrün'},
  {v:'#a8ad93',n:'Salbei'},    {v:'#ec9a80',n:'Lachs'},      {v:'#7a3f1e',n:'Nussbraun'}
];
// ---- Kachel-Set (ui.tileSet; theme_colors.KACHEL_SETS ueber /api/meta) ----
function kachelSetMeta(k){ return ((META&&META.kachelSets)||[]).find(x=>x.key===k)||null; }
function ksFarbton(ui, s){ const v=parseInt(ui.tileHue); return (v>=0 && v<360) ? v : s.farbton.standard; }
// Vorschau eines Sets auf seiner Karte: Rahmen, Flaeche, zwei Kacheln und
// die aktive mit Akzent - die Farben kommen vom Server (kachel_set_vorschau)
function kachelSetMini(v){
  v=v||{}; const k='<i style="background:'+esc(v.kachel||'')+'"></i>';
  return '<span class="ks-mini" data-ks-mini style="background:'+esc(v.rahmen||'')+'"><span class="ks-feld" style="background:'+esc(v.flaeche||'')+'">'+
    k+'<i class="an" style="background:'+esc(v.an||'')+';--ks-akzent:'+esc(v.akzent||'')+'"></i>'+k+'</span></span>';
}
// Auswahl des Sets als Karten: leer = ohne Set (Farben aus der Grundfarbe,
// Vorschau aus den Grundfarben), sonst jedes Set aus /api/meta mit seiner
// Beschreibung. Ein Klick setzt data-ks-set; wer die Karten zeigt, bindet es.
function kachelSetKarten(ui){
  const wahl=ui.tileSet||'';
  const karte=(key,label,info,mini)=>'<button type="button" class="ks-karte'+(wahl===key?' on':'')+'" data-ks-set="'+esc(key)+'" aria-pressed="'+(wahl===key)+'">'+
    mini+'<b>'+esc(label)+'</b><span class="ks-info">'+esc(info)+'</span></button>';
  const grund='<span class="ks-mini grund">'+BASE_COLORS.slice(0,4).map(c=>'<i style="background:'+esc(c.v)+'"></i>').join('')+'</span>';
  return '<div class="ks-karten" role="group" aria-label="'+esc(T('Kachel-Set'))+'">'+
    karte('', T('Eigene Farben'), T('Ohne Set: Farben aus der Grundfarbe, Kachel-Aufbau frei wählbar.'), grund)+
    ((META&&META.kachelSets)||[]).map(ks=>karte(ks.key, T(ks.label), T(ks.info), kachelSetMini(ks.vorschau))).join('')+'</div>';
}
// Karten nach einer Wahl umstellen (ohne neu zu zeichnen)
function kachelSetKartenWahl(host, key){
  (host||document).querySelectorAll('[data-ks-set]').forEach(b=>{ const an=b.dataset.ksSet===(key||'');
    b.classList.toggle('on', an); b.setAttribute('aria-pressed', String(an)); });
}
// Farbton und aktive Kachel eines Sets mit Rechnung (touch): Regler 0-359 auf
// dem Verlauf der Kachelfarben, Schnellwahl und Umschalter aus /api/meta. Leer,
// wenn das gewaehlte Set keinen Farbton hat.
function kachelSetExtraHtml(ui){
  const s=kachelSetMeta(ui.tileSet); if(!s || !s.farbton) return '';
  const h=ksFarbton(ui, s), ak=ui.tileActive||s.aktiv.standard, v=s.farbton.verlauf;
  const verlauf='linear-gradient(to right,'+v.concat([v[0]]).join(',')+')';
  return '<div class="ks-extra">'+
    '<div><div class="ks-kopf"><label class="lbl" for="ksHue" style="margin:0">'+T('Farbton')+'</label>'+
      '<span class="cval" data-ks-wert>'+h+'°</span></div>'+
    '<input type="range" class="ks-hue" id="ksHue" min="0" max="359" step="1" value="'+h+'" data-ks-hue style="--ks-verlauf:'+esc(verlauf)+'"></div>'+
    '<div><div class="lbl">'+T('Schnellwahl')+'</div><div class="ks-schnell">'+s.farbton.auswahl.map(f=>
      '<button type="button" class="ks-ton'+(f.wert===h?' on':'')+'" data-ks-ton="'+f.wert+'" aria-pressed="'+(f.wert===h)+'">'+
      '<span class="ks-punkt" style="background:'+esc(f.farbe)+'"></span>'+esc(T(f.label))+'</button>').join('')+'</div></div>'+
    '<div><div class="lbl">'+T('Aktive Kachel')+'</div>'+
    '<div class="segmode" role="group" aria-label="'+esc(T('Aktive Kachel'))+'">'+s.aktiv.auswahl.map(a=>'<button type="button" data-ks-aktiv="'+esc(a.key)+'" aria-pressed="'+(a.key===ak)+'"'+
      (a.key===ak?' class="on"':'')+'>'+esc(T(a.label))+'</button>').join('')+'</div></div>'+
    '<div class="ks-pruefung" data-ks-pruefung><div class="lbl" style="margin:0">'+T('Nachgerechnet')+'</div></div></div>';
}
// "Nachgerechnet": die Kontraste zu Farbton und aktiver Kachel rechnet der
// Server (/api/kachelset, theme_colors.kachel_set_pruefung), die Seite zeigt
// sie nur. Die letzte Antwort gewinnt.
let _ksAbruf=0;
async function kachelSetPruefen(host, ui){
  const box=host && host.querySelector('[data-ks-pruefung]'), s=kachelSetMeta(ui.tileSet);
  if(!box || !s || !s.farbton) return;
  const nr=++_ksAbruf, q=new URLSearchParams({set:ui.tileSet, farbton:String(ksFarbton(ui, s)), aktiv:ui.tileActive||s.aktiv.standard});
  let d=null;
  try{ const r=await fetch('/api/kachelset?'+q.toString()); if(r.ok) d=await r.json(); }catch(e){ d=null; }
  if(nr!==_ksAbruf || !d) return;
  const zahl=x=>String(x.toFixed(1)).replace('.',',')+' : 1';
  box.innerHTML='<div class="lbl" style="margin:0">'+T('Nachgerechnet')+'</div>'+(d.pruefung||[]).map(k=>
    '<div class="ks-zeile" data-ks-paar><span>'+esc(T(k.name))+' ('+esc(T('Ziel'))+' '+esc(zahl(k.ziel))+')</span><b>'+esc(zahl(k.wert))+'</b></div>').join('');
  const w=host.querySelector('[data-ks-wert]'); if(w) w.textContent=ksFarbton(ui, s)+'° · '+(d.kachel||'');
  // die Karte des Sets zeigt den gewaehlten Farbton
  const mini=document.querySelector('.ks-karte[data-ks-set="'+ui.tileSet+'"] [data-ks-mini]');
  if(mini && d.vorschau) mini.outerHTML=kachelSetMini(d.vorschau);
}
// Bindet kachelSetExtraHtml() in host: ui() ist das ui-Objekt, das sich
// aendert, fertig() laeuft nach jeder Aenderung. Der Standard wird nicht
// gespeichert (PANEL_STANDARD im Server).
function kachelSetExtraBinden(host, ui, fertig){
  const s=host && kachelSetMeta(ui().tileSet); if(!s || !s.farbton) return;
  const setzeTon=v=>{ const u=ui(); if(v===s.farbton.standard) delete u.tileHue; else u.tileHue=v;
    const w=host.querySelector('[data-ks-wert]'); if(w) w.textContent=v+'°';
    const r=host.querySelector('[data-ks-hue]'); if(r && +r.value!==v) r.value=v;
    host.querySelectorAll('[data-ks-ton]').forEach(b=>{ const an=+b.dataset.ksTon===v; b.classList.toggle('on', an); b.setAttribute('aria-pressed', String(an)); });
    kachelSetPruefen(host, u); fertig(); };
  const r=host.querySelector('[data-ks-hue]'); if(r) r.oninput=()=>setzeTon(+r.value);
  host.querySelectorAll('[data-ks-ton]').forEach(b=>{ b.onclick=()=>setzeTon(+b.dataset.ksTon); });
  host.querySelectorAll('[data-ks-aktiv]').forEach(b=>{ b.onclick=()=>{ const u=ui(), k=b.dataset.ksAktiv;
    if(k===s.aktiv.standard) delete u.tileActive; else u.tileActive=k;
    host.querySelectorAll('[data-ks-aktiv]').forEach(x=>{ const an=x===b; x.classList.toggle('on', an); x.setAttribute('aria-pressed', String(an)); });
    kachelSetPruefen(host, u); fertig(); }; });
  kachelSetPruefen(host, ui());
}
// Masse fuer die Rasterrechnung (raster.js) wie autoRaster() der Visu, aus
// den Massen des Kachel-Sets (/api/meta, schmal oder nicht nach der Breite,
// die Tab-Leiste auch nach der Hoehe: LoxRaster.leisteMass):
// Leistenhoehe (tabsH), die Seitenleiste eines Sets mit Leiste "links" nimmt
// Breite (railW) statt Hoehe, "oben" steht die Leiste ueber dem Raster und
// ein Rahmen geht ab (rahmenX links und rechts, rahmenY unten), dazu Abstand
// und Innenrand des Rasters. Ohne Set die Masse der Visu (VISU_MASSE).
function leisteMasse(setKey, vw, vh){
  const s=kachelSetMeta(setKey), M=LoxRaster.VISU_MASSE, art=(s&&s.leiste)||'';
  const mass=(n,r)=>LoxRaster.leisteMass((s&&s.masse)||{}, n, vw, vh, r);
  const lm={art:art, gap:mass('--kachel-abstand',M.gap), pad:mass('--feld-innen',M.pad),
            tabsH:mass('--tabs-hoehe',M.tabsH), railW:0, rahmenX:0, rahmenY:0};
  if(art==='links'){ lm.railW=mass('--rail-breite',0); lm.tabsH=0; }
  if(art==='oben'){ lm.rahmenX=2*mass('--rahmen-seite',0); lm.rahmenY=mass('--rahmen-unten',0); }
  return lm;
}
function baseRing(an){ return an?'box-shadow:0 0 0 2px var(--panel),0 0 0 4px var(--accent);':''; }
function baseField(ui){
  const cur=String(ui.baseColor||'').toLowerCase();
  return '<div class="field" style="max-width:none">'+
    '<p class="note" style="margin:0 0 8px">'+T('Eine Farbe wählen — Hintergrund, Kacheln, Leiste, Schrift, Icons und Zustandsfarben werden daraus berechnet. Eigene Zustandsfarben behalten Vorrang.')+'</p>'+
    '<div style="display:flex;flex-wrap:wrap;gap:8px;align-items:center">'+
      BASE_COLORS.map(c=>'<button type="button" class="baseSw" data-base="'+esc(c.v)+'" '+
        'title="'+esc(c.n)+'" aria-pressed="'+(cur===c.v?'true':'false')+'" '+
        'style="width:46px;height:46px;border-radius:7px;padding:0;cursor:pointer;'+
        'background:'+esc(c.v)+';border:1px solid var(--line);'+baseRing(cur===c.v)+'"></button>').join('')+
      '<input type="color" id="fBaseCustom" title="'+esc(T('Eigene Farbe'))+'" value="'+
        esc(cur&&cur[0]==='#'?ui.baseColor:'#3e4468')+'" '+
        'style="width:46px;height:46px;padding:0;border:1px solid var(--line);border-radius:7px;background:var(--bg);cursor:pointer">'+
      '<button type="button" class="minibtn" id="fBaseClr" style="height:46px">'+T('Keine')+'</button>'+
    '</div>'+
    '<span class="cval" id="fBaseVal" style="display:block;margin-top:6px;font-size:13px">'+
      esc(ui.baseColor||T('Standard-Farbschema'))+'</span>'+erbtFeld('baseColor')+'</div>';
}
// Eine Gruppe im Aussehen: Ueberschrift, Felder, kurzer Hinweis, Erklaerung
// zum Aufklappen (mehr = [Frage, Text]); attr fuer id/hidden der Gruppe
function aussehenGruppe(titel, felder, hinweis, mehr, attr){
  return '<div class="agr"'+(attr||'')+'><div class="grph">'+titel+'</div>'+felder+
    (hinweis?'<div class="hint agr-hint">'+hinweis+'</div>':'')+
    (mehr?'<details class="agr-mehr"><summary>'+mehr[0]+'</summary><p>'+mehr[1]+'</p></details>':'')+'</div>';
}
// Aufbau der Hausuebersicht (ui.hausAufbau): Auswahl und Standard aus /api/meta
// (HAUS_AUFBAUTEN im Server), der Standard wird nicht gespeichert
function hausAufbauFeld(ui){
  const std=(META&&META.hausAufbauStandard)||'', wert=ui.hausAufbau||std;
  return '<div class="sizes"><div class="field" style="max-width:none;min-width:280px"><label class="lbl">'+T('Aufbau')+'</label>'+
    '<select id="fHausAufbau" style="width:100%;max-width:none">'+((META&&META.hausAufbauten)||[]).map(a=>
      '<option value="'+esc(a.key)+'"'+(a.key===wert?' selected':'')+'>'+esc(T(a.label))+'</option>').join('')+'</select></div></div>';
}
function schriftFelder(ui){
  return '<div class="sizes">'+
    '<div class="field" style="max-width:220px"><label class="lbl">'+T('Schriftart')+'</label>'+
      '<select id="fFontSel">'+FONTS.map(f=>'<option value="'+esc(f.v)+'"'+(sameFont(ui.font,f.v)?' selected':'')+'>'+esc(f.label)+'</option>').join('')+
        '<option value="__custom"'+(customFont(ui.font)?' selected':'')+'>Eigene…</option></select>'+
      '<input type="text" id="fFontCustom" value="'+esc(customFont(ui.font)?ui.font:'')+'" placeholder="z. B. Pacifico, cursive"'+(customFont(ui.font)?'':' style="display:none"')+'>'+erbtFeld('font')+'</div>'+
    '<div class="field" style="max-width:230px"><label class="lbl">'+T('Schriftfarbe (Haupttext)')+'</label>'+
      '<div style="display:flex;align-items:center;gap:8px">'+
        '<input type="color" id="fTextColor" value="'+esc(ui.textColor&&String(ui.textColor)[0]==="#"?ui.textColor:"#e8eaed")+'" style="width:40px;height:30px;padding:0;border:1px solid var(--line);border-radius:4px;background:var(--bg);cursor:pointer">'+
        '<span class="cval" id="fTextColorVal" style="flex:1">'+esc(ui.textColor||"Standard")+'</span>'+
        '<button class="minibtn" id="fTextColorClr">Standard</button></div>'+erbtFeld('textColor')+'</div>'+
    '<div class="field" style="max-width:150px"><label class="lbl">Schriftstärke</label>'+
      '<select id="fBold"><option value="">Normal</option><option value="1"'+(ui.bold?' selected':'')+'>Fett</option></select>'+erbtFeld('bold')+'</div>'+
  '</div>';
}
// Groessen der Kachel-Beschriftung; leer erklaert, was ein leeres Feld nimmt
function groessenGruppe(ui,std,leer){
  return aussehenGruppe(T('Größen'), '<div class="sizes">'+sizeField('Icon-Größe','iconSize',ui,std)+sizeField(T('Haupttext-Größe'),'nameSize',ui,std)+
    sizeField(T('Zweittext-Größe'),'subSize',ui,std)+sizeField(T('Raum-Größe'),'roomSize',ui,std)+sizeField(T('Messwert-Größe'),'bigSize',ui,std)+'</div>',
    leer, [T('Was bedeuten die Größen?'), T('Haupttext ist die große Zeile der Kachel, Zweittext die kleine darunter. Im klassischen Aufbau ist das der Name und darunter der Zustand, im neuen steht meist der Zustand groß und der Name klein. Raum ist die Raumangabe, Messwert die große Temperatur an Stelle des Symbols.')]);
}
// Vorgaben: Grundfarbe, Sprache, Schrift, Groessen
function appearanceFields(ui,std,leer){
  ui=ui||{};
  return aussehenGruppe(T('Grundfarbe'), baseField(ui))+
    aussehenGruppe(T('Sprache'), '<div class="sizes">'+langField(ui)+'</div>')+
    aussehenGruppe(T('Schrift'), schriftFelder(ui))+
    groessenGruppe(ui,std,leer);
}

function renderGlobalEditor(p){
  if(!VG_TABS.some(t=>t.k===subVg)) subVg='appearance';
  const ui=p.ui||{}, nstd=META.nightDefaults||{};
  $('#phead').innerHTML='<h2>🌐 Vorgaben</h2><span class="badge">für alle Ansichten</span>'+
    '<span class="kurl">'+T('Werte für alle Ansichten, die sie nicht selbst setzen. Eine Ansicht überschreibt sie unter Raster, Aussehen und Verhalten.')+'</span>';
  $('#pconfHost').innerHTML =
    '<section class="spane" data-sub="appearance"><div class="card"><h3>Darstellung</h3>'+
      '<p class="note">Schrift, Größe, Farbe und Stärke der Kachel-Beschriftung — gilt für alle Ansichten.</p>'+
      appearanceFields(p.ui,sizeStd('',false),
        T('Ein leeres Feld nimmt den Standard des Kachel-Aufbaus; grau steht der des neuen Aufbaus.'))+
      altEintragHtml(p, ['scale'], 'gAlt')+
      '</div></section>'+
    '<section class="spane" data-sub="catcolors"><div class="card"><h3>Kategorie-Farben (Ampel)</h3>'+
      '<p class="note">'+T('Pro Kategorie eine <b>Aktiv-</b> und <b>OK-Farbe</b> für Kachel-Hintergrund und Rahmen — gilt auf allen Geräten (Wiedererkennung). ◐ einschalten = Zustands-Ampel (z. B. Alarm rot/grün, Tor gelb/grün). Aus = neutral. Analoge Messwerte bleiben immer neutral.')+'</p>'+
      '<div class="cclist" id="catcolors"></div></div></section>'+
    '<section class="spane" data-sub="verhalten"><div class="card"><h3>'+T('Nacht')+'</h3>'+
      '<p class="note">'+T('Wann die Geräte abdunkeln. Ohne Auslöser entscheidet der Sonnenuntergang — die Zeiten kommen vom Miniserver, ersatzweise vom Wetterdienst. Als Auslöser lässt sich jeder Baustein mit Ein/Aus-Zustand wählen; sein Ein-Zustand bedeutet Nacht. Damit auch ein Loxone-Betriebsmodus, sobald er in Loxone Config auf einen Status-Baustein mit Raum und Kategorie gelegt ist — der Modus selbst steht nicht in der Visu.')+'</p>'+
      '<div class="row2"><div class="field" style="max-width:460px"><label class="lbl">'+T('Auslöser (optional)')+'</label><select id="nt_control"></select></div></div>'+
      '<div class="grph">'+T('Abdunkelung')+'</div>'+
      '<div class="sizes">'+nachtFelder(ui, nstd.nightDim, nstd.nightWake)+'</div>'+
      '<p class="note">'+T('Nacht-Uhr: Nachts zeigt die Uhr-Seite nur die Uhrzeit, gedimmt auf Schwarz, wie die Nachtanzeige der Loxone-Taster. Sind Gesten an, stehen oben die Symbole ihrer Spalten. „Nachts abdunkeln“ wirkt zusätzlich.')+'</p>'+
      '<p class="note">'+T('Abdunkeln und Aufhellen gelten für jedes Gerät ohne eigenen Wert (Karte des Geräts, Zeile Display), die Nacht-Uhr für alle Geräte.')+'</p>'+
    '</div><div class="card"><h3>'+T('Display &amp; Neustart')+'</h3>'+
      '<div class="sizes">'+displayFelder(ui, null, null)+'</div>'+
      '<div class="hint" style="padding-top:4px">'+esc(autoNeustartHinweis())+'</div>'+
      '<p class="note">'+T('„Display aus nach“ gilt für jedes Gerät ohne eigenen Wert (Zeile Display), der Auto-Neustart für alle Ansichten, die unter Verhalten nichts eintragen.')+'</p>'+
    '</div>'+gestenVorgabenKarte(ui)+'</section>';
  bindAppearance(p);
  nachtZeichnen();
  { const s=$('#nt_control'); if(s) s.onchange=()=>{ NACHT.control=s.value; bereichOffen('nacht'); }; }
  aufhellenZeigen(nstd.nightDim);
  altEintragBinden(p);
  renderCatColors(p);
  gestenVorgabenBinden(p);
  $('#delSlot').innerHTML='';
  erbtZeichnen();
  renderSubtabs(); showSub(subVg);
}
// ---- Gesten (Loxone-Standard wie auf den Tastern) ----
// Vorgaben -> Verhalten: an/aus fuer alle Ansichten, Taster fuer "Haus aus"
// (Dreifachtipp) und je Raum fuer "Raum verlassen" (Doppeltipp). Die Taster
// listet der Server (/api/meta gestenTaster: nur Pushbutton, nur er nimmt einen
// Impuls). Ansicht -> Verhalten: an/aus und der Raum ausserhalb von Raumseiten.
function gestenWahl(id, wert, leer){
  return '<select id="'+id+'"><option value="">'+esc(leer)+'</option>'+
    '<option value="an"'+(wert===true?' selected':'')+'>'+T('An')+'</option>'+
    '<option value="aus"'+(wert===false?' selected':'')+'>'+T('Aus')+'</option></select>';
}
function tasterOptionen(sel, leer){
  const opts=((META||{}).gestenTaster||[]).slice();
  if(sel && !opts.some(o=>o.uuid===sel)) opts.unshift({uuid:sel, name:sel+' ('+T('nicht in der Struktur')+')', room:''});
  return '<option value="">'+esc(leer)+'</option>'+
    opts.map(o=>'<option value="'+esc(o.uuid)+'"'+(o.uuid===sel?' selected':'')+'>'+
      esc((o.room?o.room+' · ':'')+o.name)+'</option>').join('');
}
function gestenRaumOptionen(sel){
  const raeume=((META||{}).rooms||[]).slice();
  if(sel && !raeume.some(r=>r.uuid===sel)) raeume.unshift({uuid:sel, name:sel+' ('+T('nicht in der Struktur')+')'});
  return '<option value="">'+T('— keiner (nur auf Raumseiten) —')+'</option>'+
    raeume.map(r=>'<option value="'+esc(r.uuid)+'"'+(r.uuid===sel?' selected':'')+'>'+esc(r.name)+'</option>').join('');
}
function gestenVorgabenKarte(ui){
  const rv=ui.raumVerlassen||{};
  return '<div class="card"><h3>'+T('Gesten')+'</h3>'+
    '<p class="note">'+T('Zwei Finger bedienen den Raum der Seite wie ein Loxone-Taster: Mitte Licht (hoch/runter dimmt, ein Tipp schaltet ein bzw. zur nächsten Stimmung), links Beschattung, rechts Musik, Doppeltipp Raum verlassen, Dreifachtipp Haus aus. Ein Finger bedient die Visu wie bisher.')+'</p>'+
    '<div class="row2"><div class="field" style="max-width:320px"><label class="lbl">'+T('Gesten für alle Ansichten')+'</label>'+
      gestenWahl('gGesten', ui.gesten, T('Standard ({w})').replace('{w}', wertText('gesten', standardWert('gesten'))))+
      erbtFeld('gesten')+'</div>'+
      '<div class="field" style="max-width:320px"><label class="lbl">'+T('Hinweis-Symbol')+'</label>'+
      gestenWahl('gHinweis', ui.gestenHinweis, T('Standard ({w})').replace('{w}', wertText('gestenHinweis', standardWert('gestenHinweis'))))+
      erbtFeld('gestenHinweis')+'</div></div>'+
    '<p class="note">'+T('Hinweis-Symbol: rechts unter dem Kachelfeld, auf Seiten, auf denen Gesten wirken. Ein Tipp darauf zeigt, was zwei Finger dort tun. Es braucht eine Zeile unter den Kacheln, auf jeder Seite der Ansicht, damit die Kacheln gleich groß bleiben. Nicht auf kleinen Schirmen (4″-Panel).')+'</p>'+
    '<div class="grph">'+T('Haus aus (Dreifachtipp)')+'</div>'+
    '<div class="row2"><div class="field" style="max-width:460px"><label class="lbl">'+T('Taster aus Loxone Config')+'</label>'+
      '<select id="gHausAus">'+tasterOptionen(ui.hausAus, T('— keiner (Dreifachtipp wirkt nicht) —'))+'</select></div></div>'+
    '<div class="grph">'+T('Raum verlassen (Doppeltipp)')+'</div>'+
    '<p class="note">'+T('Je Raum ein Taster aus Loxone Config, dann regelt die Loxone-Logik alles, auch das Raumklima. Ohne Taster schaltet LoxPanel aus, was im Raum an ist und sich abschalten lässt; das Raumklima bleibt dann unberührt.')+'</p>'+
    '<div class="sizes">'+((META||{}).rooms||[]).map(r=>
      '<div class="field" style="max-width:320px"><label class="lbl">'+esc(r.name)+'</label>'+
      '<select data-gv-raum="'+esc(r.uuid)+'">'+tasterOptionen(rv[r.uuid]||'', T('— ohne Taster: ausschalten, was an ist —'))+'</select></div>').join('')+'</div>'+
    '<p class="note">'+T('Zur Auswahl stehen Taster (virtueller Eingang): nur sie nehmen laut Loxone einen Impuls an. Bausteine mit Visu-Passwort fehlen, denn eine Geste kann keine PIN abfragen.')+'</p>'+
  '</div>';
}
function gestenVorgabenBinden(p){
  const ui=()=>{ p.ui=p.ui||{}; return p.ui; };
  const gg=$('#gGesten');
  if(gg) gg.onchange=()=>{ const u=ui();
    if(gg.value==='an') u.gesten=true; else if(gg.value==='aus') u.gesten=false; else delete u.gesten;
    markDirty(); erbtZeichnen(); };
  const gh=$('#gHinweis');
  if(gh) gh.onchange=()=>{ const u=ui();
    if(gh.value==='an') u.gestenHinweis=true; else if(gh.value==='aus') u.gestenHinweis=false; else delete u.gestenHinweis;
    markDirty(); erbtZeichnen(); };
  const ha=$('#gHausAus');
  if(ha) ha.onchange=()=>{ const u=ui(); if(ha.value) u.hausAus=ha.value; else delete u.hausAus; markDirty(); };
  document.querySelectorAll('#pconfHost [data-gv-raum]').forEach(sel=>sel.onchange=()=>{
    const u=ui(), rv=Object.assign({}, u.raumVerlassen||{});
    if(sel.value) rv[sel.dataset.gvRaum]=sel.value; else delete rv[sel.dataset.gvRaum];
    if(Object.keys(rv).length) u.raumVerlassen=rv; else delete u.raumVerlassen;
    markDirty(); });
}
// Felder "Nachts abdunkeln" und "Aufhellen bei Beruehrung" (Vorgaben -> Nacht und
// Ansicht -> Verhalten). Ein leeres Feld zeigt grau, was ohne Eintrag gilt.
function nachtPlatzhalter(k,v){
  if(v==null) return '';
  return (k==='nightDim' && Number(v)===0) ? T('0 = aus') : String(v);
}
function nachtFelder(ui, dimLeer, wakeLeer){
  const wert=k=>(ui[k]==null)?'':ui[k];
  return '<div class="field" style="max-width:180px"><label class="lbl">'+T('Nachts abdunkeln (%)')+'</label>'+
      '<input type="number" min="0" max="90" step="5" data-ui="nightDim" value="'+esc(wert('nightDim'))+'" placeholder="'+esc(nachtPlatzhalter('nightDim',dimLeer))+'">'+erbtFeld('nightDim')+'</div>'+
    '<div class="field" style="max-width:180px" id="nightWakeField"><label class="lbl">'+T('Aufhellen bei Berührung (Sek.)')+'</label>'+
      '<input type="number" min="0" max="300" step="5" data-ui="nightWake" value="'+esc(wert('nightWake'))+'" placeholder="'+esc(nachtPlatzhalter('nightWake',wakeLeer))+'">'+erbtFeld('nightWake')+'</div>'+
    nachtUhrFelder(ui);
}
// Nacht-Uhr (Vorgaben -> Nacht und Ansicht -> Verhalten): nachts statt der Uhr-Seite
// nur die Uhrzeit, gedimmt auf Schwarz, mit den Symbolen der Gesten-Spalten. Leer
// = Vorgabe bzw. Standard (/api/meta nightDefaults = NACHT_STANDARD).
function nachtUhrFelder(ui){
  const vg=((PANELS[cur]||{}).__global), std=(META.nightDefaults||{});
  const leer=vg ? T('Standard ({w})').replace('{w}', wertText('nightClock', std.nightClock))
                : T('Wie Vorgabe');
  const hellLeer=vg ? std.nightClockBright : nachtVorgabe('nightClockBright');
  return '<div class="field" style="max-width:180px"><label class="lbl">'+T('Nacht-Uhr')+'</label>'+
      '<select data-ui-wahl="nightClock"><option value="">'+esc(leer)+'</option>'+
      '<option value="an"'+(ui.nightClock===true?' selected':'')+'>'+T('An')+'</option>'+
      '<option value="aus"'+(ui.nightClock===false?' selected':'')+'>'+T('Aus')+'</option></select>'+erbtFeld('nightClock')+'</div>'+
    '<div class="field" style="max-width:180px"><label class="lbl">'+T('Helligkeit der Nacht-Uhr (%)')+'</label>'+
      '<input type="number" min="5" max="100" step="5" data-ui="nightClockBright" value="'+esc(ui.nightClockBright==null?'':ui.nightClockBright)+
        '" placeholder="'+esc(hellLeer==null?'':String(hellLeer))+'">'+erbtFeld('nightClockBright')+'</div>';
}
// Felder "Display aus nach" und "Auto-Neustart alle" (Vorgaben -> Verhalten und Ansicht ->
// Verhalten). Ein leeres Feld zeigt grau die Vorgabe, ohne sie, was dann gilt.
function displayFelder(ui, dpmsLeer, reloadLeer){
  const wert=k=>(ui[k]==null)?'':ui[k];
  return '<div class="field" style="max-width:180px"><label class="lbl">'+T('Display aus nach (Sek.)')+'</label>'+
      '<input type="number" min="0" max="3600" step="30" data-ui="dpmsOff" value="'+esc(wert('dpmsOff'))+'" placeholder="'+
        esc(gesetzt(dpmsLeer)?String(dpmsLeer):T('Standard'))+'">'+erbtFeld('dpmsOff')+'</div>'+neustartFeld(ui, reloadLeer);
}
// Werte, die seit der Einrichtung neu (Schritt 4 und 4b) am Geraet stehen: "Display aus nach",
// Nacht (Abdunkeln, Aufhellen), Skalierung, Zielkachel; die Nacht-Uhr nur in den Vorgaben.
// Ein aelterer Eintrag in Ansicht oder Vorgaben gilt weiter (Server: Geraet vor Ansicht vor
// Vorgaben), der Reiter nennt ihn mit "Eintrag entfernen".
const ALT_NAMEN={scale:'Skalierung', tileSize:'Zielkachel', dpmsOff:'Display aus nach', nightDim:'Nachts abdunkeln',
  nightWake:'Aufhellen bei Berührung', nightClock:'Nacht-Uhr', nightClockBright:'Helligkeit der Nacht-Uhr'};
function altEintragHtml(p, keys, id){
  const ui=p.ui||{}, da=keys.filter(k=>gesetzt(ui[k])); if(!da.length) return '';
  const w=da.map(k=>T(ALT_NAMEN[k])+' '+wertText(k, ui[k])).join(', ');
  return '<div class="hint" style="padding-top:4px"><span id="'+id+'">'+esc((p.__global
      ? T('Die Vorgaben tragen noch {w} aus einer älteren Fassung; das gilt für Geräte ohne eigenen Wert.')
      : T('Diese Ansicht trägt noch {w} aus einer älteren Fassung; das gilt für Geräte ohne eigenen Wert.')).replace('{w}', w))+
    ' <button type="button" class="minibtn" data-alt-weg="'+esc(keys.join(','))+'" data-alt-span="'+id+'">'+T('Eintrag entfernen')+'</button></span></div>';
}
function altEintragBinden(p){
  document.querySelectorAll('#pconfHost [data-alt-weg]').forEach(b=>b.onclick=()=>{
    p.ui=p.ui||{}; b.dataset.altWeg.split(',').forEach(k=>delete p.ui[k]);
    const s=document.getElementById(b.dataset.altSpan); if(s) s.remove(); markDirty(); erbtZeichnen(); });
}
// Nur "Auto-Neustart alle" (Ansicht -> Verhalten)
function neustartFeld(ui, reloadLeer){
  const wert=k=>(ui[k]==null)?'':ui[k];
  return '<div class="field" style="max-width:180px"><label class="lbl">'+T('Auto-Neustart alle (Std.)')+'</label>'+
      '<input type="number" min="0" max="168" step="1" data-ui="reloadHours" value="'+esc(wert('reloadHours'))+'" placeholder="'+
        esc(gesetzt(reloadLeer)?String(reloadLeer):T('nachts um {h} Uhr').replace('{h}',neuladenStunde()))+'">'+erbtFeld('reloadHours')+'</div>';
}
function autoNeustartHinweis(){
  return T('Auto-Neustart gegen Einfrieren: Leer lädt die Visu jede Nacht um {h} Uhr neu, eine Zahl alle so viele Stunden, 0 nie. Neu geladen wird nur, während die Uhr-Seite steht; ein dunkles Display bleibt dabei dunkel. Linux-Geräte mit Agent starten stattdessen den Browser neu: nach der Zahl hier, ohne Eintrag nach RELOAD_HOURS in ihrer kiosk.conf.').replace('{h}',neuladenStunde());
}
// Vorgabe eines Werts (Vorgaben -> ...), ohne Standard dahinter
function vorgabeWert(k){ return (((PANELS.__global__||{}).ui)||{})[k]; }
// Progressive Disclosure: "Aufhellen bei Beruehrung" nur zeigen, wenn ueberhaupt nachts
// abgedunkelt wird (sonst wirkungslos); ein leeres Feld zaehlt mit dem Wert, der dann gilt.
function aufhellenZeigen(dimLeer){
  const nd=$('[data-ui="nightDim"]'), nw=$('#nightWakeField');
  if(!nd || !nw) return;
  const upd=()=>{ const v=(nd.value==='')?Number(dimLeer||0):Number(nd.value); nw.style.display=(v>0)?'':'none'; };
  nd.addEventListener('input', upd); upd();
}
// Was in einer Ansicht ohne eigenen Eintrag gilt: die Vorgabe, sonst der Standard des Servers.
function nachtVorgabe(k){
  const g=((PANELS.__global__||{}).ui)||{};
  return (g[k]!=null) ? g[k] : (META.nightDefaults||{})[k];
}
