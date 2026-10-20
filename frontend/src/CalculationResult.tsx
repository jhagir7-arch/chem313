import React,{useState} from 'react';
import {convertElectronicEnergy,formatElectronicEnergy} from './resultUnits.mjs';
import './result-card.css';

export type ResultIdentity={observed_inchikey?:string;expected_inchikey?:string;status?:'MATCH'|'MISMATCH'|'UNAVAILABLE';};
export type EngineProvenance='simulated'|'real'|'unverified';
export type CalculationResultProps={
  job:any;moleculeSvg?:React.ReactNode;formula?:string;charge?:number;multiplicity?:number;identity?:ResultIdentity;
  engineName?:string;jobType?:string;engineProvenance?:EngineProvenance;
  onSaveRecord?:()=>void;onDownloadInput?:()=>void;onDownloadOutput?:()=>void;onDownloadRecord?:()=>void;
};
function status(job:any,succeeded:boolean){if(succeeded)return ['✓','Finished — energy recorded'];if(job?.state==='RUNNING')return ['◌','Working locally'];if(job?.state==='QUEUED')return ['◌','Queued locally'];if(job?.state==='CANCELLED')return ['!','Stopped before a usable energy was recorded'];return ['!','No usable energy recorded'];}
function provenanceLabel(provenance:EngineProvenance,engineName:string){if(provenance==='real')return ['Real engine run',`The recorded runtime identified ${engineName} as a real engine run.`];if(provenance==='simulated')return ['Simulated engine fixture',`This record is explicitly marked as a simulated ${engineName} fixture.`];return ['Engine provenance unverified',`This record does not establish whether the saved ${engineName} runtime was a production engine.`];}

export default function CalculationResult({job,moleculeSvg,formula,charge,multiplicity,identity,engineName='Calculation engine',jobType,engineProvenance='unverified',onSaveRecord,onDownloadInput,onDownloadOutput,onDownloadRecord}:CalculationResultProps){
 const [unit,setUnit]=useState<'Eh'|'kJ/mol'|'eV'>('Eh');
 const succeeded=job?.state==='SUCCEEDED'&&job.result?.converged===true&&job.result?.normal_termination===true&&Number.isFinite(job.result?.energy_hartree);
 const energy=convertElectronicEnergy(job?.result?.energy_hartree),[statusIcon,statusText]=status(job,succeeded),[provenanceTitle,provenanceText]=provenanceLabel(engineProvenance,engineName);
 const optimized=(jobType??job?.job_type)==='optimization';
 const display=unit==='Eh'?energy?.hartree:unit==='kJ/mol'?energy?.kilojoulesPerMol:energy?.electronVolts;
 const digits=unit==='Eh'?8:unit==='kJ/mol'?2:5;
 return <section className="calculation-result" aria-labelledby="calculation-result-title">
  <div className="result-card-head"><div className="result-context">{moleculeSvg&&<div className="result-molecule-art" aria-hidden="true">{moleculeSvg}</div>}<div><p className="result-kicker">Recorded calculation</p><h4 id="calculation-result-title">{job?.molecule??'Molecule'} result</h4>{(formula||charge!==undefined||multiplicity!==undefined)&&<p className="result-context-line">{formula&&<strong>{formula}</strong>}{charge!==undefined&&<> · charge {charge}</>}{multiplicity!==undefined&&<> · spin {multiplicity}</>}</p>}</div></div><span className="result-status"><span aria-hidden="true">{statusIcon}</span> {statusText}</span></div>
  <p className="result-engine-line"><strong>{provenanceTitle}</strong> · {provenanceText}</p>
  {succeeded&&energy?<><div className="result-energy-reading"><div><p>Absolute electronic energy at the {optimized?'final':'submitted'} geometry</p><output data-testid="qchem-energy">{formatElectronicEnergy(display,digits)} {unit}</output></div><label>Units<select aria-label="Energy units" value={unit} onChange={event=>setUnit(event.target.value as typeof unit)}><option value="Eh">Eh</option><option value="kJ/mol">kJ/mol</option><option value="eV">eV</option></select></label></div>
   <details className="result-conversions"><summary>Show all unit conversions</summary><dl><div><dt>Hartree</dt><dd>{formatElectronicEnergy(energy.hartree,8)} Eh</dd></div><div><dt>Energy per mole</dt><dd>{formatElectronicEnergy(energy.kilojoulesPerMol,2)} kJ/mol</dd></div><div><dt>Electron volts</dt><dd>{formatElectronicEnergy(energy.electronVolts,5)} eV</dd></div></dl></details>
   <details className="result-explanation"><summary>What this result shows — and what it does not</summary><p><strong>Shows:</strong> the selected method’s electronic energy at the {optimized?'final':'submitted'} geometry, after recorded SCF convergence and normal termination.</p><p><strong>Does not show:</strong> {optimized?'a verified minimum (frequencies are still needed), ': 'an optimized structure, '}reaction energy, rate, experimental enthalpy, or safety result. <strong>Why:</strong> those claims need additional structures, calculations, or measurements.</p></details>
   <aside className="result-reference"><strong>No directly comparable reference is selected.</strong><p>Absolute electronic energy is not experimental enthalpy. Compare only after matching the molecule, state, phase, method, and thermochemical quantity.</p><a href="https://cccbdb.nist.gov/" target="_blank" rel="noreferrer">Check the NIST CCCBDB comparison database</a></aside>
  </>:<p className="result-scope">Wait for normal termination and SCF convergence before interpreting an energy. Failed or interrupted jobs remain records, not successful calculations.</p>}
  {identity&&<p className={'result-identity result-identity-'+String(identity.status??'UNAVAILABLE').toLowerCase()}>Identity check: {identity.status==='MATCH'?'matches the expected structure':identity.status==='MISMATCH'?'does not match the expected structure':'not available for this saved result'}{identity.observed_inchikey&&<> · InChIKey {identity.observed_inchikey}</>}</p>}
  <div className="result-card-actions">{onSaveRecord&&<button className="primary" onClick={onSaveRecord}>Save calculation record</button>}{(onDownloadInput||onDownloadOutput||onDownloadRecord)&&<details className="result-downloads"><summary>Downloads</summary><div>{onDownloadInput&&<button className="secondary" onClick={onDownloadInput}>Executed input</button>}{onDownloadOutput&&<button className="secondary" onClick={onDownloadOutput}>Engine output</button>}{onDownloadRecord&&<button className="secondary" onClick={onDownloadRecord}>Result JSON</button>}</div></details>}</div>
  <details className="result-details"><summary>Run details</summary><dl><div><dt>Job ID</dt><dd><code>{job?.id??'Unavailable'}</code></dd></div><div><dt>State</dt><dd>{job?.state??'Unavailable'}</dd></div><div><dt>Calculation</dt><dd>{jobType??job?.job_type??'single point'} · {job?.method??'Method unavailable'} / {job?.basis??'basis unavailable'}</dd></div><div><dt>Input SHA-256</dt><dd><code>{job?.input_sha256??'Unavailable'}</code></dd></div><div><dt>Output SHA-256</dt><dd><code>{job?.output_sha256??'Unavailable'}</code></dd></div></dl></details>
 </section>;
}
