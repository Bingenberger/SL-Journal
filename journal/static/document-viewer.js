'use strict';
(() => {
  const viewer=document.querySelector('[data-document-viewer]');
  if(!viewer)return;
  const bild=viewer.querySelector('[data-viewer-image]'),status=viewer.querySelector('.viewer-status');
  const leiste=viewer.querySelector('[data-viewer-bar]'),zaehler=viewer.querySelector('[data-viewer-count]');
  const zurueck=viewer.querySelector('[data-viewer-prev]'),weiter=viewer.querySelector('[data-viewer-next]');
  const seitenBasis=viewer.dataset.pagesUrl;
  let seite=1,seiten=1;

  function melde(text){bild.hidden=true;status.hidden=false;status.textContent=text;}

  function zeige(nummer){
    seite=Math.min(Math.max(1,nummer),seiten);
    status.hidden=false;status.textContent='Seite '+seite+' wird geladen …';
    // Direkt als Bild laden: die Seite kommt aus dem Journal, nicht aus der Cloud.
    bild.src=seitenBasis+seite;
    zaehler.textContent=seiten>1?`Seite ${seite} von ${seiten}`:'Vorschau';
    zurueck.disabled=seite<=1;weiter.disabled=seite>=seiten;
  }
  bild.addEventListener('load',()=>{bild.hidden=false;status.hidden=true;});
  bild.addEventListener('error',()=>melde('Diese Seite lässt sich gerade nicht anzeigen. Die Datei können Sie herunterladen.'));
  zurueck.addEventListener('click',()=>zeige(seite-1));
  weiter.addEventListener('click',()=>zeige(seite+1));
  document.addEventListener('keydown',event=>{
    if(event.target.matches('input,textarea,select')||event.ctrlKey||event.metaKey||document.querySelector('dialog[open]'))return;
    if(event.key==='ArrowLeft')zeige(seite-1);
    if(event.key==='ArrowRight')zeige(seite+1);
  });

  fetch(viewer.dataset.infoUrl,{headers:{'X-Requested-With':'fetch'}})
    .then(async antwort=>{
      const daten=await antwort.json().catch(()=>({}));
      if(!antwort.ok)throw new Error(daten.error||'Die Vorschau ist nicht verfügbar.');
      seiten=Math.max(1,Number(daten.seiten)||1);
      leiste.hidden=false;
      zurueck.hidden=weiter.hidden=seiten<2;
      zeige(1);
    })
    .catch(fehler=>{melde(fehler.message);leiste.hidden=false;zurueck.hidden=weiter.hidden=true;});
})();
