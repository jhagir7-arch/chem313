import test from 'node:test';
import assert from 'node:assert/strict';
import {parseOrca} from '../../src/orca/parser.js';
import {demoText} from '../../src/orca/demo.js';
import {comparisonIssues,exportCSV,exportRecord,formula,reviewSummary,xyz} from '../../src/orca/analysis.js';
const pair=()=>[parseOrca(demoText(),'a.out'),parseOrca(demoText(.001),'b.out')];
test('synthetic examples have complete evidence and comparison preconditions',()=>{
 const records=pair();
 assert.equal(records[0].geometry.atoms.length,3);
 assert.equal(records[0].frequencies.length,9);
 assert.equal(records[0].multiJob,false);
 assert.equal(records[0].thermochemistry.gibbs.value,-76.121);
 assert.deepEqual(comparisonIssues(records),[]);
 for(const fact of [records[0].energy,records[0].version,records[0].thermochemistry.gibbs])assert.ok(records[0].lines[fact.line-1].includes(String(fact.value)));
});
test('comparison blocks missing evidence, mixed systems, settings, failures and multijob',()=>{
 const fields=[['multiJob',true],['termination','unknown'],['energy',null],['geometry',null],['scf','not_converged'],['optimization','not_converged'],['optimization','unknown'],['charge',null],['multiplicity',{value:3,line:1}],['version',{value:'5.0',line:1}],['keywords',[]],['keywords',[{value:'HF def2-SVP',line:1}]]];
 for(const [field,value] of fields){const records=pair();records[1][field]=value;assert.ok(comparisonIssues(records).length,field);}
 const unknownScf=pair();unknownScf[1].scf='unknown';assert.ok(comparisonIssues(unknownScf).includes('SCF convergence is unresolved.'));
 const records=pair();records[1].geometry.atoms.push({element:'H',x:1,y:1,z:1});assert.ok(comparisonIssues(records).some(x=>x.includes('compositions')));
 assert.ok(comparisonIssues([]).length);
});
test('review summary keeps incomplete output on hold and never treats extracted facts as validation',()=>{
 const complete=reviewSummary(pair()[0]);
 assert.equal(complete.state,'inspect');
 assert.equal(complete.evidenceCount,7);
 assert.equal(complete.missing.length,0);
 assert.match(complete.nextAction,/does not validate/i);

 const truncated=parseOrca('Program Version 6.0.0\nFINAL SINGLE POINT ENERGY -1.0\n');
 const incomplete=reviewSummary(truncated);
 assert.equal(incomplete.state,'review');
 assert.ok(incomplete.missing.includes('an explicit normal termination'));
 assert.ok(incomplete.missing.includes('an explicit SCF outcome'));
 assert.ok(incomplete.missing.includes('a complete Cartesian geometry'));
 assert.match(incomplete.nextAction,/before using extracted values/i);

 const unrecognized=reviewSummary(parseOrca('not a calculation'));
 assert.equal(unrecognized.state,'hold');
 assert.match(unrecognized.nextAction,/does not infer results/i);
});
test('export is evidence preserving and private raw text is excluded',()=>{
 const r=pair()[0];r.filename='=HYPERLINK("bad")';r.lines.push('PRIVATE_SENTINEL');r.sourceBytes=new Uint8Array([0,1,2]);r.sha256='abc';r.demo=true;
 const record=exportRecord(r);
 assert.equal(record.lines,undefined);assert.equal(record.sourceBytes,undefined);assert.equal(record.source.sha256,'abc');assert.equal(record.source.synthetic,true);
 assert.equal(record.energy.line,r.energy.line);assert.ok(!JSON.stringify(record).includes('PRIVATE_SENTINEL'));
 const csv=exportCSV([r]);assert.ok(csv.includes("\"'=HYPERLINK(\"\"bad\"\")\""));assert.ok(csv.includes('"-76.123456789"'));
 assert.equal(formula([{element:'O'},{element:'H'},{element:'H'}]),'H2O');
 assert.ok(xyz(r.geometry,'bad\ncomment').startsWith('3\nbad comment\nO'));
});
