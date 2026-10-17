// LoxPanel-Konfigurator, Teil 8 von 11: Rubrik Einstellungen, Ersteinrichtung, SIP, Kalender.
// Die Teile laden nacheinander aus config.html (script src), alle Funktionen sind global;
// was beim Laden ausgefuehrt wird, darf nur Funktionen frueherer Teile rufen.

/* ============================================================
   SETTINGS-Rubrik (frühere /settings-Seite als Reiter)
   ============================================================ */
let SET=null;
function flash(el,msg,ok){ if(!el)return; el.textContent=msg; el.className='toast show '+(ok?'ok':'err'); setTimeout(()=>{ if(!el.classList.contains('warn')) el.classList.remove('show'); },4000); }

// Version, Commit (kurz, ganz im Tooltip) und Bauzeit in der Ortszeit des Browsers
function versionZeigen(v){
  const el=$('#lpver'); if(!el) return;
  const teile=[v.version?'LoxPanel '+v.version:T('Version unbekannt')];
  if(v.commit) teile.push(v.commit.slice(0,7));
  else if(v.inhalt) teile.push(T('Stand')+' '+v.inhalt.slice(0,7));   // lokaler Build ohne Git
  const d=v.gebaut?new Date(v.gebaut):null;
  if(d&&!isNaN(d)) teile.push(T('gebaut')+' '+d.toLocaleString(undefined,
    {day:'2-digit',month:'2-digit',year:'numeric',hour:'2-digit',minute:'2-digit'}));
  el.textContent=teile.join(' · ');
  el.title=v.commit||v.inhalt||'';
}
async function loadSettings(){
  const r=await fetch('/api/settings'); SET=await r.json();
  const m=SET.miniserver||{};
  $('#ms_host').value=m.host||''; $('#ms_user').value=m.user||'';
  $('#ms_port').value=m.port||443; $('#ms_tls').checked=!!m.verify_tls;
  $('#ms_pass').placeholder = m.hasPass ? 'unverändert lassen' : 'Passwort eingeben';
  const c=$('#conn');
  if(c){ if(SET.connected){ c.innerHTML=T('Status:')+' <b class="ok">'+T('verbunden')+'</b> · '+SET.nControls+' Controls'; }
    else { c.innerHTML=T('Status:')+' <b class="bad">'+T('nicht verbunden')+'</b>'; } }
  versionZeigen(SET.version||{});
  const box=$('#ic_list');
  if(box && !OFFEN.has('intercom')){
    if(!(SET.intercoms||[]).length){ box.innerHTML='<div class="muted">'+T('Keine Intercom-Bausteine gefunden (Miniserver verbunden?).')+'</div>'; }
    else {
      box.innerHTML=SET.intercoms.map(ic=>
        '<div class="ic" data-uuid="'+esc(ic.uuid)+'"><div class="icname">'+esc(ic.name)+'</div>'+
        '<div class="field"><label class="lbl">'+T('Video-URL (MJPEG)')+'</label><input type="text" class="ic_url" value="'+esc(ic.url)+'" placeholder="http://192.168.1.201/cgi-bin/faststream.jpg?stream=full&fps=8"></div>'+
        '<div class="row2"><div class="field"><label class="lbl">'+T('Benutzer')+'</label><input type="text" class="ic_user" value="'+esc(ic.user)+'" autocomplete="off"></div>'+
        '<div class="field"><label class="lbl">'+T('Passwort')+'</label><input type="password" class="ic_pass" autocomplete="new-password" placeholder="'+(ic.hasPass?T('unverändert lassen'):'')+'"></div></div></div>'
      ).join('');
    }
  }
  const am=SET.audiometa||{};
  const ae=$('#am_enabled'); if(ae && !OFFEN.has('audio')) ae.checked=am.enabled!==false;
  const srv=$('#am_servers');
  if(srv){ const list=am.servers||[];
    srv.innerHTML = list.length
      ? T('Erkannte Audioserver:')+' '+list.map(esc).join(', ')
      : T('Kein Audioserver in der Loxone-Struktur gefunden.'); }
  // Nacht-Ausloeser (Vorgaben -> Nacht)
  { const nt=SET.night||{};
    NACHT.options=nt.options||[];
    if(!OFFEN.has('nacht')) NACHT.control=nt.control||'';
    nachtZeichnen(); }
  // Kalender & Wetter
  const cal=SET.calendar||{};
  if($('#cal_name')){
    // Offene Eingaben bleiben stehen: loadSettings() laeuft auch nach dem Speichern
    // anderer Bereiche und nach "Verbinden & Speichern" des Miniservers.
    const kalOffen=OFFEN.has('kalender');
    if(!kalOffen){
      $('#cal_name').value=cal.name||'Family';
      if($('#cal_holurl')) $('#cal_holurl').value=cal.holiday_url||'';
      $('#cal_lat').value=(cal.lat==null?'':cal.lat);
      $('#cal_lon').value=(cal.lon==null?'':cal.lon);
      $('#cal_days').value=cal.days||14;
      $('#cal_foredays').value=cal.fore_days||4;
      if($('#cal_svevents')) $('#cal_svevents').value=cal.sv_events||3;
      if($('#cal_colors')) $('#cal_colors').checked=cal.colors!==false;
    }
    const st=cal.status||{};
    // Kalenderliste aus der gespeicherten Config aufbauen; der Status kommt je
    // Quelle ueber ihren Schluessel dazu.
    CAL_PALETTE=cal.palette||CAL_PALETTE;
    CAL_MAX=cal.max_sources||CAL_MAX;
    CAL_STAT={}; (st.cal_sources||[]).forEach(q=>{ if(q&&q.key) CAL_STAT[q.key]=q; });
    // Nur uebernehmen, solange nichts Ungespeichertes in der Liste steht.
    if(!kalOffen){
      CALS=(cal.sources||[]).map(q=>({name:q.name||'',url:q.url||'',color:q.color||'',key:q.key||''}));
    }
    renderCals();
    const cs=$('#cal_status');
    if(cs){
      // Bei einem Aussetzer zeigt das Panel weiter den letzten guten Stand —
      // das muss hier dabeistehen, sonst sieht man einen Fehler und gleichzeitig
      // Termine am Panel und hält eines von beidem für falsch.
      // Ganzer Satz statt zusammengesetzter Fragmente: im Englischen steht die
      // Uhrzeit an anderer Stelle im Satz, und "Uhr." hat dort keine Entsprechung.
      const stale=st.events_stale?'<br><span class="ccmut">'
        +T('Die Visu zeigt weiter den Stand von {zeit} Uhr.').replace('{zeit}',esc(st.events_stale))
        +'</span>':'';
      const qs=st.cal_sources||[], kaputt=qs.filter(q=>q&&q.error).length;
      if(!CALS.length) cs.innerHTML='<span class="ccmut">'+T('Kein Kalender konfiguriert.')+'</span>';
      // Der genaue Fehler steht schon oben beim betroffenen Kalender — hier
      // nur noch, wie viele betroffen sind.
      else if(kaputt) cs.innerHTML='<b class="bad">'
        +T('{n} von {gesamt} Kalendern nicht geladen').replace('{n}',kaputt).replace('{gesamt}',qs.length)
        +'</b> <span class="ccmut">· '+T('Grund steht oben beim jeweiligen Kalender.')+'</span>'
        +' · '+(st.cal_count||0)+' '+T('Termine')+stale;
      else if(st.cal_error) cs.innerHTML='<b class="bad">'+T('Fehler:')+'</b> '+esc(st.cal_error)+stale;
      else cs.innerHTML='<b class="ok">'+T('Kalender geladen')+'</b> · '+(st.cal_count||0)+' '+T('Termine')
        +(CALS.length>1?' <span class="ccmut">'+T('aus {n} Kalendern').replace('{n}',CALS.length)+'</span>':'');
    }
    // Auto-Standort vom Miniserver als Platzhalter zeigen (falls keine Koordinaten gesetzt)
    const autoGeo=(cal.ms_lat!=null&&cal.ms_lon!=null);
    if(autoGeo){ $('#cal_lat').placeholder=cal.ms_lat; $('#cal_lon').placeholder=cal.ms_lon; }
    const ws=$('#cal_wxstatus');
    if(ws){
      const manual=(cal.lat!=null&&cal.lat!=='');
      const auto=(!manual&&autoGeo)
        ? ' <span class="ccmut">· '+T('Automatisch vom Miniserver:')+' '+esc(cal.ms_location||'')+' ('+cal.ms_lat+' / '+cal.ms_lon+')</span>'
        : '';
      // Der Loxone-Wetterserver hat Vorrang; dann sind Koordinaten und Open-Meteo unbenutzt.
      if(st.wx_source==='miniserver') ws.innerHTML='<b class="ok">'+T('Wetter vom Loxone-Wetterserver')+'</b>'
        +' <span class="ccmut">· '+T('Open-Meteo wird nicht abgefragt.')+'</span>';
      else if(st.wx_error) ws.innerHTML='<b class="bad">'+T('Fehler:')+'</b> '+esc(st.wx_error);
      else if(st.wx_configured) ws.innerHTML='<b class="ok">'+T('Wetter geladen')+'</b>'+auto;
      else if(autoGeo) ws.innerHTML='<span class="ccmut">'+T('Standort vom Miniserver wird verwendet.')+'</span>'+auto;
      else ws.innerHTML='<span class="ccmut">'+T('Kein Standort konfiguriert.')+'</span>';
    }
  }
  einrichtungAnwenden(SET);
}

