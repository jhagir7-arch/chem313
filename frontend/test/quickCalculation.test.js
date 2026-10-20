import test from 'node:test';
import assert from 'node:assert/strict';
import {calculationOutcome,calculationReport} from '../src/calculationReview.mjs';
const parsed={termination:'normal',scf:'converged',energy:{value:-75.9},optimization:'not_requested',multiJob:false};
test('required markers permit a single point, never a failed or cancelled process',()=>{
 assert.equal(calculationOutcome({state:'SUCCEEDED'},parsed,'single_point').complete,true);
 for(const state of ['FAILED','CANCELLED','TIMED_OUT','INTERRUPTED'])assert.equal(calculationOutcome({state},parsed,'single_point').complete,false);
 for(const change of [{scf:'unknown'},{scf:'not_converged'},{termination:'unknown'},{energy:null},{energy:{value:NaN}},{multiJob:true}])assert.equal(calculationOutcome({state:'SUCCEEDED'},{...parsed,...change},'single_point').complete,false);
});
test('optimization requires its own converged marker and reports scientific limits',()=>{
 assert.equal(calculationOutcome({state:'SUCCEEDED'},parsed,'optimization').complete,false);
 assert.equal(calculationOutcome({state:'SUCCEEDED'},{...parsed,optimization:'converged'},'optimization').complete,true);
 const report=calculationReport('example','Water','optimization',{state:'FAILED',id:'test'},{parsed,artifact:{relative_path:'output.txt',sha256:'abc'}});
 assert.match(report,/Result needs review/);assert.match(report,/does not establish a local minimum/);assert.match(report,/Output SHA-256: abc/);
});
