import test from 'node:test';
import assert from 'node:assert/strict';
import {rankStartingShapes, STARTER_MOLECULES, CONFORMER_SEEDS} from '../src/beginner.mjs';
const candidate = (energy, seed = 42, extra = {}) => ({energy, seed, converged:true, editorSmiles:'CCCC', force_field:'MMFF', energy_unit:'kcal/mol', ...extra});
test('rank converged shapes by relative energy without mutating or discarding tied samples', () => {
  const source = [candidate(-2, 137), candidate(-4), candidate(-4, 271)];
  const ranked = rankStartingShapes(source);
  assert.deepEqual(ranked.map(x => x.seed), [42, 271, 137]);
  assert.deepEqual(ranked.map(x => x.relativeEnergy), [0, 0, 2]);
  assert.equal(source[0].seed,137);
});
test('exclude nonfinite and unconverged energies; fail when no useful sample remains', () => {
  assert.equal(rankStartingShapes([candidate(0),candidate(NaN),candidate(-10,137,{converged:false})]).length,1);
  assert.throws(()=>rankStartingShapes([candidate(Infinity),candidate(0,137,{converged:false})]),/No sampled shape converged/);
});
test('never compare molecular identity, method or unit mismatches', () => {
  for (const extra of [{editorSmiles:'CCO'}, {force_field:'UFF'}, {energy_unit:'hartree'}])
    assert.throws(()=>rankStartingShapes([candidate(0),candidate(1,137,extra)]),/same molecule/);
  assert.throws(()=>rankStartingShapes([candidate(0,42,{editorSmiles:''})]),/complete common energy model/);
});
test('starter catalog and fixed samples are bounded and unambiguous', () => {
  assert.equal(STARTER_MOLECULES.find(x=>x.name==='Butane').smiles,'CCCC');
  assert.equal(new Set(CONFORMER_SEEDS).size,5);
  assert.ok(CONFORMER_SEEDS.every(x=>Number.isInteger(x)&&x>=0));
});
