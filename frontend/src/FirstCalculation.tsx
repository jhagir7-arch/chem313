import React,{useEffect,useRef,useState} from 'react';
import Viewer from './Viewer';
import {artifactBytes,request,saveBytes,saveText,type Artifact} from './api';
import './first-calculation.css';

type Props={project:string};
type Choice={id:'ethanol'|'water'|'methane';name:string;smiles:'CCO'|'O'|'C';outcome:string};
type Relaxed={name?:string;formula:string;canonical_smiles:string;inchikey:string;identity_status?:string;initial_sdf:string;sdf:string;initial_energy_kcal_mol:number;final_energy_kcal_mol:number;energy_change_kcal_mol:number;force_field:'MMFF94';converged:boolean;rdkit_version:string;iterations_limit:1000;scope:string;svg?:string};
const choices:Choice[]=[
 {id:'ethanol',name:'Ethanol',smiles:'CCO',outcome:'The force field will adjust this starting shape toward a local lower-energy geometry.'},
 {id:'water',name:'Water',smiles:'O',outcome:'The force field will refine this starting water geometry.'},
 {id:'methane',name:'Methane',smiles:'C',outcome:'The force field will refine this starting methane geometry.'}
];
const amount=(value:number)=>value.toLocaleString(undefined,{maximumFractionDigits:4})+' kcal/mol';

