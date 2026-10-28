// LoxPanel-Konfigurator, Teil 3 von 11: Vererbung sichtbar, Skalierung, der Editor je Ansicht.
// Die Teile laden nacheinander aus config.html (script src), alle Funktionen sind global;
// was beim Laden ausgefuehrt wird, darf nur Funktionen frueherer Teile rufen.

// ---- Vererbung sichtbar (Konzept "Konfigurator neu ordnen", Schritt 6) ----
// Kette wie im Server: Geraet vor Ansicht vor Vorgaben vor Standard (effective_scale,
// effective_grid_auto, resolve_profile). Jedes Feld mit Vorgabe oder Geraetewert traegt
// eine Zeile .erbt: leer nennt sie, was gilt und woher; gesetzt bietet sie
// "× zurücksetzen" und nennt die Geraete, die den Wert ueberstimmen. In den Vorgaben
// zaehlt sie die Ansichten, fuer die der Wert gilt. Welche Schluessel eine Vorgabe haben,
// sagt der Server (/api/meta themeKeys = THEME_UI_KEYS).
function erbtFeld(k){ return '<div class="erbt" data-erbt="'+k+'"></div>'; }
function hatVorgabe(k){ return ((META||{}).themeKeys||[]).indexOf(k)>=0; }
function gesetzt(v){ return v!==undefined && v!==null && v!==''; }
// Dieselbe Einstellung heisst am Geraet anders als in der Ansicht
const GERAET_SCHLUESSEL={scale:'scale', tileSize:'tileTarget', dpmsOff:'dpmsOff', nightDim:'nightDim', nightWake:'nightWake'};
// Was ganz ohne Eintrag gilt; null = das Standard-Aussehen (Schrift, Farben, Sprache)
function standardWert(k, ui){
  if(SIZE_KEYS.indexOf(k)>=0) return sizeStd((ui||{}).tileLayout,false,(ui||{}).tileSet)[k];
  if(k==='nightDim'||k==='nightWake') return ((META||{}).nightDefaults||{})[k];
  if(k==='scale') return 'off';
  if(k==='tileSize') return kachelZiel().std;
  if(k==='gesten') return !!(META||{}).gestenStandard;
  if(k==='gestenHinweis') return !!(META||{}).gestenHinweisStandard;
  if(k==='nightClock'||k==='nightClockBright') return ((META||{}).nightDefaults||{})[k];
  return null;
}
function wertText(k, v){
  if(!gesetzt(v)){
    if(k==='baseColor') return T('Standard-Farbschema');
    // Ohne jeden Eintrag: der Agent nach seiner kiosk.conf, die Visu nach dem Server
    if(k==='dpmsOff') return T('Linux-Agent nach seiner kiosk.conf, sonst nie');
    if(k==='reloadHours') return T('nachts um {h} Uhr').replace('{h}',neuladenStunde());
    return T('Standard');
  }
  if(k==='dpmsOff') return Number(v)===0 ? T('nie') : fmtZahl(v)+' s';
  if(k==='reloadHours') return Number(v)===0 ? T('nie') : fmtZahl(v)+' h';
  if(SIZE_KEYS.indexOf(k)>=0) return fmtZahl(v)+' px';
  if(k==='tileSize') return fmtZahl(tileSizeWert(v))+' px';
  if(k==='nightDim') return Number(v)===0 ? T('Aus') : fmtZahl(v)+' %';
  if(k==='nightWake') return fmtZahl(v)+' s';
  if(k==='scale') return scaleName(v);
  if(k==='font') return (FONTS.find(x=>sameFont(x.v,v))||{label:String(v)}).label;
  if(k==='baseColor') return (BASE_COLORS.find(c=>c.v.toLowerCase()===String(v).toLowerCase())||{n:String(v)}).n;
  if(k==='bold') return v ? T('Fett') : T('Normal');
  if(k==='gesten'||k==='gestenHinweis'||k==='nightClock') return v ? T('An') : T('Aus');
  if(k==='nightClockBright') return fmtZahl(v)+' %';
  if(k==='lang') return (LANGS.find(l=>l[0]===v)||[v,String(v)])[1];
  return String(v);
}
function ansichtIds(){ return Object.keys(PANELS).filter(k=>k!=='__global__'); }
function ansichtName(id){ return (PANELS[id]||{}).title||id; }
// Was in einer Ansicht ohne ihren eigenen Eintrag gilt: Vorgabe, sonst Standard
function wasGiltOhneEigenen(k, ui){
  const g=((PANELS.__global__||{}).ui)||{};
  if(hatVorgabe(k) && gesetzt(g[k])) return {v:g[k], quelle:T('aus den Vorgaben')};
  return {v:standardWert(k,ui), quelle:T('Standard')};
}
// Was in einer Ansicht gilt, ihr eigener Eintrag eingeschlossen
function wasGiltInAnsicht(id, k){
  const ui=(PANELS[id]||{}).ui||{};
  if(gesetzt(ui[k])) return {v:ui[k], eigen:true, quelle:(GERAET_SCHLUESSEL[k]
    ? T('aus der Ansicht {a} (älterer Eintrag)') : T('aus der Ansicht {a}')).replace('{a}',ansichtName(id))};   // Werte, die am Geraet stehen
  return wasGiltOhneEigenen(k, ui);
}
// Was fuer ein Geraet gilt (Display aus, Nacht): am Geraet, sonst (ein aelterer Eintrag) der
// Ansicht, die es zeigt, sonst Vorgaben, sonst Standard
function geraetGilt(name, k){
  const d=DEV[name]||{};
  if(gesetzt(d[k])) return {v:d[k], quelle:T('am Gerät'), eigen:true};
  const id=geraetAnsicht(name);
  return id ? wasGiltInAnsicht(id, k) : wasGiltOhneEigenen(k, {});
}
// Welche Ansicht ein Geraet zeigt: gerade verbunden die gemeldete, sonst die ihm
// zugeordnete (devices[name].panel, Schritt 2)
function geraetAnsicht(name){
  const live=(GERAETE_LISTE.find(d=>d.name===name)||{}).profile;
  if(live && PANELS[live]) return live;
  const z=DEVICE_ZUORDNUNG[name]||''; return PANELS[z] ? z : ansichtFuerGeraet(name);
}
// Die Ansicht, die fuer ein Geraet angelegt wurde (device.name, "Geraet einrichten"
// schreibt es) - bis die Abfrage die Zuordnung meldet, auch ungespeichert
function ansichtFuerGeraet(name){ return ansichtIds().find(id=>((PANELS[id].device||{}).name)===name)||''; }
// Geraete, die eine Ansicht zeigen oder in einem Betriebsmodus zeigen wuerden
function geraeteDerAnsicht(id){
  return alleGeraeteNamen().filter(n=>geraetAnsicht(n)===id || ((DEV[n]||{}).modes||[]).some(m=>m[1]===id));
}
// "19 px · aus den Vorgaben"; ganz ohne Eintrag nur "Standard" (nicht doppelt)
function giltText(k, w){ return gesetzt(w.v) ? wertText(k,w.v)+' · '+w.quelle : wertText(k,null); }
function zurueckKnopf(attr, k, dann){
  return '<button type="button" class="minibtn" '+attr+'="'+esc(k)+'" title="'+
    esc(T('Dann gilt: {w}').replace('{w}',dann))+'">'+esc(T('× zurücksetzen'))+'</button>';
}
function erbtZeichnen(){
  const p=PANELS[cur]; if(!p) return;
  const ui=p.ui||{};
  document.querySelectorAll('#pconfHost .erbt[data-erbt]').forEach(el=>{
    const k=el.dataset.erbt, teile=[];
    let knopf='';
    if(p.__global){
      const ids=ansichtIds(), eigene=ids.filter(id=>gesetzt(((PANELS[id]||{}).ui||{})[k]));
      const std=giltText(k,{v:standardWert(k,{}), quelle:T('Standard')});
      if(gesetzt(ui[k])) knopf=zurueckKnopf('data-erbt-zurueck',k,std);
      else teile.push(std);
      teile.push(T('gilt für {n} von {m} Ansichten').replace('{n}',ids.length-eigene.length).replace('{m}',ids.length));
      if(eigene.length) teile.push(T('eigener Wert in {liste}').replace('{liste}',eigene.map(ansichtName).join(', ')));
      const gk=GERAET_SCHLUESSEL[k];   // Geraete mit eigenem Wert (Display aus, Nacht, Skalierung, Zielkachel)
      if(gk) alleGeraeteNamen().forEach(n=>{ const v=(DEV[n]||{})[gk];
        if(gesetzt(v)) teile.push(T('am Gerät {g}: {w}').replace('{g}',n).replace('{w}',wertText(k,v))); });
    } else {
      const w=wasGiltOhneEigenen(k,ui), dann=giltText(k,w);
      if(gesetzt(ui[k])) knopf=zurueckKnopf('data-erbt-zurueck',k,dann);
      else teile.push(dann);
      const gk=GERAET_SCHLUESSEL[k];
      if(gk && (k!=='tileSize' || layoutWert(ui)==='auto'))
        geraeteDerAnsicht(cur).forEach(n=>{ const v=(DEV[n]||{})[gk];
          if(gesetzt(v)) teile.push(T('am Gerät {g}: {w}').replace('{g}',n).replace('{w}',wertText(k,v))); });
    }
    el.innerHTML=knopf+(teile.length?'<span>'+esc(teile.join(' · '))+'</span>':'');
  });
}
// Gerätekarte, Teil "Am Gerät": leer gilt, was die gezeigte Ansicht sagt
function geraetErbtZeichnen(){
  document.querySelectorAll('#geraete .dev').forEach(row=>{
    const name=row.dataset.name, id=geraetAnsicht(name);
    row.querySelectorAll('.erbt[data-gerbt]').forEach(el=>{
      const gk=el.dataset.gerbt, k=(gk==='tileTarget')?'tileSize':'scale';
      const inp=row.querySelector(gk==='tileTarget'?'.dt_ziel':'.ds_scale');
      const eigen=!!inp && (gk==='tileTarget' ? parseInt(inp.value)>0 : inp.value!=='');
      let dann;
      if(!id) dann=T('zeigt gerade keine Ansicht');
      else if(k==='tileSize' && layoutWert((PANELS[id]||{}).ui)!=='auto')
        dann=T('wirkt nur bei Kachel-Layout „Automatisch“ (Ansicht {a})').replace('{a}',ansichtName(id));
      else { const w=wasGiltInAnsicht(id,k);
        dann=giltText(k,w)+(w.eigen?'':' ('+T('Ansicht {a}').replace('{a}',ansichtName(id))+')'); }
      el.innerHTML=eigen ? zurueckKnopf('data-gerbt-zurueck',gk,dann) : '<span>'+esc(dann)+'</span>';
    });
  });
}

