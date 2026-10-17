// LoxPanel-Visu, Teil 1 von 12: Symbole, Tabs, Zustand, Helfer, Weckton, Navigation, Intercom.
// Die Teile laden nacheinander aus panel.html (script src), alle Funktionen sind global;
// was beim Laden ausgefuehrt wird, darf nur Funktionen frueherer Teile rufen.

const ICONS = {
  folder:'<path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>',
  bulb:'<path d="M9 18h6"/><path d="M10 21h4"/><path d="M12 3a6 6 0 0 0-4 10.5c.7.8 1 1.4 1 2.5h6c0-1.1.3-1.7 1-2.5A6 6 0 0 0 12 3Z"/>',
  switch:'<rect x="3" y="7" width="18" height="10" rx="5"/><circle cx="8" cy="12" r="2.5"/>',
  mood:'<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M2 12h2M20 12h2M5 5l1.5 1.5M17.5 17.5 19 19M19 5l-1.5 1.5M6.5 17.5 5 19"/>',
  central:'<path d="M3 11 12 4l9 7"/><path d="M5 10v9a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-9"/>',
  info:'<circle cx="12" cy="12" r="9"/><path d="M12 8h.01M11 12h1v4h1"/>',
  blind:'<rect x="4" y="4" width="16" height="16" rx="1"/><path d="M4 9h16M4 13h16M4 17h16"/>',
  lamelle:'<path d="M4 4h16"/><path d="M5 8l14 3M5 12l14 3M5 16l14 3"/>',
  up:'<path d="m6 15 6-6 6 6"/>',
  down:'<path d="m6 9 6 6 6-6"/>',
  stop:'<rect x="6" y="6" width="12" height="12" rx="2"/>',
  // Gefuellte Dreiecke fuer die Tasten auf der Kachel (svgF): up/down sind
  // Linien und ergaeben gefuellt nur flache Keile.
  triup:'<path d="M12 6.5 19.5 17h-15z"/>',
  tridown:'<path d="M12 17.5 4.5 7h15z"/>',
  music:'<path d="M9 18V5l12-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="18" cy="16" r="3"/>',
  // zwei Finger, daneben hoch/runter: Hinweis-Symbol der Gesten
  zweiFinger:'<path d="M7 21v-9.5a1.5 1.5 0 0 1 3 0V21"/><path d="M10 21V8.5a1.5 1.5 0 0 1 3 0V21"/><path d="M18 3v10M16 5l2-2 2 2M16 11l2 2 2-2"/>',
  vol:'<path d="M4 9v6h4l5 4V5L8 9z"/><path d="M16 8a5 5 0 0 1 0 8"/>',
  prev:'<path d="M6 6h2v12H6zM20 6v12l-9-6z"/>',
  next:'<path d="M16 6h2v12h-2zM4 6l9 6-9 6z"/>',
  play:'<path d="M8 5v14l11-7z"/>',
  pause:'<path d="M7 5h3v14H7zM14 5h3v14h-3z"/>',
  alarm:'<path d="M18 8a6 6 0 0 0-12 0c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.7 21a2 2 0 0 1-3.4 0"/>',
  gate:'<path d="M3 10 12 4l9 6v11H3z"/><path d="M6 21v-7h12v7"/><path d="M6 17.5h12"/>',
  thermo:'<path d="M14 14.76V5a2 2 0 0 0-4 0v9.76a4 4 0 1 0 4 0Z"/>',
  fan:'<path d="M10.83 16.38a6.08 6.08 0 0 1-8.62-7l5.41 1.45a6.08 6.08 0 0 1 7-8.62l-1.45 5.41a6.08 6.08 0 0 1 8.62 7l-5.41-1.45a6.08 6.08 0 0 1-7 8.62l1.45-5.41Z"/><path d="M12 12v.01"/>',
  cam:'<rect x="2" y="6" width="14" height="12" rx="2"/><path d="m16 10 6-3v10l-6-3z"/>',
  // Hinweise der Hausseite (Server: _haus_hinweise, symbol): Fenster offen, Post da
  window:'<rect x="5" y="3" width="14" height="18" rx="1"/><path d="M12 3v18M5 12h14"/>',
  mail:'<rect x="3" y="6" width="18" height="13" rx="2"/><path d="m3 8 9 6 9-6"/>',
  list:'<path d="M8 6h13M8 12h13M8 18h13"/><path d="M3 6h.01M3 12h.01M3 18h.01"/>',
};
const TABS = [
  {tab:'favoriten', label:'Favoriten', icon:'<path d="m12 3 2.9 5.9 6.1.9-4.5 4.4 1 6.1L12 17.8 6.5 20.3l1-6.1L3 9.8l6.1-.9z"/>'},
  {tab:'zentral',   label:'Zentral',   icon:'<path d="M3 11 12 4l9 7"/><path d="M5 10v9a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-9"/>'},
  {tab:'raeume',    label:'Räume',     icon:'<rect x="4" y="4" width="16" height="16" rx="2"/><path d="M14 4v16"/>'},
  {tab:'kategorien',label:'Kategorien',icon:'<path d="m12 3 8 4.5v9L12 21l-8-4.5v-9z"/>'},
  // Kalender/Wetter als eigene Seite (FRONT_TABS im Server); Inhalt aus frontData
  {tab:'kalender',  label:'Kalender',  icon:'<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M3 10h18"/><path d="M8 3v4M16 3v4"/>'},
  {tab:'wetter',    label:'Wetter',    get icon(){ return WXI.sun; }},
  // Hausuebersicht (HAUS_TAB im Server, renderHaus)
  {tab:'haus',      label:'Haus',      icon:'<path d="M3 10.5 12 3l9 7.5"/><path d="M5 9v11h14V9"/><path d="M10 20v-6h4v6"/>'},
];

