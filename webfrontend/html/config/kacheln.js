// LoxPanel-Konfigurator, Teil 5 von 11: Kachel-Editor, eigene Auswahl, Kurzfassung.
// Die Teile laden nacheinander aus config.html (script src), alle Funktionen sind global;
// was beim Laden ausgefuehrt wird, darf nur Funktionen frueherer Teile rufen.

// ---- Kachel-Editor ----
function isPickPanel(p){ return (p.tabs||[]).some(isPick); }
// Alle gewaehlten Bausteine ueber alle freien Seiten (dedupliziert). Legacy p.picks
// wird nur beruecksichtigt, solange noch keine pickTabs migriert wurden.
function allPicks(p){ const out=[];
  const add=u=>{ if(out.indexOf(u)<0) out.push(u); };
  if(Array.isArray(p.pickTabs)&&p.pickTabs.length) p.pickTabs.forEach(t=>(t.picks||[]).forEach(add));
  else if(Array.isArray(p.picks)) p.picks.forEach(add);
  return out; }
function panelControls(p){
  // Freie-Auswahl-Panel: „Kacheln gestalten" zeigt genau die gewaehlten Bausteine,
  // nicht alle der Anlage (rooms/cats sind hier leer, sonst kaeme alles durch).
  if(isPickPanel(p)){ const ps=allPicks(p);
    return (META.controls||[]).filter(c=>ps.indexOf(c.uuid)>=0); }
  const rs=p.rooms||[], cs=p.cats||[];
  return (META.controls||[]).filter(c=>
    (rs.length ? rs.includes(c.room) : true) &&
    (cs.length ? cs.includes(c.cat) : true));
}
function renderTileList(){
  const box=$('#tiles'); if(!box) return;
  const p=PANELS[cur]; const q=(($('#tileSearch')||{}).value||'').toLowerCase();
  const list=panelControls(p).filter(c=>c.name.toLowerCase().includes(q)||(c.roomName||'').toLowerCase().includes(q));
  box.innerHTML='';
  if(!list.length){ box.innerHTML='<div class="muted">'+(((p.rooms&&p.rooms.length)||(p.cats&&p.cats.length))?'keine Kacheln im gewählten Raum-/Kategorie-Filter':'nichts gefunden')+'</div>'; return; }
  list.slice(0,400).forEach(c=>{
    const has=p.tiles&&p.tiles[c.uuid];
    const hidden=p.hide&&p.hide.includes(c.uuid);
    const d=document.createElement('div'); d.className='trow'+(c.uuid===tileSel?' active':'')+(hidden?' hidden':'');
    const ic=c.iconUrl?'<span class="tico" style="--u:url(\''+esc(c.iconUrl)+'\')"></span>':'<span class="tico gen"></span>';
    d.innerHTML=ic+'<span class="tnm">'+esc(c.name)+'</span><span class="trm">'+esc(c.roomName||'')+'</span>'+
      (has?'<span class="dot"></span>':'')+
      '<span class="eye'+(hidden?' off':'')+'" title="'+(hidden?'ausgeblendet – wieder einblenden':'sichtbar – ausblenden')+'">'+
        svg(hidden?EYE_OFF:EYE_ON)+'</span>';
    d.onclick=()=>{ tileSel=c.uuid; renderTileList(); renderTileEditor(); };
    d.querySelector('.eye').onclick=(e)=>{ e.stopPropagation(); toggleHide(c.uuid); };
    box.appendChild(d);
  });
  const hc=$('#tileHidden'), n=(p.hide||[]).length;
  if(hc){ hc.innerHTML = n ? ('· '+n+' ausgeblendet <button class="minibtn" id="clrHide">Alle einblenden</button>') : '';
    const ch=$('#clrHide'); if(ch) ch.onclick=clearHide; }
}
const EYE_ON='<path d="M1 12s4-7 11-7 11 7 11 7-4 7-11 7-11-7-11-7Z"/><circle cx="12" cy="12" r="3"/>';
const EYE_OFF='<path d="m3 3 18 18"/><path d="M10.6 10.6a2 2 0 0 0 2.8 2.8"/><path d="M6.7 6.7C3.9 8.3 2 11 1 12c1.7 2.6 5.5 7 11 7 1.7 0 3.2-.4 4.6-1"/><path d="M9.9 5.2A10 10 0 0 1 12 5c5.5 0 9.3 4.4 11 7-.6 1-1.7 2.4-3.2 3.6"/>';
function toggleHide(uuid){ const p=PANELS[cur]; p.hide=p.hide||[];
  const i=p.hide.indexOf(uuid); if(i>-1) p.hide.splice(i,1); else p.hide.push(uuid);
  if(!p.hide.length) delete p.hide; markDirty(); renderTileList(); }
