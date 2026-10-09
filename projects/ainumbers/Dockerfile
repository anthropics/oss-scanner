FROM node:24-alpine
WORKDIR /src
COPY . .

# Gate 1: every kernel parses.
RUN node -e "const{execFileSync}=require('child_process');const fs=require('fs');const dir='/src/chaingraph/kernels';const files=fs.readdirSync(dir).filter(f=>f.endsWith('.kernel.mjs')).sort();for(const f of files){execFileSync(process.execPath,['--check',dir+'/'+f],{stdio:['ignore','ignore','inherit']})}console.log('syntax OK',files.length,'kernels')"

# Gate 2: every kernel imports offline (no network, no deps) and exports compute().
RUN node --input-type=module -e "const fs=await import('node:fs');const path=await import('node:path');const url=await import('node:url');const dir='/src/chaingraph/kernels';const files=fs.readdirSync(dir).filter(f=>f.endsWith('.kernel.mjs')).sort();const bad=[];for(const f of files){try{const m=await import(url.pathToFileURL(path.join(dir,f)).href);if(typeof m.compute!=='function')bad.push(f+': no compute export')}catch(e){bad.push(f+': '+e.message)}}if(bad.length){for(const b of bad.slice(0,10))console.error('  '+b);throw new Error('import/compute FAIL '+bad.length+'/'+files.length)}console.log('import OK',files.length,'kernels export compute()')"