function renderCatColors(p){
  const box=$('#catcolors'); if(!box) return;
  const cc=p.catColors||(p.catColors={});
  const MSCOL={}; (META.cats||[]).forEach(c=>{ if(c&&c.color) MSCOL[c.name]=String(c.color); });   // Loxone-Voreinstellung je Kategorie
  // Backend matcht theme.json-Schluessel per Teilstring gegen den Kategorienamen
  // ("Beleuchtung" passt auf "1.2 Beleuchtung"). Die UI muss denselben vorhandenen
  // Schluessel finden und in-place bearbeiten, sonst entstehen Duplikate/„neutral".
  const catKey=nm=>{ const nl=nm.toLowerCase();
    for(const k in cc){ if(!k.startsWith('_') && nl.includes(k.toLowerCase())) return k; }
    return nm; };
  const names=[...new Set((META.cats||[]).map(c=>c.name).filter(Boolean))].sort((a,b)=>a.localeCompare(b,'de'));
  box.innerHTML = names.map(nm=>{
    const v=cc[catKey(nm)];
    const has=(v!=null&&v!=='');
    const amp=(has&&typeof v==='object');
    const single=(typeof v==='string')?v:'';   // Alt-/Einfachfarbe (nur Icon)
    const on=amp?(v.on||'#e2695f'):'#e2695f', off=amp?(v.off||'#52b881'):'#52b881';
    const ms=MSCOL[nm]||'';                     // Miniserver-Farbe (falls vorhanden)
    return '<div class="ccrow">'+
      '<span class="tgl'+(amp?' on':'')+'" data-catt="'+esc(nm)+'" title="Zustands-Ampel an/aus">◐</span>'+
      '<span class="ccnm">'+esc(nm)+'</span>'+
      (amp
        ? '<label class="cclbl">Aktiv</label><input type="color" data-catc="'+esc(nm)+'" data-slot="on" value="'+esc(on)+'">'+
          '<label class="cclbl">OK</label><input type="color" data-catc="'+esc(nm)+'" data-slot="off" value="'+esc(off)+'">'
        : (single
            ? '<label class="cclbl">Farbe</label><input type="color" data-catc="'+esc(nm)+'" data-slot="single" value="'+esc(single)+'">'
            : '<span class="ccmut">neutral</span>'))+
      (ms ? '<button class="minibtn ccms" data-catms="'+esc(nm)+'" title="Miniserver-Voreinstellung übernehmen" style="--sw:'+esc(ms)+'"><span class="ccsw"></span>Standard</button>' : '')+
      (has ? '<button class="minibtn ccreset" data-catr="'+esc(nm)+'" title="Diese Kategorie auf neutral zurücksetzen">neutral</button>' : '')+
    '</div>';
  }).join('');
  box.querySelectorAll('[data-catms]').forEach(b=>b.onclick=()=>{
    const nm=b.dataset.catms; cc[catKey(nm)]=MSCOL[nm]; markDirty(); renderCatColors(p);   // Einfachfarbe = Miniserver-Farbe
  });
  box.querySelectorAll('[data-catt]').forEach(t=>t.onclick=()=>{
    const k=catKey(t.dataset.catt);
    if(cc[k]&&typeof cc[k]==='object') delete cc[k];   // Ampel aus -> neutral
    else cc[k]={on:'#e2695f',off:'#52b881'};           // neutral/Einfachfarbe -> Ampel
    markDirty(); renderCatColors(p);
  });
  box.querySelectorAll('[data-catr]').forEach(b=>b.onclick=()=>{
    delete cc[catKey(b.dataset.catr)]; markDirty(); renderCatColors(p);   // zuverlaessig neutral (String ODER Objekt)
  });
  box.querySelectorAll('input[data-catc]').forEach(inp=>inp.oninput=()=>{
    const k=catKey(inp.dataset.catc), slot=inp.dataset.slot;
    if(slot==='single'){ cc[k]=inp.value; markDirty(); return; }   // Einfachfarbe als String halten
    if(!cc[k]||typeof cc[k]!=='object') cc[k]={on:'#e2695f',off:'#52b881'};
    cc[k][slot]=inp.value; markDirty();
  });
}

