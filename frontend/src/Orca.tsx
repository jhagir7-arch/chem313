import React,{useEffect,useRef,useState} from 'react';
import {parseOrca} from './orca/parser.js';
import {demoText} from './orca/demo.js';
import {comparisonIssues,exportCSV,exportRecord,reviewSummary,xyz,formula,HARTREE_TO_KCAL} from './orca/analysis.js';
import {saveText} from './api';
import Viewer from './Viewer';

type Incoming={name:string;text:string;sha256:string}|null;

export default function Orca({incoming}: {incoming?:Incoming}){
 const [records,setRecords]=useState<any[]>([]),[selected,setSelected]=useState(0),[error,setError]=useState(''),[sourceLine,setSourceLine]=useState<number|null>(null),[source,setSource]=useState(false);
 const sourceHeadingRef=useRef<HTMLHeadingElement|null>(null),fileInputRef=useRef<HTMLInputElement|null>(null);
 const current=records[selected];
 const sourceStart=Math.max(0,(sourceLine??1)-251);
 const sourceEnd=Math.min(current?.lines.length??0,sourceStart+2000);
 const issues=comparisonIssues(records);
 const review=current?reviewSummary(current):{state:'hold',evidenceCount:0,missing:[],title:'',nextAction:''};

 useEffect(()=>{if(!incoming)return;try{const record:any=parseOrca(incoming.text,incoming.name);record.sha256=incoming.sha256;record.demo=false;record.localArtifact=true;setRecords(records=>[...records,record]);setSelected(records.length);setSource(false);setSourceLine(null);setError('');}catch(e){setError(e instanceof Error?e.message:String(e));}},[incoming]);
 useEffect(()=>{if(!source||!current)return;const target=sourceLine?document.getElementById('orca-line-'+sourceLine):sourceHeadingRef.current;target?.focus({preventScroll:true});target?.scrollIntoView({block:'center',behavior:'smooth'});},[source,sourceLine,current?.filename]);

 async function load(files:FileList){
  setError('');const imported:any[]=[];const failures:string[]=[];
  for(const file of Array.from(files)){try{
   if(file.size>25*1024*1024)throw Error('exceeds 25 MB');
   const bytes=await file.arrayBuffer();
   const text=new TextDecoder('utf-8',{fatal:true,ignoreBOM:true}).decode(bytes);
   const record:any=parseOrca(text,file.name);
   record.sha256=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes))).map(b=>b.toString(16).padStart(2,'0')).join('');
   record.demo=false;imported.push(record);
  }catch(e){failures.push(file.name+': '+(e instanceof Error?e.message:String(e)));}}
  if(imported.length){setRecords(existing=>[...existing,...imported]);setSelected(records.length);setSource(false);setSourceLine(null);}
  if(failures.length)setError('Some files were not imported: '+failures.join(' · '));
 }
 function synthetic(){const record:any=parseOrca(demoText(),'water-synthetic-example.out');record.demo=true;record.sha256='Synthetic example';setRecords([...records,record]);setSelected(records.length);}
 function evidence(line:number|null){setSource(true);setSourceLine(line);}

 return <section className="orca-workspace">
  <div className="orca-toolbar"><button className="primary file-button" onClick={()=>fileInputRef.current?.click()}>Open ORCA output</button><input ref={fileInputRef} type="file" hidden multiple accept=".out,.log,.txt" onChange={e=>{if(e.target.files)load(e.target.files);e.currentTarget.value='';}}/><button onClick={synthetic}>Load synthetic example</button><span>Static reader · files remain in this session until exported</span></div>
  {error&&<div className="banner error" role="alert" data-testid="orca-import-error">{error}</div>}
  {current?<>
   <div className="orca-tabs">{records.map((r,i)=><button className={i===selected?'selected':''} key={i} onClick={()=>{setSelected(i);setSourceLine(null);}}>{r.demo?'Example · ':''}{r.filename}</button>)}</div>
   <div className="orca-grid">
    <div className="panel"><div className="panel-header"><h2>{formula(current.geometry?.atoms)||'Geometry unavailable'}</h2><span className="tag">{current.demo?'SYNTHETIC':current.localArtifact?'SAVED LOCAL RUN':'IMPORTED FILE'}</span></div><Viewer data={current.geometry?xyz(current.geometry):null} format="xyz"/><div className="panel-footer"><span>Extracted geometry · inferred bonds for display</span><button disabled={!current.geometry} onClick={()=>saveText(xyz(current.geometry),'extracted-geometry.xyz')}>Export XYZ</button></div></div>
    <div className="panel orca-properties"><div className="orca-facts-heading"><h2>Printed calculation facts</h2>{current.multiJob&&<span className="tag" data-testid="orca-multijob-label">LAST OBSERVED · MULTI-JOB</span>}</div>{current.multiJob&&<p className="orca-multijob-note">Scalar values are last observed and may belong to different stages; they are not a single validated result.</p>}<dl className="properties"><div><dt>ORCA version</dt><dd>{current.version?.value??'Unknown'}</dd></div><div><dt>Termination</dt><dd>{current.termination}</dd></div><div><dt>Optimization</dt><dd>{current.optimization}</dd></div><div><dt>SCF</dt><dd>{current.scf}</dd></div><div><dt>Charge / multiplicity</dt><dd>{current.charge?.value??'?'} / {current.multiplicity?.value??'?'}</dd></div><div><dt>Electronic energy</dt><dd><button className="evidence-link" disabled={!current.energy} onClick={()=>evidence(current.energy?.line)}>{current.energy?current.energy.value+' Eh':'Not printed'}{current.energy&&<small>Line {current.energy.line} ↗</small>}</button></dd></div><div><dt>Negative frequencies</dt><dd>{current.frequencies.length?current.frequencies.filter((f:any)=>f.value<0).length:'Not printed'}</dd></div></dl><p className="quiet-note">Normal termination alone does not establish optimization convergence or chemical validity.</p><div className="file-actions"><button onClick={()=>saveText(JSON.stringify(exportRecord(current),null,2),'orca-record.json','application/json')}>Export extracted facts</button><button aria-controls="orca-source-panel" aria-expanded={source} onClick={()=>setSource(!source)}>{source?'Hide source':'Inspect source'}</button></div><code className="source-hash wrap">SHA-256: {current.sha256}</code></div>
   </div>
   <div className={'panel orca-review '+review.state} data-testid="orca-review-summary"><div className="panel-header"><h2>Review before using this result</h2><span className="tag" data-testid="orca-review-state">{review.title}</span></div><div className="orca-review-body"><p><strong>{review.evidenceCount} of 7</strong> core facts were extracted from this file. Extracted evidence is not scientific validation.</p><dl className="orca-review-status"><div><dt>Termination</dt><dd>{current.termination}</dd></div><div><dt>Optimization</dt><dd>{current.optimization}</dd></div><div><dt>SCF</dt><dd>{current.scf}</dd></div></dl>{review.missing.length?<><h3>Missing or unresolved</h3><ul data-testid="orca-review-missing">{review.missing.map((item:string)=><li key={item}>{item}</li>)}</ul></>:<p className="orca-review-clear" data-testid="orca-review-clear">No required review facts are absent. Inspect the source before drawing a conclusion.</p>}<h3>Next action</h3><p data-testid="orca-review-next-action">{review.nextAction}</p><button className="secondary" aria-controls="orca-source-panel" aria-expanded={source} onClick={()=>{setSourceLine(null);setSource(true);}}>Inspect original source</button></div></div>
   {current.checks.length>0&&<div className="panel checks"><h2>Extraction checks</h2>{current.checks.map((c:any,i:number)=><button key={i} className={'check-row '+c.severity} onClick={()=>evidence(c.line)}><strong>{c.title}</strong><span>{c.detail}</span>{c.line&&<small>Line {c.line} ↗</small>}</button>)}</div>}
   {records.length>1&&<div className="panel comparison"><h2>Energy comparison</h2>{issues.length?<><p className="warning-text">Comparison is on hold.</p><ul>{issues.map((issue:string)=><li key={issue}>{issue}</li>)}</ul></>:<table><thead><tr><th>Calculation</th><th>Electronic energy / Eh</th><th>Relative / kcal mol⁻¹</th></tr></thead><tbody>{records.map((r,i)=><tr key={i}><td>{r.filename}</td><td>{r.energy.value}</td><td>{((r.energy.value-Math.min(...records.map(v=>v.energy.value)))*HARTREE_TO_KCAL).toFixed(4)}</td></tr>)}</tbody></table>}<button onClick={()=>saveText(exportCSV(records),'orca-results.csv','text/csv')}>Export all extracted facts as CSV</button></div>}
   {source&&<div id="orca-source-panel" className="panel source-panel" aria-label="Original ORCA source"><div className="panel-header"><h2 tabIndex={-1} ref={sourceHeadingRef}>{current.filename} · source</h2><span>Original text · lines {sourceStart+1}–{sourceEnd} of {current.lines.length.toLocaleString()}</span></div><pre>{current.lines.slice(sourceStart,sourceEnd).map((line:string,offset:number)=>{const i=sourceStart+offset;return <div id={'orca-line-'+(i+1)} key={i} tabIndex={sourceLine===i+1?-1:undefined} className={sourceLine===i+1?'highlight':''}><span>{i+1}</span>{line||' '}</div>})}</pre></div>}
  </>:<div className="panel empty-state orca-empty"><span className="large-orbit">◎</span><h3>Start with an ORCA output file.</h3><p>Choose Open ORCA output and select an actual saved .out, .log, or .txt output. The file is read locally in this session; no ORCA engine or Qwen is needed.</p><p>Load synthetic example only to explore this reader; it is not your calculation.</p><small>This reader surfaces printed electronic energy. It does not replace thermochemistry or infer missing results.</small></div>}
 </section>;
}
