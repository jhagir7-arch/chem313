// Public product index: scope is explicit; availability is checked at runtime.
export const FEATURE_INDEX = Object.freeze([
 {id:'CHEM-001',title:'Build and count atoms',workspace:'structures',scope:'Included · local RDKit and molecular editor',evidence:'frontend/test/beginner.test.js'},
 {id:'CHEM-002',title:'Compare starting shapes',workspace:'structures',scope:'Included · force-field energies, not quantum results',evidence:'frontend/test/beginner.test.js'},
 {id:'CHEM-003',title:'Energy comparison chart',workspace:'structures',scope:'Included · same molecule, model and units only',evidence:'frontend/src/ShapeEnergyChart.tsx'},
 {id:'CHEM-004',title:'Keyboard controls for 3D',workspace:'structures',scope:'Included · rotate, zoom and fit buttons',evidence:'frontend/src/Viewer.tsx'},
 {id:'CHEM-005',title:'ORCA calculation',workspace:'calculate',scope:'External licensed installation required · real run pending',evidence:'backend/tests/test_orca_runtime.py'},
 {id:'CHEM-006',title:'Q-Chem guided lesson',workspace:'qchem',scope:'Preparation included · execution needs a licensed installation',evidence:'frontend/test/qchemStudy.test.js'},
 {id:'CHEM-007',title:'Molecule identity check',workspace:'qchem',scope:'Coordinate-derived InChI check · not experimental validation',evidence:'backend/tests/test_identity.py'},
 {id:'CHEM-008',title:'Export and project records',workspace:'history',scope:'Included · source files and run records',evidence:'backend/src/hypothesislab/store.py'},
 {id:'CHEM-009',title:'Qwen assistance',workspace:'study',scope:'Labs · optional, experimental, review required',evidence:'backend/tests/test_qchem_coach.py'},
 {id:'CHEM-010',title:'Additional engines and scripts',workspace:'connections',scope:'Labs · separate availability and license checks',evidence:'backend/src/hypothesislab/engine_registry.py'},
]);
export function searchFeatures(query='') {
 const words=query.toLowerCase().trim().split(/\s+/).filter(Boolean);
 return FEATURE_INDEX.filter(row=>words.every(word=>Object.values(row).join(' ').toLowerCase().includes(word)));
}
