// Small, dependency-free helpers: SDF parsing, geometry maths and formatting. No chemistry
// rules live here; the engine's catalog decides what is allowed.

export type Atom = {el: string; x: number; y: number; z: number};
export type Bond = {a: number; b: number; order: number};

/** A molecule the user can work with: a catalog starter, something typed/drawn, or an imported file. */
export type Molecule = {
  id: string;
  name: string;
  formula: string | null;
  source: 'starter' | 'smiles' | 'molblock';
  smiles?: string;
  molblock?: string;
};

export function parseSdf(sdf: string): {atoms: Atom[]; bonds: Bond[]} {
  const lines = sdf.split(/\r?\n/);
  const counts = lines[3] ?? '';
  const nAtoms = parseInt(counts.slice(0, 3), 10) || 0;
  const nBonds = parseInt(counts.slice(3, 6), 10) || 0;
  const atoms: Atom[] = [];
  for (let i = 0; i < nAtoms; i++) {
    const l = lines[4 + i] ?? '';
    atoms.push({x: parseFloat(l.slice(0, 10)), y: parseFloat(l.slice(10, 20)), z: parseFloat(l.slice(20, 30)), el: l.slice(31, 34).trim()});
  }
  const bonds: Bond[] = [];
  for (let i = 0; i < nBonds; i++) {
    const l = lines[4 + nAtoms + i] ?? '';
    bonds.push({a: parseInt(l.slice(0, 3), 10) - 1, b: parseInt(l.slice(3, 6), 10) - 1, order: parseInt(l.slice(6, 9), 10) || 1});
  }
  return {atoms, bonds};
}

export const dist = (p: Atom, q: Atom) => Math.hypot(p.x - q.x, p.y - q.y, p.z - q.z);

/** Electron count from a neutral-formula SDF plus formal charge; null when an element is unknown here. */
const Z: Record<string, number> = {H: 1, He: 2, Li: 3, Be: 4, B: 5, C: 6, N: 7, O: 8, F: 9, Ne: 10, Na: 11, Mg: 12, Al: 13, Si: 14, P: 15, S: 16, Cl: 17, Ar: 18, K: 19, Ca: 20, Br: 35, I: 53};
export function electronCount(atoms: Atom[], formalCharge: number): number | null {
  let total = 0;
  for (const a of atoms) {
    const z = Z[a.el];
    if (z === undefined) return null;
    total += z;
  }
  return total - formalCharge;
}

export const ELEMENT_COLOR: Record<string, string> = {
  C: 'var(--el-c)', H: 'var(--el-h)', O: 'var(--el-o)', N: 'var(--el-n)', S: 'var(--el-s)', F: 'var(--el-halogen)', Cl: 'var(--el-halogen)', Br: 'var(--el-halogen)',
};

export const fmt = (v: number | null | undefined, digits = 6) => (v === null || v === undefined || Number.isNaN(v) ? '—' : v.toFixed(digits));

export const KCAL_PER_KJ = 1 / 4.184;
export const KCAL_PER_HARTREE = 627.509474;
export type EnergyUnit = 'kcal' | 'kJ' | 'Eh';
export const convertEnergy = (kcal: number, unit: EnergyUnit) => (unit === 'kcal' ? kcal : unit === 'kJ' ? kcal / KCAL_PER_KJ : kcal / KCAL_PER_HARTREE);
export const unitLabel = (unit: EnergyUnit) => (unit === 'kcal' ? 'kcal·mol⁻¹' : unit === 'kJ' ? 'kJ·mol⁻¹' : 'Eh');

/** Stable id for a user molecule from its input text. */
export function moleculeId(prefix: string, text: string): string {
  let h = 2166136261;
  for (let i = 0; i < text.length; i++) {
    h ^= text.charCodeAt(i);
    h = Math.imul(h, 16777619) >>> 0;
  }
  return `${prefix}-${h.toString(16)}`;
}