export default function FirstCalculation({project}:Props){
 const [choice,setChoice]=useState<Choice>(choices[0]);
 const [seed,setSeed]=useState(42);
 const [review,setReview]=useState<{token:string;project:string;params:{smiles:Choice['smiles'];seed:number}}|null>(null);
 const [result,setResult]=useState<Relaxed|null>(null);
 const [artifacts,setArtifacts]=useState<Artifact[]>([]);
 const [busy,setBusy]=useState(false),[error,setError]=useState(''),[reactionAnswer,setReactionAnswer]=useState<'no'|null>(null);
 const epoch=useRef(0),projectRef=useRef(project);projectRef.current=project;
 const current=()=>projectRef.current===project;
 useEffect(()=>{epoch.current++;setReview(null);setResult(null);setArtifacts([]);setError('');setBusy(false);setReactionAnswer(null);},[project]);
 function select(id:string){const next=choices.find(item=>item.id===id)!;epoch.current++;setChoice(next);setReview(null);setResult(null);setArtifacts([]);setError('');setReactionAnswer(null);}
 async function run(){
  const stamp=++epoch.current,target=project,params={smiles:choice.smiles,seed};setBusy(true);setError('');setReview(null);setResult(null);setArtifacts([]);setReactionAnswer(null);
  try{
   const preview=await request('/api/preview',{action:'molecule.relax_geometry',params,project:target});
   if(stamp!==epoch.current||projectRef.current!==target)return;
   if(!preview.preview_token)throw Error('The local calculation review receipt was not returned.');
   setReview({token:preview.preview_token,project:target,params});
   const executed=await request('/api/execute',{action:'molecule.relax_geometry',params,project:target,approved:true,preview_token:preview.preview_token});
   if(stamp!==epoch.current||projectRef.current!==target)return;
   setReview(null);setResult(executed.result as Relaxed);setArtifacts(executed.artifacts??[]);
  }catch(e){if(stamp===epoch.current&&current())setError(e instanceof Error?e.message:String(e));}
  finally{if(stamp===epoch.current&&current())setBusy(false);}
 }
 async function download(a:Artifact){try{saveBytes(await artifactBytes(a),a.relative_path.split('/').pop()!);}catch(e){setError(e instanceof Error?e.message:String(e));}}
 function saveRecord(){if(!result)return;saveText(JSON.stringify({schema:'openchem.first-calculation.v1',project,action:'molecule.relax_geometry',params:{smiles:choice.smiles,seed},model:{force_field:result.force_field,rdkit_version:result.rdkit_version,iterations_limit:result.iterations_limit},result:{formula:result.formula,canonical_smiles:result.canonical_smiles,inchikey:result.inchikey,initial_energy_kcal_mol:result.initial_energy_kcal_mol,final_energy_kcal_mol:result.final_energy_kcal_mol,energy_change_kcal_mol:result.energy_change_kcal_mol,converged:result.converged,scope:result.scope},artifacts:artifacts.map(a=>({path:a.relative_path,sha256:a.sha256,bytes:a.bytes}))},null,2),'first-calculation-record.json','application/json');}
 const chartMin=Math.min(result?.initial_energy_kcal_mol??0,result?.final_energy_kcal_mol??0,0),chartMax=Math.max(result?.initial_energy_kcal_mol??0,result?.final_energy_kcal_mol??0,0),chartRange=Math.max(chartMax-chartMin,0.000001);
 const signedBar=(value:number)=>{const zero=(-chartMin/chartRange)*100,point=((value-chartMin)/chartRange)*100;return {left:Math.min(zero,point)+'%',width:Math.max(Math.abs(point-zero),1)+'%'};};
 return <section className="first-calculation" aria-busy={busy} aria-labelledby="first-calculation-title">
  <header className="first-calculation-heading"><span className="eyebrow">FIRST CALCULATION</span><h2 id="first-calculation-title">Relax a molecular shape</h2><p>Run a real local RDKit/MMFF94 force-field geometry relaxation. The result and its source files are retained in this project.</p></header>
  {error&&<div className="banner error" role="alert">{error}</div>}
  <div className="first-calculation-grid">
   <section className="panel first-choice"><h3>Choose a familiar molecule</h3><label>Molecule<select aria-label="First calculation molecule" value={choice.id} disabled={busy} onChange={e=>select(e.target.value)}>{choices.map(item=><option value={item.id} key={item.id}>{item.name}</option>)}</select></label><dl><div><dt>Structure</dt><dd><code>{choice.smiles}</code></dd></div><div><dt>Starting seed</dt><dd><input aria-label="Reproducible seed" type="number" min="0" max="2147483647" disabled={busy} value={seed} onChange={e=>{setSeed(Number(e.target.value)||0);setReview(null);setResult(null);setArtifacts([]);setReactionAnswer(null);}}/></dd></div></dl><p className="quiet-note">{choice.outcome}</p><button className="primary" disabled={busy} onClick={run}>{busy?'Running local shape calculation…':'Run shape calculation'}</button>{review&&<p className="quiet-note" role="status">Reviewing the exact local request before it is saved and executed.</p>}</section>
   <aside className="panel first-expectation"><h3>What this calculation does</h3><dl><div><dt>Engine</dt><dd>RDKit / MMFF94</dd></div><div><dt>Maximum iterations</dt><dd>1,000</dd></div><div><dt>Energy unit</dt><dd>kcal/mol</dd></div></dl><p>It searches for a lower-energy shape of this same molecule. The two energies only compare the before and after shapes from this one run.</p><p className="quiet-note">It does not prove a reaction, predict a new substance, or provide a quantum calculation.</p></aside>
  </div>
  {result&&<section className="first-result" aria-live="polite">
   <header className="first-result-heading"><div><span className="eyebrow">SAVED LOCAL RESULT · REAL CALCULATION</span><h3>{result.name??choice.name} · {result.formula}</h3><p>Completed report and three artifacts are retained in project <code>{project}</code>.</p></div><span className={'tag '+(result.converged?'':'tag-warning')}>{result.converged?'CONVERGED':'STOPPED AT ITERATION LIMIT'}</span></header>
   <div className="first-result-grid"><section className="panel first-model"><h4>Relaxed 3D molecule</h4><Viewer data={result.sdf}/><p className="quiet-note">Final geometry shown. The initial and final SDF files are available below.</p><details className="identity-receipt"><summary>Identity: {result.identity_status??'MATCH'}</summary><dl><div><dt>InChIKey</dt><dd><code>{result.inchikey}</code></dd></div><div><dt>Canonical SMILES</dt><dd><code>{result.canonical_smiles}</code></dd></div></dl></details></section><section className="panel first-energy"><h4>Energy during this relaxation</h4><p className="energy-unit">MMFF94 energy · kcal/mol · signed scale with zero baseline</p><div className="two-bars" role="img" aria-label={'Signed energy chart: initial '+amount(result.initial_energy_kcal_mol)+', final '+amount(result.final_energy_kcal_mol)+', with a zero baseline'}><div><span>Before</span><div className="bar-track"><b aria-hidden="true" style={{left:(-chartMin/chartRange*100)+'%'}}/><i style={signedBar(result.initial_energy_kcal_mol)}/></div><strong>{amount(result.initial_energy_kcal_mol)}</strong></div><div><span>After</span><div className="bar-track"><b aria-hidden="true" style={{left:(-chartMin/chartRange*100)+'%'}}/><i style={signedBar(result.final_energy_kcal_mol)}/></div><strong>{amount(result.final_energy_kcal_mol)}</strong></div></div><dl className="energy-change"><div><dt>Change</dt><dd>{amount(result.energy_change_kcal_mol)}</dd></div><div><dt>Calculation</dt><dd>{result.force_field} · RDKit {result.rdkit_version}</dd></div></dl><p className="quiet-note">{result.converged?(result.final_energy_kcal_mol<result.initial_energy_kcal_mol?'This converged run found a lower MMFF94 value for this molecule and starting seed.':'This converged run reports the before/after MMFF94 values for this molecule and starting seed.'):'This run stopped at the iteration limit. Inspect the saved geometry and values; it does not establish a converged lower-energy shape.'}</p></section></div>
   <div className="first-notes"><details open><summary>What changed</summary><p>The atom positions were adjusted from the generated starting shape using MMFF94. The saved result identifies the final geometry and force-field energy.</p></details><details><summary>What this does not show</summary><p>It does not establish an experimental structure, a global minimum, a reaction mechanism, biological activity, or energy comparisons with a different molecule.</p></details></div>
   <div className="first-record"><div><strong>Save this calculation record</strong><span>Includes reproducible parameters, model version, values, and saved artifact hashes.</span></div><button className="secondary" onClick={saveRecord}>Download record</button></div>
   <div className="first-artifacts"><strong>Saved project files</strong>{artifacts.map(a=><button className="text-button" key={a.relative_path} onClick={()=>download(a)}>{a.relative_path.split('/').pop()} <small>{a.sha256.slice(0,12)}…</small></button>)}</div>
   <fieldset className="first-feedback"><legend>Did it prove a reaction?</legend><div><button type="button" aria-pressed={reactionAnswer==='no'} onClick={()=>setReactionAnswer('no')}>No</button><button type="button" aria-pressed={false} onClick={()=>setReactionAnswer(null)}>Yes</button></div>{reactionAnswer==='no'?<p role="status">Correct. It only relaxed the shape of the selected molecule.</p>:<p className="quiet-note">Choose an answer to check your interpretation.</p>}</fieldset>
  </section>}
 </section>;
}
