const MAX_SOURCE_BYTES = 200 * 1024;
const MAX_NAME = 100;
const MAX_STEP_NAME = 80;
const safeName = /^[A-Za-z0-9][A-Za-z0-9 _.-]*$/;

export const DEFAULT_RECIPE = {
  version: 1,
  name: 'Mass conversion and summary',
  steps: [
    {name: 'Convert milligrams to grams', operation: 'pint.convert', inputs: {value: 1000, from_unit: 'milligram', to_unit: 'gram'}},
    {name: 'Summarize measurements', operation: 'numpy.summary', inputs: {values: [1, 2, 3, 4, 5], unit: 'a.u.'}},
  ],
};

function plainObject(value) {
  return !!value && typeof value === 'object' && !Array.isArray(value) && Object.getPrototypeOf(value) === Object.prototype;
}

function fail(message) { throw new Error(message); }

export function validateRecipe(value, allowedOperations) {
  if (!plainObject(value)) fail('Recipe must be a JSON object.');
  if (Object.keys(value).length !== 3 || !['version', 'name', 'steps'].every(key => Object.hasOwn(value, key))) fail('Recipe must contain exactly version, name, and steps.');
  if (value.version !== 1) fail('Recipe version must be 1.');
  if (typeof value.name !== 'string' || !safeName.test(value.name) || value.name.length > MAX_NAME) fail(`Recipe name must be 1-${MAX_NAME} plain characters.`);
  if (!Array.isArray(value.steps) || value.steps.length < 1 || value.steps.length > 8) fail('Recipe must contain 1 to 8 steps.');
  const names = new Set();
  const allowed = allowedOperations instanceof Set ? allowedOperations : new Set(allowedOperations ?? []);
  const steps = value.steps.map((step, index) => {
    if (!plainObject(step) || Object.keys(step).length !== 3 || !['name', 'operation', 'inputs'].every(key => Object.hasOwn(step, key))) fail(`Step ${index + 1} must contain exactly name, operation, and inputs.`);
    if (typeof step.name !== 'string' || !safeName.test(step.name) || step.name.length > MAX_STEP_NAME) fail(`Step ${index + 1} name must be 1-${MAX_STEP_NAME} plain characters.`);
    if (names.has(step.name)) fail(`Step names must be unique (${step.name}).`);
    names.add(step.name);
    if (typeof step.operation !== 'string' || !allowed.has(step.operation)) fail(`Step ${index + 1} operation is not in the available scientific allowlist.`);
    if (!plainObject(step.inputs)) fail(`Step ${index + 1} inputs must be a JSON object.`);
    return {name: step.name, operation: step.operation, inputs: step.inputs};
  });
  return {version: 1, name: value.name, steps};
}

export function parseRecipeSource(source, allowedOperations) {
  if (typeof source !== 'string') fail('Recipe source must be UTF-8 text.');
  if (new TextEncoder().encode(source).byteLength > MAX_SOURCE_BYTES) fail('Recipe source must be 200 KB or smaller.');
  let parsed;
  try { parsed = JSON.parse(source); } catch { fail('Recipe source is not valid JSON.'); }
  return validateRecipe(parsed, allowedOperations);
}

export function recipeSource(recipe) { return JSON.stringify(recipe, null, 2) + '\n'; }
