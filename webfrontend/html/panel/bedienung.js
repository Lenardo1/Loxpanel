// LoxPanel-Visu, Teil 2 von 12: Befehle und Visu-PIN, Zellen und Tasten, Formular, Wert mit -/+, Bild gross, Menue, blockSig.
// Die Teile laden nacheinander aus panel.html (script src), alle Funktionen sind global;
// was beim Laden ausgefuehrt wird, darf nur Funktionen frueherer Teile rufen.

// ---- Befehle und Visu-PIN (gesicherte Bausteine, isSecured) ----
// Jeder Befehl geht ueber sendCmd(); nur cmdSchicken() baut {t:'cmd'}. Bei
// einem gesicherten Baustein fragt die Visu die PIN ab und schickt sie mit,
// der Server rechnet daraus den Hash fuer sps/ios. Bestaetigt der Miniserver
// sie (cmdresult ok), gilt sie pinMerkenS Sekunden weiter (Panel-Einstellung
// "PIN merken", 0 = jedes Mal fragen) - nur im Speicher und nur auf der Seite,
// auf der sie eingegeben wurde. Uhr-Seite, Display aus und Seitenwechsel
// vergessen sie sofort (pinVergessen).
let pinMerkenS=0;        // kommt mit dem theme; bis dahin jedes Mal fragen
let pinMerk=null, pinMerkT=null;   // bestaetigte PIN {pin, seite, bis}
let pinWarten=[];        // gesicherte Befehle, deren cmdresult aussteht
let pinJobs=null;        // Befehle, die auf die offene PIN-Abfrage warten
function cmdSchicken(uuid,cmd,pin){ const m={t:'cmd',uuid,cmd}; if(pin!=null) m.pin=pin; send(m); }
// Seite = oberster Eintrag von stack, nicht view.route: nav() legt ihn sofort
// ab, die neue Ansicht schickt der Server aber erst nach dem cmdresult eines
// laufenden Befehls (er arbeitet die Nachrichten eines Panels der Reihe nach ab)
function pinSeite(){ return key(stack[stack.length-1]); }
function pinGemerkt(){
  if(pinMerk && (Date.now()>=pinMerk.bis || pinMerk.seite!==pinSeite())) pinMerk=null;
  return pinMerk ? pinMerk.pin : null; }
function pinVergessen(){ pinMerk=null; clearTimeout(pinMerkT);
  // eine offene Abfrage gehoert zur alten Seite: zu, ihre Befehle gelten als abgebrochen
  const s=document.querySelector('.screen'), ov=s&&s.querySelector('.pinov'); if(ov) ov.remove();
  const jobs=pinJobs; pinJobs=null; if(jobs) jobs.forEach(j=>{ if(j.abbruch) j.abbruch(); }); }
