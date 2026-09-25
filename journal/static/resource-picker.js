'use strict';
for(const form of document.querySelectorAll('[data-resource-picker]')){
  const input=form.querySelector('[data-resource-query]');
  const hidden=form.elements.resource_url;
  const list=form.querySelector('[role=listbox]');
  const status=form.querySelector('[data-resource-status]');
  let timer,controller,sequence=0,items=[],active=-1;
  function close(){list.hidden=true;input.setAttribute('aria-expanded','false');input.removeAttribute('aria-activedescendant');active=-1;}
  function select(item){hidden.value=item.url;input.value=item.label;status.textContent=item.kind+' ausgewählt';close();}
  function highlight(index){
    active=index;
    [...list.children].forEach((el,i)=>el.setAttribute('aria-selected',String(i===active)));
    if(list.children[active]){
      input.setAttribute('aria-activedescendant',list.children[active].id);
      list.children[active].scrollIntoView({block:'nearest'});
    }
  }
  async function search(){
    const query=input.value.trim().replace(/^@/,'');const ticket=++sequence;
    controller?.abort();controller=new AbortController();close();items=[];
    if(!query){status.textContent='Vorhandene Ressource suchen und auswählen.';return;}
    status.textContent='Ressourcen werden gesucht …';
    try{
      const response=await fetch('/api/resources?'+new URLSearchParams({q:query}),{signal:controller.signal});
      if(response.redirected||!response.ok)throw Error('Die Suche ist nicht verfügbar. Bitte die Anmeldung und Verbindung prüfen.');
      const data=await response.json();if(ticket!==sequence)return;
      items=data.items;list.replaceChildren();
      items.forEach((item,index)=>{
        const option=document.createElement('div');option.className='ac-option';option.role='option';
        option.id=list.id+'-'+index;option.setAttribute('aria-selected','false');
        const name=document.createElement('strong');name.textContent=item.label;
        const detail=document.createElement('small');detail.textContent=[item.kind,item.detail].filter(Boolean).join(' · ');
        option.append(name,detail);
        option.addEventListener('mousedown',e=>e.preventDefault());
        option.addEventListener('click',()=>select(item));list.append(option);
      });
      list.hidden=!items.length;input.setAttribute('aria-expanded',String(Boolean(items.length)));
      status.textContent=items.length?(data.more?'Weitere Treffer: Suchbegriff bitte eingrenzen.':'Ressource aus der Liste auswählen.'):'Keine passende Ressource gefunden.';
    }catch(error){if(error.name!=='AbortError'&&ticket===sequence)status.textContent=error.message;}
  }
  input.addEventListener('input',()=>{hidden.value='';clearTimeout(timer);sequence++;controller?.abort();close();items=[];timer=setTimeout(search,150);});
  input.addEventListener('focus',()=>{if(!hidden.value)search();});
  input.addEventListener('keydown',event=>{
    if(event.isComposing)return;
    if(event.key==='ArrowDown'||event.key==='ArrowUp'){
      event.preventDefault();
      if(items.length&&!list.hidden)highlight((active+(event.key==='ArrowDown'?1:-1)+items.length)%items.length);
      else search();
    }else if(event.key==='Enter'&&!list.hidden){
      event.preventDefault();if(active>=0)select(items[active]);else if(items.length===1)select(items[0]);
    }else if(event.key==='Escape'){event.preventDefault();event.stopPropagation();close();}
  });
  form.addEventListener('focusout',()=>setTimeout(()=>{if(!form.contains(document.activeElement))close();},0));
  form.addEventListener('submit',event=>{
    if(!hidden.value){event.preventDefault();event.stopImmediatePropagation();status.textContent='Bitte zuerst eine vorhandene Ressource aus der Vorschlagsliste auswählen.';input.focus();}
  });
}