function renderEditor(){
  const p=PANELS[cur];
  if(!p){ $('#pconfHost').innerHTML='<div class="empty">Keine Ansicht gewählt.</div>'; $('#phead').innerHTML=''; return; }
  { const ov=$('#openVisu'); if(ov) ov.href = (cur==='default'||cur==='__global__') ? '/' : '/?panel='+encodeURIComponent(cur); }
  if(p.__global){ renderGlobalEditor(p); return; }
  if(!PCONF_TABS.some(t=>t.k===subPconf)) subPconf='inhalt';
  const urlTxt = cur==='default' ? '/  (Standard, ohne Parameter)' : '/?panel='+cur;
  $('#phead').innerHTML =
    '<span class="phlead">'+T('Du bearbeitest')+'</span>'+
    '<h2 id="hTitle">'+esc(p.title||cur)+'</h2>'+
    '<span class="badge phcur">'+esc(cur)+'</span>'+
    '<span class="kurl">'+T('Kiosk-URL:')+' <code>'+esc(urlTxt)+'</code></span>';

  $('#pconfHost').innerHTML =
   '<section class="spane" data-sub="allgemein">'+
   '<div class="card"><h3>Titel</h3><p class="note">Fenstertitel der Ansicht.</p>'+
     '<div class="field"><input type="text" id="fTitle" value="'+esc(p.title||'')+'" placeholder="'+esc(cur)+'"></div>'+
     langField(p.ui)+'</div>'+
   '<div class="card"><h3>'+T('Kennung')+'</h3>'+
     '<p class="note">'+T('Mit dieser Kennung öffnet ein Gerät die Ansicht:')+' <code>'+esc(urlTxt)+'</code></p>'+
     '<div class="actions" id="kennungAktionen"></div></div>'+
   '</section>'+

   '<section class="spane" data-sub="inhalt">'+
   '<div class="card"><h3>'+T('Untere Leiste')+'</h3>'+
     '<div class="segmode" id="tabMode">'+
       '<button type="button" data-mode="room">'+T('Raum-Ansicht')+'</button>'+
       '<button type="button" data-mode="classic">'+T('Klassisch')+'</button>'+
       '<button type="button" data-mode="pick">'+T('Eigene Auswahl')+'</button>'+
     '</div>'+
     '<div id="tabRoom">'+
       '<p class="note">'+T('Ein Raum ist die Startseite — das Gerät wacht direkt in diesem Raum auf (Licht &amp; Beschattung sofort bedienbar), ohne vorher zu wählen. Ideal für kleine 4″-Wandpanels. Die untere Leiste zeigt automatisch die im Raum vorkommenden Kategorien — ein Tipp scrollt zu den passenden Bausteinen oder zeigt nur sie (Einstellung unten).')+'</p>'+
       '<div class="field" style="max-width:340px"><label class="lbl">'+T('Dieser Raum')+'</label>'+
         '<select id="tabRoomSel"></select></div>'+
       '<div class="field" style="max-width:none" id="tabRoomCatWrap"><label class="lbl">'+T('Kategorie-Tabs (unten)')+
           '<button class="minibtn" id="tabRoomAuto" style="margin-left:8px">'+T('Automatisch')+'</button></label>'+
         '<div class="chips" id="tabRoomCats"></div>'+
         '<div class="hint" style="padding-top:4px">'+T('Bis zu 4 Kategorien als untere Tabs. Vorausgewählt sind die ersten im Raum — du kannst sie ändern. „Automatisch" folgt wieder dem Rauminhalt.')+'</div></div></div>'+
     '<div id="tabClassic">'+
       '<p class="note">'+T('Bis zu <b>4 Buttons</b> — die 4 Standard-Tabs, die <b>eigene Auswahl</b> und/oder einzelne Kategorien (gestrichelt) bzw. Räume (gepunktet). <b>Die Reihenfolge des Anklickens ist die Reihenfolge in der Leiste</b> (1., 2., …), der erste ist die Startseite (★). ')+
         '<span id="tabcount"></span></p>'+
       '<div class="chips" id="chips"></div></div>'+
     '<div id="tabPick"></div>'+
     '<div id="tabBarMode"></div>'+
     '</div>'+
   '<div class="card"><h3>Räume</h3>'+
     '<p class="note">'+T('Welche Räume diese Ansicht zeigt. <b>Nichts angehakt = alle Räume.</b>')+'</p>'+
     '<div class="toolbar"><span class="count" id="cntRooms"></span>'+
       '<button class="minibtn" id="clrRooms">Alle abwählen</button></div>'+
     '<div class="grid" id="rooms"></div></div>'+
   '<div class="card"><h3>Kategorien</h3>'+
     '<p class="note">'+T('Welche Kategorien im Tab „Kategorien" erscheinen. <b>Nichts angehakt = alle.</b> Bei gesetzter Raum-Auswahl werden Kategorien zusätzlich auf diese Räume gefiltert.')+'</p>'+
     '<div class="toolbar"><span class="count" id="cntCats"></span>'+
       '<button class="minibtn" id="clrCats">Alle abwählen</button></div>'+
     '<div class="grid" id="cats"></div></div>'+
   '<div class="card"><h3>'+T('Widget, Kopfzeile, Werteleiste')+'</h3>'+
     '<div class="field" style="max-width:none" id="paneField"><label class="lbl">'+T('Widget je Standard-Seite')+'</label>'+
       '<div class="cclist" id="panePerTab"></div>'+
       '<div class="hint" style="padding-top:4px">'+T('Freie Seiten (Eigene Auswahl) stellst du im Seiten-Editor ein.')+' Je Seite ein <b>Widget</b> – quer rechts neben der Visu, hochkant darunter: <b>Audio</b> (Musikzone – Zone daneben wählbar), <b>Kamera</b> (Intercom-Live-Bild – Kamera daneben wählbar, Zugang unter Einstellungen → Intercom), <b>Wetter</b>, <b>Kalender</b>, <b>Energiefluss</b>, <b>Verlauf</b> (Baustein mit Aufzeichnung) oder <b>Werte</b> (frei gewählte Bausteine). <b>Kopfzeile</b> legt stattdessen eine Zeile <b>über</b> die Kacheln: Uhr, Wetter in Kurzform und nach Wahl Werte – nimmt weniger Platz als eine Pane und lässt das Raster ungeteilt. <b>Screen füllen</b> = kein Widget, die Visu weitet sich aus – quer nach rechts (doppelte Spalten), hochkant nach unten (doppelte Zeilen; das Hochformat-Raster 2 × 3 bleibt). „Bildschirm füllen" zoomt alles auf den ganzen Schirm. Wetter/Kalender-Quelle: Einstellungen → Kalender &amp; Wetter. <b>Werte als Leiste</b> nimmt die Anzeige-Bausteine der Seite (Messwerte, Zähler, Texte, Ein/Aus-Anzeigen) aus dem Raster in eine schmale Zeile darüber – das Raster bleibt dem Bedienbaren; bei „Räume" und „Kategorien" gilt es für die Raum- bzw. Kategorie-Seiten darunter. Eine Seite nur aus Werten behält ihre Kacheln.</div></div>'+
   '</div>'+
   '</section>'+

   '<section class="spane" data-sub="seiten"><div class="card se-karte"><h3>'+T('Seiten-Editor')+'</h3>'+
     '<p class="note">'+T('Ordnet die freien Seiten (Eigene Auswahl) so an, wie das gewählte Gerät sie zeigt: Bausteine aus der Liste auf die Fläche ziehen, Kacheln verschieben, Größe 1 × 1, 2 × 1 oder 2 × 2 wählen, ein Widget daneben setzen.')+'</p>'+
     '<div id="seHinweis"></div><div class="se-host" id="seHost"></div>'+
     '<div class="grph" id="sePaneKopf">'+T('Widget, Kopfzeile, Werteleiste dieser Seite')+'</div>'+
     '<div class="cclist" id="sePaneBox"></div></div></section>'+

   '<section class="spane" data-sub="raster"><div class="card"><h3>'+T('Raster')+'</h3>'+
     '<p class="note">'+T('Überschreibt die Vorgaben nur für diese Ansicht. Leer = Vorgabe.')+'</p>'+
     '<div class="grph">'+T('Kachel-Layout')+'</div>'+
     '<div class="sizes">'+
       '<div class="field" style="max-width:220px"><label class="lbl">Kachel-Layout</label>'+
         '<select id="fLayout">'+[['2x2','2 × 2 (4″-Wandpanel)'],['3x2','3 × 2 (Tablet)'],['2x3','2 × 3 (Tablet hoch)'],
             ['3x3','3 × 3 (großes Tablet)'],['auto',T('Automatisch (Tablet)')]]
           .map(o=>'<option value="'+o[0]+'"'+(layoutWert(p.ui)===o[0]?' selected':'')+'>'+o[1]+'</option>').join('')+
         '</select></div>'+
       '<div class="field" style="max-width:220px" id="fFillField"><label class="lbl">Bildschirm füllen</label>'+
         '<select id="fFill">'+
           '<option value=""'+(((p.ui||{}).fill)?'':' selected')+'>Aus (feste Kachelgröße)</option>'+
           '<option value="1"'+(((p.ui||{}).fill)?' selected':'')+'>An (füllt große Screens)</option>'+
         '</select></div>'+
     '</div>'+
     '<div class="hint" style="padding-top:4px">'+T('Kachel-Layout „Automatisch“ (Tablet): Das Gerät rechnet Spalten und Zeilen selbst aus seiner Bildschirmgröße – ein größerer Schirm zeigt mehr Kacheln, nicht größere. Ein Widget belegt ganze Kachelspalten, hochkant ganze Zeilen; die Kacheln bleiben dabei gleich groß. „Bildschirm füllen“ und Skalierung braucht es dann nicht. Was ein Gerät daraus macht, steht unter Geräte.')+'</div>'+
     '<div class="hint" style="padding-top:4px">'+T('Zielkachel und Skalierung stehen auf der Karte des Geräts (Geräte, Zeile Technik): jedes Gerät bekommt seinen Wert, mit Vorschlag aus der gemeldeten Größe.')+'</div>'+
     altEintragHtml(p, ['tileSize','scale'], 'fRasterAlt')+
     '<div class="grph">'+T('Widget (Pane 2)')+'</div>'+
     '<div class="sizes">'+
       '<div class="field" style="max-width:220px"><label class="lbl">Split-Screen</label>'+
         '<select id="fSplit">'+
           '<option value="1"'+(((p.ui||{}).split===false)?'':' selected')+'>An (Tablet – 2 Panes)</option>'+
           '<option value="off"'+(((p.ui||{}).split===false)?' selected':'')+'>Aus (4″-Wandpanel – nur Visu)</option>'+
         '</select>'+
         '<div class="hint" style="padding-top:4px">Bei „Aus" zeigt das Gerät nur die Visu im Kachel-Layout – keine Pane 2, keine Verdopplung. Für 4″-Wandpanels.</div></div>'+
       '<div class="field" style="max-width:320px" id="fPaneColsField"><label class="lbl">'+T('Widget-Breite')+'</label>'+
         '<div class="frow"><input type="range" id="fPaneCols" min="0" max="'+esc(String(paneSpalten().max))+'" step="1" value="'+esc(String(paneColsWert((p.ui||{}).paneCols)))+'">'+
           '<span id="fPaneColsTxt">'+esc(paneColsText((p.ui||{}).paneCols))+'</span></div>'+
         '<div class="hint" style="padding-top:4px">'+T('Wie viele Kachelspalten das Widget rechts neben den Kacheln belegt, hochkant Kachelzeilen darunter – die Kacheln bleiben gleich groß. „Automatisch“ nimmt den Anteil, den das Gerät aus seinem Raster rechnet. Mit fester Breite wachsen wenige Kacheln auch neben dem Widget, es wächst dann mit. Nur im Kachel-Layout „Automatisch“.')+'</div></div>'+
     '</div>'+
     '<div class="grph">'+T('Feinjustierung')+'</div>'+
     '<div class="sizes">'+
       '<div class="field" style="max-width:180px"><label class="lbl">Horiz. Versatz (px)</label>'+
         '<input type="number" min="-40" max="40" step="2" data-ui="nudgeX" value="'+
         (((p.ui||{}).nudgeX==null)?'':(p.ui||{}).nudgeX)+'" placeholder="0"></div>'+
     '</div>'+
   '</div></section>'+

   '<section class="spane" data-sub="aussehen"><div class="card"><h3>'+T('Aussehen')+'</h3>'+
     '<p class="note">'+T('Überschreibt die Vorgaben nur für diese Ansicht. Leer = Vorgabe.')+'</p>'+
     aussehenGruppe(T('Kachel-Set'), kachelSetKarten(p.ui||{})+'<div id="fKsExtra">'+kachelSetExtraHtml(p.ui||{})+'</div>')+
     aussehenGruppe(T('Farbe und Aufbau'), baseField(p.ui||{})+
       '<div class="sizes"><div class="field" style="max-width:none;min-width:280px"><label class="lbl">'+T('Kachel-Aufbau')+'</label>'+
         '<select id="fTileLayout" style="width:100%;max-width:none"'+((p.ui||{}).tileSet?' disabled':'')+'>'+
           '<option value=""'+(((p.ui||{}).tileLayout==='classic')?'':' selected')+'>'+T('Neu (wie die Loxone-App)')+'</option>'+
           '<option value="classic"'+(((p.ui||{}).tileLayout==='classic')?' selected':'')+'>'+T('Klassisch')+'</option>'+
         '</select></div></div>',
       T('Kachel-Aufbau „Neu“: Raum klein oben rechts, der Zustand groß und der Name darunter, Temperaturen groß an Stelle des Symbols, Tasten als Leiste unten. „Klassisch“ ist der bisherige Aufbau. Das Kachel-Layout bleibt in beiden gleich.'),
       null, ' id="fAgFarbe"'+((p.ui||{}).tileSet?' hidden':''))+
     aussehenGruppe(T('Farbe und Aufbau'), '',
       T('Grundfarbe und Kachel-Aufbau kommen aus dem gewählten Set.')+' '+T('Eigene Zustandsfarben und Farben aus „Kacheln gestalten“ gelten weiter.'),
       null, ' id="fAgAusSet"'+((p.ui||{}).tileSet?'':' hidden'))+
     aussehenGruppe(T('Schrift'), schriftFelder(p.ui||{}))+
     aussehenGruppe(T('Hausübersicht'), hausAufbauFeld(p.ui||{}),
       T('Wie die Hausübersicht dieser Ansicht aufgebaut ist. „Status zuerst“: oben, was gerade an ist, mit Aus-Taste. „Räume direkt“: jede Raumkarte schaltet Licht, Musik und Co. mit runden Tasten. „Spalte links“: Uhr, Energie, „Auf einen Blick“ und die Schnellaktionen in einer Spalte links, für breite Schirme; wo sie nicht passt (hochkant, schmal), zeigt das Gerät „Status zuerst“.'))+
     groessenGruppe(p.ui||{}, sizeStd((p.ui||{}).tileLayout,true,(p.ui||{}).tileSet),
       T('Ein leeres Feld übernimmt die Vorgabe, sonst den Standard des Kachel-Aufbaus; grau steht, was dann gilt.'))+
   '</div>'+
   '<div class="card"><h3>Kacheln gestalten</h3>'+
     '<p class="note">'+T('Klicke eine Kachel an und ändere <b>Farben, Schrift und Icon nur für diese Kachel</b> (in dieser Ansicht). Farbiger Punkt = schon angepasst. Mit dem <b>Auge</b> rechts blendest du eine Kachel in dieser Ansicht ganz aus. ')+'<span id="tileHidden" class="thidden"></span></p>'+
     '<input type="text" id="tileSearch" placeholder="'+T('Kachel suchen…')+'" style="max-width:280px;margin-bottom:10px">'+
     '<div class="tlist" id="tiles"></div>'+
     '<div id="tileEditor"></div></div>'+
   '<div class="card"><h3>Aktiv-Overlay</h3>'+
     '<p class="note">'+T('Wie eine Kachel im <b>aktiven Zustand</b> hervorgehoben wird (an = Akzent, ok = grün, kritisch = rot): Rahmen, Füllung und Deckkraft. Die <b>Farbe</b> kommt je Zustand aus dem Theme, hier stellst du das <b>Aussehen</b> ein. Darunter der Rahmen der <b>inaktiven</b> Kacheln <b>und der rechten Panes</b> (Pane 2, z. B. Energieflussmonitor, Wetter, Kalender) – Deckkraft und Breite hochdrehen, falls er auf hellen Displays (z. B. Shelly) kaum sichtbar ist. Gilt für diese Ansicht — einzelne Kacheln können unten abweichen.')+'</p>'+
     '<div class="ovwrap">'+
       '<div class="ovprev"><div class="ovtile on" id="ovPrev">An</div>'+
         '<div class="ovtile off" id="ovPrevOff">Aus</div></div>'+
       '<div class="ovctrl">'+overlayFields((p.ui||{}).overlay,'ov_')+
         '<div class="frow"><button class="minibtn" id="ovReset">Auf Standard zurücksetzen</button></div>'+
       '</div></div></div>'+
   '</section>'+

   '<section class="spane" data-sub="verhalten"><div class="card"><h3>'+T('Verhalten')+'</h3>'+
     '<p class="note">'+T('Überschreibt die Vorgaben nur für diese Ansicht. Leer = Vorgabe.')+'</p>'+
     '<div id="svPaneField">'+
       '<div class="grph">'+T('Screensaver (Uhr-Seite)')+'</div>'+
       '<div class="field" style="max-width:none"><label class="lbl">Zweite Fläche (quer rechts, hochkant unten)</label>'+
       '<div id="svPaneBox"></div>'+
       '<div class="hint" style="padding-top:4px">Die Uhr-Startseite hat auf dem Tablet neben bzw. unter der Uhr Platz: im <b>Querformat</b> rechts, <b>hochkant</b> unter Uhr und Wetter. <b>Automatisch</b> zeigt dort die nächsten Termine und, sobald keine anstehen, die Wetter-Details – so bleibt die Fläche nie leer. Als <b>Widget</b> fest wählbar sind <b>Termine</b>, <b>Wetter-Details</b> (Stundenverlauf, Luftfeuchte, Wind, Sonne), <b>Audio</b> (Now Playing), <b>Energiefluss</b>, <b>Kamera</b>, <b>Verlauf</b> oder <b>Werte</b> aus frei gewählten Bausteinen. <b>Nichts</b> rückt Uhr und Wetter auf die volle Breite. Auf dem quadratischen 4″-Wandpanel bleibt es unverändert bei Wetter, Uhr und Terminen. Bedenke bei <b>Kamera</b> und <b>Energiefluss</b>: die Uhr-Seite steht auf einem Wandpanel stundenlang still – ein weitgehend unveränderliches Bild begünstigt Einbrennen. Das Kamerabild läuft nur, solange die Uhr-Seite zu sehen ist.</div></div></div>'+
     '<div class="grph">'+T('Display &amp; Neustart')+'</div>'+
     '<div class="sizes">'+
       neustartFeld(p.ui||{}, vorgabeWert('reloadHours'))+
     '</div>'+
     '<div class="hint" style="padding-top:4px">'+T('„Display aus nach“, Nachts abdunkeln und Aufhellen stehen in den Vorgaben und auf der Karte jedes Geräts (Zeile Display), die Nacht-Uhr in den Vorgaben.')+'</div>'+
     altEintragHtml(p, ['dpmsOff','nightDim','nightWake','nightClock','nightClockBright'], 'fVerhaltenAlt')+
     '<div class="hint" style="padding-top:4px">'+esc(autoNeustartHinweis())+'</div>'+
     '<div class="grph">'+T('Gesicherte Bausteine')+'</div>'+
     '<div class="sizes">'+
       '<div class="field" style="max-width:180px"><label class="lbl">PIN merken (Sek.)</label>'+
         '<input type="number" min="0" max="'+esc(String(pinMerkenCfg().max))+'" step="5" data-ui="pinMerken" value="'+
         (((p.ui||{}).pinMerken==null)?'':(p.ui||{}).pinMerken)+'" placeholder="'+esc(String(pinMerkenCfg().standard))+'"></div>'+
     '</div>'+
     '<div class="hint" style="padding-top:4px">'+T('Nach der richtigen Visu-PIN fragt die Visu bei gesicherten Bausteinen so lange nicht erneut – nur auf derselben Seite. Uhr-Seite, Display aus und Seitenwechsel vergessen die PIN sofort. 0 = jedes Mal fragen.')+'</div>'+
     '<div class="grph">'+T('Gesten')+'</div>'+
     '<div class="sizes">'+
       '<div class="field" style="max-width:240px"><label class="lbl">'+T('Zwei-Finger-Gesten')+'</label>'+
         gestenWahl('fGesten', (p.ui||{}).gesten, T('Wie Vorgabe'))+erbtFeld('gesten')+'</div>'+
       '<div class="field" style="max-width:320px"><label class="lbl">'+T('Raum außerhalb von Raumseiten')+'</label>'+
         '<select id="fGestenRaum">'+gestenRaumOptionen((p.ui||{}).gestenRaum)+'</select></div>'+
       '<div class="field" style="max-width:240px"><label class="lbl">'+T('Hinweis-Symbol')+'</label>'+
         gestenWahl('fHinweis', (p.ui||{}).gestenHinweis, T('Wie Vorgabe'))+erbtFeld('gestenHinweis')+'</div>'+
     '</div>'+
     '<div class="hint" style="padding-top:4px">'+T('Auf einer Raumseite gelten die Gesten diesem Raum. Auf anderen Seiten (Favoriten, Hausübersicht …) gelten sie dem hier gewählten Raum, ohne Auswahl dort gar nicht. Was Doppel- und Dreifachtipp auslösen, steht unter Vorgaben → Verhalten.')+'</div>'+
   '</div></section>';

  // Allgemein: Duplizieren und Loeschen der Ansicht; die Speicherleiste behaelt die Vorschau
  $('#kennungAktionen').innerHTML = '<button class="btn ghost" id="dupBtn">'+T('Duplizieren')+'</button>'+
    ((cur==='default')?'' : '<button class="btn del" id="delBtn">'+T('Ansicht löschen')+'</button>');
  $('#delSlot').innerHTML =
    '<button class="btn ghost" id="vorBtn" title="'+esc(T('Zeigt diese Ansicht mit allen Änderungen in der echten Visu, auch ungespeichert. Das Fenster zieht Änderungen nach.'))+'">'+T('Vorschau')+'</button>'+
    '<button class="btn ghost" id="vorGerBtn" title="'+esc(T('Zeigt diese Ansicht mit allen Änderungen auf dem Gerät (Vorschaugerät im Seiten-Editor, sonst das Gerät, für das sie angelegt wurde) und zieht Änderungen nach. Ohne Änderungen kehrt das Gerät nach 15 Minuten zur vorigen Ansicht zurück.'))+'"></button>';

  // Titel live
  $('#fTitle').oninput=e=>{ p.title=e.target.value; const h=$('#hTitle'); if(h)h.textContent=e.target.value||cur; markDirty(); };
  bindAppearance(p);
  { const fl=$('#fLayout'); if(fl) fl.onchange=e=>{ p.ui=p.ui||{}; const v=e.target.value;
      if(v==='auto'){ p.ui.grid='auto'; delete p.ui.cols; delete p.ui.rows; }
      else { delete p.ui.grid; delete p.ui.tileSize;
        if(v==='3x3'){ p.ui.cols=3; p.ui.rows=3; }
        else if(v==='2x3'){ delete p.ui.cols; p.ui.rows=3; }
        else if(v==='3x2'){ p.ui.cols=3; delete p.ui.rows; }
        else { delete p.ui.cols; delete p.ui.rows; } }   // 2x2
      layoutFelder(p); markDirty(); }; }
  // Widget-Breite in Kachelspalten (Schieberegler); 0 = Automatik, wird nicht gespeichert
  { const fpc=$('#fPaneCols'); if(fpc) fpc.oninput=e=>{ p.ui=p.ui||{};
      const v=parseInt(e.target.value)||0; if(v>0) p.ui.paneCols=v; else delete p.ui.paneCols;
      const t=$('#fPaneColsTxt'); if(t) t.textContent=paneColsText(v); markDirty(); }; }
  layoutFelder(p);
  altEintragBinden(p);
  { const ff=$('#fFill'); if(ff) ff.onchange=e=>{ p.ui=p.ui||{};
      if(e.target.value) p.ui.fill=true; else delete p.ui.fill; markDirty(); }; }
  // Aufbau der Hausuebersicht: der Standard wird nicht gespeichert
  { const fh=$('#fHausAufbau'); if(fh) fh.onchange=e=>{ p.ui=p.ui||{};
      if(e.target.value && e.target.value!==(META&&META.hausAufbauStandard)) p.ui.hausAufbau=e.target.value; else delete p.ui.hausAufbau;
      markDirty(); }; }
  // Kachel-Aufbau: nur "classic" wird gespeichert, der neue ist der Standard
  { const ftl=$('#fTileLayout'); if(ftl) ftl.onchange=e=>{ p.ui=p.ui||{};
      if(e.target.value==='classic') p.ui.tileLayout='classic'; else delete p.ui.tileLayout;
      sizePlatzhalter(sizeStd(p.ui.tileLayout,true,p.ui.tileSet)); markDirty(); }; }
  // Kachel-Set: leer = ohne Set (wird nicht gespeichert), sonst der Name aus /api/meta
  { const host=$('#pconfHost'), ex=$('#fKsExtra');
    const extra=()=>{ if(!ex) return; ex.innerHTML=kachelSetExtraHtml(p.ui||{}); kachelSetExtraBinden(ex, ()=>p.ui, markDirty); };
    host.querySelectorAll('[data-ks-set]').forEach(b=>{ b.onclick=()=>{ p.ui=p.ui||{};
      if(b.dataset.ksSet) p.ui.tileSet=b.dataset.ksSet; else delete p.ui.tileSet;
      kachelSetKartenWahl(host, p.ui.tileSet);
      const mitSet=!!p.ui.tileSet;
      const ftl=$('#fTileLayout'); if(ftl) ftl.disabled=mitSet;   // das Set bringt seinen Aufbau mit
      const fa=$('#fAgFarbe'), fs=$('#fAgAusSet'); if(fa) fa.hidden=mitSet; if(fs) fs.hidden=!mitSet;
      sizePlatzhalter(sizeStd(p.ui.tileLayout,true,p.ui.tileSet));   // leere Felder zeigen die Groessen des Sets
      extra(); markDirty(); }; });
    if(ex) kachelSetExtraBinden(ex, ()=>{ p.ui=p.ui||{}; return p.ui; }, markDirty); }
  { const fs=$('#fSplit'); if(fs) fs.onchange=e=>{ p.ui=p.ui||{};
      const off=e.target.value==='off';
      if(off) p.ui.split=false; else delete p.ui.split;
      renderPanes(p);   // ohne Split bleibt nur die Kopfzeile waehlbar
      const sf=$('#svPaneField'); if(sf) sf.style.display=off?'none':'';
      layoutFelder(p);  // Widget-Breite nur mit Widget
      markDirty(); }; }
  { const fg=$('#fGesten'); if(fg) fg.onchange=()=>{ p.ui=p.ui||{};
      if(fg.value==='an') p.ui.gesten=true; else if(fg.value==='aus') p.ui.gesten=false; else delete p.ui.gesten;
      markDirty(); erbtZeichnen(); }; }
  { const fr=$('#fGestenRaum'); if(fr) fr.onchange=()=>{ p.ui=p.ui||{};
      if(fr.value) p.ui.gestenRaum=fr.value; else delete p.ui.gestenRaum; markDirty(); }; }
  { const fh=$('#fHinweis'); if(fh) fh.onchange=()=>{ p.ui=p.ui||{};
      if(fh.value==='an') p.ui.gestenHinweis=true; else if(fh.value==='aus') p.ui.gestenHinweis=false; else delete p.ui.gestenHinweis;
      markDirty(); erbtZeichnen(); }; }

  bindOverlay('ov_', ()=>{ p.ui=p.ui||{}; p.ui.overlay=p.ui.overlay||{}; return p.ui.overlay; },
              ()=>{ pruneOverlay(p.ui); ovPreview('ovPrev',(p.ui||{}).overlay); markDirty(); });
  ovPreview('ovPrev',(p.ui||{}).overlay);
  { const r=$('#ovReset'); if(r) r.onclick=()=>{ if(p.ui) delete p.ui.overlay; renderEditor(); markDirty(); }; }

  renderTabMode(p); renderPanes(p); renderSvPane(p); renderChecklist(p,'rooms'); renderChecklist(p,'cats');
  renderTileList(); renderTileEditor();
  const tsr=$('#tileSearch'); if(tsr) tsr.oninput=()=>renderTileList();
  $('#clrRooms').onclick=()=>{ p.rooms=[]; renderChecklist(p,'rooms'); renderTileList(); markDirty(); };
  $('#clrCats').onclick=()=>{ p.cats=[]; renderChecklist(p,'cats'); renderTileList(); markDirty(); };
  const del=$('#delBtn'); if(del) del.onclick=()=>{ if(confirm(T('Ansicht löschen:')+' '+cur+'\n\n'+T('Gilt sofort, ohne „Speichern“. Andere offene Änderungen bleiben offen.'))) ansichtLoeschen(cur); };
  { const db=$('#dupBtn'); if(db) db.onclick=()=>dupOpen(cur); }
  { const vb=$('#vorBtn'); if(vb) vb.onclick=entwurfOeffnen; }
  { const vg=$('#vorGerBtn'); if(vg){ vg.onclick=vorGerKlick; vorGerKnopf(); } }

  seReiterZeichnen();
  erbtZeichnen();
  renderSubtabs(); showSub(subPconf);
  if(window.I18N) I18N.autoChrome('h2, h3, label.lbl, .btn, .minibtn, .note, .hint, option, .stab');
}

