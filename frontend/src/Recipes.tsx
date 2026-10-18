import React,{useEffect,useRef,useState} from 'react';
import {artifactBytes,request,saveBytes,saveText,type Artifact} from './api';
import {DEFAULT_RECIPE,parseRecipeSource,recipeSource,type RecipeStep} from './recipeSchema.mjs';

type Operation={operation:string;label:string;engine:string;units:string;limitations:string};
type Preview={preview_token:string;request_sha256:string;effect?:string;operation?:Operation};
type StepReview={step:RecipeStep;receipt:Preview;operation?:Operation};
type Job={id:string;state:string;operation:string;result?:unknown;error?:string;artifacts?:Artifact[];logs?:string|string[]};
const active=new Set(['QUEUED','RUNNING']);
const terminal=new Set(['SUCCEEDED','FAILED','CANCELLED','INTERRUPTED']);

async function sourceHash(source:string){
 const digest=await crypto.subtle.digest('SHA-256',new TextEncoder().encode(source));
 return Array.from(new Uint8Array(digest)).map(byte=>byte.toString(16).padStart(2,'0')).join('');
}
function errorText(error:unknown){return error instanceof Error?error.message:String(error)}

export default function Recipes({project}:{project:string}){
 const [source,setSource]=useState(()=>recipeSource(DEFAULT_RECIPE));
 const [operations,setOperations]=useState<Operation[]>([]);
 const [reviews,setReviews]=useState<StepReview[]|null>(null);
 const [reviewSource,setReviewSource]=useState('');
 const [reviewHash,setReviewHash]=useState('');
 const [reviewProject,setReviewProject]=useState('');
 const [jobs,setJobs]=useState<(Job|null)[]>([]);
 const [resultSteps,setResultSteps]=useState<RecipeStep[]>([]);
 const [resultProject,setResultProject]=useState('');
 const [busy,setBusy]=useState('');
 const [isReviewing,setIsReviewing]=useState(false);
 const [isRunning,setIsRunning]=useState(false);
 const [isCancelling,setIsCancelling]=useState(false);
 const [error,setError]=useState('');
 const mounted=useRef(true),generation=useRef(0),projectRef=useRef(project),sourceRef=useRef(source),runActive=useRef(false),runSerial=useRef(0),stopRequested=useRef<number|null>(null),activeJob=useRef<string|null>(null);
 projectRef.current=project;
 sourceRef.current=source;
 const live=(mark:number)=>mounted.current&&generation.current===mark;
 const invalidate=()=>{setReviews(null);setReviewSource('');setReviewHash('');setReviewProject('');};
 const edit=(value:string)=>{sourceRef.current=value;generation.current++;setIsReviewing(false);setSource(value);invalidate();};
 const recipe=()=>parseRecipeSource(source,new Set(operations.map(operation=>operation.operation)));

 useEffect(()=>{mounted.current=true;return()=>{mounted.current=false;generation.current++;};},[]);
 useEffect(()=>{const mark=++generation.current;setIsReviewing(false);setError('');invalidate();request('/api/science/operations').then(value=>{if(live(mark))setOperations(value.operations??[])}).catch(value=>{if(live(mark))setError(errorText(value));});},[project]);

 async function readFile(file:File){
  try {
   if(file.size>200*1024)throw Error('Recipe files must be 200 KB or smaller.');
   const value=new TextDecoder('utf-8',{fatal:true,ignoreBOM:true}).decode(await file.arrayBuffer());
   parseRecipeSource(value,new Set(operations.map(operation=>operation.operation)));
   edit(value);
  } catch(value) { setError(errorText(value)); }
 }
 async function review(){
  if(isReviewing||runActive.current)return;
  const mark=generation.current,requestedProject=project;
  setIsReviewing(true);setError('');
  try {
   if(!operations.length)throw Error('The scientific operation registry is still loading.');
   const exact=source; const parsed=recipe(); const hash=await sourceHash(exact);
   if(!live(mark)||requestedProject!==projectRef.current||sourceRef.current!==exact)return;
   const next:StepReview[]=[];
   for(const step of parsed.steps){
    const receipt=await request('/api/preview',{action:'science.run',params:{operation:step.operation,inputs:step.inputs},project:requestedProject}) as Preview;
    if(!receipt.preview_token)throw Error(`No review receipt was returned for ${step.name}.`);
    if(!live(mark)||requestedProject!==projectRef.current||sourceRef.current!==exact)return;
    next.push({step,receipt,operation:operations.find(operation=>operation.operation===step.operation)});
   }
   if(live(mark)&&requestedProject===projectRef.current&&sourceRef.current===exact){
    setReviewSource(exact);setReviewHash(hash);setReviewProject(requestedProject);setReviews(next);setResultSteps(parsed.steps);setResultProject(requestedProject);setJobs(Array.from({length:next.length},()=>null));
   }
  } catch(value) { if(live(mark))setError(errorText(value)); }
  finally { if(live(mark))setIsReviewing(false); }
 }
 async function poll(job:Job,mark:number,runId:number,index:number):Promise<Job>{
  let current=job;
  while(active.has(current.state)){
   await new Promise<void>(resolve=>window.setTimeout(resolve,900));
   current=await request('/api/jobs/'+encodeURIComponent(current.id)) as Job;
   if(runSerial.current===runId&&mounted.current)setJobs(rows=>rows.map((row,rowIndex)=>rowIndex===index?current:row));
  }
  return current;
 }
 async function run(){
  if(!reviews||runActive.current||isReviewing)return;
  const mark=generation.current,requestedProject=project;
  const runId=++runSerial.current;stopRequested.current=null;runActive.current=true;setIsRunning(true);setError('');
  try {
   const currentHash=await sourceHash(source);
   if(runSerial.current!==runId||!live(mark)||requestedProject!==projectRef.current||sourceRef.current!==reviewSource||reviewProject!==requestedProject||currentHash!==reviewHash)throw Error('Recipe source or project changed. Review every step again.');
   for(let index=0;index<reviews.length;index++){
    if(stopRequested.current===runId){if(live(mark))setError('Cancellation was requested. Remaining steps were not scheduled.');break;}
    if(runSerial.current!==runId||!live(mark)||requestedProject!==projectRef.current||sourceRef.current!==reviewSource)break;
    const item=reviews[index];
    let response:unknown;
    try {
     response=await request('/api/execute',{action:'science.run',params:{operation:item.step.operation,inputs:item.step.inputs},project:requestedProject,approved:true,preview_token:item.receipt.preview_token});
    } catch(value) {
     const message=errorText(value);
     if(/preview|receipt|expired|consumed/i.test(message))throw Error(`Review receipt for ${item.step.name} is no longer usable. Review the recipe again; it will not replay automatically.`);
     throw value;
    }
    const job=(response as {result?:{job_id?:string};job?:Job}).job??{id:(response as {result:{job_id:string}}).result.job_id,state:'QUEUED',operation:item.step.operation};
    activeJob.current=job.id;
    if(runSerial.current===runId&&mounted.current)setJobs(rows=>rows.map((row,rowIndex)=>rowIndex===index?job:row));
    const completed=await poll(job,mark,runId,index);activeJob.current=null;
    if(stopRequested.current===runId){if(live(mark))setError('Cancellation was requested. Remaining steps were not scheduled.');break;}
    if(runSerial.current!==runId||!live(mark)||requestedProject!==projectRef.current||sourceRef.current!==reviewSource)break;
    setJobs(rows=>rows.map((row,rowIndex)=>rowIndex===index?completed:row));
    if(!terminal.has(completed.state)||completed.state!=='SUCCEEDED'){
     setError(`${item.step.name} stopped the recipe: ${completed.error??completed.state}. Remaining steps were not scheduled.`);break;
    }
   }
  } catch(value) { if(runSerial.current===runId&&live(mark))setError(errorText(value)); }
  finally { if(runSerial.current===runId){activeJob.current=null;stopRequested.current=null;runActive.current=false;if(mounted.current){invalidate();setIsRunning(false);setIsCancelling(false);}} }
 }
 async function cancel(){
  const jobId=activeJob.current;if(!jobId||isCancelling)return;const mark=generation.current,runId=runSerial.current;stopRequested.current=runId;setIsCancelling(true);
  try {const value=await request('/api/jobs/'+encodeURIComponent(jobId)+'/cancel',{approved:true}) as Job;if(runSerial.current===runId&&live(mark))setJobs(rows=>rows.map(row=>row?.id===value.id?value:row));}
  catch(value){if(runSerial.current===runId&&live(mark))setError(errorText(value));}
  finally{if(runSerial.current===runId&&mounted.current)setIsCancelling(false);}
 }
 async function exportArtifact(artifact:Artifact){try{setBusy('Exporting artifact');saveBytes(await artifactBytes(artifact),artifact.relative_path.split('/').pop()!);}catch(value){setError(errorText(value));}finally{setBusy('');}}
 const reviewed=!!reviews&&reviewProject===project&&source===reviewSource;
 const locked=isReviewing||isRunning;
 return <section className="recipe-workspace">
  {error&&<div className="banner error" role="alert"><strong>Recipe needs attention</strong><span>{error}</span><button onClick={()=>setError('')} aria-label="Dismiss error">×</button></div>}
  <div className="recipe-ledger"><span>REPRODUCIBLE RECIPE</span><b>author JSON → review steps → run in order</b><small>Independent, sequential scientific operations only. Recipes cannot interpolate outputs into later inputs and cannot execute Python or shell commands.</small></div>
  <div className="recipe-grid"><div className="panel recipe-editor"><div className="panel-header"><h2>Recipe source</h2><div><label className="file-button">Open .json<input disabled={locked} type="file" accept="application/json,.json" onChange={event=>{const file=event.target.files?.[0];if(file)readFile(file);event.currentTarget.value='';}}/></label><button className="text-button" disabled={isReviewing} onClick={()=>saveText(source,'openchem-recipe.json','application/json')}>Export source ↗</button></div></div><textarea disabled={locked} className="recipe-source" aria-label="Recipe JSON source" value={source} spellCheck={false} onChange={event=>edit(event.target.value)}/><div className="recipe-actions"><button className="secondary" disabled={locked} onClick={()=>edit(recipeSource(DEFAULT_RECIPE))}>Load examples</button><button className="primary" disabled={locked||!operations.length} onClick={review}>Review all steps</button></div><p className="quiet-note">Exactly <code>version</code>, <code>name</code>, and <code>steps</code>; each step has exactly <code>name</code>, <code>operation</code>, and <code>inputs</code>. Files are UTF-8 JSON up to 200 KB.</p></div>
  <div className="panel recipe-review"><div className="panel-header"><h2>Immutable review</h2><span className="tag">{reviewed?'READY':'NOT REVIEWED'}</span></div>{reviewed?<div className="recipe-review-body"><dl className="science-receipt"><div><dt>Project</dt><dd>{reviewProject}</dd></div><div><dt>Source SHA-256</dt><dd className="science-digest">{reviewHash}</dd></div><div><dt>Steps</dt><dd>{reviews.length}</dd></div></dl><details open><summary>Exact reviewed source</summary><pre className="science-schema">{reviewSource}</pre></details><div className="recipe-step-reviews">{reviews.map((item,index)=><article key={item.step.name}><strong>{index+1}. {item.step.name}</strong><code>{item.step.operation}</code><small>{item.operation?.engine??'Approved operation'} · {item.operation?.units??''}</small><small>Request SHA-256: {item.receipt.request_sha256}</small></article>)}</div><button className="primary full" disabled={locked} onClick={run}>Run reviewed recipe</button><button className="secondary full" disabled={!activeJob.current||isCancelling} onClick={cancel}>{isCancelling?'Cancelling active step…':'Cancel active step'}</button></div>:<p className="quiet-note">Review obtains one single-use receipt per allowed operation. Editing source or changing project invalidates every receipt.</p>}</div></div>
  <div className="panel recipe-results"><div className="panel-header"><h2>Step results</h2>{resultProject&&<small>Recorded in {resultProject}</small>}<span>{isReviewing?'Reviewing steps':isRunning?'Running reviewed recipe':busy||(jobs.some(Boolean)?'Run finished':'Awaiting reviewed run')}</span>{activeJob.current&&<button className="secondary" disabled={isCancelling} onClick={cancel}>{isCancelling?'Cancelling…':'Cancel active step'}</button>}</div>{jobs.length?<table><thead><tr><th>Step</th><th>Operation</th><th>State</th><th>Result</th></tr></thead><tbody>{jobs.map((job,index)=>{const step=resultSteps[index];return <tr key={step?.name??index}><td>{step?.name??`Step ${index+1}`}</td><td><code>{step?.operation??job?.operation??'—'}</code></td><td>{job?.state??'NOT SCHEDULED'}</td><td>{job?.result?<details><summary>View result</summary><pre className="science-result">{JSON.stringify(job.result,null,2)}</pre></details>:job?.error??'—'}{job?.artifacts?.map(artifact=><button className="text-button" key={artifact.relative_path} onClick={()=>exportArtifact(artifact)}>Export {artifact.relative_path.split('/').pop()} ↗</button>)}</td></tr>})}</tbody></table>:<p className="science-empty">A reviewed recipe will record each job here. OpenChem preserves the existing job audit, original request, and accepted report artifacts for every executed step.</p>}</div>
  <div className="panel recipe-operations"><div className="panel-header"><h2>Available operation scope</h2><span>{operations.length} operations</span></div><div className="recipe-operation-list">{operations.map(operation=><article key={operation.operation}><strong>{operation.label}</strong><code>{operation.operation}</code><p><b>Units:</b> {operation.units}</p><p><b>Scope:</b> {operation.limitations}</p></article>)}</div></div>
 </section>;
}
