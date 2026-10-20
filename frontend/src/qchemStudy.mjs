import {qchemAtoms,qchemInput,validateQchemState} from './qchemInput.mjs';

export const QCHEM_MOLECULES=Object.freeze([
 {id:'water',name:'Water',smiles:'O',formula:'H2O',atoms:3,composition:{H:2,O:1},hint:'Start here: one oxygen and two hydrogens.'},
 {id:'methane',name:'Methane',smiles:'C',formula:'CH4',atoms:5,composition:{C:1,H:4},hint:'Practice counting hydrogens around carbon.'},
 {id:'ethanol',name:'Ethanol',smiles:'CCO',formula:'C2H6O',atoms:9,composition:{C:2,H:6,O:1},hint:'Find the hydrogens hidden in a skeletal drawing.'},
]);

export function checkedQchemLesson(geometry,molecule,charge,multiplicity){
 const selected=QCHEM_MOLECULES.find(item=>item.id===molecule);
 if(!selected)throw Error('Choose water, methane or ethanol for this lesson.');
 const atoms=qchemAtoms(geometry);
 const composition={};for(const atom of atoms)composition[atom.symbol]=(composition[atom.symbol]??0)+1;
 if(atoms.length!==selected.atoms||Object.keys(composition).length!==Object.keys(selected.composition).length||Object.entries(selected.composition).some(([key,count])=>composition[key]!==count))throw Error('The generated atoms do not match the selected molecule. Build the starting structure again.');
 const state=validateQchemState(atoms,charge,multiplicity);
 if(state.charge!==0||state.multiplicity!==1)throw Error('This starter lesson supports the neutral singlet only: charge 0 and multiplicity 1. Reset the lesson settings.');
 return {atoms,state,input:qchemInput(geometry,state),selected};
}

export function qchemCoordinatePayload(geometry,molecule){
 const checked=checkedQchemLesson(geometry,molecule,0,1);
 return {molecule,atoms:checked.atoms.map(atom=>({element:atom.symbol,x:atom.coordinates[0],y:atom.coordinates[1],z:atom.coordinates[2]}))};
}

export async function qchemStudyRecord({project,molecule,geometry,charge,multiplicity,understanding,notes='',help=[],serverPreparation=null}){
 const checked=checkedQchemLesson(geometry,molecule,charge,multiplicity);
 if(!understanding?.atom_count_correct||!understanding?.coordinates_checked||!understanding?.single_point_checked)throw Error('Complete the structure and single-point understanding checks before saving.');
 const input=serverPreparation?.input_text??checked.input;
 const hash=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(input)))).map(value=>value.toString(16).padStart(2,'0')).join('');
 if(serverPreparation&&(!serverPreparation.identity_check||serverPreparation.identity_check.status!=='match'||serverPreparation.input_sha256!==hash))throw Error('The local coordinate identity check must pass before saving this preparation.');
 return {
  schema:'openchem.qchem-preparation.v1',status:'PREPARED_NOT_RUN',project,created_at:new Date().toISOString(),
  molecule:{id:molecule,name:checked.selected.name,smiles:checked.selected.smiles,formula:checked.selected.formula},
  geometry:{source:'Local RDKit force-field starting conformer',force_field:geometry.force_field??null,seed:geometry.seed??null,coordinate_units:'angstrom',atomic_numbers:checked.atoms.map(atom=>atom.atomicNumber),coordinates:checked.atoms.map(atom=>atom.coordinates),sdf:geometry.sdf??null},
  calculation:{engine:'Q-Chem',job_type:'single_point',method:'HF',basis:'def2-SVP',charge:checked.state.charge,multiplicity:checked.state.multiplicity,electrons:checked.state.electrons},
  exact_input:input,input_sha256:hash,coordinate_identity:serverPreparation?{status:serverPreparation.identity_check.status,expected_inchikey:serverPreparation.identity_check.expected_inchikey??null,observed_inchikey:serverPreparation.identity_check.observed_inchikey??null,scope:serverPreparation.scope??serverPreparation.identity_check.scope??null}:null,
  learning:{...understanding,notes:notes.slice(0,2000),assessment:'Practice checks completed in the app; not an independent assessment of understanding.'},
  assistance:help.slice(-12),
  limitations:['Q-Chem has not been run. A separate licensed installation is required.','The coordinate identity receipt checks whether exported coordinates reproduce the selected molecule\'s standard InChI; it does not validate geometry quality, electronic state, method choice, or results.','The starting geometry is not a quantum-optimized or experimentally validated structure.','HF/def2-SVP is a teaching example, not a general research-method recommendation.','A single point holds nuclei fixed; it does not predict reaction products, rates or medication behavior.'],
  references:[{title:'Q-Chem molecular coordinate input',url:'https://manual.q-chem.com/7.0/Ch3.S3.SS1.html'}],
 };
}