$('#ms_save').onclick=async()=>{
  const body={host:$('#ms_host').value.trim(),user:$('#ms_user').value.trim(),
    port:parseInt($('#ms_port').value)||443,verify_tls:$('#ms_tls').checked};
  const pw=$('#ms_pass').value; if(pw) body.pass=pw;
  $('#ms_save').disabled=true;
  EINR_VERSUCH=''; $('#ms_toast').className='toast';
  try{
    const r=await fetch('/api/settings/miniserver',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
    const j=await r.json();
    if(j.ok){ flash($('#ms_toast'),'✓ Verbunden — '+j.nControls+' Controls',true); $('#ms_pass').value=''; loadSettings(); }
    else {
      // Fester Text (uebersetzt), der Fehler des Miniservers getrennt dahinter
      EINR_VERSUCH=T(j.error||'Fehler')+(j.fehler?' ('+j.fehler+')':'');
      if(j.gespeichert||j.connected){
        // Gespeichert, aber nicht geprueft (oder verbunden, aber nicht
        // gespeichert): Die Warnung bleibt bis zum naechsten Versuch stehen.
        const t=$('#ms_toast'); t.textContent=EINR_VERSUCH; t.className='toast show warn';
        if(j.gespeichert) $('#ms_pass').value='';
        loadSettings();
      } else flash($('#ms_toast'),EINR_VERSUCH,false);
    }
  }catch(e){ EINR_VERSUCH=T('Fehler:')+' '+e; flash($('#ms_toast'),EINR_VERSUCH,false); }
  einrichtungStand();
  $('#ms_save').disabled=false;
};

// ---- Ersteinrichtung ----
// Solange der Server keine Struktur vom Miniserver hat (einrichtung aus
// /api/settings), fuehrt der Konfigurator zuerst zum Zugang: offen sind nur
// Settings -> Miniserver und Sicherung (EINR_SUBS), denn Ansichten, Geraete und
// "Geraet einrichten" brauchen Raeume und Bausteine. Er fragt den Stand alle
// EINR_TAKT_MS nach. Steht die Verbindung - ueber "Verbinden & Speichern" oder
// von selbst -, laedt die Seite neu, damit alles frisch vom Server kommt, und
// zeigt danach den naechsten Schritt (verbundenZeigen).
function einrichtungGesperrt(sub){ return !!EINR && rubric==='settings' && !EINR_SUBS.includes(sub); }
function einrichtungAnwenden(s){
  const vorher=!!EINR;
  EINR=s.einrichtung||null; EINR_MS=s.miniserver||{};
  if(!EINR){ if(vorher) einrichtungFertig(s.nControls); return; }
  const titel=T('Erst den Miniserver verbinden');
  document.querySelectorAll('.rub').forEach(b=>{ if(b.dataset.rub!=='settings'){ b.disabled=true; b.title=titel; } });
  const ab=$('#addBtn'); if(ab){ ab.disabled=true; ab.title=titel; }
  const pl=$('#plist'); if(pl) pl.classList.add('gesperrt');
  $('#einrOk').hidden=true; $('#einr').hidden=false;
  einrichtungStand();
  if(!vorher) setRubric('settings');
  clearTimeout(EINR_TIMER); EINR_TIMER=setTimeout(einrichtungNachfragen, EINR_TAKT_MS);
}
// Zeile unter dem Hinweis: der eigene letzte Versuch, sonst der Stand des Servers.
// Ersatz als Funktion: ein $& im Host ist sonst ein Ersetzungsmuster.
function einrichtungStand(){
  const el=$('#einrStand'); if(!el||!EINR) return;
  const host=()=>EINR.host||'';
  if(EINR_VERSUCH) el.innerHTML='<b class="bad">'+esc(EINR_VERSUCH)+'</b>';
  else if(EINR.stand==='fehler') el.innerHTML='<b class="bad">'+esc(T('Keine Verbindung zu {host}:').replace('{host}',host))+'</b> '+esc(EINR.fehler);
  else if(EINR.stand==='verbindet') el.textContent=T('Verbindung zu {host} wird aufgebaut …').replace('{host}',host);
  else if(EINR_MS.host) el.textContent=T('Der gespeicherte Zugang ist nicht verbunden. Angaben prüfen und erneut „Verbinden & Speichern“.');
  else el.textContent=T('Noch kein Miniserver eingetragen.');
}
async function einrichtungNachfragen(){
  EINR_TIMER=null;
  if(!EINR) return;
  try{ einrichtungAnwenden(await (await fetch('/api/settings')).json()); return; }   // setzt den naechsten Takt
  catch(e){ /* Server gerade nicht erreichbar (z. B. Neustart): weiter nachfragen */ }
  EINR_TIMER=setTimeout(einrichtungNachfragen, EINR_TAKT_MS);
}
function einrichtungFertig(n){
  clearTimeout(EINR_TIMER); EINR_TIMER=null;
  try{ sessionStorage.setItem(EINR_KEY, String(n||0)); }catch(e){}
  OFFEN.clear(); location.reload();
}
function verbundenZeigen(){
  let n=null;
  try{ n=sessionStorage.getItem(EINR_KEY); sessionStorage.removeItem(EINR_KEY); }catch(e){ n=null; }
  if(n==null||EINR) return;
  $('#einrOkText').textContent=T('Bausteine geladen: {n}. Alle Bereiche sind jetzt offen.').replace('{n}',()=>n);
  $('#einrSicherung').hidden=!SET_TABS.some(t=>t.k==='backup');
  $('#einrOk').hidden=false;
  subSet='miniserver'; setRubric('settings');
}
// Schritt 1 (Miniserver) ist erledigt: weiter mit Gerät einrichten
$('#einrAssistent').onclick=()=>{ $('#einrOk').hidden=true; setRubric('overview'); geOpen(); };
$('#einrSicherung').onclick=()=>{ $('#einrOk').hidden=true; subSet='backup'; setRubric('settings'); };

// Speichern der Einstellungs-Karten: je eine Funktion, die Speicherleiste ruft sie
// (speichernAlles) und laedt danach einmal neu.
function intercomSpeichern(){
  const intercoms={};
  document.querySelectorAll('.ic[data-uuid]').forEach(n=>{
    const e={url:n.querySelector('.ic_url').value.trim(),user:n.querySelector('.ic_user').value.trim()};
    const p=n.querySelector('.ic_pass').value; if(p)e.pass=p;
    intercoms[n.dataset.uuid]=e;
  });
  return postJson('/api/settings/intercom', {intercoms});
}

// ---- SIP: Zugang je Intercom (gesicherte Details des Miniservers) und Pruefung ----
// Laedt bei jedem Oeffnen des Reiters neu; jede Intercom kostet eine verschluesselte
// Anfrage an den Miniserver, darum nie zwei Ladevorgaenge gleichzeitig.
let SIP_LAEUFT=null;
function loadSip(){
  if(!SIP_LAEUFT) SIP_LAEUFT=sipLaden().finally(()=>{ SIP_LAEUFT=null; });
  return SIP_LAEUFT;
}
async function sipLaden(){
  const box=$('#sip_list'); if(!box) return;
  box.innerHTML='<div class="muted">'+esc(T('Frage den Miniserver …'))+'</div>';
  let j;
  try{ j=await (await fetch('/api/sip')).json(); }
  catch(e){ box.innerHTML='<div class="muted"><b class="bad">'+esc(T('Fehler'))+'</b> '+esc(String(e))+'</div>'; return; }
  const liste=j.intercoms||[];
  if(!liste.length){ box.innerHTML='<div class="muted">'+esc(T('Keine Intercom-Bausteine gefunden (Miniserver verbunden?).'))+'</div>'; return; }
  // details.deviceType laut Strukturdoku 17.0: 0 und 1 bei Intercom und IntercomV2, 2 nur bei Intercom
  const geraet={0:T('Andere oder unbekannte Türstation'),1:'Loxone Intercom',2:'Loxone Intercom XL'};
  // Baustein in Loxone Config: Intercom ist die Tuersteuerung ("Door Controller"), IntercomV2 der Baustein Intercom
  const baustein={Intercom:T('Baustein Türsteuerung'),IntercomV2:T('Baustein Intercom')};
  box.innerHTML=liste.map(ic=>{
    const info=[ic.room,geraet[ic.deviceType],baustein[ic.type]].filter(Boolean).map(esc).join(' · ');
    // Miniserver nennt keinen SIP-Zugang: sagen, wo er in Loxone Config hingehoert.
    // Fuer die Loxone Intercom am Baustein Intercom beschreibt die Strukturdoku keinen.
    const hinweis=!ic.ohneSip?''
      : (ic.type==='IntercomV2'&&ic.deviceType===1)
        ? T('Für die Loxone Intercom am Baustein Intercom beschreibt die Strukturdoku von Loxone keinen SIP-Zugang.')
        : T('Ohne SIP-Adresse gibt es nichts zu prüfen. Die Adresse für Audio steht in Loxone Config am Baustein der Intercom (bei einer benutzerdefinierten Intercom „Host für Audio (intern)“); nach dem Speichern in den Miniserver diesen Reiter neu öffnen. Steht sie dort und fehlt hier trotzdem, gibt der Miniserver sie für diesen Baustein nicht heraus.');
    const rumpf=ic.sip
      ? '<dl class="sipzug"><dt>'+esc(T('SIP-Adresse'))+'</dt><dd>'+esc(ic.sip.host)+'</dd>'+
        '<dt>'+esc(T('Benutzer'))+'</dt><dd>'+(ic.sip.user?esc(ic.sip.user):'–')+'</dd>'+
        '<dt>'+esc(T('Passwort'))+'</dt><dd>'+esc(ic.sip.hasPass?T('vorhanden'):T('keins'))+'</dd></dl>'+
        '<div class="actions"><button class="btn ghost sip_pruefen">'+esc(T('Verbindung prüfen'))+'</button></div>'+
        '<div class="sipres"></div>'
      : '<p class="sipfehl"><b class="bad">'+esc(T(ic.error||'Fehler'))+'</b></p>'+(ic.felder?sipFelder(ic.felder):'')+
        (hinweis?'<p class="siphinweis">'+esc(hinweis)+'</p>':'');
    return '<div class="ic sip" data-uuid="'+esc(ic.uuid)+'"><div class="icname">'+esc(ic.name)+
      (info?'<span class="sipgeraet">'+info+'</span>':'')+'</div>'+rumpf+'</div>';
  }).join('');
  box.querySelectorAll('.sip_pruefen').forEach(b=>b.onclick=()=>sipPruefen(b));
}
// Aufbau der gesicherten Details, wenn kein SIP-Zugang darin steht: nur Feldnamen
// und ob sie gefuellt sind (Werte schickt der Server nicht)
function sipFelder(f){
  const leer=' ('+esc(T('leer'))+')';
  const teile=Object.keys(f).map(k=>{
    const v=f[k];
    if(v&&typeof v==='object'){
      const n=Object.keys(v);
      return esc(k)+': '+(n.length?n.map(x=>esc(x)+(v[x]?'':leer)).join(', '):esc(T('leer')));
    }
    return esc(k)+(v?'':leer);
  });
  return '<p class="sipdiag">'+esc(T('Gesicherte Details vom Miniserver:'))+' '+
    (teile.length?teile.join(' · '):esc(T('leer')))+'</p>';
}
async function sipPruefen(b){
  const karte=b.closest('.sip'), res=karte.querySelector('.sipres');
  b.disabled=true; res.innerHTML='<span class="laeuft">'+esc(T('Prüfe …'))+'</span>';
  try{
    const r=await fetch('/api/sip/pruefen',{method:'POST',headers:{'Content-Type':'application/json'},
                                            body:JSON.stringify({uuid:karte.dataset.uuid})});
    res.innerHTML=sipErgebnis(await r.json());
  }catch(e){ res.innerHTML='<b class="bad">'+esc(T('Fehler'))+'</b> '+esc(String(e)); }
  finally{ b.disabled=false; }
}
function sipErgebnis(j){
  if(!j.ok||!j.erreichbar) return '<b class="bad">'+esc(T(j.error||'Fehler'))+'</b>';
  const text={'angenommen':T('Die Türstation antwortet und nimmt die Anmeldung an.'),
              'nicht verlangt':T('Die Türstation antwortet und verlangt keine Anmeldung.'),
              'abgelehnt':T('Die Türstation lehnt die Anmeldung ab.'),
              'kein Passwort':T('Die Türstation verlangt eine Anmeldung, der Miniserver nennt aber kein Passwort.'),
              'unbekanntes Verfahren':T('Die Türstation verlangt ein Anmeldeverfahren, das LoxPanel nicht kennt.')}[j.anmeldung];
  const gut=j.anmeldung==='angenommen'||j.anmeldung==='nicht verlangt';
  const d=[];
  if(text&&j.error) d.push(esc(T(j.error)));        // etwa welches Verfahren
  if(j.antwort) d.push(esc(T('Antwort:'))+' '+esc(j.antwort)+(j.ms!=null?' ('+esc(String(j.ms))+' ms)':''));
  if(j.gegenstelle) d.push(esc(T('Gegenstelle:'))+' '+esc(j.gegenstelle));
  if((j.codecs||[]).length) d.push(esc(T('Codecs:'))+' '+esc(j.codecs.join(', ')));
  if((j.methoden||[]).length) d.push(esc(T('Methoden:'))+' '+esc(j.methoden.join(', ')));
  return '<b class="'+(gut?'ok':'bad')+'">'+(gut?'✓ ':'')+esc(text||T(j.error||'Fehler'))+'</b>'+
    (d.length?'<div class="sipdet">'+d.join(' · ')+'</div>':'');
}

// Nacht-Ausloeser: Arbeitskopie wie CALS. Das Feld steht unter Vorgaben -> Nacht und wird
// mit dem Editor neu gezeichnet; solange 'nacht' offen ist, ueberschreibt loadSettings()
// die Wahl nicht.
let NACHT={control:'', options:[]};
function nachtZeichnen(){
  const sel=$('#nt_control'); if(!sel) return;
  const c=NACHT.control||'', bekannt=NACHT.options.some(o=>o.uuid===c);
  sel.innerHTML='<option value="">'+T('— kein Auslöser (Sonnenuntergang) —')+'</option>'
    + (c && !bekannt ? '<option value="'+esc(c)+'" selected>'+esc(T('Baustein nicht mehr in der Anlage'))+' ('+esc(c)+')</option>' : '')
    + NACHT.options.map(o=>'<option value="'+esc(o.uuid)+'"'+(o.uuid===c?' selected':'')+'>'
        + esc((o.room?o.room+' · ':'')+o.name+' ('+o.type+')')+'</option>').join('');
}
function nachtSpeichern(){ return postJson('/api/settings/night', {control:NACHT.control||''}); }
function audioSpeichern(){ return postJson('/api/settings/audiometa', {enabled:$('#am_enabled').checked}); }

// ---- Kalenderliste (mehrere iCal-Abos) ----
// CALS ist die Arbeitskopie: Eingaben schreiben direkt hinein, damit ein
// Hinzufuegen oder Loeschen die anderen Zeilen nicht zuruecksetzt.
let CALS=[], CAL_STAT={}, CAL_MAX=8;
// Geaenderte Eingaben melden den Bereich 'kalender' bei der Speicherleiste (OFFEN);
// solange er offen ist, ueberschreibt loadSettings() die Arbeitskopie nicht.
let CAL_PALETTE=['#e0a24d','#52b881','#6aa9e0','#c98ad4','#e2695f','#4fc3c3','#b2c94a','#9a8fe0'];
function calStatHTML(q){
  const st=q.key?CAL_STAT[q.key]:null;
  if(!st) return q.url?'<span class="calst">'+T('noch nicht geladen')+'</span>':'';
  if(st.error) return '<span class="calst err"><b class="bad">'+T('Fehler:')+'</b> '+esc(st.error)
    +(st.stale?' · '+T('Visu zeigt den Stand von {zeit} Uhr.').replace('{zeit}',esc(st.stale)):'')+'</span>';
  return '<span class="calst"><b class="ok">'+T('geladen')+'</b> · '+(st.count||0)+' '+T('Termine')+'</span>';
}
function renderCals(){
  const box=$('#cal_list'); if(!box) return;
  if(!CALS.length){ box.innerHTML='<div class="calempty">'+T('Noch kein Kalender. Mit „＋ Kalender hinzufügen" den ersten Abo-Link eintragen.')+'</div>'; }
  else box.innerHTML=CALS.map((q,i)=>
    '<div class="cal" data-i="'+i+'">'+
      '<div class="calh"><span class="caldot" style="background:'+esc(q.color||CAL_PALETTE[i%CAL_PALETTE.length])+'"></span>'+
      '<span class="caln">'+esc(q.name||(T('Kalender')+' '+(i+1)))+'</span>'+calStatHTML(q)+
      '<button class="btn del sm" data-caldel="'+i+'">'+T('Entfernen')+'</button></div>'+
      '<div class="row2">'+
        '<div class="field" style="max-width:260px"><label class="lbl">'+T('Name')+'</label>'+
          '<input type="text" class="cal_n" data-i="'+i+'" value="'+esc(q.name||'')+'" placeholder="'+T('z.B. Müllabfuhr')+'"></div>'+
        '<div class="field" style="max-width:90px"><label class="lbl">'+T('Farbe')+'</label>'+
          '<input type="color" class="cal_c" data-i="'+i+'" value="'+esc(q.color||CAL_PALETTE[i%CAL_PALETTE.length])+'"></div>'+
      '</div>'+
      '<div class="field"><label class="lbl">'+T('iCal-Abo-URL')+'</label>'+
        '<input type="text" class="cal_u" data-i="'+i+'" value="'+esc(q.url||'')+'" placeholder="webcal://p…-caldav.icloud.com/published/2/…"></div>'+
    '</div>').join('');
  // Eingaben laufen in die Arbeitskopie, ohne die Liste neu zu zeichnen (das
  // wuerde den Cursor aus dem Feld werfen).
  box.querySelectorAll('.cal_n').forEach(inp=>inp.oninput=()=>{
    const i=+inp.dataset.i; CALS[i].name=inp.value; bereichOffen('kalender');
    const n=box.querySelector('.cal[data-i="'+i+'"] .caln');
    if(n) n.textContent=inp.value.trim()||(T('Kalender')+' '+(i+1));
  });
  box.querySelectorAll('.cal_u').forEach(inp=>inp.oninput=()=>{
    const i=+inp.dataset.i; CALS[i].url=inp.value; bereichOffen('kalender');
    // Der Status haengt am Schluessel der ALTEN URL. Bleibt er stehen, behauptet
    // die Zeile weiter "geladen · 14 Termine" fuer einen Kalender, der so gar
    // nicht mehr eingetragen ist.
    CALS[i].key='';
    const st=box.querySelector('.cal[data-i="'+i+'"] .calst');
    if(st) st.remove();
  });
  box.querySelectorAll('.cal_c').forEach(inp=>inp.oninput=()=>{
    const i=+inp.dataset.i; CALS[i].color=inp.value; bereichOffen('kalender');
    const d=box.querySelector('.cal[data-i="'+i+'"] .caldot');
    if(d) d.style.background=inp.value;
  });
  box.querySelectorAll('[data-caldel]').forEach(b=>b.onclick=()=>{
    CALS.splice(+b.dataset.caldel,1); bereichOffen('kalender'); renderCals();
  });
}
// Erste noch freie Farbe der Palette. Ueber die Listenlaenge zu gehen waere
// falsch: nach dem Loeschen einer Zeile bekaeme die naechste neue die Farbe
// einer bestehenden.
function freieFarbe(){
  const vergeben=new Set(CALS.map(q=>(q.color||'').toLowerCase()));
  return CAL_PALETTE.find(c=>!vergeben.has(c.toLowerCase()))
      || CAL_PALETTE[CALS.length%CAL_PALETTE.length];
}
if($('#cal_add')) $('#cal_add').onclick=()=>{
  if(CALS.length>=CAL_MAX){ flash($('#cal_toast'),T('Mehr als {max} Kalender gehen nicht.').replace('{max}',CAL_MAX),false); return; }
  bereichOffen('kalender');
  CALS.push({name:'',url:'',color:freieFarbe(),key:''});
  renderCals();
  const felder=$('#cal_list').querySelectorAll('.cal_n');
  if(felder.length) felder[felder.length-1].focus();
};

function kalenderSpeichern(){
  const body={
    name:$('#cal_name').value.trim(),
    sources:CALS.filter(q=>(q.url||'').trim()).map(q=>({name:(q.name||'').trim(),url:q.url.trim(),color:q.color||''})),
    holiday_url:($('#cal_holurl')?$('#cal_holurl').value.trim():''),
    lat:$('#cal_lat').value.trim(), lon:$('#cal_lon').value.trim(),
    colors:($('#cal_colors')?$('#cal_colors').checked:true),
    sv_events:parseInt($('#cal_svevents')&&$('#cal_svevents').value)||3,
    days:parseInt($('#cal_days').value)||14, fore_days:parseInt($('#cal_foredays').value)||4};
  return postJson('/api/settings/calendar', body);
}
// Eingaben der Karten melden ihren Bereich bei der Speicherleiste
[['#ic_list','intercom'],['#am_enabled','audio'],
 ['section.spane[data-sub="calendar"]','kalender']].forEach(([sel,k])=>{
  const el=$(sel); if(!el) return;
  ['input','change'].forEach(ev=>el.addEventListener(ev, ()=>bereichOffen(k)));
});
// Unter Geraete zaehlen nur die Einstellungen der Karte (.dev), nicht die Wahl der
// Ansicht in der Zeile Zeigt (.agsel, die schaltet live um) und nicht der Name eines
// Geraets ohne Namen. DEV folgt jeder Eingabe, damit die Ansicht nennen kann, welches
// Geraet sie ueberstimmt.
{ const g=$('#geraete');
  if(g){ ['input','change'].forEach(ev=>g.addEventListener(ev, e=>{ if(!e.target.closest('.dev') || e.target.classList.contains('agsel')) return;
      readDevFromDom(); bereichOffen('geraete'); geraetErbtZeichnen(); }));
    g.addEventListener('click', e=>{ const b=e.target.closest('[data-gerbt-zurueck]'); if(!b) return;
      const row=b.closest('.dev'), inp=row&&row.querySelector(b.dataset.gerbtZurueck==='tileTarget'?'.dt_ziel':'.ds_scale');
      if(!inp) return;
      inp.value=''; inp.dispatchEvent(new Event('change',{bubbles:true})); }); } }
// "× zurücksetzen" in Ansicht und Vorgaben: der eigene Eintrag faellt weg, es gilt wieder der geerbte
{ const h=$('#pconfHost');
  if(h) h.addEventListener('click', e=>{ const b=e.target.closest('[data-erbt-zurueck]'); if(!b) return;
    const p=PANELS[cur]; if(!p||!p.ui) return;
    delete p.ui[b.dataset.erbtZurueck]; markDirty(); renderEditor(); }); }
