// LoxPanel-Konfigurator, Teil 10 von 11: Audio-Testton, Speichern-Knopf, Sicherung einspielen.
// Die Teile laden nacheinander aus config.html (script src), alle Funktionen sind global;
// was beim Laden ausgefuehrt wird, darf nur Funktionen frueherer Teile rufen.

// ---- Audio: Test-Ton ----
function fillAudioPanels(){
  const sel=$('#at_panel'); if(!sel) return;
  sel.innerHTML='<option value="">'+T('Alle Geräte')+'</option>'+
    PANEL_IDS.map(id=>'<option value="'+esc(id)+'">'+esc(id)+'</option>').join('');
}
$('#at_send').onclick=async()=>{
  const panel=$('#at_panel').value;
  $('#at_send').disabled=true;
  try{
    const r=await fetch('/api/testtone',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({panel})});
    const j=await r.json();
    if(j.ok){ flash($('#at_toast'), j.sent? ('✓ an '+j.sent+' '+(j.sent>1?'Geräte':'Gerät')+' gesendet') : 'Kein Gerät verbunden (Kiosk offen?)', j.sent>0); }
    else flash($('#at_toast'), j.error||'Fehler', false);
  }catch(e){ flash($('#at_toast'),'Fehler: '+e,false); }
  $('#at_send').disabled=false;
};

// ---- Speichern-Knopf ----
$('#saveBtn').onclick=speichernAlles;

// ---- Sicherung einspielen ----
// Nach dem Einspielen laedt die Seite neu: Profile, Geraete und Einstellungen im
// Speicher waeren sonst der alte Stand, und das naechste Speichern ueberschriebe
// die eingespielten Werte. Das Ergebnis wartet so lange in der sessionStorage
// und erscheint danach in der Rubrik Sicherung.
const RS_KEY='lp_einspiel_ergebnis';
const RS_MS={
  verbunden:'Miniserver: mit dem eingespielten Zugang neu verbunden.',
  unveraendert:'Miniserver: Zugang unverändert, die Verbindung bleibt.',
  kein_kennwort:'Miniserver: Kennwort fehlt – unter Einstellungen → Miniserver eintragen.',
  behalten:'Miniserver: Die Sicherung enthält keinen Zugang, der bisherige bleibt.',
  umgebung:'Miniserver: Der Zugang kommt hier aus den Umgebungsvariablen und bleibt.',
  keiner:'Miniserver: weder in der Sicherung noch hier eingetragen – unter Einstellungen → Miniserver eintragen.',
  kein_kennwort_behalten:'Miniserver: Für {ziel} aus der Sicherung fehlt das Kennwort, der bisherige Zugang bleibt. Zum Wechseln unter Einstellungen → Miniserver mit Kennwort eintragen.',
  unvollstaendig:'Miniserver: Benutzer fehlt – unter Einstellungen → Miniserver eintragen.',
  unvollstaendig_behalten:'Miniserver: Für {ziel} aus der Sicherung fehlt der Benutzer, der bisherige Zugang bleibt. Zum Wechseln unter Einstellungen → Miniserver vollständig eintragen.',
  fehler:'Miniserver: Verbindung mit dem eingespielten Zugang fehlgeschlagen:',
  fehler_behalten:'Miniserver: Verbindung mit dem eingespielten Zugang fehlgeschlagen, der bisherige Zugang bleibt:'};
