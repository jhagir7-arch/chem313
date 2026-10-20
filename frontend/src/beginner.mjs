export const STARTER_MOLECULES = Object.freeze([
  {name: 'Water', smiles: 'O', formula: 'H2O', note: 'A small first example with three atoms, including hydrogens.'},
  {name: 'Ethanol', smiles: 'CCO', formula: 'C2H6O', note: 'Explore rotation around single bonds.'},
  {name: 'Butane', smiles: 'CCCC', formula: 'C4H10', note: 'Try sampling different starting shapes of the same molecule.'},
  {name: 'Benzene', smiles: 'c1ccccc1', formula: 'C6H6', note: 'Inspect an aromatic ring and its generated geometry.'},
]);

export const CONFORMER_SEEDS = Object.freeze([42, 137, 271, 811, 1297]);

// A common molecule, energy unit and force field are required for a relative ranking.
export function rankStartingShapes(candidates) {
  const usable = candidates.filter(x => x.converged === true && Number.isFinite(x.energy));
  if (!usable.length) throw Error('No sampled shape converged. Try Generate 3D or use a smaller molecule.');
  const first = usable[0];
  if (!first.editorSmiles || !first.force_field || first.energy_unit !== 'kcal/mol')
    throw Error('The sampled shapes do not have a complete common energy model.');
  if (usable.some(x => x.editorSmiles !== first.editorSmiles || x.force_field !== first.force_field || x.energy_unit !== first.energy_unit))
    throw Error('Relative energies require the same molecule, force field and units.');
  const sorted = [...usable].sort((a, b) => a.energy - b.energy || a.seed - b.seed);
  return sorted.map(x => ({...x, relativeEnergy: Math.max(0, x.energy - sorted[0].energy)}));
}
