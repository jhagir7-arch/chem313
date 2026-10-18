import assert from 'node:assert/strict';
import test from 'node:test';
import {DEFAULT_RECIPE, parseRecipeSource, recipeSource} from '../src/recipeSchema.mjs';

const allowed = new Set(['pint.convert', 'numpy.summary']);
const source = () => recipeSource(DEFAULT_RECIPE);

test('accepts a bounded declarative recipe with allowed operations', () => {
  assert.deepEqual(parseRecipeSource(source(), allowed), DEFAULT_RECIPE);
});

test('rejects malformed JSON and unknown recipe fields', () => {
  assert.throws(() => parseRecipeSource('{', allowed), /valid JSON/);
  assert.throws(() => parseRecipeSource(JSON.stringify({...DEFAULT_RECIPE, python: 'import os'}), allowed), /exactly version/);
  assert.throws(() => parseRecipeSource(JSON.stringify({...DEFAULT_RECIPE, steps: [{...DEFAULT_RECIPE.steps[0], shell: 'rm -rf'}]}), allowed), /exactly name/);
});

test('rejects arbitrary operations and non-object inputs', () => {
  const arbitrary = {...DEFAULT_RECIPE, steps: [{...DEFAULT_RECIPE.steps[0], operation: 'python.exec'}]};
  assert.throws(() => parseRecipeSource(JSON.stringify(arbitrary), allowed), /allowlist/);
  const invalidInputs = {...DEFAULT_RECIPE, steps: [{...DEFAULT_RECIPE.steps[0], inputs: []}]};
  assert.throws(() => parseRecipeSource(JSON.stringify(invalidInputs), allowed), /inputs/);
});

test('requires 1 to 8 uniquely named steps', () => {
  assert.throws(() => parseRecipeSource(JSON.stringify({...DEFAULT_RECIPE, steps: []}), allowed), /1 to 8/);
  assert.throws(() => parseRecipeSource(JSON.stringify({...DEFAULT_RECIPE, steps: Array.from({length: 9}, (_, i) => ({...DEFAULT_RECIPE.steps[0], name: `Step ${i}`}))}), allowed), /1 to 8/);
  assert.throws(() => parseRecipeSource(JSON.stringify({...DEFAULT_RECIPE, steps: [DEFAULT_RECIPE.steps[0], {...DEFAULT_RECIPE.steps[0]}]}), allowed), /unique/);
});
