// LoxPanel-Visu, Teil 10 von 12: Uhr-Seite an und aus, Einrichtung und Kopplung, Hinweise, fester Spieler, Ruhe-Timer.
// Die Teile laden nacheinander aus panel.html (script src), alle Funktionen sind global;
// was beim Laden ausgefuehrt wird, darf nur Funktionen frueherer Teile rufen.

const FRONT_TEST=new URLSearchParams(location.search).has('front');
if(FRONT_TEST){ const fp=el('frontPage'); if(fp) fp.classList.remove('hidden'); }
function saverOn(){ return !el('saver').classList.contains('hidden'); }
// Screensaver zweispaltig im Querformat (breites 2-Pane-Tablet, z.B. Shelly
// X2) – gleiches Kriterium wie das Kachel-Grid (s. render()). Hochkant liegt
// die zweite Flaeche UNTER Uhr und Wetter (Klasse "hoch"), sobald der Kasten
// deutlich hoeher als breit ist (mind. Wurzel 2, wie bei der Verdopplung nach
// unten) - gemessen am Kasten, denn in ihm liegt der Screensaver. Das
// quadratische 4"-Panel bleibt einspaltig (Wetter oben, Uhr, Termine
// untereinander).
// WICHTIG: Die Entscheidung haengt an der aktuellen Fenster- und Kastengroesse,
// die beim Kiosk-Start / nach dem Auto-Reload (Speichern) kurz falsch sein
// kann, bevor die echte Flaeche steht. Darum gekapselt und bei jedem resize und
// jeder Groessenaenderung des Kastens neu getroffen – sonst bleibt die Anzeige
// in der beim Start zufaellig gemessenen Spaltigkeit haengen (2-spaltig direkt
// nach dem Speichern, erst spaeter wieder einspaltig).
function applySaverSplit(){
  const s=el('saver'), sc=document.querySelector('.screen');
  const vp=vpSize(), quer=vp.w > vp.h;
  const hoch=!!themeSplit && !quer && !!sc && sc.offsetHeight >= sc.offsetWidth*Math.SQRT2;
  s.classList.toggle('split', (!!themeSplit && quer) || hoch);
  s.classList.toggle('hoch', hoch);
}
function showSaver(){
  pinVergessen();   // Uhr-Seite: gemerkte PIN weg
  gestenHilfeWeg(); // ... und die Hilfe der Gesten
  // Native Kiosk-App (LoxPanel): nur EIN sichtbarer Screensaver — diese Uhr.
  // Der App sagen, dass ihr Saver läuft; sie dunkelt nur noch das Backlight
  // (nach dpmsOff) und weckt per Annäherung/Berührung auf den 1. Tab.
  try{ if(window.LoxKiosk && LoxKiosk.setSaver) LoxKiosk.setSaver(true); }catch(e){}
  tickClock();
  applySaverSplit();
  el('saver').classList.remove('hidden');
  // Reihenfolge zaehlt: erst sichtbar schalten (svSideOn() gilt), dann die
  // Energie-/Kamera-Kachel auf die Wahl des Screensavers umstellen, dann
  // zeichnen — jetzt hat er auch eine Hoehe, an der sich svFit ausrichtet.
  applyPane();
  renderFront(); }
function hideSaver(){ try{ if(window.LoxKiosk && LoxKiosk.setSaver) LoxKiosk.setSaver(false); }catch(e){}
  el('saver').classList.add('hidden');
  // Zweite Spalte abraeumen: ein Kamerabild dort haelt sonst seine Verbindung
  // zur Tuerstation offen, obwohl die Uhr-Seite gar nicht mehr zu sehen ist.
  const b=el('svBox');
  if(b){ b.innerHTML=''; b.hidden=true; delete b.dataset.cam; delete b.dataset.camsig; }
  applyPane(); }
