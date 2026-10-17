// LoxPanel-Konfigurator, Teil 4 von 11: Speicherleiste, Vorschau in der Visu und am Geraet.
// Die Teile laden nacheinander aus config.html (script src), alle Funktionen sind global;
// was beim Laden ausgefuehrt wird, darf nur Funktionen frueherer Teile rufen.

// ---- Eine Speicherleiste fuer alles (Konzept "Konfigurator neu ordnen", Schritt 2) ----
// OFFEN haelt fest, was noch nicht gespeichert ist: je Ansicht 'ansicht:<Kennung>'
// ('ansicht:__global__' = Vorgaben), dazu die Bereiche ausserhalb der Ansichten. Der Wert
// ist eine laufende Nummer: Speichern hakt nur ab, was seit dem Absenden nicht wieder
// geaendert wurde. Ein Rubrikwechsel verliert nichts (alles bleibt in der Arbeitskopie
// bzw. in den Feldern), nur Neuladen oder Schliessen der Seite fragt nach.
const OFFEN=new Map();
let OFFEN_NR=0;
const BEREICH_NAME={geraete:'Geräte', nacht:'Nachtmodus', intercom:'Kamera / Türstation', audio:'Audio', kalender:'Kalender & Wetter'};
function markieren(k){
  OFFEN.set(k, ++OFFEN_NR);
  const t=$('#toast'); if(t){ t.className='toast'; t.textContent=''; }
  leisteZeigen();
}
function bereichOffen(k){ markieren(k); }
function ansichtenOffen(){ for(const k of OFFEN.keys()) if(k.indexOf('ansicht:')===0) return true; return false; }
function allesOffen(){ return OFFEN.size>0; }
function offenStand(filter){ const m=new Map(); OFFEN.forEach((n,k)=>{ if(filter(k)) m.set(k,n); }); return m; }
function erledigt(stand){ stand.forEach((n,k)=>{ if(OFFEN.get(k)===n) OFFEN.delete(k); }); }
function offenNamen(){
  const n=[];
  OFFEN.forEach((_,k)=>{
    if(k.indexOf('ansicht:')!==0) return;
    const id=k.slice(8);
    if(id==='__global__') n.push(T('Vorgaben'));
    else if(PANELS[id]) n.push(T('Ansicht')+' '+(PANELS[id].title||id));
  });
  Object.keys(BEREICH_NAME).forEach(k=>{ if(OFFEN.has(k)) n.push(T(BEREICH_NAME[k])); });
  return n;
}
let SPEICHERN_LAEUFT=false;
function leisteZeigen(){
  const n=offenNamen(), b=$('#saveBtn'), o=$('#offenTxt');
  if(b) b.disabled=SPEICHERN_LAEUFT || !n.length;
  if(o) o.textContent = n.length ? T('Nicht gespeichert:')+' '+n.join(', ') : T('Alles gespeichert');
}
// Ergebnisse {ok, text, warn} in der Meldungsleiste; eine Warnung ueber nicht
// Uebernommenes bleibt bis zur naechsten Aenderung stehen, alles andere geht nach 4 s.
function meldungZeigen(erg){
  const t=$('#toast'); if(!t || !erg.length) return;
  const fehler=erg.some(e=>!e.ok), warn=erg.some(e=>e.warn);
  t.className='toast show'+(fehler?' err':(warn?' warn':''));
  t.textContent=erg.map(e=>e.text).join(' · ');
  setTimeout(()=>{ if(t && !t.classList.contains('warn')) t.classList.remove('show'); }, 4000);
}
// Speichert alles Offene nacheinander: erst die Ansichten (Betriebsmodi der Geraete
// verweisen auf sie), dann die Geraete, dann die Einstellungen. Ein Bereich, der
// scheitert, bleibt offen; die anderen gelten.
async function speichernAlles(){
  if(SPEICHERN_LAEUFT) return;
  SPEICHERN_LAEUFT=true; leisteZeigen();
  const erg=[]; let einst=false, kal=false;
  try{
    let ansichtenOk=true;
    if(ansichtenOffen()){ const e=await ansichtenSpeichern(); erg.push(e); ansichtenOk=e.ok; }
    // Ohne die Ansichten keine Geraete: der Server verwirft Betriebsmodi, deren Ansicht
    // er nicht kennt (etwa eine gerade neu angelegte), sie blieben dann still weg
    if(OFFEN.has('geraete') && ansichtenOk) erg.push(await geraeteSpeichern());
    for(const [k,f] of [['nacht',nachtSpeichern],['intercom',intercomSpeichern],['audio',audioSpeichern],['kalender',kalenderSpeichern]]){
      if(!OFFEN.has(k)) continue;
      const stand=offenStand(x=>x===k);
      const e=await einstellungSpeichern(k, f);
      erg.push(e);
      if(e.ok){ erledigt(stand); einst=true; if(k==='kalender') kal=true; }
    }
  } finally { SPEICHERN_LAEUFT=false; }
  meldungZeigen(erg); leisteZeigen();
  standNeuNachziehen();
  // Erst jetzt neu laden: nach jeder einzelnen Karte wuerde es die noch offenen
  // ueberschreiben. Den Kalender holt der Server frisch, darum kurz warten.
  if(einst) setTimeout(loadSettings, kal?1500:0);
}
async function einstellungSpeichern(k, f){
  const name=T(BEREICH_NAME[k]);
  try{
    const j=await f();
    return j.ok ? {ok:true, text:'✓ '+T('Gespeichert:')+' '+name} : {ok:false, text:name+': '+(j.error||T('Fehler'))};
  }catch(e){ return {ok:false, text:name+': '+e}; }
}
window.addEventListener('beforeunload',e=>{ if(allesOffen()){ e.preventDefault(); e.returnValue=''; } });

