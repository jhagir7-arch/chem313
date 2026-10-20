export const HARTREE_TO_KCAL = 627.509474;
export const MAX_FILE_BYTES = 25 * 1024 * 1024;
export function formula(atoms = []) {
  const counts = new Map();
  for (const {element} of atoms) counts.set(element, (counts.get(element) || 0) + 1);
  const order = [...counts.keys()].sort((a,b) => {
    if (counts.has('C')) {if (a === 'C') return -1; if (b === 'C') return 1; if (a === 'H') return -1; if (b === 'H') return 1;}
    return a.localeCompare(b);
  });
  return order.map(el => el + (counts.get(el) > 1 ? counts.get(el) : '')).join('');
}
/**
 * Describe what the reader extracted without promoting an output to a
 * scientifically validated result. This is deliberately separate from
 * comparisonIssues(): a single imported file still deserves a clear, safe
 * review path before anyone attempts a comparison.
 */
export function reviewSummary(record) {
  const missing = [];
  if (!record.recognized) missing.push('a recognizable ORCA output marker');
  if (record.termination !== 'normal') missing.push('an explicit normal termination');
  if (!record.energy) missing.push('a final electronic energy');
  if (!record.geometry) missing.push('a complete Cartesian geometry');
  if (!record.charge) missing.push('a printed charge');
  if (!record.multiplicity) missing.push('a printed multiplicity');
  if (!record.version) missing.push('a printed ORCA version');
  if (!record.keywords?.length) missing.push('echoed input keywords');

  const warningChecks = record.checks.filter((check) => check.severity === 'warning');
  const unresolved = [
    ...missing,
    ...warningChecks.map((check) => check.title),
    ...(record.multiJob ? ['a single, unambiguous ORCA job'] : []),
    ...(record.optimization === 'unknown' ? ['an explicit optimization outcome'] : []),
    ...(record.scf === 'unknown' ? ['an explicit SCF outcome'] : []),
    ...(record.scf === 'not_converged' ? ['SCF convergence'] : []),
    ...(record.optimization === 'not_converged' ? ['geometry optimization convergence'] : []),
  ];
  const uniqueUnresolved = [...new Set(unresolved)];
  const evidenceCount = [record.version, record.termination === 'normal', record.energy, record.geometry, record.charge, record.multiplicity, record.keywords?.length].filter(Boolean).length;

  if (!record.recognized) return {
    state: 'hold', evidenceCount, missing: uniqueUnresolved,
    title: 'Review on hold',
    nextAction: 'Confirm that this is a complete ORCA output file. This reader does not infer results from unrecognized text.',
  };
  if (uniqueUnresolved.length) return {
    state: 'review', evidenceCount, missing: uniqueUnresolved,
    title: 'Review required',
    nextAction: 'Inspect the printed source and resolve the listed gaps before using extracted values in a comparison or conclusion.',
  };
  return {
    state: 'inspect', evidenceCount, missing: [],
    title: 'Evidence extracted — inspect before use',
    nextAction: 'Review the printed facts and source lines. Extracted evidence does not validate the calculation or chemical interpretation.',
  };
}
export function comparisonIssues(results) {
  if (results.length < 2) return ['Import at least two calculations.'];
  const issues = new Set();
  const first = results[0];
  const keywords = r => r.keywords.map(k => k.value.trim().replace(/\s+/g,' ').toLowerCase()).join(' | ');
  for (const r of results) {
    if (r.checks.some(check=>check.severity==='warning')) issues.add('Resolve extraction warnings before comparing energies.');
    if (r.multiJob) issues.add('Multiple jobs in one file are not supported for comparison.');
    if (r.termination !== 'normal') issues.add('Every calculation needs an explicit normal termination.');
    if (!r.energy) issues.add('Every calculation needs a final electronic energy.');
    if (!r.geometry) issues.add('Every calculation needs a complete geometry.');
    if (r.scf === 'unknown') issues.add('SCF convergence is unresolved.');
    if (r.scf === 'not_converged' || r.optimization === 'not_converged') issues.add('A calculation reports non-convergence.');
    if (r.optimization === 'unknown') issues.add('Optimization convergence is unresolved.');
    if (!r.charge || !r.multiplicity) issues.add('Charge and multiplicity must be printed in every file.');
    if (!keywords(r)) issues.add('Echoed input keywords are missing.');
    if (formula(r.geometry?.atoms) !== formula(first.geometry?.atoms)) issues.add('Atom compositions differ.');
    if (r.charge?.value !== first.charge?.value || r.multiplicity?.value !== first.multiplicity?.value) issues.add('Charges or multiplicities differ.');
    if (keywords(r) !== keywords(first)) issues.add('Printed input keyword lines differ.');
    if (!r.version || r.version.value !== first.version?.value) issues.add('Printed ORCA versions differ or are missing.');
  }
  return [...issues];
}
export function exportRecord(r) {
  const {lines, id, demo, sourceBytes, ...facts} = r;
  return {...facts, source: {filename: r.filename, sha256:r.sha256, synthetic:!!r.demo}, limits:'Static extraction only. Last observed facts may belong to different stages. Missing values are unknown; checks do not certify chemical validity.'};
}
export function csvCell(value) {
  let s = value == null ? '' : String(value);
  if (typeof value === 'string' && /^[\s]*[=+@\-]/.test(s)) s = "'" + s;
  return '"' + s.replaceAll('"','""') + '"';
}
export function exportCSV(results) {
  const rows = [['file','sha256','synthetic','ORCA version','formula','charge','multiplicity','termination','optimization','electronic energy (Eh)','energy line','Gibbs energy (Eh)','Gibbs line','negative frequencies (cm^-1)']];
  for (const r of results) rows.push([r.filename,r.sha256,!!r.demo,r.version?.value,formula(r.geometry?.atoms),r.charge?.value,r.multiplicity?.value,r.termination,r.optimization,r.energy?.value,r.energy?.line,r.thermochemistry.gibbs?.value,r.thermochemistry.gibbs?.line,r.frequencies.filter(f=>f.value<0).map(f=>f.value).join('; ')]);
  return rows.map(row=>row.map(csvCell).join(',')).join('\r\n');
}
export function xyz(geometry, label='Geometry extracted from ORCA output') {
  return `${geometry.atoms.length}\n${label.replace(/[\r\n]/g,' ')}\n` + geometry.atoms.map(a=>`${a.element} ${a.x} ${a.y} ${a.z}`).join('\n')+'\n';
}
