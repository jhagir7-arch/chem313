import React,{useEffect,useMemo,useState} from 'react';
import {request,saveText} from './api';
import {qchemAtoms,qchemInput,validateQchemState} from './qchemInput.mjs';
import {qchemCoordinatePayload} from './qchemStudy.mjs';
import IdentityCheck from './IdentityCheck';
import './qchem-preparation.css';

type Props={choiceName:string;geometry:any};

export default function QchemPreparation({choiceName,geometry}:Props){
 const [charge,setCharge]=useState('0');
 const [multiplicity,setMultiplicity]=useState('1');
 const [serverPreparation,setServerPreparation]=useState<any>(null),[identityError,setIdentityError]=useState('');
 const prepared=useMemo(()=>{
  try{
   const atoms=qchemAtoms(geometry);
   const state=validateQchemState(atoms,charge,multiplicity);
   return {input:qchemInput(geometry,{charge:state.charge,multiplicity:state.multiplicity}),electrons:state.electrons};
  }catch(error){return {error:error instanceof Error?error.message:String(error)};}
 },[geometry,charge,multiplicity]);
 const issue='error' in prepared?prepared.error:null;
 const input='input' in prepared?prepared.input:null;
 const electrons='electrons' in prepared?prepared.electrons:null;
 const filename=`chem313-${choiceName.toLowerCase().replaceAll(/[^a-z0-9]+/g,'-')}-hf-sp.in`;
 const moleculeId=choiceName.toLowerCase();
 useEffect(()=>{let live=true;setServerPreparation(null);setIdentityError('');if(issue||charge!=='0'||multiplicity!=='1')return;request('/api/qchem/prepare',qchemCoordinatePayload(geometry,moleculeId)).then(value=>{if(live)setServerPreparation(value);}).catch(error=>{if(live)setIdentityError(error instanceof Error?error.message:String(error));});return()=>{live=false;};},[geometry,moleculeId,charge,multiplicity,issue]);
 const checked=serverPreparation?.identity_check?.status==='match';
 return <section className="qchem-preparation" aria-labelledby="qchem-preparation-title">
  <div className="panel-header"><div><span className="eyebrow">Q-CHEM INPUT PREPARATION</span><h3 id="qchem-preparation-title">Review and download a single-point input</h3></div><span className="tag">PREPARATION ONLY</span></div>
  <p>This uses the same local RDKit starting geometry shown above. It prepares a text file; This preparation panel does not run Q-Chem or claim that a licensed Q-Chem engine is available.</p>
  <div className="qchem-settings">
   <label>Q-Chem charge<input aria-label="Q-Chem charge" type="number" step="1" required value={charge} onChange={event=>setCharge(event.target.value)}/></label>
   <label>Q-Chem multiplicity<input aria-label="Q-Chem multiplicity" type="number" min="1" step="1" required value={multiplicity} onChange={event=>setMultiplicity(event.target.value)}/></label>
   <dl><div><dt>Calculation</dt><dd>HF single-point energy</dd></div><div><dt>Basis</dt><dd>def2-SVP</dd></div>{electrons!==null&&<div><dt>Electrons after charge</dt><dd>{electrons}</dd></div>}</dl>
  </div>
  <p className="quiet-note">Charge 0 means a neutral molecule. Multiplicity 1 is a paired-electron singlet; do not guess a different charge or multiplicity.</p>
  {issue?<p className="warning-text" role="alert">Input not ready: {issue}</p>:<><h4>Exact Q-Chem input</h4><pre aria-label="Exact Q-Chem input">{serverPreparation?.input_text??input}</pre>{serverPreparation&&<IdentityCheck identity={serverPreparation.identity_check} scope={serverPreparation.scope}/>} {identityError&&<p className="warning-text" role="alert">Coordinate identity check unavailable: {identityError}</p>}<button type="button" disabled={!checked} onClick={()=>saveText(serverPreparation.input_text,filename,'text/plain')}>Download checked Q-Chem input</button>{!checked&&<p className="quiet-note">Download is available after the local coordinate-to-InChI check passes. This beginner route supports the neutral singlet (0 / 1).</p>}</>}
  <p className="quiet-note">A single point computes energy with this starting geometry held fixed. It does not optimize the geometry or predict a reaction. HF/def2-SVP is a beginner starter setting, not a general research-method recommendation.</p>
  <p className="quiet-note">The file uses <code>$molecule</code> Cartesian coordinates in ångström and a <code>$rem</code> block with <code>JOBTYPE sp</code>, <code>METHOD hf</code>, and <code>BASIS def2-SVP</code>. Review it in Q-Chem before any separate licensed execution.</p>
 </section>;
}