function clearHide(){ const p=PANELS[cur]; if(p.hide){ delete p.hide; markDirty(); renderTileList(); } }

// ---- Eigene Auswahl (Tab "auswahl") ----
// Die Liste ist BEWUSST UNGEFILTERT (kein panelControls()): der Sinn der Seite
// ist, ueber den Raum-/Kategoriefilter des Panels hinauszugreifen. Waere sie
// gefiltert, kaeme man nie an die Bausteine, fuer die man sie anlegt.
// Reihenfolge = Klickreihenfolge, wie bei der Tab-Leiste (toggleTab).
// Bis zu 4 freie Seiten je Panel: p.pickTabs = [{name, picks}]. Tabs heissen
// auswahl, auswahl2..auswahl4 (siehe _pick_index in webvisu.py). Ein altes
// picks/pickName wird beim ersten Schreiben zur ersten Seite migriert.
let curPickIdx=0;
function isPick(t){ if(t===PICK_TAB) return true; if(typeof t==='string' && t.indexOf(PICK_TAB)===0){ const s=t.slice(PICK_TAB.length); return /^[2-4]$/.test(s); } return false; }
function pickKey(i){ return i===0?PICK_TAB:PICK_TAB+(i+1); }
// Kennung einer freien Seite -> ihr Index (auswahl -> 0, auswahl3 -> 2), sonst -1
function pickIdx(k){ return !isPick(k) ? -1 : (k===PICK_TAB ? 0 : parseInt(k.slice(PICK_TAB.length),10)-1); }
// Fallen freie Seiten weg oder ruecken nach, haengt an ihrer Kennung (auswahl, auswahl2 ...)
// noch mehr: der Eintrag in der Leiste, das Widget (ui.panes) und die Werteleiste (ui.valueBar).
// neu(i) = neuer Index der Seite i, -1 = sie ist weg. -> Funktion alte Kennung -> neue ('' = weg);
// andere Kennungen bleiben.
function pickKennungNeu(neu){ return k=>{ const i=pickIdx(k); if(i<0) return k; const j=neu(i); return j<0 ? '' : pickKey(j); }; }
function pickNachLoeschen(weg){ return pickKennungNeu(i=>i===weg ? -1 : (i>weg ? i-1 : i)); }
function panesUmbenennen(panes, f){ const ps={}; Object.entries(panes||{}).forEach(([k,v])=>{ const z=f(k); if(z && !(z in ps)) ps[z]=v; }); return ps; }
// Leiste, Widgets und Werteleiste eines Profils auf die neuen Kennungen bringen
function pickBezuegeNeu(p, f){
  if(Array.isArray(p.tabs)) p.tabs=p.tabs.map(f).filter(Boolean);   // auch die klassische Leiste mit einzelnen auswahlN
  const u=p.ui; if(!u) return;
  if(u.panes && typeof u.panes==='object'){ const ps=panesUmbenennen(u.panes, f); if(Object.keys(ps).length) u.panes=ps; else delete u.panes; }
  if(Array.isArray(u.valueBar)){ const vb=u.valueBar.map(f).filter(Boolean); if(vb.length) u.valueBar=vb; else delete u.valueBar; }
}
// LESEN: legt nichts an (siehe alter Kommentar - kein Zuruecksetzen entfernter Keys).
function pickList(p){ const t=p.pickTabs;
  if(Array.isArray(t)&&t[curPickIdx]) return t[curPickIdx].picks||[];
  return curPickIdx===0 ? (p.picks||[]) : []; }
