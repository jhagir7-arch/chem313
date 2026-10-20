// Task navigation is independent of the selected chemistry engine.
export const SECTIONS = Object.freeze([
 {id:'learn',label:'Learn',workspace:'qchem',icon:'note',hint:'A guided first study'},
 {id:'molecule',label:'Molecule',workspace:'structures',icon:'structure',hint:'Draw, check and explore'},
 {id:'calculate',label:'Calculate',workspace:'calculate',icon:'orbit',hint:'Prepare, run and interpret'},
 {id:'records',label:'Records',workspace:'history',icon:'folder',hint:'Files and observations'},
]);
const routes=Object.freeze({qchem:'learn',help:'learn',structures:'molecule',calculate:'calculate',orcaInput:'calculate',orca:'calculate',history:'records',notes:'records'});
export const CORE_WORKSPACES=Object.freeze(Object.keys(routes));
export function sectionForWorkspace(id){return routes[id]??'labs';}
export function visibleWorkspaces(tabs,labs){return labs?tabs:tabs.filter(tab=>CORE_WORKSPACES.includes(tab.id));}
export function workspaceNeedsLabs(id){return sectionForWorkspace(id)==='labs';}
