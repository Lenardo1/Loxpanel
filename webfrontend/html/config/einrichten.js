// LoxPanel-Konfigurator, Teil 7 von 11: Leer anlegen, Duplizieren, gemeinsame Helfer, Geraet einrichten, Geraet verbinden.
// Die Teile laden nacheinander aus config.html (script src), alle Funktionen sind global;
// was beim Laden ausgefuehrt wird, darf nur Funktionen frueherer Teile rufen.

/* ============================================================
   Leere Ansicht anlegen ("Leer anlegen" in Gerät einrichten): nur die Kennung,
   der Rest im Editor unter Ansichten.
   ============================================================ */
function createBlankPanel(){
  let id=prompt(T('Kennung der neuen Ansicht (klein, ohne Leerzeichen), z. B. wohnzimmer:'));
  if(!id) return; id=id.trim().toLowerCase().replace(/[^a-z0-9-]/g,'');
  if(!id){ alert(T('Ungültige ID.')); return; }
  if(PANELS[id]){ alert('Ansicht „'+id+'" gibt es schon.'); return; }
  PANELS[id]={title:id.charAt(0).toUpperCase()+id.slice(1), tabs:defaultTabs(), rooms:[], cats:[], ui:{}, states:{}, tiles:{}};
  cur=id; tileSel=null; renderList(); setRubric('pconf'); markDirty();
}
/* ============================================================
   Ansicht duplizieren mit Raumtausch (Punkt 14). Kopie eines Profils, in der
   jeder Baustein aus dem Quellraum durch den gleichnamigen (gleicher Typ,
   sonst gleicher Name) aus dem Zielraum ersetzt ist: in Tabs (room:),
   Raum-Liste, hide, freien Seiten, Kachel-Einstellungen, Widgets je Tab,
   Werteleiste und Uhr-Seite. Wer im Zielraum kein Gegenstueck hat, faellt
   weg und wird genannt; Bausteine anderer Raeume bleiben.
   ============================================================ */