function askPin(cb,msg){
  const s=document.querySelector('.screen'); let ov=s.querySelector('.pinov'); if(ov)ov.remove();
  ov=document.createElement('div'); ov.className='pinov';
  let val='';
  const keys=['1','2','3','4','5','6','7','8','9','del','0','ok'];
  ov.innerHTML='<div class="pinbox"><div class="pinttl">PIN / Passwort</div>'+
    '<div class="pindisp" id="pindisp"></div>'+
    '<div class="pinmsg">'+(msg||'')+'</div>'+
    '<div class="pinpad">'+keys.map(k=>{
      const cls='pinkey'+(k==='ok'?' ok':'')+(k==='del'?' del':'');
      const lbl=k==='del'?'⌫':(k==='ok'?'OK':k);
      return '<div class="'+cls+'" data-k="'+k+'">'+lbl+'</div>';
    }).join('')+'</div>'+
    '<div class="pinbtn cancel">Abbrechen</div></div>';
  s.appendChild(ov);
  const disp=ov.querySelector('#pindisp');
  const draw=()=>{ disp.textContent='•'.repeat(val.length); };
  const done=v=>{ ov.remove(); cb(v); };
  ov.querySelectorAll('.pinkey').forEach(b=>{ b.onclick=()=>{
    const k=b.dataset.k;
    if(k==='ok') done(val);
    else if(k==='del'){ val=val.slice(0,-1); draw(); }
    else if(val.length<12){ val+=k; draw(); }
  };});
  ov.querySelector('.cancel').onclick=()=>done(null);
}
// Ist die Abfrage schon offen, gilt die eine PIN fuer alle wartenden Befehle.
function pinAbfragen(job,msg){
  if(pinJobs){ pinJobs.push(job); const m=document.querySelector('.screen .pinov .pinmsg'); if(m&&msg) m.textContent=msg; return; }
  pinJobs=[job];
  askPin(pin=>{ const jobs=pinJobs||[]; pinJobs=null;
    if(pin==null){ jobs.forEach(j=>{ if(j.abbruch) j.abbruch(); }); return; }
    jobs.forEach(j=>pinSenden(j,pin,true,false)); }, msg);
}
// Mit PIN schicken. neu: eben eingegeben (gemerkt, sobald bestaetigt). Eine
// Halten-Taste (job.los): mit gemerkter PIN echtes Halten, das Loslassen
// schickt endHold mit derselben PIN; nach der Abfrage ist der Finger laengst
// oben, dann folgt es sofort (wirkt wie ein Tipp). Nie Druecken ohne Loslassen.
// seite: die des Tipps (job.seite), nicht die der Eingabe - job.ok und das
// Merken gelten nur dort, auch fuer die Wiederholung nach abgelehnter PIN.
function pinSenden(job,pin,neu,halten){
  const w={job,pin,neu,seite:job.seite};
  pinWarten.push(w); cmdSchicken(job.uuid,job.cmd,pin);
  if(!job.los) return;
  const los={job:job.los,pin,seite:w.seite,zu:w};
  if(halten) holdRelease=los; else { pinWarten.push(los); cmdSchicken(los.job.uuid,los.job.cmd,pin); }
}
function pinErgebnis(msg){
  const i=pinWarten.findIndex(w=>w.job.uuid===msg.uuid && w.job.cmd===msg.cmd); if(i<0) return;
  const w=pinWarten.splice(i,1)[0];
  if(msg.ok){
    if(w.neu && pinMerkenS>0 && w.seite===pinSeite()){
      pinMerk={pin:w.pin, seite:w.seite, bis:Date.now()+pinMerkenS*1000};
      clearTimeout(pinMerkT); pinMerkT=setTimeout(()=>{ pinMerk=null; }, pinMerkenS*1000); }
    if(w.job.ok && w.seite===pinSeite()) w.job.ok();
    return; }
  w.fehl=true; pinMerk=null;      // abgelehnt: auch eine gemerkte PIN gilt nicht mehr
  if(w.zu && w.zu.fehl) return;   // Loslassen zu abgelehntem Druecken: die neue Abfrage schickt beide
  // Seite inzwischen gewechselt: keine Abfrage fuer einen fremden Befehl, abgebrochen
  if(w.seite!==pinSeite()){ if(w.job.abbruch) w.job.abbruch(); return; }
  pinAbfragen(w.job, msg.code==null ? 'Miniserver antwortet nicht – nochmal' : 'PIN falsch – nochmal');
}
// opt.los: Loslassen einer Halten-Taste; opt.ok: danach (etwa zurueck), bei
// PIN erst nach der Bestaetigung und nur noch auf derselben Seite;
// opt.abbruch: PIN abgebrochen oder Verbindung gesperrt (Anzeige zurueck).
function sendCmd(uuid,cmd,secured,opt){ opt=opt||{};
  // Ohne bestaetigte Verbindung nichts schicken: Anzeige zurueck, Leiste sofort
  if(verbindungGesperrt()){ if(opt.abbruch) opt.abbruch(); verbindungZeigen(true); return; }
  const job={uuid,cmd,los:opt.los||null,ok:opt.ok||null,abbruch:opt.abbruch||null,seite:pinSeite()};
  if(!secured){ cmdSchicken(uuid,cmd,null); if(job.los) holdRelease={job:job.los,pin:null}; if(job.ok) job.ok(); return; }
  const pin=pinGemerkt();
  if(pin==null) pinAbfragen(job,''); else pinSenden(job,pin,false,true);
}
const SLD_STEP=5;   // Schrittweite der -/+ Tasten am Schieberegler (Lautstaerke etc.)
// Fuellstand der Leiste als CSS-Var --p (Prozent) setzen -> gefuellte Anzeige
// unabhaengig vom nativen accent-color-Rendering des jeweiligen WebViews.
function sldFill(sld){ if(!sld)return;
  const min=+sld.min||0, max=(sld.max!==''?+sld.max:100);
  const p=max>min?((+sld.value-min)/(max-min))*100:0;
  sld.style.setProperty('--p', Math.max(0,Math.min(100,p))+'%'); }
