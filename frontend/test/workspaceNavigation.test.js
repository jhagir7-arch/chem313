import test from 'node:test';
import assert from 'node:assert/strict';
import {SECTIONS,sectionForWorkspace,workspaceNeedsLabs} from '../src/workspaceNavigation.mjs';
test('four task destinations keep engine input and output in one calculation section',()=>{
 assert.deepEqual(SECTIONS.map(x=>x.id),['learn','molecule','calculate','records']);
 for(const id of ['calculate','orcaInput','orca'])assert.equal(sectionForWorkspace(id),'calculate');
 for(const id of ['qchem','help'])assert.equal(sectionForWorkspace(id),'learn');
 for(const id of ['notes','history'])assert.equal(sectionForWorkspace(id),'records');
 for(const id of ['science','connections','recipes','measurements','study'])assert.equal(workspaceNeedsLabs(id),true);
 assert.equal(workspaceNeedsLabs('orcaInput'),false);
});
