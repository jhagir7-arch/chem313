import {forwardRef, useEffect, useImperativeHandle, useRef} from 'react';
import {Editor} from 'ketcher-react';
import {StandaloneStructServiceProvider} from 'ketcher-standalone';
import type {Ketcher} from 'ketcher-core';
import 'ketcher-react/dist/index.css';
import type {Molecule} from './chem';
import type {DrawingStore} from './drawing';

const provider = new StandaloneStructServiceProvider();
export type EditorHandle = {snapshot: (id: string) => Promise<string>};

const StructureEditor = forwardRef<EditorHandle, {molecule: Molecule | null; drawings: DrawingStore}>(function StructureEditor({molecule, drawings}, ref) {
  const ketcher = useRef<Ketcher | null>(null);
  const loaded = useRef<string | null>(null);
  const pending = useRef<Promise<void>>(Promise.resolve());
  const current = useRef(molecule);
  current.current = molecule;

  const load = (k: Ketcher, m: Molecule | null) => {
    pending.current = pending.current.catch(() => undefined).then(async () => {
      if (loaded.current === m?.id) return;
      if (loaded.current) drawings.save(loaded.current, await k.getMolfile('v2000'));
      loaded.current = null;
      const text = m ? drawings.get(m.id) ?? m.molblock ?? m.smiles ?? '' : '';
      await k.setMolecule(text);
      loaded.current = m?.id ?? null;
    });
    // A subsequent selection can recover from a failed load, but snapshot must observe it.
    pending.current.catch((e) => console.error('Ketcher could not load the molecule', e));
  };
  useEffect(() => { if (ketcher.current) load(ketcher.current, molecule); }, [molecule]);
  useImperativeHandle(ref, () => ({snapshot: async (id) => {
    await pending.current;
    if (!ketcher.current || loaded.current !== id) throw new Error('Structure editor is not ready');
    return drawings.snapshot(id, () => ketcher.current!.getMolfile('v2000'));
  }}), [drawings]);
  return <div style={{position: 'absolute', inset: 0}}><Editor staticResourcesUrl="/ketcher" structServiceProvider={provider}
    errorHandler={(message) => console.error('Ketcher:', message)}
    onInit={(k: Ketcher) => { ketcher.current = k; load(k, current.current); }} /></div>;
});
export default StructureEditor;
