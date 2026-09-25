'use strict';
(() => {
  const dialog=document.querySelector('#voice-dialog');if(!dialog)return;
  const start=dialog.querySelector('[data-voice-start]'),stop=dialog.querySelector('[data-voice-stop]'),save=dialog.querySelector('[data-voice-save]');
  const status=dialog.querySelector('[data-voice-status]'),clock=dialog.querySelector('[data-voice-clock]'),preview=dialog.querySelector('audio'),error=dialog.querySelector('[data-voice-error]');
  let recorder,stream,blob,url,timer,started,pending=false,saving=false,recording=false,generation=0;
  const release=()=>{stream?.getTracks().forEach(track=>track.stop());stream=null;clearInterval(timer);};
  const fail=message=>{error.textContent=message;error.hidden=false;};
  function clear(){
    generation++;recording=false;pending=false;
    if(recorder?.state==='recording')recorder.stop();
    release();blob=null;preview.pause();preview.removeAttribute('src');preview.load();preview.hidden=true;
    if(url)URL.revokeObjectURL(url);url=null;save.disabled=true;stop.hidden=true;start.hidden=false;start.disabled=false;
    start.lastChild.textContent=' Aufnahme starten';clock.textContent='00:00';
  }
  function close(){
    if(saving)return;
    if((recording||blob)&&!confirm('Ungespeicherte Aufnahme verwerfen?'))return;
    clear();dialog.close();
  }
  document.querySelector('[data-voice-open]').addEventListener('click',()=>{
    clear();error.hidden=true;status.textContent='Bereit zur Aufnahme.';dialog.showModal();
    if(!navigator.mediaDevices?.getUserMedia||!window.MediaRecorder){fail('Dieser Browser unterstützt keine Mikrofonaufnahme. Bitte einen aktuellen Browser über HTTPS verwenden.');start.disabled=true;}
  });
  dialog.querySelectorAll('[data-voice-close]').forEach(button=>button.addEventListener('click',close));
  dialog.addEventListener('cancel',event=>{event.preventDefault();close();});
  start.addEventListener('click',async()=>{
    if(blob&&!confirm('Die bisherige Aufnahme durch eine neue ersetzen?'))return;
    clear();const version=generation;pending=true;start.disabled=true;error.hidden=true;status.textContent='Mikrofon wird angefragt …';
    try{
      const acquired=await navigator.mediaDevices.getUserMedia({audio:true});
      if(version!==generation||!dialog.open){acquired.getTracks().forEach(track=>track.stop());return;}
      stream=acquired;
      const mime=['audio/webm;codecs=opus','audio/ogg;codecs=opus','audio/mp4'].find(type=>MediaRecorder.isTypeSupported(type));
      if(!mime)throw Error('format');
      recorder=new MediaRecorder(stream,{mimeType:mime});const chunks=[];let bytes=0;
      recorder.ondataavailable=event=>{if(event.data.size){chunks.push(event.data);bytes+=event.data.size;if(bytes>24*1024*1024&&recorder.state==='recording')recorder.stop();}};
      recorder.onstop=()=>{
        if(version!==generation)return;
        recording=false;release();blob=new Blob(chunks,{type:mime.split(';')[0]});
        start.disabled=false;start.hidden=false;stop.hidden=true;start.lastChild.textContent=' Neu aufnehmen';
        if(!blob.size){blob=null;fail('Keine Audiodaten aufgenommen. Bitte erneut versuchen.');return;}
        url=URL.createObjectURL(blob);preview.src=url;preview.hidden=false;save.disabled=false;
        status.textContent='Aufnahme fertig. Anhören oder im Tagesjournal speichern.';
      };
      recorder.onerror=()=>{if(version===generation){clear();fail('Die Aufnahme wurde unterbrochen. Bitte erneut versuchen.');}};
      recorder.start(1000);pending=false;recording=true;started=Date.now();start.hidden=true;stop.hidden=false;
      status.textContent='Aufnahme läuft …';stop.focus();
      timer=setInterval(()=>{const seconds=Math.floor((Date.now()-started)/1000);clock.textContent=String(Math.floor(seconds/60)).padStart(2,'0')+':'+String(seconds%60).padStart(2,'0');if(seconds>=600&&recorder.state==='recording')recorder.stop();},250);
    }catch(e){if(version!==generation)return;clear();status.textContent='Keine Aufnahme gestartet.';fail(e.name==='NotAllowedError'?'Der Mikrofonzugriff wurde nicht erlaubt. Bitte in den Browsereinstellungen freigeben.':e.name==='NotFoundError'?'Kein Mikrofon gefunden.':'Die Aufnahme konnte nicht gestartet werden. Bitte Mikrofon und Browser prüfen.');}
  });
  stop.addEventListener('click',()=>{if(recorder?.state==='recording'){stop.disabled=true;recorder.stop();stop.disabled=false;}});
  save.addEventListener('click',async()=>{
    if(!blob||saving)return;saving=true;save.disabled=true;start.disabled=true;error.hidden=true;status.textContent='Aufnahme wird gespeichert …';
    try{
      const data=new FormData();data.append('audio',blob,'Sprachi');
      const response=await fetch('/voice/save',{method:'POST',body:data,headers:{'X-CSRF-Token':document.querySelector('meta[name=csrf-token]').content,'X-Requested-With':'fetch'}});
      if(response.redirected)throw Error('Die Sitzung ist abgelaufen. Bitte in einem anderen Tab anmelden und erneut speichern.');
      const result=await response.json().catch(()=>({}));if(!response.ok)throw Error(result.error||'Speichern fehlgeschlagen. Die Aufnahme bleibt zum erneuten Versuch erhalten.');
      saving=false;clear();dialog.close();location.assign(result.redirect);
    }catch(e){saving=false;save.disabled=false;start.disabled=false;status.textContent='Aufnahme noch nicht gespeichert.';fail(e.message);}
  });
  addEventListener('beforeunload',event=>{if(recording||pending||blob||saving){event.preventDefault();event.returnValue='';}});
  addEventListener('pagehide',release);
})();
