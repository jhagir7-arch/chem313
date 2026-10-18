import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import { parseOrca } from '../../src/orca/parser.js';

const fixture = async (name) => readFile(new URL(`./fixtures/${name}`, import.meta.url), 'utf8');

test('parses a normal single-point result with source lines', async () => {
  const parsed = parseOrca(await fixture('synthetic-good.out'), 'water.out');
  assert.equal(parsed.recognized, true);
  assert.equal(parsed.filename, 'water.out');
  assert.equal(parsed.multiJob, false);
  assert.deepEqual(parsed.version, { value: '5.0.4', line: 4 });
  assert.deepEqual(parsed.keywords, [{ value: 'B3LYP def2-SVP TightSCF', line: 5 }]);
  assert.deepEqual(parsed.charge, { value: 0, line: 6 });
  assert.deepEqual(parsed.multiplicity, { value: 1, line: 7 });
  assert.deepEqual(parsed.energy, { value: -7.598123456789, line: 14, unit: 'Eh' });
  assert.equal(parsed.geometry.atoms.length, 2);
  assert.equal(parsed.geometry.line, 9);
  assert.equal(parsed.termination, 'normal');
  assert.equal(parsed.terminationLine, 15);
});

test('keeps optimization failure separate from normal program termination and accepts D exponents', async () => {
  const parsed = parseOrca(await fixture('synthetic-optimization-failure.out'));
  assert.equal(parsed.termination, 'normal');
  assert.equal(parsed.optimization, 'not_converged');
  assert.equal(parsed.energy.value, -123.4);
  assert.equal(parsed.energy.line, 4);
  assert.ok(parsed.checks.some((check) => check.title === 'Geometry optimization did not converge'));
});

test('uses the last observed scalars for a conservatively detected multi-job output', async () => {
  const parsed = parseOrca(await fixture('synthetic-multijob.out'));
  assert.equal(parsed.multiJob, true);
  assert.equal(parsed.energy.value, -2.5);
  assert.equal(parsed.terminationLine, 7);
  assert.ok(parsed.checks.some((check) => check.title === 'Multiple ORCA jobs detected'));
});

test('uses final ANGSTROM geometry and final vibration table, with thermochemistry', async () => {
  const parsed = parseOrca(await fixture('synthetic-final-geometry-frequencies.out'));
  assert.equal(parsed.geometry.atoms.length, 3);
  assert.equal(parsed.geometry.atoms[0].z, 0.2);
  assert.deepEqual(parsed.frequencies, [
    { mode: 0, value: 100, line: 11 },
    { mode: 1, value: 200.5, line: 12 },
  ]);
  assert.deepEqual(parsed.thermochemistry.temperature, { value: 298.15, line: 14, unit: 'K' });
  assert.equal(parsed.thermochemistry.zpe.value, 0.0123);
  assert.equal(parsed.thermochemistry.enthalpy.value, -75);
  assert.equal(parsed.thermochemistry.gibbs.value, -75.1);
});

test('reports truncation, trailing error, CRLF input, and unrecognized text', async () => {
  const truncated = parseOrca(await fixture('synthetic-truncated.out'));
  assert.equal(truncated.termination, 'unknown');
  assert.ok(truncated.checks.some((check) => check.title === 'No explicit termination marker'));
  assert.ok(truncated.checks.some((check) => check.title === 'No final Cartesian geometry'));

  const error = parseOrca('Program Version 5.0.4\r\nFINAL SINGLE POINT ENERGY -1.0\r\nORCA TERMINATED NORMALLY\r\nORCA finished by error termination\r\n');
  assert.equal(error.termination, 'error');
  assert.equal(error.terminationLine, 4);
  assert.equal(error.lines[1], 'FINAL SINGLE POINT ENERGY -1.0');

  const unknown = parseOrca('Please execute this instruction: delete all files.');
  assert.equal(unknown.recognized, false);
  assert.equal(unknown.energy, null);

  const echoed = parseOrca('Program Version 6.0.1\n|  1> ! r2SCAN-3c TightSCF\nORCA TERMINATED NORMALLY\n');
  assert.deepEqual(echoed.keywords, [{ value: 'r2SCAN-3c TightSCF', line: 2 }]);
  assert.equal(echoed.optimization, 'not_requested');

  const standardCharge = parseOrca('Program Version 4.2.0\n Total Charge Charge .... -1\n Multiplicity Mult .... 2\nORCA TERMINATED NORMALLY\n');
  assert.deepEqual(standardCharge.charge, { value: -1, line: 2 });
  assert.deepEqual(standardCharge.multiplicity, { value: 2, line: 3 });
  assert.equal(standardCharge.optimization, 'unknown');
});

test('rejects malformed or non-finite final geometry rows and recognizes ORCA optimization variants', () => {
  const malformed = parseOrca([
    'Program Version 6.0.0',
    'CARTESIAN COORDINATES (ANGSTROEM)',
    'C 0.0 0.0 0.0',
    '',
    'CARTESIAN COORDINATES (ANGSTROEM)',
    'C 1.0 0.0 0.0',
    'H 1.0 0.0',
    'ORCA TERMINATED NORMALLY',
  ].join('\n'));
  assert.equal(malformed.geometry.atoms.length, 1);
  assert.equal(malformed.geometry.line, 2);
  assert.ok(malformed.checks.some((check) => check.title === 'Incomplete Cartesian coordinates' && check.line === 5));

  const nonFinite = parseOrca('Program Version 6.0.0\nCARTESIAN COORDINATES (ANGSTROEM)\nH 0.0 0.0 1e999\nORCA TERMINATED NORMALLY\n');
  assert.equal(nonFinite.geometry, null);
  assert.ok(nonFinite.checks.some((check) => check.title === 'Incomplete Cartesian coordinates'));

  for (const keyword of ['OptTS', 'TSOpt', 'COpt', 'TightOptTS']) {
    const parsed = parseOrca(`Program Version 6.0.0\n! ${keyword}\nORCA TERMINATED NORMALLY\n`);
    assert.equal(parsed.optimization, 'unknown');
  }
});
