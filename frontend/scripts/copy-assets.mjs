// Ketcher static icons/templates; copies package-provided assets, not vendored source.
import {cpSync,mkdirSync,existsSync} from 'node:fs';
import {resolve} from 'node:path';
const from=resolve('node_modules/ketcher-react/dist');
const to=resolve('public/ketcher');
if(!existsSync(from))throw new Error('Ketcher installation missing: '+from);
mkdirSync(to,{recursive:true});
cpSync(from,to,{recursive:true,force:true});
console.log('Ketcher static assets copied to /ketcher');