// Zielkachel des automatischen Rasters: Grenzen, Standard, alte Stufen und
// Wachstumsfaktor kommen vom Server (/api/meta kachelZiel, KACHEL_ZIEL* in webvisu.py)
function kachelZiel(){ return (META&&META.kachelZiel)||{stufen:{}}; }
// Wert aus dem Profil als Zahl; eine alte Stufe ("small"/"large") ueber die Tabelle des Servers
function tileSizeWert(v){ if(typeof v==='number') return v; return (v&&kachelZiel().stufen[v])||''; }
function zielkachelHinweis(){ const k=kachelZiel(), st=k.stufen||{};
  return T('Zielkachel: Breite einer Kachel in CSS-Pixeln, aus der das Tablet Spalten und Zeilen rechnet. Leer = Standard')+' '+k.std+
    ' ('+T('die bisherigen Stufen Klein, Mittel und Groß entsprechen')+' '+[st.small,st.medium,st.large].join(', ')+'). '+
    T('Passen alle Kacheln einer Seite auf den Schirm, wachsen sie (ohne Widget daneben oder mit fester Widget-Breite) bis zum')+' '+fmtZahl(k.wachsen)+'-'+T('Fachen')+'. '+
    T('Bliebe bei mehreren Seiten die letzte mehr als ein Drittel leer, werden sie kleiner, wenn das eine Seite spart, höchstens bis zur Zielkachel geteilt durch')+' '+fmtZahl(k.wachsen)+'. '+
    T('Leer gilt, was die Ansicht aus einer älteren Fassung noch trägt, sonst der Standard.'); }
// Kachel-Layout eines Profils als Wert der Auswahl: "auto" oder Spalten x Zeilen
function layoutWert(ui){ ui=ui||{};
  return ui.grid==='auto' ? 'auto' : (ui.cols==3?'3':'2')+'x'+(ui.rows==3?'3':'2'); }
// Im automatischen Raster rechnet das Panel selbst: die Kachelgroesse zaehlt,
// "Bildschirm fuellen" und Skalierung wirken dann nicht und verschwinden
function layoutFelder(p){ const auto=layoutWert(p.ui)==='auto', split=(p.ui||{}).split!==false;
  [['#fFillField',!auto],['#fPaneColsField',auto&&split]].forEach(f=>{
    const e=$(f[0]); if(e) e.style.display=f[1]?'':'none'; }); }
// Widget-Breite im automatischen Raster: Grenze und Anteil der Automatik vom
// Server (/api/meta paneCols = PANE_SPALTEN_MAX, PANE_ANTEIL)
function paneSpalten(){ return (META&&META.paneCols)||{max:1,anteil:0}; }
function paneColsWert(v){ const n=parseInt(v)||0; return n>0 ? Math.min(n, paneSpalten().max) : 0; }
function paneColsText(v){ const n=paneColsWert(v);
  if(!n) return T('Automatisch')+' ('+T('rund')+' '+Math.round(paneSpalten().anteil*100)+' % '+T('der Spalten')+')';
  return n+' '+(n===1?T('Kachelspalte'):T('Kachelspalten')); }