function pickNameOf(p){ const t=p.pickTabs;
  if(Array.isArray(t)&&t[curPickIdx]) return t[curPickIdx].name||'';
  return curPickIdx===0 ? (p.pickName||'') : ''; }
function pick0Name(p){ const t=p.pickTabs; return String((Array.isArray(t)&&t[0]?t[0].name:p.pickName)||'').trim(); }
// SCHREIBEN: migriert auf die kanonische pickTabs-Form.
function ensurePickTabs(p){
  if(!Array.isArray(p.pickTabs)||!p.pickTabs.length){
    p.pickTabs=[{name:(p.pickName||''), picks:(p.picks||[]).slice()}];
    delete p.picks; delete p.pickName;
  }
  if(p.pickTabs.length>4) p.pickTabs=p.pickTabs.slice(0,4);
  return p.pickTabs;
}
function curPT(p){ const t=ensurePickTabs(p); if(curPickIdx>=t.length) curPickIdx=t.length-1; if(curPickIdx<0) curPickIdx=0; return t[curPickIdx]; }
function pickSyncTabsMode(p){ if(tabMode(p)==='pick') p.tabs=ensurePickTabs(p).map((_,i)=>pickKey(i)); }
// vorgabe: Felder der neuen Seite (Hausuebersicht: Name und Inhalt)
function pickAddTab(p,vorgabe){ const t=ensurePickTabs(p); if(t.length>=4) return; t.push(Object.assign({name:'',picks:[]}, vorgabe||{})); curPickIdx=t.length-1; pickSyncTabsMode(p); markDirty(); renderPick(p); renderChips(p); }
function pickDelTab(p,i){ const t=ensurePickTabs(p); if(t.length<=1) return;
  t.splice(i,1); pickBezuegeNeu(p, pickNachLoeschen(i));
  if(curPickIdx>i || curPickIdx>=t.length) curPickIdx=Math.max(0, curPickIdx-1);   // dieselbe Seite bleibt gewaehlt
  pickSyncTabsMode(p); markDirty(); renderPick(p); renderChips(p); renderPanes(p); }
function icoUrl(ic){ return ic ? (ic.charAt(0)==='/' ? ic : '/icon?p='+encodeURIComponent(ic)) : ''; }
function pickTabBar(p){
  const t=ensurePickTabs(p);
  return '<div class="picktabbar">'+t.map((x,i)=>{
    const ic=x.icon?'<span class="loxi" style="--u:url(\''+esc(icoUrl(x.icon))+'\')"></span>':'';
    return '<button class="ptb'+(i===curPickIdx?' on':'')+'" data-pti="'+i+'">'+ic+
      esc((x.name||'').trim()||(T('Seite')+' '+(i+1)))+(t.length>1?'<span class="ptx" data-ptdel="'+i+'">✕</span>':'')+'</button>';
  }).join('')+
    (t.length<4?'<button class="ptadd" id="ptAdd" title="'+T('Seite hinzufügen')+'">＋</button>':'')+'</div>';
}
// Icon-Auswahl einer freien Seite: volle Loxone-Bibliothek (referenzierte + loxlib),
// als fertige URL gespeichert. Suche filtert clientseitig (DOM, ohne Neurender).
function icoBtn(url,cur,title){ return '<button class="pgi'+(cur===url?' on':'')+'" data-pic="'+esc(url)+'" data-in="'+esc((title||'').toLowerCase())+'" title="'+esc(title)+'"><span class="loxi" style="--u:url(\''+esc(url)+'\')"></span></button>'; }
function icoGridBody(cur){
  var g='<button class="pgi none'+(cur?'':' on')+'" data-pic="" data-in="">'+T('kein')+'</button>';
  (((META.icons||{}).loxone)||[]).forEach(function(pth){ g+=icoBtn('/icon?p='+encodeURIComponent(pth),cur,pth); });
  (LOXLIB||[]).forEach(function(n){ g+=icoBtn('/loxlib?n='+encodeURIComponent(n),cur,n.replace(/\.svg$/i,'')); });
  return g;
}
// Suche in einer Icon-Bibliothek (root: das Element um Suchfeld und Raster; ohne
// root alle). Filtert im DOM, ohne Neuzeichnen.
function pickIcoFilter(v, root){ v=(v||'').trim().toLowerCase(); (root||document).querySelectorAll('.picogrid .pgi[data-in]').forEach(function(b){ if(b.classList.contains('none')) return; b.hidden = !!v && (b.getAttribute('data-in')||'').indexOf(v)<0; }); }