// Pane-/Widget-Wert mit getauschten UUIDs: uu(uuid) -> neue UUID oder null (weg).
function paneTausch(v, uu){
  const m=/^([a-z]+):(.*)$/.exec(v||''); if(!m) return v;   // weather, calendar, header, off, ''
  const art=m[1], rest=m[2];
  if(art==='player'||art==='energy'){ const z=uu(rest); return z ? art+':'+z : ''; }
  if(art==='camera'){ const [bild, werte]=rest.split('|'); const b=uu(bild); if(!b) return '';
    const w=(werte||'').split(',').filter(Boolean).map(uu).filter(Boolean);
    return 'camera:'+b+(w.length?('|'+w.join(',')):''); }
  const l=rest.split(',').filter(Boolean).map(uu).filter(Boolean);   // chart, status, header
  if(art==='header') return l.length ? 'header:'+l.join(',') : 'header';
  return l.length ? art+':'+l.join(',') : '';
}
function profilMitRaumtausch(p, von, nach, controls){
  const quelle=controls.filter(c=>c.room===von), ziel=controls.filter(c=>c.room===nach);
  const map=new Map();
  quelle.forEach(c=>{ const z=ziel.find(x=>x.name===c.name && x.type===c.type) || ziel.find(x=>x.name===c.name);
    map.set(c.uuid, z ? z.uuid : null); });
  const fehlend=[];
  const uu=u=>{ if(!map.has(u)) return u;   // anderer Raum: bleibt
    const z=map.get(u); if(z===null){ const c=quelle.find(x=>x.uuid===u); if(c && fehlend.indexOf(c.name)<0) fehlend.push(c.name); }
    return z; };
  // War der Zielraum schon im Profil, erzeugt der Tausch Dubletten (zweimal
  // room:nach, derselbe Baustein zweimal): die zweite faellt weg, die Reihenfolge bleibt.
  const einmal=xs=>xs.filter((x,i)=>xs.indexOf(x)===i);
  const liste=xs=>einmal((xs||[]).map(uu).filter(Boolean));
  const tab=t=> (t==='room:'+von) ? 'room:'+nach : t;
  const n=JSON.parse(JSON.stringify(p));
  n.tabs=einmal((n.tabs||[]).map(tab));
  if(Array.isArray(n.rooms)) n.rooms=einmal(n.rooms.map(r=>r===von?nach:r));
  if(Array.isArray(n.hide)) n.hide=liste(n.hide);
  if(Array.isArray(n.picks)) n.picks=liste(n.picks);
  if(Array.isArray(n.pickTabs)) n.pickTabs.forEach(t=>{ if(t){ t.picks=liste(t.picks); if(t.widget) t.widget=paneTausch(t.widget, uu);
    // Layout aus dem Seiten-Editor: getauscht wie picks, die erste Dublette zaehlt (wie im Server)
    if(Array.isArray(t.layout)){ const da=new Set();
      t.layout=t.layout.map(e=>(e && typeof e.id==='string') ? Object.assign({}, e, {id:uu(e.id)}) : null)
        .filter(e=>e && e.id && !da.has(e.id) && da.add(e.id));
      if(!t.layout.length) delete t.layout; } } });
  if(n.tiles && typeof n.tiles==='object'){ const t={}; Object.entries(n.tiles).forEach(([u,v])=>{ const z=uu(u); if(z) t[z]=v; }); n.tiles=t; }
  if(n.ui && typeof n.ui==='object'){
    if(n.ui.panes && typeof n.ui.panes==='object'){ const ps={}, alle=Object.entries(n.ui.panes);
      // Treffen zwei Seiten auf denselben Tab, gewinnt die getauschte (die Vorlage, uebertragen auf den Zielraum)
      [...alle.filter(([k])=>tab(k)!==k), ...alle.filter(([k])=>tab(k)===k)].forEach(([k,v])=>{
        const z=tab(k); if(z in ps) return; const w=paneTausch(v, uu); if(w) ps[z]=w; });
      n.ui.panes=ps; }
    if(Array.isArray(n.ui.valueBar)) n.ui.valueBar=einmal(n.ui.valueBar.map(tab));
    if(typeof n.ui.svPane==='string' && n.ui.svPane) n.ui.svPane=paneTausch(n.ui.svPane, uu);
    if(typeof n.ui.player==='string' && n.ui.player) n.ui.player=uu(n.ui.player)||'';
  }
  return {profil:n, fehlend:fehlend, getauscht:[...map.values()].filter(Boolean).length};
}
// Raum eines Profils: sein room:-Tab, sonst der erste der Raum-Liste, sonst
// der Raum, aus dem die meisten gewaehlten Bausteine stammen (der feste
// Player zaehlt mit, sonst bliebe ein reines Musik-Panel ohne Raum).
function profilRaum(p){
  const t=(p.tabs||[]).find(x=>typeof x==='string' && x.indexOf('room:')===0); if(t) return t.slice(5);
  if(Array.isArray(p.rooms) && p.rooms.length) return p.rooms[0];
  const zahl={}, zaehl=u=>{ const c=(META.controls||[]).find(x=>x.uuid===u); if(c&&c.room) zahl[c.room]=(zahl[c.room]||0)+1; return u; };
  (p.hide||[]).forEach(zaehl); (p.picks||[]).forEach(zaehl);
  (p.pickTabs||[]).forEach(t=>{ (t&&t.picks||[]).forEach(zaehl); if(t&&t.widget) paneTausch(t.widget, zaehl); });
  Object.keys(p.tiles||{}).forEach(zaehl);
  Object.values((p.ui||{}).panes||{}).forEach(v=>paneTausch(v, zaehl));
  if((p.ui||{}).svPane) paneTausch(p.ui.svPane, zaehl);
  if(typeof (p.ui||{}).player==='string' && p.ui.player) zaehl(p.ui.player);
  return Object.keys(zahl).sort((a,b)=>zahl[b]-zahl[a])[0]||'';
}
// Kennung aus einem Raumnamen: klein, Umlaute ausgeschrieben, Rest Bindestrich; frei (sonst -2, -3 ...)
function nameSlug(name){
  return (name||'').toLowerCase().replace(/ä/g,'ae').replace(/ö/g,'oe').replace(/ü/g,'ue').replace(/ß/g,'ss')
    .replace(/[^a-z0-9]+/g,'-').replace(/^-+|-+$/g,'');
}
function idAusName(name){
  const id=nameSlug(name) || 'panel';
  let k=id, n=2; while(PANELS[k]){ k=id+'-'+(n++); } return k;
}
let DUP={quelle:''};
function dupOpen(id){
  const p=PANELS[id]; if(!p || p.__global) return;
  DUP.quelle=id;
  const rooms=META.rooms||[], von=profilRaum(p);
  const nach=(rooms.find(r=>r.uuid!==von)||{}).uuid||'';
  const opts=(sel, leer)=>(leer?'<option value="">'+esc(leer)+'</option>':'')+
    rooms.map(r=>'<option value="'+esc(r.uuid)+'"'+(r.uuid===sel?' selected':'')+'>'+esc(r.name)+'</option>').join('');
  $('#dupQuelle').textContent=T('Vorlage')+': '+(p.title||id);
  $('#dupBody').innerHTML='<div class="wzrow">'+
      '<div class="wzfield" style="flex:1;min-width:160px"><label>'+T('Neue ID')+'</label><input id="dupId"></div>'+
      '<div class="wzfield" style="flex:1;min-width:160px"><label>'+T('Titel')+'</label><input id="dupTitle"></div></div>'+
    '<div class="wzrow" style="margin-top:12px">'+
      '<div class="wzfield" style="flex:1;min-width:160px"><label>'+T('Raum tauschen: von')+'</label><select id="dupVon">'+opts(von,'')+'</select></div>'+
      '<div class="wzfield" style="flex:1;min-width:160px"><label>'+T('nach')+'</label><select id="dupNach">'+opts(nach, T('(kein Raumtausch – reine Kopie)'))+'</select></div></div>'+
    '<div class="wznote" id="dupInfo" style="margin-top:10px"></div>';
  const vorschlag=()=>{   // ID und Titel aus dem Zielraum, solange niemand selbst getippt hat
    const z=$('#dupNach').value, zn=z?roomName(z):'', vn=roomName($('#dupVon').value);
    if(!$('#dupId')._tippt) $('#dupId').value = z ? idAusName(zn) : idAusName(id+'-kopie');
    if(!$('#dupTitle')._tippt) $('#dupTitle').value = z ? ((p.title||'').indexOf(vn)>=0 && vn!=='?' ? p.title.split(vn).join(zn) : zn) : ((p.title||id)+' '+T('(Kopie)'));
    dupInfo(); };
  ['dupId','dupTitle'].forEach(k=>{ $('#'+k).oninput=()=>{ $('#'+k)._tippt=true; }; });
  $('#dupVon').onchange=vorschlag; $('#dupNach').onchange=vorschlag;
  vorschlag();
  // Die Knoepfe erst hier verdrahten: das Overlay steht im Dokument hinter dem Skript
  $('#dupX').onclick=dupClose; $('#dupCancel').onclick=dupClose; $('#dupGo').onclick=dupBuild;
  $('#dupOv').hidden=false;
  $('#dupId').focus();
}
function dupInfo(){
  const p=PANELS[DUP.quelle], von=$('#dupVon').value, nach=$('#dupNach').value, box=$('#dupInfo');
  if(!nach){ box.textContent=T('Reine Kopie: alle Tabs, Bausteine und Einstellungen bleiben, wie sie sind.'); return; }
  if(von===nach){ box.textContent=T('Quell- und Zielraum sind gleich – nichts zu tauschen.'); return; }
  const r=profilMitRaumtausch(p, von, nach, META.controls||[]);
  box.textContent=r.getauscht+' '+T('Bausteine aus')+' '+roomName(von)+' '+T('werden durch die gleichnamigen in')+' '+roomName(nach)+' '+T('ersetzt.')+
    (r.fehlend.length ? ' '+T('Ohne Gegenstück dort (fallen weg):')+' '+r.fehlend.join(', ') : '');
}
function dupClose(){ $('#dupOv').hidden=true; }
function dupBuild(){
  const p=PANELS[DUP.quelle]; if(!p) return;
  const id=($('#dupId').value||'').trim().toLowerCase().replace(/[^a-z0-9-]/g,'');
  if(!id){ alert(T('Ungültige ID.')); return; }
  if(PANELS[id]){ alert('Ansicht „'+id+'" '+T('gibt es schon.')); return; }
  const von=$('#dupVon').value, nach=$('#dupNach').value;
  const r=(nach && nach!==von) ? profilMitRaumtausch(p, von, nach, META.controls||[])
                               : {profil: JSON.parse(JSON.stringify(p)), fehlend: []};
  r.profil.title=($('#dupTitle').value||'').trim().slice(0,40) || id;
  PANELS[id]=r.profil;
  cur=id; tileSel=null; dupClose(); renderList(); setRubric('pconf'); markDirty();
  flash($('#toast'), 'Ansicht „'+id+'" '+T('angelegt – Speichern nicht vergessen.')+
    (r.fehlend.length ? ' '+T('Weggefallen:')+' '+r.fehlend.join(', ') : ''), !r.fehlend.length);
}
/* ============================================================
   Gemeinsame Helfer der Dialoge (Gerät einrichten, Gerät verbinden, Seiten-Editor,
   Betriebsmodus-Assistent): Icons, Geraete mit gemeldeter Groesse, dieser Browser,
   der Katalog des Servers, der Raum zum Geraetenamen, die Raum-Auswahl und der
   Weg "Ansicht speichern und am Geraet zeigen". Sie stammen aus dem frueheren
   sechsstufigen Assistenten, der seit dem 15.10.2026 abgebaut ist.
   ============================================================ */
