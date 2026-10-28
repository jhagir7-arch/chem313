import {DrawingStore} from './drawing';
import type {EditorHandle} from './editor';
import {useCallback, useEffect, useMemo, useRef, useState} from 'react';
import {artifactText, catalog as loadCatalog, engineStatus, events as loadEvents, execute, onMenu, openStructureFile, request, saveTextFile, type Artifact, type Catalog, type EngineStatus, type EventRecord} from './engine';
import {moleculeId, type Molecule} from './chem';
import {Navigator, Inspector, Console, StatusBar, Palette, NewMoleculeDialog, type PaletteCommand} from './panels';
import {Workspace, type Tab} from './workspace';

/** The engine's relaxation report (what the event log keeps). Geometry text is loaded separately. */
export type RelaxReport = {
  schema: string; name: string; smiles: string; canonical_smiles: string; formula: string; atom_count: number; formal_charge: number;
  inchikey: string; identity_status: string; seed: number; embedding: string; force_field: string; iterations_limit: number;
  force_tolerance: number; energy_tolerance: number; converged: boolean; convergence_status: number;
  initial_energy_kcal_mol: number; final_energy_kcal_mol: number; energy_change_kcal_mol: number; energy_unit: string;
  rdkit_version: string; engine_provenance: string; energy_geometry: string; scope: string;
  geometry_artifacts?: Artifact[];
};
export type Geometry = {initial_sdf: string; sdf: string; svg: string | null};

export type Job = {
  id: string; molecule: Molecule; engine: string; method: string; params: RelaxParams;
  state: 'running' | 'converged' | 'failed'; wallMs: number | null; startedAt: string;
  result: RelaxReport | null; geometry: Geometry | null; error: string | null; artifacts: Artifact[];
};
export type RelaxParams = {force_field: string; seed: number; max_iterations: number};

export type Workbench = {
  name: string; version: string; projects: string[]; data_directory: string;
  engines: Record<string, string>; avogadro?: {status?: string}; orca_engine?: {status?: string}; llm?: {status?: string};
};

export type LogLine = {t: string; text: string};
const now = () => new Date().toTimeString().slice(0, 8);
const PROJECT = 'default';

function moleculeFromReport(r: RelaxReport, known: Molecule[] = []): Molecule {
  const match = known.find((m) => m.smiles === r.canonical_smiles);
  if (match) return {...match, formula: r.formula};
  return {id: moleculeId('smiles', r.canonical_smiles), name: r.name, formula: r.formula, source: 'smiles', smiles: r.canonical_smiles};
}

function jobFromEvent(e: EventRecord, index: number): Job | null {
  if (e.action !== 'molecule.relax_geometry' || !e.result) return null;
  const r = e.result as RelaxReport;
  return {
    id: `${e.parameters_sha256.slice(0, 8)}-${index}`, molecule: moleculeFromReport(r), engine: 'RDKit', method: `${r.force_field} relax`,
    params: {force_field: r.force_field, seed: r.seed, max_iterations: r.iterations_limit},
    state: r.converged ? 'converged' : 'failed', wallMs: null, startedAt: e.timestamp_utc.replace('T', ' ').slice(0, 19),
    result: r, geometry: null, error: null, artifacts: e.artifacts ?? [],
  };
}

