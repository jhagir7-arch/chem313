import {useEffect, useMemo, useState} from 'react';
import type {Catalog, EngineStatus} from './engine';
import {electronCount, parseSdf, type Molecule} from './chem';
import type {Job, LogLine, Workbench} from './App';
import type {Tab} from './workspace';

const stateClass: Record<Job['state'], string> = {running: 'warn', converged: 'ok', failed: 'err'};
const stateGlyph: Record<Job['state'], string> = {running: '●', converged: '✓', failed: '✕'};

export function Navigator({molecules, molecule, jobs, selectedJob, onMolecule, onJob}: {
  molecules: Molecule[]; molecule: Molecule | null; jobs: Job[]; selectedJob: string | null; onMolecule: (m: Molecule) => void; onJob: (j: Job) => void;
}) {
  const starters = molecules.filter((m) => m.source === 'starter');
  const own = molecules.filter((m) => m.source !== 'starter');
  const row = (m: Molecule) => (
    <button key={m.id} type="button" className={`row${molecule?.id === m.id && selectedJob === null ? ' sel' : ''}`} onClick={() => onMolecule(m)}>
      <span className={`dot ${m.source === 'starter' ? 'ok' : 'on'}`} />{m.name}<span className="right mono">{m.formula ?? m.source}</span>
    </button>
  );
  return (
    <nav className="navigator" aria-label="Project">
      <div className="grp">Molecules</div>
      {starters.length === 0 && <div className="muted" style={{padding: '0 8px', height: 22, display: 'flex', alignItems: 'center'}}>loading catalog…</div>}
      {starters.map(row)}
      {own.length > 0 && <div className="grp">Your molecules</div>}
      {own.map(row)}
      <div className="grp">Calculations</div>
      {jobs.length === 0 && <div className="muted" style={{padding: '0 8px', height: 22, display: 'flex', alignItems: 'center'}}>none yet</div>}
      {[...jobs].reverse().map((j) => (
        <button key={j.id} type="button" className={`row${j.id === selectedJob ? ' sel' : ''}`} onClick={() => onJob(j)}>
          <span className={stateClass[j.state]}>{stateGlyph[j.state]}</span>
          {j.molecule.name} · {j.method}<span className="right mono">{j.startedAt.slice(-8)}</span>
        </button>
      ))}
      <div className="grp">Records</div>
      {jobs.filter((j) => j.artifacts.length).length === 0 && <div className="muted" style={{padding: '0 8px', height: 22, display: 'flex', alignItems: 'center'}}>none saved</div>}
      {[...jobs].reverse().filter((j) => j.artifacts.length).map((j) => (
        <button key={j.id} type="button" className="row" onClick={() => onJob(j)}>
          <span className="mono" style={{fontSize: 'var(--fs-xs)'}}>{j.artifacts.find((a) => a.relative_path.includes('/reports/'))?.relative_path.split('/').pop()?.slice(0, 12) ?? j.id}… · {j.artifacts.length} files</span>
        </button>
      ))}
    </nav>
  );
}

