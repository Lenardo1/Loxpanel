// LoxPanel-Konfigurator, Teil 11 von 11: Start: Daten laden, Uebersetzung der Oberflaeche.
// Die Teile laden nacheinander aus config.html (script src), alle Funktionen sind global;
// was beim Laden ausgefuehrt wird, darf nur Funktionen frueherer Teile rufen.

// ---- Start ----
load().then(einspielErgebnisZeigen).catch(e=>{ $('#pconfHost').innerHTML='<div class="empty">Konnte Daten nicht laden: '+esc(e)+'</div>'; });
loadSettings().catch(e=>{ const c=$('#conn'); if(c) c.innerHTML='Konnte Einstellungen nicht laden: '+esc(e); });
{ const mh=$('#mode_host'); if(mh) mh.textContent=location.host; }
loadPanelIds().then(()=>{ fillAudioPanels(); renderDevices(); pollDevices(); setInterval(pollDevices,6000); });

if(window.I18N) I18N.autoChrome('h2, h3, h4, label.lbl, .btn, .minibtn, .addbtn, .navbtn .nbt, .navbtn .nbs, .brand small, .itab, .cclbl, .ccmut, .empty, .muted, .note, .lead, .hint, .rub, .stab, .sectlbl, option, figcaption, .nm, .spec, .desc, .badge, .ovbox b, .ovbox span, .as-lead, .as-desc, .as-of, .as-chip, .as-def .tag, .as-def b, .as-def p, .as-start, [data-i18n]');
