export type QchemAtom={symbol:'H'|'C'|'O';atomicNumber:number;coordinates:[number,number,number]};
export function qchemAtoms(geometry:any):QchemAtom[];
export function validateQchemState(atoms:QchemAtom[],charge:number|string,multiplicity:number|string):{charge:number;multiplicity:number;electrons:number};
export function qchemInput(geometry:any,settings?:{charge?:number|string;multiplicity?:number|string;basis?:'def2-SVP'}):string;