// Einrichtungshinweis vom Server (t:'einrichtung'): solange er keine Struktur
// vom Miniserver hat, steht hier, wo der Konfigurator zu oeffnen ist. Die
// Adresse ist die, ueber die das Panel die Visu geladen hat - ausser bei
// 127.0.0.1 (die App auf dem Panel selbst), dann die des Servers im Netz.
function einrichtungsUrls(loc, msg){
  const pfad=msg.pfad||'/config';
  const h=(loc.hostname||'').replace(/^\[|\]$/g,'');
  if(!(h==='localhost' || h==='::1' || /^127\./.test(h))) return [loc.protocol+'//'+loc.host+pfad];
  const port=loc.port ? ':'+loc.port : '';
  return (msg.adressen||[]).map(a=>loc.protocol+'//'+a+port+pfad);
}
// Kopplungscode vom Server (t:'kopplung'): ein Browser ohne Geraetekennung
// bekommt beim Verbinden einen Code, merkt ihn sich (localStorage) und schickt
// ihn beim naechsten Verbinden zurueck, damit er gleich bleibt. Ohne ?panel=
// zeigt die Karte "Dieses Geraet einrichten" den Code und die Adresse des
// Konfigurators; unter Displays steht derselbe Code, "Namen vergeben" dort
// schickt setdevice an genau dieses Geraet. Ein Tipp blendet die Karte bis
// zum naechsten Laden aus.
let KOPPLUNG='';
try{ KOPPLUNG=localStorage.getItem('lp_kopplung')||''; }catch(e){}
let _kopplungWeg=false;
function zeigeKopplung(msg){
  const k=el('kopplung'); if(!k) return;
  if(msg.code){ KOPPLUNG=msg.code; try{ localStorage.setItem('lp_kopplung', msg.code); }catch(e){} }
  k.textContent='';
  if(!msg.karte || _kopplungWeg || DEVICE_ID){ k.classList.add('hidden'); return; }
  const zeile=(cls, text)=>{ const d=document.createElement('div'); d.className=cls; d.textContent=text||''; k.appendChild(d); };
  zeile('ei-titel', msg.titel); zeile('ei-code', msg.code); zeile('ei-hinweis', msg.hinweis);
  const urls=einrichtungsUrls(location, msg);
  if(urls.length) urls.forEach(u=>zeile('ei-url', u)); else zeile('ei-grund', msg.unbekannt);
  zeile('ei-weg', msg.weg);
  k.onclick=()=>{ _kopplungWeg=true; k.classList.add('hidden'); };
  k.classList.remove('hidden');
}
function kopplungVergessen(){
  KOPPLUNG=''; try{ localStorage.removeItem('lp_kopplung'); }catch(e){}
  const k=el('kopplung'); if(k) k.classList.add('hidden');
}
function zeigeEinrichtung(msg){
  const k=el('einrichtung'); if(!k) return;
  k.textContent='';
  if(!msg.aktiv){ k.classList.add('hidden'); return; }
  const zeile=(cls, text)=>{ const d=document.createElement('div'); d.className=cls; d.textContent=text||''; k.appendChild(d); };
  zeile('ei-titel', msg.titel); zeile('ei-grund', msg.grund); zeile('ei-hinweis', msg.hinweis);
  const urls=einrichtungsUrls(location, msg);
  if(urls.length) urls.forEach(u=>zeile('ei-url', u)); else zeile('ei-grund', msg.unbekannt);
  k.classList.remove('hidden');
}
// Kurze Nachricht/Banner vom Server (t:'notify') oben im Panel einblenden.
function showNotify(text, level, secs){
  if(!text) return;
  const s=document.querySelector('.screen'); if(!s) return;
  let n=s.querySelector('.lpnotify');
  if(!n){ n=document.createElement('div'); n.className='lpnotify';
    n.style.cssText='position:absolute;left:10px;right:10px;top:10px;z-index:50;padding:12px 14px;'+
      'border-radius:12px;font-size:15px;font-weight:600;line-height:1.25;text-align:center;'+
      'box-shadow:0 8px 24px rgba(0,0,0,.45);pointer-events:none;word-break:break-word;';
    s.appendChild(n); }
  const col = level==='crit' ? '226,107,95' : (level==='warn' ? '224,162,77' : '82,184,129');
  n.style.background='rgba('+col+',.96)'; n.style.color='#10140f';
  n.textContent=text; hideSaver();
  clearTimeout(n._t);
  n._t=setTimeout(()=>{ if(n&&n.parentNode) n.parentNode.removeChild(n); }, Math.max(1,(secs||5))*1000);
}
// Fester Player im Split-Layout (linke Spalte). Baut das Grundgeruest einmal
// auf und aktualisiert danach nur Cover/Titel/Transport/Lautstaerke in-place
// (kein Neu-Rendern bei jedem 0.3s-Update -> kein Cover-Flackern).
function renderPlayer(blocks){
  const pane=el('playerpane'); if(!pane||!Array.isArray(blocks)) return;
  const cover=blocks.find(b=>b.k==='cover');
  const title=blocks.find(b=>b.k==='title');
  const row=blocks.find(b=>b.k==='row');
  const sl=blocks.find(b=>b.k==='slider');
  if(!_playerBuilt){
    pane.innerHTML=
      '<div class="fp-page solo pppage">'+
      '<div class="ppcover"><div class="coverph">'+svg(ICONS.music)+'</div><img id="ppimg" alt=""></div>'+
      '<div class="pptitle" id="pptitle"></div>'+
      '<div class="ppsub" id="ppsub"></div>'+
      '<div class="pptrans" id="pptrans"></div>'+
      '<div class="ppvol"><span class="sico">'+svg(ICONS.vol)+'</span>'+
        '<button type="button" class="sbtn" data-sd="dn">−</button>'+
        '<input type="range" class="sld" id="ppsld" min="0" max="100" value="0">'+
        '<button type="button" class="sbtn" data-sd="up">+</button><span class="sval" id="ppsldv">0</span></div>'+
      '</div>';
    const s=el('ppsld'), zurueck=()=>renderPlayer(playerData);   // PIN abgebrochen: Stand des Servers
    pane.querySelector('.ppvol .sbtn[data-sd="dn"]').addEventListener('pointerdown',ev=>{ ev.preventDefault(); nudgeSld(s,-SLD_STEP,el('ppsldv'),playerSecured,zurueck); });
    pane.querySelector('.ppvol .sbtn[data-sd="up"]').addEventListener('pointerdown',ev=>{ ev.preventDefault(); nudgeSld(s,SLD_STEP,el('ppsldv'),playerSecured,zurueck); });
    s.addEventListener('input',()=>{ _playerVolDrag=true; sldFill(s); el('ppsldv').textContent=s.value; });
    s.addEventListener('change',()=>{ _playerVolDrag=false;
      if(s._uuid&&s._tmpl) sendCmd(s._uuid,s._tmpl.replace('{v}',s.value),playerSecured,{abbruch:zurueck}); });
    _playerBuilt=true;
  }
  // Cover nur bei Aenderung neu laden (sonst Flackern)
  const img=el('ppimg');
  if(img){ if(cover&&cover.src){ if(img.getAttribute('src')!==cover.src){
        img.onload=()=>img.style.opacity='1'; img.onerror=()=>img.style.opacity='0'; img.src=cover.src; } }
    else { img.removeAttribute('src'); img.style.opacity='0'; } }
  el('pptitle').textContent=title?(title.text||''):'';
  el('ppsub').textContent=title?(title.sub||''):'';
  // Transport-Buttons: einmal bauen, dann Icon+cmd in-place aktualisieren
  const tr=el('pptrans'), cells=(row&&row.cells)||[];
  if(tr){
    if(tr.children.length!==cells.length){
      tr.innerHTML=cells.map((c,i)=>'<div class="btn'+(c.icon?' icon':'')+(c.big?' big':'')+'" data-c="'+i+'"></div>').join('');
      tr.querySelectorAll('[data-c]').forEach(n=>n.addEventListener('pointerdown',ev=>{ ev.preventDefault();
        if(n._cmd) sendCmd(n._cmd.uuid,n._cmd.cmd,playerSecured); }));
    }
    cells.forEach((c,i)=>{ const n=tr.querySelector('[data-c="'+i+'"]'); if(!n)return;
      n._cmd=c.cmd||null;
      n.innerHTML=c.icon?svgF(ICONS[c.icon]||ICONS.info):esc(c.label||'');
      n.className='btn'+(c.icon?' icon':'')+(c.big?' big':''); });
  }
  if(sl){ const s=el('ppsld'); if(s&&sl.cmd){ s._uuid=sl.cmd.uuid; s._tmpl=sl.cmd.tmpl; }
    if(s&&!_playerVolDrag){ s.value=sl.value; sldFill(s); el('ppsldv').textContent=sl.value; } }
}
// Nach Ruhe zurueck zur Startseite und zur Uhr. Ein gesetzter Filter der
// Sprungmarken faellt dabei weg, sonst zeigte das Wandpanel dauerhaft nur
// eine Gruppe.
function nachRuhe(){ katFilter=null; goTab(tabsCfg[0]||'favoriten'); showSaver(); }
function resetIdle(){ clearTimeout(idleTimer);
  idleTimer=setTimeout(nachRuhe, SAVER_IDLE_MS);
  armDpms(); }