// Nachkommastellen einer Zahl (0.5 -> 1, 5 -> 0)
function stellen(x){ const s=String(Math.abs(+x)), i=s.indexOf('.'); return i<0?0:s.length-i-1; }
// Auf die Stellen der Schrittweite runden: 0,5er-Schritte bleiben 0,5er-Schritte
// (frueher Math.round: 20 + 0,5 ergab 21), Rechenreste wie 20.000000000000004
// fallen weg.
function nudgeSld(sld,delta,valEl,secured,abbruch){ if(!sld)return;
  const min=+sld.min||0, max=(sld.max!==''?+sld.max:100);
  let v=+((+sld.value||0)+delta).toFixed(stellen(delta)); v=Math.max(min,Math.min(max,v));
  if(v===(+sld.value)) return;
  sld.value=v; sldFill(sld); if(valEl) valEl.textContent=v;
  if(sld._uuid&&sld._tmpl) sendCmd(sld._uuid,sld._tmpl.replace('{v}',v),secured,{abbruch}); }

let holdRelease=null;
let videoTimer=null;
function stopVideo(){ if(videoTimer){ clearInterval(videoTimer); videoTimer=null; } }
function setMore(route){ const s=document.querySelector('.screen'); if(!s)return; let mb=s.querySelector('.moreb');
  if(route){ if(!mb){ mb=document.createElement('div'); mb.className='moreb'; mb.textContent='⋮'; s.appendChild(mb);} mb.onclick=()=>nav(route); }
  else if(mb){ mb.remove(); } }
function endHold(){ const h=holdRelease; if(!h) return; holdRelease=null;
  if(h.pin!=null) pinWarten.push(h);
  cmdSchicken(h.job.uuid,h.job.cmd,h.pin); }
window.addEventListener('pointerup', endHold);
window.addEventListener('pointercancel', endHold);

// nav, form, confirm und back wirken erst beim Tippen (click), nicht schon beim
// Aufsetzen des Fingers: sonst oeffnete ein Wischer ueber die Zonenliste eine
// Zone, und "Löschen" braucht zwei echte Tipps.
function bindCell(btn,c){ btn._cmd=c.cmd||null; btn._release=c.release||null; btn._hold=!!c.hold; btn._menu=c.menu||null;
  btn._nav=c.nav||null; btn._form=c.form||null; btn._confirm=c.confirm||null; btn._back=!!c.back;
  btn._tippen=!!(c.nav||c.form||c.confirm||c.back); }
