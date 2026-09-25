import {Compartment, EditorSelection, EditorState} from '@codemirror/state';
import {Decoration, EditorView, ViewPlugin, WidgetType, keymap, placeholder} from '@codemirror/view';
import {defaultKeymap, history, historyKeymap, redo} from '@codemirror/commands';
import {markdown, markdownKeymap} from '@codemirror/lang-markdown';
import {syntaxTree} from '@codemirror/language';
import {GFM} from '@lezer/markdown';
import {resourceLinks, resourceHelp} from './resource-links.js';

// Only the view is decorated. The original Markdown (including unsupported
// syntax, whitespace and imported HTML) remains the single source of truth.
const editors = new Map();

class Marker extends WidgetType {
  constructor(text, className='') { super(); this.text=text; this.className=className; }
  eq(other) { return this.text===other.text && this.className===other.className; }
  toDOM() {
    const span=document.createElement('span');
    span.className='md-marker '+this.className;
    span.textContent=this.text;
    span.setAttribute('aria-hidden','true');
    return span;
  }
}

function decorations(view) {
  const ranges=[];
  const doc=view.state.doc;
  const lines=new Set();
  const editing=(from,to)=>view.hasFocus && view.state.selection.ranges.some(
    range=>range.empty ? range.head>=from && range.head<to : range.from<to && range.to>from);
  const hide=(from,to,widget)=>{
    if(editing(from,to)) return;
    // View plugins may not replace line breaks. Keep wrapped link destinations safe.
    while(from<to) {
      const end=Math.min(to,doc.lineAt(from).to);
      if(from<end) ranges.push(Decoration.replace(widget?{widget}:{}).range(from,end));
      from=end+1;
    }
  };
  const mark=(from,to,className)=>{
    if(from<to) ranges.push(Decoration.mark({class:className}).range(from,to));
  };
  const line=(pos,className)=>{
    const start=doc.lineAt(pos).from;
    const key=start+':'+className;
    if(!lines.has(key)) {
      ranges.push(Decoration.line({class:className}).range(start));
      lines.add(key);
    }
  };
  syntaxTree(view.state).iterate({
    enter(ref) {
      const {name,from,to,node}=ref;
      if(name==='Escape') hide(from,from+1);
      if(name==='StrongEmphasis') mark(from,to,'md-bold');
      if(name==='Emphasis') mark(from,to,'md-italic');
      if(name==='Strikethrough') mark(from,to,'md-strike');
      if(name==='InlineCode') mark(from,to,'md-inline-code');
      if(/^ATXHeading[1-6]$|^SetextHeading[12]$/.test(name)) line(from,'md-heading md-h'+name.slice(-1));
      if(name==='HeaderMark') {
        let end=to;
        if(doc.sliceString(to,to+1)===' ') end++;
        hide(from,end);
      }
      if(name==='EmphasisMark' || name==='StrikethroughMark') hide(from,to);
      if(name==='CodeMark' && node.parent?.name==='InlineCode') hide(from,to);
      if(name==='ListMark') {
        const text=doc.sliceString(from,to);
        if(/[-+*]/.test(text)) hide(from,to,new Marker('•','md-bullet'));
        else mark(from,to,'md-list-number');
      }
      if(name==='TaskMarker') {
        hide(from,to,new Marker(doc.sliceString(from,to).toLowerCase()==='[x]'?'☑':'☐','md-task-marker'));
      }
      if(name==='QuoteMark') {
        line(from,'md-quote');
        hide(from,to,new Marker('','md-quote-marker'));
      }
      if(name==='FencedCode' || name==='CodeBlock') {
        const last=doc.lineAt(to).number;
        for(let n=doc.lineAt(from).number;n<=last;n++) line(doc.line(n).from,'md-code-line');
      }
      if(name==='CodeInfo' || (name==='CodeMark' && node.parent?.name==='FencedCode')) mark(from,to,'md-code-fence');
      if(name==='HorizontalRule') {
        line(from,'md-rule-line');
        hide(from,to,new Marker('','md-rule'));
      }
      if(name==='Table') {
        for(let n=doc.lineAt(from).number;n<=doc.lineAt(to).number;n++) line(doc.line(n).from,'md-table-line');
      }
      if(name==='TableHeader') mark(from,to,'md-bold');
      if(name==='Link') {
        const children=[];
        for(let child=node.firstChild;child;child=child.nextSibling) children.push(child);
        const labelEnd=children.find(child=>child.name==='LinkMark' && doc.sliceString(child.from,child.to)===']');
        if(labelEnd) {
          const destination=children.find(child=>child.name==='URL');
          const href=destination?doc.sliceString(destination.from,destination.to):'';
          if(/^\/(?!\/)/.test(href)) {
            ranges.push(Decoration.mark({tagName:'a',class:'md-link md-resource-link',attributes:{href,title:'Strg/Befehl + Klick öffnet die Ressource in einem neuen Tab'}}).range(from+1,labelEnd.from));
          } else mark(from+1,labelEnd.from,'md-link');
          hide(from,from+1);
          // Reveal the destination when the cursor enters it, or use source mode.
          hide(labelEnd.from,to);
        }
      }
      // Image links and embedded HTML stay literal: no remote image fetches,
      // HTML insertion or script execution while writing.
    }
  });
  return Decoration.set(ranges,true);
}