// Zu welchem Panel curPickIdx gehoert: beim Panelwechsel beginnt die Rubrik
// wieder bei der ersten Seite, ohne dass renderEditor() (das auch aus anderen
// Gruenden laeuft) sie zuruecksetzt.
let pickFor=null;

// Raeume der Auswahl in derselben Reihenfolge wie der Server sie gruppiert:
// erstes Vorkommen in picks. Ausgeblendete Bausteine zaehlen nicht mit, weil
// _view_tab() sie per _shown() schon vorher aussortiert - sonst verspraeche
// die Vorschau Sprungmarken, die am Panel gar nicht auftauchen.
function pickRooms(p){
  const out=[];
  pickSichtbar(p).forEach(u=>{
    const c=(META.controls||[]).find(x=>x.uuid===u);
    if(c && c.room && out.indexOf(c.room)<0) out.push(c.room);
  });
  return out;
}
function roomName(uuid){ const r=(META.rooms||[]).find(x=>x.uuid===uuid); return r?r.name:'?'; }

// Auf diesem Panel ausgeblendete Bausteine. _view_tab() wirft sie per _shown()
// AUS DER AUSWAHL, bevor es nach Raum gruppiert - sie bestimmen am Panel also
// weder die Reihenfolge der Raeume noch die Nummern.
function pickAus(p,uuid){ return !!(p.hide && p.hide.indexOf(uuid)>-1); }
function pickSichtbar(p){ return pickList(p).filter(u=>!pickAus(p,u)); }
// Die aktuelle Seite zum Lesen (legt nichts an, wie pickList)
function pickSeite(p){ const t=p.pickTabs;
  if(Array.isArray(t)&&t[curPickIdx]) return t[curPickIdx];
  return curPickIdx===0 ? {picks:p.picks||[]} : {picks:[]}; }

// Die Reihenfolge, in der die Bausteine WIRKLICH am Panel stehen: _view_tab()
// gruppiert nach Raum, Raumreihenfolge = erstes Vorkommen, innerhalb eines
// Raums die Klickreihenfolge. Chips und Nummern hier zeigen genau das - sonst
// versprechen sie eine Ordnung, die das Panel nicht einhaelt.
// Ausgeblendete haengen ungezaehlt hinten an: gewaehlt sind sie ja, nur
// erscheinen sie nicht. Waeren sie eingereiht, verschoebe ein einziger
// ausgeblendeter Baustein jede Nummer dahinter gegenueber dem Panel.
function pickOrder(p){
  const grp=new Map(), aus=[];
  // Ohne Gruppierung (Seiten-Editor, byRoom aus) gilt die Folge der Seite
  if(pickSeite(p).byRoom===false){
    const an=seFolge(pickSeite(p), p.tiles).map(e=>e.id);
    return an.filter(u=>!pickAus(p,u)).concat(an.filter(u=>pickAus(p,u)));
  }
  pickList(p).forEach(u=>{
    if(pickAus(p,u)){ aus.push(u); return; }
    const c=(META.controls||[]).find(x=>x.uuid===u);
    const k=(c&&c.room)?c.room:'\u0000';   // ohne bekannten Raum: ans Ende
    if(!grp.has(k)) grp.set(k,[]);
    grp.get(k).push(u);
  });
  const out=[];
  grp.forEach((us,k)=>{ if(k!=='\u0000') out.push.apply(out,us); });
  if(grp.has('\u0000')) out.push.apply(out,grp.get('\u0000'));
  return out.concat(aus);
}