export function App() {
  const [status, setStatus] = useState<EngineStatus | null>(null);
  const [workbench, setWorkbench] = useState<Workbench | null>(null);
  const [cat, setCat] = useState<Catalog | null>(null);
  const [tab, setTab] = useState<Tab>('structure');
  const [userMolecules, setUserMolecules] = useState<Molecule[]>([]);
  const [moleculeIdSel, setMoleculeIdSel] = useState<string | null>(null);
  const [params, setParams] = useState<RelaxParams>({force_field: 'MMFF94', seed: 42, max_iterations: 1000});
  const [jobs, setJobs] = useState<Job[]>([]);
  const [selectedJob, setSelectedJob] = useState<string | null>(null);
  const [log, setLog] = useState<LogLine[]>([]);
  const [guided, setGuided] = useState(true);
  const [showNav, setShowNav] = useState(true);
  const [showInspector, setShowInspector] = useState(true);
  const [showConsole, setShowConsole] = useState(true);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [newMoleculeOpen, setNewMoleculeOpen] = useState(false);
  const drawings = useRef(new DrawingStore()).current;
  const editorRef = useRef<EditorHandle>(null);
  const seq = useRef(1);
  const runBusy = useRef(false);

  const say = useCallback((text: string) => setLog((l) => [...l.slice(-499), {t: now(), text}]), []);

  const starters: Molecule[] = useMemo(() => (cat?.molecules ?? []).map((m) => ({id: m.id, name: m.name, formula: m.formula, source: 'starter', smiles: m.smiles})), [cat]);
  const molecules = useMemo(() => [...starters, ...userMolecules], [starters, userMolecules]);
  const job = useMemo(() => jobs.find((j) => j.id === selectedJob) ?? null, [jobs, selectedJob]);
  const molecule = useMemo(() => job?.molecule ?? molecules.find((m) => m.id === moleculeIdSel) ?? molecules[0] ?? null, [molecules, moleculeIdSel, job]);

  // Engine handshake: poll until the host reports the sidecar, then read workbench, catalog and the event log.
  useEffect(() => {
    let cancelled = false;
    let tries = 0;
    const tick = async () => {
      const s = await engineStatus().catch((e) => ({ready: false, url: null, error: String(e), data_dir: ''}));
      if (cancelled) return;
      setStatus(s);
      if (s.ready) {
        try {
          const [wb, c, ev] = await Promise.all([request<Workbench>('/api/workbench'), loadCatalog(), loadEvents(PROJECT)]);
          if (cancelled) return;
          setWorkbench(wb);
          setCat(c);
          setParams({...c.relaxation.defaults});
          const restored = ev.events.map(jobFromEvent).filter((j): j is Job => j !== null).map((j) => ({...j, molecule: moleculeFromReport(j.result!, c.molecules.map((m) => ({...m, source: 'starter' as const})))}));
          setJobs(restored);
          const known = new Set(c.molecules.map((m) => m.smiles));
          const extra = new Map<string, Molecule>();
          for (const j of restored) if (j.molecule.smiles && !known.has(j.molecule.smiles)) extra.set(j.molecule.id, j.molecule);
          setUserMolecules([...extra.values()]);
          say(`[engine] ${wb.name} ${wb.version} · RDKit ${wb.engines?.rdkit ?? '?'} · ${c.molecules.length} starters · ${restored.length} saved calculations`);
        } catch (e) {
          say(`[engine] startup read failed: ${String(e)}`);
        }
        return;
      }
      if (s.error) {
        say(`[engine] ${s.error}`);
        return;
      }
      if (tries++ < 100) setTimeout(tick, 250);
    };
    tick();
    return () => {
      cancelled = true;
    };
  }, [say]);

  const latestForMolecule = useMemo(() => (molecule ? [...jobs].reverse().find((j) => j.molecule.id === molecule.id && j.result) ?? null : null), [jobs, molecule]);
  const shown = job ?? latestForMolecule;

  // Saved calculations keep only their report in the log; fetch the SDFs on first view.
  useEffect(() => {
    if (!shown || shown.geometry || !shown.result?.geometry_artifacts) return;
    const [initial, final] = shown.result.geometry_artifacts;
    if (!initial || !final) return;
    let cancelled = false;
    Promise.all([artifactText(initial.relative_path), artifactText(final.relative_path)])
      .then(([initial_sdf, sdf]) => { if (!cancelled) setJobs((js) => js.map((j) => (j.id === shown.id ? {...j, geometry: {initial_sdf, sdf, svg: null}} : j))); })
      .catch((e) => say(`[records] could not load geometry for ${shown.id}: ${String(e)}`));
    return () => { cancelled = true; };
  }, [shown, say]);

  const addMolecule = useCallback((m: Molecule) => {
    setUserMolecules((ms) => (ms.some((x) => x.id === m.id) ? ms : [...ms, m]));
    setMoleculeIdSel(m.id);
    setSelectedJob(null);
    setTab('structure');
    say(`[molecule] added ${m.name} (${m.source})`);
  }, [say]);

  const runJob = useCallback(async () => {
    if (!status?.ready || !molecule || runBusy.current) return;
    runBusy.current = true;
    const id = `live-${seq.current++}`;
    let molblock: string;
    try {
      if (!editorRef.current) throw new Error('Structure editor is not ready');
      molblock = await editorRef.current.snapshot(molecule.id);
    } catch (e) { runBusy.current = false; say(`[job] cannot run: ${String(e)}`); return; }
    const input = {molblock};
    const created: Job = {id, molecule, engine: 'RDKit', method: `${params.force_field} relax`, params: {...params}, state: 'running', wallMs: null, startedAt: now(), result: null, geometry: null, error: null, artifacts: []};
    setJobs((js) => [...js, created]);
    setSelectedJob(id);
    say(`[job ${id}] ${molecule.name} ${params.force_field} relax · seed ${params.seed} · start`);
    const t0 = performance.now();
    try {
      const reply = await execute<RelaxReport & Geometry>('molecule.relax_geometry', {...input, ...params, ...(molecule.source !== 'starter' ? {name: molecule.name} : {})}, PROJECT);
      const wallMs = performance.now() - t0;
      const {initial_sdf, sdf, svg, ...report} = reply.result;
      const geometry: Geometry = {initial_sdf, sdf, svg};
      const calculated = moleculeFromReport(report, molecules);
      if (!molecules.some((m) => m.id === calculated.id)) setUserMolecules((ms) => ms.some((m) => m.id === calculated.id) ? ms : [...ms, calculated]);
      setJobs((js) => js.map((j) => (j.id === id ? {...j, molecule: calculated, state: report.converged ? 'converged' : 'failed', wallMs, result: report, geometry, artifacts: reply.artifacts ?? []} : j)));
      say(`[job ${id}] ${report.converged ? 'converged' : 'not converged'} · E ${report.initial_energy_kcal_mol.toFixed(6)} → ${report.final_energy_kcal_mol.toFixed(6)} ${report.energy_unit} · identity ${report.identity_status}`);
      setTab('results');
    } catch (e) {
      const wallMs = performance.now() - t0;
      setJobs((js) => js.map((j) => (j.id === id ? {...j, state: 'failed', wallMs, error: String(e)} : j)));
      say(`[job ${id}] failed · ${String(e)}`);
    } finally { runBusy.current = false; }
  }, [status, molecule, molecules, params, say]);

  const importStructure = useCallback(async () => {
    try {
      const file = await openStructureFile();
      if (!file) return;
      addMolecule({id: moleculeId('molblock', file.contents), name: file.name.replace(/\.(mol|sdf)$/i, ''), formula: null, source: 'molblock', molblock: file.contents});
    } catch (e) {
      say(`[import] ${String(e)}`);
    }
  }, [addMolecule, say]);

  const exportRecord = useCallback(async () => {
    if (!shown?.result) return;
    const record = {...shown.result, artifacts: shown.artifacts, exported_utc: new Date().toISOString(), exported_by: `Chem313 ${__APP_VERSION__}`};
    try {
      const path = await saveTextFile(`${shown.molecule.id}-${shown.result.force_field.toLowerCase()}-relax.json`, JSON.stringify(record, null, 2));
      say(path ? `[export] record saved to ${path}` : '[export] cancelled');
    } catch (e) {
      say(`[export] ${String(e)}`);
    }
  }, [shown, say]);

  const commands: PaletteCommand[] = useMemo(
    () => [
      {id: 'run', label: 'Run calculation', kbd: '⌘R', run: runJob},
      {id: 'new-molecule', label: 'New molecule from SMILES…', kbd: '⌘N', run: () => setNewMoleculeOpen(true)},
      {id: 'import', label: 'Import structure (.mol, .sdf)…', kbd: '⌘O', run: importStructure},
      {id: 'export-record', label: 'Export record…', kbd: '⌘E', run: exportRecord},
      {id: 'tab-structure', label: 'Go to Structure', kbd: '⌘1', run: () => setTab('structure')},
      {id: 'tab-3d', label: 'Go to 3D', kbd: '⌘2', run: () => setTab('3d')},
      {id: 'tab-setup', label: 'Go to Setup', kbd: '⌘3', run: () => setTab('setup')},
      {id: 'tab-results', label: 'Go to Results', kbd: '⌘4', run: () => setTab('results')},
      {id: 'toggle-navigator', label: 'Toggle Navigator', kbd: '⌘⌥1', run: () => setShowNav((v) => !v)},
      {id: 'toggle-inspector', label: 'Toggle Inspector', kbd: '⌘⌥2', run: () => setShowInspector((v) => !v)},
      {id: 'toggle-console', label: 'Toggle Console', kbd: '⌘⌥3', run: () => setShowConsole((v) => !v)},
      {id: 'toggle-guided', label: 'Toggle Guided mode', kbd: '⌘G', run: () => setGuided((v) => !v)},
      ...molecules.map((m) => ({id: `mol-${m.id}`, label: `Open ${m.name}`, kbd: m.formula ?? '', run: () => { setMoleculeIdSel(m.id); setSelectedJob(null); }})),
    ],
    [runJob, importStructure, exportRecord, molecules],
  );

  // Native menu events and keyboard shortcuts resolve to the same command list.
  useEffect(() => {
    const byId = (id: string) => commands.find((c) => c.id === id)?.run();
    const unlisten = onMenu((id) => {
      if (id === 'command-palette') setPaletteOpen(true);
      else if (id === 'check') setTab('structure');
      else byId(id);
    });
    const onKey = (e: KeyboardEvent) => {
      const mod = e.metaKey || e.ctrlKey;
      const k = e.key.toLowerCase();
      if (mod && k === 'k') { e.preventDefault(); setPaletteOpen((v) => !v); }
      else if (mod && k === 'r') { e.preventDefault(); runJob(); }
      else if (mod && k === 'n') { e.preventDefault(); setNewMoleculeOpen(true); }
      else if (mod && k === 'o') { e.preventDefault(); importStructure(); }
      else if (mod && k === 'e') { e.preventDefault(); exportRecord(); }
      else if (mod && !e.altKey && ['1', '2', '3', '4'].includes(e.key)) { e.preventDefault(); setTab((['structure', '3d', 'setup', 'results'] as Tab[])[Number(e.key) - 1]); }
      else if (e.key === 'Escape') { setPaletteOpen(false); setNewMoleculeOpen(false); }
    };
    window.addEventListener('keydown', onKey);
    return () => { window.removeEventListener('keydown', onKey); unlisten.then((u) => u()); };
  }, [commands, runJob, importStructure, exportRecord]);

  const running = jobs.filter((j) => j.state === 'running').length;
  const done = jobs.filter((j) => j.state === 'converged' || j.state === 'failed').length;

  return (
    <div className={`shell${showConsole ? '' : ' console-collapsed'}`}>
      <div className="toolbar">
        <button className="tool" type="button" onClick={() => setNewMoleculeOpen(true)}>New molecule</button>
        <button className="tool" type="button" onClick={importStructure}>Import…</button>
        <span className="rule" />
        <button className="tool" type="button" onClick={() => setTab('structure')}>Check</button>
        <button className="tool" type="button" onClick={() => setTab('setup')}>Set up calculation</button>
        <button className="tool primary" type="button" onClick={runJob} disabled={!status?.ready || !molecule || running > 0}>Run</button>
        <button className="tool" type="button" onClick={exportRecord} disabled={!shown?.result}>Export record…</button>
        <span className="spacer" />
        <label className="cmdfield" htmlFor="cmd">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true"><circle cx="11" cy="11" r="7" /><path d="M20 20l-3.5-3.5" /></svg>
          <input id="cmd" type="text" placeholder="Command or molecule…  ⌘K" readOnly onFocus={() => setPaletteOpen(true)} />
        </label>
        <button className="tool" type="button" aria-pressed={guided} onClick={() => setGuided((v) => !v)}><span className={`dot${guided ? ' on' : ''}`} />Guided</button>
      </div>

      <div className="body">
        {showNav && <Navigator molecules={molecules} molecule={molecule} jobs={jobs} selectedJob={selectedJob} onMolecule={(m) => { setMoleculeIdSel(m.id); setSelectedJob(null); }} onJob={(j) => { setSelectedJob(j.id); setMoleculeIdSel(j.molecule.id); setTab('results'); }} />}
        <Workspace tab={tab} onTab={setTab} molecule={molecule} job={shown} jobs={jobs} params={params} onParams={setParams} catalog={cat} onRun={runJob} canRun={!!status?.ready && !!molecule && running === 0} workbench={workbench} onSelectJob={(id) => { setSelectedJob(id); setTab('results'); }} editorRef={editorRef} drawings={drawings} onAddMolecule={addMolecule} />
        {showInspector && <Inspector molecule={molecule} job={shown} guided={guided} tab={tab} />}
      </div>

      <Console jobs={jobs} log={log} workbench={workbench} status={status} catalog={cat} collapsed={!showConsole} onToggle={() => setShowConsole((v) => !v)} onSelectJob={(id) => { setSelectedJob(id); setTab('results'); }} selectedJob={selectedJob} />
      <StatusBar status={status} workbench={workbench} running={running} done={done} queued={0} />
      {paletteOpen && <Palette commands={commands} onClose={() => setPaletteOpen(false)} onSmiles={(smiles) => { setPaletteOpen(false); setNewMoleculeOpen(true); setPendingSmiles(smiles); }} />}
      {newMoleculeOpen && <NewMoleculeDialog initialSmiles={pendingSmilesRef.current} onClose={() => { setNewMoleculeOpen(false); pendingSmilesRef.current = ''; }} onAdd={(name, smiles) => { addMolecule({id: moleculeId('smiles', smiles), name: name || smiles, formula: null, source: 'smiles', smiles}); setNewMoleculeOpen(false); pendingSmilesRef.current = ''; }} />}
    </div>
  );

  function setPendingSmiles(s: string) { pendingSmilesRef.current = s; }
}

const pendingSmilesRef = {current: ''};