const liveMarkdown=ViewPlugin.fromClass(class {
  constructor(view) { this.decorations=decorations(view); }
  update(update) {
    if(update.docChanged || update.selectionSet || update.focusChanged ||
       syntaxTree(update.startState)!==syntaxTree(update.state)) {
      this.decorations=decorations(update.view);
    }
  }
},{decorations:plugin=>plugin.decorations});

function wrap(view,delimiter) {
  const range=view.state.selection.main;
  const selected=view.state.sliceDoc(range.from,range.to);
  const before=view.state.sliceDoc(Math.max(0,range.from-delimiter.length),range.from);
  const after=view.state.sliceDoc(range.to,range.to+delimiter.length);
  if(selected && before===delimiter && after===delimiter) {
    view.dispatch({
      changes:[{from:range.from-delimiter.length,to:range.from},{from:range.to,to:range.to+delimiter.length}],
      selection:{anchor:range.from-delimiter.length,head:range.to-delimiter.length},
      userEvent:'input'
    });
  } else {
    const text=selected||'Text';
    view.dispatch({
      changes:{from:range.from,to:range.to,insert:delimiter+text+delimiter},
      selection:EditorSelection.range(range.from+delimiter.length,range.from+delimiter.length+text.length),
      userEvent:'input'
    });
  }
  view.focus();
  return true;
}

function prefixLines(view,prefix) {
  const range=view.state.selection.main;
  const first=view.state.doc.lineAt(range.from);
  const last=view.state.doc.lineAt(range.to);
  const changes=[];
  const remove=view.state.sliceDoc(first.from,first.from+prefix.length)===prefix;
  for(let n=first.number;n<=last.number;n++) {
    const line=view.state.doc.line(n);
    if(remove && line.text.startsWith(prefix)) changes.push({from:line.from,to:line.from+prefix.length});
    else if(!remove) changes.push({from:line.from,insert:prefix});
  }
  view.dispatch({changes,userEvent:'input'});
  view.focus();
}

