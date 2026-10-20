const SYMBOLS = Object.freeze({1:'H',6:'C',8:'O'});
function fail(message){throw Error(message);}
export function lessonAtoms(geometry){
 const numbers=geometry?.atomic_numbers,coordinates=geometry?.coordinates;
 if(!Array.isArray(numbers)||!Array.isArray(coordinates)||numbers.length===0||numbers.length!==coordinates.length)fail('Lesson geometry needs equally sized atomic-number and coordinate arrays.');
 if(geometry.coordinate_units!=='angstrom')fail('Lesson geometry coordinates must be in angstrom.');
 if((geometry.atom_count!=null&&geometry.atom_count!==numbers.length)||(geometry.coordinate_count!=null&&geometry.coordinate_count!==coordinates.length))fail('Lesson geometry count metadata does not match its coordinate arrays.');
 return numbers.map((atomicNumber,index)=>{if(!Number.isInteger(atomicNumber)||!Object.hasOwn(SYMBOLS,atomicNumber))fail('Lesson geometry supports integer hydrogen, carbon, and oxygen atomic numbers only.');const point=coordinates[index];if(!Array.isArray(point)||point.length!==3||point.some(value=>!Number.isFinite(value)))fail('Lesson geometry has a malformed coordinate.');return {index:index+1,atomicNumber,symbol:SYMBOLS[atomicNumber],coordinates:[...point]};});
}
export function countFormula(atoms){const counts={C:0,H:0,O:0};for(const atom of atoms){if(!Object.hasOwn(counts,atom.symbol))fail('Unsupported lesson atom.');counts[atom.symbol]++;}return ['C','H','O'].filter(symbol=>counts[symbol]).map(symbol=>symbol+(counts[symbol]===1?'':counts[symbol])).join('');}
export function xyzText(atoms,comment='OpenChem generated starting geometry'){return [String(atoms.length),comment,...atoms.map(atom=>`${atom.symbol} ${atom.coordinates.map(value=>value.toFixed(6)).join(' ')}`)].join('\n')+'\n';}
export function incompleteHydrogenExercise(atoms,variant=0){
 if(!Number.isSafeInteger(variant))fail('Exercise variant must be an integer.');
 const hydrogens=atoms.filter(atom=>atom.atomicNumber===1);if(!hydrogens.length)fail('A hydrogen atom is needed for the incomplete-coordinate exercise.');
 const omitted=hydrogens[((variant%hydrogens.length)+hydrogens.length)%hydrogens.length];
 return {omittedAtomIndex:omitted.index,atoms:atoms.filter(atom=>atom.index!==omitted.index).map(atom=>({...atom,coordinates:[...atom.coordinates]}))};
}
