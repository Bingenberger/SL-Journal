'use strict';
(() => {
  let serial=0;
  function attach(input,mode,scope){
    const form=input.form,id='field-suggestions-'+(++serial);
    let wrapper,list,status;
    if(mode==='global'){
      wrapper=form;list=form.querySelector('[role=listbox]');status=form.querySelector('[data-search-status]');
    }else{
      wrapper=document.createElement('div');wrapper.className='suggestion-field';
      input.before(wrapper);wrapper.append(input);
      list=document.createElement('div');list.className='search-suggestions';list.id=id;list.role='listbox';list.setAttribute('aria-label','Vorschläge');list.hidden=true;
      status=document.createElement('span');status.className='sr-only';status.role='status';wrapper.append(list,status);
    }
    input.autocomplete='off';input.setAttribute('role','combobox');input.setAttribute('aria-autocomplete','list');input.setAttribute('aria-expanded','false');input.setAttribute('aria-controls',list.id);
    let timer,controller,version=0,active=-1;
    const close=()=>{list.hidden=true;input.setAttribute('aria-expanded','false');input.removeAttribute('aria-activedescendant');active=-1;};
    const cancel=()=>{clearTimeout(timer);controller?.abort();version++;close();};
    function parameters(){
      const params=new URLSearchParams();
      if(mode==='scoped')for(const field of form.elements){
        if(!field.name||field.disabled||['submit','button'].includes(field.type)||(['checkbox','radio'].includes(field.type)&&!field.checked))continue;
        if(field.name==='q'||field.name==='page'||field.name==='focus_task')continue;
        params.set(field.name,field.value);
      }
      params.set('q',input.value.trim());return params;
    }
    function contactQuery(){
      if(scope!=='emails')return input.value.trim();
      const end=input.selectionStart??input.value.length;
      return input.value.slice(0,end).split(/[,;\n]/).pop().trim();
    }
    function choose(option){
      if(mode!=='contact'){location.assign(option.href);return;}
      if(scope==='emails'){
        const value=input.value,caret=input.selectionStart??value.length;
        const before=value.slice(0,caret),start=Math.max(before.lastIndexOf(','),before.lastIndexOf(';'),before.lastIndexOf('\n'))+1;
        const rest=value.slice(caret),next=rest.search(/[,;\n]/),end=next<0?value.length:caret+next;
        const prefix=start>0?' ':'';
        input.value=value.slice(0,start)+prefix+option.dataset.value+value.slice(end);
        input.setSelectionRange(start+prefix.length+option.dataset.value.length,start+prefix.length+option.dataset.value.length);
      }else input.value=option.dataset.value;
      input.dispatchEvent(new Event('input',{bubbles:true}));input.dispatchEvent(new Event('change',{bubbles:true}));cancel();input.focus();
    }
    function highlight(index){
      active=index;
      [...list.children].forEach((option,i)=>option.setAttribute('aria-selected',String(i===index)));
      const option=list.children[index];
      if(option){input.setAttribute('aria-activedescendant',option.id);option.scrollIntoView({block:'nearest'});}
    }
    async function suggest(){
      const params=parameters(),query=mode==='contact'?contactQuery():params.get('q'),requestVersion=++version;
      if(!query&&mode!=='contact'){close();return;}
      params.set('q',query);
      const endpoint=mode==='contact'?'/api/contact-values/'+scope:mode==='scoped'&&scope!=='all'?'/api/search/'+scope:'/api/search';
      controller=new AbortController();
      try{
        const response=await fetch(endpoint+'?'+params,{signal:controller.signal});
        if(!response.ok)throw new Error('Vorschläge nicht verfügbar');
        const data=await response.json();
        if(requestVersion!==version||document.activeElement!==input)return;
        list.replaceChildren();input.removeAttribute('aria-activedescendant');active=-1;
        for(const [index,item] of data.items.entries()){
          const option=document.createElement(mode==='contact'?'button':'a');
          if(mode==='contact'){option.type='button';option.dataset.value=item.label;}else option.href=item.url;
          option.id=list.id+'-option-'+index;option.role='option';option.tabIndex=-1;option.setAttribute('aria-selected','false');
          const kind=document.createElement('span');kind.className='small muted';kind.textContent=[item.kind,item.detail].filter(Boolean).join(' · ');
          const title=document.createElement('strong');title.textContent=item.label;option.append(kind,title);list.append(option);
        }
        if(mode!=='contact'){
          const all=document.createElement('a'),target=new URL(form.action,location.href);target.search=parameters().toString();
          all.href=target.href;all.id=list.id+'-all';all.role='option';all.tabIndex=-1;all.setAttribute('aria-selected','false');all.textContent=data.total?`Alle ${data.total} Treffer anzeigen`:'Keine Treffer – Suche öffnen';list.append(all);
        }
        list.hidden=!list.children.length;input.setAttribute('aria-expanded',String(!list.hidden));status.textContent=data.total+' Vorschläge';
      }catch(error){if(error.name!=='AbortError'&&requestVersion===version){close();status.textContent='Vorschläge derzeit nicht verfügbar.';}}
    }
    input.addEventListener('input',()=>{cancel();timer=setTimeout(suggest,180);});
    input.addEventListener('focus',()=>{if(input.value.trim()||mode==='contact')timer=setTimeout(suggest,180);});
    input.addEventListener('keydown',event=>{
      if(event.key==='Escape'&&!list.hidden){event.preventDefault();event.stopPropagation();cancel();return;}
      if(list.hidden)return;
      if(event.key==='ArrowDown'||event.key==='ArrowUp'){
        event.preventDefault();highlight(active<0?(event.key==='ArrowDown'?0:list.children.length-1):(active+(event.key==='ArrowDown'?1:-1)+list.children.length)%list.children.length);
      }else if(event.key==='Enter'&&active>=0){event.preventDefault();choose(list.children[active]);}
    });
    wrapper.addEventListener('focusout',event=>{if(!wrapper.contains(event.relatedTarget))cancel();});
    list.addEventListener('mousedown',event=>event.preventDefault());
    list.addEventListener('click',event=>{const option=event.target.closest('[role=option]');if(option){event.preventDefault();choose(option);}});
    document.addEventListener('pointerdown',event=>{if(!wrapper.contains(event.target))cancel();});
    form.addEventListener('submit',cancel);form.addEventListener('reset',cancel);
    form.addEventListener('change',event=>{if(event.target!==input)cancel();});
    input.closest('dialog')?.addEventListener('close',cancel);
  }
  const global=document.querySelector('.global-search input');if(global)attach(global,'global','all');
  document.querySelectorAll('[data-search-scope]').forEach(input=>attach(input,'scoped',input.dataset.searchScope));
  document.querySelectorAll('[data-contact-value]').forEach(input=>attach(input,'contact',input.dataset.contactValue));
})();
