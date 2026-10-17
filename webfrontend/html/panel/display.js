// LoxPanel-Visu, Teil 11 von 12: Nachtmodus, Nacht-Uhr, Kiosk-App, Skalierung, Bildschirm melden, Display-Einstellungen, Neuladen.
// Die Teile laden nacheinander aus panel.html (script src), alle Funktionen sind global;
// was beim Laden ausgefuehrt wird, darf nur Funktionen frueherer Teile rufen.

// ---- Nachtmodus: Panel abdunkeln ----
// Tag/Nacht meldet der Server ({t:"night"}), Staerke und Aufhelldauer kommen je
// Panel im theme. Gedimmt wird ueber eine schwarze Auflage statt per CSS-Filter:
// ein Filter auf dem Seitenrumpf zerschiesst die Positionierung von
// position:fixed-Elementen, und die Auflage wirkt wie heruntergeregelte
// Hintergrundbeleuchtung (Weiss wird grau, nicht nur dunkler).
// hell: nach einer Beruehrung aufgehellt; uhr/uhrHell: Nacht-Uhr und ihre Helligkeit in %
const NIGHT = { on:false, dim:0, wake:20, hell:false, uhr:false, uhrHell:0 };
let nightEl=null, nightWakeTimer=null;
function nightLayer(){
  if(!nightEl){
    nightEl=document.createElement('div'); nightEl.id='nightdim';
    nightEl.style.cssText='position:fixed;inset:0;background:#000;opacity:0;'+
      'pointer-events:none;z-index:100000;transition:opacity .8s ease';
    document.body.appendChild(nightEl);
  }
  return nightEl;
}
// LoxPanel-App: Dort senkt die App statt der Auflage die echte Helligkeit
// (LoxKiosk.setDisplayBrightness, Prozent der eingestellten Helligkeit). Die
// Auflage wirkt auf die Farbwerte, die Leuchtdichte faellt also mit der Potenz
// 2,2 (sRGB): 70 % abdunkeln liess etwa 7 % Leuchtdichte uebrig. Dieselbe
// Einstellung ergibt in der App dieselbe Leuchtdichte. Lehnt die App ab
// (automatische Helligkeit am Geraet) oder kennt sie die Funktion nicht (aeltere
// App), dunkelt wie bisher die Auflage ab.
function appHelligkeit(dim){
  const prozent = dim>0 ? Math.max(1, Math.round(100*Math.pow(1-dim/100, 2.2))) : 100;
  try{ return !!(window.LoxKiosk && typeof LoxKiosk.setDisplayBrightness==='function'
                 && LoxKiosk.setDisplayBrightness(prozent)); }catch(e){ return false; } }
function applyNight(awake){
  NIGHT.hell=!!awake;
  const dim = (NIGHT.on && NIGHT.dim>0 && !awake) ? Math.min(90,NIGHT.dim) : 0;
  nightLayer().style.opacity = appHelligkeit(dim) ? 0 : dim/100;
}
function setNight(on){ const vorher=NIGHT.on; NIGHT.on=!!on; clearTimeout(nightWakeTimer); applyNight(false);
  if(NIGHT.on && !vorher) pinVergessen();   // Nacht beginnt: gemerkte PIN weg
  nachtUhrSetzen(); }
