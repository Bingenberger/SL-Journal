'use strict';
(() => {
  const sidebarList=document.querySelector('#sidebar-list');
  if(sidebarList){
    const storageKey='journal-sidebar-list';
    let selected='projects';
    const displayList=()=>{
      document.querySelector('#sidebar-projects').hidden=selected!=='projects';
      document.querySelector('#sidebar-cases').hidden=selected!=='cases';
      sidebarList.querySelectorAll('button').forEach(button=>button.setAttribute('aria-pressed',String(button.dataset.sidebarList===selected)));
    };
    try{if(localStorage.getItem(storageKey)==='cases')selected='cases';}catch{}
    displayList();
    sidebarList.addEventListener('click',event=>{
      const button=event.target.closest('[data-sidebar-list]');
      if(!button)return;
      selected=button.dataset.sidebarList;
      displayList();
      try{localStorage.setItem(storageKey,selected);}catch{}
    });
  }
  const snapshots=new WeakMap();
  function snapshot(form) {
    // Do not construct FormData here: autocomplete uses that event when saving.
    return JSON.stringify([...form.querySelectorAll('input,textarea,select,[contenteditable=true],.ac-tokens')].map(el=>{
      if(el.matches('input[type=hidden]'))return null;
      if(el.matches('[contenteditable=true],.ac-tokens'))return el.textContent;
      if(el.type==='file')return [...el.files].map(f=>[f.name,f.size,f.lastModified]);
      if(el.type==='checkbox'||el.type==='radio')return [el.name,el.checked];
      if(el.multiple)return [...el.selectedOptions].map(o=>o.value);
      return [el.name,el.value];
    }));
  }
  const guarded=form=>form?.matches('dialog form,.journal-panel>form,#settings-form,#entry-classification form');
  const dirty=form=>guarded(form)&&snapshots.has(form)&&snapshots.get(form)!==snapshot(form);
  const baseline=form=>snapshots.set(form,snapshot(form));
  function close(dialog) {
    if(dirty(dialog.querySelector('form'))&&!confirm('Ungespeicherte Änderungen verwerfen? Mit „Abbrechen“ können Sie weiterschreiben.'))return;
    baseline(dialog.querySelector('form'));
    dialog.close();
  }
  window.JournalUI={opened:baseline,saved:baseline,close};
  document.querySelectorAll('dialog').forEach(dialog=>{
    const form=dialog.querySelector('form');
    if(!form)return;
    const footer=form.querySelector('.dialog-footer');
    const heading=form.querySelector('.dialog-heading');
    if(footer){
      const scroll=document.createElement('div');scroll.className='dialog-scroll';
      [...form.childNodes].forEach(node=>{if(node!==footer&&node!==heading)scroll.append(node);});
      if(heading)form.append(heading);
      form.append(scroll,footer);
      dialog.classList.add('structured-dialog');
    }
    dialog.addEventListener('cancel',event=>{event.preventDefault();close(dialog);});
    if(!dialog.hasAttribute('aria-labelledby')){
      const title=dialog.querySelector('h2');
      if(title){title.id ||= dialog.id+'-heading';dialog.setAttribute('aria-labelledby',title.id);}
    }
  });
  // Deferred components (for example recurrence date rows) finish after ui.js.
  // Their initial controls belong to the clean state, not to user edits.
  document.addEventListener('DOMContentLoaded',()=>{
    document.querySelectorAll('form').forEach(form=>{
      if(guarded(form)&&!snapshots.has(form))baseline(form);
    });
  },{once:true});
  // Keep label captions on one line, separate from controls and help text.
  document.querySelectorAll('form label').forEach(label=>{
    if(label.matches('.checkbox-label')||label.querySelector('input[type=checkbox],input[type=radio]'))return;
    const caption=document.createElement('span');caption.className='field-caption';
    for(const node of [...label.childNodes]){
      if(node.nodeType===Node.TEXT_NODE||node.nodeType===Node.ELEMENT_NODE&&node.matches('span.muted:not(.small)'))caption.append(node);
      else break;
    }
    if(caption.textContent.trim())label.prepend(caption);
  });
  document.querySelectorAll('dialog form,#settings-form').forEach(form=>{
    const hint=document.createElement('p');hint.className='small muted form-field-guide';
    hint.textContent=form.id==='settings-form'?'Für eine Verbindung sind Adresse, Benutzername und Zugangsdaten erforderlich; für IMAP zusätzlich eigene Mailadressen.':'* Pflichtfeld. Alle übrigen Angaben sind optional.';
    (form.querySelector('.dialog-scroll')||form).prepend(hint);
  });
  addEventListener('beforeunload',event=>{
    if([...document.forms].some(dirty)){event.preventDefault();event.returnValue='';}
  });
  const nav=document.querySelector('#main-navigation');
  const toggle=document.querySelector('.mobile-nav-toggle');
  if(nav&&toggle){
    const current=nav.querySelector('.active');
    toggle.querySelector('[data-current-section]').textContent=current?.textContent.trim()||document.querySelector('.breadcrumb')?.textContent.split('/').pop().trim()||'Mein Journal';
    toggle.addEventListener('click',()=>{
      const expanded=toggle.getAttribute('aria-expanded')!=='true';
      toggle.setAttribute('aria-expanded',String(expanded));nav.classList.toggle('mobile-open',expanded);
    });
    nav.addEventListener('keydown',event=>{if(event.key==='Escape'){nav.classList.remove('mobile-open');toggle.setAttribute('aria-expanded','false');toggle.focus();}});
  }
  // Rückweg zur vorherigen Ansicht, mit Filtern und Suchbegriffen.
  if(document.referrer){
    const previous=new URL(document.referrer);
    const bekannt=/^\/(?:entries|tasks|people|projects|cases|tags|person\/\d+|project\/\d+|case\/\d+|entry\/\d+)?$/;
    if(previous.origin===location.origin&&previous.pathname!==location.pathname&&bekannt.test(previous.pathname)){
      // Benennen, wohin es zurückgeht – „vorherige Ansicht" sagt zu wenig.
      const ziele=[[/^\/entry\/\d+$/,'Zurück zum Eintrag'],[/^\/project\/\d+$/,'Zurück zum Projekt'],
                   [/^\/case\/\d+$/,'Zurück zum Vorgang'],[/^\/person\/\d+$/,'Zurück zum Kontakt']];
      const treffer=ziele.find(([muster])=>muster.test(previous.pathname));
      document.querySelectorAll('[data-context-back]').forEach(link=>{
        link.href=previous.href;
        const symbol=link.querySelector('svg');
        link.textContent=treffer?treffer[1]:'Zurück zur vorherigen Ansicht';
        if(symbol)link.prepend(symbol);
      });
    }
  }
  document.addEventListener('click',event=>{
    document.querySelectorAll('.task-actions[open]').forEach(menu=>{if(!menu.contains(event.target))menu.open=false;});
  });
  document.addEventListener('keydown',event=>{
    if(event.key==='Escape'&&!document.querySelector('dialog[open]'))document.querySelectorAll('.task-actions[open]').forEach(menu=>{menu.open=false;menu.querySelector('summary').focus();});
  });
  const proposals=document.querySelector('#suggestions');
  if(proposals){
    const key='journal-proposals:'+location.pathname;
    proposals.open=sessionStorage.getItem(key)==='open';
    proposals.addEventListener('toggle',()=>sessionStorage.setItem(key,proposals.open?'open':'closed'));
  }
  document.querySelectorAll('nav a.active,.tabs a.selected').forEach(link=>link.setAttribute('aria-current','page'));
  // Existing Markdown links may predate pagination and contain only a fragment.
  const taskHash=/^#task-([1-9][0-9]*)$/.exec(location.hash);
  if(location.pathname==='/tasks'&&taskHash&&!document.getElementById('task-'+taskHash[1])&&!new URL(location.href).searchParams.has('focus_task')){
    const target=new URL('/tasks',location.origin);target.searchParams.set('filter','all');target.searchParams.set('focus_task',taskHash[1]);target.hash=location.hash;location.replace(target.href);
  }
  const position=sessionStorage.getItem('journal-position');
  if(position){
    sessionStorage.removeItem('journal-position');
    try {const saved=JSON.parse(position);if(saved.url===location.pathname+location.search&&!sessionStorage.getItem('journal-scroll-target'))requestAnimationFrame(()=>scrollTo(0,saved.y));}catch{}
  }
})();