// std: was bei leerem Feld gilt, grau im Feld (sizeStd)
function sizeField(label,key,ui,std){
  const v=(ui||{})[key], ph=(std||{})[key];
  return '<div class="field"><label class="lbl">'+label+'</label>'+
    '<input type="number" min="8" max="80" data-ui="'+key+'" value="'+(v==null?'':v)+'" placeholder="'+(ph==null?'—':esc(String(ph)))+'">'+erbtFeld(key)+'</div>';
}
// Groessen, die bei leerem Feld gelten: der Standard des Kachel-Aufbaus vom
// Server (/api/meta sizeDefaults), fuer ein Panel davor die globale Einstellung
const SIZE_KEYS=['iconSize','nameSize','subSize','roomSize','bigSize'];
// Auto-Neustart ohne Eintrag: Die Visu laedt jede Nacht um diese Stunde neu,
// sie kommt vom Server (/api/meta reloadAt = NEULADEN_STUNDE).
function neuladenStunde(){ return (META||{}).reloadAt; }
// PIN merken: Standard und Grenze kommen vom Server (/api/meta pinMerken =
// PIN_MERKEN_STANDARD/PIN_MERKEN_MAX).
function pinMerkenCfg(){ return (META||{}).pinMerken||{standard:'',max:''}; }
function sizeStd(layout,mitGlobal,tileSet){
  // ein Kachel-Set bringt seinen (neuen) Aufbau und eigene Standardgroessen mit (/api/meta)
  const ks=kachelSetMeta(tileSet);
  const std=Object.assign({},((META||{}).sizeDefaults||{})[(layout==='classic'&&!ks)?'classic':'neu'], (ks&&ks.groessen)||{});
  const g=mitGlobal?(((PANELS.__global__||{}).ui)||{}):{};
  SIZE_KEYS.forEach(k=>{ if(g[k]!=null&&g[k]!=='') std[k]=g[k]; });
  return std;
}
// Nach einem Wechsel des Kachel-Aufbaus: leere Felder zeigen den neuen Standard
function sizePlatzhalter(std){
  SIZE_KEYS.forEach(k=>{ const i=document.querySelector('#pconfHost input[data-ui="'+k+'"]');
    if(i&&std[k]!=null) i.placeholder=String(std[k]); });
}
const LANGS=[['','Standard (Deutsch)'],['de','Deutsch'],['en','English'],['fr','Français'],['it','Italiano'],['es','Español'],['nl','Nederlands']];
function langField(ui){
  const cur=(ui||{}).lang||'';
  return '<div class="field" style="max-width:220px"><label class="lbl">Sprache</label>'+
    '<select id="fLang">'+LANGS.map(l=>'<option value="'+l[0]+'"'+(cur===l[0]?' selected':'')+'>'+esc(l[1])+'</option>').join('')+'</select>'+
    '<div class="hint" style="padding-top:4px">Steuert vorerst Datum &amp; Uhr in der Visu. Gerätenamen kommen aus dem Miniserver.</div>'+erbtFeld('lang')+'</div>';
}
function audioZoneOptions(sel){
  return (META.controls||[]).filter(c=>c.type==='AudioZone'||c.type==='AudioZoneV2')
    .map(c=>'<option value="'+esc(c.uuid)+'"'+(sel===c.uuid?' selected':'')+'>'+esc(c.name)+(c.roomName?' ('+esc(c.roomName)+')':'')+'</option>').join('');
}
function firstAudioZone(){
  const z=(META.controls||[]).find(c=>c.type==='AudioZone'||c.type==='AudioZoneV2');
  return z?z.uuid:'';
}
function energyControlOptions(sel){
  return (META.controls||[]).filter(c=>c.type==='EFM'||c.type==='EnergyManager2')
    .map(c=>'<option value="'+esc(c.uuid)+'"'+(sel===c.uuid?' selected':'')+'>'+esc(c.name)+(c.roomName?' ('+esc(c.roomName)+')':'')+'</option>').join('');
}
function statControls(){
  return (META.controls||[]).filter(c=>c.stat)
    .sort((a,b)=>(a.roomName||'').localeCompare(b.roomName||'','de')||a.name.localeCompare(b.name,'de'));
}
function chartControlOptions(sel){
  return statControls()
    .map(c=>'<option value="'+esc(c.uuid)+'"'+(sel===c.uuid?' selected':'')+'>'+esc(c.name)+(c.roomName?' ('+esc(c.roomName)+')':'')+'</option>').join('');
}
function chartAddOptions(){   // Dropdown zum Hinzufuegen: nur Bausteine mit Aufzeichnung
  return '<option value="">'+T('＋ hinzufügen …')+'</option>'+chartControlOptions('');
}
function firstChartControl(){ const z=statControls()[0]; return z?z.uuid:''; }
function firstEnergyControl(){
  // Standard = Energieflussmonitor (EFM, mit Verbraucher-Leistungen). Der
  // Energiemanager (EnergyManager2, nur PV/Netz/Speicher) nur als Rueckfall,
  // wenn kein EFM existiert – sonst ausdruecklich im Dropdown waehlbar.
  const cs=(META.controls||[]);
  const z=cs.find(c=>c.type==='EFM')||cs.find(c=>c.type==='EnergyManager2');
  return z?z.uuid:'';
}
// Kameras = Intercom-Bausteine (Tuerstation/Kamera): Tuersteuerung (Intercom) und
// der Baustein Intercom (IntercomV2). Das Live-Bild kommt ueber /mjpeg?id=<uuid>;
// die Zugangsdaten stehen in Einstellungen -> Intercom.
const INTERCOM_TYPEN=['Intercom','IntercomV2'];
function cameraOptions(sel){
  return (META.controls||[]).filter(c=>INTERCOM_TYPEN.includes(c.type))
    .map(c=>'<option value="'+esc(c.uuid)+'"'+(sel===c.uuid?' selected':'')+'>'+esc(c.name)+(c.roomName?' ('+esc(c.roomName)+')':'')+'</option>').join('');
}
function firstCamera(){
  const z=(META.controls||[]).find(c=>INTERCOM_TYPEN.includes(c.type));
  return z?z.uuid:'';
}

// ---- Skalierung (Profil und Geraet) ----
// Welche Werte zulaessig sind, entscheidet allein der Server (/api/meta
// scaleRange). Die Stufen hier sind nur die Auswahl fuer die Bedienung.
const SCALE_STEPS=[0.8,0.9,1.1,1.25,1.5,1.75,2];
function fmtZahl(v){ try{ return Number(v).toLocaleString((window.I18N&&I18N.lang)||'de',{maximumFractionDigits:2}); }catch(e){ return String(v); } }
// Kette: Global -> Profil -> Geraet. erbe = Text der Option "erbt von oben"
// (Profil: "Wie Vorgabe", Geraet: "Wie in der Ansicht"); ohne erbe (global) ist das
// Fehlen gleich "Aus".
function scaleName(v){
  if(v==='auto') return T('Automatisch');
  if(typeof v==='number') return Math.round(v*100)+' %';
  return T('Aus');
}
function scaleOptions(cur, erbe){
  const r=(META&&META.scaleRange)||[1,1];
  const leer=(cur===undefined||cur===null||cur==='');
  const pct=v=>Math.round(v*100)+' %';
  let h='';
  if(erbe) h+='<option value=""'+(leer?' selected':'')+'>'+esc(erbe)+'</option>';
  h+='<option value="off"'+((cur==='off'||(!erbe&&leer))?' selected':'')+'>'+T('Aus (feste Größe)')+'</option>';
  h+='<option value="auto"'+(cur==='auto'?' selected':'')+'>'+T('Automatisch (Bildschirm ausnutzen)')+'</option>';
  SCALE_STEPS.filter(v=>v>=r[0]&&v<=r[1]).forEach(v=>{
    h+='<option value="'+v+'"'+(cur===v?' selected':'')+'>'+T('Fest')+' '+pct(v)+'</option>'; });
  // Ein gespeicherter Faktor ausserhalb der Stufen (z.B. von Hand in
  // panels.json) darf beim Oeffnen nicht still auf "Aus" springen.
  if(typeof cur==='number' && SCALE_STEPS.indexOf(cur)<0)
    h+='<option value="'+cur+'" selected>'+T('Fest')+' '+pct(cur)+'</option>';
  return h;
}
function scaleValue(v){ return (v==='auto'||v==='off'||v==='') ? v : parseFloat(v); }
// Was ein Panel ueber seinen Bildschirm meldet ({t:'screen'}): sichtbare
// Flaeche in CSS-Pixeln und Ausrichtung, die physischen Pixel (Flaeche x
// Pixeldichte) - und was die Visu daraus macht: Faktor und Anteil des
// Bildschirms, den sie nutzt.
// Zielgeraet eines Profils (Punkt 15): fuer welches Geraet es gemacht ist, mit
// der beim Waehlen gemeldeten Groesse. Displays warnt, wenn ein anderes Geraet
// oder eines mit deutlich anderer Groesse (ZIEL_TOLERANZ je Seite, Drehung
// zaehlt nicht) das Profil nutzt.
const ZIEL_TOLERANZ=0.1;
// Geraeteklasse aus der gemeldeten Groesse: das quadratische 4"-Wandpanel
// (480x480, mit Rahmen etwas mehr), ein grosses Display, sonst ein Tablet
function geraeteKlasse(sc){
  if(!sc||!sc.vw||!sc.vh) return T('Gerät');
  if(Math.abs(sc.vw-sc.vh)<=16 && sc.vw<=600) return T('4″-Wandpanel');
  if(Math.min(sc.vw,sc.vh)>=1000 && Math.max(sc.vw,sc.vh)>=1600) return T('Display');
  return T('Tablet');
}
function screenInfo(sc){
  if(!sc||!sc.vw||!sc.vh) return '';
  const lage=sc.vw>sc.vh?T('quer'):(sc.vw<sc.vh?T('hoch'):T('quadratisch'));
  const teile=[sc.vw+'×'+sc.vh+' '+lage];
  if(sc.dpr&&sc.dpr!==1) teile.push(T('physisch')+' '+Math.round(sc.vw*sc.dpr)+'×'+Math.round(sc.vh*sc.dpr));
  const k=sc.k||1;
  if(sc.bw&&sc.bh){
    const anteil=Math.min(100,Math.round(100*sc.bw*sc.bh*k*k/(sc.vw*sc.vh)));
    teile.push((k!==1?(T('Visu')+' '+fmtZahl(k)+'× · '):'')+T('nutzt')+' '+anteil+' %');
  }
  if(sc.rc&&sc.rr) teile.push(T('Raster')+' '+sc.rc+' × '+sc.rr);   // Kachelansicht, auch "Automatisch"
  return teile.join(' · ');
}

