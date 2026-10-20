import test from 'node:test';
import assert from 'node:assert/strict';
import {HARTREE_TO_EV,HARTREE_TO_KJ_PER_MOL,convertElectronicEnergy,formatElectronicEnergy} from '../src/resultUnits.mjs';

test('converts an absolute electronic energy without changing its sign',()=>{
  const converted=convertElectronicEnergy(-1);
  assert.equal(converted.hartree,-1);
  assert.equal(converted.kilojoulesPerMol,-HARTREE_TO_KJ_PER_MOL);
  assert.equal(converted.electronVolts,-HARTREE_TO_EV);
});

test('rejects a missing energy and formats finite values predictably',()=>{
  assert.equal(convertElectronicEnergy(Number.NaN),null);
  assert.equal(convertElectronicEnergy('-.5'),null);
  assert.equal(formatElectronicEnergy(-75.123456789,4),'-75.1235');
  assert.equal(formatElectronicEnergy(undefined),'Unavailable');
});