function cellCls(c){ return 'btn'+(c.icon?' icon':'')+(c.big?' big':'')+(c.menu?' toggler':'')+(c.on?' on':'')+(c.nav?' nav':''); }
function cellHtml(c,i){
  const inner=c.icon?svgF(ICONS[c.icon]||ICONS.info):esc(c.label);
  return '<div class="'+cellCls(c)+'" data-c="'+i+'">'+inner+'</div>';
}
// Tipp auf eine Zelle mit nav/form/confirm/back. confirm: der erste Tipp fragt
// nach (Beschriftung wird zur Rueckfrage), erst ein zweiter innerhalb von
// ZELLE_BESTAETIGEN_MS fuehrt aus.
const ZELLE_BESTAETIGEN_MS = 4000;
function zelleTippen(g,btn){
  if(btn._nav){ nav(btn._nav); return; }
  if(btn._confirm && !btn._armed){
    btn._armed=true; btn._label=btn.textContent; btn.textContent=btn._confirm; btn.classList.add('arm');
    btn._armT=setTimeout(()=>{ btn._armed=false; btn.textContent=btn._label; btn.classList.remove('arm'); },ZELLE_BESTAETIGEN_MS);
    return; }
  clearTimeout(btn._armT);
  const danach=btn._back?{ok:back}:null;   // mit PIN erst zurueck, wenn der Miniserver bestaetigt
  if(btn._form){ const cmd=formBefehl(g,btn._form); if(cmd===null) return; sendCmd(btn._form.uuid,cmd,view&&view.secured,danach); }
  else if(btn._cmd) sendCmd(btn._cmd.uuid,btn._cmd.cmd,view&&view.secured,danach);
  else if(btn._back) back();
}
// ---- Formular (Weckzeit bearbeiten) ----
// Felder tragen data-f (Name in der Befehlsvorlage). "Speichern" (form) setzt
// ihre Werte ein: Text URL-kodiert, Uhrzeit in Sekunden ab Mitternacht,
// Auswahl als Liste mit Komma. Ein leeres Feld oder keine Auswahl sperrt den
// Knopf. Die Werte gehoeren der Visu, bis gespeichert ist: Ein Update vom
// Server aendert sie nicht (blockSig ohne Werte).
function formWerte(g){ const w={};
  g.querySelectorAll('[data-f]').forEach(e=>{ const n=e.dataset.f;
    if(e.tagName==='INPUT') w[n]=encodeURIComponent(e.value.trim());
    else if(e.classList.contains('tpk')) w[n]=String(+e.dataset.v||0);
    else if(e.classList.contains('chipset')) w[n]=[...e.querySelectorAll('.chp.on')].map(c=>c.dataset.v).join(',');
  });
  return w; }
function formBefehl(g,form){ const w=formWerte(g); let cmd=form.tmpl;
  for(const n in w){ if(w[n]==='') return null; cmd=cmd.split('{'+n+'}').join(w[n]); }
  return cmd; }
function formPruefen(g){ g.querySelectorAll('.btn').forEach(b=>{ if(b._form) b.classList.toggle('dis',formBefehl(g,b._form)===null); }); }
// Taste mit Wiederholung: ein Schritt sofort, nach TASTE_HALTEN_MS gedrueckt
// alle TASTE_TAKT_MS einer.
const TASTE_HALTEN_MS = 450, TASTE_TAKT_MS = 110;
function wiederholen(btn,fn){
  let t1=null, t2=null;
  const stop=()=>{ clearTimeout(t1); clearInterval(t2); t1=t2=null; };
  btn.addEventListener('pointerdown',ev=>{ ev.preventDefault(); stop(); fn();
    t1=setTimeout(()=>{ t2=setInterval(()=>{ if(btn.isConnected) fn(); else stop(); },TASTE_TAKT_MS); },TASTE_HALTEN_MS); });
  ['pointerup','pointerleave','pointercancel'].forEach(n=>btn.addEventListener(n,stop));
}
function zeitSchritt(t,u,d){
  const s=+t.dataset.v||0; let h=Math.floor(s/3600), m=Math.floor(s%3600/60);
  if(u==='h') h=(h+d+24)%24; else m=(m+d+60)%60;
  t.dataset.v=h*3600+m*60;
  const p=n=>String(n).padStart(2,'0'), v=t.querySelectorAll('.tpv'); v[0].textContent=p(h); v[1].textContent=p(m); }
