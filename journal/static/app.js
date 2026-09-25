'use strict';
const csrf = document.querySelector('meta[name="csrf-token"]').content;
const today = new Date().toLocaleDateString('en-CA', {timeZone:'Europe/Berlin'});
const currentDay = new URL(location.href).searchParams.get('date') || today;
const toast = message => { const el=document.querySelector('#toast'); el.textContent=message; el.hidden=false; setTimeout(()=>el.hidden=true,5000); };
function openDialog(id, data={}) {
  const dialog=document.getElementById(id);
  if (!dialog) return;
  const form=dialog.querySelector('form');
  form.reset();
  form.querySelectorAll('[data-task-repeater]').forEach(group=>{
    const rows=[...group.querySelectorAll('[data-task-draft]')];
    rows.slice(1).forEach(row=>row.remove());
    rows[0]?.querySelectorAll('input').forEach(input=>input.value='');
  });
  form.querySelectorAll('details').forEach(details=>details.open=false);
  form.querySelectorAll('input[type=hidden]:not([name=csrf_token])').forEach(el=>el.value='');
  if(form.elements.namedItem('date')) form.elements.namedItem('date').value=currentDay;
  if(form.elements.namedItem('time')) form.elements.namedItem('time').value=new Intl.DateTimeFormat('de-DE',{hour:'2-digit',minute:'2-digit',timeZone:'Europe/Berlin'}).format(new Date());
  for(const [key,value] of Object.entries(data)) {
    const el=form.elements.namedItem(key);
    if(!el || el.type==='file') continue;
    if(el instanceof HTMLSelectElement && el.multiple) {const values=(value||[]).map(v=>String(v.id ?? v)); [...el.options].forEach(o=>o.selected=values.includes(o.value));}
    else el.value=value ?? '';
  }
  form.querySelectorAll('.form-error').forEach(e=>e.hidden=true);
  if(id==='entry-dialog') {
    document.getElementById('entry-dialog-title').textContent=data.id?'Eintrag bearbeiten':'Neuer Eintrag';
    updateMailFields(form);
    form.querySelector('[data-entry-attachments]').hidden=Boolean(data.type==='note' && data.drawings?.length);
    form.querySelector('[data-entry-attachments]').closest('details').hidden=Boolean(data.type==='note' && data.drawings?.length);
    form.querySelector('[data-chosen-documents]')?.replaceChildren();
    form.querySelectorAll('[data-cloud-chosen]').forEach(el=>el.textContent='');
  }
  if(id==='document-dialog') {
    form.querySelector('h2').textContent=data.id?'Dokumentverweis bearbeiten':'Nextcloud-Dokument verknüpfen';
    form.querySelector('[data-document-edit-help]').hidden=!data.id;
    form.querySelector('[data-document-new-help]').hidden=Boolean(data.id);
  }
  if(id==='task-dialog') {
    const child=Boolean(data.parent_id);
    form.querySelector('[data-task-heading]').textContent=data.id?(child?'Unteraufgabe bearbeiten':'Aufgabe bearbeiten'):(child?'Neue Unteraufgabe':'Neue Aufgabe');
    form.querySelector('[data-subtask-section]').hidden=child;
    const caption=form.querySelector('[data-parent-caption]');
    caption.hidden=!child;
    caption.textContent=child?'Unteraufgabe von: '+(data.parent_text||'Hauptaufgabe'):'';
  }
  const titles={'person-dialog':['Neuer Kontakt','Kontakt bearbeiten'],'project-dialog':['Neues Projekt','Projekt bearbeiten'],'case-dialog':['Neuer Vorgang','Vorgang bearbeiten'],'process-dialog':['Neuer Jahresprozess','Jahresprozess bearbeiten']};
  if(titles[id])form.querySelector('h2').textContent=titles[id][data.id?1:0];
  window.JournalRecurrence?.refresh(form,data);
  window.JournalAutocomplete?.refresh(form, data);
  window.JournalMarkdown?.refresh(form);
  window.JournalUI?.opened(form);
  dialog.showModal();
  const focus=(id==='document-dialog'?form.querySelector('input[type=url]'):null)||form.querySelector('input[name=title]')||form.querySelector('textarea[name=text]')||form.querySelector('input[name=name]')||form.querySelector('input:not([type=hidden])');
  if(focus) focus.focus();
}
function updateMailFields(form){form.querySelectorAll('.protocol-fields').forEach(field=>field.hidden=form.elements.type.value!=='protocol');const box=form.querySelector('.mail-fields');if(box) box.hidden=!form.elements.type.value.startsWith('mail_');}
document.addEventListener('click',async event=>{
  const button=event.target.closest('button,a');
  if(!button) return;
  try {
    if(button.dataset.editSeries) {
      const series=JSON.parse(button.dataset.editSeries);
      openDialog('series-dialog',{text:series.template,due:series.start_date,repeat_frequency:series.frequency,repeat_interval:series.interval,repeat_until:series.until_date,repeat_dates:JSON.parse(series.dates).join('\n')});
      document.querySelector('#series-dialog form').action='/task-series/'+series.id+'/save';return;
    }
    if(button.hasAttribute('data-new-document')) {
      openDialog('document-dialog',{owner:button.dataset.owner,owner_id:button.dataset.ownerId});
      return;
    }
    if(button.dataset.editDocument) {
      openDialog('document-dialog',JSON.parse(button.dataset.editDocument));
      return;
    }
    if(button.hasAttribute('data-add-task')) {
      const group=button.closest('[data-task-repeater]');
      if(group.querySelectorAll('[data-task-draft]').length>=100) {toast('Maximal 100 Aufgaben pro Speichervorgang.');return;}
      const row=group.querySelector('[data-task-draft]').cloneNode(true);
      row.querySelectorAll('input').forEach(input=>input.value='');
      group.querySelector('[data-task-rows]').append(row);
      row.querySelector('input').focus();
      return;
    }
    if(button.hasAttribute('data-remove-task')) {
      const group=button.closest('[data-task-repeater]');
      const row=button.closest('[data-task-draft]');
      if(group.querySelectorAll('[data-task-draft]').length>1) row.remove();
      else row.querySelectorAll('input').forEach(input=>input.value='');
      return;
    }
    if(button.dataset.newSubtask) {
      const parent=JSON.parse(button.dataset.newSubtask);
      openDialog('task-dialog',{parent_id:parent.id,parent_text:parent.text,entry_id:parent.entry_id||'',project_items:parent.project_items||[],case_items:parent.case_items||[],case_id:parent.case_id||''});
      return;
    }
    if(button.dataset.newCaseSuggestion) {
      const proposal=JSON.parse(button.dataset.newCaseSuggestion);
      openDialog('case-dialog',{suggestion_id:proposal.id,title:proposal.name,status:'open'});return;
    }
    if(button.dataset.linkCaseSuggestion) {
      const proposal=JSON.parse(button.dataset.linkCaseSuggestion);
      openDialog('case-suggestion-link-dialog');
      const dialog=document.getElementById('case-suggestion-link-dialog');
      dialog.querySelector('form').action='/case-suggestion/'+proposal.id+'/resolve';
      dialog.querySelector('.suggestion-name').textContent=proposal.name;
      dialog.querySelector('.ac-input').focus();return;
    }
    if(button.dataset.newProjectSuggestion) {
      const suggestion=JSON.parse(button.dataset.newProjectSuggestion);
      openDialog('project-dialog',{suggestion_id:suggestion.id,name:suggestion.name,school_year:suggestion.school_year});
      return;
    }
    if(button.dataset.linkProjectSuggestion) {
      const suggestion=JSON.parse(button.dataset.linkProjectSuggestion);
      openDialog('project-suggestion-link-dialog');
      const dialog=document.getElementById('project-suggestion-link-dialog');
      dialog.querySelector('form').action='/project-suggestion/'+suggestion.id+'/link';
      dialog.querySelector('.suggestion-name').textContent=suggestion.name;
      dialog.querySelector('.ac-input').focus();
      return;
    }
    if(button.dataset.newContactSuggestion) {
      const suggestion=JSON.parse(button.dataset.newContactSuggestion);
      openDialog('person-dialog',{suggestion_id:suggestion.id,name:suggestion.contact_name,emails:suggestion.email});
      return;
    }
    if(button.dataset.linkSuggestion) {
      const suggestion=JSON.parse(button.dataset.linkSuggestion);
      openDialog('suggestion-link-dialog');
      const dialog=document.getElementById('suggestion-link-dialog');
      dialog.querySelector('form').action='/suggestion/'+suggestion.id+'/link';
      dialog.querySelector('.suggestion-name').textContent=suggestion.name;
      dialog.querySelector('.ac-input').focus();
      return;
    }
    if(button.hasAttribute('data-close')) {window.JournalUI?.close(button.closest('dialog'));return;}
    if(button.dataset.dialog) {openDialog(button.dataset.dialog);return;}
    if(button.hasAttribute('data-new-entry')) {
      openDialog('entry-dialog',{type:button.dataset.type||'note',title:button.dataset.title||'',date:button.dataset.date||currentDay,...(button.dataset.time!==undefined?{time:button.dataset.time}:{}),projects:button.dataset.projectId?[button.dataset.projectId]:[],cases:button.dataset.caseId?[button.dataset.caseId]:[]});return;
    }
    if(button.dataset.editEntry) {
      const response=await fetch('/api/entry/'+button.dataset.editEntry);
      if(!response.ok || response.redirected) throw Error('Eintrag konnte nicht geladen werden. Bitte neu anmelden.');
      openDialog('entry-dialog',await response.json());return;
    }
    if(button.hasAttribute('data-new-task')) {
      const selection=button.hasAttribute('data-selection')?window.getSelection().toString().trim():'';
      openDialog('task-dialog',{repeat_frequency:button.dataset.repeat||'',text:selection||button.dataset.text||'',entry_id:button.dataset.entryId||'',project_id:button.dataset.projectId||'',case_id:button.dataset.caseId||'',due:button.dataset.due||''});return;
    }
    if(button.dataset.editTask) {openDialog('task-dialog',JSON.parse(button.dataset.editTask));return;}
    for(const type of ['project','person','process','case']) {
      const key='edit'+type[0].toUpperCase()+type.slice(1);
      if(button.dataset[key]) {const data=JSON.parse(button.dataset[key]);if(type==='process') data.todos=(data.tasks||[]).join('\n');openDialog(type+'-dialog',data);return;}
    }
    if(button.id==='setup-qr') {
      const form=document.getElementById('setup-form');
      const data=new FormData();data.append('csrf_token',csrf);data.append('setup_code',form.elements.setup_code.value);
      button.disabled=true;
      const response=await fetch('/setup/qr',{method:'POST',body:data});
      if(!response.ok) throw Error('Einrichtungscode ungültig oder Anmeldung vorübergehend gesperrt.');
      const result=await response.json();document.getElementById('qr-image').src=result.image;document.getElementById('totp-secret').textContent=result.secret;document.getElementById('qr-area').hidden=false;
    }
  } catch(error) {toast(error.message);} finally {if(button.id==='setup-qr')button.disabled=false;}
});
document.addEventListener('change',event=>{
  if(event.target.matches('[data-auto-submit]')) event.target.form.requestSubmit();
  if(event.target.matches('#entry-dialog select[name=type]')) updateMailFields(event.target.form);
});
document.addEventListener('submit',async event=>{
  const form=event.target;
  if(form.dataset.confirm && !confirm(form.dataset.confirm)) {event.preventDefault();return;}
  if(!form.hasAttribute('data-async')) return;
  event.preventDefault();
  if(form.dataset.busy==='1') return;
  const data=new FormData(form);
  if(event.submitter?.name)data.set(event.submitter.name,event.submitter.value);
  let bytes=0;
  for(const value of data.values()) if(value instanceof File) bytes+=value.size;
  if(bytes>25*1024*1024) {toast('Die Dateien dürfen zusammen höchstens 25 MB groß sein.');return;}
  // Empty options mean no association, never a foreign key with an empty string.
  for(const name of ['projects','people']) {const values=data.getAll(name).filter(Boolean);data.delete(name);values.forEach(v=>data.append(name,v));}
  const buttons=[...form.querySelectorAll('button[type=submit],button:not([type])')];
  buttons.forEach(b=>b.disabled=true);form.dataset.busy='1';
  try {
    const response=await fetch(form.action,{method:'POST',body:data,headers:{'X-Requested-With':'fetch'}});
    if(response.redirected) throw Error('Die Sitzung ist abgelaufen. Bitte in einem neuen Tab anmelden; Ihre Eingaben bleiben hier erhalten.');
    if(!response.headers.get('content-type')?.includes('application/json')) throw Error('Speichern fehlgeschlagen. Bitte Sitzung und Dateigröße prüfen.');
    const result=await response.json();
    if(!response.ok) throw Error(result.error||'Die Aktion konnte nicht abgeschlossen werden.');
    window.JournalUI?.saved(form);
    if(!result.redirect || new URL(result.redirect,location.href).href===location.href)sessionStorage.setItem('journal-position',JSON.stringify({url:location.pathname+location.search,y:scrollY}));
    sessionStorage.setItem('journal-message',result.message||'Gespeichert.');
    if(result.redirect) {
      const target=new URL(result.redirect,location.href);
      if(target.origin===location.origin && target.pathname===location.pathname && target.search===location.search) {
        if(target.hash)sessionStorage.setItem('journal-scroll-target',target.hash.slice(1));
        location.reload();
      } else location.assign(target.href);
    } else location.reload();
  } catch(error) {
    const el=form.querySelector('.form-error');if(el){el.textContent=error.message;el.hidden=false;el.scrollIntoView({block:'nearest'});}else toast(error.message);
  } finally {buttons.forEach(b=>b.disabled=false);delete form.dataset.busy;}
});
document.addEventListener('keydown',event=>{
  if(event.target.matches('input,textarea,select') || event.target.isContentEditable || document.querySelector('dialog[open]'))return;
  if(event.ctrlKey||event.metaKey||event.altKey)return;
  if(event.key==='n' && document.getElementById('entry-dialog')){event.preventDefault();openDialog('entry-dialog');}
  if(event.key==='a' && document.getElementById('task-dialog')){event.preventDefault();openDialog('task-dialog');}
  if(event.key==='/'){const input=document.querySelector('.global-search input');if(input){event.preventDefault();input.focus();}}
});
const storedMessage=sessionStorage.getItem('journal-message');if(storedMessage){sessionStorage.removeItem('journal-message');toast(storedMessage);}

const scrollTarget=sessionStorage.getItem('journal-scroll-target');
if(scrollTarget){
  sessionStorage.removeItem('journal-scroll-target');
  document.getElementById(scrollTarget)?.scrollIntoView({block:'start'});
}