// Stand des Servers (/api/devices "stand", der Commit): den der ersten Abfrage
// merkt sich die Seite. Meldet ein neu gestarteter Server einen anderen, laeuft
// hier noch der alte Konfigurator - ohne offene Aenderungen laedt er neu, sonst
// sagt es die Speicherleiste und er laedt nach dem Speichern neu.
let SERVER_STAND=null, STAND_NEU=false;
function serverStandPruefen(st){
  if(!st) return;
  if(SERVER_STAND===null){ SERVER_STAND=st; return; }
  if(st===SERVER_STAND) return;
  STAND_NEU=true;
  standNeuNachziehen();
}
function standNeuNachziehen(){
  if(!STAND_NEU) return;
  if(!allesOffen() && !SPEICHERN_LAEUFT){ location.reload(); return; }
  const h=$('#standNeu'); if(!h || !h.hidden) return;
  h.innerHTML=esc(T('Neuer Stand auf dem Server – nach dem Speichern lädt die Seite neu.'))+
    ' <button type="button" class="minibtn" id="standNeuJetzt">'+esc(T('Jetzt neu laden'))+'</button>';
  h.hidden=false;
  $('#standNeuJetzt').onclick=()=>location.reload();
}

// ---- Vorschau in der echten Visu (Punkt 10, Teil 3) ----
// „Vorschau“ schickt das Profil samt allen ungespeicherten Aenderungen als
// Entwurf an den Server (/api/entwurf, nur im Speicher) und oeffnet die echte
// Visu damit in einem Fenster in der Groesse des Vorschaugeraets (Seiten-Editor).
// Solange das Fenster offen ist, zieht jede Aenderung nach; Speichern beendet den
// Entwurf, das Fenster zeigt dann das gespeicherte Profil.
// gen zaehlt die Speichervorgaenge: eine Antwort, die erst danach eintrifft, gehoert zu einem
// Entwurf, den der Server beendet hat, und darf weder ENTWURF aendern noch das Fenster lenken.
// geraet: das Geraet, das den Entwurf gerade zeigt (Punkt 12, sonst '')
const ENTWURF={token:'', id:'', win:null, timer:0, gen:0, geraet:''};
async function entwurfSenden(id=cur, p=PANELS[cur]){
  if(!p || p.__global) return null;
  const gen=ENTWURF.gen;
  const j=await postJson('/api/entwurf', {id:id, panel:p, token:(ENTWURF.id===id?ENTWURF.token:'')});
  if(gen!==ENTWURF.gen) return null;
  if(!j.ok) throw new Error(j.error||'?');
  ENTWURF.token=j.token; ENTWURF.id=id;
  return j;
}
// Die Visu im Fenster auf die Adresse bringen; zeigt es sie schon, hat der Server es neu geladen
function entwurfZiel(w, url){ if(w.location.pathname+w.location.search!==url) w.location.href=url; }
function entwurfFensterMass(p){
  const g=seGeraetReiter(p)||dieserBrowser();
  const b=Math.max(320, Math.min(g.vw, screen.availWidth-40)), h=Math.max(320, Math.min(g.vh, screen.availHeight-80));
  return 'popup=yes,width='+b+',height='+h;
}
async function entwurfOeffnen(){
  const p=PANELS[cur], t=$('#toast'); if(!p || p.__global) return;
  // Das Fenster gleich beim Klick oeffnen (sonst blockt der Browser es), die Adresse folgt
  const w=(ENTWURF.win && !ENTWURF.win.closed) ? ENTWURF.win : window.open('', 'loxpanel-entwurf', entwurfFensterMass(p));
  if(!w){ flash(t, T('Das Vorschaufenster hat der Browser blockiert.'), false); return; }
  try{
    const j=await entwurfSenden();
    if(!j) return;   // inzwischen gespeichert
    ENTWURF.win=w; entwurfZiel(w, j.url); w.focus();
    if((j.verworfen||[]).length) flash(t, T('Nicht übernommen:')+' '+j.verworfen.join('; '), false);
  }catch(e){ try{ w.close(); }catch(x){} flash(t, T('Vorschau nicht möglich:')+' '+e.message, false); }
}
function fensterOffen(){ return !!(ENTWURF.win && !ENTWURF.win.closed); }
function entwurfLaeuft(){ return fensterOffen() || !!ENTWURF.geraet; }   // Fenster offen oder ein Geraet zeigt ihn
function entwurfNachziehen(){
  if(!entwurfLaeuft() || ENTWURF.id!==cur) return;
  clearTimeout(ENTWURF.timer);
  ENTWURF.timer=setTimeout(async()=>{
    if(!entwurfLaeuft() || ENTWURF.id!==cur) return;
    // der Server laedt Fenster und Geraet mit diesem Entwurf selbst neu; ein Fenster, das auf
    // einer anderen Adresse steht (neuer Token), lenkt entwurfZiel um
    try{ const j=await entwurfSenden(); if(j && fensterOffen()) entwurfZiel(ENTWURF.win, j.url); }catch(e){}
  }, 600);
}
// ---- Vorschau am Geraet (Punkt 12) ----
// Derselbe Entwurf laeuft auf dem echten Geraet: /api/device/switch mit dem Token, nur an
// eine verbundene Visu (ein Agent kann den Token nicht tragen). Das Geraet kehrt zur vorigen
// Ansicht zurueck, wenn die Vorschau beendet wird oder 15 Minuten niemand mehr daran arbeitet;
// Speichern beendet sie ebenfalls (das Geraet zeigt dann das gespeicherte Profil).
// Es laeuft hoechstens eine Vorschau am Geraet: vor einer auf einem anderen Geraet endet die
// bisherige (gelingt das nicht, startet die neue nicht - sonst liefe die alte unbemerkt weiter).
async function vorschauAmGeraet(id, p, name){   // -> Fehlertext, '' wenn die Vorschau laeuft
  const t=$('#toast');
  if(ENTWURF.geraet && ENTWURF.geraet!==name){ const f=await vorschauGeraetBeenden(); if(f) return f; }
  try{
    const j=await entwurfSenden(id, p); if(!j) return T('Vorschau nicht möglich:')+' ?';
    const k=await postJson('/api/device/switch', {device:name, panel:id, entwurf:j.token, ip:DEVICE_IPS[name]||''});
    if(!k.ok){ const f=k.error||T('Fehler'); flash(t, f, false); return f; }
    ENTWURF.geraet=name; ENTWURF.seit=Date.now();
    if((j.verworfen||[]).length) flash(t, T('Nicht übernommen:')+' '+j.verworfen.join('; '), false);
    else flash(t, T('Vorschau läuft auf')+' '+name, true);
    vorGerKnopf();
    return '';
  }catch(e){ const f=T('Vorschau nicht möglich:')+' '+e.message; flash(t, f, false); return f; }
}
// Erst wenn der Server das Ende bestaetigt, gilt sie als beendet; sonst bleibt der Knopf
// "Am Gerät beenden" stehen, damit es sich wiederholen laesst. -> Fehlertext, '' wenn beendet
async function vorschauGeraetBeenden(){
  const name=ENTWURF.geraet; if(!name) return '';
  const t=$('#toast');
  let f='';
  try{ const j=await postJson('/api/vorschau/beenden', {device:name}); if(!j.ok) f=j.error||T('Fehler'); }
  catch(e){ f=e.message||String(e); }
  if(f){ f=T('Vorschau am Gerät nicht beendet:')+' '+f; flash(t, f, false); return f; }
  if(ENTWURF.geraet===name){ ENTWURF.geraet=''; vorGerKnopf(); }
  flash(t, T('Vorschau am Gerät beendet.'), true);
  return '';
}
// Welches Geraet? Das Vorschaugeraet des Seiten-Editors, sofern es ein echtes Geraet ist, sonst das
// Zielgeraet des Profils (seGeraetReiter nimmt es als Vorgabe)
function vorschauGeraetName(p){ const g=seGeraetReiter(p); return (g && g.quelle==='geraet') ? g.name : ''; }
function vorGerKnopf(){
  const b=$('#vorGerBtn'); if(!b) return;
  b.textContent=(ENTWURF.geraet && ENTWURF.id===cur) ? T('Am Gerät beenden') : T('Am Gerät ansehen');
}
async function vorGerKlick(){
  const p=PANELS[cur], t=$('#toast'); if(!p || p.__global) return;
  if(ENTWURF.geraet && ENTWURF.id===cur){ await vorschauGeraetBeenden(); return; }
  const name=vorschauGeraetName(p);
  if(!name){ flash(t, T('Für die Vorschau am Gerät im Seiten-Editor ein Gerät wählen, das verbunden ist.'), false); return; }
  if(!(DEVICE_CONN[name]>0)){ flash(t, name+' '+T('hat keine verbundene Visu – eine Vorschau braucht sie.'), false); return; }
  await vorschauAmGeraet(cur, p, name);
}
// Gespeichert: der Entwurf ist erledigt. Das offene Fenster schickt der Server selbst auf
// das gespeicherte Profil ({t:"entwurfEnde"}); hier nur nichts mehr nachziehen.
function entwurfBeendet(){
  clearTimeout(ENTWURF.timer); ENTWURF.gen++;
  ENTWURF.token=''; ENTWURF.id=''; ENTWURF.geraet=''; vorGerKnopf();
}