function formBind(g){
  g.querySelectorAll('.fld input').forEach(i=>i.addEventListener('input',()=>formPruefen(g)));
  g.querySelectorAll('.tpk').forEach(t=>t.querySelectorAll('.tpc').forEach(c=>
    c.querySelectorAll('.sbtn').forEach(b=>wiederholen(b,()=>zeitSchritt(t,c.dataset.u,+b.dataset.d)))));
  g.querySelectorAll('.chipset').forEach(cs=>{ const multi=!!cs.dataset.multi;
    cs.querySelectorAll('.chp').forEach(c=>c.addEventListener('click',()=>{
      if(multi) c.classList.toggle('on'); else cs.querySelectorAll('.chp').forEach(x=>x.classList.toggle('on',x===c));
      formPruefen(g); })); });
  formPruefen(g);
}
// ---- Wert mit -/+ (Laufzeit einer Zone, Dauern des Weckers) ----
// Die Visu zaehlt selbst weiter und schickt den Wert erst, wenn STP_SENDEN_MS
// lang niemand tippt: Beim Durchtippen kommt so ein Befehl an statt zehn, und
// kein Tipp geht verloren, weil die Antwort des Miniservers noch aussteht.
// Bis STP_HALTEN_MS nach dem letzten Tipp zeigt sie ihren eigenen Wert.
const STP_SENDEN_MS = 900, STP_HALTEN_MS = 3000;
function dauerText(s){ s=Math.max(0,Math.round(+s||0)); const h=Math.floor(s/3600), m=Math.floor(s%3600/60), r=s%60;
  if(!s) return '0 min'; if(h) return h+' h'+(m?' '+m+' min':''); if(m) return m+' min'+(r?' '+r+' s':''); return r+' s'; }
function stpText(b,v){ return b.fmt==='dauer' ? dauerText(v) : b.fmt==='prozent' ? v+' %' : String(v); }
function stepperBind(e,b){ e._b=b; e._v=+b.value||0;
  e.querySelectorAll('.sbtn[data-st]').forEach(btn=>wiederholen(btn,()=>{
    const bb=e._b, d=+btn.dataset.st, st=+bb.step||1;
    const mn=bb.min!=null?+bb.min:-Infinity, mx=bb.max!=null?+bb.max:Infinity;
    // Liegt der Wert schon ausserhalb der Grenzen, fuehrt ein Schritt nie weiter hinaus
    let v=e._v+d*st;
    v=d<0 ? Math.max(v,Math.min(mn,e._v)) : Math.min(v,Math.max(mx,e._v));
    if(v===e._v) return;
    e._v=v; e._lokal=Date.now(); e.querySelector('.stpv').textContent=stpText(bb,v);
    clearTimeout(e._senden);
    e._senden=setTimeout(()=>{ e._senden=null; const c=e._b.cmd;
      if(c) sendCmd(c.uuid,c.tmpl.split('{v}').join(String(e._v)),view&&view.secured,
                    {abbruch:()=>{ e._lokal=0; stepperUpdate(e,e._b); }}); },STP_SENDEN_MS);
  }));
}
function stepperUpdate(e,b){ e._b=b;
  if(e._senden || (e._lokal && Date.now()-e._lokal<STP_HALTEN_MS)) return;
  e._v=+b.value||0; e.querySelector('.stpv').textContent=stpText(b,e._v); }
// ---- Bild gross (verpasste Klingeln): Tippen schliesst ----
function bildZeigen(it){ const s=document.querySelector('.screen'); if(!s) return;
  const ov=document.createElement('div'); ov.className='galov';
  ov.innerHTML='<img alt="" src="'+esc(it.src)+'"><div class="gcap">'+esc(it.label||'')+'</div>';
  ov.addEventListener('click',()=>ov.remove()); s.appendChild(ov); }
