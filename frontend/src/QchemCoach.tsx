import React,{useEffect,useRef,useState} from 'react';
import {request} from './api';

type Props={project:string;step:'choose'|'inspect'|'settings'|'export';molecule:string;atomCount:number;charge:number;multiplicity:number;enabled:boolean;onHelp:(value:any)=>void};
const examples={choose:['Which molecule should I start with?'],inspect:['What do these coordinates mean?','How do I count the hydrogens?'],settings:['Why is the charge zero?','What is multiplicity?','What is a single-point energy?','What does the basis mean?'],export:['What do I do with this file?','Did Q-Chem run?']};
export default function QchemCoach({project,step,molecule,atomCount,charge,multiplicity,enabled,onHelp}:Props){
 const [prompt,setPrompt]=useState(''),[busy,setBusy]=useState(false),[reply,setReply]=useState<any>(null),[error,setError]=useState('');
 const generation=useRef(0),mounted=useRef(true);
 useEffect(()=>{mounted.current=true;return()=>{mounted.current=false;generation.current++;}},[]);
 useEffect(()=>{generation.current++;setReply(null);setError('');setPrompt('');},[project,step,molecule,charge,multiplicity,enabled]);
 async function ask(question=prompt){
  if(!question.trim()||busy||!enabled)return;
  const current=++generation.current;setPrompt(question);setBusy(true);setError('');setReply(null);
  try{const value=await request('/api/qchem/coach',{project,prompt:question.trim(),step,molecule,charge,multiplicity,atom_count:atomCount});if(mounted.current&&generation.current===current){setReply(value);onHelp({step,molecule,charge,multiplicity,atom_count:atomCount,question:question.trim(),...value});}}
  catch(e){if(mounted.current&&generation.current===current)setError('The assistant is unavailable right now. You can continue using the lesson notes and controls.');}
  finally{if(mounted.current)setBusy(false);}
 }
 return <aside className="qchem-coach" aria-labelledby="qchem-coach-title" aria-busy={busy}>
  <h3 id="qchem-coach-title">Need a hint?</h3>
  <p>Qwen is optional. The lesson works without it, and its suggestions never change your molecule, settings, or result.</p>
  {!enabled&&<p className="qchem-coach-unavailable" role="status">Qwen help is unavailable while this lesson step is still being prepared. You can continue with the cards and notes.</p>}<div className="coach-examples" aria-label="Suggested questions">{examples[step].map(text=><button className="text-button" type="button" key={text} disabled={busy||!enabled} onClick={()=>ask(text)}>{text}</button>)}</div>
  <form onSubmit={e=>{e.preventDefault();ask();}}><label htmlFor="qchem-question">Your question</label><textarea id="qchem-question" rows={3} maxLength={1000} value={prompt} onChange={e=>{setPrompt(e.target.value);setReply(null);setError('');}} placeholder="For example: why do I need all the hydrogens?" disabled={busy||!enabled}/><button type="submit" className="secondary" disabled={busy||!enabled||!prompt.trim()}>{busy?'Qwen is reading your question…':'Ask Qwen'}</button></form>
  <p className="qchem-help-status" role="status">{busy?'Finding a lesson hint. You can keep working while this finishes.':''}</p>
  {error&&<p role="alert" className="qchem-error">{error}</p>}
  {reply&&<section className="qchem-coach-answer" role="status"><span className="eyebrow">{reply.provenance?.guard?'CHECKED LESSON GUIDANCE':'QWEN-ASSISTED GUIDANCE'}</span><h4>{reply.title}</h4><p>{reply.message}</p><p><strong>Next:</strong> {reply.next_action}</p><details><summary>About this suggestion</summary><p>{reply.provenance?.guard?'Chem313 recognized a request outside this lesson; the model did not run.':'Local Qwen selected a help topic using checked lesson notes for your current molecule and settings.'}</p><p>It is a learning suggestion, not an independent scientific conclusion. Review the input and result yourself.</p><p>It did not change your molecule, settings, or run a calculation.</p>{!reply.provenance?.guard&&<code>{reply.provenance?.variant}</code>}{!reply.provenance?.guard&&<p>Model time: {reply.provenance?.seconds??'unreported'} seconds.</p>}</details></section>}
 </aside>;
}