// Widget, Kopfzeile und Werteleiste je Seite: die Standard-Seiten der Leiste unter
// Inhalt, die gewaehlte freie Seite im Seiten-Editor - dieselbe Zeile, jede Seite an
// genau einem Ort.
function renderPanes(p){
  paneListe(p, $('#panePerTab'), (p.tabs||[]).filter(t=>!isPick(t)),
    T('Keine Standard-Seite in der Leiste. Freie Seiten stellst du im Seiten-Editor ein.'));
  sePaneZeichnen(p);
}
function sePaneZeichnen(p){
  if(!p || p.__global) return;   // ohne ensurePickTabs: Zeichnen allein aendert die Ansicht nicht
  // Hausuebersicht: Kopf und Spieler hat sie selbst, ein Widget daneben,
  // Kopfzeile oder Werteleiste gibt es fuer sie nicht
  const haus=((p.pickTabs||[])[curPickIdx]||{}).widget==='haus', kopf=$('#sePaneKopf'), box=$('#sePaneBox');
  if(kopf) kopf.hidden=haus;
  if(haus){ if(box) box.innerHTML=''; return; }
  // die Werte der Kopfzeile waehlt der Seiten-Editor auf seiner Flaeche, hier nicht noch einmal
  paneListe(p, box, [pickKey(curPickIdx)], '', ()=>seReiterZeichnen(), {kopfWerte:false});
}
// Name einer Seite der Leiste: Standard-Seite aus META.tabs, freie Seite ihr eigener
function seitenName(p, tk){
  if(isPick(tk)){ const i=tk===PICK_TAB?0:(parseInt(tk.slice(PICK_TAB.length))||1)-1, t=(p.pickTabs||[])[i]||{};
    return (t.name||'').trim() || (T('Seite')+' '+(i+1)); }
  const meta=(META.tabs||[]).find(t=>t.tab===tk); return meta?meta.label:tk;
}
// nachher: nach jeder Aenderung (Seiten-Editor: Flaeche neu zeichnen);
// opt.kopfWerte:false laesst die Werte-Auswahl der Kopfzeile weg
function paneListe(p, box, tabs, leer, nachher, opt={}){
  if(!box) return;
  // Split "Aus" (4"-Panel): keine Pane daneben, die Kopfzeile ueber den
  // Kacheln aber schon - das Feld bleibt, die Widget-Gruppe ist gesperrt.
  const splitAus=((p.ui||{}).split===false);
  const panes=(p.ui&&p.ui.panes)||{};
  const leiste=(p.ui&&Array.isArray(p.ui.valueBar))?p.ui.valueBar:[];   // Seiten mit Werteleiste
  box.innerHTML = (splitAus?'<div class="ccmut" style="margin-bottom:6px">'+T('Split ist aus: ein Widget daneben gibt es nicht, die Kopfzeile über den Kacheln schon.')+'</div>':'')+tabs.map(tk=>{
    const label=seitenName(p, tk);
    const v=panes[tk]||'';
    const isP=v.indexOf('player:')===0, isE=v.indexOf('energy:')===0, isC=v.indexOf('camera:')===0, isV=v.indexOf('chart:')===0, isS=v.indexOf('status:')===0;
    const isH=(v==='header'||v.indexOf('header:')===0);   // Kopfzeile: Uhr, Wetter, dazu Werte nach Wahl
    const kind=isP?'player':(isE?'energy':(isC?'camera':(isV?'chart':(isS?'status':(isH?'header':v))))), zone=isP?v.slice(7):'', euid=isE?v.slice(7):'';
    // Kamera: "camera:<uuid>|<uuid>,..." - Bild-UUID vor, Werte unter dem Bild hinter dem Strich
    // mehrere Kameras ("camera:a,b|...") = blaetterbare Seiten; die erste waehlt das Feld, weitere die Chips
    const cams=isC?camUuids(v):[], camu=cams[0]||'', cwu=isC?camWerte(v):[];
    const suu=isS?v.slice(7).split(',').filter(Boolean):[];
    const huu=isH?v.slice(7).split(',').filter(Boolean):[];   // "header:" ist 7 Zeichen wie "status:"
    // Verlauf: ein oder mehrere Bausteine; Modus 'page:'/'stack:' optional vorangestellt
    let vArg=isV?v.slice(6):'', vMode='stack';
    { const vm=vArg.match(/^(page|stack):([\s\S]*)$/); if(vm){ vMode=vm[1]; vArg=vm[2]; } }
    const vuu=vArg.split(',').filter(Boolean);
    let row='<div class="ccrow"><span class="ccnm">'+esc(label)+'</span>'+
      '<select data-pane="'+esc(tk)+'">'+
        '<option value=""'+(kind===''?' selected':'')+'>'+T('Kein Widget (Screen füllen)')+'</option>'+
        '<optgroup label="'+T('Widget')+'"'+(splitAus?' disabled':'')+'>'+
          '<option value="weather"'+(kind==='weather'?' selected':'')+'>Wetter</option>'+
          '<option value="calendar"'+(kind==='calendar'?' selected':'')+'>Kalender</option>'+
          '<option value="player"'+(kind==='player'?' selected':'')+'>Audio</option>'+
          '<option value="energy"'+(kind==='energy'?' selected':'')+'>Energiefluss</option>'+
          '<option value="camera"'+(kind==='camera'?' selected':'')+'>Kamera</option>'+
          (statControls().length?'<option value="chart"'+(kind==='chart'?' selected':'')+'>Verlauf</option>':'')+
          '<option value="status"'+(kind==='status'?' selected':'')+'>Werte</option>'+
        '</optgroup>'+
        '<optgroup label="'+T('Über den Kacheln')+'">'+
          '<option value="header"'+(kind==='header'?' selected':'')+'>'+T('Kopfzeile (Uhr, Wetter, Werte)')+'</option>'+
        '</optgroup>'+
      '</select>';
    if(isP) row+='<select data-panez="'+esc(tk)+'">'+audioZoneOptions(zone)+'</select>';
    if(isE) row+='<select data-panee="'+esc(tk)+'">'+energyControlOptions(euid)+'</select>';
    if(isC) row+='<select data-panec="'+esc(tk)+'">'+cameraOptions(camu)+'</select>';
    row+='</div>';
    // Werteleiste: die Anzeige-Bausteine dieser Seite als Zeile ueber dem
    // Raster statt als Kacheln (ui.valueBar nennt die Seiten)
    row+='<div class="ccrow" style="margin:2px 0 0 0"><label class="chk" style="margin:0;font-size:13px">'+
      '<input type="checkbox" data-leiste="'+esc(tk)+'"'+(leiste.indexOf(tk)>-1?' checked':'')+'> '+
      T('Werte als Leiste über den Kacheln')+'</label></div>';
    if(isC){   // weitere Kameras: blaetterbare Seiten mit Punkten, gestreamt wird nur die sichtbare
      const frei=(META.controls||[]).filter(c=>INTERCOM_TYPEN.includes(c.type) && cams.indexOf(c.uuid)<0);
      row+='<div class="ccrow" style="margin:4px 0 0 0;flex-wrap:wrap"><span class="ccnm">'+T('Weitere Kameras')+'</span>'+
        (frei.length ? '<select class="pcams-add" data-pk="'+esc(tk)+'"><option value="">'+T('＋ hinzufügen …')+'</option>'+
          frei.map(c=>'<option value="'+esc(c.uuid)+'">'+esc(c.name)+(c.roomName?' ('+esc(c.roomName)+')':'')+'</option>').join('')+'</select>' : '')+
        '</div><div class="picked" style="margin:6px 0 2px">'+(cams.length>1
          ? cams.slice(1).map(u=>{ const c=(META.controls||[]).find(x=>x.uuid===u);
              return '<span class="chip on" data-pk="'+esc(tk)+'" data-camx="'+esc(u)+'">'+esc(c?c.name:u)+
                '<span class="rm">'+esc((c&&c.roomName)||'')+'</span><span class="x">×</span></span>'; }).join('')
          : '<span class="ccmut">'+T('Keine – eine Kamera ohne Blättern.')+'</span>')+'</div>';
    }
    if(isC){   // Werte unter dem Kamerabild (Tablet: die Pane ist hoeher als das 4:3-Bild)
      row+='<div class="ccrow" style="margin:4px 0 0 0;flex-wrap:wrap"><span class="ccnm">'+T('Werte unter dem Bild')+'</span>'+
        '<select class="pcam-add" data-pk="'+esc(tk)+'"><option value="">'+T('＋ hinzufügen …')+'</option>'+controlOptions()+'</select>'+
        ((svMax()&&cwu.length>=svMax())?'<span class="ccmut">'+T('Mehr passt nicht auf die Seite.')+'</span>':'')+'</div>'+
        '<div class="picked" style="margin:6px 0 2px">'+(cwu.length
          ? cwu.map(u=>{ const c=(META.controls||[]).find(x=>x.uuid===u);
              return '<span class="chip on" data-pk="'+esc(tk)+'" data-cwu="'+esc(u)+'">'+esc(c?c.name:u)+
                '<span class="rm">'+esc((c&&c.roomName)||'')+'</span><span class="x">×</span></span>'; }).join('')
          : '<span class="ccmut">'+T('Keine – das Bild steht allein.')+'</span>')+'</div>';
    }
    if(isS){   // Werte = mehrere Bausteine, wie auf der Uhr-Seite
      row+='<div class="ccrow" style="margin:4px 0 0 0;flex-wrap:wrap"><span class="ccnm">'+T('Bausteine')+'</span>'+
        '<select class="pstat-add" data-pk="'+esc(tk)+'"><option value="">'+T('＋ hinzufügen …')+'</option>'+controlOptions()+'</select>'+
        ((svMax()&&suu.length>=svMax())?'<span class="ccmut">'+T('Mehr passt nicht auf die Seite.')+'</span>':'')+'</div>'+
        '<div class="picked" style="margin:6px 0 2px">'+(suu.length
          ? suu.map(u=>{ const c=(META.controls||[]).find(x=>x.uuid===u);
              return '<span class="chip on" data-pk="'+esc(tk)+'" data-su="'+esc(u)+'">'+esc(c?c.name:u)+
                '<span class="rm">'+esc((c&&c.roomName)||'')+'</span><span class="x">×</span></span>'; }).join('')
          : '<span class="none">'+T('Noch nichts gewählt – oben hinzufügen.')+'</span>')+'</div>';
    }
    if(isH && opt.kopfWerte!==false){   // Kopfzeile: Werte nach Wahl, ohne bleibt es bei Uhr und Wetter
      row+='<div class="ccrow" style="margin:4px 0 0 0;flex-wrap:wrap"><span class="ccnm">'+T('Werte')+'</span>'+
        '<select class="pkopf-add" data-pk="'+esc(tk)+'"><option value="">'+T('＋ hinzufügen …')+'</option>'+controlOptions()+'</select>'+
        ((svMax()&&huu.length>=svMax())?'<span class="ccmut">'+T('Mehr passt nicht in die Zeile.')+'</span>':'')+'</div>'+
        '<div class="picked" style="margin:6px 0 2px">'+(huu.length
          ? huu.map(u=>{ const c=(META.controls||[]).find(x=>x.uuid===u);
              return '<span class="chip on" data-pk="'+esc(tk)+'" data-hu="'+esc(u)+'">'+esc(c?c.name:u)+
                '<span class="rm">'+esc((c&&c.roomName)||'')+'</span><span class="x">×</span></span>'; }).join('')
          : '<span class="none">'+T('Ohne Werte zeigt die Kopfzeile Uhr und Wetter.')+'</span>')+'</div>';
    }
    if(isV){   // Verlauf = ein oder mehrere Bausteine; Darstellung stapeln ODER blaettern
      row+='<div class="ccrow" style="margin:4px 0 0 0;flex-wrap:wrap"><span class="ccnm">'+T('Bausteine')+'</span>'+
        '<select class="pchart-add" data-pk="'+esc(tk)+'">'+chartAddOptions()+'</select>'+
        ((svMax()&&vuu.length>=svMax())?'<span class="ccmut">'+T('Mehr passt nicht auf die Seite.')+'</span>':'')+'</div>'+
        '<div class="picked" style="margin:6px 0 2px">'+(vuu.length
          ? vuu.map(u=>{ const c=(META.controls||[]).find(x=>x.uuid===u);
              return '<span class="chip on" data-pk="'+esc(tk)+'" data-cu="'+esc(u)+'">'+esc(c?c.name:u)+
                '<span class="rm">'+esc((c&&c.roomName)||'')+'</span><span class="x">×</span></span>'; }).join('')
          : '<span class="none">'+T('Noch nichts gewählt – oben hinzufügen.')+'</span>')+'</div>'+
        (vuu.length>=2
          ? '<div class="ccrow" style="margin:4px 0 0 0"><span class="ccnm">'+T('Darstellung')+'</span>'+
            '<select class="pchart-mode" data-pk="'+esc(tk)+'">'+
              '<option value="stack"'+(vMode==='stack'?' selected':'')+'>'+T('Gestapelt (scrollen)')+'</option>'+
              '<option value="page"'+(vMode==='page'?' selected':'')+'>'+T('Blättern (Punkte)')+'</option>'+
            '</select></div>'
          : '');
    }
    return row;
  }).join('') || (leer?'<div class="ccmut">'+esc(leer)+'</div>':'');
  const setPane=(tk,val)=>{ p.ui=p.ui||{}; p.ui.panes=p.ui.panes||{};
    if(val) p.ui.panes[tk]=val; else delete p.ui.panes[tk];
    if(!Object.keys(p.ui.panes).length) delete p.ui.panes; markDirty(); if(nachher) nachher(); };
  box.querySelectorAll('select[data-pane]').forEach(s=>s.onchange=()=>{
    const tk=s.dataset.pane, k=s.value;
    if(k==='player'){ const cur=(p.ui&&p.ui.panes&&p.ui.panes[tk])||'';
      const z=cur.indexOf('player:')===0?cur.slice(7):firstAudioZone(); setPane(tk,'player:'+z); }
    else if(k==='energy'){ const cur=(p.ui&&p.ui.panes&&p.ui.panes[tk])||'';
      const u=cur.indexOf('energy:')===0?cur.slice(7):firstEnergyControl(); setPane(tk,'energy:'+u); }
    else if(k==='camera'){ const cur=(p.ui&&p.ui.panes&&p.ui.panes[tk])||'';
      setPane(tk, cur.indexOf('camera:')===0?cur:'camera:'+firstCamera()); }
    else if(k==='chart'){ const cur=(p.ui&&p.ui.panes&&p.ui.panes[tk])||'';
      const u=cur.indexOf('chart:')===0?cur.slice(6):firstChartControl(); setPane(tk,'chart:'+u); }
    else if(k==='status'){ const cur=(p.ui&&p.ui.panes&&p.ui.panes[tk])||'';
      setPane(tk, cur.indexOf('status:')===0?cur:'status:'); }   // Bausteine unten wählen
    else if(k==='header'){ const cur=(p.ui&&p.ui.panes&&p.ui.panes[tk])||'';
      setPane(tk, cur.indexOf('header')===0?cur:'header'); }     // Werte unten nach Wahl
    else setPane(tk,k);
    renderPanes(p);   // Zonen-/Control-/Kamera-/Werte-Auswahl ein-/ausblenden
  });
  box.querySelectorAll('input[data-leiste]').forEach(c=>c.onchange=()=>{ p.ui=p.ui||{};
    const vb=(Array.isArray(p.ui.valueBar)?p.ui.valueBar:[]).filter(t=>t!==c.dataset.leiste);
    if(c.checked) vb.push(c.dataset.leiste);
    if(vb.length) p.ui.valueBar=vb; else delete p.ui.valueBar;
    markDirty(); if(nachher) nachher(); });
  const paneStatUu=tk=>{ const cur=(p.ui&&p.ui.panes&&p.ui.panes[tk])||''; return cur.indexOf('status:')===0?cur.slice(7).split(',').filter(Boolean):[]; };
  box.querySelectorAll('.pstat-add').forEach(s=>s.onchange=()=>{ const tk=s.dataset.pk, u=s.value; s.value='';
    const uu=paneStatUu(tk); if(!u||uu.indexOf(u)>-1||(svMax()&&uu.length>=svMax())) return;
    setPane(tk,'status:'+uu.concat([u]).join(',')); renderPanes(p); });
  box.querySelectorAll('.chip[data-su][data-pk]').forEach(n=>n.onclick=()=>{ const tk=n.dataset.pk;
    const rest=paneStatUu(tk).filter(x=>x!==n.dataset.su);
    setPane(tk, rest.length?('status:'+rest.join(',')):'status:'); renderPanes(p); });
  const paneKopfUu=tk=>{ const cur=(p.ui&&p.ui.panes&&p.ui.panes[tk])||''; return cur.indexOf('header:')===0?cur.slice(7).split(',').filter(Boolean):[]; };
  const kopfWert=uu=>uu.length?('header:'+uu.join(',')):'header';
  box.querySelectorAll('.pkopf-add').forEach(s=>s.onchange=()=>{ const tk=s.dataset.pk, u=s.value; s.value='';
    const uu=paneKopfUu(tk); if(!u||uu.indexOf(u)>-1||(svMax()&&uu.length>=svMax())) return;
    setPane(tk,kopfWert(uu.concat([u]))); renderPanes(p); });
  box.querySelectorAll('.chip[data-hu][data-pk]').forEach(n=>n.onclick=()=>{ const tk=n.dataset.pk;
    setPane(tk, kopfWert(paneKopfUu(tk).filter(x=>x!==n.dataset.hu))); renderPanes(p); });
  // Verlauf-Wert zerlegen: Modus ('stack'|'page') + Bausteine. 'chart:a,b' =
  // stack (Vorgabe), 'chart:page:a,b' = blaettern. Schreiben: Modus nur bei page.
  const paneChartParse=tk=>{ const cur=(p.ui&&p.ui.panes&&p.ui.panes[tk])||'';
    let a=cur.indexOf('chart:')===0?cur.slice(6):'', m='stack';
    const mm=a.match(/^(page|stack):([\s\S]*)$/); if(mm){ m=mm[1]; a=mm[2]; }
    return {mode:m, uu:a.split(',').filter(Boolean)}; };
  const chartVal=(uu,mode)=> 'chart:'+(mode==='page'?'page:':'')+uu.join(',');
  box.querySelectorAll('.pchart-add').forEach(s=>s.onchange=()=>{ const tk=s.dataset.pk, u=s.value; s.value='';
    const cp=paneChartParse(tk); if(!u||cp.uu.indexOf(u)>-1||(svMax()&&cp.uu.length>=svMax())) return;
    setPane(tk, chartVal(cp.uu.concat([u]), cp.mode)); renderPanes(p); });
  box.querySelectorAll('.chip[data-cu][data-pk]').forEach(n=>n.onclick=()=>{ const tk=n.dataset.pk, cp=paneChartParse(tk);
    const rest=cp.uu.filter(x=>x!==n.dataset.cu);
    setPane(tk, rest.length?chartVal(rest,cp.mode):'chart:'); renderPanes(p); });
  box.querySelectorAll('.pchart-mode').forEach(s=>s.onchange=()=>{ const tk=s.dataset.pk, cp=paneChartParse(tk);
    setPane(tk, chartVal(cp.uu, s.value)); renderPanes(p); });
  box.querySelectorAll('select[data-panez]').forEach(s=>s.onchange=()=>{
    setPane(s.dataset.panez,'player:'+s.value);
  });
  box.querySelectorAll('select[data-panee]').forEach(s=>s.onchange=()=>{
    setPane(s.dataset.panee,'energy:'+s.value);
  });
  box.querySelectorAll('select[data-panec]').forEach(s=>s.onchange=()=>{   // erste Kamera wechseln, weitere und Werte behalten
    const tk=s.dataset.panec, cur=(p.ui&&p.ui.panes&&p.ui.panes[tk])||'';
    const rest=camUuids(cur).slice(1).filter(x=>x!==s.value);
    setPane(tk, camPane([s.value].concat(rest).join(','), camWerte(cur)));
    renderPanes(p);
  });
  box.querySelectorAll('.pcams-add').forEach(s=>s.onchange=()=>{ const tk=s.dataset.pk, u=s.value; s.value='';
    const cur=(p.ui&&p.ui.panes&&p.ui.panes[tk])||'', cc=camUuids(cur);
    if(!u||cc.indexOf(u)>-1) return;
    setPane(tk, camPane(cc.concat([u]).join(','), camWerte(cur))); renderPanes(p); });
  box.querySelectorAll('.chip[data-camx][data-pk]').forEach(n=>n.onclick=()=>{ const tk=n.dataset.pk;
    const cur=(p.ui&&p.ui.panes&&p.ui.panes[tk])||'';
    setPane(tk, camPane(camUuids(cur).filter(x=>x!==n.dataset.camx).join(','), camWerte(cur))); renderPanes(p); });
  box.querySelectorAll('.pcam-add').forEach(s=>s.onchange=()=>{ const tk=s.dataset.pk, u=s.value; s.value='';
    const cur=(p.ui&&p.ui.panes&&p.ui.panes[tk])||'', uu=camWerte(cur);
    if(!u||uu.indexOf(u)>-1||(svMax()&&uu.length>=svMax())) return;
    setPane(tk, camPane(camUuid(cur), uu.concat([u]))); renderPanes(p); });
  box.querySelectorAll('.chip[data-cwu][data-pk]').forEach(n=>n.onclick=()=>{ const tk=n.dataset.pk;
    const cur=(p.ui&&p.ui.panes&&p.ui.panes[tk])||'';
    setPane(tk, camPane(camUuid(cur), camWerte(cur).filter(x=>x!==n.dataset.cwu))); renderPanes(p); });
}
// Kamera-Widget: "camera:<uuid>[,<uuid>...]" oder dahinter "|<uuid>,<uuid>" (Werte unter
// dem Bild). camUuid liefert alle Kameras als Text (fuer camPane), camUuids als Liste.
function camUuid(v){ return (v||'').indexOf('camera:')===0 ? v.slice(7).split('|')[0] : ''; }
function camUuids(v){ return camUuid(v).split(',').filter(Boolean); }
function camWerte(v){ if((v||'').indexOf('camera:')!==0) return []; const r=v.slice(7), i=r.indexOf('|');
  return i<0?[]:r.slice(i+1).split(',').filter(Boolean); }
