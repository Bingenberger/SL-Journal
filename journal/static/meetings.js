'use strict';
(() => {
  const dialog=document.querySelector('#meeting-dialog');if(!dialog)return;
  const form=dialog.querySelector('form'),status=form.querySelector('[data-meeting-status]'),sync=form.querySelector('[data-meeting-sync]');
  let generation=0;
  async function refresh(){
    if(sync.disabled)return;
    const current=generation;
    sync.disabled=true;status.textContent='Kalender wird geladen …';
    const data=new FormData();data.set('csrf_token',csrf);data.set('start_date',form.elements.start_date.value);
    try{
      const response=await fetch('/appointments/sync',{method:'POST',body:data,headers:{'X-Requested-With':'fetch'}});
      if(response.redirected)throw Error('Bitte erneut anmelden.');
      const result=await response.json();if(!response.ok)throw Error(result.error||'Kalender konnte nicht geladen werden.');
      if(current!==generation||!dialog.open)return;
      status.textContent='Kalender aktualisiert. Wählen Sie jetzt den Termin.';
      form.querySelector('.ac-input').focus();
    }catch(error){if(current===generation)status.textContent=error.message;}finally{sync.disabled=false;}
  }
  sync.addEventListener('click',refresh);
  document.addEventListener('click',async event=>{
    const button=event.target.closest('[data-plan-meeting]');if(!button)return;
    const current=++generation;
    if(button.dataset.eventId){
      const select=form.elements.event_id;
      if(![...select.options].some(o=>o.value===button.dataset.eventId))select.add(new Option(button.dataset.eventLabel,button.dataset.eventId));
    }
    openDialog('meeting-dialog',{text:button.dataset.text||'',source_entry_id:button.dataset.sourceEntryId||'',attachment_id:button.dataset.attachmentId||'',document_id:button.dataset.meetingDocumentId||'',event_id:button.dataset.eventId||'',start_date:today,request_key:crypto.randomUUID()});
    form.querySelector('[data-meeting-source]').textContent=button.dataset.sourceLabel?'Bezug: '+button.dataset.sourceLabel:'';
    status.textContent='Gespeicherte Nextcloud-Termine. Aktualisieren lädt 90 Tage ab dem gewählten Datum.';
    try{
      const response=await fetch('/api/autocomplete/appointments');if(!response.ok||response.redirected)return;
      const result=await response.json();
      if(current!==generation||!dialog.open)return;
      if(!result.loaded&&result.configured)refresh();
      else if(!result.configured)status.textContent='Bitte verbinden Sie den Nextcloud-Kalender unter Einstellungen.';
    }catch{status.textContent='Termine konnten nicht geprüft werden. Bitte Kalender aktualisieren.';}
  });
  dialog.addEventListener('close',()=>generation++);
})();