export function Inspector({molecule, job, guided, tab}: {molecule: Molecule | null; job: Job | null; guided: boolean; tab: Tab}) {
  const r = job?.result ?? null;
  const electrons = useMemo(() => (job?.geometry ? electronCount(parseSdf(job.geometry.sdf).atoms, r?.formal_charge ?? 0) : null), [job, r]);
  const step = tab === 'structure' || tab === '3d' ? 2 : tab === 'setup' ? 3 : 5;
  return (
    <aside className="inspector" aria-label="Inspector">
      <div className="sec">
        <h3>Identity</h3>
        <dl className="kv mono sel-text">
          <dt>Name</dt><dd>{r?.name ?? molecule?.name ?? '—'}</dd>
          <dt>Formula</dt><dd>{r?.formula ?? molecule?.formula ?? <span className="muted">after first run</span>}</dd>
          <dt>SMILES</dt><dd>{r?.canonical_smiles ?? molecule?.smiles ?? <span className="muted">from drawing</span>}</dd>
          <dt>InChIKey</dt><dd>{r?.inchikey ?? <span className="muted">after first run</span>}</dd>
          <dt>Charge</dt><dd>{r?.formal_charge ?? <span className="muted">—</span>}</dd>
          <dt>Electrons</dt><dd>{electrons ?? <span className="muted">—</span>}</dd>
          <dt>Atoms</dt><dd>{r?.atom_count ?? <span className="muted">—</span>}</dd>
        </dl>
      </div>
      <div className="sec">
        <h3>Checks</h3>
        <table>
          <tbody>
            <tr><td className={r ? 'ok' : 'muted'}>{r ? '✓' : '○'}</td><td>InChI round-trip</td><td className="muted">{r ? (r.identity_status === 'MATCH' ? '3D ↔ drawing match' : r.identity_status) : 'not run'}</td></tr>
            <tr><td className={r ? (r.converged ? 'ok' : 'err') : 'muted'}>{r ? (r.converged ? '✓' : '✕') : '○'}</td><td>Convergence</td><td className="muted">{r ? `status ${r.convergence_status}` : 'not run'}</td></tr>
            <tr><td className={job?.error ? 'err' : 'muted'}>{job?.error ? '✕' : '○'}</td><td>Engine</td><td className={job?.error ? 'err' : 'muted'} style={{whiteSpace: 'normal'}}>{job?.error ?? 'no error'}</td></tr>
          </tbody>
        </table>
      </div>
      {guided && (
        <div className="sec guided">
          <h3>Guided · step {step} of 6 · {tab === 'results' ? 'Results' : tab === 'setup' ? 'Setup' : 'Check'}</h3>
          {step === 2 && <p>Count the hydrogens in {molecule?.name ?? 'the molecule'} before you run. The drawing fixes the bonds; the 3D table only gives positions.</p>}
          {step === 3 && <p>Same seed gives the same starting shape. Change the seed and the energies will differ; the molecule will not.</p>}
          {step === 5 && r && <p>ΔE = {r.energy_change_kcal_mol.toFixed(3)} {r.energy_unit}. It compares two shapes of the same molecule in one force field, nothing else.</p>}
          {step === 5 && !r && <p>Run a calculation to see its result here.</p>}
        </div>
      )}
      <div className="sec">
        <h3>Source</h3>
        <dl className="kv sel-text">
          <dt>Origin</dt><dd>{molecule ? ({starter: 'Catalog starter', smiles: 'Typed SMILES', molblock: 'Imported or drawn'} as const)[molecule.source] : '—'}</dd>
          <dt>Geometry</dt><dd>{r ? `${r.embedding} · seed ${r.seed} · RDKit ${r.rdkit_version}` : <span className="muted">not generated</span>}</dd>
        </dl>
      </div>
    </aside>
  );
}