// Vorschau der unteren Leiste in der Kurzfassung unter Tabs, damit man nicht erst
// speichern und zum Panel laufen muss.
function pickAnchorsInner(p){
  const rs=pickRooms(p);
  if(!pickList(p).length) return '';
  if(pickSeite(p).byRoom===false) return '<p class="hint">'+
    T('Die Seite ist nicht nach Räumen gruppiert (Seiten-Editor) – die untere Leiste bleibt darum ohne Sprungmarken.')+'</p>';
  if(rs.length<2) return '<p class="hint">'+
    T('Alle Bausteine liegen im selben Raum – die untere Leiste bleibt darum ohne Sprungmarken.')+'</p>';
  return '<p class="hint">'+((p.ui&&p.ui.catFilter) ? T('Untere Leiste in der Visu – ein Tipp zeigt nur diese Gruppe:')
                                                    : T('Untere Leiste in der Visu – ein Tipp scrollt zur Gruppe:'))+'</p>'+
    '<div class="anchors">'+rs.slice(0,4).map(ru=>'<span class="chip on">'+esc(roomName(ru))+'</span>').join('')+'</div>'+
    (rs.length>4 ? '<p class="hint" style="padding-top:6px">'+
      T('In die Leiste passen 4 Sprungmarken – die Bausteine der weiteren Räume stehen trotzdem auf der Seite.')+'</p>' : '');
}
function pickAnchorsHtml(p){ return '<div id="pickAnchors">'+pickAnchorsInner(p)+'</div>'; }

// ---- Kurzfassung unter Tabs ----
// Tabs sagt, welche freien Seiten in der Leiste stehen und was sie zeigen. Name,
// Icon, Inhalt und Anordnung stellt der Seiten-Editor ein (seEigenHtml).
// Widget-Wert einer freien Seite (statt Kacheln). Kind/Arg wie eine Tab-Pane.
function wKind(v){ if(!v) return ''; const i=v.indexOf(':'); return i>0?v.slice(0,i):v; }
function wArg(v){ const i=v.indexOf(':'); return i>0?v.slice(i+1):''; }
function pickKurzHtml(p){
  const e=pickSeite(p), w=e.widget||'';
  const ic=e.icon?'<span class="loxi" style="--u:url(\''+esc(icoUrl(e.icon))+'\')"></span>':'';
  const name='<b>'+esc(pickNameOf(p).trim()||(T('Seite')+' '+(curPickIdx+1)))+'</b> ';
  let h;
  if(w) h='<p class="wsum">'+name+T('zeigt das Widget')+' <b>'+esc(T(SE_PANE_NAMEN[wKind(w)]||wKind(w)))+'</b> '+T('über die ganze Fläche.')+'</p>';
  else {
    // Gezaehlt wird, was am Panel ANKOMMT: ausgeblendete Bausteine wirft der
    // Server vorher weg, sie duerfen die Zahl nicht aufblaehen.
    const sel=pickSichtbar(p), rs=pickRooms(p), weg=pickList(p).length-sel.length;
    h='<p class="wsum">'+name+(sel.length
      ? T('zeigt')+' <b>'+sel.length+'</b> '+(sel.length===1?T('Baustein'):T('Bausteine'))+' '+
        T('aus')+' <b>'+rs.length+'</b> '+(rs.length===1?T('Raum'):T('Räumen'))+'.'
      : T('ist noch leer.'))+'</p>'+
      (weg?'<p class="hint">'+weg+' '+(weg===1?T('gewählter Baustein ist in dieser Ansicht ausgeblendet und erscheint nicht.')
                                             :T('gewählte Bausteine sind in dieser Ansicht ausgeblendet und erscheinen nicht.'))+'</p>':'')+
      pickAnchorsHtml(p);
  }
  return '<div class="pick-kurz">'+(ic?'<span class="pick-kurz-ic">'+ic+'</span>':'')+'<div>'+h+
    '<button type="button" class="minibtn" id="pickZumEditor">'+T('Im Seiten-Editor bearbeiten')+'</button>'+
    '<p class="hint">'+T('Name, Icon, Inhalt und Anordnung der Seite stellst du im Seiten-Editor ein.')+'</p></div></div>';
}

