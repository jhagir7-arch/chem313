import test from 'node:test';
import assert from 'node:assert/strict';
import {convertEnergy, dist, electronCount, fmt, moleculeId, parseSdf, unitLabel} from '../src/chem.ts';

const WATER = `
     RDKit          3D

  3  2  0  0  0  0  0  0  0  0999 V2000
   -0.0343    0.0183    0.0000 O   0  0  0  0  0  0  0  0  0  0  0  0
    0.8974    0.2160    0.0000 H   0  0  0  0  0  0  0  0  0  0  0  0
   -0.8631   -0.2343    0.0000 H   0  0  0  0  0  0  0  0  0  0  0  0
  1  2  1  0
  1  3  1  0
M  END
$$$$
`;

test('parseSdf reads atoms and bonds from a V2000 block', () => {
  const {atoms, bonds} = parseSdf(WATER);
  assert.equal(atoms.length, 3);
  assert.deepEqual(atoms[0], {el: 'O', x: -0.0343, y: 0.0183, z: 0});
  assert.deepEqual(bonds, [{a: 0, b: 1, order: 1}, {a: 0, b: 2, order: 1}]);
});

test('bond lengths come out near 0.96 Å for the water sample', () => {
  const {atoms} = parseSdf(WATER);
  const oh = dist(atoms[0], atoms[1]);
  assert.ok(oh > 0.9 && oh < 1.0, `O–H ${oh}`);
});

test('electronCount sums atomic numbers and applies charge; unknown elements give null', () => {
  const {atoms} = parseSdf(WATER);
  assert.equal(electronCount(atoms, 0), 10);
  assert.equal(electronCount(atoms, 1), 9);
  assert.equal(electronCount([{el: 'Xx', x: 0, y: 0, z: 0}], 0), null);
});

test('energy conversion and labels', () => {
  assert.equal(convertEnergy(1, 'kcal'), 1);
  assert.ok(Math.abs(convertEnergy(1, 'kJ') - 4.184) < 1e-12);
  assert.ok(Math.abs(convertEnergy(627.509474, 'Eh') - 1) < 1e-12);
  assert.equal(unitLabel('kJ'), 'kJ·mol⁻¹');
});

test('fmt handles missing values and digits', () => {
  assert.equal(fmt(null), '—');
  assert.equal(fmt(NaN), '—');
  assert.equal(fmt(1.23456789, 3), '1.235');
});

test('moleculeId is stable and distinguishes inputs', () => {
  assert.equal(moleculeId('smiles', 'CCO'), moleculeId('smiles', 'CCO'));
  assert.notEqual(moleculeId('smiles', 'CCO'), moleculeId('smiles', 'CCN'));
  assert.match(moleculeId('molblock', 'x'), /^molblock-[0-9a-f]+$/);
});
