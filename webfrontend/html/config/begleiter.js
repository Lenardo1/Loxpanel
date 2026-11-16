// Begleit-Tablets (eigene Version): Tablets, auf denen die LoxPanel-App nur im
// Hintergrund laeuft und vorn eine andere App zeigt (z. B. die Loxone-App).
// Die App meldet sich jede Minute (POST /api/begleiter/melden) und holt sich die
// hier gespeicherten Einstellungen. Ohne gespeicherte Einstellungen schlaegt die
// Karte vor, was das Tablet selbst gemeldet hat.
(function(){
  let STAND=null, timer=null;
  const tt=(s)=>(typeof T==='function'?T(s):s);
  function sichtbar(){ const h=$('#displaysHost'); return !!(h && h.offsetParent); }

  function statusText(g){
    if(!g) return tt('hat sich noch nicht gemeldet');
    const alt=g.vorSek, on=alt<150;
    const wann= alt<90 ? tt('gerade eben') : (alt<3600 ? tt('vor {m} min').replace('{m}', Math.round(alt/60)) : tt('vor {h} h').replace('{h}', Math.round(alt/3600)));
    return (on?'● ':'○ ')+[wann, g.ip, g.modell, g.android?('Android '+g.android):'', g.version?('App '+g.version):'',
      g.bedienungshilfe ? tt('Bedienungshilfe an') : tt('Bedienungshilfe aus')].filter(Boolean).join(' · ');
  }
  function haken(k, wert, text, hinweis){
    return '<label class="bgz"><input type="checkbox" data-k="'+k+'"'+(wert?' checked':'')+'> <b>'+esc(text)+'</b>'+
      (hinweis?'<span class="note"> – '+esc(hinweis)+'</span>':'')+'</label>';
  }
  function feld(k, wert, text, typ, breite){
    return '<label class="bgz">'+esc(text)+' <input type="'+(typ||'text')+'" data-k="'+k+'" value="'+esc(wert)+'"'+
      ' style="width:'+(breite||'28em')+'"></label>';
  }
  function karte(name, e){
    const s=e.soll || (e.gesehen && e.gesehen.ist) || STAND.standard;
    const farbe=s.farbe||'schwarz', eigen=!(farbe in STAND.farben);
    const g=e.gesehen;
    return '<div class="card bg" data-bg="'+esc(name)+'" style="margin:10px 0">'+
      '<h4 style="margin:0 0 4px">'+esc(name)+'</h4>'+
      '<div class="note bgstatus">'+esc(statusText(g))+(e.soll?'':' · '+esc(tt('noch nicht hier gespeichert – Vorschlag aus dem Tablet')))+'</div>'+
      '<div style="display:grid;gap:6px;margin-top:8px">'+
      haken('wetter', s.wetter, tt('Wetter über der App einblenden'))+
      '<div style="margin-left:24px;display:grid;gap:4px">'+
        feld('wetterQuelle', s.wetterQuelle, tt('Weather4Lox-Adresse'))+
        feld('wetterSymbole', s.wetterSymbole, tt('Miniserver-Adresse (Loxone-Wettersymbole)'))+
        '<label class="bgz">'+esc(tt('Farbe des Feldes'))+' <select data-k="farbeWahl">'+
          '<option value="schwarz"'+(farbe==='schwarz'?' selected':'')+'>'+esc(tt('Schwarz (Loxone-Kopfzeile neutral)'))+'</option>'+
          '<option value="gruen"'+(farbe==='gruen'?' selected':'')+'>'+esc(tt('Grün (Loxone-Kopfzeile Highlight)'))+'</option>'+
          '<option value="eigen"'+(eigen?' selected':'')+'>'+esc(tt('Eigene Farbe'))+'</option></select> '+
          '<input type="color" data-k="farbeEigen" value="'+esc(eigen?farbe:'#0e0e0e')+'"'+(eigen?'':' hidden')+'></label>'+
        '<label class="bgz">'+esc(tt('Lage in Pixeln (−1 = Standard)'))+' x <input type="number" data-k="x" value="'+esc(s.x)+'" style="width:6em"> '+
          'y <input type="number" data-k="y" value="'+esc(s.y)+'" style="width:6em"></label>'+
        haken('menueAusblenden', s.menueAusblenden, tt('Ausblenden, wenn das Menü der App offen ist'),
          (g && !g.bedienungshilfe) ? tt('braucht die Bedienungshilfe „LoxPanel“ am Tablet (Einstellungen → Eingabehilfe → Installierte Apps)') : '')+
      '</div>'+
      haken('startApp', s.startApp, tt('Diese App nach dem Hochfahren öffnen'))+
      '<div style="margin-left:24px">'+feld('startPaket', s.startPaket, tt('App (Paketname)'), 'text', '18em')+'</div>'+
      haken('weckdienst', s.weckdienst, tt('Display per Bewegungsmelder schalten'), tt('Port 2971, virtueller Ausgang in Loxone'))+
      haken('ble', s.ble, tt('BLE-Scanner für BLE Presence'))+
      '<div style="margin-left:24px;display:grid;gap:4px">'+
        feld('bleName', s.bleName||'', tt('Name des Scanners im Plugin (leer = wie bisher)'), 'text', '14em')+
        '<label class="bgz">'+esc(tt('Schlüssel aus BLE Presence (Shelly-Clients)'))+' <input type="password" autocomplete="off" data-k="bleSchluessel" value="" '+
          'placeholder="'+esc(s.bleSchluesselGesetzt ? tt('gesetzt – leer lassen zum Behalten') : tt('nicht gesetzt'))+'" style="width:22em"></label>'+
      '</div>'+
      '</div>'+
      '<div class="actions"><button class="btn prim" data-bgact="speichern">'+esc(tt('Speichern'))+'</button>'+
      (e.soll?' <button class="btn" data-bgact="loeschen">'+esc(tt('Einstellungen entfernen'))+'</button>':'')+
      ' <span class="toast bgtoast"></span></div></div>';
  }
  function lesen(k){
    const v=(x)=>{ const n=k.querySelector('[data-k="'+x+'"]'); return n?(n.type==='checkbox'?n.checked:n.value):null; };
    const fw=v('farbeWahl');
    return {wetter:v('wetter'), wetterQuelle:v('wetterQuelle').trim(), wetterSymbole:v('wetterSymbole').trim(),
      farbe: fw==='eigen' ? v('farbeEigen') : fw, x:parseInt(v('x'),10), y:parseInt(v('y'),10),
      menueAusblenden:v('menueAusblenden'), startApp:v('startApp'), startPaket:v('startPaket').trim(),
      weckdienst:v('weckdienst'), ble:v('ble'), bleName:v('bleName').trim(), bleSchluessel:v('bleSchluessel').trim()};
  }
  function binden(k){
    const name=k.dataset.bg;
    const sel=k.querySelector('[data-k="farbeWahl"]'), eig=k.querySelector('[data-k="farbeEigen"]');
    if(sel) sel.onchange=()=>{ eig.hidden=sel.value!=='eigen'; };
    k.querySelectorAll('button[data-bgact]').forEach(b=>{ b.onclick=async()=>{
      const toast=k.querySelector('.bgtoast');
      if(b.dataset.bgact==='loeschen' && !confirm(tt('Gespeicherte Einstellungen für {n} entfernen? Das Tablet behält dann seine eigenen.').replace('{n}', name))) return;
      try{
        const r=await fetch('/api/begleiter',{method:'POST',headers:{'Content-Type':'application/json'},
          body:JSON.stringify({name, soll: b.dataset.bgact==='loeschen' ? null : lesen(k)})});
        const j=await r.json();
        flash(toast, j.ok ? '✓ '+tt('gespeichert – das Tablet übernimmt es innerhalb einer Minute') : tt('Fehler')+': '+(j.error||r.status), !!j.ok);
        if(j.ok) laden(true);
      }catch(e){ flash(toast, tt('Fehler')+': '+e, false); }
    }; });
  }
  function zeichnen(neu){
    const box=$('#begleiter'), karte_=$('#begleiterKarte'); if(!box||!STAND) return;
    const namen=Object.keys(STAND.begleiter||{});
    karte_.hidden=!namen.length;
    const f=document.activeElement, editiert=f && box.contains(f) && f.tagName!=='BUTTON';
    namen.forEach(n=>{
      let k=box.querySelector('.bg[data-bg="'+CSS.escape(n)+'"]');
      if(!k || neu===true && !(editiert && k.contains(f))){
        const d=document.createElement('div'); d.innerHTML=karte(n, STAND.begleiter[n]);
        const nk=d.firstChild; if(k) k.replaceWith(nk); else box.appendChild(nk); binden(nk); k=nk;
      } else {
        const st=k.querySelector('.bgstatus'); if(st) st.textContent=statusText(STAND.begleiter[n].gesehen);
      }
    });
    box.querySelectorAll('.bg').forEach(k=>{ if(namen.indexOf(k.dataset.bg)<0) k.remove(); });
  }
  async function laden(neu){
    try{ const r=await fetch('/api/begleiter'); STAND=await r.json(); zeichnen(neu); }catch(e){}
  }
  function takt(){ if(sichtbar()) laden(false); }
  laden(true);
  timer=setInterval(takt, 15000);
})();
