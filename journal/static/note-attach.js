'use strict';
(() => {
  document.addEventListener('click',event=>{
    const button=event.target.closest('[data-attach-note]');if(!button)return;
    const dialog=document.querySelector('#note-dialog');
    openDialog('note-dialog',{resource_url:button.dataset.resourceUrl||''});
    dialog.querySelector('[data-note-source]').textContent=button.dataset.sourceLabel?'Quelle: '+button.dataset.sourceLabel:'';
    dialog.querySelector('.ac-input')?.focus();
  });
})();
