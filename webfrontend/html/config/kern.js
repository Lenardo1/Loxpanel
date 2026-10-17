// LoxPanel-Konfigurator, Teil 1 von 11: Zustand, Helfer, Rubriken und Reiter.
// Die Teile laden nacheinander aus config.html (script src), alle Funktionen sind global;
// was beim Laden ausgefuehrt wird, darf nur Funktionen frueherer Teile rufen.

const $ = (s,r=document)=>r.querySelector(s);
let META=null, PANELS={}, cur=null, tileSel=null;
// Zuletzt gespeicherter Stand der Ansichten (wie an /api/panels geschickt): "Ansicht loeschen"
// schickt ihn ohne die geloeschte, damit andere offene Aenderungen nicht nebenbei mitgehen.
let GESPEICHERT={};
let rubric='overview', subPconf='inhalt', subSet='miniserver', subVg='appearance';
// Die Vorgaben bearbeitet derselbe Editor wie eine Ansicht (cur='__global__'), aber nur in
// ihrer Rubrik; jede andere Rubrik kehrt zu der Ansicht zurueck, die vorher gewaehlt war.
let letzteAnsicht=null;
// Ersteinrichtung (siehe einrichtungAnwenden): Stand aus /api/settings, solange
// der Server keine Struktur hat, sonst null; dazu der Zugang aus der Config und
// der Fehler des letzten eigenen Verbindungsversuchs.
let EINR=null, EINR_MS={}, EINR_VERSUCH='', EINR_TIMER=null;
const EINR_SUBS=['miniserver','backup'];       // ohne Struktur offene Settings-Reiter
const EINR_TAKT_MS=3000;                       // so oft fragt der Konfigurator nach
const EINR_KEY='lp_einrichtung_verbunden';     // naechster Schritt nach dem Neuladen
function svg(inner){return '<svg viewBox="0 0 24 24">'+inner+'</svg>';}
const BICONS = {
  folder:'<path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>',
  bulb:'<path d="M9 18h6"/><path d="M10 21h4"/><path d="M12 3a6 6 0 0 0-4 10.5c.7.8 1 1.4 1 2.5h6c0-1.1.3-1.7 1-2.5A6 6 0 0 0 12 3Z"/>',
  switch:'<rect x="3" y="7" width="18" height="10" rx="5"/><circle cx="8" cy="12" r="2.5"/>',
  mood:'<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M2 12h2M20 12h2M5 5l1.5 1.5M17.5 17.5 19 19M19 5l-1.5 1.5M6.5 17.5 5 19"/>',
  central:'<path d="M3 11 12 4l9 7"/><path d="M5 10v9a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-9"/>',
  info:'<circle cx="12" cy="12" r="9"/><path d="M12 8h.01M11 12h1v4h1"/>',
  blind:'<rect x="4" y="4" width="16" height="16" rx="1"/><path d="M4 9h16M4 13h16M4 17h16"/>',
  up:'<path d="m6 15 6-6 6 6"/>', down:'<path d="m6 9 6 6 6-6"/>',
  stop:'<rect x="6" y="6" width="12" height="12" rx="2"/>',
  music:'<path d="M9 18V5l12-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="18" cy="16" r="3"/>',
  vol:'<path d="M4 9v6h4l5 4V5L8 9z"/><path d="M16 8a5 5 0 0 1 0 8"/>',
  prev:'<path d="M6 6h2v12H6zM20 6v12l-9-6z"/>', next:'<path d="M16 6h2v12h-2zM4 6l9 6-9 6z"/>',
  play:'<path d="M8 5v14l11-7z"/>', pause:'<path d="M7 5h3v14H7zM14 5h3v14h-3z"/>',
  alarm:'<path d="M18 8a6 6 0 0 0-12 0c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.7 21a2 2 0 0 1-3.4 0"/>',
  gate:'<path d="M3 10 12 4l9 6v11H3z"/><path d="M6 21v-7h12v7"/><path d="M6 17.5h12"/>',
  thermo:'<path d="M14 14.76V5a2 2 0 0 0-4 0v9.76a4 4 0 1 0 4 0Z"/>',
  cam:'<rect x="2" y="6" width="14" height="12" rx="2"/><path d="m16 10 6-3v10l-6-3z"/>',
};
const FONTS = [
  {label:'Standard (Vorgabe)', v:''},
  {label:'Inter', v:'Inter, sans-serif'},
  {label:'Roboto', v:'Roboto, sans-serif'},
  {label:'System (Sans)', v:'system-ui, sans-serif'},
  {label:'Arial', v:'Arial, Helvetica, sans-serif'},
  {label:'Verdana', v:'Verdana, Geneva, sans-serif'},
  {label:'Tahoma', v:'Tahoma, sans-serif'},
  {label:'Trebuchet MS', v:'"Trebuchet MS", sans-serif'},
  {label:'Georgia (Serif)', v:'Georgia, serif'},
  {label:'Times (Serif)', v:'"Times New Roman", Times, serif'},
  {label:'Monospace', v:'ui-monospace, "Courier New", monospace'},
];
const sameFont=(f,v)=>((f||'')===(v||''));
const customFont=(f)=>!!f && !FONTS.some(x=>x.v===f);
function esc(s){return (s==null?'':String(s)).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));}

