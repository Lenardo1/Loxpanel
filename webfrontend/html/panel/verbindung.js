// LoxPanel-Visu, Teil 7 von 12: Kennung, Entwurf, Geraet, Sprache, Regler am Geraet, Verbindungszustand, connect() und die Nachrichten des Servers.
// Die Teile laden nacheinander aus panel.html (script src), alle Funktionen sind global;
// was beim Laden ausgefuehrt wird, darf nur Funktionen frueherer Teile rufen.

let booted=false;
const PANEL_ID = new URLSearchParams(location.search).get('panel') || '';
// Vorschau aus dem Konfigurator: ein noch nicht gespeichertes Profil, vom Server
// unter diesem Token im Speicher gehalten (/api/entwurf). Laeuft er ab, zeigt die
// Visu das gespeicherte Profil und sagt es (entwurfZeigen).
const ENTWURF = new URLSearchParams(location.search).get('entwurf') || '';
function entwurfZeigen(gilt){
  const m=el('entwurfMarke'); if(!m) return;
  if(!ENTWURF || gilt===undefined || gilt===null){ m.classList.add('hidden'); return; }
  m.textContent = gilt ? 'Entwurf – nicht gespeichert' : 'Entwurf abgelaufen – gespeicherte Ansicht';
  m.classList.toggle('alt', !gilt); m.classList.remove('hidden');
}
// Geraetename (physisches Panel, ?device=). Darueber adressiert der Server dieses
// Geraet (Betriebsmodus, Display, Ansicht wechseln) und listet es unter
// Einstellungen -> Panels. Quelle: ?device=<name> in der Kiosk-URL, sonst ein
// unter Einstellungen -> Panels vergebener Name (t:'setdevice', localStorage).
let DEVICE_ID = new URLSearchParams(location.search).get('device') || '';
try{ if(!DEVICE_ID) DEVICE_ID = localStorage.getItem('lp_device') || ''; }catch(e){}
let LANG='de-DE';   // Panel-Sprache (aus dem Profil, Server sendet sie im theme); steuert Datum/Uhr
// Horizontaler Feinversatz der ganzen Visu — live einstellbar ohne Redeploy:
//   ?x=-6  -> 6px nach links     ?x=8 -> nach rechts     ?x=0 -> zuruecksetzen
// Der Wert wird gemerkt (localStorage) und gilt dann auch ohne Parameter weiter.
(function(){
  const p=new URLSearchParams(location.search).get('x');
  if(p!==null) localStorage.setItem('lp_nudge_x', p);
  const v=localStorage.getItem('lp_nudge_x');
  if(v!==null && v!=='') document.documentElement.style.setProperty('--nudge-x',(parseFloat(v)||0)+'px');
})();
// Strichstaerke des Positionsrings live am echten Display einstellen (verschiedene
// Panels zeichnen duenne Linien unterschiedlich – Shelly braucht mehr fuer eine
// sichtbare Linie): ?ring=4 duenner · ?ring=8 dicker · ?ring=6 Standard. Gemerkt.
// Der gemerkte Geraetewert muss NACH den Theme-Variablen erneut gesetzt werden:
// seit die Strichstaerke auch aus der Konfiguration kommt, schickt der Server
// --posring-w mit, und der Theme-Push wuerde den Live-Test sonst ueberschreiben.
// Der Wert am Geraet gewinnt - genau das ist der Zweck des Reglers.
function posringOverride(){
  const v=localStorage.getItem('lp_posring_w');
  if(v!==null && v!=='') document.documentElement.style.setProperty('--posring-w', parseFloat(v)||6);
}
(function(){
  const p=new URLSearchParams(location.search).get('ring');
  if(p!==null) localStorage.setItem('lp_posring_w', p);
  posringOverride();
})();
// ---- Verbindungszustand ----
// Zwei Verbindungen tragen die Werte: dieser WebSocket zum LoxPanel-Server und
// die des Servers zum Miniserver ({t:'verbindung'}, mit Takt, Fristen und
// Texten der Leiste). Fehlt eine, sind die Werte nicht mehr bestaetigt:
// sendCmd() sperrt sofort, die Leiste #verbindung und die blasse Darstellung
// (.screen.verbweg) kommen erst nach verb.hinweis Sekunden - kurze Aussetzer
// blitzen so nicht auf -, oder sofort, sobald ein Tipp gesperrt wurde. Der
// Server meldet sich alle verb.takt Sekunden; bleibt er verb.stumm Sekunden
// still, gilt der WebSocket als abgerissen und wird neu aufgebaut (ein still
// verschwundener Server - WLAN, Strom - schlosse ihn sonst nie).
const verb={server:false, ms:true, msSeit:null, msStand:null, serverSeit:null,
            takt:0, stumm:0, hinweis:0, texte:null};