const IKONEN={
  p1:'<svg viewBox="0 0 24 24"><rect x="7" y="4" width="10" height="16" rx="2"/></svg>',
  p2:'<svg viewBox="0 0 24 24"><rect x="2" y="5" width="9" height="14" rx="1.5"/><rect x="13" y="5" width="9" height="14" rx="1.5"/></svg>',
  room:'<svg viewBox="0 0 24 24"><path d="M3 11 12 4l9 7"/><path d="M5 10v10h14V10"/><rect x="10" y="14" width="4" height="6"/></svg>',
  grid:'<svg viewBox="0 0 24 24"><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/></svg>',
  pick:'<svg viewBox="0 0 24 24"><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><path d="M14 17.5h7M17.5 14v7"/></svg>',
  clock:'<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></svg>',
  cal:'<svg viewBox="0 0 24 24"><rect x="3" y="4.5" width="18" height="16" rx="2"/><path d="M3 9h18M8 3v4M16 3v4"/></svg>',
  wx:'<svg viewBox="0 0 24 24"><path d="M17.5 19a4.5 4.5 0 0 0 0-9 6 6 0 0 0-11.6 1.5A4 4 0 0 0 6.5 19z"/></svg>',
  paint:'<svg viewBox="0 0 24 24"><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/></svg>',
  brush:'<svg viewBox="0 0 24 24"><path d="M17 3 21 7 10 18l-4 1 1-4z"/><path d="M14 6l4 4"/></svg>',
  energy:'<svg viewBox="0 0 24 24"><path d="M13 2 4 14h7l-1 8 9-12h-7z"/></svg>',
  camera:'<svg viewBox="0 0 24 24"><path d="M23 7l-7 5 7 5V7z"/><rect x="1" y="5" width="15" height="14" rx="2"/></svg>',
  status:'<svg viewBox="0 0 24 24"><path d="M4 19V5M4 19h16"/><rect x="7" y="11" width="3" height="5"/><rect x="12" y="8" width="3" height="8"/><rect x="17" y="13" width="3" height="3"/></svg>',
  ext:'<svg viewBox="0 0 24 24"><rect x="3" y="4" width="18" height="16" rx="2"/><path d="M12 4v16"/></svg>',
  photo:'<svg viewBox="0 0 24 24"><rect x="3" y="4" width="18" height="16" rx="2"/><circle cx="8.5" cy="9.5" r="1.5"/><path d="m21 16-5-5-9 9"/></svg>',
  audio:'<svg viewBox="0 0 24 24"><path d="M9 18V5l10-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="16" cy="16" r="3"/></svg>'
};
function ikon(k){ return '<span class="ic">'+(IKONEN[k]||IKONEN.grid)+'</span>'; }
// Raum zum Geraetenamen. Passen mehrere, gewinnt der, dessen Name in der Laenge am
// naechsten am Geraetenamen liegt: der gleiche Name (Abstand 0) immer, sonst etwa
// "badezimmer-oben" -> "Badezimmer" vor "Bad"; bei Gleichstand die Reihenfolge der Raeume.
function raumZumGeraet(n){
  const passt=(a,b)=>{ a=nameSlug(a); b=nameSlug(b); return !!a && !!b && (a===b || (a.length>=3 && b.indexOf(a)>=0) || (b.length>=3 && a.indexOf(b)>=0)); };
  const l=nameSlug(n).length;
  return (META.rooms||[]).filter(r=>passt(n, r.name))
    .sort((a,b)=>Math.abs(nameSlug(a.name).length-l)-Math.abs(nameSlug(b.name).length-l))[0]||null;
}
// Geraete mit gemeldeter Groesse (Vorschaugeraete), dieser Browser und der Katalog des Servers
function geraeteMitGroesse(){
  return [...new Set([].concat(KNOWN_NAMES, Object.keys(DEV||{})))]
    .filter(n=>{ const s=DEVICE_SCREENS[n]; return n && s && s.vw && s.vh; })
    .sort((a,b)=>a.localeCompare(b))
    .map(n=>({quelle:'geraet', name:n, vw:DEVICE_SCREENS[n].vw, vh:DEVICE_SCREENS[n].vh}));
}
function dieserBrowser(){ return {quelle:'browser', name:T('Dieser Browser'), vw:Math.round(window.innerWidth), vh:Math.round(window.innerHeight)}; }
function geraeteKatalog(){ return (META.geraeteKatalog||[]).map(k=>({quelle:'katalog', name:T(k.name), vw:k.vw, vh:k.vh})); }
// Ansicht speichern und am Geraet zeigen ("Fertig" in Gerät einrichten): ziel > 0 merkt
// die Zielkachel am Geraet (Displays); umschalten speichert die Ansicht, wenn sie noch nicht
// (so) auf dem Server steht, und schaltet das Geraet per /api/device/switch um (die
// Zuordnung, Einrichtung neu Schritt 2) - auch wenn es gerade nicht verbunden ist.
async function ansichtAmGeraet(id, name, umschalten, ziel){
  const t=$('#toast');
  if(ziel){
    readDevFromDom();
    DEV[name]=Object.assign({auto:true, modes:[]}, DEV[name]||{}, {tileTarget:ziel});
    try{ const j=await devSpeichern();
      if(!j.ok){ flash(t, j.error||T('Fehler'), false); return; }
      devGespeichert(j, T('✓ Gespeichert')); renderDevices(); }
    catch(e){ flash(t, 'Fehler: '+e, false); return; }
  }
  if(!umschalten) return;
  // Speichern nur, wenn die Ansicht noch nicht (so) auf dem Server steht: es laedt jede Visu neu
  if(!GESPEICHERT[id] || OFFEN.has('ansicht:'+id)){ if(!(await save())) return; }
  // Das Speichern laedt jede offene Visu neu ({t:"reload"}); bis das Geraet
  // wieder verbunden ist, meldet /api/device/switch "nicht online" - so lange
  // erneut versuchen, hoechstens etwa zehn Sekunden.
  let j={ok:false};
  for(let i=0; i<20 && !j.ok; i++){
    if(i) await new Promise(r=>setTimeout(r, 500));
    try{ j=await postJson('/api/device/switch', {device:name, ip:DEVICE_IPS[name]||'', panel:id}); }
    catch(e){ j={ok:false}; }
  }
  flash(t, j.ok ? ('Ansicht „'+id+'" '+T('gespeichert,')+' '+name+' '+(j.offline ? T('zeigt sie, sobald es verbindet.') : T('schaltet um.')))
               : (name+' '+T('ist nicht online – die Ansicht ist gespeichert, umschalten unter Geräte.')), !!j.ok);
}
// Widget-Wahl der Seite (weather, calendar, header, audio, energy, camera, chart) -> der
// Wert in ui.panes, mit dem ersten passenden Baustein der Anlage
function paneWert(v){
  if(v==='weather'||v==='calendar'||v==='header') return v;
  if(v==='audio'){ var z=firstAudioZone(); return z?'player:'+z:''; }
  if(v==='energy'){ var u=firstEnergyControl(); return u?'energy:'+u:''; }
  if(v==='camera'){ var u=firstCamera(); return u?'camera:'+u:''; }
  if(v==='chart'){ var u=firstChartControl(); return u?'chart:'+u:''; }
  return '';
}
function raumOptionen(sel, leer){
  return (leer?'<option value="">'+esc(leer)+'</option>':'')+(META.rooms||[]).map(function(r){ return '<option value="'+esc(r.uuid)+'"'+(r.uuid===sel?' selected':'')+'>'+esc(r.name)+'</option>'; }).join('');
}

