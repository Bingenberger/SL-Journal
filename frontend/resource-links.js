import {autocompletion, acceptCompletion} from '@codemirror/autocomplete';
import {keymap, EditorView} from '@codemirror/view';
import {Prec} from '@codemirror/state';
import {syntaxTree} from '@codemirror/language';

export const resourceHelp='Markdown wird beim Schreiben formatiert. Leerzeichen + @ verlinkt Ressourcen.';

function escapeLabel(label) {
  return label.replace(/\s+/g,' ').replace(/[\\\x60*_[\]<>]/g,'\\$&');
}
async function resourceSource(context) {
  if(!context.state.selection.main.empty) return null;
  const match=context.matchBefore(/ @[^@\n]{0,100}$/);
  if(!match) return null;
  for(let node=syntaxTree(context.state).resolveInner(context.pos,-1);node;node=node.parent) {
    if(/^(InlineCode|FencedCode|CodeBlock|Link|Image|Autolink|HTMLTag|HTMLBlock|CommentBlock)$/.test(node.name)) return null;
  }
  const controller=new AbortController();
  context.addEventListener('abort',()=>controller.abort(),{onDocChange:true});
  try {
    const response=await fetch('/api/resources?'+new URLSearchParams({q:match.text.slice(2)}),{signal:controller.signal});
    if(!response.ok||response.redirected) return null;
    const data=await response.json();
    if(context.aborted) return null;
    return {
      from:match.from+1,
      filter:false,
      options:data.items.map(item=>({
        label:item.label,
        detail:[item.kind,item.detail].filter(Boolean).join(' · '),
        type:'text',
        apply:'['+escapeLabel(item.label)+']('+item.url.replace(/[()<>\s\\]/g,c=>encodeURIComponent(c).replace('(','%28').replace(')','%29'))+') '
      }))
    };
  } catch(error) {
    return null;
  }
}
export const resourceLinks=[
  autocompletion({override:[resourceSource],activateOnTypingDelay:150,maxRenderedOptions:20,icons:false,tooltipClass:()=> 'resource-completions'}),
  Prec.highest(keymap.of([{key:'Tab',run:acceptCompletion}])),
  EditorView.domEventHandlers({
    click(event) {
      const link=event.target.closest('a.md-resource-link');
      if(!link) return false;
      event.preventDefault();
      if(event.ctrlKey||event.metaKey) window.open(link.href,'_blank','noopener,noreferrer');
      return true;
    }
  })
];
