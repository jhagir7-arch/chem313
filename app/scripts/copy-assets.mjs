// Ketcher serves its icons and fonts from a static folder; copy them into public/ so Vite ships
// them at /ketcher in dev and in the bundle. Runs on `npm install`.
import {cpSync, existsSync, rmSync} from 'node:fs';
import {dirname, resolve} from 'node:path';
import {fileURLToPath} from 'node:url';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const source = resolve(root, 'node_modules/ketcher-react/dist');
const target = resolve(root, 'public/ketcher');
if (!existsSync(source)) throw new Error(`ketcher-react is not installed: ${source}`);
rmSync(target, {recursive: true, force: true});
cpSync(source, target, {recursive: true});
console.log(`copied Ketcher static resources to ${target}`);