/* ============================================================
   Gerät einrichten (Einrichtung neu, Schritt 3): EIN Bildschirm. Name der Ansicht
   (aus dem Raum zum Geraetenamen vorgeschlagen, die Kennung folgt daraus), die Frage
   "Was soll es zeigen?" mit drei Karten - ein Raum, das ganze Haus, wie ein anderes
   Geraet (mit Raumtausch) - und rechts die echte Visu als Vorschau in der gemeldeten
   Groesse des Geraets (/api/entwurf, skalierter iframe; jede Aenderung zieht nach).
   "Fertig" legt die Ansicht an, speichert und ordnet sie dem Geraet zu
   (/api/device/switch, Schritt 2) - in einem Zug. Raster, Farben, Schrift und
   Display kommen aus den Vorgaben; am 4"-Wandpanel (quadratisch) gibt es kein Haus
   und ein festes 2 x 2. Ohne Geraet ("+ Neue Ansicht") dasselbe ohne Zuordnung.
   ============================================================ */
/* ============================================================
   Gerät verbinden (Einrichtung neu, Schritt 5): drei Wege, je eine Zeile zum Kopieren.
   LoxPanel-App (Server-Adresse), Kiosk-Browser (Start-Adresse ohne Parameter: Namen und
   Ansicht vergibt der Konfigurator, sobald sich das Geraet meldet) und Linux-Agent (ein
   Befehl per SSH, ohne PANEL und AGENT_NAME: Ansicht und Display kommen vom Server). Die
   Server-Adresse ist immer die LAN-Adresse (/api/meta adressen), auch wenn der Konfigurator
   ueber 127.0.0.1 laeuft. Der Fuss wartet auf ein neues Geraet (neueGeraete) und fuehrt
   zum Banner "Neues Geraet gefunden".
   ============================================================ */
