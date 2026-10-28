import {test} from 'node:test';
import {strict as assert} from 'node:assert';
import {DrawingStore} from '../src/drawing.ts';

test('drawings remain associated with their molecule across navigation', async () => {
  const store = new DrawingStore();
  store.save('a', 'drawing A');
  store.save('b', 'drawing B');
  assert.equal(store.get('a'), 'drawing A');
  assert.equal(store.get('b'), 'drawing B');
});

test('run takes the latest editor snapshot and rejects empty or failed snapshots', async () => {
  const store = new DrawingStore();
  store.save('a', 'old');
  assert.equal(await store.snapshot('a', async () => 'latest'), 'latest');
  await assert.rejects(() => store.snapshot('a', async () => ''), /empty/i);
  await assert.rejects(() => store.snapshot('a', async () => { throw new Error('editor failed'); }), /editor failed/);
});
