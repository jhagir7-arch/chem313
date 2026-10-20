import test from 'node:test';
import assert from 'node:assert/strict';
import {checkedQchemLesson,qchemCoordinatePayload,qchemStudyRecord} from '../src/qchemStudy.mjs';
const water={coordinate_units:'angstrom',atomic_numbers:[8,1,1],coordinates:[[0,0,0],[.96,0,0],[-.24,.93,0]],force_field:'MMFF94',seed:7};
const context={project:'lesson',molecule:'water',geometry:water,charge:'0',multiplicity:'1',understanding:{atom_count_correct:true,coordinates_checked:true,single_point_checked:true},notes:'The atoms stay in place.'};
test('preparation record binds exact reviewed input and actual geometry, with honest status',async()=>{
 const record=await qchemStudyRecord(context);
 assert.equal(record.status,'PREPARED_NOT_RUN');
 assert.equal(record.exact_input,checkedQchemLesson(water,'water',0,1).input);
 const digest=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(record.exact_input)))).map(value=>value.toString(16).padStart(2,'0')).join('');
 assert.equal(record.input_sha256,digest);assert.equal(record.geometry.force_field,'MMFF94');assert.deepEqual(record.geometry.coordinates,water.coordinates);
 water.coordinates[0][0]=.01;assert.equal(record.geometry.coordinates[0][0],0);water.coordinates[0][0]=0;
 assert.equal(record.learning.notes,context.notes);assert.ok(record.limitations.some(line=>line.includes('not been run')));
});
test('changed molecule, invalid state and incomplete checks cannot produce saved lesson',async()=>{
 assert.throws(()=>checkedQchemLesson(water,'methane',0,1),/do not match/);
 assert.throws(()=>checkedQchemLesson(water,'water','',1),/required/);
 assert.throws(()=>checkedQchemLesson(water,'water',0,2),/parity/);
 assert.throws(()=>checkedQchemLesson(water,'water',1,2),/neutral singlet/);
 await assert.rejects(qchemStudyRecord({...context,understanding:{atom_count_correct:false,coordinates_checked:true,single_point_checked:true}}),/understanding/);
});
test('coordinate payload is explicit and a record rejects an unchecked server preparation',async()=>{
 assert.deepEqual(qchemCoordinatePayload(water,'water'),{molecule:'water',atoms:[{element:'O',x:0,y:0,z:0},{element:'H',x:.96,y:0,z:0},{element:'H',x:-.24,y:.93,z:0}]});
 await assert.rejects(qchemStudyRecord({...context,serverPreparation:{input_text:checkedQchemLesson(water,'water',0,1).input,input_sha256:'not-a-digest',identity_check:{status:'match'}}}),/identity check/);
});