const GV={_wired:false};
function gvHost(){
  const lan=((META&&META.adressen)||[])[0]||'';
  const host=lan || location.hostname;
  const port=location.port && !((location.protocol==='http:' && location.port==='80') || (location.protocol==='https:' && location.port==='443')) ? ':'+location.port : '';
  return {host:host+port, lan:!!lan, url:location.protocol+'//'+host+port+'/'};
}
function gvWeg(icon, titel, text, zeile, knopf, klein){
  return '<div class="gv-weg"><span class="ic">'+icon+'</span><div><b>'+esc(titel)+'</b><div class="gv-text">'+esc(text)+'</div>'+
    '<div class="gv-zeile"><code>'+esc(zeile)+'</code><button type="button" class="btn sm" data-gv-copy="'+esc(zeile)+'">'+esc(knopf)+'</button></div>'+
    '<div class="gv-klein">'+esc(klein)+'</div></div></div>';
}
function gvRender(){
  const b=$('#gvBody'), a=gvHost();
  const ic={app:'<svg viewBox="0 0 24 24"><rect x="7" y="2" width="10" height="20" rx="2"/><path d="M11 18h2"/></svg>',
            kiosk:'<svg viewBox="0 0 24 24"><rect x="3" y="5" width="18" height="12" rx="1.5"/><path d="M8 21h8M12 17v4"/></svg>',
            agent:'<svg viewBox="0 0 24 24"><path d="M4 17l6-5-6-5M12 19h8"/></svg>'};
  b.innerHTML=
    gvWeg(ic.app, T('LoxPanel-App auf Android'),
      T('App installieren und öffnen. Sie fragt „Wo läuft der Server?“: „Im Netz“ wählen und diese Adresse eintragen. Die App zeigt dann die Visu dieses Servers und meldet sich mit Code.'),
      a.host, T('Adresse kopieren'),
      T('Später ändern: auf der Uhr-Seite den Finger drei Sekunden liegen lassen, dann „Server ändern“. Antwortet der Server nicht, steht der Knopf auf der Fehlerseite der App.'))+
    gvWeg(ic.kiosk, T('Fully Kiosk, WallPanel oder ein Browser'),
      T('Diese Adresse als Start-URL eintragen, mehr nicht: Namen und Ansicht vergibt der Konfigurator, sobald sich das Gerät meldet.'),
      a.url, T('Adresse kopieren'),
      T('Fully: JavaScript-Schnittstelle und Launch on Boot einschalten (deploy/ANDROID.md). Ein Gerät, das schon eine Adresse mit ?panel= hat, darf sie behalten.'))+
    gvWeg(ic.agent, T('Linux-Wandpanel mit Agent'),
      T('Einmal per SSH auf dem Panel ausführen, als dessen Login-Benutzer. Der Agent startet Chromium im Kiosk, meldet das Panel hier und übernimmt Display und Neustart.'),
      'curl -fsSL '+a.url+'install-agent.sh | SERVER='+a.host+' bash', T('Befehl kopieren'),
      T('Fragt nach dem sudo-Passwort des Panels. Das Panel heißt wie sein Hostname (AGENT_NAME=… davor ändert das); Ansicht und Display-Abschaltung kommen vom Konfigurator, nicht aus der kiosk.conf.'))+
    '<div class="gv-server">'+esc(T('Server-Adresse im Heimnetz:'))+' <b>'+esc(a.host)+'</b>. '+
      esc(a.lan ? T('Sie steht in jeder Zeile schon drin, auch wenn der Konfigurator über eine andere Adresse geöffnet ist.')
                : T('Der Server kennt keine eigene Adresse im Netz; die Zeilen nehmen die Adresse dieses Fensters.'))+'</div>';
  b.querySelectorAll('[data-gv-copy]').forEach(k=>k.onclick=()=>{
    navigator.clipboard.writeText(k.dataset.gvCopy).then(()=>flash($('#gvToast'), T('✓ kopiert'), true))
      .catch(()=>flash($('#gvToast'), T('Kopieren nicht möglich – bitte manuell markieren'), false)); });
  gvStandZeichnen();
}
// Fuss: warten, oder das gefundene Geraet (dieselbe Quelle wie das Banner) und der Weg dorthin
let NEU_LETZTE=[];
function gvStandZeichnen(){
  const s=$('#gvStand'); if(!s || $('#gvOv').hidden) return;
  const g=NEU_LETZTE[0];
  if(!g){ s.innerHTML='<span class="punkt"></span>'+esc(T('Warte auf ein neues Gerät …')); return; }
  const was=(g.art==='code' ? T('Neues Gerät gefunden:') : T('Neues Gerät verbunden:'))+' '+(g.art==='code' ? geraeteKlasse(g.screen) : g.name)+
    (g.screen&&g.screen.vw ? ' · '+g.screen.vw+'×'+g.screen.vh : '')+(g.code ? ' · '+T('Code')+' '+g.code : '');
  s.innerHTML='<span class="punkt an"></span>'+esc(was)+' <button type="button" class="btn sm prim" id="gvWeiter">'+esc(T('Weiter mit Einrichten →'))+'</button>';
  $('#gvWeiter').onclick=()=>{ gvClose(); const b=$('#neuGeraet'); if(b && !b.hidden){ b.scrollIntoView({block:'start'}); const n=b.querySelector('.nb-name'); if(n) n.focus(); } };
}
function gvOpen(){
  if(!GV._wired){ GV._wired=true;
    $('#gvOv').onclick=e=>{ if(e.target===$('#gvOv')) gvClose(); };
    $('#gvX').onclick=gvClose; $('#gvZu').onclick=gvClose; }
  $('#gvOv').hidden=false; gvRender();
}
function gvClose(){ $('#gvOv').hidden=true; }
$('#geraetVerbindenBtn').onclick=gvOpen;