let verbBestaetigt=null;   // letzte Nachricht des Servers, als er den Miniserver noch erreichte
let verbWegAb=null;        // seit wann gesperrt (Uhr der Visu)
let verbT=null, verbWache=null;
function verbindungGesperrt(){ return !verb.server || !verb.ms; }
function verbUhr(ms, sekunden){
  return new Date(ms).toLocaleTimeString(LANG, sekunden ? {hour:'2-digit',minute:'2-digit',second:'2-digit'}
                                                        : {hour:'2-digit',minute:'2-digit'}); }
function verbindungZeigen(sofort){
  const box=el('verbindung'), sc=document.querySelector('.screen');
  clearTimeout(verbT); verbT=null;
  if(!verbindungGesperrt()){ verbWegAb=null; box.hidden=true; if(sc) sc.classList.remove('verbweg'); return; }
  if(verbWegAb==null) verbWegAb=Date.now();
  const rest = sofort ? 0 : verbWegAb + verb.hinweis*1000 - Date.now();
  if(rest>0){ verbT=setTimeout(()=>verbindungZeigen(false), rest); return; }
  const tx=verb.texte; if(!tx) return;   // noch nie eine Meldung bekommen: kein Text
  // Ohne Server ist auch der Stand des Miniservers nicht mehr bekannt: dessen
  // Meldung geht vor. Bestaetigt ist, was zuletzt bei erreichbarem Miniserver kam.
  const seit = verb.server ? verb.msSeit : verb.serverSeit;
  const stand = verb.ms ? verbBestaetigt : verb.msStand;
  box.querySelector('.vb-titel').textContent =
    (verb.server ? tx.ms : tx.server).replace('{seit}', seit ? verbUhr(seit) : '');
  box.querySelector('.vb-stand').textContent =
    (stand ? tx.stand.replace('{stand}', verbUhr(stand, true))+' · ' : '') + tx.gesperrt;
  box.hidden=false; if(sc) sc.classList.add('verbweg');
}
// Lebenszeichen: jede Nachricht des Servers zaehlt
function verbNachricht(){
  if(verb.ms) verbBestaetigt=Date.now();
  clearTimeout(verbWache);
  if(verb.stumm) verbWache=setTimeout(verbAbgerissen, verb.stumm*1000);
}
function verbServer(ok){
  if(ok){ verb.server=true; verbNachricht(); }
  else{ clearTimeout(verbWache); if(verb.server){ verb.server=false; verb.serverSeit=Date.now(); } }
  verbindungZeigen(false);
}
function verbMiniserver(m){
  verb.ms = m.ms!==false;
  verb.msSeit = m.seit||null; verb.msStand = m.stand||null;
  verb.takt = +m.takt||0; verb.stumm = +m.stumm||0; verb.hinweis = +m.hinweis||0;
  if(m.texte && typeof m.texte==='object') verb.texte = m.texte;
  verbNachricht();
  verbindungZeigen(false);
}
// Der Server schweigt laenger als verb.stumm: alten Socket aufgeben (sein
// close() kann bei einer toten Gegenstelle lange haengen) und neu verbinden
function verbAbgerissen(){
  const alt=ws; if(!alt) return;
  alt.onopen=alt.onclose=alt.onmessage=null;
  try{ alt.close(); }catch(err){ /* schon zu */ }
  verbServer(false); pinWarten=[]; connect();
}
function connect(){
  const q=[];
  if(PANEL_ID) q.push('panel='+encodeURIComponent(PANEL_ID));
  if(ENTWURF) q.push('entwurf='+encodeURIComponent(ENTWURF));
  if(DEVICE_ID) q.push('device='+encodeURIComponent(DEVICE_ID));
  else if(KOPPLUNG) q.push('code='+encodeURIComponent(KOPPLUNG));   // Kopplungscode behalten (s. zeigeKopplung)
  const kk=kioskKind(); if(kk) q.push('kiosk='+kk);   // Kiosk-App melden -> Typ in der Geraeteliste
  ws=new WebSocket((location.protocol==='https:'?'wss://':'ws://')+location.host+'/ws'
                   +(q.length?('?'+q.join('&')):''));
  // Erststart: Startseite kommt vom Server (erster Tab des Profils). Nach einem
  // Reconnect stattdessen die zuletzt betrachtete Seite wiederherstellen.
  ws.onopen=()=>{ verbServer(true); abosVergessen(); if(booted) send({t:'nav',route:stack[stack.length-1]}); };
  ws.onclose=()=>{ verbServer(false); pinWarten=[]; setTimeout(connect,1500); };
  ws.onmessage=e=>{
    verbNachricht();
    let msg;
    try{ msg=JSON.parse(e.data); }
    catch(err){ console.warn('LoxPanel: unlesbare Nachricht verworfen', err); return; }
    if(!msg || typeof msg!=='object') return;
    if(msg.t==='theme'){ if(serverStandPruefen(msg.stand)) return;
      const v=msg.vars||{};
      kachelMasse=v;
      // Was die vorige Nachricht setzte und diese nicht mehr nennt (anderes
      // Kachel-Set, keine Grundfarbe mehr), faellt weg - sonst bliebe etwa
      // --kachel-an oder --an-text des vorigen Sets bis zum Neuladen stehen.
      for(const k of _themeVars) if(!v[k]) document.documentElement.style.removeProperty(k);
      _themeVars = Object.keys(v).filter(k=>v[k]);
      for(const k in v){ if(v[k]) document.documentElement.style.setProperty(k,v[k]); }
      entwurfZeigen(msg.entwurf);
      posringOverride();      // ?ring= am Geraet schlaegt die Konfiguration
      profCols = (v['--cols']?(parseInt(v['--cols'])||2):2);
      profRows = (v['--rows']?(parseInt(v['--rows'])||2):2);
      gridCols = profCols; gridRows = profRows;
      panesCfg = (msg.panes && typeof msg.panes==='object') ? msg.panes : {};
      themeFill = !!msg.fill;
      themeSplit = (msg.split !== false);   // Default an; nur explizit aus (4"-Panel)
      themeCatFilter = !!msg.catFilter;     // Sprungmarken filtern statt springen
      tileLayout = (msg.tileLayout==='classic') ? 'classic' : '';
      // Kachel-Set (fertiger Look): die Farben kamen schon mit vars, die Regeln
      // fuer Symbole, Tasten und Tab-Leiste haengen am Attribut.
      if(typeof msg.tileSet==='string' && msg.tileSet) document.documentElement.setAttribute('data-kachelset', msg.tileSet);
      else document.documentElement.removeAttribute('data-kachelset');
      kachelAufbau = (typeof msg.tileSetAufbau==='string') ? msg.tileSetAufbau : '';
      kachelLeiste = (typeof msg.tileSetLeiste==='string') ? msg.tileSetLeiste : '';
      for(const [attr, wert] of [['data-kachelset-aufbau', kachelAufbau], ['data-kachelset-leiste', kachelLeiste]]){
        if(wert) document.documentElement.setAttribute(attr, wert); else document.documentElement.removeAttribute(attr); }
      schmalEinrichten();
      gridAuto = (typeof msg.gridAuto==='number' && msg.gridAuto>0) ? msg.gridAuto : 0;
      gridGrow = (typeof msg.gridGrow==='number' && msg.gridGrow>=1) ? msg.gridGrow : 1;
      paneCols = (typeof msg.paneCols==='number' && msg.paneCols>0) ? Math.round(msg.paneCols) : 0;
      paneShare = (typeof msg.paneShare==='number' && msg.paneShare>0 && msg.paneShare<1) ? msg.paneShare : 0;
      if(!themeCatFilter) katFilter=null;
      svPaneCfg = (typeof msg.svPane==='string') ? msg.svPane : '';   // rechte Spalte der Uhr-Seite
      if(saverOn()){ applySaverSplit(); renderFront(); }   // Spaltigkeit UND Inhalt der Uhr-Seite nachziehen
      applyPane();                          // Energie-/Kamera-Kachel und Status-Werte neu anmelden
      if(msg.lang){ LANG=msg.lang; tickClock(); }   // Panel-Sprache -> Datum/Uhr sofort aktualisieren
      if(msg.title) document.title=msg.title;
      if(msg.tabMeta) tabMeta=msg.tabMeta;
      if(msg.night){ NIGHT.dim=+msg.night.dim||0; NIGHT.wake=+msg.night.wake||0;
        NIGHT.uhr=(msg.night.uhr===true); NIGHT.uhrHell=+msg.night.uhrHell||0; setNight(msg.night.on); }
      if(Array.isArray(msg.tabs)&&msg.tabs.length) tabsCfg=msg.tabs;
      applyDisplayCfg(msg);   // Display aus / Auto-Neustart ohne Agent (Kiosk-App)
      pinMerkenS=(typeof msg.pinMerken==='number' && msg.pinMerken>0) ? msg.pinMerken : 0;
      gestenAn=(msg.gesten===true);   // Zwei-Finger-Gesten (Vorgaben/Ansicht)
      gestenHinweis=(msg.gestenHinweis===true);   // ... mit Hinweis-Symbol
      nachtUhrSetzen();               // ihre Symbole auf der Nacht-Uhr
      uiScaleCfg=scaleCfg(msg.scale);
      _screenSent='';         // neue Verbindung: der Server kennt die Groesse noch nicht
      applyScale();
      renderTabs(); return; }
    if(msg.t==='ring'){ if(msg.id){ wake(); nav({view:'control',id:msg.id}); } return; }   // Klingel: Display an, Uhr weg
    if(msg.t==='alarm'){ if(msg.on){ wake(); startAlarmTone(); if(msg.id) nav({view:'control',id:msg.id}); } else { stopAlarmTone(); } return; }
    if(msg.t==='testtone'){ playTestTone(); return; }
    if(msg.t==='front'){ frontData=msg; renderFront(); if(FRONT_TEST) renderFrontRich(el('frontPage')); applyPane();
      if(view && view.front && el('grid').classList.contains('fronttab')) renderFrontTab();
      if(view && view.layout==='haus' && el('grid').classList.contains('haus') && !updateHaus()) render();   // Kopf: Wetter, Termin
      return; }   // Kalender/Wetter fuer die Uhr-Seite
    if(msg.t==='player'){ playerData=Array.isArray(msg.blocks)?msg.blocks:[]; playerSecured=!!msg.secured;
      if(svSideOn()){ renderFront(); return; }   // Screensaver oben -> Audio als zweite Uhr-Spalte
      renderPlayer(playerData); return; }   // sonst fester Player in Pane 2
    if(msg.t==='energy'){ energyData=msg;
      if(svSideOn()){ renderFront(); return; }   // Screensaver oben -> dort zeichnen, nicht in die verdeckte Pane
      const fp=el('frontpane'); if(fp && paneKind(paneRawNow())==='energy') renderEnergyPane(fp); return; }   // Energiefluss-Pane
    if(msg.t==='camera'){ cameraData=msg;
      if(svSideOn()){ renderFront(); return; }
      const fp=el('frontpane'); if(fp && paneKind(paneRawNow())==='camera') renderCameraPane(fp); return; }   // Kamera-Pane (Intercom-Vollansicht)
    if(msg.t==='scale'){ uiScaleCfg=scaleCfg(msg.scale); applyScale(); return; }   // Skalierung des Geraets geaendert (ohne Neuladen)
    if(msg.t==='gridAuto'){   // Zielkachel des Geraets geaendert (Displays gespeichert): Raster neu
      const g=(typeof msg.gridAuto==='number' && msg.gridAuto>0) ? msg.gridAuto : 0;
      if(g!==gridAuto){ gridAuto=g; applyScale(); render(); }
      return; }
    if(msg.t==='svstatus'){ svStatusData=Array.isArray(msg.items)?msg.items:[];
      if(saverOn()){ renderFront(); return; }   // Uhr-Seite oben -> dort
      if(kopfAktiv()){ renderKopfzeile(); return; }   // Werte in der Kopfzeile
      const fp=el('frontpane');
      if(fp && !svSideOn()){ const pk=paneKind(paneRawNow());
        if(pk==='status') renderWertePane(fp);          // Werte als Pane 2
        else if(pk==='camera') renderCameraWerte(fp); }  // Werte unter dem Kamerabild
      return; }
    if(msg.t==='chart'){   // Verlaufs-Pane
      // Nur Daten des zuletzt angefragten Stapels: ein Push, der beim Wechsel
      // schon unterwegs war, nennt Bausteine, die die Pane nicht mehr zeigt.
      const want=curChartKey.split('|')[0].split(',').map(u=>u.trim());
      if(!(msg.controls||[]).every(u=>want.indexOf(u)>-1)) return;
      chartData=msg;
      if(svSideOn()){ renderFront(); return; }   // Screensaver oben -> als zweite Uhr-Spalte zeichnen
      const fp=el('frontpane'); if(fp && paneKind(paneRawNow())==='chart') renderChartPane(fp); return; }
    if(msg.t==='switch'){ if(msg.panel!==undefined){ const u=new URL(location.href);
        if(msg.panel) u.searchParams.set('panel',msg.panel); else u.searchParams.delete('panel');
        // Ein Entwurf (Vorschau am Geraet) gilt nur fuer sein Profil: jeder andere Wechsel
        // nimmt ihn aus der Adresse, sonst zeigte das neue Profil ein "abgelaufen"
        if(msg.entwurf) u.searchParams.set('entwurf',msg.entwurf); else u.searchParams.delete('entwurf');
        location.replace(u.toString()); } return; }   // Betriebsmodus -> Profil live wechseln
    if(msg.t==='reload'){ location.reload(); return; }                       // Server -> Panel neu laden
    if(msg.t==='entwurfEnde'){ const u=new URL(location.href); u.searchParams.delete('entwurf');
      location.replace(u.toString()); return; }                              // Entwurf gespeichert -> gespeichertes Profil
    if(msg.t==='einrichtung'){ zeigeEinrichtung(msg); return; }               // noch kein Miniserver
    if(msg.t==='verbindung'){ verbMiniserver(msg); return; }                 // Miniserver erreichbar? Lebenszeichen
    if(msg.t==='kopplung'){ zeigeKopplung(msg); return; }                     // Browser ohne Namen: Code, Karte
    if(msg.t==='night'){ setNight(msg.on); return; }                         // Tag/Nacht gewechselt
    if(msg.t==='goto'){ if(msg.route){ wake(); nav(msg.route); } return; }  // auf Seite springen
    if(msg.t==='notify'){ wake(); showNotify(msg.text, msg.level, msg.secs); return; }  // Nachricht einblenden
    if(msg.t==='display'){   // Server schaltet Display (Kiosk-App); presence = Praesenzmelder des Geraets
      if(typeof msg.presence==='boolean'){ DISP.presence=msg.presence; appLeerlauf(); }
      if(msg.on) wake(); else { clearTimeout(dpmsTimer); pinVergessen(); screenOff(); }
      return; }
    if(msg.t==='setdevice'){ if(msg.name){ try{ localStorage.setItem('lp_device', msg.name); }catch(e){}
        DEVICE_ID=msg.name; kopplungVergessen(); ws.close(); } return; }   // in den Einstellungen benannt -> mit Namen neu verbinden
    if(msg.t==='cmdresult'){ pinErgebnis(msg); return; }
    if(msg.t==='geste'){ gesteAntwort(msg); return; }   // Zwei-Finger-Geste: Startwert, Text oder Fehler
    if(msg.t!=='view') return;
    if(view && key(view.route)!==key(msg.route)){ pinVergessen(); gestenHilfeWeg(); }   // Seitenwechsel
    if(!booted){ booted=true; if(msg.route&&msg.route.view==='tab') stack=[msg.route]; }
    if(msg.layout==='scheme'){
      const sameS = view && key(view.route)===key(msg.route) && el('grid').classList.contains('scheme');
      view=msg; renderLeiste();
      if(!(sameS && updateScheme(msg))) renderScheme(msg);   // gleiche Seite: nur Werte patchen (Zoom bleibt)
      return;
    }
    if(msg.layout==='haus'){   // Hausuebersicht: gleiche Seite -> nur geaenderte Bloecke tauschen
      const sameH = view && key(view.route)===key(msg.route);
      view=msg; renderLeiste();
      if(!(sameH && updateHaus())) render();
      return;
    }
    if(msg.widget){ view=msg; render(); return; }   // Widget-Seite (Vollbild-Tab)
    const same = view && key(view.route)===key(msg.route);
    if(msg.blocks){
      view=msg; renderLeiste();
      if(same && el('grid').classList.contains('panel')) updatePanel(msg.blocks);
      else renderPanel(msg.blocks);
    } else {
      const st=same?g.scrollTop:0, sl=same?g.scrollLeft:0;
      view=msg;
      // Gleiche Kachel-Seite: nur die veraenderlichen Teile patchen (kein
      // innerHTML-Neuaufbau -> kein Flackern/Neuladen der Icons, z.B. Fully Kiosk).
      // Struktur geaendert (andere/mehr Kacheln) -> voller Neuaufbau, die
      // Seite (senkrecht wie waagerecht) bleibt stehen.
      if(!(same && updateGrid(katSichtbar(view.items||[])) && updateLeiste(view.leiste))){ render(); g.scrollTop=st; g.scrollLeft=sl; punkteNachziehen(); }
      else { const gh=g.querySelector('.ghinweis'); if(gh) gh.hidden=!view.gestenHilfe; }   // Hinweis-Symbol nachziehen
    }
  };
}
