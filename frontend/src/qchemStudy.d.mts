export const QCHEM_MOLECULES:ReadonlyArray<{id:string;name:string;smiles:string;formula:string;atoms:number;composition:Record<string,number>;hint:string}>;
export function checkedQchemLesson(geometry:any,molecule:string,charge:string|number,multiplicity:string|number):{atoms:any[];state:{charge:number;multiplicity:number;electrons:number};input:string;selected:typeof QCHEM_MOLECULES[number]};
export function qchemCoordinatePayload(geometry:any,molecule:string):{molecule:string;atoms:{element:string;x:number;y:number;z:number}[]};
export function qchemStudyRecord(context:{project:string;molecule:string;geometry:any;charge:string|number;multiplicity:string|number;understanding:any;notes?:string;help?:any[];serverPreparation?:any}):Promise<any>;
