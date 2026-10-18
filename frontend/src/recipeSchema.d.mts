export type RecipeStep = {name:string; operation:string; inputs:Record<string, unknown>};
export type Recipe = {version:1; name:string; steps:RecipeStep[]};
export const DEFAULT_RECIPE: Recipe;
export function validateRecipe(value:unknown, allowedOperations:Iterable<string>):Recipe;
export function parseRecipeSource(source:string, allowedOperations:Iterable<string>):Recipe;
export function recipeSource(recipe:Recipe):string;
