// LoxPanel-Visu, Teil 9 von 12: Hausuebersicht.
// Die Teile laden nacheinander aus panel.html (script src), alle Funktionen sind global;
// was beim Laden ausgefuehrt wird, darf nur Funktionen frueherer Teile rufen.

// ---- Hausuebersicht (Tab "haus", Server: _view_haus) ----
// Die Seite besteht aus benannten Bloecken (data-hb: Kopf, Zeile, je
// aktivem Geraet, je Raum, Spieler). renderHaus baut alles; kommt dieselbe
// Seite mit neuen Zustaenden, ersetzt updateHaus nur die Bloecke, deren HTML
// sich geaendert hat - solange Lage und Blockfolge (Signatur) gleich bleiben.
// Bedient wird ueber einen Klick-Verteiler am Raster (hausKlick), deshalb
// brauchen ersetzte Bloecke keine eigenen Handler.
const HS_PFEIL='<path d="m9 6 6 6-6 6"/>', HS_ZURUECK='<path d="M15 5l-7 7 7 7"/>';
const HS_LEISER='<path d="M4 9v6h4l5 4V5L8 9z"/><path d="M16 12h5"/>';
const HS_LAUTER='<path d="M4 9v6h4l5 4V5L8 9z"/><path d="M16 12h5M18.5 9.5v5"/>';
const HS_ENERGIE='<path d="M13 2 4 14h7l-1 8 9-12h-7z"/>', HS_RUHIG='<path d="M5 12.5l4.5 4.5L19 7.5"/>';
const HS_TASTE={prev:'Zurück', play:'Wiedergabe', pause:'Pause', next:'Weiter'};
// ⋮ wie auf der Detailseite der Audio-Zone: oeffnet die Musikauswahl
const HS_DREI='<circle cx="12" cy="5" r="1.9"/><circle cx="12" cy="12" r="1.9"/><circle cx="12" cy="19" r="1.9"/>';
const HS_SCHNELL_ICO={licht:'bulb', audio:'music'};
// Mindestbreite einer Karte unter "Gerade aktiv" und einer Raumkarte, die
// Hoehe, ab der Raumkarten scrollen statt schrumpfen, und das Seitenverhaeltnis,
// das die Spaltenzahl der Raeume anstrebt (alles bei --hk 1)
const HS_AKTIV_MIN=260, HS_RAUM_MIN=200, HS_RAUM_HOCH=150, HS_RAUM_SEITE=1.4;
// Aufbau "raeume": Mindesthoehe einer Raumkarte mit Tasten (Kopfzeile 44,
// Hauptwert, Zeile darunter, Taste 52 mit Beschriftung, Rand); Aufbau
// "spalte": Breite der linken Spalte (Entwurf: 440 px am grossen Display)
const HS_RAUM_HOCH_TASTEN=200, HS_LINKS=320;
// Hinweise: Mindestbreite einer Karte in der Leiste, Breite der Taste "+n"
// dahinter und die Hoehe der Leiste (wie .hs-h)
const HS_HINWEIS_MIN=240, HS_HINWEIS_PLUS=72, HS_HINWEIS_HOCH=60;
// Sender im Spieler: Mindestbreite einer Cover-Kachel in der Leiste, Breite
// der Kachel "Mehr", Hoehe einer Kachel (Rand 8+10, Cover 64, Abstand 6,
// Name) und wie viele die Spalte nebeneinander zeigt
const HS_SENDER_MIN=104, HS_SENDER_MEHR=96, HS_SENDER_HOCH=108, HS_SENDER_SPALTE=3;
function hsIco(s, extra){
  const k='hs-i'+(extra?' '+extra:'');
  if(s.iconImg) return '<span class="'+k+'"><img src="'+esc(s.iconImg)+'" alt=""></span>';
  if(s.iconUrl) return '<span class="'+k+' img" style="--u:url(\''+esc(s.iconUrl)+'\')"></span>';
  return '<span class="'+k+'">'+svg(ICONS[s.icon]||ICONS.info)+'</span>';
}
function hsWo(a){ return a.label && a.label!==a.raum ? a.label+' · '+a.raum : (a.raum||a.label||''); }
// Masse der Flaeche: Massstab --hk aus der kleineren Seite (iPad quer 1, das
// grosse Display mehr, das 4"-Panel weniger), dazu die Lage: Spieler als
// Spalte rechts, wenn die Flaeche breit genug und quer ist, sonst als Leiste.
function hausLage(v){
  const g=el('grid'), cs=getComputedStyle(g);
  const w=g.clientWidth-parseFloat(cs.paddingLeft)-parseFloat(cs.paddingRight);
  const h=g.clientHeight-parseFloat(cs.paddingTop)-parseFloat(cs.paddingBottom);
  const hk=Math.max(.7, Math.min(1.5, Math.min(w,h)/740)), gap=12*hk;
  const spalte=!!v.spieler && w>=860 && w>h*1.1;
  const seiteW=spalte ? 280*hk+16*hk : 0, linksW=HS_LINKS*hk+16*hk;
  // Aufbau der Ansicht (Server: HAUS_AUFBAUTEN). "spalte" nur quer und nur,
  // wo neben ihr (und dem Spieler) noch zwei Raumspalten passen, sonst wie
  // "status"; die Unterseite "Gerade aktiv" gehoert zu "status"
  let aufbau=v.liste ? 'status' : (v.aufbau||'status');
  if(aufbau==='spalte' && !(w>h*1.1 && w-seiteW-linksW>=2*HS_RAUM_MIN*hk+gap)) aufbau='status';
  const links=aufbau==='spalte';
  const mainW=w-seiteW-(links?linksW:0);
  // Schnellaktionen: als Zeile ueber den Raumkarten, in "spalte" links unten
  const schnell=v.schnell.length>0 && !links;
  const zeile=aufbau==='status' && (v.aktiv.length>0 || v.schnell.length>0) && !v.liste;
  const sp=Math.max(1, Math.floor((mainW+gap)/(HS_AKTIV_MIN*hk+gap)));
  // Hinweise als Leiste unter dem Kopf ("spalte": oben in "Auf einen Blick"):
  // so viele Spalten, wie Karten in der Mindestbreite passen; sind es mehr
  // Hinweise, ruecken sie fuer die Taste "+n" zusammen
  const hn=(v.hinweise||[]).length, leiste=hn>0 && !links && !v.liste;
  const passen=breite=>Math.max(1, Math.floor((breite+gap)/(HS_HINWEIS_MIN*hk+gap)));
  let hc=passen(mainW);
  if(hn>hc) hc=passen(mainW-HS_HINWEIS_PLUS*hk-gap);
  // Hoehe fuer die Raumkarten: Flaeche minus Kopf (in "spalte" nur die
  // Titelzeile), Zeile "Gerade aktiv" bzw. Titelzeile "Raeume",
  // Schnellaktionen und (hochkant) die Spieler-Leiste
  const tH=Math.max(44,56*hk), abst=14*hk;
  let raumH=h-(links ? Math.max(44,48*hk) : 72*hk)-abst;
  if(zeile) raumH-=Math.max(44,48*hk)+10*hk+Math.max(64,80*hk)+abst;
  if(aufbau==='raeume') raumH-=Math.max(44,48*hk)+abst;
  if(schnell) raumH-=Math.max(44,72*hk)+abst;
  if(leiste) raumH-=Math.max(52,HS_HINWEIS_HOCH*hk)+abst;
  if(v.spieler && !spalte) raumH-=28*hk+64*hk+12*hk+tH+abst;
  // Karten mit Tasten ("raeume") brauchen mehr Hoehe
  const hoch=(aufbau==='raeume' ? HS_RAUM_HOCH_TASTEN : HS_RAUM_HOCH)*hk;
  // Sender im Spieler: in der Spalte eine Zeile, wenn sie neben Kopf, Karte,
  // Transport, Lautstaerke und einer Zone in die Hoehe passt; in der Leiste
  // so viele, wie neben "Mehr" in die Breite passen - sie kostet die
  // Raumkarten eine Zeile und steht nur, wenn danach noch eine Reihe Raeume
  // Platz hat (kleiner oder niedriger Schirm). Sonst bleibt die Musikauswahl (⋮)
  const sn=v.spieler && v.spieler.sender ? v.spieler.sender.length : 0, senderH=HS_SENDER_HOCH*hk+gap;
  let fc=0;
  if(sn && spalte){
    const bedarf=36*hk+3*tH+104*hk+Math.max(44,HS_SENDER_HOCH*hk)+44+Math.max(44,52*hk)+6*gap;
    if(h>=bedarf) fc=HS_SENDER_SPALTE;
  } else if(sn && raumH-senderH>=hoch){
    const frei=mainW-32*hk-(v.spieler.mehr ? HS_SENDER_MEHR*hk+gap : 0);
    fc=Math.max(1, Math.floor((frei+gap)/(HS_SENDER_MIN*hk+gap)));
    raumH-=senderH;
  }
  // Spalten der Raeume: die, deren Karten dem Seitenverhaeltnis am naechsten
  // kommen, ohne zu scrollen; scrollt jede Wahl, die mit den meisten Spalten
  // ueber der Mindestbreite und feste Kartenhoehe
  const n=Math.max(1, v.raeume.length);
  let best=null;
  for(let c=1;c<=4;c++){
    const cw=(mainW-(c-1)*gap)/c; if(c>1 && cw<HS_RAUM_MIN*hk) break;
    const rows=Math.ceil(n/c), ch=(raumH-(rows-1)*gap)/rows;
    const scroll=ch<hoch;
    const wert=(scroll?10:0)+Math.abs(Math.log((cw/Math.max(1,ch))/HS_RAUM_SEITE));
    if(!best || wert<best.wert) best={c, wert, scroll};
  }
  return {hk, spalte, sp, rc:best.c, rh:best.scroll ? Math.round(hoch*1.15)+'px' : '', zeile, schnell, aufbau, links, leiste, hc, fc};
}
// Wetter in einer Zeile: die Vorschau fuer morgen, ohne sie Lage und Hoch/Tief von heute
function hsWetter(w){
  const mo=(Array.isArray(w.forecast)?w.forecast:[])[1];
  return mo ? [mo.day, tdeg(mo.hi)+' / '+tdeg(mo.lo)].filter(Boolean).join(' ')
    : [w.cond, (w.hi!=null||w.lo!=null) ? tdeg(w.hi)+' / '+tdeg(w.lo) : ''].filter(Boolean).join(' · ');
}
// Raumkarte "status"/"spalte": die ganze Karte oeffnet den Raum
function hsRaumKarte(r, i, L){
  const sym=r.symbole.map(s=>'<span class="s'+(s.on?' on':'')+'">'+hsIco(s)+'</span>').join('');
  return '<button type="button" class="hs-c hs-r" data-hb="r:'+esc(r.id)+'" data-hs="raum" data-i="'+i+'" aria-label="'+esc('Raum '+r.name+' öffnen')+'">'+
    '<span class="kopf"><span class="nm">'+esc(r.name)+'</span><span class="chev'+(L.spalte?'':' rund')+'">'+svg(HS_PFEIL)+'</span></span>'+
    '<span class="wt'+((r.wert||'').length>8?' lang':'')+'">'+esc(r.wert||'')+'</span>'+
    '<span class="sb">'+esc(r.sub || (r.anzahl===1 ? '1 Baustein' : r.anzahl+' Bausteine'))+'</span>'+
    '<span class="sym">'+sym+(r.an?'<span class="an">'+r.an+' an</span>':'')+'</span></button>';
}
// Raumkarte "raeume": runde Tasten schalten direkt (Server: _haus_tasten), die
// Taste oben rechts oeffnet den Raum. Eine Taste mit Rueckfrage (frage) zeigt
// nach dem ersten Tipp die Frage, erst der zweite schaltet (hsFrage)
function hsRaumTasten(r, i){
  const tasten=(r.tasten||[]).map((t,j)=>{
    const frage=hsFrage===t.id && t.frage;
    return '<button type="button" class="hs-t'+(t.an?' on':'')+(frage?' arm':'')+'" data-hs="taste" data-r="'+i+'" data-t="'+j+'" aria-pressed="'+t.an+'" '+
      'aria-label="'+esc(t.name+' '+r.name+', '+(frage||t.zustand))+'"><span class="k">'+hsIco(t)+'</span><span class="l">'+esc(frage||t.name)+'</span></button>';
  }).join('');
  return '<div class="hs-c hs-r direkt" data-hb="r:'+esc(r.id)+'">'+
    '<span class="kopf"><span class="nm">'+esc(r.name)+'</span><button type="button" class="chev rund" data-hs="raum" data-i="'+i+'" aria-label="'+
      esc('Raum '+r.name+' öffnen')+'">'+svg(HS_PFEIL)+'</button></span>'+
    '<span class="wt'+((r.wert||'').length>8?' lang':'')+'">'+esc(r.wert||'')+'</span>'+
    '<span class="sb">'+esc(r.sub || (r.anzahl===1 ? '1 Baustein' : r.anzahl+' Bausteine'))+'</span>'+
    (tasten ? '<span class="tasten">'+tasten+'</span>' : '')+'</div>';
}
// Hinweis als Karte (Leiste, Unterseite, "Auf einen Blick"); ein Tipp oeffnet den Baustein
function hsHinweis(h, i){
  return '<button type="button" class="hs-h '+esc(h.stufe)+'" data-hs="hinweis" data-i="'+i+'"'+(h.nav?'':' disabled')+
    ' aria-label="'+esc(h.titel+', '+h.wo)+'"><span class="kr">'+hsIco(h)+'</span>'+
    '<span class="tx"><span class="z">'+esc(h.titel)+'</span><span class="w">'+esc(h.wo)+'</span></span></button>';
}
function hsHinweise(n){ return n===1 ? '1 Hinweis' : n+' Hinweise'; }
// Termine von heute und morgen aus der Front, die noch kommen (heute mit
// Uhrzeit: ab jetzt), hoechstens so viele, wie die Uhr-Seite zeigt
// (svCount): in "Auf einen Blick" der Spalte, die keinen Kopf mit dem
// naechsten Termin hat. tickClock zeichnet sie jede Minute neu
function hsTermine(d){
  const jetzt=new Date(), nun=jetzt.getHours()*60+jetzt.getMinutes();
  const tag=plus=>{ const t=new Date(jetzt); t.setDate(t.getDate()+plus);
    return t.getFullYear()+'-'+String(t.getMonth()+1).padStart(2,'0')+'-'+String(t.getDate()).padStart(2,'0'); };
  const heute=tag(0), morgen=tag(1);
  return (Array.isArray(d.events)?d.events:[]).filter(e=>{
    if(e.date===morgen || (e.date===heute && e.allday)) return true;
    const m=e.date===heute && /^(\d{1,2}):(\d{2})$/.exec(e.time||'');
    return !!m && +m[1]*60 + +m[2] >= nun;
  }).slice(0, svCount(d));
}
// Cover (Spieler, Sender): das Bild liegt ueber dem Musik-Symbol, damit ein
// Bild, das nicht laedt, nur verschwindet (hsCoverFehlt)
function hsCover(k, src){ return '<span class="'+k+'">'+svg(ICONS.music)+(src ? '<img src="'+esc(src)+'" alt="">' : '')+'</span>'; }
function hsCoverFehlt(e){
  const i=e.target;
  if(i && i.tagName==='IMG' && i.parentElement && i.parentElement.matches('.hs-cov,.hs-f .fc')) i.remove();
}
// Sender im Spieler (Server: _haus_sender): Cover und Name, ein Tipp spielt ihn
function hsSender(s, i){
  return '<button type="button" class="btn hs-b hs-f'+(s.laeuft?' akt':'')+'" data-hs="sender" data-i="'+i+'" aria-pressed="'+!!s.laeuft+'" '+
    'aria-label="'+esc(s.name+(s.laeuft ? ', läuft' : ', abspielen'))+'">'+hsCover('fc', s.cover)+'<span class="n">'+esc(s.name)+'</span></button>';
}
// Unterseite ohne Inhalt (nichts mehr an bzw. kein Hinweis mehr): zurueck
function hsListeLeer(v){ return v.liste==='hinweise' ? !(v.hinweise||[]).length : !v.aktiv.length; }
function hausBloecke(v, L){
  const B=[], d=frontData||{}, w=d.weather, ev=(Array.isArray(d.events)?d.events:[])[0];
  const hw=v.hinweise||[];
  const e=v.energie, summen=e && e.cons!=null;
  if(L.links){
    // Spalte links: Uhr mit Wetter, Energie, "Auf einen Blick" (Server:
    // _haus_blick), darunter die Schnellaktionen
    B.push(['luhr','links','<div class="hs-luhr" data-hb="luhr"><span class="t" id="hsTime">--:--</span><span class="d" id="hsDate"></span>'+
      (w ? '<span class="wx"><span class="hs-i">'+wxSvg(w.icon)+'</span><span class="z">'+tdeg(w.temp)+'</span><span class="w">'+esc(hsWetter(w))+'</span></span>' : '')+'</div>']);
    if(e) B.push(['lenergie','links','<button type="button" class="hs-c hs-len" data-hb="lenergie" data-hs="energie" aria-label="'+esc(e.label)+'">'+
      '<span class="kopf"><b>Energie</b><span>'+esc(e.label)+'</span></span>'+
      (summen ? '<span class="werte">'+(e.prod!=null ? '<span class="wt"><span class="w">Produktion</span><span class="z">'+esc(fmtPower(e.prod))+'</span></span>' : '')+
        '<span class="wt"><span class="w">Verbrauch</span><span class="z">'+esc(fmtPower(e.cons))+'</span></span></span>'
       : '<span class="z">'+esc(e.wert||e.label)+'</span>')+'</button>']);
    // oben die Hinweise (ohne: "Alles in Ordnung"), dann die Termine von
    // heute und morgen, darunter unter "Status" die Bausteine (_haus_blick)
    const blick=v.blick||[], termine=hsTermine(d), kal=(TABS.find(t=>t.tab==='kalender')||{}).icon||ICONS.info;
    B.push(['blick','links','<div class="hs-c hs-blick" data-hb="blick"><div class="kopf"><h2>Auf einen Blick</h2>'+
      (hw.length ? '<span class="n">'+hsHinweise(hw.length)+'</span>' : '')+'</div><div class="liste">'+
      (hw.length ? hw.map(hsHinweis).join('')
       : '<div class="hs-h ok"><span class="kr"><span class="hs-i ok">'+svg(HS_RUHIG)+'</span></span>'+
         '<span class="tx"><span class="z">Alles in Ordnung</span></span></div>')+
      termine.map(t=>'<div class="hs-h termin"><span class="kr"><span class="hs-i">'+svg(kal)+'</span></span>'+
        '<span class="tx"><span class="z">'+esc(t.title||'')+'</span><span class="w">'+esc([t.day, t.time].filter(Boolean).join(', '))+'</span></span></div>').join('')+
      (blick.length ? '<span class="lbl">Status</span>'+blick.map((x,i)=>'<button type="button" class="hs-bz" data-hs="blick" data-i="'+i+'"'+(x.nav?'':' disabled')+'>'+hsIco(x)+
        '<span class="tx"><span class="z">'+esc(x.zustand)+'</span><span class="w">'+esc(x.name)+'</span></span></button>').join('') : '')+
      '</div></div>']);
  } else {
    let kopf='<div class="hs-kopf" data-hb="kopf"><div class="hs-uhr"><span class="t" id="hsTime">--:--</span><span class="d" id="hsDate"></span></div>';
    if(w) kopf+='<div class="hs-c hs-k">'+'<span class="hs-i wx">'+wxSvg(w.icon)+'</span><span class="tx"><span class="z">'+tdeg(w.temp)+'</span>'+
      '<span class="w">'+esc(hsWetter(w))+'</span></span></div>';
    if(ev) kopf+='<div class="hs-c hs-k"><span class="tx"><span class="w">'+esc([ev.day, ev.time].filter(Boolean).join(', '))+'</span>'+
      '<span class="z">'+esc(ev.title||'')+'</span></span></div>';
    if(e) kopf+='<button type="button" class="hs-c hs-k" data-hs="energie" aria-label="'+esc(e.label)+'">'+
      '<span class="hs-i">'+svg(HS_ENERGIE)+'</span><span class="tx"><span class="z">'+esc(summen ? fmtPower(e.cons) : (e.wert||e.label))+'</span>'+
      '<span class="w">'+esc(summen ? 'Verbrauch'+(e.prod!=null ? ' · PV '+fmtPower(e.prod) : '') : e.label)+'</span></span></button>';
    B.push(['kopf','main',kopf+'</div>']);
    // Hinweise als Leiste; passen nicht alle, fuehrt "+n" zur Unterseite
    if(L.leiste){
      const zeigen=Math.min(hw.length, L.hc), rest=hw.length-zeigen;
      B.push(['hinweise','main','<div class="hs-hw" data-hb="hinweise" style="grid-template-columns:repeat('+L.hc+',minmax(0,1fr))'+(rest?' auto':'')+'">'+
        hw.slice(0,zeigen).map(hsHinweis).join('')+
        (rest ? '<button type="button" class="hs-h hs-hplus" data-hs="hinweise" aria-label="Alle '+hsHinweise(hw.length)+' zeigen">+'+rest+svg(HS_PFEIL)+'</button>' : '')+
        '</div>']);
    }
  }
  // Schnellaktionen (Zentral-Bausteine der Anlage): rechts, wie viele an sind,
  // leer, wenn nichts laeuft; die Zahl kommt mit jeder Zustandsaenderung neu.
  // In "spalte" stehen sie links unter "Auf einen Blick"
  if(v.schnell.length) B.push(['schnell',L.links?'links':'schnell','<div class="hs-schnell" data-hb="schnell">'+v.schnell.map((s,i)=>{
    const n=s.an ? s.an+' an' : '';
    return '<button type="button" class="hs-c hs-s" data-hs="schnell" data-art="'+esc(s.art)+'" data-i="'+i+'" aria-label="'+
      esc(s.label+(n ? ', '+n : ''))+'"><span class="hs-i">'+svg(ICONS[HS_SCHNELL_ICO[s.art]]||ICONS.switch)+'</span>'+
      '<span class="z">'+esc(s.label)+'</span><span class="n">'+esc(n)+'</span></button>';
  }).join('')+'</div>']);
  const anzahl=v.aktiv.length===1 ? '1 Gerät' : v.aktiv.length+' Geräte';
  const karte=(a,i)=>'<div class="hs-c hs-a on" data-hb="a:'+esc(a.id)+'">'+hsIco(a)+
    '<span class="tx"><span class="z">'+esc(a.zustand||a.label)+'</span><span class="w">'+esc(hsWo(a))+'</span></span>'+
    '<button type="button" class="btn hs-b" data-hs="aus" data-i="'+i+'" aria-label="'+esc(a.taste+': '+hsWo(a))+'">'+esc(a.taste)+'</button></div>';
  if(v.liste){
    const hinweise=v.liste==='hinweise';
    B.push(['lkopf','main','<div class="hs-zeile" data-hb="lkopf"><button type="button" class="btn hs-b hs-rund" data-hs="zurueck" aria-label="Zurück">'+
      svg(HS_ZURUECK)+'</button><h2>'+(hinweise ? 'Hinweise' : 'Gerade aktiv')+'</h2><span class="n">'+(hinweise ? hsHinweise(hw.length) : anzahl)+'</span></div>']);
    if(hinweise) hw.forEach((h,i)=>B.push(['h:'+h.id,'liste',hsHinweis(h,i)]));
    else v.aktiv.forEach((a,i)=>B.push(['a:'+a.id,'liste',karte(a,i)]));
  } else {
    if(L.zeile){
      B.push(['akopf','main','<div class="hs-zeile" data-hb="akopf"><h2>Gerade aktiv</h2><span class="n">'+anzahl+'</span></div>']);
      // So viele Karten wie Spalten; mehr -> die letzte Stelle wird "+n weitere"
      const zeigen = v.aktiv.length>L.sp ? L.sp-1 : v.aktiv.length;
      v.aktiv.slice(0,zeigen).forEach((a,i)=>B.push(['a:'+a.id,'aktiv',karte(a,i)]));
      if(v.aktiv.length>zeigen) B.push(['mehr','aktiv','<button type="button" class="hs-c hs-a hs-mehr" data-hb="mehr" data-hs="mehr" '+
        'aria-label="Alle '+v.aktiv.length+' aktiven Geräte zeigen">+'+(v.aktiv.length-zeigen)+' weitere'+svg(HS_PFEIL)+'</button>']);
      if(!v.aktiv.length) B.push(['ruhig','aktiv','<div class="hs-c hs-a" data-hb="ruhig"><span class="hs-i ok">'+svg(HS_RUHIG)+'</span>'+
        '<span class="tx"><span class="z">Alles ruhig</span><span class="w">Kein Licht an, keine Musik</span></span></div>']);
    }
    // "raeume" und "spalte": statt "Gerade aktiv" eine Titelzeile mit der Zahl
    if(L.aufbau!=='status') B.push(['rkopf','main','<div class="hs-zeile" data-hb="rkopf"><h2>Räume</h2><span class="n">'+
      (v.aktiv.length===1 ? '1 Gerät an' : v.aktiv.length+' Geräte an')+'</span></div>']);
    v.raeume.forEach((r,i)=>B.push(['r:'+r.id,'raeume', L.aufbau==='raeume' ? hsRaumTasten(r,i) : hsRaumKarte(r,i,L)]));
  }
  const sp=v.spieler;
  if(sp){
    const cover=hsCover('hs-cov', sp.cover);
    const zustand=sp.sub || (sp.spielt ? 'Spielt' : 'Pausiert');
    const tasten='<div class="hs-tasten">'+sp.tasten.map((t,i)=>'<button type="button" class="btn hs-b" data-hs="sp" data-i="'+i+'" aria-label="'+
      esc(HS_TASTE[t.icon]||t.icon)+'">'+svgF(ICONS[t.icon]||ICONS.info)+'</button>').join('')+'</div>';
    const l=sp.laut, pct=l ? Math.round(100*(l.wert-l.min)/Math.max(1,l.max-l.min)) : 0;
    const laut=l ? '<div class="hs-laut"><button type="button" class="btn hs-b" data-hs="laut" data-d="-1" aria-label="Leiser">'+svg(HS_LEISER)+'</button>'+
      '<span class="v"><span>'+l.wert+'</span><span class="bar"><i style="width:'+pct+'%"></i></span></span>'+
      '<button type="button" class="btn hs-b" data-hs="laut" data-d="1" aria-label="Lauter">'+svg(HS_LAUTER)+'</button></div>' : '';
    const kl=' class="hs-c hs-sp'+(sp.spielt?' spielt':'')+(L.spalte?'':' leiste'+(sp.spielt?' on':''))+'" data-hb="sp"';
    const drei=sp.mehr ? '<button type="button" class="btn hs-b hs-drei" data-hs="quellen" aria-label="'+
      esc('Musikauswahl '+sp.name)+'">'+svgF(HS_DREI)+'</button>' : '';
    // Sender: so viele, wie die Lage vorsieht (L.fc), der Rest in der Musikauswahl
    const sender=(sp.sender||[]).slice(0, L.fc), alle=sp.mehr ? 'aria-label="'+esc('Alle Sender und Favoriten, '+sp.name)+'"' : '';
    if(L.spalte){
      const zonen=sp.zonen.length>1 ? '<div class="hs-zonen"><span class="lbl">Zonen</span>'+sp.zonen.map(z=>
        '<button type="button" class="btn hs-b hs-zone'+(z.id===sp.zone?' akt':'')+'" data-hs="zone" data-id="'+esc(z.id)+'" aria-pressed="'+(z.id===sp.zone)+'">'+
        '<span class="hs-i'+(z.spielt?' wx':'')+'">'+svg(ICONS.music)+'</span><span class="tx"><span class="z">'+esc(z.name)+'</span>'+
        '<span class="w">'+esc(z.spielt ? ['Spielt', z.titel].filter(Boolean).join(' · ') : 'Aus')+'</span></span></button>').join('')+'</div>' : '';
      const favs=sender.length ? '<div class="hs-fk"><span class="lbl">Favoriten</span>'+
        (sp.mehr ? '<button type="button" class="btn hs-b hs-alle" data-hs="quellen" '+alle+'>Alle'+svg(HS_PFEIL)+'</button>' : '')+'</div>'+
        '<div class="hs-fav" style="grid-template-columns:repeat('+L.fc+',minmax(0,1fr))">'+sender.map(hsSender).join('')+'</div>' : '';
      B.push(['sp','seite','<div'+kl+'><div class="hs-spk"><b>Audio</b><span>'+esc(sp.name)+'</span>'+drei+'</div>'+
        '<div class="hs-cv">'+cover+'<span class="cvt"><span class="ti">'+esc(sp.titel)+'</span><span class="w st">'+esc(zustand)+'</span></span></div>'+
        tasten+laut+favs+zonen+'</div>']);
    } else {
      const i=sp.zonen.findIndex(z=>z.id===sp.zone), weiter=sp.zonen[(i+1)%sp.zonen.length];
      const zw=sp.zonen.length>1 ? '<button type="button" class="btn hs-b hs-zw" data-hs="zone" data-id="'+esc(weiter.id)+'" aria-label="'+
        esc('Zone wechseln, jetzt '+sp.name+', weiter zu '+weiter.name)+'">'+svg('<path d="M4 8h13l-3-3M20 16H7l3 3"/>')+'<span>'+esc(sp.name)+'</span></button>' : '';
      const favs=sender.length ? '<div class="hs-fav" style="grid-template-columns:repeat('+L.fc+',minmax(0,1fr))'+
        (sp.mehr ? ' calc('+HS_SENDER_MEHR+'px * var(--hk))' : '')+'">'+sender.map(hsSender).join('')+
        (sp.mehr ? '<button type="button" class="btn hs-b hs-fmehr" data-hs="quellen" '+alle+'>'+svg(HS_PFEIL)+'Mehr</button>' : '')+'</div>' : '';
      B.push(['sp','unten','<div'+kl+'><div class="r1">'+cover+'<span class="tx"><span class="ti">'+esc(sp.titel)+'</span>'+
        '<span class="w st">'+esc(zustand+(sp.zonen.length>1?'':' · '+sp.name))+'</span></span>'+zw+drei+'</div>'+
        '<div class="r2">'+tasten+laut+'</div>'+favs+'</div>']);
    }
  }
  return B;
}
// Signatur: Lage und Blockfolge. Gleich -> updateHaus darf Bloecke tauschen.
// Zur Lage gehoert, ob die Raumkarten scrollen, nicht ihre Hoehe: die waechst
// mit --hk und kommt wie die anderen Masse aus hausMasse
function hausSig(L, B){ return JSON.stringify([L.aufbau, L.links, L.spalte, L.sp, L.rc, !!L.rh, L.zeile, L.leiste, L.fc, B.map(b=>b[0])]); }
// Masse der Lage als CSS-Variablen; auch bei gleicher Signatur, denn --hk (Schrift-
// Skalierung) waechst und schrumpft mit dem Fenster, ohne dass die Lage kippt
function hausMasse(g, L){
  g.style.setProperty('--hk', L.hk.toFixed(3));
  g.style.setProperty('--hs-sp', L.sp);
  g.style.setProperty('--hs-rc', L.rc);
  if(L.rh) g.style.setProperty('--hs-rh', L.rh); else g.style.removeProperty('--hs-rh');
}
// Raumkarten, die ihren Inhalt nicht fassen (zweizeiliger Name, langer
// Zustand): die Reihen so hoch, wie die hoechste Karte braucht - dann
// scrollt die Liste senkrecht, statt dass eine Zeile abgeschnitten wird.
// Nach hausMasse, das --hs-rh auf die gerechnete Hoehe zuruecksetzt
function hausReihen(g){
  const karten=[...g.querySelectorAll('.hs-r')];
  if(karten.some(k=>k.scrollHeight>k.clientHeight+1))
    g.style.setProperty('--hs-rh', Math.ceil(Math.max(...karten.map(k=>k.scrollHeight)))+'px');
}
function renderHaus(){
  const g=el('grid'), v=view;
  g.classList.remove('list','snapy','lx','hpages','punkte','fuss','panel','bigpage','anchorbot','scheme','fronttab','chartpage');
  g.classList.add('haus');
  // Unterseite "Gerade aktiv" bzw. "Hinweise", aber nichts mehr da: zurueck zur Uebersicht
  if(v.liste && hsListeLeer(v)){ if(stack.length>1) back(); }
  const L=hausLage(v);
  hausMasse(g, L);
  const B=hausBloecke(v, L), teil=o=>B.filter(b=>b[1]===o).map(b=>b[2]).join('');
  let main=teil('main');
  if(v.liste) main+=teil('schnell')+'<div class="hs-liste">'+teil('liste')+'</div>';
  else { main+=(L.zeile?'<div class="hs-aktiv">'+teil('aktiv')+'</div>':'')+teil('schnell')+'<div class="hs-raeume">'+teil('raeume')+'</div>'; }
  main+=teil('unten');
  const links=L.links ? '<div class="hs-links">'+teil('links')+'</div>' : '';
  g.innerHTML='<div class="hs'+(L.spalte?' spalte':'')+(L.links?' links':'')+'">'+links+'<div class="hs-main">'+main+'</div>'+teil('seite')+'</div>';
  B.forEach(b=>{ const n=g.querySelector('[data-hb="'+CSS.escape(b[0])+'"]'); if(n) n._h=b[2]; });
  hausReihen(g);
  g._hsSig=hausSig(L, B);
  if(!g._hsKlick){ g._hsKlick=true; g.addEventListener('click', hausKlick); g.addEventListener('error', hsCoverFehlt, true); }
  tickClock();
  renderTabs();
}
// Gleiche Seite, neue Zustaende: nur geaenderte Bloecke tauschen. false ->
// Lage oder Blockfolge anders, renderHaus baut neu.
function updateHaus(){
  const g=el('grid'), v=view;
  if(!v || v.layout!=='haus' || !g.classList.contains('haus')) return false;
  if(v.liste && hsListeLeer(v)) return false;
  const L=hausLage(v), B=hausBloecke(v, L);
  if(g._hsSig!==hausSig(L, B)) return false;
  hausMasse(g, L);
  B.forEach(([k,,h])=>{
    const n=g.querySelector('[data-hb="'+CSS.escape(k)+'"]');
    if(!n || n._h===h) return;
    const t=document.createElement('template'); t.innerHTML=h;
    const m=t.content.firstElementChild; m._h=h; n.replaceWith(m);
  });
  hausReihen(g);
  tickClock();
  return true;
}
// Aufbau "raeume": Taste mit Rueckfrage nach dem ersten Tipp (id des
// Bausteins) und ihr Zeitlimit; renderHaus/updateHaus zeichnen sie danach
let hsFrage=null, hsFrageT=null;
function hausNeu(){ if(view && view.layout==='haus' && !updateHaus()) renderHaus(); }
function hausZone(id){
  const r=Object.assign({}, view.route, {zone:id});
  stack[stack.length-1]=r; send({t:'nav', route:r});
}
function hausKlick(e){
  const v=view; if(!v || v.layout!=='haus') return;
  const b=e.target.closest('[data-hs]'); if(!b) return;
  const art=b.dataset.hs, i=+b.dataset.i, sp=v.spieler;
  if(art==='raum'){ const r=v.raeume[i]; if(r) nav(r.nav); }
  else if(art==='aus'){ const a=v.aktiv[i]; if(a) sendCmd(a.aus.uuid, a.aus.cmd, a.secured); }
  else if(art==='schnell'){ const s=v.schnell[i]; if(s) sendCmd(s.cmd.uuid, s.cmd.cmd, s.secured); }
  else if(art==='mehr') nav(Object.assign({}, v.route, {liste:'aktiv'}));
  else if(art==='zurueck') back();
  else if(art==='energie'){ if(v.energie) nav(v.energie.nav); }
  else if(art==='sp'){ const t=sp && sp.tasten[i]; if(t) sendCmd(t.cmd.uuid, t.cmd.cmd, sp.secured); }
  else if(art==='laut' && sp && sp.laut){
    const l=sp.laut, neu=Math.max(l.min, Math.min(l.max, l.wert+(+b.dataset.d)*l.schritt));
    if(neu!==l.wert) sendCmd(l.cmd.uuid, l.cmd.tmpl.replace('{v}', neu), sp.secured); }
  else if(art==='zone' && b.dataset.id) hausZone(b.dataset.id);
  else if(art==='quellen'){ if(sp && sp.mehr) nav(sp.mehr); }
  else if(art==='sender'){ const s=sp && sp.sender && sp.sender[i]; if(s) sendCmd(s.cmd.uuid, s.cmd.cmd, sp.secured); }
  else if(art==='blick'){ const x=v.blick && v.blick[i]; if(x && x.nav) nav(x.nav); }
  else if(art==='hinweis'){ const h=v.hinweise && v.hinweise[i]; if(h && h.nav) nav(h.nav); }
  else if(art==='hinweise') nav(Object.assign({}, v.route, {liste:'hinweise'}));
  else if(art==='taste'){
    const r=v.raeume[+b.dataset.r], t=r && r.tasten && r.tasten[+b.dataset.t]; if(!t) return;
    clearTimeout(hsFrageT);
    if(t.frage && hsFrage!==t.id){
      // erster Tipp: nachfragen, nach ZELLE_BESTAETIGEN_MS ohne zweiten zurueck
      hsFrage=t.id; hsFrageT=setTimeout(()=>{ hsFrage=null; hausNeu(); }, ZELLE_BESTAETIGEN_MS); hausNeu(); return;
    }
    if(hsFrage){ hsFrage=null; hausNeu(); }
    sendCmd(t.cmd.uuid, t.cmd.cmd, t.secured);
  }
}
// Test-/Vorschau-Schalter: ?front=1 zeigt die ausfuehrliche Ansicht als Vollseite.
