import React,{useEffect,useState} from 'react';
import {request} from './api';

type OrcaStatus={status?:string;detail?:string;path?:string};
type Props={
 status:OrcaStatus|null;
 onRefresh:()=>Promise<unknown>|unknown;
 onError:(message:string)=>void;
 locked:boolean;
 onConfigured?:()=>Promise<unknown>|unknown;
};

function setupReason(status:OrcaStatus|null){
 if(!status)return 'Checking whether ORCA is connected on this Mac.';
 if(status.status==='READY')return 'ORCA is connected. Starting a calculation remains an explicit review step.';
 if(status.status==='UNVERIFIED')return 'The selected executable is connected, but its version response was not verified.';
 if(status.status==='UNAVAILABLE')return status.detail??'The saved ORCA path is unavailable. Select the installed executable again.';
 return 'ORCA is not connected yet. Find an installed copy, or register for the official download.';
}

export default function OrcaConnection({status,onRefresh,onError,locked,onConfigured}:Props){
 const [path,setPath]=useState('');
 const [candidates,setCandidates]=useState<string[]>([]);
 const [finding,setFinding]=useState(false);
 const [connecting,setConnecting]=useState(false);
 const desktop=(window as any).webkit?.messageHandlers?.desktop;
 const disabled=locked||finding||connecting;
 useEffect(()=>{
  const selected=(event:Event)=>{const value=(event as CustomEvent<string>).detail;if(typeof value==='string'&&value)setPath(value)};
  window.addEventListener('openchem:orca-selected',selected);
  return()=>window.removeEventListener('openchem:orca-selected',selected);
 },[]);
 async function findInstallation(){
  setFinding(true);onError('');
  try{const reply=await request('/api/orca/discover');setCandidates(Array.isArray(reply.candidates)?reply.candidates:[]);}
  catch(error){onError(error instanceof Error?error.message:String(error));}
  finally{setFinding(false);}
 }
 async function connect(){
  if(!path.trim())return;
  setConnecting(true);onError('');
  try{
   await request('/api/orca/configure',{executable:path.trim()});
   setPath('');
   await (onConfigured??onRefresh)();
  }catch(error){onError(error instanceof Error?error.message:String(error));}
  finally{setConnecting(false);}
 }
 const needsSetup=status?.status==='NOT_CONFIGURED'||status?.status==='UNAVAILABLE'||!status;
 return <section className="panel orca-connection" aria-labelledby="orca-connection-title" aria-busy={disabled}>
  <div className="panel-header"><div><span className="eyebrow">LOCAL ORCA</span><h3 id="orca-connection-title">ORCA connection</h3></div><button className="text-button" disabled={disabled} onClick={()=>Promise.resolve(onRefresh()).catch(error=>onError(error instanceof Error?error.message:String(error)))}>Refresh status</button></div>
  <p role="status">{setupReason(status)}</p>
  {status?.path&&<code className="wrap">{status.path}</code>}
  {needsSetup&&<div className="orca-config">
   <label>ORCA executable path<input value={path} disabled={disabled} onChange={event=>setPath(event.target.value)} placeholder="/absolute/path/to/orca" spellCheck={false}/></label>
   <div className="file-actions"><button className="secondary" disabled={disabled} onClick={findInstallation}>{finding?'Finding installations…':'Find installation'}</button>{desktop&&<button className="secondary" disabled={disabled} onClick={()=>desktop.postMessage({action:'choose-orca'})}>Choose ORCA executable…</button>}<button className="secondary" disabled={disabled||!path.trim()} onClick={connect}>{connecting?'Connecting ORCA…':'Connect ORCA'}</button></div>
   {candidates.length>0&&<label>Found executable<select aria-label="Found ORCA executable" value="" disabled={disabled} onChange={event=>setPath(event.target.value)}><option value="">Select an installation</option>{candidates.map(candidate=><option value={candidate} key={candidate}>{candidate}</option>)}</select></label>}
   {candidates.length===0&&!finding&&<p className="quiet-note">Search checks only standard installation paths and PATH. It does not run ORCA or change the saved setting.</p>}
   <p className="quiet-note">ORCA is separately licensed and is not bundled. <a href="https://www.faccts.de/docs/orca/6.1/tutorials/first_steps/install.html" target="_blank" rel="noreferrer">Official registration and installation guide</a>. Connecting checks your executable; it starts no calculation.</p>
  </div>}
 </section>;
}