// Der Editor haengt daran, ob die Seite ueberhaupt benutzt wird: im
// Auswahl-Modus immer, im klassischen Modus sobald der Chip in der Leiste ist.
// Damit liegen Zusammenstellen und Sichtbarmachen an EINER Stelle.
// Sprungmarken der unteren Leiste: springen (Standard) oder filtern. Nur fuer
// Panels, deren Leiste aus Sprungmarken besteht - eine Raum-Ansicht oder eine
// einzige freie Seite mit Kacheln (wie isRoomPanel() im Panel; eine Widget-Seite
// hat keine Marken). Haengt an renderPick, weil das bei jedem Wechsel der
// Leiste laeuft (Modus, Seiten hinzu/weg, Kacheln/Widget).
function renderBarMode(p){
  const box=$('#tabBarMode'); if(!box) return;
  const t=p.tabs||[];
  const s0=(p.pickTabs||[])[0]||{};
  const anker=t.length===1 && (String(t[0]).indexOf('room:')===0
    || (isPick(t[0]) && !s0.widget && s0.byRoom!==false));
  if(!anker){ box.innerHTML=''; return; }
  const an=!!(p.ui&&p.ui.catFilter);
  box.innerHTML='<div class="field" style="max-width:440px;margin-top:14px"><label class="lbl">'+T('Tipp auf eine Sprungmarke')+'</label>'+
    '<select id="fCatFilter" style="max-width:none">'+
      '<option value=""'+(an?'':' selected')+'>'+T('Springen – zur Gruppe scrollen')+'</option>'+
      '<option value="1"'+(an?' selected':'')+'>'+T('Filtern – nur diese Gruppe zeigen')+'</option>'+
    '</select>'+
    '<div class="hint" style="padding-top:4px">'+T('Springen: die Kacheln der Gruppe leuchten kurz auf. Filtern: ein zweiter Tipp auf dieselbe Marke zeigt wieder alle, ebenso eine Minute ohne Bedienung.')+'</div></div>';
  $('#fCatFilter').onchange=e=>{ p.ui=p.ui||{};
    if(e.target.value) p.ui.catFilter=true; else delete p.ui.catFilter;
    markDirty(); const pa=$('#pickAnchors'); if(pa) pa.innerHTML=pickAnchorsInner(p); };
}
function renderPick(p){
  renderBarMode(p);
  const box=$('#tabPick'); if(!box) return;
  if(pickFor!==cur){ pickFor=cur; curPickIdx=0; }
  if(!(p.tabs||[]).some(isPick)){ box.style.display='none'; box.innerHTML=''; return; }
  box.style.display='';
  box.innerHTML='<div class="grph">'+T('Eigene Auswahl')+'</div>'+(tabMode(p)==='pick' ? pickTabBar(p) : '')+pickKurzHtml(p);
  bindPick(p);
}

function bindPick(p){
  const box=$('#tabPick');
  // Seitenleiste (bis 4 Seiten): wechseln / hinzufuegen / entfernen
  box.querySelectorAll('[data-pti]').forEach(el=>el.onclick=(ev)=>{
    if(ev.target && ev.target.hasAttribute('data-ptdel')) return;
    curPickIdx=+el.dataset.pti; renderPick(p); });
  box.querySelectorAll('[data-ptdel]').forEach(el=>el.onclick=(ev)=>{
    ev.stopPropagation(); pickDelTab(p,+el.dataset.ptdel); });
  { const pa=$('#ptAdd'); if(pa) pa.onclick=()=>pickAddTab(p); }
  { const ze=$('#pickZumEditor'); if(ze) ze.onclick=()=>{ subPconf='seiten'; renderSubtabs(); showSub('seiten'); }; }
  // BEWUSST applyChrome, nicht autoChrome: autoChrome setzt in i18n.js den
  // modulweiten Selektor NEU und haengt bei jedem Aufruf einen weiteren
  // MutationObserver an; applyChrome uebersetzt nur diesen Teilbaum.
  if(window.I18N && I18N.applyChrome) I18N.applyChrome(box);
}

// Nach jeder Aenderung an einer Seite (Seiten-Editor): die Kurzfassung unter
// Tabs und die Buttons der klassischen Leiste, die den Seitennamen tragen
function pickRefresh(){ const p=PANELS[cur]; if(!p || p.__global) return; renderPick(p); renderChips(p); }
