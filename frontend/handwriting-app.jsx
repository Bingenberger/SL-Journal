import React from 'react';
import {createRoot} from 'react-dom/client';
import {Excalidraw, MainMenu, serializeAsJSON, exportToBlob, getSceneVersion} from '@excalidraw/excalidraw';

const boot=JSON.parse(document.getElementById('sheet-data').textContent);
const title=document.getElementById('sheet-title');
const date=document.getElementById('sheet-date');
const status=document.getElementById('sheet-status');
const saveButton=document.getElementById('sheet-save');
const back=document.getElementById('sheet-back');
const download=document.getElementById('sheet-download');
let api, timer, pending, ready=false, savedSignature, conflict=false;
const allowed=new Set(['freedraw','line','arrow','rectangle','diamond','ellipse','text','frame']);
function signature(elements,state){
  return JSON.stringify([getSceneVersion(elements),title.value,date.value,state.viewBackgroundColor]);
}
function currentSignature(){return api ? signature(api.getSceneElementsIncludingDeleted(),api.getAppState()) : '';}
function dirty(){return ready && currentSignature()!==savedSignature;}
function message(text,error=false){
  status.textContent=text;
  if(error)status.dataset.error='true';else delete status.dataset.error;
}
function changed(elements,state){
  if(!ready)return;
  clearTimeout(timer);
  if(signature(elements,state)!==savedSignature){
    if(!conflict)message('Änderungen noch nicht gespeichert …');
    if(!conflict)timer=setTimeout(()=>save(),1500);
  }else if(!pending&&!conflict){message(boot.id?'Gespeichert':'Bereit zum Schreiben');}
}
function sceneJSON(){
  return serializeAsJSON(api.getSceneElementsIncludingDeleted(),api.getAppState(),{},'local');
}
async function snapshotPreview(scene){
  const elements=scene.elements.filter(e=>!e.isDeleted);
  if(!elements.length){
    const canvas=document.createElement('canvas');canvas.width=100;canvas.height=100;
    const ctx=canvas.getContext('2d');ctx.fillStyle='#fff';ctx.fillRect(0,0,100,100);
    return new Promise(resolve=>canvas.toBlob(resolve,'image/png'));
  }
  return exportToBlob({elements,appState:{...scene.appState,exportBackground:true,exportWithDarkMode:false},files:{},maxWidthOrHeight:1400,mimeType:'image/png'});
}
async function save(){
  clearTimeout(timer);
  if(pending){await pending;return dirty()&&!conflict?save():!dirty();}
  if(!ready||!dirty())return true;
  if(conflict)return false;
  if(!title.value.trim()||!date.value){message('Bitte Blatttitel und Datum eingeben.',true);return false;}
  const captured=currentSignature();
  const capturedTitle=title.value.trim(),capturedDate=date.value;
  const raw=sceneJSON();
  const scene=JSON.parse(raw);
  if(scene.elements.some(e=>!allowed.has(e.type))){
    message('Bitte nur Stiftstriche, Text und Formen verwenden. Dateien können Sie am Eintrag anhängen.',true);return false;
  }
  saveButton.disabled=true;
  message('Wird gespeichert …');
  pending=(async()=>{
    try{
      const preview=await snapshotPreview(scene);
      const form=new FormData();
      form.set('scene',raw);form.set('preview',preview,'preview.png');
      form.set('title',capturedTitle);form.set('date',capturedDate);
      form.set('client_key',boot.client_key);form.set('revision',boot.revision);
      if(boot.entry_id)form.set('entry_id',boot.entry_id);
      const controller=new AbortController();
      const timeout=setTimeout(()=>controller.abort(),20000);
      let response;
      try{
        response=await fetch(boot.save,{method:'POST',body:form,signal:controller.signal,
          headers:{'X-CSRF-Token':document.querySelector('meta[name=csrf-token]').content,'X-Requested-With':'fetch'}});
      }finally{clearTimeout(timeout);}
      const result=await response.json().catch(()=>({error:'Die Sitzung oder Verbindung ist unterbrochen. Bitte die Zeichnung herunterladen und erneut anmelden.'}));
      if(!response.ok||!result.id){if(response.status===409)conflict=true;throw new Error(result.error||'Speichern fehlgeschlagen.');}
      Object.assign(boot,result);
      history.replaceState(null,'',result.edit);
      back.href=result.back;back.textContent='Zum Eintrag';
      document.getElementById('sheet-date-label').hidden=true;
      savedSignature=captured;
      message(dirty()?'Weitere Änderungen werden gespeichert …':'Gespeichert');
      if(dirty())timer=setTimeout(()=>save(),500);
      return true;
    }catch(error){
      message(error.name==='AbortError'?'Speichern dauert zu lange. Die Zeichnung bleibt hier geöffnet. Bitte erneut speichern.':error.message,true);
      return false;
    }finally{pending=null;saveButton.disabled=false;}
  })();
  return pending;
}
function downloadScene(){
  if(!api)return;
  const url=URL.createObjectURL(new Blob([sceneJSON()],{type:'application/json'}));
  const link=document.createElement('a');link.href=url;link.download=(title.value.trim()||'Handschrift')+'.excalidraw';link.click();
  setTimeout(()=>URL.revokeObjectURL(url),1000);
}
saveButton.addEventListener('click',()=>save());
download.addEventListener('click',downloadScene);
for(const input of [title,date])input.addEventListener('input',()=>{if(api)changed(api.getSceneElementsIncludingDeleted(),api.getAppState());});
back.addEventListener('click',async e=>{e.preventDefault();if(await save())location.assign(back.href);});
window.addEventListener('beforeunload',e=>{if(dirty()||pending){e.preventDefault();e.returnValue='';}});
document.addEventListener('visibilitychange',()=>{if(document.visibilityState==='hidden')save();});
document.addEventListener('keydown',e=>{if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==='s'){e.preventDefault();save();}},true);
const initial=boot.scene||{elements:[],appState:{}};
initial.appState={...initial.appState,activeTool:{type:'freedraw',locked:false},currentItemStrokeWidth:1,currentItemRoughness:0};
initial.scrollToContent=true;
createRoot(document.getElementById('drawing-root')).render(
  <Excalidraw langCode="de-DE" initialData={initial} theme="light"
    excalidrawAPI={value=>{
      api=value;
      // Wait for initialData restoration before marking subsequent edits dirty.
      setTimeout(()=>{
        savedSignature=currentSignature();ready=true;
        saveButton.disabled=false;download.disabled=false;
        message(boot.id?'Gespeichert':'Bereit zum Schreiben · Speicherung nach dem ersten Strich');
      },100);
    }}
    onChange={changed} validateEmbeddable={()=>false}
    UIOptions={{tools:{image:false},canvasActions:{loadScene:false,saveToActiveFile:false,export:false,saveAsImage:false,toggleTheme:false}}}
  >
    <MainMenu>
      <MainMenu.Item onSelect={downloadScene}>Zeichnung herunterladen</MainMenu.Item>
      <MainMenu.DefaultItems.ClearCanvas />
      <MainMenu.DefaultItems.ChangeCanvasBackground />
    </MainMenu>
  </Excalidraw>
);
