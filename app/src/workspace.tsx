import {Suspense, lazy, useMemo, useState, type RefObject} from 'react';
import type {EditorHandle} from './editor';
import type {DrawingStore} from './drawing';
import {convertEnergy, dist, fmt, parseSdf, unitLabel, type EnergyUnit, type Molecule} from './chem';
import type {Catalog} from './engine';
import type {Job, RelaxParams, Workbench} from './App';

export type Tab = 'structure' | '3d' | 'setup' | 'results';
const TABS: {id: Tab; label: string}[] = [{id: 'structure', label: 'Structure'}, {id: '3d', label: '3D'}, {id: 'setup', label: 'Setup'}, {id: 'results', label: 'Results'}];

// Ketcher and 3Dmol are large; load them only when their tab is first shown.
const StructureEditor = lazy(() => import('./editor'));
const Viewer3D = lazy(() => import('./viewer3d'));

export type WorkspaceProps = {
  tab: Tab; onTab: (t: Tab) => void; molecule: Molecule | null; job: Job | null; jobs: Job[]; params: RelaxParams; onParams: (p: RelaxParams) => void;
  catalog: Catalog | null; onRun: () => void; canRun: boolean; workbench: Workbench | null; onSelectJob: (id: string) => void;
  editorRef: RefObject<EditorHandle>; drawings: DrawingStore; onAddMolecule: (m: Molecule) => void;
};

export function Workspace(props: WorkspaceProps) {
  const {tab, onTab, molecule, job} = props;
  return (
    <main className="workspace">
      <div className="tabs" role="tablist">
        {TABS.map((t) => (
          <button key={t.id} type="button" role="tab" aria-selected={tab === t.id} className={`tab${tab === t.id ? ' active' : ''}`} onClick={() => onTab(t.id)}>{t.label}</button>
        ))}
        <span className="tab ctx mono muted">{molecule?.name ?? 'no molecule'}{job ? ` · ${job.method} · ${job.startedAt}` : ' · no calculation yet'}</span>
      </div>
      <div className="content">
        <Suspense fallback={<div className="empty">Loading…</div>}>
          <div style={{display: tab === 'structure' ? 'contents' : 'none'}}><Structure {...props} /></div>
          {tab === '3d' && <ThreeD job={job} />}
          {tab === 'setup' && <Setup {...props} />}
          {tab === 'results' && <Results job={job} onTab={onTab} catalog={props.catalog} />}
        </Suspense>
      </div>
    </main>
  );
}

function Structure({molecule, job, editorRef, drawings}: WorkspaceProps) {
  const geom = useMemo(() => (job?.geometry ? parseSdf(job.geometry.sdf) : null), [job]);
  return (
    <div className="split">
      <div style={{flex: '3 1 0'}}>
        <div className="pane-head"><span className="label">2D · drawing</span><span className="spacer" /><span className="muted" style={{fontSize: 'var(--fs-xs)'}}>Ketcher · edits become the molecule you run</span></div>
        <div style={{flexGrow: 1, minHeight: 0, position: 'relative', background: 'var(--bg-canvas)'}}>
          <StructureEditor ref={editorRef} molecule={molecule} drawings={drawings} />
        </div>
      </div>
      <div style={{flex: '2 1 0'}}>
        <div className="pane-head"><span className="label">Atoms · {job?.geometry ? 'final geometry' : 'no geometry yet'}</span></div>
        <div style={{overflow: 'auto', flexGrow: 1}}>
          {geom ? (
            <table className="mono sel-text" style={{fontSize: 'var(--fs-sm)'}}>
              <thead><tr><th className="num">#</th><th>El</th><th className="num">x / Å</th><th className="num">y / Å</th><th className="num">z / Å</th></tr></thead>
              <tbody>{geom.atoms.map((a, i) => <tr key={i}><td className="num">{i + 1}</td><td>{a.el}</td><td className="num">{fmt(a.x, 4)}</td><td className="num">{fmt(a.y, 4)}</td><td className="num">{fmt(a.z, 4)}</td></tr>)}</tbody>
            </table>
          ) : <div className="empty">Run a calculation (⌘R) to get coordinates.</div>}
        </div>
      </div>
    </div>
  );
}

