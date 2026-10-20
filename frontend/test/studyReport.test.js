import test from 'node:test';
import assert from 'node:assert/strict';
import {guidedQuestion,studyReport} from '../src/studyReport.mjs';

test('guided requests bind the selected molecule and bounded count',()=>{
  assert.equal(guidedQuestion('acetic acid',3),'Compare 3 shapes of acetic acid');
  for(const [name,n] of [['unknown',3],['butane',0],['butane',9],['butane',2.5]]) assert.throws(()=>guidedQuestion(name,n));
});
test('readable report preserves failed and duplicate attempts and explains score limits',()=>{
  const report=studyReport('demo',{}, {id:'job',status:'cancelled',completed:3,requested:5,recipe:{plan:{prompt:'Compare 5 shapes of butane',molecule:'butane',planner_note:'Checked fallback',provenance:{model:'test',variant:'base'}},result:{candidates:[{status:'unique',seed:42,energy:-4,relative_energy:0,energy_unit:'kcal/mol',force_field:'MMFF'},{status:'duplicate',seed:137,duplicate_of:42,rmsd:0.1},{status:'failed',seed:271,error:'Did not converge'}]}}});
  for(const value of ['Status: cancelled','Completed samples: 3 of 5','energy -4 kcal/mol; relative energy 0 kcal/mol','Same shape as seed 42','Did not converge','does not prove the true most stable shape','Planner note: Checked fallback']) assert.ok(report.includes(value),value);
  assert.ok(!report.includes('energy undefined'));
});
test('missing results are disclosed without inventing scores or successful completion',()=>{
  const report=studyReport('demo',null,{id:'job',status:'failed',error:'Worker unavailable'});
  for(const text of ['Status: failed','No sample outcomes recorded.','Model SHA-256: not reported','Run error: Worker unavailable']) assert.ok(report.includes(text));
});
