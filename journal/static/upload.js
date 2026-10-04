'use strict';
(() => {
  const box=document.querySelector('.quick-upload');
  if(!box)return;
  const drop=document.querySelector('#upload-drop'),picker=document.querySelector('#upload-files');
  const dialog=document.querySelector('#upload-dialog'),form=dialog.querySelector('form');
  const status=document.querySelector('#upload-status'),progress=document.querySelector('#upload-progress'),result=document.querySelector('#upload-result');
  const error=form.querySelector('.form-error');
  // Eigenes Datum statt der Konstante aus app.js: Die hielte nur, solange die
  // Skripte in dieser Reihenfolge geladen werden.
  const heute=new Date().toLocaleDateString('en-CA',{timeZone:'Europe/Berlin'});
  let files=[],busy=false,key='',direct=false;
  function mode(){
    const existing=direct||form.elements.mode.value==='existing';
    for(const [selector,disabled] of [['[data-upload-new]',existing],['[data-upload-existing]',!existing]]){
      const field=form.querySelector(selector);field.hidden=disabled;field.disabled=disabled;
    }
    form.querySelector('[data-upload-mode]').hidden=direct;
    if(direct)form.querySelector('[data-upload-existing]').hidden=true;
  }
  function close(){
    if(busy)return;
    if(files.length&&!confirm('Ausgewählte Dateien und Eingaben verwerfen?'))return;
    files=[];window.JournalUI?.saved(form);dialog.close();
  }
  form.querySelectorAll('[data-upload-close]').forEach(button=>button.addEventListener('click',close));
  dialog.addEventListener('cancel',event=>{event.preventDefault();event.stopImmediatePropagation();close();},true);
  form.addEventListener('change',event=>{if(event.target.name==='mode')mode();});
  function choose(chosen){
    if(busy||!chosen.length)return;
    if(files.length){status.textContent='Bitte zuerst die ausgewählten Dateien speichern oder verwerfen.';dialog.showModal();return;}
    if(chosen.length>25||chosen.reduce((sum,file)=>sum+file.size,0)>25*1024*1024){status.textContent='Bitte höchstens 25 Dateien mit zusammen maximal 25 MB auswählen.';return;}
    files=chosen;key=crypto.randomUUID();direct=Boolean(box.dataset.entry);
    form.reset();error.hidden=true;result.hidden=true;
    form.elements.title.value=files.length===1?files[0].name:'Dateien · '+new Date().toLocaleDateString('de-DE');
    form.elements.date.value=new URL(location.href).searchParams.get('date')||heute;
    for(const [name,id] of [['projects',box.dataset.project],['cases',box.dataset.case]]){
      [...form.elements[name].options].forEach(option=>option.selected=Boolean(id)&&option.value===id);
    }
    window.JournalAutocomplete?.refresh(form,{});
    form.querySelector('[data-upload-list]').textContent=files.map(f=>f.name).join(', ');
    mode();window.JournalUI?.opened(form);
    if(direct)send();else{dialog.showModal();form.elements.title.focus();}
  }
  drop.addEventListener('click',()=>{if(files.length){if(!dialog.open)dialog.showModal();}else picker.click();});
  picker.addEventListener('change',()=>{choose([...picker.files]);picker.value='';});
  let depth=0;
  const isFiles=event=>[...(event.dataTransfer?.types||[])].includes('Files');
  document.addEventListener('dragenter',event=>{if(isFiles(event)){depth++;box.classList.add('dragging');}});
  document.addEventListener('dragleave',()=>{if(--depth<=0){depth=0;box.classList.remove('dragging');}});
  document.addEventListener('dragover',event=>{if(isFiles(event)){event.preventDefault();event.dataTransfer.dropEffect=busy?'none':'copy';}});
  document.addEventListener('drop',event=>{
    if(!isFiles(event))return;
    event.preventDefault();depth=0;box.classList.remove('dragging');
    if(!box.contains(event.target)){status.textContent='Dateien bitte auf dem Upload-Feld unten rechts ablegen.';return;}
    const items=[...event.dataTransfer.items];
    if(items.some(item=>item.webkitGetAsEntry?.()?.isDirectory)){status.textContent='Bitte einzelne Dateien statt Ordner auswählen.';return;}
    choose([...event.dataTransfer.files]);
  });
  form.addEventListener('submit',event=>{event.preventDefault();send();});
  async function send(){
    if(busy||!files.length)return;
    const data=new FormData(form);
    if(direct){data.set('mode','existing');data.set('target_id',box.dataset.entry);}
    if(data.get('mode')==='existing'&&!data.get('target_id')){error.textContent='Bitte einen Eintrag aus den Vorschlägen auswählen.';error.hidden=false;return;}
    files.forEach(file=>data.append('attachments',file));data.set('request_key',key);
    busy=true;drop.disabled=true;form.querySelectorAll('button').forEach(b=>b.disabled=true);
    progress.hidden=false;progress.value=0;status.textContent='Dateien werden hochgeladen …';error.hidden=true;
    try{
      const answer=await new Promise((resolve,reject)=>{
        const xhr=new XMLHttpRequest();xhr.open('POST',form.action);xhr.timeout=180000;
        xhr.setRequestHeader('X-Requested-With','fetch');
        xhr.upload.onprogress=event=>{if(event.lengthComputable){progress.value=Math.round(event.loaded/event.total*100);status.textContent=progress.value===100?'Upload abgeschlossen, Dateien werden gespeichert …':`Upload: ${progress.value} %`;}};
        xhr.onload=()=>{let response;try{response=JSON.parse(xhr.responseText);}catch{reject(new Error('Upload nicht bestätigt. Bitte Anmeldung prüfen und erneut versuchen.'));return;}if(xhr.status>=200&&xhr.status<300&&response.ok)resolve(response);else reject(new Error(response.error||'Upload fehlgeschlagen.'));};
        xhr.onerror=xhr.ontimeout=()=>reject(new Error('Verbindung unterbrochen. Die Dateien bleiben für einen erneuten Versuch ausgewählt.'));
        xhr.send(data);
      });
      files=[];window.JournalUI?.saved(form);dialog.close();
      status.textContent='Dateien gespeichert. Die Volltextsuche wird im Hintergrund vorbereitet.';
      result.href=answer.url;result.hidden=false;
      if(direct){
        try{
          const response=await fetch(answer.url);if(!response.ok)throw new Error();
          const html=new DOMParser().parseFromString(await response.text(),'text/html');
          const updated=html.querySelector('#upload-attachments'),current=document.querySelector('#upload-attachments');
          if(updated&&current)current.replaceWith(updated);
        }catch{status.textContent+=' Zum Anzeigen der Anhänge den Eintrag erneut öffnen.';}
      }
    }catch(exc){
      error.textContent=exc.message;error.hidden=false;status.textContent=exc.message;
      if(!dialog.open)dialog.showModal();
    }finally{busy=false;drop.disabled=false;progress.hidden=true;form.querySelectorAll('button').forEach(b=>b.disabled=false);}
  }
  window.addEventListener('beforeunload',event=>{if(files.length||busy){event.preventDefault();event.returnValue='';}});
})();
