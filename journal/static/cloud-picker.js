'use strict';
(() => {
  const groesse=bytes=>!bytes?'':bytes>=1048576?`${(bytes/1048576).toFixed(1)} MB`:`${Math.max(1,Math.round(bytes/1024))} KB`;
  const datum=wert=>{const d=new Date(wert);return isNaN(d)?'':d.toLocaleDateString('de-DE');};
  const symbol=name=>{
    const bild=document.createElementNS('http://www.w3.org/2000/svg','svg');
    bild.setAttribute('class','icon');bild.setAttribute('aria-hidden','true');
    const nutzung=document.createElementNS('http://www.w3.org/2000/svg','use');
    nutzung.setAttribute('href','#i-'+name);bild.append(nutzung);
    return bild;
  };

  function einrichten(bereich){
    const dialog=bereich.closest('dialog'),formular=bereich.closest('form');
    const oeffnen=dialog.querySelector(`[data-cloud-open][aria-controls="${bereich.id}"]`);
    if(!oeffnen)return;
    const mehrfach=bereich.dataset.cloudMode==='multi';
    const gewaehlt=oeffnen.parentElement.querySelector('[data-cloud-chosen]');
    const korb=mehrfach?bereich.closest('details').querySelector('[data-chosen-documents]'):null;
    const suche=bereich.querySelector('[data-cloud-search]'),pfadleiste=bereich.querySelector('[data-cloud-path]');
    const liste=bereich.querySelector('[data-cloud-list]'),status=bereich.querySelector('[data-cloud-status]');
    const neuladen=bereich.querySelector('[data-cloud-reload]');
    let pfad='',laeuft=null,tippen=null;

    const gewaehlteAdressen=()=>korb?[...korb.querySelectorAll('input[name=document_url]')].map(i=>i.value):[];

    function meldung(){
      if(!korb)return;
      const anzahl=korb.children.length;
      gewaehlt.textContent=anzahl?`${anzahl} ${anzahl===1?'Datei':'Dateien'} vorgemerkt`:'';
    }

    function pfadZeigen(teile){
      pfadleiste.replaceChildren();
      const wurzel=document.createElement('button');
      wurzel.type='button';wurzel.className='cloud-crumb';wurzel.textContent='Nextcloud';
      wurzel.addEventListener('click',()=>lade(''));
      pfadleiste.append(wurzel);
      teile.forEach((stueck,index)=>{
        pfadleiste.append(Object.assign(document.createElement('span'),{className:'cloud-sep',textContent:'/'}));
        const knopf=document.createElement('button');
        knopf.type='button';knopf.className='cloud-crumb';knopf.textContent=stueck;
        knopf.addEventListener('click',()=>lade(teile.slice(0,index+1).join('/')));
        pfadleiste.append(knopf);
      });
    }

    function vormerken(eintrag){
      if(gewaehlteAdressen().includes(eintrag.url))return;
      const zeile=document.createElement('li');
      zeile.className='chosen-document';
      const name=eintrag.name.replace(/\.[^.]+$/,'');
      zeile.append(symbol('file'),Object.assign(document.createElement('span'),{textContent:eintrag.name}));
      const weg=document.createElement('button');
      weg.type='button';weg.className='mini-button';weg.setAttribute('aria-label','Verknüpfung zu '+eintrag.name+' wieder entfernen');
      weg.append(symbol('close'),Object.assign(document.createElement('span'),{textContent:'Entfernen'}));
      weg.addEventListener('click',()=>{zeile.remove();meldung();});
      zeile.append(weg);
      for(const [feld,wert] of [['document_url',eintrag.url],['document_name',name]]){
        const versteckt=document.createElement('input');
        versteckt.type='hidden';versteckt.name=feld;versteckt.value=wert;
        zeile.append(versteckt);
      }
      korb.append(zeile);
      meldung();
    }

    function waehle(eintrag){
      if(mehrfach){vormerken(eintrag);return;}
      formular.elements.url.value=eintrag.url;
      if(!formular.elements.name.value.trim())formular.elements.name.value=eintrag.name.replace(/\.[^.]+$/,'');
      gewaehlt.textContent='Gewählt: '+eintrag.name;
      schliessen();
      formular.elements.name.focus();
    }

    function zeichne(daten){
      liste.replaceChildren();
      pfadZeigen(daten.suche?[]:daten.teile||[]);
      pfadleiste.hidden=Boolean(daten.suche);
      if(!daten.eintraege.length){
        status.hidden=false;
        status.textContent=daten.suche?'Keine Datei mit diesem Namen gefunden.':'Dieser Ordner ist leer.';
        return;
      }
      status.hidden=true;
      const schon=gewaehlteAdressen();
      for(const eintrag of daten.eintraege){
        const zeile=document.createElement('li');
        const knopf=document.createElement('button');
        const vorgemerkt=!eintrag.ordner&&schon.includes(eintrag.url);
        knopf.type='button';knopf.className='cloud-item'+(eintrag.ordner?' ist-ordner':'')+(vorgemerkt?' ist-gewaehlt':'');
        const text=document.createElement('span');text.className='cloud-name';text.textContent=eintrag.name;
        const rand=document.createElement('span');rand.className='cloud-meta';
        rand.textContent=[daten.suche?eintrag.pfad.split('/').slice(0,-1).join('/'):'',
                          eintrag.ordner?'':groesse(eintrag.groesse),datum(eintrag.geaendert),
                          vorgemerkt?'vorgemerkt':''].filter(Boolean).join(' · ');
        knopf.append(symbol(eintrag.ordner?'folder':'file'),text,rand);
        knopf.addEventListener('click',()=>{
          if(eintrag.ordner){lade(eintrag.pfad);return;}
          waehle(eintrag);
          if(mehrfach&&!knopf.classList.contains('ist-gewaehlt')){
            knopf.classList.add('ist-gewaehlt');
            rand.textContent=[rand.textContent,'vorgemerkt'].filter(Boolean).join(' · ');
          }
        });
        zeile.append(knopf);liste.append(zeile);
      }
      if(daten.gekuerzt){
        const hinweis=document.createElement('li');
        hinweis.className='cloud-hint';
        hinweis.textContent=daten.suche?'Nur die ersten Treffer werden gezeigt. Bitte genauer suchen.':'Sehr großer Ordner – es werden nicht alle Einträge gezeigt.';
        liste.append(hinweis);
      }
    }

    async function hole(adresse){
      laeuft?.abort();
      const steuerung=new AbortController();laeuft=steuerung;
      status.hidden=false;status.textContent='Wird geladen …';
      try{
        const antwort=await fetch(adresse,{headers:{'X-Requested-With':'fetch'},signal:steuerung.signal});
        const daten=await antwort.json().catch(()=>({}));
        if(!antwort.ok)throw new Error(daten.error||'Die Nextcloud ist gerade nicht erreichbar.');
        zeichne(daten);
      }catch(fehler){
        if(fehler.name==='AbortError')return;
        liste.replaceChildren();status.hidden=false;status.textContent=fehler.message;
      }
    }

    function lade(ziel){pfad=ziel;suche.value='';hole('/api/nextcloud/files?path='+encodeURIComponent(ziel));}
    function schliessen(){bereich.hidden=true;oeffnen.setAttribute('aria-expanded','false');}

    oeffnen.addEventListener('click',()=>{
      const offen=bereich.hidden;
      bereich.hidden=!offen;oeffnen.setAttribute('aria-expanded',String(offen));
      if(offen){lade(pfad);suche.focus();}
    });
    neuladen.addEventListener('click',()=>suche.value.trim()?hole('/api/nextcloud/files?q='+encodeURIComponent(suche.value.trim())):lade(pfad));
    suche.addEventListener('input',()=>{
      clearTimeout(tippen);
      const begriff=suche.value.trim();
      tippen=setTimeout(()=>begriff.length>=2?hole('/api/nextcloud/files?q='+encodeURIComponent(begriff)):lade(pfad),250);
    });
    suche.addEventListener('keydown',event=>{if(event.key==='Escape'&&suche.value){event.stopPropagation();suche.value='';lade(pfad);}});
    dialog.addEventListener('close',()=>{schliessen();gewaehlt.textContent='';korb?.replaceChildren();});
  }

  document.querySelectorAll('[data-cloud-picker]').forEach(einrichten);
})();
