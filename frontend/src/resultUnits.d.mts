export const HARTREE_TO_KJ_PER_MOL: number;
export const HARTREE_TO_EV: number;
export function isFiniteEnergy(value: unknown): value is number;
export function convertElectronicEnergy(hartree: unknown): {
  hartree: number;
  kilojoulesPerMol: number;
  electronVolts: number;
} | null;
export function formatElectronicEnergy(value: unknown, digits?: number): string;
