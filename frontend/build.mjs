import {build} from 'esbuild';
import {readFile,writeFile,mkdir} from 'node:fs/promises';

await build({
  entryPoints:['frontend/markdown-editor.js'],
  outfile:'journal/static/markdown-editor.js',
  bundle:true,
  minify:true,
  format:'iife',
  target:['es2020'],
  legalComments:'eof'
});
// Keep the license notices alongside the redistributed browser bundle.
const lock=JSON.parse(await readFile('package-lock.json','utf8'));
const notices=[];
for(const path of Object.keys(lock.packages).filter(p=>p.startsWith('node_modules/') && !lock.packages[p].dev)) {
  try {
    const license=await readFile(path+'/LICENSE','utf8');
    notices.push(path.replace('node_modules/','')+'\n'+license);
  } catch(error) {
    if(error.code!=='ENOENT') throw error;
  }
}
await writeFile('journal/static/markdown-editor.LICENSE.txt',notices.join('\n\n---\n\n'));