// Der Finger, der die Uhr-Seite wegtippt, darf darunter nichts ausloesen. Sie
// verschwindet schon beim Aufsetzen; Loslassen, click und Langdruck derselben
// Beruehrung landen sonst auf der Kachel, die jetzt unter dem Finger liegt
// (Safari laesst den click durch, sobald der Finger kurz liegen bleibt). Die
// Beruehrung endet nicht an einer festen Zeit, darum gilt die Sperre bis zur
// naechsten: deren pointerdown (Capture, vor allen anderen) hebt sie auf.
let saverGeste=false;
window.addEventListener('pointerdown', ()=>{ saverGeste=false; }, true);
window.addEventListener('keydown', ()=>{ saverGeste=false; }, true);
['pointerup','click','dblclick','contextmenu'].forEach(ev=>window.addEventListener(ev, e=>{
  if(!saverGeste) return; e.preventDefault(); e.stopImmediatePropagation(); }, true));
el('saver').addEventListener('pointerdown', e=>{ e.preventDefault(); e.stopPropagation();
  const wecken=()=>{ saverGeste=true; nightWake(); hideSaver(); resetIdle(); };
  if(gestenImDunkeln(e)) weckenAufschieben(wecken); else wecken(); });   // zwei Finger: Geste im Dunkeln
// input: Android-Tastaturen melden nicht jedes Zeichen als keydown (Name einer Weckzeit)
// Nachts abgedunkelt: das Aufhellen wartet wie das Wecken, ob ein zweiter Finger kommt
['pointerdown','keydown','input','wheel'].forEach(ev=>document.addEventListener(ev, e=>{
  if(ev==='pointerdown' && gestenImDunkeln(e)) weckenAufschieben(nightWake); else nightWake();
  if(!saverOn()) resetIdle(); }, {passive:true}));
