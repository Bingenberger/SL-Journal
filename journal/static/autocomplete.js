'use strict';
(() => {
  const controls=[];
  const normalize=value=>String(value||'').normalize('NFKC').trim().replace(/\s+/g,' ').toLocaleLowerCase('de-DE');
  let serial=0;

  class Autocomplete {
    constructor(source) {
      this.source=source;
      this.kind=source.dataset.autocomplete;
      this.free=this.kind==='notes'||this.kind==='participants'||this.kind==='tags'||(['projects','cases'].includes(this.kind)&&source.dataset.existingOnly!=='true');
      this.multiple=source instanceof HTMLSelectElement?source.multiple:source.dataset.single!=='true';
      this.required=source.required;
      this.items=[];
      this.results=[];
      this.active=-1;
      this.sequence=0;
      this.wrapper=document.createElement('div');
      this.wrapper.className='autocomplete';
      this.wrapper.dataset.autocompleteField=source.name;
      this.box=document.createElement('div');this.box.className='ac-box';
      this.tokens=document.createElement('div');this.tokens.className='ac-tokens';
      this.input=document.createElement('input');
      this.input.type='text';this.input.autocomplete='off';
      this.input.id='ac-input-'+(++serial);
      this.input.className='ac-input';
      this.input.setAttribute('role','combobox');
      this.input.setAttribute('aria-autocomplete','list');
      this.input.setAttribute('aria-expanded','false');
      this.input.setAttribute('aria-haspopup','listbox');
      this.input.setAttribute('aria-required',String(this.required));
      this.input.placeholder=this.kind==='participants'?'Name, Rolle, Institution oder Mail suchen …':this.kind==='tags'?'Tag suchen oder neu eingeben …':this.kind==='notes'?'Notiz suchen oder neu benennen …':this.kind==='appointments'?'Termin, Datum oder Kalender suchen …':this.kind==='people'?'Kontakt suchen …':this.kind==='cases'?(this.free?'Vorgang suchen oder neu eingeben …':'Vorgang suchen …'):this.kind==='entries'?'Eintrag suchen …':'Projekt suchen …';
      this.list=document.createElement('div');
      this.list.className='ac-list';this.list.id='ac-list-'+serial;
      this.list.setAttribute('role','listbox');this.list.hidden=true;
      this.input.setAttribute('aria-controls',this.list.id);
      this.message=document.createElement('div');this.message.className='ac-message';
      this.message.setAttribute('role','status');this.message.setAttribute('aria-live','polite');
      this.message.id='ac-help-'+serial;
      this.input.setAttribute('aria-describedby',this.message.id);
      this.box.append(this.tokens,this.input);
      this.wrapper.append(this.box,this.list,this.message);
      const label=source.closest('label');
      const name=source.dataset.label||source.getAttribute('aria-label')||source.name;
      if(label) {
        const copy=label.cloneNode(true);
        copy.querySelectorAll('input,select,textarea').forEach(el=>el.remove());
        const field=document.createElement('div');field.className='autocomplete-field';
        const title=document.createElement('label');title.htmlFor=this.input.id;
        title.textContent=copy.textContent.trim();
        field.append(title,this.wrapper);
        label.replaceWith(field);
        field.append(source);
        this.input.setAttribute('aria-label',source.dataset.label||title.textContent);
      } else {
        source.before(this.wrapper);
        this.input.setAttribute('aria-label',name);
      }
      source.hidden=true;source.required=false;
      source.setAttribute('aria-hidden','true');
      this.readSource(source.dataset.caseItems ? {case_items:JSON.parse(source.dataset.caseItems)} : source.dataset.projectItems ? {project_items:JSON.parse(source.dataset.projectItems)} : undefined);
      this.render();
      this.input.addEventListener('input',()=>{
        this.clearError();this.results=[];this.active=-1;
        clearTimeout(this.timer);
        this.controller?.abort();this.sequence++;
        this.timer=setTimeout(()=>this.search(),120);
      });
      this.input.addEventListener('focus',()=>this.search());
      this.input.addEventListener('keydown',event=>this.keydown(event));
      this.wrapper.addEventListener('focusout',()=>{
        setTimeout(()=>{
          if(!this.wrapper.contains(document.activeElement)) {
            if(this.free) this.commit(false);
            this.close();
          }
        },0);
      });
      this.box.addEventListener('click',event=>{
        if(event.target===this.box||event.target===this.tokens) this.input.focus();
      });
    }

    key(item) {return item.id!==undefined?item.kind+':'+item.id:item.kind+':'+normalize(item.label)+':'+(item.school_year||'');}
    fromOption(option) {
      return {kind:this.kind==='notes'?'entry':this.kind==='appointments'?'appointment':this.kind==='people'?'person':this.kind==='cases'?'case':this.kind==='entries'?'entry':'project',id:Number(option.value),label:option.dataset.label||option.textContent.trim(),detail:option.dataset.detail||''};
    }
    readSource(data) {
      if(this.kind==='participants') {
        if(data?.participant_items) this.items=data.participant_items.map(item=>({...item}));
        else this.items=this.source.value.split(/[;\n]/).filter(s=>s.trim()).map(label=>({kind:'new',label:label.trim()}));
      } else if(this.kind==='cases'&&data?.case_items) {
        this.items=data.case_items.map(item=>({...item}));
      } else if(this.kind==='projects'&&data?.project_items) {
        this.items=data.project_items.map(item=>({...item}));
      } else if(this.source instanceof HTMLSelectElement) {
        this.items=[...this.source.selectedOptions].filter(o=>o.value).map(o=>this.fromOption(o));
        if(this.kind==='projects'&&Array.isArray(data?.projects)) {
          this.items=this.items.map(item=>{
            const found=data.projects.find(p=>String(p.id??p)===String(item.id));
            return found?.name?{...item,label:found.name,detail:found.school_year}:item;
          });
        }
      } else {
        this.items=this.source.value.split(',').filter(s=>s.trim()).map(label=>({kind:'tag',label:label.trim().replace(/^#+/,'')}));
      }
      if(!this.multiple) this.items=this.items.slice(0,1);
    }
    reset(data) {
      this.close();this.input.value='';this.clearError();
      this.readSource(data);this.render();this.sync();
    }
    sync() {
      if(this.source instanceof HTMLSelectElement) {
        [...this.source.options].forEach(o=>o.selected=false);
        for(const item of this.items.filter(i=>i.id!==undefined)) {
          let option=[...this.source.options].find(o=>o.value===String(item.id));
          if(!option) {
            option=new Option(item.label,String(item.id));
            option.dataset.label=item.label;option.dataset.detail=item.detail||'';
            this.source.add(option);
          }
          option.selected=true;
        }
        if(!this.items.length) this.source.value='';
      } else this.source.value=this.items.map(i=>i.label).join(this.kind==='tags'?', ':'; ');
    }
    render() {
      this.tokens.replaceChildren();
      for(const item of this.items) {
        const chip=document.createElement('span');chip.className='ac-chip';
        const label=document.createElement('span');label.textContent=item.label;
        chip.append(label);
        if(item.kind==='new'||item.kind==='new_project'||item.kind==='new_case'||item.kind==='new_note') {
          const badge=document.createElement('small');badge.textContent='neu';chip.append(badge);
        }
        if(item.detail) chip.title=item.detail;
        const remove=document.createElement('button');remove.type='button';
        remove.textContent='×';remove.setAttribute('aria-label',item.label+' entfernen');
        remove.addEventListener('click',()=>{
          this.items=this.items.filter(value=>this.key(value)!==this.key(item));
          this.render();this.sync();this.input.focus();this.search();
        });
        chip.append(remove);this.tokens.append(chip);
      }
    }
    add(item,focus=true) {
      if(!this.multiple) this.items=[];
      if(!this.items.some(existing=>this.key(existing)===this.key(item))) this.items.push(item);
      this.input.value='';this.clearError();this.render();this.sync();this.close();if(focus)this.input.focus();
    }
    clearError() {
      this.wrapper.classList.remove('ac-invalid');
      this.input.removeAttribute('aria-invalid');
      this.message.textContent=this.kind==='participants'?'Neue Namen werden beim Speichern als Kontaktvorschläge gesammelt.':this.kind==='projects'&&this.free?'Neue Namen werden beim Speichern als Projektvorschläge gesammelt.':this.kind==='cases'&&this.free?'Neue Namen werden beim Speichern als Vorgangsvorschläge gesammelt.':'';
    }
    error(message) {
      this.wrapper.classList.add('ac-invalid');this.input.setAttribute('aria-invalid','true');
      this.message.textContent=message;return false;
    }
    close() {
      clearTimeout(this.timer);this.controller?.abort();this.sequence++;
      this.list.hidden=true;this.input.setAttribute('aria-expanded','false');
      this.input.removeAttribute('aria-activedescendant');
      this.active=-1;
    }
    async search() {
      const query=this.input.value.trim();
      this.controller?.abort();this.controller=new AbortController();
      const sequence=++this.sequence;
      const params=new URLSearchParams({q:query});
      if(this.kind==='appointments'&&this.source.form.elements.start_date?.value)params.set('from',this.source.form.elements.start_date.value);
      if(this.source.dataset.existingOnly==='true') params.set('existing_only','1');
      if(this.source.dataset.includeClosed==='true') params.set('include_closed','1');
      try {
        const response=await fetch('/api/autocomplete/'+this.kind+'?'+params,{signal:this.controller.signal});
        if(!response.ok||response.redirected) throw Error('Die Vorschläge konnten nicht geladen werden. Bitte erneut versuchen.');
        const result=await response.json();
        if(sequence!==this.sequence||document.activeElement!==this.input) return;
        this.results=result.items.filter(item=>!this.items.some(selected=>this.key(selected)===this.key(item)));
        const clean=this.kind==='tags'?query.replace(/^#+/,''):query;
        const exact=this.results.some(item=>normalize(item.label)===normalize(clean));
        const selected=this.items.some(item=>normalize(item.label)===normalize(clean));
        if(this.free&&clean&&!exact&&!selected) {
          this.results.push({kind:this.kind==='notes'?'new_note':this.kind==='tags'?'tag':this.kind==='projects'?'new_project':this.kind==='cases'?'new_case':'new',label:clean,detail:this.kind==='notes'?'Als neue Notiz anlegen':this.kind==='tags'?'Neuen Tag übernehmen':this.kind==='projects'?'Als Projektvorschlag übernehmen':this.kind==='cases'?'Als Vorgangsvorschlag übernehmen':'Als Beteiligte übernehmen · Kontaktvorschlag',fresh:true});
        }
        this.showResults(result.more);
      } catch(error) {
        if(error.name!=='AbortError'&&sequence===this.sequence) {
          this.results=[];this.close();
          this.message.textContent=error.message;
        }
      }
    }
    showResults(more) {
      this.list.replaceChildren();this.active=-1;
      for(const [index,item] of this.results.entries()) {
        const option=document.createElement('div');
        option.className='ac-option';option.id=this.list.id+'-'+index;
        option.setAttribute('role','option');option.setAttribute('aria-selected','false');
        const title=document.createElement('span');title.textContent=item.label;
        const detail=document.createElement('small');detail.textContent=item.detail||'';
        option.append(title,detail);
        option.addEventListener('pointerdown',event=>event.preventDefault());
        option.addEventListener('click',()=>this.add(item));
        this.list.append(option);
      }
      if(!this.results.length||more) {
        const text=document.createElement('div');text.className='ac-empty';
        text.textContent=more?'Weitere Treffer – Suche eingrenzen.':this.kind==='projects'?'Kein passendes Projekt gefunden.':'Keine weiteren Vorschläge.';
        this.list.append(text);
      }
      this.list.hidden=false;this.input.setAttribute('aria-expanded','true');
    }
    highlight(index) {
      this.active=index;
      [...this.list.querySelectorAll('[role=option]')].forEach((option,i)=>{
        option.setAttribute('aria-selected',String(i===index));
        if(i===index) {
          this.input.setAttribute('aria-activedescendant',option.id);
          option.scrollIntoView({block:'nearest'});
        }
      });
    }
    commit(focus=true) {
      const text=this.input.value.trim();
      if(text) {
        const clean=this.kind==='tags'?text.replace(/^#+/,''):text;
        const exact=this.results.filter(item=>normalize(item.label)===normalize(clean));
        if(this.items.some(item=>normalize(item.label)===normalize(clean))) this.input.value='';
        else if(exact.length===1) this.add(exact[0],focus);
        else if(this.free&&clean) this.add({kind:this.kind==='notes'?'new_note':this.kind==='tags'?'tag':this.kind==='projects'?'new_project':this.kind==='cases'?'new_case':'new',label:clean},focus);
        else {
          const options=this.source instanceof HTMLSelectElement?[...this.source.options].filter(o=>o.value&&normalize(o.dataset.label||o.textContent)===normalize(clean)):[];
          if(options.length===1) this.add(this.fromOption(options[0]),focus);
          else return this.error('Bitte einen passenden Vorschlag auswählen.');
        }
      }
      this.sync();
      if(this.required&&!this.items.length) return this.error('Bitte eine Auswahl treffen.');
      return true;
    }
    keydown(event) {
      if(event.isComposing) return;
      if(event.key==='ArrowDown'||event.key==='ArrowUp') {
        event.preventDefault();
        if(this.list.hidden) {this.search();return;}
        if(this.results.length) this.highlight((this.active+(event.key==='ArrowDown'?1:-1)+this.results.length)%this.results.length);
      } else if(event.key==='Enter'||(event.key===','&&this.kind==='tags'&&this.multiple)) {
        event.preventDefault();
        if(!this.list.hidden&&this.active>=0&&this.results[this.active]) this.add(this.results[this.active]);
        else this.commit();
      } else if(event.key==='Tab'&&this.input.value.trim()) {
        if(!this.list.hidden&&this.active>=0&&this.results[this.active]) this.add(this.results[this.active]);
        else this.commit();
      } else if(event.key==='Escape'&&!this.list.hidden) {
        event.preventDefault();event.stopPropagation();this.close();
      } else if(event.key==='Backspace'&&!this.input.value&&this.items.length) {
        this.items.pop();this.render();this.sync();
      }
    }
  }
  document.querySelectorAll('[data-autocomplete]').forEach(source=>controls.push(new Autocomplete(source)));
  window.JournalAutocomplete={
    refresh(form,data) {
      controls.filter(c=>c.source.form===form).forEach(c=>c.reset(data));
    }
  };
  document.addEventListener('submit',event=>{
    let firstInvalid=null;
    for(const control of controls.filter(c=>c.source.form===event.target)) {
      if(!control.commit(false)&&!firstInvalid) firstInvalid=control;
      control.close();
    }
    if(firstInvalid) {
      event.preventDefault();event.stopImmediatePropagation();firstInvalid.input.focus();
    }
  },true);
  document.addEventListener('formdata',event=>{
    for(const control of controls.filter(c=>c.source.form===event.target)) {
      control.sync();
      if(control.kind==='notes')event.formData.set('target_title',control.items.find(item=>item.kind==='new_note')?.label||'');
      if(control.kind==='cases') event.formData.set('case_items',JSON.stringify(control.items));
      if(control.kind==='projects') event.formData.set('project_items',JSON.stringify(control.items.map(({kind,id,label,school_year})=>({kind,id,label,school_year}))));
      if(control.kind==='participants') event.formData.set('participant_items',JSON.stringify(control.items.map(({kind,id,label})=>({kind,id,label}))));
      if(control.source instanceof HTMLSelectElement) {
        event.formData.delete(control.source.name);
        control.items.filter(item=>item.id!==undefined).forEach(item=>event.formData.append(control.source.name,String(item.id)));
      } else event.formData.set(control.source.name,control.source.value);
    }
  });
})();