// Freie Bausteinauswahl: eine Seite je Panel, Name kommt per tabMeta vom
// Server (PICK_TAB in bin/webvisu.py). Muss mit dem Server uebereinstimmen.
const PICK_TAB = 'auswahl';
// Bis zu 4 freie Seiten: auswahl, auswahl2..auswahl4 (muss mit _pick_index in webvisu.py uebereinstimmen).
function isPick(t){ if(t===PICK_TAB) return true; if(typeof t==='string' && t.indexOf(PICK_TAB)===0){ const s=t.slice(PICK_TAB.length); return /^[2-4]$/.test(s); } return false; }

const el = id => document.getElementById(id);
let ws, stack = [{view:'tab',tab:'favoriten'}], view = null;
// Touch-Panel: nach der ersten Beruehrung den Mauszeiger ausblenden (Desktop-Maus bleibt)
addEventListener('touchstart', ()=>document.body.classList.add('touch'), {once:true, passive:true});
let tabsCfg = ['favoriten','zentral','raeume','kategorien'];
let tabMeta = {};   // Label/Icon fuer dynamische Tabs (Kategorien), vom Server
let gridCols = 2;   // effektive Spalten der aktuellen Ansicht (Vollbreit-Pane -> 4)
let gridRows = 2;   // effektive sichtbare Zeilen pro Seite (hochkant Vollbreit -> 4)
let profCols = 2, profRows = 2;   // Profil-Standard (aus dem Theme); Vollbreit ueberschreibt auf 4x2 bzw. 2x4
let _lastRaster = null, _lastWidget = false;   // zuletzt gerenderte Lage + Raster (fuer resize-Nachzug, s. render())
let _playerBuilt = false, _playerVolDrag = false;   // fester Player (Split-Layout)
// Split-Pane pro Tab: panesCfg = {tabKennung -> "weather"|"calendar"|"wide"|"player:<zone>"|"energy:<uuid>"|"camera:<uuid>"}
// (vom Server). themeFill = "Bildschirm fuellen" (gilt jetzt auch im Split).
// curPlayerZone = zuletzt an den Server gemeldete Player-Zone (setplayer).
let panesCfg = {}, themeFill = false, curPlayerZone = '', curEnergyUuid = '', curCameraUuid = '';
// Rechte Spalte der Uhr-Seite (Screensaver), Einstellung je Panel; svStatusData
// sind die Werte der frei gewaehlten Bausteine ({t:'svstatus'} vom Server).
let svPaneCfg = '', svStatusData = null, curSvStatus = '';
let cameraData = null;   // letzter {t:'camera'}-Push (Intercom-Bloecke) fuer die Kamera-Pane
let energyData = null;   // letzter {t:'energy'}-Push fuer die Energiefluss-Pane
let playerData = null;   // letzter {t:'player'}-Push (Player-Bloecke) fuer die Audio-Pane
let playerSecured = false;   // Zone des Players ist gesichert (Visu-PIN)
// Verlaufs-Pane (chart:<uuid>): gemeldeter Baustein|Zeitraum, letzter {t:'chart'}-Push,
// in der Pane gewaehlter Zeitraum (gilt fuer alle Verlaufs-Panes dieses Panels).
let curChartKey = '', chartData = null, chartRange = '24h';
// Die Kennungen oben sind die zuletzt gemeldeten Abos (set*). Der Server fuehrt
// sie je Verbindung und raeumt sie ab, wenn sie endet (ws_handler, _send_or_drop).
// Nach jedem Verbindungsaufbau gelten sie darum als nicht gemeldet; der
// theme-Push ruft danach applyPane(), das alle aktiven neu anmeldet. Aufruf in
// ws.onopen, nicht in onclose: send() verwirft ohne Verbindung, ein Wechsel in
// der Trennung setzte die Kennung sonst, ohne dass der Server davon erfaehrt.
// Ein neues Abo mit eigener Kennung gehoert hier hinein.
function abosVergessen(){ curEnergyUuid=''; curCameraUuid=''; curPlayerZone=''; curSvStatus=''; curChartKey=''; }
let themeSplit = true;   // Split-Screen an/aus (aus = 4"-Panel: nur die Visu, keine Pane 2)
let tileLayout = '';     // Kachel-Aufbau: '' = neu (Standard), 'classic' = der bisherige
// Kachel-Set (theme-Nachricht): Art der Kachel ('lx'|'mitte'|'kreis') und der
// Tab-Leiste ('pille'|'oben'|'links'), '' ohne Set. Als data-kachelset-aufbau
// und data-kachelset-leiste am <html>; daran haengen die Regeln im CSS.
let kachelAufbau = '', kachelLeiste = '';
let kachelMasse = {};   // Variablen der theme-Nachricht (Masse des Sets fuer raster.js leisteMass)
let _themeVars = [];     // Variablen der letzten theme-Nachricht (s. dort)
// Stand des Servers (Commit, theme-Nachricht "stand"), den die erste
// Verbindung meldet. Meldet ein neu gestarteter Server nach dem Wiederverbinden
// einen anderen, laeuft hier noch HTML/JS des alten: die Seite laedt neu.
let serverStand = null;
function serverStandPruefen(st){
  if(!st) return false;
  if(serverStand===null){ serverStand=st; return false; }
  if(st===serverStand) return false;
  location.reload();
  return true;
}
let gridAuto = 0;        // automatisches Raster: Zielgroesse einer Kachel in px (vom Server), 0 = festes Raster
let gridGrow = 1;        // ... bis zu diesem Vielfachen wachsen die Kacheln, wenn alle auf eine Seite passen (vom Server)
let paneCols = 0;        // Widget im automatischen Raster: feste Breite in Kachelspalten (hochkant Zeilen), 0 = Automatik (vom Server)
let paneShare = 0;       // ... Anteil der Spalten in der Automatik (PANE_ANTEIL vom Server)

