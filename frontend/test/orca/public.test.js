import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {parseOrca} from '../../src/orca/parser.js';
const manifest=JSON.parse(await readFile(new URL('./public-sources.json',import.meta.url)));
const expectations={
 'ORCA_ORCA4.2_dvb_sp.out':{energy:-382.050758039646,atoms:20,optimization:'not_requested',frequencies:0},
 'ORCA_ORCA4.2_dvb_gopt.out':{energy:-382.050786152348,atoms:20,optimization:'converged',frequencies:0},
 'ORCA_ORCA4.2_dvb_ir.out':{atoms:20,optimization:'not_requested',frequencies:60,gibbs:-381.90678131},
 'ORCA_ORCA3.0_dvb_gopt_unconverged.out':{energy:-382.049935357823,atoms:20,optimization:'not_converged',frequencies:0},
 'ORCA_ORCA6.0_1618.out':{energy:-237.199466497591,atoms:4,multiJob:true,optimization:'converged'},
 'ORCA_ORCA6.1_1509.out':{atoms:817,optimization:'not_requested',multiJob:false}
};
for(const file of manifest.files)test('public fixture: '+file.file,async t=>{
 let bytes;try{bytes=await readFile(new URL('./fixtures/public/'+file.file,import.meta.url));}catch(error){if(error.code==='ENOENT'){t.skip('Fetch optional public fixtures with python3 scripts/fetch_fixtures.py');return;}throw error;}
 assert.equal(createHash('sha256').update(bytes).digest('hex'),file.sha256,'pinned content');
 const result=parseOrca(bytes.toString('utf8'),file.file),expected=expectations[file.file];
 assert.ok(result.recognized);assert.equal(result.geometry.atoms.length,expected.atoms);assert.equal(result.optimization,expected.optimization);
 if(expected.energy!==undefined)assert.equal(result.energy.value,expected.energy);
 if(expected.frequencies!==undefined)assert.equal(result.frequencies.length,expected.frequencies);
 if(expected.gibbs!==undefined)assert.equal(result.thermochemistry.gibbs.value,expected.gibbs);
 if(expected.multiJob!==undefined)assert.equal(result.multiJob,expected.multiJob);
 assert.equal(result.termination,'normal');
 for(const evidence of [result.version,result.energy,result.charge,result.multiplicity,...result.keywords,...Object.values(result.thermochemistry)].filter(Boolean)){
  assert.ok(evidence.line>=1&&evidence.line<=result.lines.length);
 }
});