function ThreeD({job}: {job: Job | null}) {
  const [which, setWhich] = useState<'final' | 'initial'>('final');
  const sdf = job?.geometry ? (which === 'final' ? job.geometry.sdf : job.geometry.initial_sdf) : null;
  return (
    <>
      <div className="pane-head">
        <span className="label">3D · {which} geometry</span><span className="spacer" />
        <button type="button" className={`tool sm${which === 'initial' ? ' primary' : ''}`} onClick={() => setWhich('initial')}>Initial</button>
        <button type="button" className={`tool sm${which === 'final' ? ' primary' : ''}`} onClick={() => setWhich('final')}>Final</button>
      </div>
      {sdf ? <Viewer3D sdf={sdf} /> : <div className="viewport"><span className="muted">No geometry yet. Run a calculation (⌘R).</span></div>}
    </>
  );
}

function Setup({molecule, jobs, params, onParams, catalog, onRun, canRun, workbench, onSelectJob}: WorkspaceProps) {
  const rel = catalog?.relaxation;
  const orca = (workbench?.orca_engine?.status ?? 'NOT_CONFIGURED').toLowerCase().replace(/_/g, ' ');
  const clamp = (v: number, lo: number, hi: number) => Math.max(lo, Math.min(hi, Number.isFinite(v) ? v : lo));
  return (
    <>
      <div className="sec" style={{padding: '10px 12px'}}>
        <h3>Engine</h3>
        <table>
          <thead><tr><th /><th>Engine</th><th>Method</th><th>Kind</th><th>Tier</th><th>Status</th><th /></tr></thead>
          <tbody>
            {(rel?.force_fields ?? []).map((f) => (
              <tr key={f.id} className={params.force_field === f.id ? 'sel' : ''}>
                <td><input type="radio" name="engine" checked={params.force_field === f.id} onChange={() => onParams({...params, force_field: f.id})} aria-label={`RDKit ${f.label}`} /></td>
                <td>RDKit {workbench?.engines?.rdkit ?? ''}</td><td>{f.label} relaxation</td><td>Force field</td><td>Basic</td><td className="ok">installed</td><td className="muted" style={{whiteSpace: 'normal'}}>{f.note}</td>
              </tr>
            ))}
            {!rel && <tr><td colSpan={7} className="muted">loading catalog…</td></tr>}
            <tr><td><input type="radio" name="engine" disabled aria-label="PySCF" /></td><td className="muted">PySCF</td><td className="muted">HF / def2-SVP single point</td><td className="muted">Quantum</td><td className="muted">Science</td><td className="warn">pack not installed</td><td><button type="button" className="tool sm" disabled>Install Science pack</button></td></tr>
            <tr><td><input type="radio" name="engine" disabled aria-label="ORCA" /></td><td className="muted">ORCA</td><td className="muted">HF / def2-SVP single point</td><td className="muted">Quantum</td><td className="muted">Engines</td><td className="muted">{orca} · licensed separately</td><td><button type="button" className="tool sm" disabled>Locate executable…</button></td></tr>
          </tbody>
        </table>
      </div>
      <div style={{display: 'flex', borderBottom: 'var(--bw) solid var(--border-subtle)'}}>
        <div className="sec" style={{flex: '1 1 0', borderBottom: 0, borderRight: 'var(--bw) solid var(--border-subtle)', padding: '10px 12px'}}>
          <h3>Parameters · {params.force_field} relaxation</h3>
          <div className="field">
            <label htmlFor="emb">Starting geometry</label><select id="emb" disabled><option>{rel?.embedding ?? 'ETKDGv3'} embedding</option></select><span className="hint">Distance-geometry start; bonds come from the drawing.</span>
            <label htmlFor="seed">Random seed</label><input id="seed" className="mono" type="number" min={rel?.limits.seed.min ?? 0} max={rel?.limits.seed.max ?? 2147483647} value={params.seed} onChange={(e) => onParams({...params, seed: clamp(Number(e.target.value), rel?.limits.seed.min ?? 0, rel?.limits.seed.max ?? 2147483647)})} /><span className="hint">Same seed → same start, same result.</span>
            <label htmlFor="iter">Max iterations</label><input id="iter" className="mono" type="number" min={rel?.limits.max_iterations.min ?? 1} max={rel?.limits.max_iterations.max ?? 10000} value={params.max_iterations} onChange={(e) => onParams({...params, max_iterations: clamp(Number(e.target.value), rel?.limits.max_iterations.min ?? 1, rel?.limits.max_iterations.max ?? 10000)})} /><span className="hint">{rel ? `${rel.limits.max_iterations.min}–${rel.limits.max_iterations.max}` : ''}</span>
            <label htmlFor="ftol">Force tolerance</label><input id="ftol" className="mono" type="text" value={rel?.limits.force_tolerance ?? ''} readOnly /><span className="hint">kcal·mol⁻¹·Å⁻¹ · fixed by the engine</span>
            <label htmlFor="etol">Energy tolerance</label><input id="etol" className="mono" type="text" value={rel?.limits.energy_tolerance ?? ''} readOnly /><span className="hint">kcal·mol⁻¹ · fixed by the engine</span>
          </div>
          <div style={{marginTop: 12, display: 'flex', gap: 6}}>
            <button type="button" className="tool primary" onClick={onRun} disabled={!canRun}>Run  ⌘R</button>
          </div>
        </div>
        <div className="sec" style={{width: 360, flexShrink: 0, borderBottom: 0, padding: '10px 12px'}}>
          <h3>Input review</h3>
          <dl className="kv mono sel-text">
            <dt>Molecule</dt><dd>{molecule ? `${molecule.name}${molecule.formula ? ` · ${molecule.formula}` : ''}` : '—'}</dd>
            <dt>Input</dt><dd style={{whiteSpace: 'pre-wrap'}}>{molecule?.source === 'molblock' ? 'molfile (drawn / imported)' : molecule?.smiles ?? '—'}</dd>
            <dt>Engine</dt><dd>RDKit {params.force_field} · local · no licence</dd>
            <dt>Limits</dt><dd>{rel ? `≤ ${rel.limits.heavy_atoms.max} heavy atoms · one fragment` : '—'}</dd>
            <dt>Output</dt><dd>initial.sdf · final.sdf · report.json</dd>
          </dl>
          <p className="muted" style={{margin: '10px 0 0', fontSize: 'var(--fs-sm)'}}>{rel?.scope ?? ''}</p>
        </div>
      </div>
      <div className="sec" style={{padding: '10px 12px', borderBottom: 0}}>
        <h3>Queue</h3>
        <table className="mono" style={{fontSize: 'var(--fs-sm)'}}>
          <thead><tr><th>Started</th><th>Molecule</th><th>Engine · method</th><th>State</th><th style={{width: 220}}>Progress</th><th className="num">E / kcal·mol⁻¹</th><th className="num">Wall</th><th /></tr></thead>
          <tbody>
            {jobs.length === 0 && <tr><td colSpan={8} className="muted">Queue is empty.</td></tr>}
            {[...jobs].reverse().map((j) => (
              <tr key={j.id}>
                <td>{j.startedAt}</td><td>{j.molecule.name}</td><td>{j.engine} · {j.method}</td>
                <td className={j.state === 'converged' ? 'ok' : j.state === 'failed' ? 'err' : 'warn'}>{j.state}</td>
                <td><div className="bar"><span className={j.state === 'converged' ? 'done' : ''} style={{width: j.state === 'running' ? '50%' : '100%'}} /></div></td>
                <td className="num">{j.result ? j.result.final_energy_kcal_mol.toFixed(6) : '—'}</td>
                <td className="num">{j.wallMs === null ? '—' : `${(j.wallMs / 1000).toFixed(2)} s`}</td>
                <td>{j.result && <button type="button" className="tool sm" onClick={() => onSelectJob(j.id)}>Open</button>}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}

function Results({job, onTab, catalog}: {job: Job | null; onTab: (t: Tab) => void; catalog: Catalog | null}) {
  const r = job?.result ?? null;
  const [unit, setUnit] = useState<EnergyUnit>('kcal');
  const diff = useMemo(() => {
    if (!job?.geometry) return null;
    const a = parseSdf(job.geometry.initial_sdf).atoms, b = parseSdf(job.geometry.sdf).atoms;
    const rows = b.map((q, i) => ({i, el: q.el, p: a[i], q, d: a[i] ? dist(a[i], q) : NaN}));
    const heavy = rows.filter((x) => x.el !== 'H');
    const largest = rows.reduce((m, x) => (x.d > m.d ? x : m), rows[0]);
    return {rows, largest, heavyMax: Math.max(...heavy.map((x) => x.d)), bonds: parseSdf(job.geometry.sdf).bonds.length};
  }, [job]);
  if (!job) return <div className="empty">Select a calculation in the Navigator, or run one (⌘R).</div>;
  if (!r) return <div className="err-box">{job.state === 'running' ? 'Running…' : job.error ?? 'No result.'}</div>;
  const digits = unit === 'Eh' ? 8 : 6;
  const e0 = convertEnergy(r.initial_energy_kcal_mol, unit), e1 = convertEnergy(r.final_energy_kcal_mol, unit);
  const top = Math.max(e0, e1, 0), bottom = Math.min(e0, e1, 0);
  const span = top - bottom || 1;
  const y = (v: number) => 30 + ((top - v) / span) * 180;
  return (
    <>
      <div className="stats sel-text">
        <div className="stat"><div className="l">E initial</div><div className="v">{fmt(e0, digits)}</div><div className="u">{unitLabel(unit)}</div></div>
        <div className="stat"><div className="l">E final</div><div className="v">{fmt(e1, digits)}</div><div className="u">{unitLabel(unit)}</div></div>
        <div className="stat"><div className="l">ΔE</div><div className="v">{fmt(e1 - e0, digits)}</div><div className="u">{unitLabel(unit)} · same molecule, same force field</div></div>
        <div className="stat"><div className="l">Convergence</div><div className={`v ${r.converged ? 'ok' : 'err'}`}>{r.convergence_status}</div><div className="u">RDKit status · force &lt; {r.force_tolerance}</div></div>
        <div className="stat"><div className="l">Identity</div><div className={`v ${r.identity_status === 'MATCH' ? 'ok' : 'err'}`}>{r.identity_status}</div><div className="u">InChIKey initial = final</div></div>
        <div className="stat scope"><div className="l">Scope</div><div style={{fontSize: 'var(--fs-base)', maxWidth: 420}}>{r.scope ?? catalog?.relaxation.scope ?? ''}</div></div>
      </div>
      <div className="split">
        <div>
          <div className="pane-head">
            <span className="label">Energy · before / after</span><span className="spacer" />
            {(['kcal', 'kJ', 'Eh'] as const).map((u) => <button key={u} type="button" className={`tool sm${unit === u ? ' primary' : ''}`} onClick={() => setUnit(u)}>{u === 'kcal' ? 'kcal/mol' : u === 'kJ' ? 'kJ/mol' : 'Eh'}</button>)}
          </div>
          <div className="canvas" style={{backgroundImage: 'none'}}>
            <svg width="420" height="250" viewBox="0 0 420 250" role="img" aria-label={`Energy before ${fmt(e0, 3)} and after ${fmt(e1, 3)} ${unitLabel(unit)}`}>
              <line x1="60" y1="20" x2="60" y2="220" stroke="var(--border)" />
              <line x1="56" y1={y(0)} x2="400" y2={y(0)} stroke="var(--border)" />
              <text x="52" y={y(0) + 4} fill="var(--text-muted)" fontSize="10" fontFamily="var(--font-mono)" textAnchor="end">0</text>
              <rect x="120" y={Math.min(y(e0), y(0))} width="90" height={Math.abs(y(e0) - y(0))} fill="var(--el-c)" />
              <text x="165" y={y(e0) + (e0 >= 0 ? -6 : 14)} fill="var(--text-strong)" fontSize="12" fontFamily="var(--font-mono)" textAnchor="middle">{fmt(e0, 3)}</text>
              <text x="165" y="238" fill="var(--text-secondary)" fontSize="11" textAnchor="middle">initial · {r.embedding}</text>
              <rect x="260" y={Math.min(y(e1), y(0))} width="90" height={Math.abs(y(e1) - y(0))} fill="var(--accent)" />
              <text x="305" y={y(e1) + (e1 >= 0 ? -6 : 14)} fill="var(--text-strong)" fontSize="12" fontFamily="var(--font-mono)" textAnchor="middle">{fmt(e1, 3)}</text>
              <text x="305" y="238" fill="var(--text-secondary)" fontSize="11" textAnchor="middle">final · {r.force_field}</text>
            </svg>
          </div>
          <div style={{padding: '6px 10px', borderTop: 'var(--bw) solid var(--border-subtle)', display: 'flex', gap: 16, alignItems: 'center', fontSize: 'var(--fs-sm)'}}>
            <span className="muted">Reference:</span><a href="https://cccbdb.nist.gov/" target="_blank" rel="noreferrer" style={{color: 'var(--accent-text)'}}>NIST CCCBDB</a>
            <span className="muted">lookup only — no compatible observable for a force-field energy.</span>
          </div>
        </div>
        <div style={{flex: '0 0 440px'}}>
          <div className="pane-head"><span className="label">Geometry change</span><span className="spacer" /><button type="button" className="tool sm" onClick={() => onTab('3d')}>Show in 3D</button></div>
          <div style={{overflow: 'auto', flexGrow: 1}}>
            {diff ? (
              <table className="mono sel-text" style={{fontSize: 'var(--fs-sm)'}}>
                <thead><tr><th className="num">#</th><th>El</th><th className="num">x₀ / Å</th><th className="num">x₁ / Å</th><th className="num">y₀</th><th className="num">y₁</th><th className="num">z₀</th><th className="num">z₁</th><th className="num">|Δ| / Å</th></tr></thead>
                <tbody>
                  {diff.rows.map((x) => (
                    <tr key={x.i}><td className="num">{x.i + 1}</td><td>{x.el}</td><td className="num muted">{fmt(x.p?.x, 4)}</td><td className="num">{fmt(x.q.x, 4)}</td><td className="num muted">{fmt(x.p?.y, 4)}</td><td className="num">{fmt(x.q.y, 4)}</td><td className="num muted">{fmt(x.p?.z, 4)}</td><td className="num">{fmt(x.q.z, 4)}</td><td className="num">{fmt(x.d, 4)}</td></tr>
                  ))}
                </tbody>
              </table>
            ) : <div className="empty">Loading saved geometry…</div>}
          </div>
          {diff && <div className="mono muted" style={{padding: '6px 10px', borderTop: 'var(--bw) solid var(--border-subtle)', fontSize: 'var(--fs-xs)'}}>largest move: {diff.largest.el}{diff.largest.i + 1} {fmt(diff.largest.d, 4)} Å · heavy atoms ≤ {fmt(diff.heavyMax, 4)} Å · bonds unchanged ({diff.bonds})</div>}
        </div>
      </div>
      <div className="sec" style={{display: 'flex', gap: 24, borderBottom: 0}}>
        <dl className="kv mono sel-text" style={{flex: '1 1 0'}}>
          <dt>Schema</dt><dd>{r.schema}</dd>
          <dt>Engine</dt><dd>RDKit {r.rdkit_version} · {r.engine_provenance}</dd>
          <dt>Embedding</dt><dd>{r.embedding} · seed {r.seed}</dd>
          <dt>Tolerances</dt><dd>force {r.force_tolerance} · energy {r.energy_tolerance} · ≤ {r.iterations_limit} iter</dd>
          <dt>Energies</dt><dd>{r.energy_geometry}</dd>
        </dl>
        <div style={{flex: '1 1 0'}}>
          <h3 style={{margin: '0 0 6px', fontSize: 'var(--fs-xs)', fontWeight: 600, letterSpacing: 'var(--track-label)', textTransform: 'uppercase', color: 'var(--text-muted)'}}>Artefacts · immutable</h3>
          <table className="mono sel-text" style={{fontSize: 'var(--fs-xs)'}}>
            <tbody>
              {job.artifacts.length === 0 && <tr><td className="muted">no saved files reported</td></tr>}
              {job.artifacts.map((a) => <tr key={a.relative_path}><td>{a.relative_path.split('/').slice(1).join('/')}</td><td className="num">{a.bytes} B</td><td className="muted" style={{whiteSpace: 'normal', wordBreak: 'break-all'}}>{a.sha256}</td></tr>)}
            </tbody>
          </table>
        </div>
      </div>
    </>
  );
}