// ---- Nacht-Uhr ----
// Nachts zeigt die Uhr-Seite auf Wunsch nur die Uhrzeit, gedimmt auf Schwarz
// (night.uhr, Helligkeit night.uhrHell in Prozent, vom Server je Panel), wie die
// Nachtanzeige der Loxone-Taster. Oben stehen, wenn Gesten an sind, die Symbole
// ihrer Spalten (links Beschattung, Mitte Licht, rechts Musik), genau ueber der
// Mitte jeder Spalte (GESTE_SPALTEN). Wetter, Termine und die zweite Spalte
// ruhen dann: keine Kamera laeuft die ganze Nacht. "Nachts abdunkeln" wirkt
// zusaetzlich wie auf jeder Seite.
function nachtUhrAn(){ return NIGHT.on && NIGHT.uhr; }
function nachtUhrSetzen(){
  const s=el('saver'), n=el('svNacht'); if(!s || !n) return;
  const an=nachtUhrAn(), vorher=s.classList.contains('nacht');
  s.classList.toggle('nacht', an); n.hidden=!an;
  s.style.setProperty('--nu-hell', String(Math.max(0, Math.min(100, NIGHT.uhrHell))/100));
  const z=el('nuZonen');
  if(z){ const grenzen=[0, ...GESTE_SPALTEN, 1];
    z.innerHTML=gestenAn ? GESTE_ARTEN.map((a, i)=>'<span style="left:'+((grenzen[i]+grenzen[i+1])/2*100)+'%">'+
      svg(ICONS[a.ico])+'</span>').join('') : ''; }
  tickClock();
  // Wechsel, waehrend die Uhr-Seite steht: zweite Spalte an- oder abmelden, neu zeichnen
  if(an!==vorher && saverOn()){ applySaverSplit(); applyPane(); renderFront(); }
}
// Nachts abgedunkelt und nicht gerade aufgehellt (Gesten im Dunkeln)
function nachtGedimmt(){ return NIGHT.on && NIGHT.dim>0 && !NIGHT.hell; }
function nightWake(){          // Beruehrung -> kurz voll aufhellen, dann zurueck
  if(!NIGHT.on || NIGHT.dim<=0 || NIGHT.wake<=0) return;
  clearTimeout(nightWakeTimer);
  applyNight(true);
  nightWakeTimer=setTimeout(()=>applyNight(false), NIGHT.wake*1000);
}
// ---- Display ohne Agent: Kiosk-App-Anbindung (Android) ----
// Auf einem Linux-Panel schaltet der Agent das Display (Server meldet agent:true,
// die Seite haelt sich dann raus). Ohne Agent uebernimmt die Seite: nach dpmsOff
// Sekunden Inaktivitaet Display aus ueber die JS-Schnittstelle der Kiosk-App,
// bei Klingel / Wecker / Notify / Goto wieder an. Erkannt werden Fully Kiosk
// Browser (window.fully; dort "Enable JavaScript Interface" einschalten) und die
// LoxPanel-App fuer Android (window.LoxKiosk); beide haben dieselbe Schnittstelle.
// Neu laden gegen Einfrieren erledigt die Seite ohne Agent selbst (s. neuladenFaellig).
// Hat das Geraet einen Praesenzmelder (Displays -> Display-Steuerung), meldet der
// Server, solange er jemanden sieht (presence): dann bleibt das Display an, der
// Leerlauf schaltet nicht ab. Wird der Raum leer, schaltet der Server es aus.
const DISP = { dpmsOff: 0, reloadHours: 0, reloadAt: null, agent: false, presence: false };
let dpmsTimer=null;
// Kiosk-Apps: Kennung (meldet die Seite dem Server -> Typ in der Geraeteliste)
// -> Name ihrer JS-Schnittstelle im window.
const KIOSK_APPS = { fully: 'fully', loxpanel: 'LoxKiosk' };
function kioskKind(){
  for(const k in KIOSK_APPS){ const f=window[KIOSK_APPS[k]];
    if(f && typeof f.turnScreenOff==='function' && typeof f.turnScreenOn==='function') return k; }
  return '';
}
function kiosk(){ const k=kioskKind(); return k ? window[KIOSK_APPS[k]] : null; }
function screenOff(){ const f=kiosk(); if(!f) return; try{ f.turnScreenOff(); }catch(e){} }
function screenOn(){ const f=kiosk(); if(!f) return;
  try{ if(typeof f.isScreenOn!=='function' || !f.isScreenOn()) f.turnScreenOn(); }catch(e){} }
// LoxPanel-App: Ihr eigener Bildschirmschoner kommt nach dpmsOff Sekunden.
// Solange der Praesenzmelder des Geraets jemanden sieht, setzt er aus (0) -
// sonst dunkelte die App trotz Anwesenheit ab.
function appLeerlauf(){
  try{ if(window.LoxKiosk && LoxKiosk.setDisplayOff) LoxKiosk.setDisplayOff(DISP.presence ? 0 : DISP.dpmsOff); }catch(e){} }
