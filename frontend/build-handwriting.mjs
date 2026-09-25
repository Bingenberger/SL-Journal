import {build} from 'esbuild';
import {cp,mkdir,readFile,writeFile} from 'node:fs/promises';
const out='journal/static/excalidraw';
await mkdir(out,{recursive:true});
await build({
  entryPoints:['frontend/handwriting.js'],outdir:out,bundle:true,minify:true,
  splitting:true,format:'esm',target:['es2020'],conditions:['production'],
  define:{'process.env.NODE_ENV':'"production"','process.env.IS_PREACT':'false'},
  plugins:[{
    name:'local-only',
    setup(build){
      let fonts=0,environment=0;
      build.onEnd(()=>{
        if(fonts!==1)throw new Error('Expected exactly one Excalidraw font loader.');
        if(environment!==1)throw new Error('Expected exactly one Excalidraw environment module.');
      });
      build.onLoad({filter:/excalidraw\/dist\/prod\/.*\.js$/},async args=>{
        const source=await readFile(args.path,'utf8');
        if(source.includes('static createUrls(')){
          // Upstream appends its CDN even when a local asset path is configured.
          // Keep all font requests on the journal server.
          const pattern=/return ([\w$]+)\.push\(new URL\(([\w$]+),[\w$]+\.ASSETS_FALLBACK_URL\)\),\1/;
          if(!pattern.test(source))throw new Error('Excalidraw font loader changed; review local-only patch.');
          fonts++;
          return {contents:source.replace(pattern,'return $1'),loader:'js'};
        }
        if(source.includes('VITE_APP_FIREBASE_CONFIG')){
          // Das Journal zeichnet ausschließlich lokal: keine Zusammenarbeit, keine
          // Bibliothek, kein Cloud-Backend. Excalidraw liefert die Adressen und den
          // öffentlichen Firebase-Schlüssel seines eigenen Dienstes trotzdem mit.
          // Sie gehören nicht in den Auslieferungsstand des Journals.
          const keys=['VITE_APP_BACKEND_V2_GET_URL','VITE_APP_BACKEND_V2_POST_URL',
                      'VITE_APP_LIBRARY_URL','VITE_APP_LIBRARY_BACKEND','VITE_APP_PLUS_LP',
                      'VITE_APP_PLUS_APP','VITE_APP_AI_BACKEND','VITE_APP_WS_SERVER_URL',
                      'VITE_APP_FIREBASE_CONFIG','VITE_APP_PLUS_EXPORT_PUBLIC_KEY'];
          let contents=source;
          for(const key of keys){
            const pattern=new RegExp(key+':(?:"[^"]*"|\'[^\']*\'|`[^`]*`)');
            if(!pattern.test(contents))throw new Error('Excalidraw environment changed; review '+key+'.');
            contents=contents.replace(pattern,key+':""');
          }
          if(/AIza[\w-]{20}/.test(contents))throw new Error('Excalidraw environment still carries a key.');
          environment++;
          return {contents,loader:'js'};
        }
      });
    }
  }],
  loader:{'.woff2':'file','.ttf':'file','.wasm':'file'},legalComments:'linked',
});
await cp('node_modules/@excalidraw/excalidraw/dist/prod/fonts',out+'/fonts',{recursive:true});
const lock=JSON.parse(await readFile('package-lock.json','utf8'));
const notices=[];
for(const path of Object.keys(lock.packages).filter(p=>p.startsWith('node_modules/')&&!lock.packages[p].dev)){
  for(const name of ['LICENSE','LICENSE.txt','LICENSE.md','license']){
    try{notices.push(path+'\n'+await readFile(path+'/'+name,'utf8'));break;}
    catch(e){if(e.code!=='ENOENT')throw e;}
  }
}
await writeFile(out+'/LICENSE.txt',notices.join('\n\n---\n\n'));
