import {createHash} from 'node:crypto';
import {existsSync, readFileSync, readdirSync, writeFileSync} from 'node:fs';
import {dirname, relative, resolve, sep} from 'node:path';
import {fileURLToPath} from 'node:url';

const frontend = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const digest = path => createHash('sha256').update(readFileSync(path)).digest('hex');
const files = root => readdirSync(root, {withFileTypes:true}).flatMap(entry => {
  const path = resolve(root, entry.name);
  if (entry.isSymbolicLink()) throw new Error('Symlink in emitted UI: ' + entry.name);
  return entry.isDirectory() ? files(path) : [path];
});

export function uiLicenseProvenance() {
  const locked = JSON.parse(readFileSync(resolve(frontend, 'package-lock.json'), 'utf8')).packages;
  return {
    name:'openchem-ui-license-provenance',
    writeBundle(options, bundle) {
      const output = resolve(options.dir || 'dist');
      const packages = new Set();
      const identify = id => {
        const clean = id.replaceAll('\\', '/').split('?')[0];
        const base = frontend.replaceAll('\\', '/') + '/';
        const position = clean.indexOf(base);
        if (position < 0) return;
        const local = clean.slice(position + base.length);
        if (!local.startsWith('node_modules/')) return;
        let directory = dirname(resolve(frontend, local));
        while (directory.startsWith(frontend + sep)) {
          const location = relative(frontend, directory).split(sep).join('/');
          if (locked[location] && existsSync(resolve(directory, 'package.json'))) {
            packages.add(location);
            return;
          }
          directory = dirname(directory);
        }
        throw new Error('Emitted dependency has no package owner');
      };
      for (const item of Object.values(bundle)) {
        if (item.type === 'chunk') Object.keys(item.modules).forEach(identify);
        else (item.originalFileNames || []).forEach(identify);
      }
      // copy-assets.mjs copies only this package's static distribution. Check
      // every copied file against its installed source before attributing it.
      const copied = resolve(output, 'ketcher');
      if (existsSync(copied)) {
        for (const file of files(copied)) {
          const source = resolve(frontend, 'node_modules/ketcher-react/dist', relative(copied, file));
          if (!existsSync(source) || digest(file) !== digest(source)) throw new Error('Unattributed Ketcher asset');
        }
        packages.add('node_modules/ketcher-react');
      }
      const inventory = files(output).filter(path => relative(output, path) !== 'ui-provenance.json').map(path => ({
        path:relative(output, path).split(sep).join('/'), sha256:digest(path),
      })).sort((a,b) => a.path.localeCompare(b.path));
      writeFileSync(resolve(output, 'ui-provenance.json'), JSON.stringify({
        schema:'openchem.ui-provenance.v1', packages:[...packages].sort(), files:inventory,
      }, null, 2) + '\n');
    },
  };
}
