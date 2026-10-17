// LoxPanel-Konfigurator, Teil 9 von 11: Geraete: Karten, neues Geraet, Betriebsmodus-Automatik und -Assistent.
// Die Teile laden nacheinander aus config.html (script src), alle Funktionen sind global;
// was beim Laden ausgefuehrt wird, darf nur Funktionen frueherer Teile rufen.

// ---- Panels (alle Anzeigegeraete: Agent, Kiosk-App, Browser) ----
let PANEL_IDS=[];
let DEV={};            // Panel-Name -> {auto, modes:[[modus,profil],...], display}  (Arbeitskopie)
let GER_GESPEICHERT={}; // zuletzt gespeicherte Geraeteliste (Form von devicesPayload) - fuer "Entfernen"
let KNOWN_NAMES=[];    // bisher gesehene Geraetenamen (Agent ODER Browser ?device=)
let DEVICE_IPS={};     // Geraetename -> zuletzt gesehene IP (Vorbelegung Display-Treiber)
let DEVICE_ZUORDNUNG={}; // Geraetename -> zugeordnete Ansicht (devices[name].panel, Schritt 2)
let DEVICE_SUGGEST={}; // Geraetename -> Vorschlag Zielkachel px aus der gemeldeten Groesse (/api/devices tileSuggest)
let DEVICE_SCREENS={}; // Geraetename -> gemeldete Bildschirmgroesse (fuer den Hinweis zum Vorschlag)
let DEVICE_CONN={};    // Geraetename -> Anzahl verbundener Visus (Vorschau am Geraet braucht eine)
let DEVICE_VORSCHAU={}; // Geraetename -> {id, bis}, solange das Geraet einen Entwurf zeigt
let ANON_DEVICES=[];   // verbundene Geraete ohne Namen (nach IP), zuletzt von /api/devices
let LICHT_OPTS=[];     // Lichtsteuerungen mit Stimmungen (Stimmung beim Einschalten), aus /api/meta
let ACTIVE_OPTS=[];    // Bausteine mit active-State (Auswahl Praesenzmelder), aus /api/meta
let PRESENCE_NOW={};   // Geraetename -> meldet sein Praesenzmelder gerade jemanden? (aus /api/devices)
let PASS_ZIEL={};      // Geraetename -> {driver, host}, fuer das der Server ein Display-Kennwort hat
// Das Kennwort selbst bekommt der Konfigurator nie, nur hasPass (wie beim Miniserver).
function passZielLesen(devices){
  PASS_ZIEL={};
  Object.entries(devices||{}).forEach(([name,d])=>{
    if(d && d.display && d.display.hasPass) PASS_ZIEL[name]={driver:d.display.driver, host:d.display.host};
  });
}
async function loadPanelIds(){
  try{
    const r=await fetch('/api/meta'); const m=await r.json();
    PANEL_IDS=Object.keys(m.panels||{});
    ACTIVE_OPTS=Array.isArray(m.activeControls)?m.activeControls:[];
    LICHT_OPTS=Array.isArray(m.lichtStimmungen)?m.lichtStimmungen:[];
    passZielLesen(m.devices);
    GER_GESPEICHERT=devicesPayload(devAusServer(m.devices));
    // Offene Eingaben unter Geraete bleiben: nur uebernehmen, was im Editor steht
    if(OFFEN.has('geraete')) readDevFromDom(); else DEV=devAusServer(m.devices);
  }catch(e){ PANEL_IDS=[]; }
}
// Geraete, wie der Server sie liefert (/api/meta, Antwort von /api/devices) -> Arbeitskopie
function devAusServer(devices){
  const out={};
  Object.entries(devices||{}).forEach(([name,d])=>{
    out[name]={auto:d.auto!==false, modes:Object.entries(d.modes||{}), display:d.display||null,
               scale:(d.scale===undefined?'':d.scale),   // '' = wie in der Ansicht
               presence:d.presence||'',                  // '' = kein Praesenzmelder
               tileTarget:d.tileTarget||'',               // '' = Zielkachel wie in der Ansicht
               dpmsOff:(d.dpmsOff===undefined||d.dpmsOff===null)?'':d.dpmsOff,   // '' = Ansicht oder Vorgaben (Schritt 4)
               nightDim:(d.nightDim===undefined||d.nightDim===null)?'':d.nightDim,   // Nacht am Geraet (Schritt 4b)
               nightWake:(d.nightWake===undefined||d.nightWake===null)?'':d.nightWake,
               lichtStart:lichtStartWert(d.lichtStart)};  // '' = erste Stimmung im Raum
  });
  return out;
}
const TYPE_LABEL={agent:'Agent', fully:'Fully Kiosk', loxpanel:'LoxPanel-App', browser:'Browser'};
function profSelect(cls, cur){
  return '<select class="'+cls+'"><option value="">'+T('(Standard)')+'</option>'+
    PANEL_IDS.map(id=>'<option value="'+esc(id)+'"'+(cur===id?' selected':'')+'>'+esc(id)+'</option>').join('')+'</select>';
}
// Kopf der Karte: Zustand, Name, Typ, Adresse und die Steuerung des Geraets. Welche
// Ansicht es zeigt, steht in der Zeile "Zeigt" darunter (zeigtHtml), Entfernen in der
// letzten Zeile (Einrichtung neu, Schritt 4).
function deviceRow(d){
  const info=[d.ip, (d.agent&&d.agent.kiosk)?T('Kiosk läuft'):'', d.connections?T('Visu offen'):''].filter(Boolean).join(' · ');
  let btns='';
  if(d.connections) btns+='<button class="btn sm ghost" data-act="wsreload">'+T('Neu laden')+'</button>';
  // Kiosk-Apps schalten das Display aus der Seite heraus (Fully Kiosk, LoxPanel-App)
  if(d.type==='fully'||d.type==='loxpanel') btns+='<button class="btn sm ghost" data-act="dispoff">'+T('Display aus')+'</button>'+
                             '<button class="btn sm ghost" data-act="dispon">'+T('Display an')+'</button>';
  if(d.agent) btns+='<button class="btn sm'+(d.connections?' ghost':'')+'" data-act="start">'+T('Start')+'</button>'+
                    '<button class="btn sm ghost" data-act="reload">'+T('Reload')+'</button>'+
                    '<button class="btn sm ghost" data-act="stop">'+T('Stop')+'</button>';
  // Diagnosepaket dieses Geraets (ZIP, /api/diagnose) - auch offline
  btns+='<a class="btn sm ghost" data-diagnose href="/api/diagnose?device='+encodeURIComponent(d.name)+'" download>'+T('Diagnose')+'</a>';
  return '<div class="ag" data-name="'+esc(d.name)+'" data-ip="'+esc(d.agent?d.agent.ip:'')+'">'+
    '<span class="dot'+(d.online?' on':'')+'"></span>'+
    '<span class="agn">'+esc(d.name)+'</span>'+
    '<span class="tag">'+esc(TYPE_LABEL[d.type]||d.type)+'</span>'+
    '<span class="agip">'+esc(info)+'</span>'+
    '<span class="sp"></span>'+btns+
    (screenInfo(d.screen)?'<div class="agscr">'+esc(screenInfo(d.screen))+'</div>':'')+'</div>';
}
// Das Geraet der letzten Abfrage, sonst ein Platzhalter (steht in panels.json, hat sich nie gemeldet)
function geraetDaten(name){
  return GERAETE_LISTE.find(d=>d.name===name) || {name:name, online:false, configured:!!GER_GESPEICHERT[name], profile:'',
    zugeordnet:(DEVICE_ZUORDNUNG[name]||''), type:'browser', connections:0, agent:null, ip:'', screen:null};
}
// ---- Die fuenf Zeilen der Karte (Einrichtung neu, Schritt 4) ----
function gzZeile(key, name, wert, woher, aktion){
  return '<div class="gz" data-gz="'+key+'"><div class="gz-name">'+esc(name)+'</div><div class="gz-mitte">'+
    '<div class="gz-wert">'+wert+'</div><div class="gz-woher">'+esc(woher)+'</div></div><div class="gz-aktion">'+aktion+'</div></div>';
}
function gzAufKnopf(key, name, auf){
  return '<button type="button" class="btn sm ghost gz-auf" data-gz="'+key+'" aria-expanded="'+(auf?'true':'false')+'">'+esc(name)+' '+(auf?'▾':'▸')+'</button>';
}
// Zeile "Zeigt": Auswahl der Ansicht (schaltet live, Zuordnung nach Schritt 2) und Feinschliff
function zeigtHtml(name, d, sel){
  const cur=(sel!==undefined)?sel:(d.profile||d.zugeordnet||'');
  const id=geraetAnsicht(name), p=PANELS[id]||null, teile=[];
  if(p){ teile.push(T('Ansicht')+' „'+id+'“');
    const ui=p.ui||{}; teile.push(T('Raster')+' '+(layoutWert(ui)==='auto'?T('automatisch'):layoutWert(ui).replace('x',' × ')));
    const ks=kachelSetMeta(ui.tileSet||vorgabeWert('tileSet')); teile.push(T('Set')+' '+(ks?T(ks.label):T('Standard'))+(ui.tileSet?'':' · '+T('aus den Vorgaben'))); }
  else teile.push(d.online ? T('zeigt die Standardansicht, noch keine zugeordnet') : T('noch nicht gemeldet'));
  if(d.profile && d.zugeordnet && d.profile!==d.zugeordnet) teile.push(T('gerade durch einen Betriebsmodus: {a}').replace('{a}', ansichtName(d.profile)));
  return gzZeile('zeigt', T('Zeigt'), profSelect('agsel', cur)+'<button class="btn sm" data-act="switch">'+T('Ansicht wechseln')+'</button>',
    teile.join(' · '), (p?'<button type="button" class="btn sm gz-fein" data-fein="'+esc(id)+'">'+T('Feinschliff ›')+'</button>':'')+gzAufKnopf('zeigt', T('Gesten'), GK_AUF.has(name+'/zeigt')));
}
// Was fuer "Display aus nach" am Geraet gilt: Geraet, sonst die Ansicht, sonst Vorgaben, sonst Standard
function displayGilt(name){ return geraetGilt(name, 'dpmsOff'); }
function presenceName(uuid){
  const o=ACTIVE_OPTS.find(x=>x.uuid===uuid); return o ? ((o.room?o.room+' · ':'')+o.name) : uuid;
}
function displayHtml(name){
  const d=DEV[name]||{}, w=displayGilt(name), n=geraetGilt(name, 'nightDim');
  const aus=gesetzt(w.v) ? (Number(w.v)===0 ? T('Display bleibt an') : T('Aus nach {s} s').replace('{s}', fmtZahl(w.v))) : wertText('dpmsOff', null);
  const nacht=(gesetzt(n.v) && Number(n.v)>0) ? T('nachts {p} % dunkler').replace('{p}', fmtZahl(n.v)) : T('nachts nicht abgedunkelt');
  const wert=aus+' · '+nacht;
  const woher=[T('Display aus')+': '+w.quelle, T('Nacht')+': '+n.quelle,
    d.presence ? T('Präsenzmelder')+' '+presenceName(d.presence)+(presenceText(name)?' ('+presenceText(name)+')':'') : T('kein Präsenzmelder')].join(' · ');
  return gzZeile('display', T('Display'), esc(wert), woher, gzAufKnopf('display', T('Ändern'), GK_AUF.has(name+'/display')));
}
function modiHtml(name){
  const d=DEV[name]||{auto:true, modes:[]}, modi=(d.modes||[]).filter(([m,p])=>m&&p);
  const wert=modi.length ? modi.map(([m,p])=>m+' → '+ansichtName(p)).join(' · ')+(d.auto===false?' ('+T('Automatik aus')+')':'') : T('Keine');
  const woher=modi.length ? T('Loxone schaltet die Ansicht über /api/mode/<modus> um; „Ansicht wechseln“ hebt den Modus für dieses Gerät auf.')
    : T('Erst nötig, wenn Loxone die Ansicht umschalten soll (Gäste, Nacht, Urlaub).');
  return gzZeile('modi', T('Betriebsmodi'), esc(wert), woher, gzAufKnopf('modi', modi.length?T('Ändern'):T('Einrichten'), GK_AUF.has(name+'/modi')));
}
function technikHtml(name, d){
  const e=DEV[name]||{}, disp=e.display||{};
  const typ=TYPE_LABEL[d.type]||d.type||T('Browser');
  const ueber=disp.driver==='fully' ? T('Display über Fully Kiosk (Remote Admin)') : disp.driver==='wallpanel' ? T('Display über WallPanel (HTTP)')
    : d.type==='loxpanel' ? T('Display über die App') : d.type==='agent' ? T('Display über den Agenten') : d.type==='fully' ? T('Display über die Seite (JavaScript-Schnittstelle)') : T('kein Display-Treiber');
  const id=geraetAnsicht(name), auto=!!id && layoutWert((PANELS[id]||{}).ui)==='auto';
  const skal=gesetzt(e.scale) ? scaleName(e.scale)+' ('+T('am Gerät')+')' : (id ? giltText('scale', wasGiltInAnsicht(id,'scale')) : T('wie in der Ansicht'));
  const ziel=parseInt(e.tileTarget)>0 ? fmtZahl(e.tileTarget)+' px ('+T('am Gerät')+')' : (auto ? giltText('tileSize', wasGiltInAnsicht(id,'tileSize')) : T('nur bei Raster „Automatisch“'));
  return gzZeile('technik', T('Technik'), esc(typ)+' <span class="gz-neben">· '+esc(ueber)+'</span>',
    T('Skalierung')+' '+skal+' · '+T('Zielkachel')+' '+ziel, gzAufKnopf('technik', T('Ändern'), GK_AUF.has(name+'/technik')));
}
function entfernenHtml(name, d){
  const id=DEVICE_ZUORDNUNG[name]||'';
  const woher=d.configured ? (id ? T('Die Ansicht „{a}“ bleibt bestehen.').replace('{a}', ansichtName(id))+' ' : '')+
      T('Betriebsmodi, Display-Treiber, Skalierung, Zielkachel und Präsenzmelder gehen verloren; gilt sofort.')
    : T('Ein Gerät ohne Einstellungen verschwindet von selbst, sobald es nicht mehr verbunden ist.');
  return gzZeile('entfernen', T('Entfernen'), esc(T('Gerät aus der Liste nehmen')), woher,
    d.configured ? '<button class="btn sm del" data-act="entfernen" data-online="'+(d.online?1:0)+'">'+T('Entfernen')+'</button>' : '');
}
// Geraet ohne Namen: der Kopplungscode (das Panel zeigt ihn unter "Dieses
// Geraet einrichten") ist der Schluessel der Zeile, "Namen vergeben" trifft
// damit genau dieses Geraet - auch bei mehreren hinter einer IP.
function anonKey(a){ return a.code||a.ip; }
function anonRow(a, typed){
  const info=[a.ip, TYPE_LABEL[a.kiosk]||T('Browser'), a.profile?(T('Ansicht')+' '+a.profile):'', screenInfo(a.screen)].filter(Boolean).join(' · ');
  return '<div class="ag" data-anon="'+esc(anonKey(a))+'" data-ip="'+esc(a.ip)+'" data-code="'+esc(a.code||'')+'">'+
    '<span class="dot on"></span><span class="agn">'+(a.code?(T('Code')+' '+esc(a.code)):T('Ohne Namen'))+'</span>'+
    '<span class="agip">'+esc(info)+'</span><span class="sp"></span>'+
    '<input type="text" class="anname" placeholder="'+T('Gerätename')+'" value="'+esc(typed||'')+'" style="max-width:180px">'+
    '<button class="btn sm" data-act="name">'+T('Namen vergeben')+'</button></div>';
}
// Eine Karte je Geraet (Konzept "Konfigurator neu ordnen", Schritt 4): der Kopf
// (Zustand, Ansicht, Steuerung) folgt der Abfrage alle paar Sekunden, darunter
// stehen aufklappbar die Einstellungen (renderDevices). Beide zeichnen getrennt,
// so faehrt die Abfrage nie in ein Feld, in dem jemand tippt.
let GERAETE_LISTE=[];     // benannte Geraete der letzten Abfrage von /api/devices
const GK_AUF=new Set();   // aufgeklappte Editoren ("<geraet>/<zeile>"), bleiben beim Neuzeichnen offen
function alleGeraeteNamen(){
  return Array.from(new Set(GERAETE_LISTE.map(d=>d.name).filter(Boolean).concat(KNOWN_NAMES, Object.keys(DEV)))).sort();
}
// Karten in Namensfolge: fehlende anlegen, weggefallene entfernen -> Namen
function geraeteKarten(){
  const box=$('#geraete'); if(!box) return [];
  const soll=alleGeraeteNamen();
  box.querySelectorAll(':scope > :not(.gk)').forEach(n=>n.remove());
  box.querySelectorAll(':scope > .gk').forEach(k=>{ if(soll.indexOf(k.dataset.gk)<0) k.remove(); });
  soll.forEach((n,i)=>{
    let k=box.querySelector(':scope > .gk[data-gk="'+CSS.escape(n)+'"]');
    if(!k){
      k=document.createElement('div'); k.className='card gk'; k.dataset.gk=n;
      k.innerHTML='<div class="gk-kopf"></div><div class="gk-body"></div>';
    }
    if(box.children[i]!==k) box.insertBefore(k, box.children[i]||null);
  });
  if(!soll.length) box.innerHTML='<div class="muted">'+esc(T('Noch kein Gerät gefunden. Ein Gerät erscheint, sobald es die Visu mit ?device=<name> öffnet oder der Agent darauf läuft.'))+'</div>';
  return soll;
}
// Kopf eines Geraets, das in panels.json steht, aber nicht in der Abfrage
function kopfOhneMeldung(name){
  return '<div class="ag" data-name="'+esc(name)+'" data-ip=""><span class="dot"></span>'+
    '<span class="agn">'+esc(name)+'</span><span class="agip">'+esc(T('noch nicht gemeldet'))+'</span></div>';
}
// Knoepfe der Karte (Kopf und Zeilen): Steuerung, Ansicht wechseln (Auswahl der Zeile
// "Zeigt"), Entfernen, Feinschliff (Editor der Ansicht)
function gkAktionenBinden(k, wurzel){
  const name=k.dataset.gk, ag=k.querySelector('.gk-kopf .ag');
  wurzel.querySelectorAll('button[data-act]').forEach(b=>{
    b.onclick=()=>{ const s=k.querySelector('.agsel');
      if(b.dataset.act==='entfernen') devEntfernen(name, b.dataset.online==='1');
      else deviceAction(b.dataset.act, name, ag?ag.dataset.ip:'', s?s.value:''); }; });
  wurzel.querySelectorAll('[data-fein]').forEach(b=>{ b.onclick=()=>{ cur=b.dataset.fein; tileSel=null; renderList(); setRubric('pconf'); }; });
}
// Kopf und Zeile "Zeigt" folgen der Abfrage (nicht, wo gerade jemand waehlt)
function koepfeZeichnen(){
  const box=$('#geraete'); if(!box) return;
  const f=document.activeElement;
  const fk=(f && f.tagName!=='BUTTON' && f.closest) ? (f.closest('.gk-kopf') || f.closest('.gz[data-gz="zeigt"]')) : null;
  box.querySelectorAll(':scope > .gk').forEach(k=>{
    const kopf=k.querySelector('.gk-kopf'), d=geraetDaten(k.dataset.gk);
    if(kopf!==fk){ kopf.innerHTML = GERAETE_LISTE.some(x=>x.name===k.dataset.gk) ? deviceRow(d) : kopfOhneMeldung(k.dataset.gk); gkAktionenBinden(k, kopf); }
    const z=k.querySelector('.gz[data-gz="zeigt"]');
    if(z && z!==fk){ const s=z.querySelector('.agsel'); const neu=document.createElement('div'); neu.innerHTML=zeigtHtml(k.dataset.gk, d, s?s.value:undefined);
      z.replaceWith(neu.firstChild); gkAktionenBinden(k, k.querySelector('.gz[data-gz="zeigt"]')); }
    gzWerteZeichnen(k);   // Display, Betriebsmodi, Technik, Entfernen: Herkunft folgt der Ansicht und der Zuordnung
  });
}
function renderDeviceList(j){
  GERAETE_LISTE=j.devices||[];
  geraeteKarten(); koepfeZeichnen(); geraetErbtZeichnen();
  // Geraete ohne Namen: eigener Abschnitt unter den Karten
  const anon=j.anonymous||[], ab=$('#ag_anon'), ak=$('#ag_anon_karte');
  if(ak) ak.hidden=!anon.length;
  if(!ab) return;
  const f=document.activeElement;
  if(f && f.tagName!=='BUTTON' && ab.contains(f)) return;   // jemand tippt einen Namen
  const prevName={};
  ab.querySelectorAll('.ag[data-anon]').forEach(n=>{ const i=n.querySelector('.anname'); if(i) prevName[n.dataset.anon]=i.value; });
  ab.innerHTML=anon.map(a=>anonRow(a,prevName[anonKey(a)])).join('');
  ab.querySelectorAll('.ag[data-anon] button[data-act="name"]').forEach(b=>{
    const row=b.closest('.ag');
    b.onclick=()=>nameDevice(row.dataset.ip, row.querySelector('.anname').value.trim(), row.dataset.code);
  });
}
async function postJson(url, body){
  const r=await fetch(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  return r.json();
}
async function deviceAction(act, name, ip, panel){
  try{
    let j;
    if(act==='start'||act==='reload'||act==='stop') j=await postJson('/api/agent/command',{ip,action:act,panel});
    else if(act==='switch') j=await postJson('/api/device/switch',{device:name,ip,panel});   // ip: Agent dieser Zeile
    else if(act==='wsreload') j=await postJson('/api/reload',{device:name});
    else if(act==='dispoff') j=await postJson('/api/display',{device:name,on:false});
    else if(act==='dispon') j=await postJson('/api/display',{device:name,on:true});
    else return;
    const n=(j.sent!==undefined)?j.sent:j.reloaded;
    if(act==='switch' && j.ok && j.offline){ flash($('#ag_toast'), '✓ '+T('zugeordnet – {g} zeigt die Ansicht, sobald es verbindet').replace('{g}', name), true); return; }
    const ok=!!j.ok && (n===undefined || n>0);
    flash($('#ag_toast'), ok?('✓ '+act+(n!==undefined?(' → '+n):'')):('Fehler: '+(j.error||(n===0?T('Gerät nicht erreicht'):('HTTP '+j.status)))), ok);
  }catch(e){ flash($('#ag_toast'),'Fehler: '+e,false); }
}
// Gerät entfernen: seine Einstellungen (Betriebsmodi, Display-Steuerung,
// Skalierung, Zielkachel, Praesenzmelder) fallen weg, gespeichert wird sofort
// wie mit "Speichern" im Editor darunter (die ganze Liste). Ist es noch
// verbunden, meldet die naechste Abfrage es wieder - dann ohne Einstellungen.
async function devEntfernen(name, online){
  if(!confirm(T('Gerät entfernen:')+' '+name+'\n\n'+
      T('Seine Einstellungen (Betriebsmodi, Display-Steuerung, Skalierung, Zielkachel, Präsenzmelder, Display aus, Nacht, Zuordnung) gehen verloren; die Ansicht bleibt. Gilt sofort, ohne „Speichern“; andere offene Änderungen bleiben offen.')+
      (online?'\n'+T('Es ist gerade verbunden und erscheint danach wieder, ohne Einstellungen.'):''))) return;
  readDevFromDom();
  const alt=DEV[name]; delete DEV[name];
  // Zeile gleich aus dem Editor: liest ein weiteres Speichern die Liste, kaeme sie sonst zurueck
  const zeile=document.querySelector('#geraete .dev[data-name="'+CSS.escape(name)+'"]'); if(zeile) zeile.remove();
  // Offene Aenderungen an anderen Geraeten gehen nicht nebenbei mit: dann den
  // gespeicherten Stand ohne dieses Geraet schicken, die Arbeitskopie bleibt offen
  let liste=null;
  if(OFFEN.has('geraete')){ liste=Object.assign({}, GER_GESPEICHERT); delete liste[name]; }
  try{
    const j=await devSpeichern(liste);
    if(!j.ok){ DEV[name]=alt; renderDevices(); flash($('#ag_toast'),'Fehler: '+(j.error||''),false); return; }
    KNOWN_NAMES=KNOWN_NAMES.filter(n=>n!==name);
    renderDevices(); devGespeichert(j, T('✓ Gespeichert'));
    flash($('#ag_toast'), '✓ '+T('Entfernt:')+' '+name, true);
    pollDevices();
  }catch(e){ DEV[name]=alt; renderDevices(); flash($('#ag_toast'),'Fehler: '+e,false); }
}
async function nameDevice(ip,name,code){
  if(!name){ flash($('#ag_toast'),T('Bitte einen Namen eingeben'),false); return false; }
  try{
    const j=await postJson('/api/device/name', code?{code,name}:{ip,name});   // Code trifft genau ein Geraet
    flash($('#ag_toast'), j.ok?('✓ '+name):('Fehler: '+(j.error||'')), j.ok);
    if(document.activeElement) document.activeElement.blur();
    setTimeout(pollDevices,2500);   // Geraet verbindet sich mit Namen neu
    return !!j.ok;
  }catch(e){ flash($('#ag_toast'),'Fehler: '+e,false); return false; }
}
// ---- Neues Geraet gefunden (Einrichtung neu, Schritt 1) ----
// Ein Geraet ohne Namen (es zeigt seinen Code) oder ein frisch verbundenes
// mit Namen, das noch keine Zuordnung hat und die Standardansicht zeigt,
// meldet der Konfigurator oben in jeder Rubrik. "Benennen und einrichten"
// vergibt den Namen (das Geraet verbindet sich damit neu) und oeffnet dann
// "Geraet einrichten" mit diesem Geraet; "Spaeter" merkt sich das Geraet im
// Browser. Neu zeichnen nur, wenn sich die Geraete aendern (NEU_SIG), sonst
// faehrt die Abfrage in das Namensfeld.
let NEU_WEG=new Set(), NEU_SIG='', NEU_NACH='';
try{ NEU_WEG=new Set(JSON.parse(localStorage.getItem('lp_neu_weg')||'[]')); }catch(e){}
function neuWegMerken(key){ NEU_WEG.add(key); try{ localStorage.setItem('lp_neu_weg', JSON.stringify([...NEU_WEG])); }catch(e){} }
function neueGeraete(j){
  const aus=[];
  (j.anonymous||[]).forEach(a=>{ if(a.code && !NEU_WEG.has('code:'+a.code))
    aus.push({key:'code:'+a.code, art:'code', code:a.code, ip:a.ip, screen:a.screen||null, kiosk:a.kiosk||''}); });
  (j.devices||[]).forEach(d=>{ if(d.online && !d.configured && !d.zugeordnet && (!d.profile || d.profile==='default')
    && !NEU_WEG.has('name:'+d.name)) aus.push({key:'name:'+d.name, art:'name', name:d.name, screen:d.screen||null, kiosk:d.kiosk||''}); });
  return aus;
}
function neuGeraetEinrichten(name){
  // "Geraet einrichten" mit diesem Geraet (Schritt 3: ein Bildschirm, Vorschau in seiner Groesse)
  if(EINR) return;
  geOpen(name);
}
function neuBannerZeichnen(j){
  const box=$('#neuGeraet'); if(!box) return;
  // der benannte Browser ist wieder da: gleich einrichten, und nicht noch einmal melden
  if(NEU_NACH && (j.devices||[]).some(d=>d.name===NEU_NACH && d.online)){
    const n=NEU_NACH; NEU_NACH=''; neuWegMerken('name:'+n); neuGeraetEinrichten(n); }
  const liste=EINR?[]:neueGeraete(j);
  NEU_LETZTE=liste; gvStandZeichnen();
  const sig=JSON.stringify(liste.map(x=>[x.key, x.screen&&x.screen.vw, x.screen&&x.screen.vh]));
  if(sig===NEU_SIG) return;
  NEU_SIG=sig;
  box.hidden=!liste.length;
  if(!liste.length){ box.innerHTML=''; return; }
  const g=liste[0], klasse=geraeteKlasse(g.screen), masse=screenInfo(g.screen), app=TYPE_LABEL[g.kiosk]||'';
  const wo=[klasse, masse, app].filter(Boolean).join(' · ');
  const mehr=liste.length>1 ? '<span class="nb-mehr">+'+(liste.length-1)+' '+T('weitere')+'</span>' : '';
  const sym='<span class="nb-sym"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="13" rx="2"/><path d="M8 21h8"/></svg></span>';
  if(g.art==='code'){
    box.innerHTML=sym+'<div class="nb-tx"><b>'+T('Neues Gerät gefunden:')+' '+esc(wo)+'</b><span>'+T('Zeigt den Code')+
      ' <span class="nb-code">'+esc(g.code)+'</span> · '+esc(g.ip)+'</span></div>'+
      '<input type="text" class="nb-name" placeholder="'+T('Gerätename, z. B. Bad')+'" aria-label="'+T('Gerätename')+'">'+
      '<button class="btn" data-nb="benennen">'+T('Benennen und einrichten')+'</button>'+
      '<button class="btn ghost" data-nb="spaeter">'+T('Später')+'</button>'+mehr;
    const inp=box.querySelector('.nb-name'), los=async()=>{
      const name=inp.value.trim(); if(!name){ inp.focus(); return; }
      if(await nameDevice(g.ip, name, g.code)){ NEU_NACH=name; neuWegMerken(g.key); NEU_SIG=''; }
    };
    box.querySelector('[data-nb="benennen"]').onclick=los;
    inp.onkeydown=e=>{ if(e.key==='Enter') los(); };
  } else {
    box.innerHTML=sym+'<div class="nb-tx"><b>'+T('Neues Gerät verbunden:')+' '+esc(g.name)+'</b><span>'+esc(wo)+' · '+
      T('zeigt die Standardansicht, noch keine zugeordnet')+'</span></div>'+
      '<button class="btn" data-nb="einrichten">'+T('Einrichten')+'</button>'+
      '<button class="btn ghost" data-nb="spaeter">'+T('Später')+'</button>'+mehr;
    box.querySelector('[data-nb="einrichten"]').onclick=()=>neuGeraetEinrichten(g.name);
  }
  box.querySelector('[data-nb="spaeter"]').onclick=()=>{ neuWegMerken(g.key); NEU_SIG=''; neuBannerZeichnen(j); };
}
async function pollDevices(){
  try{
    const r=await fetch('/api/devices'); const j=await r.json();
    serverStandPruefen(j.stand);
    renderDeviceList(j);
    ANON_DEVICES=Array.isArray(j.anonymous)?j.anonymous:[];
    const names=(j.devices||[]).map(d=>d.name).filter(Boolean);
    let vorschlagNeu=false;
    (j.devices||[]).forEach(d=>{ if(d.ip) DEVICE_IPS[d.name]=d.ip;
      const v=d.tileSuggest||null; if(v!==(DEVICE_SUGGEST[d.name]||null)) vorschlagNeu=true;
      DEVICE_SUGGEST[d.name]=v; DEVICE_SCREENS[d.name]=d.screen||null;
      DEVICE_CONN[d.name]=d.connections||0; DEVICE_VORSCHAU[d.name]=d.vorschau||null;
      DEVICE_ZUORDNUNG[d.name]=d.zugeordnet||''; });
    // Das Geraet ist von selbst zurueckgekehrt (abgelaufen, anders umgeschaltet): Knopf nachziehen
    // (nicht in den ersten Sekunden: die Abfrage kann vor dem Start der Vorschau losgegangen sein)
    if(ENTWURF.geraet && !DEVICE_VORSCHAU[ENTWURF.geraet] && Date.now()-(ENTWURF.seit||0)>4000){ ENTWURF.geraet=''; vorGerKnopf(); }
    PRESENCE_NOW={};
    (j.devices||[]).forEach(d=>{ if(typeof d.presence==='boolean') PRESENCE_NOW[d.name]=d.presence; });
    document.querySelectorAll('#geraete .dev').forEach(n=>{
      const s=n.querySelector('.dp_state'); if(s) s.textContent=presenceText(n.dataset.name); });
    const isNew=names.some(n=>KNOWN_NAMES.indexOf(n)<0);
    KNOWN_NAMES=Array.from(new Set(KNOWN_NAMES.concat(names)));
    if(isNew||vorschlagNeu){ readDevFromDom(); renderDevices(); }   // neues Panel oder neuer Vorschlag -> Editor ergaenzen (Eingaben behalten)
    mzGeraeteNeu(names);   // offener Betriebsmodus-Assistent: neu benanntes Geraet uebernehmen
    neuBannerZeichnen(j);  // nach DEVICE_SCREENS: "Geraet einrichten" braucht die Groesse des Geraets
  }catch(e){}
}

// ---- Betriebsmodus-Automatik ----
function profOpts(sel){
  return '<option value="">'+T('— Ansicht wählen —')+'</option>'+
    PANEL_IDS.map(id=>'<option'+(sel===id?' selected':'')+'>'+esc(id)+'</option>').join('');
}
function devRow(name){
  const d=DEV[name]||{auto:true,modes:[]}, g=geraetDaten(name);
  const pairs=d.modes&&d.modes.length?d.modes:[['','']];
  const rows=pairs.map(([m,p])=>
    '<div class="dmrow" style="display:flex;gap:6px;align-items:center;margin:4px 0">'+
      '<input type="text" class="dm_mode" placeholder="'+T('Modus (z.B. gaeste)')+'" value="'+esc(m)+'" style="flex:1;min-width:120px">'+
      '<span style="opacity:.6">→</span>'+
      '<select class="dm_prof" style="flex:1;min-width:120px">'+profOpts(p)+'</select>'+
      '<button class="btn sm ghost dm_del" type="button" title="'+T('Zeile entfernen')+'">✕</button>'+
    '</div>').join('');
  const editor=(key, inhalt)=>'<div class="gz-editor" data-gze="'+key+'"'+(GK_AUF.has(name+'/'+key)?'':' hidden')+'>'+inhalt+'</div>';
  const w=displayGilt(name), leer=gesetzt(w.v) ? wertText('dpmsOff', w.v)+' · '+w.quelle : wertText('dpmsOff', null);
  const nd=geraetGilt(name, 'nightDim'), nw=geraetGilt(name, 'nightWake');
  // Fuenf Zeilen: Zeigt, Display, Betriebsmodi, Technik, Entfernen; "Aendern" klappt den Editor darunter auf
  return '<div class="dev" data-name="'+esc(name)+'">'+
    zeigtHtml(name, g)+
    editor('zeigt',
      '<div class="gk-teil">'+T('Gesten')+'</div>'+
      '<div class="dlrow" style="display:flex;gap:6px;align-items:center;flex-wrap:wrap;margin:8px 0 2px">'+
        '<span style="font-size:13px;opacity:.85">'+T('Stimmung beim Einschalten')+'</span>'+
        '<select class="dl_start" style="max-width:100%">'+lichtStartOptionen(d.lichtStart)+'</select>'+
      '</div>'+
      '<div class="note">'+T('Was zwei Finger in der Mitte einschalten, wenn im Raum alles aus ist; ihre Lichtsteuerung ist die, durch deren Stimmungen ein Tipp schaltet. Leer: die erste Stimmung der ersten Lichtsteuerung im Raum.')+'</div>')+
    displayHtml(name)+
    editor('display',
      '<div class="ddprow" style="display:flex;gap:6px;align-items:center;flex-wrap:wrap;margin:8px 0 2px">'+
        '<span style="font-size:13px;opacity:.85">'+T('Display aus nach (Sek.)')+'</span>'+
        '<input type="number" class="dd_dpms" min="0" max="3600" step="30" placeholder="'+esc(gesetzt(w.v)?String(w.v):'')+'" value="'+esc(gesetzt(d.dpmsOff)?d.dpmsOff:'')+'" style="width:90px">'+
        '<span class="note">'+esc(T('Leer gilt:')+' '+leer+'. '+T('0 = Display bleibt an.'))+'</span>'+
      '</div>'+
      '<div class="gk-teil">'+T('Nacht')+'</div>'+
      '<div class="dnrow" style="display:flex;gap:6px;align-items:center;flex-wrap:wrap;margin:8px 0 2px">'+
        '<span style="font-size:13px;opacity:.85">'+T('Nachts abdunkeln (%)')+'</span>'+
        '<input type="number" class="dd_dim" min="0" max="90" step="5" placeholder="'+esc(nachtPlatzhalter('nightDim', nd.v))+'" value="'+esc(gesetzt(d.nightDim)?d.nightDim:'')+'" style="width:80px">'+
        '<span style="font-size:13px;opacity:.85">'+T('Aufhellen bei Berührung (Sek.)')+'</span>'+
        '<input type="number" class="dd_wake" min="0" max="300" step="5" placeholder="'+esc(nachtPlatzhalter('nightWake', nw.v))+'" value="'+esc(gesetzt(d.nightWake)?d.nightWake:'')+'" style="width:80px">'+
      '</div>'+
      '<div class="note">'+esc(T('Leer gilt:')+' '+giltText('nightDim', nd)+', '+giltText('nightWake', nw)+'. ')+
        T('Wann es Nacht ist und ob die Nacht-Uhr läuft, steht in den Vorgaben. In der LoxPanel-App senkt „Nachts abdunkeln“ die echte Display-Helligkeit, statt das Bild abzudunkeln.')+'</div>'+
      '<div class="gk-teil">'+T('Präsenzmelder')+'</div>'+
      '<div class="dprow" style="display:flex;gap:6px;align-items:center;flex-wrap:wrap;margin:8px 0 2px">'+
        '<select class="dp_presence" style="max-width:100%">'+presenceOptions(d.presence)+'</select>'+
        '<span class="note dp_state">'+esc(presenceText(name))+'</span>'+
      '</div>')+
    modiHtml(name)+
    editor('modi',
      '<label style="font-size:13px;opacity:.85"><input type="checkbox" class="dev_auto"'+(d.auto?' checked':'')+'> '+T('Automatik aktiv')+'</label>'+
      '<div class="dmrows">'+rows+'</div>'+
      '<button class="btn sm ghost dm_add" type="button" style="margin-top:4px">'+T('+ Modus')+'</button>')+
    technikHtml(name, g)+
    editor('technik',
      '<div class="gk-teil">'+T('Am Gerät')+'</div>'+
      '<div class="dsrow" style="display:flex;gap:6px;align-items:center;flex-wrap:wrap;margin:8px 0 2px">'+
        '<span style="font-size:13px;opacity:.85">'+T('Skalierung')+'</span>'+
        '<select class="ds_scale skal">'+scaleOptions(d.scale,T('Wie in der Ansicht'))+'</select>'+
      '</div>'+'<div class="erbt" data-gerbt="scale"></div>'+
      '<div class="dtrow" style="display:flex;gap:6px;align-items:center;flex-wrap:wrap;margin:8px 0 2px">'+
        '<span style="font-size:13px;opacity:.85">'+T('Zielkachel (Automatik)')+'</span>'+
        '<input type="number" class="dt_ziel" min="'+kachelZiel().min+'" max="'+kachelZiel().max+'" step="10" placeholder="'+T('wie in der Ansicht')+'" value="'+(d.tileTarget||'')+'" style="width:90px">'+
        '<span style="font-size:13px;opacity:.85">px</span>'+
        '<span class="note dt_hinweis">'+esc(vorschlagText(name))+'</span>'+
        (DEVICE_SUGGEST[name]?'<button class="btn sm ghost dt_nehmen" type="button">'+T('übernehmen')+'</button>':'')+
      '</div>'+'<div class="erbt" data-gerbt="tileTarget"></div>'+
      '<div class="note">'+esc(zielkachelHinweis())+'</div>'+
      '<div class="gk-teil">'+T('Display-Steuerung')+'</div>'+
      '<div class="note">'+T('Nur für Fully Kiosk oder WallPanel nötig; die LoxPanel-App und der Linux-Agent schalten das Display selbst.')+'</div>'+
      displayRow(d.display, name))+
    entfernenHtml(name, g)+
  '</div>';
}
// Auswahl Praesenzmelder: alle Bausteine mit active-State (wie beim Nacht-
// Ausloeser). Ein gewaehlter, den die Struktur gerade nicht kennt (Miniserver
// getrennt, Baustein entfernt), bleibt sichtbar statt beim Speichern still
// verloren zu gehen.
function presenceOptions(sel){
  const opts=ACTIVE_OPTS.slice();
  if(sel && !opts.some(o=>o.uuid===sel)) opts.unshift({uuid:sel, name:sel, type:T('nicht in der Struktur'), room:''});
  return '<option value="">'+T('— keiner (Display nach der Leerlaufzeit aus) —')+'</option>'+
    opts.map(o=>'<option value="'+esc(o.uuid)+'"'+(o.uuid===sel?' selected':'')+'>'+
      esc((o.room?o.room+' · ':'')+o.name+' ('+o.type+')')+'</option>').join('');
}
// Stimmung beim Einschalten (Gesten): Wert im Feld "Lichtsteuerung|Stimmungs-ID",
// gespeichert als {lc, mood}. Die Auswahl listet der Server (/api/meta
// lichtStimmungen); eine gewaehlte, die die Struktur gerade nicht kennt, bleibt.
function lichtStartWert(ls){ return (ls && ls.lc && ls.mood!=null) ? ls.lc+'|'+ls.mood : ''; }
function lichtStartAusWert(v){
  const i=String(v||'').lastIndexOf('|'); if(i<1) return null;
  const mood=parseInt(String(v).slice(i+1)); return isNaN(mood) ? null : {lc:String(v).slice(0,i), mood};
}
function lichtStartOptionen(sel){
  sel=sel||'';
  const bekannt=LICHT_OPTS.some(o=>(o.moods||[]).some(m=>o.uuid+'|'+m.id===sel));
  return '<option value="">'+T('— erste Stimmung im Raum —')+'</option>'+
    (sel && !bekannt ? '<option value="'+esc(sel)+'" selected>'+esc(sel+' ('+T('nicht in der Struktur')+')')+'</option>' : '')+
    LICHT_OPTS.map(o=>'<optgroup label="'+esc((o.room?o.room+' · ':'')+o.name)+'">'+
      (o.moods||[]).map(m=>{ const v=o.uuid+'|'+m.id;
        return '<option value="'+esc(v)+'"'+(v===sel?' selected':'')+'>'+esc(m.name)+'</option>'; }).join('')+
    '</optgroup>').join('');
}
function presenceText(name){
  const p=PRESENCE_NOW[name];
  return p===true ? T('gerade: jemand da') : p===false ? T('gerade: Raum leer') : '';
}
// Vorschlag fuer die Zielkachel eines Geraets (Server: _kachel_vorschlag aus
// der gemeldeten Groesse und Pixeldichte); wirkt nur im Kachel-Layout "Automatisch"
function vorschlagText(name){
  const v=DEVICE_SUGGEST[name], sc=DEVICE_SCREENS[name];
  if(!v||!sc||!sc.vw) return T('kein Vorschlag: das Gerät hat noch keine Größe gemeldet');
  return T('Vorschlag')+' '+v+' px ('+sc.vw+'×'+sc.vh+(sc.dpr?', '+T('Pixeldichte')+' '+fmtZahl(sc.dpr):'')+')';
}
const DRIVER_PORT={fully:2323, wallpanel:2971};
// Leeres Kennwortfeld: Der Server behaelt das gespeicherte Kennwort nur fuer
// dasselbe Ziel (Treiber und Host, _KENNWORT_ZIEL in webvisu.py). Dieselbe
// Regel hier, damit der Platzhalter sagt, was beim Speichern passiert.
function pwHinweis(name, drv, host){
  const z=PASS_ZIEL[name];
  return (z && z.driver===drv && z.host===String(host||'').trim()) ? T('unverändert lassen') : T('Passwort (Fully)');
}
// ... fuer eine Zeile nach Treiber und Host, wie sie gerade im Formular stehen
function pwHinweisZeigen(row){
  row.querySelector('.dd_pw').placeholder=pwHinweis(row.dataset.name, row.querySelector('.dd_drv').value, row.querySelector('.dd_host').value);
}
function displayRow(disp, name){
  const x=disp||{driver:'',host:'',port:'',password:''};   // password: nur selbst Eingetipptes
  return '<div class="ddrow" style="display:flex;gap:6px;align-items:center;flex-wrap:wrap;margin:8px 0 2px">'+
    '<select class="dd_drv"><option value="">'+T('keine (nur über die Seite)')+'</option>'+
      '<option value="fully"'+(x.driver==='fully'?' selected':'')+'>Fully Kiosk (Remote Admin)</option>'+
      '<option value="wallpanel"'+(x.driver==='wallpanel'?' selected':'')+'>WallPanel (HTTP)</option></select>'+
    '<input type="text" class="dd_host" placeholder="IP" value="'+esc(x.host||'')+'" style="width:130px">'+
    '<input type="text" class="dd_port" placeholder="Port" value="'+esc(x.port||'')+'" style="width:70px">'+
    '<input class="dd_pw" type="password" placeholder="'+pwHinweis(name, x.driver, x.host)+'" value="'+esc(x.password||'')+'" style="width:140px" autocomplete="new-password">'+
  '</div>';
}
function readDevFromDom(){
  const box=$('#geraete'); if(!box) return;
  box.querySelectorAll('.dev').forEach(n=>{
    const modes=[];
    n.querySelectorAll('.dmrow').forEach(r=>{
      modes.push([r.querySelector('.dm_mode').value, r.querySelector('.dm_prof').value]);
    });
    const drv=n.querySelector('.dd_drv').value;
    const display=drv?{driver:drv, host:n.querySelector('.dd_host').value.trim(),
      port:parseInt(n.querySelector('.dd_port').value)||DRIVER_PORT[drv]||0,
      password:n.querySelector('.dd_pw').value}:null;
    const sc=n.querySelector('.ds_scale'), pr=n.querySelector('.dp_presence'), tz=n.querySelector('.dt_ziel');
    const ls=n.querySelector('.dl_start'), dp=n.querySelector('.dd_dpms'), dn=n.querySelector('.dd_dim'), dw=n.querySelector('.dd_wake');
    const zahl=(el, max)=>(el&&el.value.trim()!=='')?Math.max(0, Math.min(max, Number(el.value))):'';
    DEV[n.dataset.name]={auto:n.querySelector('.dev_auto').checked, modes, display,
                         scale:sc?scaleValue(sc.value):'', presence:pr?pr.value:'',
                         tileTarget:(tz&&parseInt(tz.value)>0)?parseInt(tz.value):'',
                         dpmsOff:zahl(dp, 3600), nightDim:zahl(dn, 90), nightWake:zahl(dw, 300),
                         lichtStart:ls?ls.value:'',
                         panel:(DEV[n.dataset.name]||{}).panel||''};   // Zuordnung (Schritt 2): setzt nur "Ansicht wechseln"
  });
}
function renderDevices(){
  const box=$('#geraete'); if(!box) return;
  geraeteKarten();
  box.querySelectorAll(':scope > .gk').forEach(k=>{ k.querySelector('.gk-body').innerHTML=devRow(k.dataset.gk); gkAktionenBinden(k, k.querySelector('.gk-body')); });
  koepfeZeichnen(); geraetErbtZeichnen();
  // "Aendern"/"Einrichten"/"Gesten": den Editor der Zeile auf- und zuklappen; offen bleibt offen
  box.querySelectorAll('.gz-auf').forEach(b=>b.onclick=()=>{
    const k=b.closest('.gk'), key=b.dataset.gz, ed=k.querySelector('.gz-editor[data-gze="'+key+'"]'), auf=ed.hidden;
    ed.hidden=!auf; if(auf) GK_AUF.add(k.dataset.gk+'/'+key); else GK_AUF.delete(k.dataset.gk+'/'+key);
    b.setAttribute('aria-expanded', String(auf)); b.textContent=b.textContent.replace(/[▾▸]$/, auf?'▾':'▸'); });
  // Wert und Herkunft der Zeilen Display, Betriebsmodi und Technik folgen den Eingaben
  box.querySelectorAll('.dd_dpms, .dd_dim, .dd_wake, .dp_presence, .dm_mode, .dm_prof, .dev_auto, .ds_scale, .dt_ziel, .dd_drv').forEach(el=>{
    el.addEventListener(el.tagName==='SELECT'||el.type==='checkbox'?'change':'input', ()=>{ readDevFromDom(); gzWerteZeichnen(el.closest('.gk')); }); });
  box.querySelectorAll('.dm_add').forEach(b=>b.onclick=()=>{
    readDevFromDom(); const name=b.closest('.dev').dataset.name;
    (DEV[name]=DEV[name]||{auto:true,modes:[]}).modes.push(['','']); bereichOffen('geraete'); renderDevices();
  });
  box.querySelectorAll('.dd_drv').forEach(sel=>sel.onchange=()=>{
    const row=sel.closest('.dev'), name=row.dataset.name, drv=sel.value;
    const host=row.querySelector('.dd_host'), port=row.querySelector('.dd_port');
    if(drv){ if(!host.value && DEVICE_IPS[name]) host.value=DEVICE_IPS[name]; if(!port.value) port.value=DRIVER_PORT[drv]||''; }
    pwHinweisZeigen(row);
  });
  box.querySelectorAll('.dd_host').forEach(inp=>inp.oninput=()=>pwHinweisZeigen(inp.closest('.dev')));
  box.querySelectorAll('.dt_nehmen').forEach(b=>b.onclick=()=>{
    const row=b.closest('.dev'), v=DEVICE_SUGGEST[row.dataset.name];
    if(v){ row.querySelector('.dt_ziel').value=v; bereichOffen('geraete'); } });
  box.querySelectorAll('.dm_del').forEach(b=>b.onclick=()=>{
    const dev=b.closest('.dev'), name=dev.dataset.name;
    const idx=Array.from(dev.querySelectorAll('.dmrow')).indexOf(b.closest('.dmrow'));
    readDevFromDom(); DEV[name].modes.splice(idx,1); bereichOffen('geraete'); renderDevices();
  });
}
// Zeilen Display, Betriebsmodi und Technik neu beschriften (die Editoren bleiben, wie sie sind)
function gzWerteZeichnen(k){
  if(!k) return;
  const name=k.dataset.gk, g=geraetDaten(name);
  if(!k.querySelector('.dev')) return;   // Zeilen noch nicht gezeichnet (renderDevices kommt)
  const neu={display:displayHtml(name), modi:modiHtml(name), technik:technikHtml(name, g), entfernen:entfernenHtml(name, g)};
  Object.keys(neu).forEach(key=>{ const z=k.querySelector('.gz[data-gz="'+key+'"]'); if(!z) return;
    const h=document.createElement('div'); h.innerHTML=neu[key]; const n=h.firstChild;
    const alt=z.querySelector('.gz-auf'), nb=n.querySelector('.gz-auf');
    if(alt && nb){ nb.setAttribute('aria-expanded', alt.getAttribute('aria-expanded')); nb.textContent=nb.textContent.replace(/[▾▸]$/, alt.textContent.slice(-1)); nb.onclick=alt.onclick; }
    z.replaceWith(n); });
  gkAktionenBinden(k, k.querySelector('.gk-body'));
}
// Speicher-Daten fuer /api/devices aus der Arbeitskopie DEV - eine Quelle fuer
// "Speichern" und den Betriebsmodus-Assistenten. Ein Geraet bleibt, sobald es
// Modi, einen Display-Treiber, eine Skalierung oder einen Praesenzmelder traegt
// (bisher fiel eines ohne Modi und Display-Treiber still weg).
function devicesPayload(quelle=DEV){
  const devices={};
  Object.entries(quelle).forEach(([name,d])=>{
    const modes={};
    (d.modes||[]).forEach(([m,p])=>{ m=(m||'').trim(); if(m&&p) modes[m]=p; });
    const display=(d.display&&d.display.driver&&d.display.host)?d.display:null;
    const scale=(d.scale===''||d.scale===undefined||d.scale===null)?null:d.scale;   // null = wie in der Ansicht
    const presence=d.presence||'';
    const ziel=(parseInt(d.tileTarget)>0)?parseInt(d.tileTarget):0;   // Zielkachel je Geraet; ohne sie ging sie beim Speichern verloren
    const lichtStart=lichtStartAusWert(d.lichtStart);   // Stimmung beim Einschalten (Gesten)
    const zahl=v=>(v===''||v===undefined||v===null||isNaN(Number(v)))?null:Number(v);
    const dpms=zahl(d.dpmsOff), dim=zahl(d.nightDim), wake=zahl(d.nightWake);   // Display aus nach Sek., Nacht
    if(Object.keys(modes).length || display || scale!==null || presence || ziel || lichtStart || d.panel || dpms!==null || dim!==null || wake!==null){
      devices[name]={auto:d.auto!==false, modes};
      if(d.panel) devices[name].panel=d.panel;
      if(dpms!==null) devices[name].dpmsOff=dpms;
      if(dim!==null) devices[name].nightDim=dim;
      if(wake!==null) devices[name].nightWake=wake;
      if(display) devices[name].display=display;
      if(scale!==null) devices[name].scale=scale;
      if(presence) devices[name].presence=presence;
      if(ziel) devices[name].tileTarget=ziel;
      if(lichtStart) devices[name].lichtStart=lichtStart;
    }
  });
  return devices;
}
// Die Geraeteliste nacheinander speichern: Jede Anfrage traegt die ganze Liste,
// eine spaetere darf eine fruehere nicht ueberholen (sonst kaeme ein gerade
// entferntes Display zurueck). Die Liste entsteht erst, wenn die Anfrage dran ist.
// liste: fertige Liste statt der Arbeitskopie ("Entfernen" bei offenen Aenderungen).
// Geht die ganze Arbeitskopie durch, ist der Bereich 'geraete' erledigt.
let DEV_SPEICHERN=Promise.resolve();
function devSpeichern(liste){
  const stand=liste?null:offenStand(k=>k==='geraete');
  const lauf=DEV_SPEICHERN.then(()=>postJson('/api/devices',{devices:liste||devicesPayload()})).then(j=>{
    if(j.ok){ passZielLesen(j.devices); GER_GESPEICHERT=devicesPayload(devAusServer(j.devices));
      if(stand) erledigt(stand); leisteZeigen(); }
    return j;
  });
  DEV_SPEICHERN=lauf.catch(()=>{});
  return lauf;
}
// Nach dem Speichern: welche Kennwoerter der Server jetzt hat (auch in den
// Platzhaltern, "Speichern" zeichnet nicht neu); eines, das er wegen eines
// anderen Ziels verworfen hat, nennen (bleibt stehen).
function kennwortHinweis(j){
  document.querySelectorAll('#geraete .dev').forEach(pwHinweisZeigen);
  const weg=j.kennwortVerworfen||[];
  return weg.length ? T('Display-Kennwort nicht übernommen, weil Host oder Treiber geändert:')+' '+weg.join(', ') : '';
}
function devGespeichert(j, text){
  const h=kennwortHinweis(j), t=$('#dev_toast');
  if(!h){ flash(t,text,true); return; }
  t.className='toast show warn';
  t.textContent=text+' · '+h;
}
// Bereich 'geraete' der Speicherleiste
async function geraeteSpeichern(){
  readDevFromDom();
  try{
    const j=await devSpeichern();
    if(!j.ok) return {ok:false, text:T('Geräte')+': '+(j.error||T('Fehler'))};
    const h=kennwortHinweis(j);
    return {ok:true, warn:!!h, text:'✓ '+T('Gespeichert:')+' '+T('Geräte')+(h?' · '+h:'')};
  }catch(e){ return {ok:false, text:T('Geräte')+': '+e}; }
}

// ---- Betriebsmodus-Assistent ----
// Geführter Weg: Geräte -> Modi -> Ansicht je Modus -> fertige Loxone-Adresse.
// Schreibt in dieselbe Struktur wie die Detail-Tabelle (DEV[name].modes) und
// speichert über /api/devices - danach steht alles auch in der Tabelle.
const MZ_PRESETS=[
  {key:'anwesend',label:'Anwesend'},{key:'abwesend',label:'Abwesend'},
  {key:'gaeste',label:'Gäste'},{key:'putzen',label:'Putzen'},
  {key:'urlaub',label:'Urlaub'},{key:'nacht',label:'Nacht'}];
const MZ={devices:[],modes:[],step:0,_wired:false,benannt:''};
function mzKey(s){ return (s||'').toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g,'').replace(/[^a-z0-9]+/g,''); }
function mzFlow(){ return ['geraete','modi','zuordnung','fertig']; }
function mzDevNames(){ return Array.from(new Set(KNOWN_NAMES.concat(Object.keys(DEV)))).sort(); }
function mzCustom(){ return MZ.modes.filter(m=>!MZ_PRESETS.some(p=>p.key===m.key)); }
function mzOpen(){
  if(!MZ._wired){ MZ._wired=true;
    $('#mzBack').onclick=()=>{ if(MZ.step>0){ MZ.step--; mzRender(); } };
    $('#mzNext').onclick=mzNext;
    $('#mzOv').onclick=(e)=>{ if(e.target===$('#mzOv')) mzClose(); };
    $('#mzX').onclick=mzClose;
  }
  MZ.devices=[]; MZ.modes=[]; MZ.step=0; MZ.benannt='';
  $('#mzOv').hidden=false; mzRender();
}
function mzClose(){ $('#mzOv').hidden=true; }
function mzRender(){
  const f=mzFlow(), key=f[MZ.step], b=$('#mzBody');
  $('#mzStep').textContent=T('Schritt')+' '+(MZ.step+1)+' / '+f.length;
  if(key==='geraete'){
    const names=mzDevNames();
    MZ._sig=mzGeraeteSig();
    // Verbundene Geraete ohne Namen gleich hier benennen: vorher hiess es nur
    // "Noch kein Gerät bekannt", obwohl eines verbunden war, und man sass fest.
    const anon=ANON_DEVICES.map(a=>'<div class="mzanon" data-mzanon="'+esc(anonKey(a))+'" data-ip="'+esc(a.ip)+'" data-code="'+esc(a.code||'')+'">'+
      '<span class="agip">'+(a.code?('<b>'+T('Code')+' '+esc(a.code)+'</b> · '):'')+esc(a.ip)+' · '+
      esc(TYPE_LABEL[a.kiosk]||T('Browser'))+'</span><input type="text" class="mzname" placeholder="'+T('Gerätename')+'">'+
      '<button class="wzbtn" data-mzname>'+T('Namen vergeben')+'</button></div>').join('');
    b.innerHTML='<p class="wzq">'+T('Für welche Geräte?')+'</p>'+
      (names.length? '<div class="mzchips">'+names.map(n=>'<button class="chip'+(MZ.devices.indexOf(n)>=0?' on':'')+'" data-mzdev="'+esc(n)+'">'+esc(n)+'</button>').join('')+'</div>'
        : (anon ? '' : '<div class="wznote">'+esc(T('Noch kein Gerät bekannt. Ein Gerät muss die Visu einmal öffnen und im Konfigurator einen Namen bekommen, oder einen Agent haben.'))+'</div>'))+
      (anon ? '<div class="wznote" style="margin-top:10px">'+T('Verbunden, aber noch ohne Namen – erst benennen, dann auswählen:')+'</div>'+anon : '')+
      (MZ.benannt ? '<div class="wznote" style="margin-top:8px">'+esc(T('✓ Name vergeben – das Gerät verbindet sich neu und erscheint gleich oben:')+' '+MZ.benannt)+'</div>' : '')+
      '<div class="wznote" style="margin-top:10px">'+T('Die Modus-Zuordnung gilt für alle gewählten Geräte gleich. Feinabstimmung je Gerät danach in der Detail-Tabelle.')+'</div>';
  } else if(key==='modi'){
    b.innerHTML='<p class="wzq">'+T('Welche Betriebsmodi?')+'</p><div class="wzopts">'+
      MZ_PRESETS.map(m=>{ const on=MZ.modes.some(x=>x.key===m.key);
        return '<button class="wzo'+(on?' on':'')+'" data-mzmode="'+esc(m.key)+'" data-mzlabel="'+esc(m.label)+'">'+ikon('grid')+
          '<span class="tx"><b>'+esc(m.label)+'</b><span>'+T('Loxone sendet')+' <code>'+esc(m.key)+'</code></span></span></button>'; }).join('')+'</div>'+
      '<div class="wzrow" style="margin-top:12px"><div class="wzfield" style="flex:1;max-width:240px"><label>'+T('Eigener Modus')+'</label>'+
        '<input id="mzCustomIn" placeholder="'+T('z. B. Kino')+'"></div><button class="wzbtn" id="mzAdd" style="align-self:flex-end">＋ '+T('Hinzufügen')+'</button></div>'+
      (mzCustom().length? '<div class="mzchips" style="margin-top:10px">'+mzCustom().map(m=>'<span class="chip on" data-mzdel="'+esc(m.key)+'">'+esc(m.label)+' <code>'+esc(m.key)+'</code> <span class="x">×</span></span>').join('')+'</div>':'');
  } else if(key==='zuordnung'){
    b.innerHTML='<p class="wzq">'+T('Welche Ansicht bei welchem Modus?')+'</p><div class="mztable">'+
      MZ.modes.map(m=>'<div class="mzrow"><span class="mzml"><b>'+esc(m.label)+'</b> <code>'+esc(m.key)+'</code></span>'+
        '<select class="mzprof" data-mzk="'+esc(m.key)+'"><option value="">'+T('unverändert lassen')+'</option>'+
        PANEL_IDS.map(id=>'<option value="'+esc(id)+'"'+(m.profile===id?' selected':'')+'>'+esc(id)+'</option>').join('')+'</select></div>').join('')+'</div>'+
      '<div class="wznote" style="margin-top:10px">'+T('„Unverändert lassen" heißt: dieser Modus schaltet das Gerät nicht um.')+'</div>';
  } else {
    const host=location.host;
    const lines=MZ.modes.map(m=>'http://'+host+'/api/mode/'+m.key).join('\n');
    const zuo=MZ.modes.filter(m=>m.profile).map(m=>'<div class="mzrow"><span class="mzml"><b>'+esc(m.label)+'</b></span><b>→ '+esc(m.profile)+'</b></div>').join('')
      ||('<div class="wznote">'+T('Keine Zuordnung gewählt — es würde nichts umgeschaltet.')+'</div>');
    b.innerHTML='<p class="wzq">'+T('Fertig — in Loxone einrichten')+'</p>'+
      '<div class="wznote">'+T('Lege in Loxone Config je Betriebsart einen virtuellen HTTP-Ausgang mit dieser Adresse an (der Modusname am Ende zählt):')+'</div>'+
      '<pre class="cmdout" id="mzLines" style="margin-top:6px;white-space:pre-wrap">'+esc(lines)+'</pre>'+
      '<button class="wzbtn" id="mzCopy" style="margin-top:6px">'+T('Adressen kopieren')+'</button>'+
      '<p class="wzq mt">'+T('Zuordnung')+'</p><div class="mztable">'+zuo+'</div>'+
      '<div class="wznote" style="margin-top:10px">'+T('Geräte:')+' <b>'+esc(MZ.devices.join(', ')||'—')+'</b>. '+T('„Übernehmen" speichert das für alle gewählten Geräte.')+'</div>';
  }
  b.querySelectorAll('[data-mzdev]').forEach(el=>el.onclick=()=>{ const n=el.dataset.mzdev, i=MZ.devices.indexOf(n); if(i>=0)MZ.devices.splice(i,1); else MZ.devices.push(n); mzRender(); });
  b.querySelectorAll('[data-mzanon]').forEach(row=>{
    const inp=row.querySelector('.mzname'), btn=row.querySelector('[data-mzname]');
    const go=async()=>{ const name=inp.value.trim(); if(!name){ inp.focus(); return; }
      btn.disabled=true;
      if(await nameDevice(row.dataset.ip,name,row.dataset.code)){ MZ.benannt=name; mzRender(); } else btn.disabled=false; };
    btn.onclick=go; inp.onkeydown=(e)=>{ if(e.key==='Enter'){ e.preventDefault(); go(); } };
  });
  b.querySelectorAll('[data-mzmode]').forEach(el=>el.onclick=()=>{ const k=el.dataset.mzmode, i=MZ.modes.findIndex(x=>x.key===k);
    if(i>=0)MZ.modes.splice(i,1); else MZ.modes.push({key:k,label:el.dataset.mzlabel,profile:''}); mzRender(); });
  b.querySelectorAll('[data-mzdel]').forEach(el=>el.onclick=()=>{ const k=el.dataset.mzdel, i=MZ.modes.findIndex(x=>x.key===k); if(i>=0){ MZ.modes.splice(i,1); mzRender(); } });
  { const add=$('#mzAdd'), inp=$('#mzCustomIn');
    const go=()=>{ const lbl=(inp&&inp.value||'').trim(), k=mzKey(lbl); if(!k) return; if(!MZ.modes.some(x=>x.key===k)) MZ.modes.push({key:k,label:lbl||k,profile:''}); mzRender(); };
    if(add) add.onclick=go; if(inp) inp.onkeydown=(e)=>{ if(e.key==='Enter'){ e.preventDefault(); go(); } }; }
  b.querySelectorAll('.mzprof').forEach(sel=>sel.onchange=()=>{ const m=MZ.modes.find(x=>x.key===sel.dataset.mzk); if(m) m.profile=sel.value; });
  { const cp=$('#mzCopy'); if(cp) cp.onclick=()=>{ navigator.clipboard.writeText($('#mzLines').textContent)
      .then(()=>flash($('#dev_toast'),T('✓ kopiert'),true)).catch(()=>{}); }; }
  $('#mzBack').disabled=MZ.step===0;
  $('#mzNext').textContent=(MZ.step===f.length-1)?T('Übernehmen ✓'):T('Weiter →');
  let ok=true;
  if(key==='geraete') ok=MZ.devices.length>0;
  else if(key==='modi') ok=MZ.modes.length>0;
  $('#mzNext').disabled=!ok;
}
function mzNext(){ const f=mzFlow(); if(MZ.step<f.length-1){ MZ.step++; mzRender(); return; } mzApply(); }
// Neue Geraetenamen aus pollDevices: steht der Betriebsmodus-Assistent bei den Geraeten
// und wurde darin gerade eines benannt, erscheint es als Chip und ist gewaehlt.
// Signatur der Geraeteliste fuer den offenen Betriebsmodus-Assistenten: Geraete ohne Namen
// ueber ihren Code (anonKey), nicht nur die IP - sonst bliebe nach dem Tausch
// eines Browsers hinter derselben IP der alte Code stehen (Codex an #131).
function mzGeraeteSig(){ return JSON.stringify([mzDevNames(), ANON_DEVICES.map(anonKey)]); }
function mzGeraeteNeu(names){
  if($('#mzOv').hidden || mzFlow()[MZ.step]!=='geraete') return;
  let neu=false;
  if(MZ.benannt && names.indexOf(MZ.benannt)>=0){
    if(MZ.devices.indexOf(MZ.benannt)<0) MZ.devices.push(MZ.benannt);
    MZ.benannt=''; neu=true;
  }
  if(!neu && mzGeraeteSig()===MZ._sig) return;   // nichts Neues: nicht alle 6 s neu zeichnen
  const b=$('#mzBody'); if(b && b.contains(document.activeElement) && document.activeElement.tagName==='INPUT') return;   // nicht beim Tippen
  mzRender();
}
async function mzApply(){
  readDevFromDom();   // manuelle Tabellen-Edits nicht überschreiben
  MZ.devices.forEach(name=>{
    const d=DEV[name]||(DEV[name]={auto:true,modes:[]});
    const map=new Map((d.modes||[]).map(([m,p])=>[m,p]));
    MZ.modes.forEach(m=>{ if(m.profile) map.set(m.key,m.profile); else map.delete(m.key); });
    d.modes=Array.from(map.entries()); d.auto=true;
  });
  try{
    const j=await devSpeichern();
    if(j.ok){ mzClose(); devGespeichert(j,T('✓ Betriebsmodus gespeichert')); renderDevices(); }
    else flash($('#dev_toast'),j.error||T('Fehler'),false);
  }catch(e){ flash($('#dev_toast'),'Fehler: '+e,false); }
}
{ const mo=$('#mzOpenBtn'); if(mo) mo.onclick=mzOpen; }
// Esc schliesst den offenen Dialog (der Betriebsmodus-Assistent liegt ueber allem).
document.addEventListener('keydown',e=>{
  if(e.key!=='Escape') return;
  if(!$('#mzOv').hidden) mzClose(); else if(!$('#gvOv').hidden) gvClose(); else if(!$('#geOv').hidden) geClose();
});
