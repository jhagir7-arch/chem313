/** Tested by Python source-contract guard until the browser build is available. */
export function sameReviewedInput(
  reviewed: {mol: string; project: string} | null,
  latestMol: string,
  activeProject: string
): boolean {
  return reviewed !== null && latestMol === reviewed.mol && activeProject === reviewed.project;
}