// Reiter-Definitionen je Rubrik
// Schluessel der frei zusammengestellten Seite - derselbe Wert wie PICK_TAB
// im Server und im Panel. Sie hat KEINEN eigenen Unterreiter mehr: der Editor
// lebt unter "Tabs", wo die Seite auch sichtbar geschaltet wird.
const PICK_TAB='auswahl';
// Reiter einer Ansicht, nach der Frage, die man gerade hat (Konzept "Konfigurator neu
// ordnen", Schritt 3): Was zu EINER Seite gehoert, steht bei der Seite (Inhalt fuer die
// Standard-Seiten, Seiten-Editor fuer die freien); was fuer die ganze Ansicht gilt, in
// Raster, Aussehen oder Verhalten.
const PCONF_TABS=[
  {k:'allgemein',label:'Allgemein'},{k:'inhalt',label:'Inhalt'},{k:'seiten',label:'Seiten'},
  {k:'raster',label:'Raster'},{k:'aussehen',label:'Aussehen'},{k:'verhalten',label:'Verhalten'}];
const VG_TABS=[{k:'appearance',label:'Darstellung'},{k:'catcolors',label:'Kategorie-Farben'},{k:'verhalten',label:'Verhalten'}];
const SET_TABS=[
  {k:'miniserver',label:'Miniserver'},{k:'intercom',label:'Kamera / Türstation'},
  {k:'sip',label:'SIP'},{k:'audio',label:'Audio'},
  {k:'calendar',label:'Kalender & Wetter'},{k:'backup',label:'Sicherung'}];

async function load(){
  const r = await fetch('/api/meta'); META = await r.json();
  PANELS = JSON.parse(JSON.stringify(META.panels||{}));
  GESPEICHERT = JSON.parse(JSON.stringify(META.panels||{}));
  if(!PANELS.default) PANELS.default = {title:'LoxPanel', tabs:defaultTabs(), rooms:[], cats:[], ui:{}, states:{}};
  PANELS.__global__ = {title:'Vorgaben (alle Ansichten)', ui: JSON.parse(JSON.stringify((META.theme||{}).ui||{})),
                       catColors: JSON.parse(JSON.stringify((META.theme||{}).categories||{})), __global:true};
  cur = PANELS.default ? 'default' : Object.keys(PANELS)[0];
  renderList(); setRubric('overview'); verbundenZeigen(); leisteZeigen();
}

function renderList(){
  const box=$('#plist'); box.innerHTML='';
  for(const id of Object.keys(PANELS)){
    if(id==='__global__') continue;
    const p=PANELS[id];
    const d=document.createElement('div');
    d.className='pitem'+(id===cur?' active':'');
    d.innerHTML='<span class="pn">'+esc(p.title||id)+'</span><span class="pid">?panel='+esc(id)+'</span>';
    d.onclick=()=>{ cur=id; tileSel=null; renderList(); setRubric('pconf'); };
    box.appendChild(d);
  }
}