function armDpms(){ clearTimeout(dpmsTimer);
  if(window.LoxKiosk) return;   // native LoxPanel-Kiosk-App schaltet selbst ab (eigener Screensaver)
  // Mit Agent schaltet X (xset dpms) nach dpmsOff Sekunden ohne Eingabe ab, auch
  // bei Anwesenheit (dort wirkt der Praesenzmelder nicht), und die Seite erfaehrt
  // nichts davon: Sie vergisst die gemerkte PIN zur selben Zeit. Die LoxPanel-App
  // braucht das nicht, sie dunkelt erst dpmsOff nach der Uhr-Seite ab (setSaver),
  // und die vergisst die PIN schon.
  if(DISP.agent && DISP.dpmsOff>0){ dpmsTimer=setTimeout(pinVergessen, DISP.dpmsOff*1000); return; }
  if(DISP.agent || DISP.presence || !(DISP.dpmsOff>0)) return;
  // Mit Kiosk-JS (Fully) direkt abschalten; sonst dem Server Leerlauf melden,
  // der schaltet ueber den Display-Treiber des Geraets (Fully REST / WallPanel).
  dpmsTimer=setTimeout(()=>{ pinVergessen(); if(kiosk()) screenOff(); else send({t:'idle'}); }, DISP.dpmsOff*1000); }
// ---- Skalierung ("scale" aus Profil oder Geraet, vom Server) ----
// Die Visu rechnet mit festen 240er Kacheln; ein groesseres Display zeigte den
// Kasten bisher mit Rand (1280x800: 55 % des Schirms ungenutzt). "auto"
// vergroessert ihn gleichmaessig, bis er an Breite oder Hoehe anstoesst - ohne
// Verzerrung, Schrift und Icons wachsen mit. Eine Zahl ist ein fester Faktor,
// aber nie groesser, als der Schirm hergibt (sonst waere ein Teil
// abgeschnitten). "off" = feste Groesse wie bisher. Unter "Bildschirm fuellen"
// ist der Kasten schon so gross wie der Schirm, dort ergibt sich von selbst 1.
let uiScaleCfg='off', uiScaleEff=1;
function scaleCfg(v){ return (v==='auto' || (typeof v==='number' && v>0)) ? v : 'off'; }
function applyScale(){
  const s=document.querySelector('.screen'); if(!s) return;
  const w=s.offsetWidth, h=s.offsetHeight;          // Layout-Groesse, vom transform unberuehrt
  const vp=vpSize();
  const passt=(w&&h) ? Math.min(vp.w/w, vp.h/h) : 1;
  let k=1;
  if(gridAuto) k=1;                                  // automatisches Raster: Kacheln haben ihre Groesse, der Kasten ist der Schirm
  else if(uiScaleCfg==='auto') k=Math.max(1,passt); // nur vergroessern: kleiner rechnet das Layout selbst
  else if(typeof uiScaleCfg==='number') k=Math.min(uiScaleCfg,passt);
  k=Math.round(k*1000)/1000;
  if(k!==uiScaleEff || s.style.getPropertyValue('--ui-scale')===''){
    uiScaleEff=k;
    s.style.setProperty('--ui-scale', String(k));
    document.documentElement.classList.toggle('scaled', k!==1);
  }
  reportScreen();
}
// Groesse an den Server melden (Anzeige unter Settings -> Panels). Entprellt:
// beim Drehen oder Kiosk-Start feuert resize mehrfach hintereinander. Nur
// senden, was sich geaendert hat.
let _screenTimer=null, _screenSent='';
function reportScreen(){
  clearTimeout(_screenTimer);
  _screenTimer=setTimeout(()=>{
    const s=document.querySelector('.screen'), sc=window.screen||{};
    const m={t:'screen', vw:innerWidth, vh:innerHeight, sw:sc.width||0, sh:sc.height||0,
      dpr:window.devicePixelRatio||1, bw:s?s.offsetWidth:0, bh:s?s.offsetHeight:0, k:uiScaleEff,
      rc:gridCols, rr:gridRows};   // Raster der Kachelansicht (zeigt, was "Automatisch" ergibt)
    const sig=JSON.stringify(m);
    if(sig===_screenSent) return;
    try{ send(m); _screenSent=sig; }catch(e){}
  },400);
}
// Aendert sich die Layout-Groesse des Kastens (Split an/aus beim Tab-Wechsel,
// Layout, "Bildschirm fuellen") oder des Fensters, muss der Faktor neu. Der
// transform selbst aendert die Layout-Groesse nicht - kein Rueckkopplungskreis.
window.addEventListener('resize', applyScale);
// Der Screensaver liegt im Kasten: waechst dieser (etwa beim Start, sobald die
// erste Ansicht das Raster hochkant verdoppelt), muss auch er seine Aufteilung
// neu waehlen und neu einpassen (svFit kuerzt sonst Termine, die jetzt passen).
function onScreenResize(){
  applyScale();
  faktorNachziehen();   // Split an/aus, Kopfzeile: andere Kachelbreite
  if(saverOn()){ const vorher=el('saver').className; applySaverSplit();
    if(el('saver').className!==vorher){ applyPane(); }
    renderFront(); }
}
if(window.ResizeObserver){ const _s=document.querySelector('.screen'); if(_s) new ResizeObserver(onScreenResize).observe(_s); }
// Pane 2 passt ihren Inhalt an, sobald sich ihre Groesse aendert: Drehen, Split
// an/aus, automatisches Raster, Einblenden nach der Uhr-Seite.
function paneEinpassen(){ const fp=el('frontpane'); if(!fp || fp.hidden) return;
  wetterEinpassen(fp); kalenderEinpassen(fp); werteEinpassen(fp); }
