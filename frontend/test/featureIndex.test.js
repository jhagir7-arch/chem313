import test from 'node:test';
import assert from 'node:assert/strict';
import {FEATURE_INDEX,searchFeatures} from '../src/featureIndex.mjs';
test('index IDs are unique and search covers availability limits',()=>{
 assert.equal(new Set(FEATURE_INDEX.map(x=>x.id)).size,FEATURE_INDEX.length);
 assert.equal(searchFeatures('ORCA licensed')[0].id,'CHEM-005');
 assert.equal(searchFeatures('quantum results')[0].id,'CHEM-002');
 assert.equal(searchFeatures('nothing matches here').length,0);
});