// ---- Rubriken / Reiter-Steuerung ----
function setRubric(r){
  // Ersteinrichtung: ohne Struktur fuehrt jeder Weg zu Settings -> Miniserver
  if(EINR){ r='settings'; if(!EINR_SUBS.includes(subSet)) subSet='miniserver'; }
  rubric=r;
  if(r==='vorgaben'){ if(cur!=='__global__'){ letzteAnsicht=cur; cur='__global__'; tileSel=null; renderList(); } }
  else if(cur==='__global__'){ cur=(letzteAnsicht&&PANELS[letzteAnsicht])?letzteAnsicht:ersteAnsicht(); tileSel=null; renderList(); }
  document.querySelectorAll('.rub').forEach(b=>b.classList.toggle('active',b.dataset.rub===r));
  const ov=r==='overview', pc=r==='pconf', vg=r==='vorgaben', dv=r==='devices', dp=r==='displays';
  const oh=$('#overviewHost'); if(oh) oh.style.display = ov?'':'none';
  const dph=$('#displaysHost'); if(dph) dph.style.display = dp?'':'none';
  $('#pconfHost').style.display = (pc||vg)?'':'none';
  $('#setHost').style.display = (ov||pc||vg||dv||dp)?'none':'';
  $('#savebar').style.display = (ov||dv)?'none':'';   // eine Leiste fuer Ansichten, Geraete, Einstellungen
  $('#delSlot').style.display = pc?'':'none';
  $('#phead').style.display = (pc||vg)?'':'none';
  $('#subtabs').style.display = (ov||dv||dp)?'none':'';
  if(ov||dv||dp) return;
  if(pc||vg){ renderEditor(); }
  else { renderSubtabs(); showSub(subSet); }
}
function ersteAnsicht(){ return PANELS.default ? 'default' : (Object.keys(PANELS).find(k=>k!=='__global__')||null); }
document.querySelectorAll('.rub').forEach(b=>b.onclick=()=>setRubric(b.dataset.rub));
document.querySelectorAll('.ovbox').forEach(b=>b.onclick=()=>{
  const g=(b.dataset.goto||'').split(':'), r=g[0], sub=g[1];
  if(r==='wizard'){ geOpen(); return; }
  if(r==='verbinden'){ gvOpen(); return; }
  if(r==='pconf'||r==='vorgaben'||r==='settings'){ subMerken(r,sub);
    setRubric(r); renderSubtabs(); showSub(sub); }
  else { setRubric(r);   // overview/displays: keine Subtabs
    const d=sub && document.getElementById(sub);   // displays:<Abschnitt> klappt ihn auf
    if(d){ if(d.tagName==='DETAILS') d.open=true; d.scrollIntoView({block:'start'}); } }
});

function subTabs(){
  if(rubric==='settings') return SET_TABS;
  return rubric==='vorgaben' ? VG_TABS : PCONF_TABS;
}
function subAktiv(){ return rubric==='settings' ? subSet : (rubric==='vorgaben' ? subVg : subPconf); }
function subMerken(r,k){ if(r==='settings') subSet=k; else if(r==='vorgaben') subVg=k; else subPconf=k; }
function renderSubtabs(){
  const tabs=subTabs(), active=subAktiv();
  const bar=$('#subtabs');
  const zu=' disabled title="'+esc(T('Erst den Miniserver verbinden'))+'"';
  bar.innerHTML=tabs.map(t=>'<button class="stab'+(t.k===active?' active':'')+'" data-sub="'+t.k+'"'+
    (einrichtungGesperrt(t.k)?zu:'')+'>'+esc(t.label)+'</button>').join('');
  bar.querySelectorAll('.stab').forEach(b=>b.onclick=()=>{
    subMerken(rubric,b.dataset.sub);
    bar.querySelectorAll('.stab').forEach(x=>x.classList.toggle('active',x===b));
    showSub(b.dataset.sub);
  });
  if(window.I18N) I18N.autoChrome('.stab');
}
function showSub(k){
  const host = (rubric==='settings')?$('#setHost'):$('#pconfHost');
  if(!host) return;
  if(einrichtungGesperrt(k)) k='miniserver';
  const panes=host.querySelectorAll('.spane');
  let found=false;
  panes.forEach(p=>{ const on=p.dataset.sub===k; p.classList.toggle('active',on); if(on)found=true; });
  if(!found&&panes.length){ panes[0].classList.add('active'); }
  if(rubric==='settings'&&k==='sip') loadSip();
  if(rubric==='pconf'&&k==='seiten') seReiterZeichnen();   // Auswahl unter Inhalt inzwischen geaendert
}
