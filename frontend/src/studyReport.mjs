// Names accepted by the checked study planner; no free-form structure guessing.
export const STUDY_MOLECULES = ['butane','ethanol','water','methanol','propane','methane','ethane','benzene','acetone','acetic acid','aspirin','caffeine','paracetamol','glycine'];

export function guidedQuestion(molecule, samples) {
  if (!STUDY_MOLECULES.includes(molecule) || !Number.isInteger(samples) || samples < 1 || samples > 8) throw Error('Choose a listed molecule and one to eight shapes.');
  return `Compare ${samples} shapes of ${molecule}`;
}

export function studyReport(project, plan, study) {
  const recipe = study.recipe;
  const scope = recipe?.plan ?? plan ?? {};
  const result = recipe?.result ?? study.result ?? {};
  const rows = Array.isArray(result.candidates) ? result.candidates : [];
  const score = value => typeof value === 'number' && Number.isFinite(value) ? String(value) : 'not reported';
  const lines = [
    'Chem313 molecule study', `Project: ${project}`, `Study: ${study.id}`, `Status: ${study.status}`,
    `Question: ${scope.prompt ?? 'not recorded'}`, `Molecule: ${scope.molecule ?? 'not reported'}`,
    `Formula: ${scope.formula ?? 'not reported'}`, `SMILES: ${scope.canonical_smiles ?? 'not reported'}`,
    `Completed samples: ${study.completed ?? result.completed ?? 0} of ${study.requested ?? result.requested ?? scope.samples ?? 'not reported'}`,
    '', 'How to read this study',
    'Each sample starts from a different 3D arrangement of the same molecule. A unique result is a converged shape that passed the duplicate check. A duplicate is another attempt that reached an already recorded shape.',
    'Energy is a force-field model score, not an experimental measurement. Lower scores compare only this molecule with the same force field. Relative zero means the lowest score in this sampled set; it does not prove the true most stable shape. Sampling is not exhaustive.',
    'This study does not simulate reactions, predict medication breakdown, or run ORCA. ORCA input preparation is a separate next step; ORCA requires a separate license and installation.',
    '', 'All sample outcomes',
  ];
  if (!rows.length) lines.push('No sample outcomes recorded.');
  rows.forEach((row, i) => {
    lines.push(`${i + 1}. ${row.status ?? 'unknown'}; seed ${row.seed ?? 'not reported'}; ${row.force_field ?? 'force field not reported'}; energy ${score(row.energy)} ${row.energy_unit ?? '(unit not reported)'}; relative energy ${score(row.relative_energy)}${typeof row.relative_energy === 'number' ? ' kcal/mol' : ''}`);
    if (row.status === 'duplicate') lines.push(`   Same shape as seed ${row.duplicate_of ?? 'not reported'}; RMSD ${score(row.rmsd)} angstrom.`);
    if (row.error) lines.push(`   Detail: ${row.error}`);
  });
  if (study.error) lines.push('', `Run error: ${study.error}`);
  lines.push('', 'Traceability', `Planner model: ${scope.provenance?.model ?? 'not reported'}`, `Model variant: ${scope.provenance?.variant ?? 'not reported'}`, `Model SHA-256: ${scope.provenance?.model_sha256 ?? 'not reported'}`);
  if (scope.planner_note) lines.push(`Planner note: ${scope.planner_note}`);
  lines.push('Export JSON in Chem313 retains the exact coordinates, sampling settings, model provenance and saved artifact hashes. This readable report is a summary, not a replacement for that record.');
  return lines.join('\n') + '\n';
}