if(window.ResizeObserver){ const _fp=el('frontpane'); if(_fp) new ResizeObserver(paneEinpassen).observe(_fp); }
function applyDisplayCfg(msg){
  DISP.dpmsOff = (typeof msg.dpmsOff==='number' && msg.dpmsOff>0) ? msg.dpmsOff : 0;
  DISP.presence = !!msg.presence;   // jemand im Raum -> Display bleibt an (auch nach Neuladen)
  // Native LoxPanel-Kiosk-App: konfigurierte Display-aus-Zeit an ihren Screensaver
  // geben, bei Anwesenheit 0.
  appLeerlauf();
  // Neu laden: null = nicht eingestellt (nachts um reloadAt Uhr), sonst Stunden, 0 = aus
  DISP.reloadHours = (typeof msg.reloadHours==='number') ? Math.max(0, msg.reloadHours) : null;
  DISP.reloadAt = (typeof msg.reloadAt==='number') ? msg.reloadAt : null;
  DISP.agent = !!msg.agent;
  armDpms();
}
// Neu laden gegen Einfrieren, nur ohne Agent (der startet den Browser selbst
// neu). reloadHours nicht eingestellt: einmal je Nacht, sobald es nach dem
// Laden der Seite reloadAt Uhr geworden ist; eine Zahl: so viele Stunden nach
// dem Laden; 0: nie. Bis die Einstellungen vom Server da sind, gilt 0. Geladen
// wird nur, waehrend die Uhr-Seite steht, nie unter den Fingern; ein Display
// im Schoner bleibt dabei dunkel (die Seite startet mit der Uhr, ohne zu wecken).
const SEITE_GELADEN = Date.now();
function neuladenFaellig(jetzt){
  if(DISP.agent) return false;
  if(DISP.reloadHours===null){
    if(DISP.reloadAt===null) return false;
    const nacht=new Date(SEITE_GELADEN); nacht.setHours(DISP.reloadAt,0,0,0);
    if(nacht.getTime()<=SEITE_GELADEN) nacht.setDate(nacht.getDate()+1);
    return jetzt>=nacht.getTime();
  }
  return DISP.reloadHours>0 && jetzt-SEITE_GELADEN >= DISP.reloadHours*3600*1000;
}
function neuladenPruefen(){ if(saverOn() && neuladenFaellig(Date.now())) location.reload(); }