const GE={device:'', screen:null, name:'', _nameT:false, art:'raum', raum:'', aufbau:'', quelle:'', nach:'', token:'', url:'', timer:0, _wired:false};
function geQuadrat(){ const s=GE.screen; return !!s && LoxRaster.quadratisch(s.vw, s.vh); }
function geRaumVorschlag(){ const r=GE.device ? raumZumGeraet(GE.device) : null; return r ? r.uuid : ''; }
function geId(){ return idAusName(GE.name.trim() || GE.device || 'ansicht'); }
// Name, solange niemand einen getippt hat: der Raum, "Haus", bei der Kopie der Zielraum oder die Vorlage, sonst das Geraet
function geNameVorschlag(){
  if(GE._nameT) return;
  let t='';
  if(GE.art==='raum' && GE.raum && roomName(GE.raum)!=='?') t=roomName(GE.raum);
  else if(GE.art==='haus') t=T('Haus');
  else if(GE.art==='wie'){ const q=PANELS[GE.quelle]; if(q) t=GE.nach ? roomName(GE.nach) : ((q.title||GE.quelle)+' '+T('(Kopie)')); }
  if(!t && GE.device) t=GE.device.charAt(0).toUpperCase()+GE.device.slice(1);
  GE.name=t;
}
// Vorlagen fuer "Wie ein anderes Geraet": jede Ansicht, mit den Geraeten, die sie zeigen
function geVorlagen(){
  return ansichtIds().map(id=>{
    const zeigt=[...new Set(Object.keys(DEVICE_ZUORDNUNG).filter(n=>DEVICE_ZUORDNUNG[n]===id)
      .concat(((PANELS[id]||{}).device||{}).name||[]))].filter(n=>n && n!==GE.device);
    return {id:id, label:ansichtName(id)+(zeigt.length ? ' · '+T('zeigt')+' '+zeigt.join(', ') : '')}; });
}
function geKopieInfo(){
  const q=PANELS[GE.quelle]; if(!q) return '';
  const von=profilRaum(q);
  if(!GE.nach) return T('Reine Kopie: alle Tabs, Bausteine und Einstellungen bleiben, wie sie sind.');
  if(!von) return T('Die Vorlage hat keinen Raum – es bleibt bei der reinen Kopie.');
  if(von===GE.nach) return T('Quell- und Zielraum sind gleich – nichts zu tauschen.');
  const r=profilMitRaumtausch(q, von, GE.nach, META.controls||[]);
  return r.getauscht+' '+T('Bausteine aus')+' '+roomName(von)+' '+T('werden durch die gleichnamigen in')+' '+roomName(GE.nach)+' '+T('ersetzt.')+
    (r.fehlend.length ? ' '+T('Ohne Gegenstück dort (fallen weg):')+' '+r.fehlend.join(', ') : '');
}
// Die Ansicht, die "Fertig" anlegt (UI-Form wie in PANELS); null, solange etwas fehlt
function geProfil(){
  const sc=GE.screen||{}, id=geId(), name=GE.name.trim()||id;
  const geraet=GE.device ? {device:Object.assign({name:GE.device}, (sc.vw&&sc.vh)?{vw:sc.vw, vh:sc.vh}:{})} : {};
  let p;
  if(GE.art==='wie'){
    const q=PANELS[GE.quelle]; if(!q) return null;
    const von=profilRaum(q);
    p=(GE.nach && von && GE.nach!==von) ? profilMitRaumtausch(q, von, GE.nach, META.controls||[]).profil : JSON.parse(JSON.stringify(q));
    delete p.device; p.title=name;
  } else {
    if(GE.art==='raum' && !GE.raum) return null;
    if(GE.art==='haus' && geQuadrat()) return null;
    const ui={};
    if(geQuadrat()) ui.split=false; else ui.grid='auto';   // 4"-Panel: ein Pane, festes 2 x 2; sonst rechnet das Geraet das Raster selbst
    if(GE.art==='haus' && GE.aufbau && GE.aufbau!==((META&&META.hausAufbauStandard)||'')) ui.hausAufbau=GE.aufbau;
    p={title:name, tabs:(GE.art==='haus' ? ['haus','favoriten'] : ['room:'+GE.raum]), rooms:[], cats:[], ui:ui, states:{}, tiles:{}};
  }
  return Object.assign(p, geraet);
}
// Vorschau: iframe in Geraetegroesse, verkleinert auf den Platz rechts (die Visu rechnet ihr Raster fuer die echte Groesse)
function geVorschauMass(){
  const box=$('#geVor'), f=$('#geFrame'); if(!box||!f) return;
  const g=(GE.screen&&GE.screen.vw&&GE.screen.vh) ? GE.screen : dieserBrowser(), vw=g.vw, vh=g.vh;
  const s=Math.min(1, (box.clientWidth-16)/vw, (box.clientHeight-16)/vh);
  f.style.width=vw+'px'; f.style.height=vh+'px'; f.style.transform='scale('+s+')';
  f.style.left=Math.round((box.clientWidth-vw*s)/2)+'px'; f.style.top=Math.round((box.clientHeight-vh*s)/2)+'px';
  const m=$('#geVorMass'); if(m) m.textContent=vw+' × '+vh+(s<1 ? ' · '+Math.round(s*100)+' %' : '');
}
// Entwurf an den Server; der iframe folgt der Adresse. Gleicher Token und gleiche
// Kennung: der Server laedt die Visu im iframe selbst neu (api_entwurf reloaded).
function geVorschau(){
  clearTimeout(GE.timer);
  GE.timer=setTimeout(async()=>{
    const p=geProfil(), f=$('#geFrame'), h=$('#geVorHinweis'), id=geId(); if(!f) return;
    if(!p){ if(h) h.textContent=T('Für die Vorschau fehlt noch eine Wahl.'); return; }
    try{ const j=await postJson('/api/entwurf', {id:id, panel:p, token:GE.token});
      if(!j.ok || $('#geOv').hidden) return;
      GE.token=j.token;
      if(j.url!==GE.url){ GE.url=j.url; f.src=j.url; }
      if(h) h.textContent=(j.verworfen||[]).length ? T('Nicht übernommen:')+' '+j.verworfen.join('; ')
        : T('Die Vorschau ist die echte Visu mit den Vorgaben, in der gemeldeten Größe des Geräts.');
    }catch(e){ if(h) h.textContent=T('Vorschau nicht möglich:')+' '+e.message; }
  }, 350);
}
function geKarte(art, icon, titel, text, innen, sperre){
  const an=GE.art===art;
  return '<div class="wzo ge-karte'+(an?' on':'')+(sperre?' aus':'')+'" role="button" tabindex="0" data-ge-art="'+art+'"'+(sperre?' aria-disabled="true"':'')+'>'+
    ikon(icon)+'<span class="tx"><b>'+esc(titel)+'</b><span>'+esc(sperre||text)+'</span>'+(an&&innen ? '<span class="ge-innen">'+innen+'</span>' : '')+'</span></div>';
}
function geKopf(){
  if(!GE.device) return T('ohne Gerät');
  const sc=GE.screen; return GE.device+' · '+geraeteKlasse(sc)+((sc&&sc.vw&&sc.vh) ? ' · '+sc.vw+'×'+sc.vh+' '+(sc.vw>sc.vh?T('quer'):(sc.vw<sc.vh?T('hoch'):T('quadratisch'))) : '');
}
function geRender(){
  const b=$('#geLinks'); if(!b) return;
  geNameVorschlag();
  const quadrat=geQuadrat(), vorlagen=geVorlagen(), g=GE.device;
  if(GE.art==='haus' && quadrat) GE.art='raum';
  $('#geKopf').textContent=geKopf();
  $('#geVorTitel').textContent=g ? T('So sieht es auf {g} aus').replace('{g}', g) : T('So sieht es aus');
  $('#geFuss').textContent=g ? T('Nach „Fertig“ zeigt {g} diese Ansicht sofort.').replace('{g}', g) : T('Danach bist du im Editor zum Feinschliff.');
  $('#geFertig').textContent=g ? T('Fertig – auf {g} anzeigen').replace('{g}', g) : T('Ansicht anlegen');
  const raumSel='<label>'+T('Raum')+'</label><select id="geRaum">'+raumOptionen(GE.raum,'')+'</select>';
  const aufbauSel='<label>'+T('Aufbau')+'</label><select id="geAufbau">'+((META&&META.hausAufbauten)||[]).map(a=>
    '<option value="'+esc(a.key)+'"'+(a.key===GE.aufbau?' selected':'')+'>'+esc(T(a.label))+'</option>').join('')+'</select>';
  const wieSel='<label>'+T('Vorlage')+'</label><select id="geQuelle">'+vorlagen.map(v=>'<option value="'+esc(v.id)+'"'+(v.id===GE.quelle?' selected':'')+'>'+esc(v.label)+'</option>').join('')+'</select>'+
    '<label>'+T('Raum tauschen nach')+'</label><select id="geNach">'+raumOptionen(GE.nach, T('(kein Raumtausch – reine Kopie)'))+'</select>'+
    '<span class="ge-info">'+esc(geKopieInfo())+'</span>';
  b.innerHTML='<div class="wzfield"><label>'+T('Name der Ansicht')+'</label><input id="geName" value="'+esc(GE.name)+'" placeholder="'+esc(T('z. B. Bad'))+'">'+
      '<div class="wznote">'+(GE._nameT ? '' : esc(T('Vorgeschlagen.'))+' ')+T('Kennung')+' <code id="geIdText">'+esc(geId())+'</code></div></div>'+
    '<p class="wzq mt">'+esc(g ? T('Was soll {g} zeigen?').replace('{g}', g) : T('Was soll die Ansicht zeigen?'))+'</p><div class="wzopts">'+
    geKarte('raum','room',T('Einen Raum'),T('Alles aus einem Loxone-Raum, die Kategorien als Sprungmarken. Die übliche Wahl für ein Gerät im Raum.'),
      raumSel, (META.rooms||[]).length ? '' : T('Die Anlage hat keine Räume.'))+
    geKarte('haus','grid',T('Das ganze Haus'),T('Hausübersicht: Räume, was gerade an ist, Hinweise, Musik. Für Flur, Küche oder ein großes Display.'),
      aufbauSel, quadrat ? T('Auf einem 4″-Wandpanel zu klein – dort einen Raum oder eine Kopie.') : '')+
    geKarte('wie','ext',T('Wie ein anderes Gerät'),T('Dieselbe Ansicht wie ein vorhandenes Gerät, auf Wunsch mit getauschtem Raum.'),
      wieSel, vorlagen.length ? '' : T('Es gibt noch keine Ansicht zum Kopieren.'))+
    '</div><p class="wznote" style="margin-top:14px">'+T('Raster, Farben, Schrift, Screensaver und Display aus kommen aus den Vorgaben und passen zur Bildschirmgröße. Änderbar danach unter Ansichten.')+'</p>';
  const ni=$('#geName'); ni.oninput=()=>{ GE.name=ni.value; GE._nameT=true; $('#geIdText').textContent=geId(); geVorschau(); };
  b.querySelectorAll('[data-ge-art]').forEach(el=>{ el.onclick=e=>{
    if(el.classList.contains('aus') || e.target.closest('select,label')) return;
    const art=el.dataset.geArt;
    if(GE.art!==art){ GE.art=art; geRender(); } };
    el.onkeydown=e=>{ if((e.key==='Enter'||e.key===' ') && e.target===el){ e.preventDefault(); el.click(); } }; });
  { const r=$('#geRaum'); if(r) r.onchange=()=>{ GE.raum=r.value; geRender(); }; }
  { const a=$('#geAufbau'); if(a) a.onchange=()=>{ GE.aufbau=a.value; geVorschau(); }; }
  { const q=$('#geQuelle'); if(q) q.onchange=()=>{ GE.quelle=q.value; geRender(); }; }
  { const n=$('#geNach'); if(n) n.onchange=()=>{ GE.nach=n.value; geRender(); }; }
  $('#geFertig').disabled=!geProfil();
  geVorschauMass(); geVorschau();
}
function geOpen(name){
  // ohne Struktur beginnt der Weg beim Miniserver
  if(EINR){ setRubric('settings'); flash($('#toast'), T('Erst den Miniserver verbinden'), false); return; }
  if(!GE._wired){ GE._wired=true;
    $('#geOv').onclick=e=>{ if(e.target===$('#geOv')) geClose(); };
    $('#geX').onclick=geClose; $('#geAbbrechen').onclick=geClose;
    $('#geLeer').onclick=()=>{ geClose(); createBlankPanel(); };
    $('#geFertig').onclick=geFertig;
    window.addEventListener('resize', ()=>{ if(!$('#geOv').hidden) geVorschauMass(); });
  }
  const sc=(name && DEVICE_SCREENS[name]) || null;
  Object.assign(GE, {device:name||'', screen:(sc&&sc.vw&&sc.vh)?{vw:sc.vw, vh:sc.vh}:null, name:'', _nameT:false, art:'raum', raum:'',
    aufbau:(META&&META.hausAufbauStandard)||'', quelle:ansichtIds()[0]||'', nach:'', token:'', url:''});
  GE.raum=geRaumVorschlag()||(((META.rooms||[])[0]||{}).uuid||'');
  GE.nach=geRaumVorschlag();
  if(!GE.raum) GE.art=(ansichtIds().length ? 'wie' : 'haus');   // eine Anlage ohne Raeume
  $('#geOv').hidden=false; geRender();
  setTimeout(()=>{ const ni=$('#geName'); if(ni){ ni.focus(); ni.select(); } }, 30);
}
// Schliessen ersetzt den iframe: ein src='about:blank' kaeme zu spaet, wenn die Visu darin
// gerade selbst navigiert (Speichern beendet den Entwurf, sie laedt /?panel= ohne Token) -
// die Verbindung ohne Namen bliebe stehen und staende im Banner als neues Geraet.
function geClose(){
  clearTimeout(GE.timer); GE.url='';
  const f=$('#geFrame'), n=document.createElement('iframe'); n.id='geFrame'; n.title=f.title; f.replaceWith(n);
  $('#geOv').hidden=true;
}
// Fertig: Ansicht anlegen, speichern und dem Geraet zuordnen (ansichtAmGeraet: /api/device/switch
// schreibt die Zuordnung, Schritt 2 - auch wenn das Geraet gerade nicht verbunden ist)
async function geFertig(){
  const p=geProfil(); if(!p) return;
  const id=geId(), name=GE.device, btn=$('#geFertig'); btn.disabled=true;
  PANELS[id]=p; cur=id; tileSel=null; curPickIdx=0; renderList(); markDirty();
  geClose();
  if(name){ setRubric('displays'); await ansichtAmGeraet(id, name, true, 0); }
  else setRubric('pconf');
  btn.disabled=false;
}
$('#addBtn').onclick=()=>geOpen();
['#geraetEinrichtenBtn','#ovGeraetEinrichten'].forEach(sel=>{ const k=$(sel); if(k) k.onclick=()=>geOpen(); });
