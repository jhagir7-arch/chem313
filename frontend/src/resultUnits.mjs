export const HARTREE_TO_KJ_PER_MOL = 2625.4996394799;
export const HARTREE_TO_EV = 27.211386245988;

export function isFiniteEnergy(value) {
  return typeof value === 'number' && Number.isFinite(value);
}

export function convertElectronicEnergy(hartree) {
  if (!isFiniteEnergy(hartree)) return null;
  return {
    hartree,
    kilojoulesPerMol: hartree * HARTREE_TO_KJ_PER_MOL,
    electronVolts: hartree * HARTREE_TO_EV,
  };
}

export function formatElectronicEnergy(value, digits = 6) {
  return isFiniteEnergy(value) ? value.toFixed(digits) : 'Unavailable';
}
