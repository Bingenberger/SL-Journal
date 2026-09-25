import '@excalidraw/excalidraw/index.css';
window.EXCALIDRAW_ASSET_PATH='/static/excalidraw/';
import('./handwriting-app.jsx').catch(error=>{
  console.error(error);
  const status=document.getElementById('sheet-status');
  status.dataset.error='true';
  status.textContent='Der Zeicheneditor konnte nicht geladen werden. Bitte die Seite neu laden.';
});
