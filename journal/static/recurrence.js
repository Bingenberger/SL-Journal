'use strict';
(() => {
  const months=['Januar','Februar','März','April','Mai','Juni','Juli','August','September','Oktober','November','Dezember'];
  function dateRow(control,value=''){
    const row=document.createElement('div');row.className='date-row';
    const label=document.createElement('label');label.textContent='Fälligkeitstermin';
    const input=document.createElement('input');input.type='date';input.value=value;input.dataset.repeatDate='';
    const remove=document.createElement('button');remove.type='button';remove.className='text-button';remove.textContent='Entfernen';
    remove.setAttribute('aria-label','Fälligkeitstermin entfernen');
    label.append(input);row.append(label,remove);control.querySelector('[data-date-rows]').append(row);
    input.addEventListener('input',()=>syncDates(control));
    remove.addEventListener('click',()=>{row.remove();if(!control.querySelector('[data-repeat-date]'))dateRow(control);syncDates(control);control.querySelector('[data-add-date]').focus();});
    return input;
  }
  function syncDates(control){
    control.querySelector('[name=repeat_dates]').value=[...control.querySelectorAll('[data-repeat-date]')].map(el=>el.value).filter(Boolean).join('\n');
    preview(control.closest('form'));
  }
  function loadDates(control){
    control.querySelector('[data-date-rows]').replaceChildren();
    const values=control.querySelector('[name=repeat_dates]').value.trim().split(/[\s,;]+/).filter(Boolean);
    (values.length?values:['']).forEach(value=>dateRow(control,value));
  }
  function preview(form){
    const control=form.querySelector('[data-recurrence-controls]');if(!control)return;
    const frequency=control.querySelector('[data-repeat-frequency]').value;
    control.querySelector('[data-repeat-options]').hidden=!frequency;
    control.querySelector('[data-repeat-dates]').hidden=frequency!=='dates';
    control.querySelector('[data-repeat-interval]').hidden=!['weekly','monthly'].includes(frequency);
    control.querySelector('[data-repeat-unit]').textContent=frequency==='weekly'?'Wochen':'Monate';
    control.querySelector('[data-repeat-pattern]').hidden=frequency==='dates';
    const linked=form.closest('#task-dialog')&&form.querySelector('[data-task-series-note]')&&!form.querySelector('[data-task-series-note]').hidden;
    const due=form.elements.namedItem('due');
    if(due){due.required=Boolean(frequency)&&frequency!=='dates'&&!linked;due.disabled=frequency==='dates'&&!linked;}
    const text=form.elements.namedItem('text')?.value||'';
    const dates=control.querySelector('[name=repeat_dates]').value.trim().split(/[\s,;]+/).filter(Boolean).sort();
    const dateText=frequency==='dates'?dates[0]:due?.value;
    const result=control.querySelector('[data-repeat-preview]');
    if(!frequency||!dateText||!text){result.textContent='Vorschau: Titel und ersten Termin eingeben.';return;}
    if(!/^\d{4}-\d{2}-\d{2}$/.test(dateText)){result.textContent='Bitte gültige Termine im Format JJJJ-MM-TT eingeben.';return;}
    const day=new Date(dateText+'T12:00:00Z');
    if(Number.isNaN(day.valueOf())||day.toISOString().slice(0,10)!==dateText){result.textContent='Bitte einen gültigen Termin eingeben.';return;}
    const thursday=new Date(day);thursday.setUTCDate(day.getUTCDate()+4-(day.getUTCDay()||7));
    const isoYear=thursday.getUTCFullYear();
    const week=Math.ceil((((thursday-Date.UTC(isoYear,0,1))/86400000)+1)/7);
    const values={KW:String(week).padStart(2,'0'),KW_JAHR:String(isoYear),JAHR:String(day.getUTCFullYear()),MONAT:String(day.getUTCMonth()+1).padStart(2,'0'),MONATSNAME:months[day.getUTCMonth()],QUARTAL:String(Math.floor(day.getUTCMonth()/3)+1),DATUM:dateText.split('-').reverse().join('.')};
    const title=text.replace(/\{([A-Z_]+)\}/g,(match,key)=>values[key]??match);
    result.textContent='Vorschau: '+title+' · '+values.DATUM;
  }
  window.JournalRecurrence={refresh(form,data={}){
    const control=form.querySelector('[data-recurrence-controls]');
    if(control)loadDates(control);
    const section=form.querySelector('[data-task-repeat-section]');
    if(section){
      section.hidden=Boolean(data.parent_id||data.series||data.done);
      section.querySelectorAll('input,select,textarea').forEach(el=>el.disabled=section.hidden);
      const note=form.querySelector('[data-task-series-note]');note.hidden=!data.series;
      if(data.series)note.querySelector('a').href='/task-series/'+data.series.id;
      if(data.repeat_frequency)section.open=true;
    }
    preview(form);
  }};
  document.addEventListener('input',event=>{if(event.target.form)preview(event.target.form);});
  document.addEventListener('change',event=>{if(event.target.form)preview(event.target.form);});
  document.querySelectorAll('[data-recurrence-controls]').forEach(control=>{
    loadDates(control);
    control.querySelector('[data-add-date]').addEventListener('click',()=>dateRow(control).focus());
    control.querySelector('[name=repeat_dates]').addEventListener('input',()=>loadDates(control));
    preview(control.closest('form'));
  });
})();