function mount(textarea) {
  const wrapper=document.createElement('div');
  wrapper.className='markdown-editor';
  wrapper.dataset.field=textarea.name;
  const toolbar=document.createElement('div');
  toolbar.className='md-toolbar';
  toolbar.setAttribute('role','toolbar');
  toolbar.setAttribute('aria-label','Text formatieren');
  const surface=document.createElement('div');
  surface.className='md-surface';
  const help=document.createElement('div');
  help.className='md-help';
  help.textContent=resourceHelp;
  help.id=(textarea.id||'md-'+editors.size)+'-help';
  wrapper.append(toolbar,surface,help);
  // Do not nest a contenteditable/toolbar inside the textarea's original label.
  const label=textarea.closest('label');
  if(label) label.after(wrapper);
  else textarea.after(wrapper);
  const name=textarea.dataset.editorLabel||'Text';
  const liveMode=new Compartment();
  const minHeight=new Compartment();
  const settings={
    live:true,
    required:textarea.required,
    textarea,
    wrapper,
    view:null,
    reset() {
      const state=createState(textarea.value);
      this.view.setState(state); // resets undo history between unrelated entries
      this.view.requestMeasure();
      this.wrapper.classList.remove('md-invalid');
      this.view.contentDOM.removeAttribute('aria-invalid');
    },
    sync() {textarea.value=this.view.state.doc.toString();},
    validate() {
      this.sync();
      const valid=!this.required || Boolean(textarea.value.trim());
      this.wrapper.classList.toggle('md-invalid',!valid);
      this.view.contentDOM.setAttribute('aria-invalid',String(!valid));
      if(!valid) {
        help.textContent='Bitte zuerst einen Text eingeben.';
        this.view.focus();
      } else help.textContent=this.live?resourceHelp:'Markdown-Quelltext bearbeiten.';
      return valid;
    }
  };
  function createState(text) {
    return EditorState.create({
      doc:text,
      extensions:[
        markdown({extensions:GFM}),
        history(),
        resourceLinks,
        keymap.of([
          {key:'Mod-Shift-z',run:redo},
          {key:'Mod-b',run:view=>wrap(view,'**')},
          {key:'Mod-i',run:view=>wrap(view,'*')},
          ...markdownKeymap,...defaultKeymap,...historyKeymap
        ]),
        EditorView.lineWrapping,
        EditorView.cspNonce.of(document.querySelector('meta[name="style-nonce"]')?.content||''),
        EditorView.contentAttributes.of({
          'aria-label':name,
          'aria-describedby':help.id,
          'aria-required':String(settings.required),
          spellcheck:'true',
          autocapitalize:'sentences',
          'data-md-content':textarea.name
        }),
        placeholder(textarea.placeholder||'Text schreiben …'),
        minHeight.of(EditorView.theme({'.cm-content':{minHeight:Math.max(100,Number(textarea.rows)*23)+'px'}})),
        liveMode.of(settings.live?[liveMarkdown]:[]),
        EditorView.updateListener.of(update=>{
          if(update.docChanged) {
            textarea.value=update.state.doc.toString();
            textarea.dispatchEvent(new Event('input',{bubbles:true}));
            wrapper.classList.remove('md-invalid');
            help.textContent=settings.live?resourceHelp:'Markdown-Quelltext bearbeiten.';
            update.view.contentDOM.removeAttribute('aria-invalid');
          }
        })
      ]
    });
  }
  try {
    settings.view=new EditorView({state:createState(textarea.value),parent:surface});
  } catch(error) {
    wrapper.remove();
    console.error('Markdown-Editor konnte nicht geladen werden.',error);
    return;
  }
  function button(text,title,action) {
    const el=document.createElement('button');
    el.type='button';el.textContent=text;el.title=title;el.setAttribute('aria-label',title);
    el.addEventListener('mousedown',event=>event.preventDefault());
    el.addEventListener('click',action);
    toolbar.append(el);
    return el;
  }
  button('B','Fett (Strg/Befehl+B)',()=>wrap(settings.view,'**')).className='md-tool-bold';
  button('I','Kursiv (Strg/Befehl+I)',()=>wrap(settings.view,'*')).className='md-tool-italic';
  button('H','Überschrift',()=>prefixLines(settings.view,'## '));
  button('•','Aufzählung',()=>prefixLines(settings.view,'- '));
  button('1.','Nummerierte Liste',()=>prefixLines(settings.view,'1. '));
  button('❝','Zitat',()=>prefixLines(settings.view,'> '));
  const source=button('Markdown','Markdown-Quelltext anzeigen',()=>{
    settings.live=!settings.live;
    settings.view.dispatch({effects:liveMode.reconfigure(settings.live?[liveMarkdown]:[])});
    source.setAttribute('aria-pressed',String(!settings.live));
    source.textContent=settings.live?'Markdown':'Formatiert';
    source.setAttribute('aria-label',settings.live?'Markdown-Quelltext anzeigen':'Formatierten Text anzeigen');
    source.title=source.getAttribute('aria-label');
    help.textContent=settings.live?resourceHelp:'Markdown-Quelltext bearbeiten.';
    settings.view.focus();
  });
  source.className='md-source-toggle';
  source.setAttribute('aria-pressed','false');
  textarea.hidden=true;
  textarea.required=false; // validation belongs to the visible editor, not a hidden textarea
  textarea.setAttribute('aria-hidden','true');
  if(label) {
    label.addEventListener('click',event=>{
      if(event.target===label || event.target.tagName==='SPAN') settings.view.focus();
    });
  }
  editors.set(textarea,settings);
}

window.JournalMarkdown={
  refresh(form) {
    for(const [textarea,editor] of editors) if(textarea.form===form) editor.reset();
  },
  validate(form) {
    let valid=true;
    for(const [textarea,editor] of editors) {
      if(textarea.form===form && !editor.validate()) valid=false;
    }
    return valid;
  }
};
document.querySelectorAll('textarea[data-markdown]').forEach(mount);
document.addEventListener('reset',event=>{
  // Native form.reset() changes values after the event dispatch completes.
  queueMicrotask(()=>window.JournalMarkdown.refresh(event.target));
});
document.addEventListener('formdata',event=>{
  for(const [textarea,editor] of editors) if(textarea.form===event.target) {
    editor.sync();
    event.formData.set(textarea.name,textarea.value);
  }
});
document.addEventListener('submit',event=>{
  if(!window.JournalMarkdown.validate(event.target)) {
    event.preventDefault();
    event.stopImmediatePropagation();
  }
},true);
