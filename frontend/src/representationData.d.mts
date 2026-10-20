export type LessonAtom={index:number;atomicNumber:number;symbol:'H'|'C'|'O';coordinates:[number,number,number]};
export function lessonAtoms(geometry:any):LessonAtom[];
export function countFormula(atoms:LessonAtom[]):string;
export function xyzText(atoms:LessonAtom[],comment?:string):string;
export function incompleteHydrogenExercise(atoms:LessonAtom[],variant?:number):{omittedAtomIndex:number;atoms:LessonAtom[]};
