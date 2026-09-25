'use strict';
(() => {
  const panel=document.getElementById('pdf-preview');
  if(!panel) return;
  const status=panel.querySelector('.pdf-preview-status');
  const surface=panel.querySelector('.pdf-preview-image');
  let active=null, pinned=false, opening=null, closing=null, version=0, returnFocus=null, suppressFocus=false;
  const canHover=()=>matchMedia('(hover: hover) and (pointer: fine)').matches;
  function position() {
    if(!active) return;
    const width=Math.min(pinned?640:420,innerWidth-24);
    const height=Math.min(620,innerHeight-24);
    panel.style.width=width+'px';
    panel.style.maxHeight=height+'px';
    const rect=active.getBoundingClientRect();
    let left=pinned?(innerWidth-width)/2:rect.left-width-12;
    if(!pinned&&left<12) left=rect.right+12;
    left=Math.max(12,Math.min(left,innerWidth-width-12));
    const top=pinned?(innerHeight-height)/2:Math.max(12,Math.min(rect.top,innerHeight-height-12));
    panel.style.left=left+'px';panel.style.top=top+'px';
  }
  function close(restore=false) {
    clearTimeout(opening);clearTimeout(closing);version++;
    if(active) active.querySelector('.pdf-preview-button').setAttribute('aria-expanded','false');
    if(panel.hidePopover&&panel.matches(':popover-open')) panel.hidePopover();
    panel.hidden=true;surface.replaceChildren();active=null;pinned=false;
    if(restore&&returnFocus?.isConnected) {
      suppressFocus=true;returnFocus.focus();suppressFocus=false;
    }
  }
  function show(row,pin=false) {
    clearTimeout(opening);clearTimeout(closing);
    if(active===row&&!panel.hidden) {
      pinned=pinned||pin;position();
      if(pin) panel.querySelector('[data-pdf-close]').focus();
      return;
    }
    close();
    active=row;pinned=pin;returnFocus=row.querySelector('.pdf-preview-button');
    const current=++version;
    panel.querySelector('#pdf-preview-title').textContent=row.dataset.pdfName;
    panel.querySelector('.pdf-preview-download').href=row.dataset.pdfDownload;
    const weiter=panel.querySelector('.pdf-preview-more');
    weiter.hidden=!row.dataset.pdfMore;
    if(row.dataset.pdfMore)weiter.href=row.dataset.pdfMore;
    status.textContent='Vorschau wird geladen …';status.hidden=false;
    row.querySelector('.pdf-preview-button').setAttribute('aria-expanded','true');
    panel.hidden=false;position();
    if(panel.showPopover) panel.showPopover();
    const img=document.createElement('img');
    img.alt='Erste Seite von '+row.dataset.pdfName;
    img.hidden=true;
    img.onload=()=>{if(current===version){status.hidden=true;img.hidden=false;}};
    img.onerror=()=>{if(current===version){img.remove();status.textContent='Keine Vorschau verfügbar. Die Datei kann geschützt oder beschädigt sein. Bitte herunterladen.';}};
    img.src=row.dataset.pdfUrl;surface.append(img);
    if(pin) panel.querySelector('[data-pdf-close]').focus();
  }
  function scheduleClose() {
    clearTimeout(opening);clearTimeout(closing);
    if(!pinned) closing=setTimeout(()=>close(),350);
  }
  document.querySelectorAll('[data-pdf-url]').forEach(row=>{
    row.addEventListener('pointerenter',()=>{
      if(!canHover()||pinned) return;
      clearTimeout(closing);
      opening=setTimeout(()=>show(row),300);
    });
    row.addEventListener('pointerleave',scheduleClose);
    row.addEventListener('focusin',event=>{
      if(event.target.closest('[data-plan-meeting]'))return;
      if(!suppressFocus&&!pinned) show(row);
    });
    row.addEventListener('focusout',()=>{
      setTimeout(()=>{if(!row.contains(document.activeElement)&&!panel.contains(document.activeElement))scheduleClose();},0);
    });
    row.querySelector('.pdf-preview-button').addEventListener('click',()=>show(row,true));
  });
  panel.addEventListener('pointerenter',()=>clearTimeout(closing));
  panel.addEventListener('pointerleave',scheduleClose);
  panel.addEventListener('focusin',()=>clearTimeout(closing));
  panel.addEventListener('focusout',()=>setTimeout(()=>{
    if(!panel.contains(document.activeElement)&&!active?.contains(document.activeElement))scheduleClose();
  },0));
  panel.querySelector('[data-pdf-close]').addEventListener('click',()=>close(true));
  document.addEventListener('keydown',event=>{
    if(event.key==='Escape'&&!panel.hidden) {
      event.preventDefault();event.stopImmediatePropagation();close(pinned);
    }
  },true);
  document.addEventListener('pointerdown',event=>{
    if(!panel.hidden&&!panel.contains(event.target)&&!active?.contains(event.target))close();
  });
  document.addEventListener('click',event=>{if(event.target.closest('[data-plan-meeting]'))close();});
  window.addEventListener('resize',position);
  document.addEventListener('scroll',event=>{
    if(panel.hidden||panel.contains(event.target))return;
    if(pinned)position();else close();
  },true);
})();