// Alles, was die ganze Liste der Ansichten an den Server schickt (Speichern, auch ueber
// "Geraet einrichten", und "Ansicht loeschen"), laeuft nacheinander. Jeder Auftrag nimmt
// seinen Stand erst, wenn er dran ist, und als tiefe Kopie: Was waehrenddessen getippt
// wird, geht nicht mit, und ein zweiter Auftrag baut auf dem Ergebnis des ersten auf.
let ANSICHTEN_KETTE=Promise.resolve();
function ansichtenAuftrag(f){
  const r=ANSICHTEN_KETTE.then(f);
  ANSICHTEN_KETTE=r.catch(()=>{});
  return r;
}
function tiefKopie(o){ return JSON.parse(JSON.stringify(o)); }
// Antwort von /api/panels: `panels` ist, was der Server tatsaechlich gespeichert hat
// (ohne Verworfenes); ohne das Feld gilt der abgeschickte Stand.
function gespeichertSetzen(j, gesendet){ GESPEICHERT=(j.panels && typeof j.panels==='object') ? j.panels : gesendet; }

async function ansichtenSpeichern(){
  clearTimeout(ENTWURF.timer); ENTWURF.gen++;   // Vorschau: ab jetzt nichts mehr nachziehen, Verspaetetes verwerfen
  return ansichtenAuftrag(async()=>{
    const stand=offenStand(k=>k.indexOf('ansicht:')===0);
    const panels={}; for(const k in PANELS){ if(k!=='__global__') panels[k]=tiefKopie(PANELS[k]); }
    const g=PANELS.__global__;
    const vorgaben=g ? {ui:tiefKopie(g.ui||{}), categories:tiefKopie(g.catColors||{})} : null;
    try{
      const j=await postJson('/api/panels', {panels});
      if(j.ok) gespeichertSetzen(j, panels);   // steht in der Datei, auch wenn die Vorgaben scheitern
      let okT=true, errT='';
      if(vorgaben){ const j2=await postJson('/api/theme', vorgaben); okT=j2.ok; errT=j2.error||''; }
      if(!(j.ok&&okT)) return {ok:false, text:'Fehler: '+(j.error||errT||'?')};
      erledigt(stand); entwurfBeendet();
      // Liste der Ansichten fuer die Geraete-Zuordnung auffrischen (sonst fehlt eine neue
      // Ansicht dort bis zum Reload - PANEL_IDS wird sonst nur beim Start geladen).
      try{ await loadPanelIds(); renderDevices(); }catch(e){}
      // Was der Server nicht uebernommen hat (unbekannt/ungueltig), nennen statt
      // es still zu verlieren; die Warnung bleibt stehen.
      const weg=j.verworfen||[];
      return {ok:true, warn:weg.length>0,
              text:'✓ Gespeichert ('+j.count+' Ansichten) — die Geräte haben automatisch neu geladen'+
                   (weg.length? ' · '+T('Nicht übernommen:')+' '+weg.join('; ') : '')};
    }catch(e){ return {ok:false, text:'Fehler: '+e}; }
  });
}
// Nur die Ansichten und Vorgaben (Geraet einrichten, Tests); die Leiste nimmt speichernAlles()
async function save(){ const e=await ansichtenSpeichern(); meldungZeigen([e]); leisteZeigen(); return e.ok; }
// "Ansicht loeschen" gilt nach der Rueckfrage sofort. Geschickt wird der zuletzt
// gespeicherte Stand ohne diese Ansicht; offene Aenderungen an anderen bleiben offen.
async function ansichtLoeschen(id){
  return ansichtenAuftrag(async()=>{
    if(GESPEICHERT[id]){
      const panels=tiefKopie(GESPEICHERT); delete panels[id];
      let j;
      try{ j=await postJson('/api/panels', {panels}); }catch(e){ j={ok:false, error:String(e)}; }
      if(!j.ok){ meldungZeigen([{ok:false, text:'Fehler: '+(j.error||'?')}]); return false; }
      gespeichertSetzen(j, panels);
    }
    if(ENTWURF.id===id) entwurfBeendet();
    delete PANELS[id]; OFFEN.delete('ansicht:'+id);
    cur='default'; tileSel=null; renderList(); setRubric('pconf'); leisteZeigen();
    meldungZeigen([{ok:true, text:'✓ '+T('Gelöscht:')+' '+id}]);
    try{ await loadPanelIds(); renderDevices(); }catch(e){}
    return true;
  });
}
