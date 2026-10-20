// Q-Chem 7.0 syntax checked against https://manual.q-chem.com/7.0/Ch3.S3.SS1.html
// and https://manual.q-chem.com/7.0/sect_ovocv-analysis.html (October 2026).
const SYMBOLS=Object.freeze({1:'H',6:'C',8:'O'});
const fail=message=>{throw Error(message);};

function requiredInteger(value,label){
 if(typeof value==='number'&&Number.isSafeInteger(value))return value;
 if(typeof value!=='string'||!/^[+-]?\d+$/.test(value))fail(`${label} is required and must be an integer.`);
 const parsed=Number(value);
 if(!Number.isSafeInteger(parsed))fail(`${label} must be a safe integer.`);
 return parsed;
}

export function qchemAtoms(geometry){
 const numbers=geometry?.atomic_numbers;
 const coordinates=geometry?.coordinates;
 if(!Array.isArray(numbers)||!Array.isArray(coordinates)||!numbers.length||numbers.length!==coordinates.length)fail('Q-Chem preparation needs equally sized atomic-number and coordinate arrays.');
 if(geometry.coordinate_units!=='angstrom')fail('Q-Chem preparation requires coordinates in angstrom.');
 return numbers.map((atomicNumber,index)=>{
  if(!Number.isInteger(atomicNumber)||!Object.hasOwn(SYMBOLS,atomicNumber))fail('Q-Chem preparation supports integer hydrogen, carbon, and oxygen atomic numbers only.');
  const point=coordinates[index];
  if(!Array.isArray(point)||point.length!==3||point.some(value=>!Number.isFinite(value)))fail('Q-Chem preparation found a malformed coordinate.');
  return {symbol:SYMBOLS[atomicNumber],atomicNumber,coordinates:[...point]};
 });
}

export function validateQchemState(atoms,chargeValue,multiplicityValue){
 const charge=requiredInteger(chargeValue,'Charge');
 const multiplicity=requiredInteger(multiplicityValue,'Multiplicity');
 if(multiplicity<1)fail('Multiplicity must be a positive integer.');
 const electrons=atoms.reduce((total,atom)=>total+atom.atomicNumber,0)-charge;
 if(electrons<1)fail('Charge leaves no electrons for this geometry.');
 if(multiplicity>electrons+1)fail('Multiplicity is too large for this electron count.');
 if((electrons-(multiplicity-1))%2!==0)fail('Electron count and multiplicity have incompatible parity.');
 return {charge,multiplicity,electrons};
}

export function qchemInput(geometry,{charge=0,multiplicity=1,basis='def2-SVP'}={}){
 const atoms=qchemAtoms(geometry);
 const state=validateQchemState(atoms,charge,multiplicity);
 if(basis!=='def2-SVP')fail('This beginner Q-Chem preparation uses def2-SVP.');
 const rows=atoms.map(atom=>`${atom.symbol} ${atom.coordinates.map(value=>value.toFixed(8)).join(' ')}`);
 return ['$molecule',`${state.charge} ${state.multiplicity}`,...rows,'$end','','$rem','JOBTYPE sp','METHOD hf',`BASIS ${basis}`,'$end',''].join('\n');
}