export function Console({jobs, log, workbench, status, catalog, collapsed, onToggle, onSelectJob, selectedJob}: {
  jobs: Job[]; log: LogLine[]; workbench: Workbench | null; status: EngineStatus | null; catalog: Catalog | null; collapsed: boolean; onToggle: () => void; onSelectJob: (id: string) => void; selectedJob: string | null;
}) {
  const [sub, setSub] = useState<'jobs' | 'console' | 'engines'>('jobs');
  const ready = !!status?.ready;
  return (
    <div className="console">
      <div className="tabs sub">
        <button type="button" className={`tab${sub === 'jobs' ? ' active' : ''}`} onClick={() => setSub('jobs')}>Jobs</button>
        <button type="button" className={`tab${sub === 'console' ? ' active' : ''}`} onClick={() => setSub('console')}>Console</button>
        <button type="button" className={`tab${sub === 'engines' ? ' active' : ''}`} onClick={() => setSub('engines')}>Engines</button>
        <button type="button" className="tab ctx" onClick={onToggle} aria-label={collapsed ? 'Expand console' : 'Collapse console'} style={{cursor: 'pointer'}}>{collapsed ? '▴' : '▾'}</button>
      </div>
      {!collapsed && (
        <div className="scroll">
          {sub === 'jobs' && (
            <table className="mono" style={{fontSize: 'var(--fs-sm)'}}>
              <thead><tr><th>Started</th><th>Molecule</th><th>Engine</th><th>Method</th><th>State</th><th className="num">Wall</th><th className="num">E final / kcal·mol⁻¹</th><th>Record</th></tr></thead>
              <tbody>
                {jobs.length === 0 && <tr><td colSpan={8} className="muted">No calculations yet. Press Run (⌘R).</td></tr>}
                {[...jobs].reverse().map((j) => (
                  <tr key={j.id} className={`clickable${j.id === selectedJob ? ' sel' : ''}`} onClick={() => onSelectJob(j.id)}>
                    <td>{j.startedAt}</td><td>{j.molecule.name}</td><td>{j.engine}</td><td>{j.method}</td>
                    <td className={stateClass[j.state]}>{j.state}</td>
                    <td className="num">{j.wallMs === null ? '—' : `${(j.wallMs / 1000).toFixed(2)} s`}</td>
                    <td className="num">{j.result ? j.result.final_energy_kcal_mol.toFixed(6) : '—'}</td>
                    <td className={j.artifacts.length ? '' : 'muted'} style={{whiteSpace: 'normal'}}>{j.artifacts.length ? `${j.artifacts.length} files` : j.error ? j.error : 'not saved'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          {sub === 'console' && (
            <div className="log">{log.length === 0 ? 'starting engine…' : log.map((l, i) => <div key={i}><span className="t">{l.t}</span> {l.text}</div>)}</div>
          )}
          {sub === 'engines' && (
            <table style={{fontSize: 'var(--fs-sm)'}}>
              <thead><tr><th>Engine</th><th>Version</th><th>Kind</th><th>Tier</th><th>Status</th></tr></thead>
              <tbody>
                {(catalog?.relaxation.force_fields ?? [{id: 'MMFF94', label: 'MMFF94', note: '', elements: []}]).map((f) => (
                  <tr key={f.id}><td>RDKit · {f.label}</td><td className="mono">{workbench?.engines?.rdkit ?? '—'}</td><td>Force field</td><td>Basic</td><td className={ready ? 'ok' : 'muted'}>{ready ? 'installed' : 'starting'}</td></tr>
                ))}
                <tr><td>SciPy</td><td className="mono">{workbench?.engines?.scipy ?? '—'}</td><td>Numerics</td><td>Basic</td><td className={ready ? 'ok' : 'muted'}>{ready ? 'installed' : 'starting'}</td></tr>
                <tr><td className="muted">PySCF</td><td className="mono muted">—</td><td className="muted">Quantum</td><td className="muted">Science</td><td className="warn">pack not installed</td></tr>
                <tr><td className="muted">ORCA</td><td className="mono muted">—</td><td className="muted">Quantum</td><td className="muted">Engines</td><td className="muted">{(workbench?.orca_engine?.status ?? 'not detected').toLowerCase().replace(/_/g, ' ')}</td></tr>
                <tr><td className="muted">Qwen</td><td className="mono muted">—</td><td className="muted">Assistant</td><td className="muted">Max</td><td className="muted">{(workbench?.llm?.status ?? 'not installed').toLowerCase().replace(/_/g, ' ')}</td></tr>
              </tbody>
            </table>
          )}
        </div>
      )}
    </div>
  );
}

export function StatusBar({status, workbench, running, done, queued}: {status: EngineStatus | null; workbench: Workbench | null; running: number; done: number; queued: number}) {
  const engine = status?.error ? <><span className="dot err" /> Engine failed</> : status?.ready ? <><span className={`dot ${running ? 'warn' : 'ok'}`} /> Engine {running ? 'busy' : 'ready'} · RDKit {workbench?.engines?.rdkit ?? '…'}</> : <><span className="dot warn" /> Engine starting…</>;
  return (
    <div className="statusbar">
      <span>{engine}</span>
      <span>Tier: Basic</span>
      <span>Jobs {running} running · {queued} queued · {done} done</span>
      <span className="spacer" />
      <span title={workbench?.data_directory ?? status?.data_dir ?? ''}>Data {(workbench?.data_directory ?? status?.data_dir ?? '').replace(/^\/Users\/[^/]+/, '~').replace(/^C:\\Users\\[^\\]+/, '~')}</span>
      <span>v{__APP_VERSION__}</span>
    </div>
  );
}

export type PaletteCommand = {id: string; label: string; kbd?: string; run: () => void};

const looksLikeSmiles = (s: string) => /^[A-Za-z0-9@+\-\[\]()=#$%\\/.:]+$/.test(s) && /[A-Za-z]/.test(s);

export function Palette({commands, onClose, onSmiles}: {commands: PaletteCommand[]; onClose: () => void; onSmiles: (smiles: string) => void}) {
  const [q, setQ] = useState('');
  const [active, setActive] = useState(0);
  const list = useMemo(() => {
    const matches = commands.filter((c) => c.label.toLowerCase().includes(q.toLowerCase()));
    const trimmed = q.trim();
    if (trimmed && looksLikeSmiles(trimmed)) matches.push({id: 'smiles-' + trimmed, label: `Add molecule from SMILES: ${trimmed}`, kbd: 'SMILES', run: () => onSmiles(trimmed)});
    return matches;
  }, [commands, q, onSmiles]);
  useEffect(() => setActive(0), [q]);
  const choose = (c: PaletteCommand | undefined) => { if (c) { onClose(); c.run(); } };
  return (
    <div className="palette-backdrop" onMouseDown={onClose}>
      <div className="palette" role="dialog" aria-label="Command palette" onMouseDown={(e) => e.stopPropagation()}>
        <input
          autoFocus type="text" value={q} placeholder="Type a command, a molecule name or a SMILES" aria-label="Command" onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'ArrowDown') { e.preventDefault(); setActive((a) => Math.min(a + 1, list.length - 1)); }
            else if (e.key === 'ArrowUp') { e.preventDefault(); setActive((a) => Math.max(a - 1, 0)); }
            else if (e.key === 'Enter') { e.preventDefault(); choose(list[active]); }
            else if (e.key === 'Escape') onClose();
          }}
        />
        {list.map((c, i) => (
          <button key={c.id} type="button" className={`item${i === active ? ' active' : ''}`} onMouseEnter={() => setActive(i)} onClick={() => choose(c)}>
            {c.label}{c.kbd && <span className="kbd">{c.kbd}</span>}
          </button>
        ))}
        {list.length === 0 && <div className="empty">No matching command</div>}
      </div>
    </div>
  );
}

export function NewMoleculeDialog({initialSmiles, onClose, onAdd}: {initialSmiles: string; onClose: () => void; onAdd: (name: string, smiles: string) => void}) {
  const [name, setName] = useState('');
  const [smiles, setSmiles] = useState(initialSmiles);
  const ok = smiles.trim().length > 0 && looksLikeSmiles(smiles.trim());
  return (
    <div className="palette-backdrop" onMouseDown={onClose}>
      <div className="palette" role="dialog" aria-label="New molecule" onMouseDown={(e) => e.stopPropagation()} style={{padding: 'var(--sp-5)'}}>
        <h3 style={{margin: '0 0 var(--sp-4)', fontSize: 'var(--fs-xs)', fontWeight: 600, letterSpacing: 'var(--track-label)', textTransform: 'uppercase', color: 'var(--text-muted)'}}>New molecule</h3>
        <div className="field" style={{gridTemplateColumns: '90px 1fr'}}>
          <label htmlFor="nm-smiles">SMILES</label><input id="nm-smiles" className="mono" autoFocus value={smiles} onChange={(e) => setSmiles(e.target.value)} onKeyDown={(e) => { if (e.key === 'Enter' && ok) onAdd(name.trim(), smiles.trim()); }} placeholder="e.g. CC(=O)O" />
          <label htmlFor="nm-name">Name</label><input id="nm-name" value={name} onChange={(e) => setName(e.target.value)} placeholder="optional" />
        </div>
        <p className="muted" style={{margin: 'var(--sp-4) 0 0', fontSize: 'var(--fs-sm)'}}>The engine checks the structure, element coverage and size when you run. Or draw it on the Structure tab.</p>
        <div style={{display: 'flex', gap: 6, marginTop: 'var(--sp-5)', justifyContent: 'flex-end'}}>
          <button type="button" className="tool" onClick={onClose}>Cancel</button>
          <button type="button" className="tool primary" disabled={!ok} onClick={() => onAdd(name.trim(), smiles.trim())}>Add</button>
        </div>
      </div>
    </div>
  );
}