function closeMenu(){ const m=document.querySelector('.menuov'); if(m)m.remove(); }
// Auswahl-Popup ueber einem Button (Klima Modus/Fan): oeffnet nach oben, Tipp
// daneben schliesst. Auswahl sendet den Befehl und schliesst.
// Verhaeltnis sichtbare Groesse / Layout-Groesse eines Elements. Ist die Visu
// skaliert (transform am .screen), liefern getBoundingClientRect und Pointer-
// Koordinaten SICHTBARE Pixel, offsetWidth/clientWidth und CSS-Werte aber
// LAYOUT-Pixel. Wer beides verrechnet, teilt Sichtbares hierdurch. Am Element
// selbst gemessen statt aus einer Variablen gelesen: stimmt so fuer jede Art
// der Skalierung, auch fuer kuenftige.
function visScale(e){ const w=e&&e.offsetWidth; return w ? (e.getBoundingClientRect().width/w)||1 : 1; }
function openMenu(btn, items){
  const s=document.querySelector('.screen'); if(!s)return;
  closeMenu();
  const ov=document.createElement('div'); ov.className='menuov';
  const box=document.createElement('div'); box.className='menubox';
  box.innerHTML=items.map((it,i)=>'<div class="menuitem'+(it.on?' on':'')+'" data-m="'+i+'">'+esc(it.label)+'</div>').join('');
  ov.appendChild(box); s.appendChild(ov);
  // Rects sind SICHTBARE Pixel, style.left/bottom LAYOUT-Pixel: bei skalierter
  // Visu erst umrechnen, sonst sitzt das Menue neben seinem Button.
  const br=btn.getBoundingClientRect(), sr=s.getBoundingClientRect(), k=visScale(s);
  let left=(br.left-sr.left)/k;
  left=Math.max(8, Math.min(left, s.offsetWidth-box.offsetWidth-8));
  box.style.left=left+'px';
  box.style.bottom=((sr.height-(br.top-sr.top))/k+6)+'px';   // ueber dem Button
  box.querySelectorAll('.menuitem').forEach(n=>{
    n.addEventListener('pointerdown',ev=>{ ev.preventDefault(); ev.stopPropagation();
      const it=items[+n.dataset.m]; closeMenu();
      if(it&&it.cmd) sendCmd(it.cmd.uuid,it.cmd.cmd,view&&view.secured); });
  });
  ov.addEventListener('pointerdown',()=>closeMenu());
}
// Struktur-Signatur der Bloecke: Art und Reihenfolge, dazu die Zaehlungen, die
// die Anzeige formen. Weicht sie vom zuletzt Gerenderten ab, muss komplett neu
// aufgebaut werden — in-place patchen wuerde neu dazugekommene Zeilen nie
// erzeugen (z.B. "Wasser nachfuellen" in der Sauna) und weggefallene stehen
// lassen. Bei den Favoriten zaehlt der Inhalt (Name, Cover, Befehl): updatePanel
// patcht sie nicht, und der Tipp haelt den Favoriten vom Aufbau fest.
function blockSig(blocks){
  return intercomBlocks(blocks).filter(b=>b.k!=='more').map(b=>
    b.k==='row' ? 'row'+b.cells.length+(b.hidden?'h':'')
    : b.k==='favs' ? 'favs'+JSON.stringify((b.items||[]).map(f=>[f.label,f.cover,f.cmd]))
    : b.k==='alarmlist' ? 'alarm'+JSON.stringify(b.entries||[])
    : b.k==='astat' ? 'astat'+(b.sub?1:0)
    : b.k==='stepper' ? 'stp'+(b.cmd?1:0)+(b.sub?1:0)
    : b.k==='chips' ? 'chips'+(b.multi?'m':'')+(b.items?b.items.length:0)
    : b.k==='gallery' ? 'gal'+(b.items||[]).map(i=>i.src).join(',')
    : b.k==='intercom-talk' ? 'intercom-talk'+b.uuid
    : b.k).join('|');
}