function svg(inner){return '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">'+inner+'</svg>';}
function svgF(inner){return '<svg viewBox="0 0 24 24" fill="currentColor">'+inner+'</svg>';}
let sldDragging=false;
function esc(s){return (s==null?'':String(s)).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
function key(r){return JSON.stringify(r||{});}

// ---- Weckton (Loxone-Wecker klingelt) ----
// Synthetischer Piep-Loop per Web Audio API: kein Audio-Asset noetig, laeuft bis
// der Server das Ende meldet ({t:'alarm',on:false}, nach 'dismiss' in Loxone/App
// oder ueber den "Wecker aus"-Button am Panel). Der Kiosk startet Chromium mit
// --autoplay-policy=no-user-gesture-required, darum spielt der Ton ohne vorherige
// Nutzergeste. Zusaetzlich ein Failsafe, der nach 5 Min stoppt, falls das
// Aus-Event mal ausbleibt (sonst piepte das Panel endlos).
let _actx=null, _alarmTimer=null, _alarmFailsafe=null;
function startAlarmTone(){
  if(_alarmTimer) return;               // laeuft schon
  try{
    _actx = _actx || new (window.AudioContext||window.webkitAudioContext)();
    if(_actx.state==='suspended') _actx.resume();
    const beep=()=>{
      const t=_actx.currentTime, o=_actx.createOscillator(), g=_actx.createGain();
      o.type='square'; o.frequency.value=880;
      g.gain.setValueAtTime(0.0001,t);
      g.gain.exponentialRampToValueAtTime(0.35,t+0.02);
      g.gain.exponentialRampToValueAtTime(0.0001,t+0.4);
      o.connect(g); g.connect(_actx.destination);
      o.start(t); o.stop(t+0.45);
    };
    beep();
    _alarmTimer=setInterval(beep,700);
    clearTimeout(_alarmFailsafe);
    _alarmFailsafe=setTimeout(stopAlarmTone,5*60*1000);
  }catch(e){}
}
function stopAlarmTone(){
  if(_alarmTimer){ clearInterval(_alarmTimer); _alarmTimer=null; }
  clearTimeout(_alarmFailsafe); _alarmFailsafe=null;
}
// Sichtbarer Hinweis oben am Panel — bestaetigt, dass ein Test-Ton-Event
// tatsaechlich ankam, und meldet den AudioContext-Status. So laesst sich
// "Push kommt nicht an" von "Audio-Ausgabe stumm" trennen.
function flashAudioBadge(txt, ok){
  let b=document.getElementById('audiobadge');
  if(!b){
    b=document.createElement('div'); b.id='audiobadge';
    b.style.cssText='position:fixed;top:16px;left:50%;transform:translateX(-50%);z-index:99999;'+
      'padding:13px 20px;border-radius:12px;font:600 15px system-ui,sans-serif;color:#fff;'+
      'box-shadow:0 8px 28px rgba(0,0,0,.45);pointer-events:none;opacity:0;transition:opacity .3s;max-width:90vw;text-align:center;';
    document.body.appendChild(b);
  }
  b.textContent=txt;
  b.style.background = ok ? 'rgba(82,184,129,.96)' : 'rgba(226,107,95,.96)';
  b.style.opacity='1';
  clearTimeout(b._t); b._t=setTimeout(()=>{ b.style.opacity='0'; }, 3500);
}
// Kurzer Test-Ton (3 Pieptoene) von der Einstellungen-Seite ausgeloest. Eigener
// AudioContext (stoert einen evtl. laufenden echten Weckton nicht). resume()
// wird abgewartet, damit der Ton auch bei anfangs suspendiertem Context spielt;
// der Badge meldet, ob der Context wirklich laeuft.
function playTestTone(){
  let actx;
  try{ actx=new (window.AudioContext||window.webkitAudioContext)(); }
  catch(e){ flashAudioBadge('🔊 Test-Ton empfangen — Web Audio nicht verfügbar', false); return; }
  const boom=()=>{
    try{
      let t=actx.currentTime;
      for(let i=0;i<3;i++){
        const o=actx.createOscillator(), g=actx.createGain();
        o.type='square'; o.frequency.value=880;
        g.gain.setValueAtTime(0.0001,t);
        g.gain.exponentialRampToValueAtTime(0.4,t+0.02);
        g.gain.exponentialRampToValueAtTime(0.0001,t+0.35);
        o.connect(g); g.connect(actx.destination);
        o.start(t); o.stop(t+0.4); t+=0.5;
      }
    }catch(e){}
    const running = actx.state==='running';
    flashAudioBadge(running ? '🔊 Test-Ton — Audio läuft' : '🔊 empfangen, Audio blockiert ('+actx.state+')', running);
    setTimeout(()=>{ try{ actx.close(); }catch(e){} }, 2200);
  };
  if(actx.state==='suspended'){ actx.resume().then(boom, boom); }
  else boom();
}

function send(o){ ws && ws.readyState===1 && ws.send(JSON.stringify(o)); }
function nav(route){ stack.push(route); send({t:'nav',route}); }
function goTab(tab){ stack=[{view:'tab',tab}]; send({t:'nav',route:stack[0]}); }
function back(){ if(stack.length>1){ stack.pop(); send({t:'nav',route:stack[stack.length-1]}); } }

// Gegensprechen ist eine native Faehigkeit der LoxPanel-App. Der Server nennt
// nur die Baustein-UUID; SIP-Zugang und Audio bleiben in der App. Beide Panes
// teilen einen Status, der ausschliesslich die Sprech-Bedienung aktualisiert.
function intercomNative(){
  const b=window.LoxKiosk;
  return !!(b && typeof b.startIntercom==='function' && typeof b.stopIntercom==='function'
    && typeof b.intercomStatus==='function'); }
function intercomBlocks(blocks){ return blocks.filter(b=>
  !(b.nativeOnly || b.k==='intercom-talk') || intercomNative()); }
let intercomState={state:'idle',uuid:'',message:''}, intercomReadAt=0;
const INTERCOM_ACTIVE=['connecting','connected','ending'];
const INTERCOM_TEXT={idle:'',connecting:'Verbindung wird aufgebaut …',connected:'Gespräch verbunden',
  ending:'Gespräch wird beendet …',error:'Gegensprechen ist derzeit nicht verfügbar'};
function intercomRead(force){
  if(!intercomNative() || (!force && Date.now()-intercomReadAt<500)) return;
  intercomReadAt=Date.now();
  try{
    const s=JSON.parse(LoxKiosk.intercomStatus());
    if(!s || !Object.prototype.hasOwnProperty.call(INTERCOM_TEXT,s.state)
      || typeof s.uuid!=='string' || typeof s.message!=='string') throw new Error('Status');
    intercomState={state:s.state,uuid:s.uuid,message:s.message.slice(0,240)};
  }catch(e){ intercomState={state:'error',uuid:'',message:INTERCOM_TEXT.error}; }
}
function intercomTalkHtml(b){ return '<div class="intercom-talk" data-intercom="'+esc(b.uuid)+'">'+
  '<button type="button" class="btn intercom-talk-button">Sprechen</button>'+
  '<div class="intercom-talk-status" role="status" hidden></div></div>'; }
function intercomPaint(){
  const s=intercomState, active=INTERCOM_ACTIVE.includes(s.state);
  document.querySelectorAll('.intercom-talk').forEach(e=>{
    const own=s.uuid===e.dataset.intercom, other=active&&!own;
    const btn=e.querySelector('.intercom-talk-button'), status=e.querySelector('.intercom-talk-status');
    btn.textContent=active&&own?'Auflegen':'Sprechen';
    btn.disabled=other || (own&&s.state==='ending');
    btn.classList.toggle('on',active&&own);
    const text=other?'Gespräch an anderer Türstation':
      (own || !s.uuid ? s.message||INTERCOM_TEXT[s.state] : '');
    status.textContent=text; status.hidden=!text;
    e.classList.toggle('error',s.state==='error'&&(own||!s.uuid));
  });
}
function intercomTalk(uuid){
  if(!intercomNative()) return;
  intercomRead(true);
  const active=INTERCOM_ACTIVE.includes(intercomState.state);
  if((active&&intercomState.uuid!==uuid) || intercomState.state==='ending'){ intercomPaint(); return; }
  let accepted=false;
  try{ accepted=active?LoxKiosk.stopIntercom():LoxKiosk.startIntercom(uuid); }catch(e){}
  if(accepted===true){
    // Die Bruecke fuehrt den Auftrag auf dem App-Thread aus. Bis zur naechsten
    // Statusabfrage bleibt ein zweiter Tipp daher bereits als Auflegen sichtbar.
    intercomState={state:active?'ending':'connecting',uuid,message:''}; intercomReadAt=Date.now();
  }else{
    intercomRead(true);
    if(INTERCOM_ACTIVE.includes(intercomState.state)){
      if(intercomState.uuid===uuid) intercomState.message='Gespräch konnte nicht beendet werden';
    }else if(intercomState.state!=='error') intercomState={state:'error',uuid,message:INTERCOM_TEXT.error};
  }
  intercomPaint();
}
function intercomBind(container){
  const talks=container.querySelectorAll('.intercom-talk');
  if(!talks.length) return;
  talks.forEach(e=>{
    const btn=e.querySelector('.intercom-talk-button');
    if(!btn._intercomBound){ btn._intercomBound=true; btn.addEventListener('click',()=>intercomTalk(e.dataset.intercom)); }
  });
  intercomRead(false); intercomPaint();
}
setInterval(()=>{
  if(!document.querySelector('.intercom-talk')) return;
  intercomRead(true); intercomPaint();
},500);
// Die App gibt die Bruecke erst dem fertig geladenen, lokalen Hauptdokument.
// Bereits laufendes Video bei dieser Freigabe ebenfalls unangetastet lassen.
window.addEventListener('loxpanel-intercom-ready',()=>{
  if(!intercomNative()) return;
  const g=el('grid'), talk=view&&view.blocks&&intercomBlocks(view.blocks).find(b=>b.k==='intercom-talk');
  if(g && g.classList.contains('panel') && talk && !g.querySelector('.intercom-talk')){
    const ring=g.querySelector('[data-rowid="klingel"]');
    if(ring) ring.insertAdjacentHTML('beforebegin',intercomTalkHtml(talk));
    else g.insertAdjacentHTML('beforeend',intercomTalkHtml(talk));
    g.classList.add('intercom-page'); g.dataset.bsig=blockSig(view.blocks);
    intercomBind(g); panelEinpassen();
  }
  const fp=el('frontpane');
  if(fp && paneKind(paneRawNow())==='camera') renderCameraPane(fp);
});