function rsZiel(z){
  if(z.art==='miniserver') return T('Miniserver');
  if(z.art==='kamera') return T('Kamera')+' „'+z.name+'“';
  if(z.art==='display') return T('Display-Treiber')+' „'+z.name+'“';
  return z.name||'';
}
function rsZeigen(j, nichtNeuGeladen){
  const z=[], kw=j.kennwoerter||{};
  z.push('<b class="'+(j.ok?'ok':'bad')+'">'+esc(j.ok?T('✓ Eingespielt:'):T('Nur teilweise eingespielt:'))+' '+
         esc((j.dateien||[]).join(', ')||'–')+'</b>');
  if(j.error) z.push('<b class="bad">'+esc(T(j.error))+'</b>');
  if((j.nichtEingespielt||[]).length) z.push('<b class="bad">'+esc(T('Nicht eingespielt:'))+' '+esc(j.nichtEingespielt.join(', '))+'</b>');
  if(j.miniserver){
    const ziel=j.miniserverZiel||{};
    // Ersatz als Funktion: ein $& oder $' im Benutzernamen ist sonst ein Ersetzungsmuster
    z.push(esc(T(RS_MS[j.miniserver]||j.miniserver).replace('{ziel}', ()=>(ziel.host||'')+(ziel.user?' ('+ziel.user+')':'')))+
           (j.miniserverFehler?' '+esc(j.miniserverFehler):''));
  }
  if((kw.fehlen||[]).length) z.push('<b class="bad">'+esc(T('Kennwort fehlt, bitte unter Einstellungen eintragen:'))+'</b> '+
                                    esc(kw.fehlen.map(rsZiel).join(', ')));
  if((kw.behalten||[]).length) z.push(esc(T('Kennwort von diesem Server übernommen:'))+' '+esc(kw.behalten.map(rsZiel).join(', ')));
  if((j.nichtEnthalten||[]).length) z.push(esc(T('Nicht in der Sicherung, unverändert:'))+' '+esc(j.nichtEnthalten.join(', ')));
  if((j.verworfen||[]).length) z.push(esc(T('Nicht übernommen:'))+' '+esc(j.verworfen.join('; ')));
  if(nichtNeuGeladen) z.push('<b class="bad">'+esc(T('Bitte die Seite neu laden, damit der Konfigurator den eingespielten Stand zeigt.'))+'</b>');
  $('#rs_result').innerHTML=z.join('<br>');
}
function einspielErgebnisZeigen(){
  let j=null;
  try{ j=JSON.parse(sessionStorage.getItem(RS_KEY)||'null'); sessionStorage.removeItem(RS_KEY); }catch(e){ j=null; }
  if(!j) return;
  subSet='backup'; setRubric('settings'); renderSubtabs(); showSub('backup');
  rsZeigen(j, false);
}
// Erst die Datei waehlen, dann fragen: Der Dateidialog braucht den Klick
// selbst, nach einer Rueckfrage oeffnet ihn nicht jeder Browser.
$('#rs_pick').onclick=()=>{ $('#rs_file').value=''; $('#rs_file').click(); };
$('#rs_file').onchange=async()=>{
  const f=$('#rs_file').files[0]; if(!f) return;
  const frage=T('Die Sicherung ersetzt die Einstellungen dieses Servers. Am besten vorher „Einstellungen herunterladen“. Fortfahren?')+
    (allesOffen()?'\n\n'+T('Ungespeicherte Änderungen gehen dabei verloren.'):'');
  if(!confirm(frage)) return;
  $('#rs_pick').disabled=true; $('#rs_result').textContent='';
  let j;
  try{
    const r=await fetch('/api/restore',{method:'POST',headers:{'Content-Type':'application/zip'},body:f});
    j=(r.headers.get('content-type')||'').includes('json') ? await r.json() : {ok:false, error:'HTTP '+r.status};
  }catch(e){ j={ok:false, error:String(e)}; }
  $('#rs_pick').disabled=false;
  if((j.dateien||[]).length){            // ganz oder teilweise geschrieben: neu laden
    try{ sessionStorage.setItem(RS_KEY, JSON.stringify(j)); OFFEN.clear(); location.reload(); return; }
    catch(e){ rsZeigen(j, true); return; }
  }
  flash($('#rs_toast'), T('Nicht eingespielt'), false);
  $('#rs_result').innerHTML='<b class="bad">'+esc(j.error?T(j.error):T('Fehler'))+'</b>';
};