function camPane(u,uu){ return 'camera:'+(u||'')+(uu&&uu.length?'|'+uu.join(','):''); }
// Screensaver: rechte Spalte. Gleiche Werte-Grammatik wie die Tab-Panes, damit
// es nicht zwei Sprachen fuer dieselbe Sache gibt.
// Drei Arten brauchen ein Ziel: "Werte" mindestens einen Baustein, Energiefluss
// und Kamera je einen passenden. Solange keines da ist, wird NICHTS gespeichert
// — ein halber Wert wie "energy:" wuerde vom Server still verworfen und die
// Auswahl spraenge beim naechsten Laden kommentarlos zurueck. Dass die Auswahl
// trotzdem stehen bleibt (mit Hinweis), merkt sich svWant je Panel und Art.
let svWant='';
function svWantKind(){ return (svWant.indexOf(cur+'|')===0) ? svWant.slice(cur.length+1) : ''; }
// Obergrenze kommt vom Server (/api/meta) - eine Quelle fuer beide Seiten.
function svMax(){ return Number(META && META.svStatusMax) || 0; }
function controlOptions(){
  return (META.controls||[]).map(c=>'<option value="'+esc(c.uuid)+'">'+esc(c.name)+
    (c.roomName?' ('+esc(c.roomName)+')':'')+'</option>').join('');
}
function renderSvPane(p){
  const fld=$('#svPaneField'); if(fld) fld.style.display=((p.ui||{}).split===false)?'none':'';
  const box=$('#svPaneBox'); if(!box) return;
  const v=((p.ui||{}).svPane)||'';
  const i=v.indexOf(':');
  const arg=i>0?v.slice(i+1):'';
  const k=(i>0?v.slice(0,i):v) || svWantKind();
  let h='<div class="ccrow"><span class="ccnm">'+T('Inhalt')+'</span>'+
    '<select id="fSvPane">'+
      '<option value=""'+(k===''?' selected':'')+'>Automatisch (Termine, sonst Wetter)</option>'+
      '<option value="calendar"'+(k==='calendar'?' selected':'')+'>Kalender</option>'+
      '<option value="weather"'+(k==='weather'?' selected':'')+'>Wetter</option>'+
      '<option value="player"'+(k==='player'?' selected':'')+'>Audio</option>'+
      '<option value="energy"'+(k==='energy'?' selected':'')+'>Energiefluss</option>'+
      '<option value="camera"'+(k==='camera'?' selected':'')+'>Kamera</option>'+
      '<option value="chart"'+(k==='chart'?' selected':'')+'>Verlauf</option>'+
      '<option value="status"'+(k==='status'?' selected':'')+'>Werte</option>'+
      '<option value="off"'+(k==='off'?' selected':'')+'>Nichts (Uhr über volle Breite)</option>'+
    '</select>';
  if(k==='player'||k==='energy'||k==='camera'){
    const opt=(k==='player')?audioZoneOptions(arg):(k==='energy')?energyControlOptions(arg):cameraOptions(arg);
    h+= opt ? '<select id="fSvArg">'+opt+'</select>'
      : '<span class="ccmut">'+(k==='player'
          ? T('Keine Musikzone in der Anlage.')
          : k==='energy' ? T('Kein Energieflussmonitor in der Anlage.')
          : T('Kein Intercom-Baustein in der Anlage.'))+'</span>';
  }
  h+='</div>';
  const uu=(k==='status'&&arg)?arg.split(','):[];
  const vuu=(k==='chart'&&arg)?arg.split(','):[];   // Verlauf gestapelt (wie Werte)
  if(k==='status'){
    h+='<div class="ccrow" style="margin-top:8px"><span class="ccnm">'+T('Bausteine')+'</span>'+
       '<select id="fSvAdd"><option value="">'+T('＋ hinzufügen …')+'</option>'+controlOptions()+'</select>'+
       ((svMax()&&uu.length>=svMax())?'<span class="ccmut">'+T('Mehr passt nicht auf die Seite.')+'</span>':'')+'</div>';
    h+='<div class="picked" id="svStatChips" style="margin-top:8px">'+(uu.length
      ? uu.map(u=>{ const c=(META.controls||[]).find(x=>x.uuid===u);
          return '<span class="chip on" data-su="'+esc(u)+'">'+esc(c?c.name:u)+
            '<span class="rm">'+esc((c&&c.roomName)||'')+'</span><span class="x">×</span></span>'; }).join('')
      : '<span class="none">'+T('Noch nichts gewählt – oben hinzufügen.')+'</span>')+'</div>';
  }
  if(k==='chart'){
    h+='<div class="ccrow" style="margin-top:8px"><span class="ccnm">'+T('Bausteine')+'</span>'+
       '<select id="fSvChartAdd">'+chartAddOptions()+'</select>'+
       ((svMax()&&vuu.length>=svMax())?'<span class="ccmut">'+T('Mehr passt nicht auf die Seite.')+'</span>':
         (statControls().length?'':'<span class="ccmut">'+T('Kein Baustein mit Aufzeichnung in der Anlage.')+'</span>'))+'</div>';
    h+='<div class="picked" style="margin-top:8px">'+(vuu.length
      ? vuu.map(u=>{ const c=(META.controls||[]).find(x=>x.uuid===u);
          return '<span class="chip on" data-cu="'+esc(u)+'">'+esc(c?c.name:u)+
            '<span class="rm">'+esc((c&&c.roomName)||'')+'</span><span class="x">×</span></span>'; }).join('')
      : '<span class="none">'+T('Noch nichts gewählt – oben hinzufügen.')+'</span>')+'</div>';
  }
  box.innerHTML=h;
  const setSv=(val)=>{ p.ui=p.ui||{};
    if(val) p.ui.svPane=val; else delete p.ui.svPane;
    markDirty(); renderSvPane(p); };
  const sel=$('#fSvPane');
  if(sel) sel.onchange=()=>{
    const nk=sel.value;
    // Arten mit Ziel: nur speichern, wenn es das Ziel wirklich gibt. Sonst die
    // Auswahl nur merken (Hinweis erscheint), aber nichts Halbes ablegen.
    let ziel='';
    if(nk==='player') ziel=(k==='player'&&arg)?arg:firstAudioZone();
    else if(nk==='energy') ziel=(k==='energy'&&arg)?arg:firstEnergyControl();
    else if(nk==='camera') ziel=(k==='camera'&&arg)?arg:firstCamera();
    else if(nk==='chart') ziel=(k==='chart'&&arg)?arg:firstChartControl();
    else if(nk==='status') ziel=uu.join(',');
    svWant=(nk==='player'||nk==='energy'||nk==='camera'||nk==='chart'||nk==='status') && !ziel ? cur+'|'+nk : '';
    if(nk==='player'||nk==='energy'||nk==='camera'||nk==='chart'||nk==='status') setSv(ziel?(nk+':'+ziel):'');
    else setSv(nk);
  };
  const sa=$('#fSvArg');
  if(sa) sa.onchange=()=>setSv(k+':'+sa.value);
  const add=$('#fSvAdd');
  if(add) add.onchange=()=>{ const u=add.value; add.value='';
    if(!u || uu.indexOf(u)>-1 || (svMax()&&uu.length>=svMax())) return;
    setSv('status:'+uu.concat([u]).join(',')); };
  box.querySelectorAll('.chip[data-su]').forEach(n=>n.onclick=()=>{
    const rest=uu.filter(x=>x!==n.dataset.su);
    setSv(rest.length?('status:'+rest.join(',')):'');
  });
  const cadd=$('#fSvChartAdd');
  if(cadd) cadd.onchange=()=>{ const u=cadd.value; cadd.value='';
    if(!u || vuu.indexOf(u)>-1 || (svMax()&&vuu.length>=svMax())) return;
    setSv('chart:'+vuu.concat([u]).join(',')); };
  box.querySelectorAll('.chip[data-cu]').forEach(n=>n.onclick=()=>{
    const rest=vuu.filter(x=>x!==n.dataset.cu);
    setSv(rest.length?('chart:'+rest.join(',')):'');
  });
  if(window.I18N && I18N.applyChrome) I18N.applyChrome(box);
}
function renderChips(p){
  const box=$('#chips'); if(!box) return; box.innerHTML='';
  const full = p.tabs.length>=4;
  META.tabs.forEach(t=>{
    const on=p.tabs.includes(t.tab);
    const pos = p.tabs.indexOf(t.tab);          // Platz in der Leiste (0 = Startseite)
    const first = on && pos===firstTabIndex(p);
    const c=document.createElement('div');
    c.className='chip'+(on?' on':'')+(!on&&full?' dis':'')+(t.cat?' cat':'')+(t.room?' room':'');
    // Der Auswahl-Tab traegt den Namen, den die Seite hier bekommen hat. Das
    // Label aus META.tabs ist nur der Rueckfall - /api/meta baut die Tabliste
    // fuer alle Panels zusammen und kennt das einzelne Profil gar nicht.
    const label=(t.pick&&pick0Name(p))?pick0Name(p):t.label;
    c.innerHTML=(t.iconUrl?'<img class="chic" src="'+esc(t.iconUrl)+'">':'')+
      esc(label)+(first?'<span class="star">★ Start</span>'
                   :(on?'<span class="pos">'+(pos+1)+'.</span>':''));
    // renderPick: der Editor haengt daran, ob der Tab in der Leiste steht.
    c.onclick=()=>{ toggleTab(p,t.tab); renderChips(p); renderPanes(p); renderPick(p); markDirty(); };
    box.appendChild(c);
  });
  const tc=$('#tabcount'); if(tc){ tc.textContent=p.tabs.length+'/4 gewählt'+(full?' (voll)':''); tc.className=full?'full':''; }
  document.querySelectorAll('input[data-ui]').forEach(inp=>{
    inp.oninput=()=>{ p.ui=p.ui||{}; const k=inp.dataset.ui;
      if(inp.value==='') delete p.ui[k]; else p.ui[k]=Number(inp.value); markDirty(); };
  });
}
// Tabs-Modus. Drei Bauformen, und der Umschalter wechselt in Wahrheit die
// BEDEUTUNG der unteren Leiste:
//   "Klassisch"      - die Leiste sind bis zu 4 SEITEN (p.tabs).
//   "Raum-Ansicht"     - eine Seite (ein Raum), die Leiste sind SPRUNGMARKEN auf
//                      die Kategorien des Raums.
//   "Eigene Auswahl" - eine Seite (handverlesene Bausteine), die Leiste sind
//                      SPRUNGMARKEN auf die Raeume der Auswahl.
// Der Modus wird aus p.tabs abgeleitet - kein eigener Speicherschluessel, den
// _sanitize_panels() erst freischalten muesste.
function tabMode(p){
  const t=p.tabs||[], eins=(t.length===1);
  if(eins && String(t[0]||'').indexOf('room:')===0) return 'room';
  if(t.length && t.every(isPick)) return 'pick';   // eine oder mehrere freie Seiten
  return 'classic';
}
// Gilt die Leiste als selbst zusammengestellt? Nur dann wird vor dem Verwerfen
// gefragt - die unveraenderte Standardleiste darf kommentarlos weichen, sonst
// steht bei jedem Ausprobieren eine Rueckfrage im Weg.
function tabsEigen(p){
  const t=p.tabs||[], d=defaultTabs();
  return t.length!==d.length || t.some((x,i)=>x!==d[i]);
}
function renderTabMode(p){
  p.tabs = Array.isArray(p.tabs) ? p.tabs : [];
  const rooms = (META.tabs||[]).filter(t=>t.room);
  const mode = tabMode(p), isRoom = (mode==='room');
  const seg=$('#tabMode'), roomBox=$('#tabRoom'), classicBox=$('#tabClassic');
  if(seg) seg.querySelectorAll('button').forEach(b=>{
    b.classList.toggle('on', b.dataset.mode===mode);
    b.onclick=()=>{
      const ziel=b.dataset.mode; if(ziel===mode) return;
      if(ziel==='room' && !rooms.length){ alert(T('Keine Räume verfügbar.')); return; }
      // Der Wechsel ueberschreibt p.tabs. Frueher geschah das stillschweigend;
      // mit drei Modi trifft es einen dreimal so oft.
      if(mode==='classic' && tabsEigen(p) &&
         !confirm(T('Die zusammengestellte Tab-Leiste geht dabei verloren. Fortfahren?'))) return;
      if(ziel==='room') p.tabs=[rooms[0].tab];
      else if(ziel==='pick'){ curPickIdx=0; ensurePickTabs(p); p.tabs=p.pickTabs.map((_,i)=>pickKey(i)); }
      else p.tabs=defaultTabs();
      delete p.roomCats;   // Kategorie-Auswahl galt der alten Raum-Ansicht, wie beim Raumwechsel unten
      markDirty(); renderTabMode(p); renderPanes(p);
    };
  });
  if(roomBox) roomBox.style.display=isRoom?'':'none';
  if(classicBox) classicBox.style.display=(mode==='classic')?'':'none';
  const sel=$('#tabRoomSel');
  if(sel){
    const curRoom=isRoom?p.tabs[0]:'';
    sel.innerHTML=(rooms.length?'':'<option value="">'+T('Keine Räume')+'</option>')+
      rooms.map(r=>'<option value="'+esc(r.tab)+'"'+(r.tab===curRoom?' selected':'')+'>'+esc(r.label)+'</option>').join('');
    // Raumwechsel -> die Kategorie-Auswahl gilt nur fuer den alten Raum, zurueck auf Auto.
    sel.onchange=()=>{ if(sel.value){ p.tabs=[sel.value]; delete p.roomCats; markDirty(); renderTabMode(p); renderPanes(p); } };
  }
  if(isRoom) renderRoomCats(p);
  else if(mode==='classic') renderChips(p);
  renderPick(p);
}
// Kategorien, die es im gewaehlten Raum gibt (Reihenfolge = META.cats = cats_with).
function roomCatList(roomTab){
  const ru=String(roomTab||'').slice(5);
  return (META.cats||[]).filter(cat=>(META.controls||[]).some(c=>c.room===ru && c.cat===cat.uuid));
}
// Auswahl der unteren Kategorie-Tabs in der Raum-Ansicht: die Auto-4 sind vorgewaehlt,
// aenderbar (max 4). Ohne eigene Auswahl bleibt p.roomCats leer = automatisch.
function renderRoomCats(p){
  const box=$('#tabRoomCats'); if(!box) return;
  const cats=roomCatList((p.tabs&&p.tabs[0])||'');
  const auto=cats.slice(0,4).map(c=>c.uuid);
  const isAuto=!(Array.isArray(p.roomCats)&&p.roomCats.length);
  const sel=isAuto?auto:p.roomCats, selSet=new Set(sel), full=sel.length>=4;
  box.innerHTML = cats.length
    ? cats.map(c=>{ const on=selSet.has(c.uuid);
        return '<div class="chip'+(on?' on':'')+(!on&&full?' dis':'')+'" data-rc="'+esc(c.uuid)+'">'+esc(c.name)+'</div>'; }).join('')
    : '<span class="ccmut">'+T('Keine Kategorien im Raum')+'</span>';
  box.querySelectorAll('.chip[data-rc]').forEach(n=>n.onclick=()=>{
    let cur=(Array.isArray(p.roomCats)&&p.roomCats.length)?p.roomCats.slice():auto.slice();
    const id=n.dataset.rc, i=cur.indexOf(id);
    if(i>-1) cur.splice(i,1); else { if(cur.length>=4) return; cur.push(id); }
    if(cur.length) p.roomCats=cur; else delete p.roomCats;
    markDirty(); renderRoomCats(p);
  });
  const a=$('#tabRoomAuto'); if(a){ a.style.visibility=isAuto?'hidden':'visible';
    a.onclick=()=>{ delete p.roomCats; markDirty(); renderRoomCats(p); }; }
}
function defaultTabs(){ return (META.tabs||[]).filter(t=>!t.cat&&!t.room).slice(0,4).map(t=>t.tab); }
function firstTabIndex(p){ return 0; }   // Startseite = erster Tab der Leiste
function toggleTab(p,tab){
  // Die Reihenfolge ist die KLICKREIHENFOLGE - sie bestimmt die Tab-Leiste und
  // damit die Startseite (der erste Tab). Vorher wurde hart nach der Liste
  // sortiert; dabei rutschten Kategorie- und Raum-Tabs immer ans Ende und
  // konnten nie Startseite sein, ausser sie waren der einzige Tab.
  const i=p.tabs.indexOf(tab);
  if(i>-1){ if(p.tabs.length>1) p.tabs.splice(i,1); }
  else { if(p.tabs.length>=4) return; p.tabs.push(tab); }
}

function renderChecklist(p,kind){
  const list=META[kind]||[], sel=p[kind]||[];
  const box=$('#'+kind); if(!box) return; box.innerHTML='';
  list.forEach(o=>{
    const on=sel.includes(o.uuid);
    const d=document.createElement('div');
    d.className='opt'+(on?' on':'');
    d.innerHTML='<span class="box">'+(on?'✓':'')+'</span><span class="nm">'+esc(o.name)+'</span>';
    d.onclick=()=>{ const i=p[kind].indexOf(o.uuid); if(i>-1)p[kind].splice(i,1); else p[kind].push(o.uuid);
      renderChecklist(p,kind); renderTileList(); markDirty(); };
    box.appendChild(d);
  });
  const cnt=$('#'+(kind==='rooms'?'cntRooms':'cntCats'));
  if(cnt) cnt.innerHTML = sel.length? ('<b>'+sel.length+'</b> von '+list.length+' ausgewählt')
                                    : ('<b>alle</b> '+list.length+' sichtbar');
}

function markDirty(){ markieren('ansicht:'+cur); renderList(); entwurfNachziehen(); erbtZeichnen(); }
