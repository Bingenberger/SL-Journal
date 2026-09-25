// Builds journal/templates/icons.html: one inline sprite with the Phosphor
// symbols the interface uses. Inline instead of a separate file because every
// response is sent with Cache-Control: no-store, so a second request would
// never be cached anyway.
import {readFile,writeFile} from 'node:fs/promises';

const source='node_modules/@phosphor-icons/core/assets/regular/';

// Interface slot -> Phosphor icon. Slot names describe the role, not the shape,
// so a later set can be swapped in without touching the templates.
const ICONS={
  cockpit:'squares-four', inbox:'tray', tasks:'check-square', projects:'folder', cases:'clipboard-text', tags:'tag',
  entries:'list-bullets', processes:'arrows-clockwise', people:'users',
  more:'dots-three', settings:'gear', logout:'sign-out', search:'magnifying-glass', plus:'plus',
  microphone:'microphone', handwriting:'pen-nib', newentry:'note-pencil', calendar:'calendar-blank', journal:'pencil-simple', phone:'phone',
  mail:'envelope-simple', mailin:'arrow-down-left', mailout:'arrow-up-right', person:'user',
  attachment:'paperclip', download:'download-simple',
  external:'arrow-square-out', forward:'arrow-right', back:'arrow-left',
  previous:'caret-left', next:'caret-right', check:'check', close:'x',
  sparkle:'sparkle', empty:'circle-dashed', subtask:'arrow-elbow-down-right',
  // Handlungen: Bearbeiten, Löschen, Speichern, Filtern, Verknüpfen …
  edit:'pencil-simple', delete:'trash', filter:'funnel', reset:'arrow-counter-clockwise',
  link:'link-simple', upload:'upload-simple', eye:'eye', qr:'qr-code', stop:'stop-circle',
  pause:'pause', play:'play', menu:'list', sidebar:'sidebar-simple',
  // Dateibrowser der Nextcloud
  folder:'folder', file:'file', home:'house'
};

const symbols=[];
for(const [slot,name] of Object.entries(ICONS)) {
  const file=await readFile(source+name+'.svg','utf8');
  const viewBox=file.match(/viewBox="([^"]+)"/)[1];
  const body=file.replace(/^[\s\S]*?<svg[^>]*>/,'').replace(/<\/svg>\s*$/,'').trim();
  // Paths inherit the surrounding text colour through .icon{fill:currentColor}.
  symbols.push(`<symbol id="i-${slot}" viewBox="${viewBox}">${body.replace(/\s+/g,' ')}</symbol>`);
}
await writeFile('journal/templates/icons.html',
  '{# Erzeugt von frontend/build-icons.mjs – nicht von Hand bearbeiten. #}\n'+
  '<svg class="icon-sprite" aria-hidden="true">'+symbols.join('')+'</svg>\n');

// Keep the licence notice alongside the redistributed artwork.
const licence=await readFile('node_modules/@phosphor-icons/core/LICENSE','utf8');
const version=JSON.parse(await readFile('node_modules/@phosphor-icons/core/package.json','utf8')).version;
await writeFile('journal/static/icons.LICENSE.txt',
  `Phosphor Icons ${version} (https://phosphoricons.com)\n\n${licence}`);

console.log(`${symbols.length} Symbole nach journal/templates/icons.html geschrieben.`);
