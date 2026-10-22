// Opt-in native AppKit/WKWebView QA for the visible first force-field calculation.
// It runs the bundled RDKit action through the real preview/execute API; it never mocks fetch.
const checks=[];
const tick=()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)));
const wait=async(fn,label,ms=90000)=>{const end=Date.now()+ms;while(Date.now()<end){const value=await fn();if(value)return value;await new Promise(resolve=>setTimeout(resolve,100));}throw Error('Timed out: '+label);};
const visible=element=>!!element?.getClientRects().length;
const button=(name,root=document)=>[...root.querySelectorAll('button')].find(element=>visible(element)&&(element.textContent.trim()===name||element.textContent.trim().startsWith(name)));
const click=async(name,root=document)=>{const element=await wait(()=>{const candidate=button(name,root);return candidate&&!candidate.disabled?candidate:null;},'button '+name);element.click();await tick();};
const setSelect=(element,value)=>{Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype,'value').set.call(element,value);element.dispatchEvent(new Event('change',{bubbles:true}));};
const sha256=async bytes=>Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes))).map(value=>value.toString(16).padStart(2,'0')).join('');
const command=async detail=>{window.dispatchEvent(new CustomEvent('openchem:command',{detail}));await tick();};
let restorePostMessage=null;
try{
 if(document.querySelector('.welcome-sheet'))await click('Run your first calculation');
 else await command('calculate');
 const root=await wait(()=>document.querySelector('.first-calculation'),'Calculate command opens first calculation');
 const projectInput=await wait(()=>document.querySelector('#current-project'),'current project');
 const token=(await(await fetch('/api/session')).json()).session_token;
 const api=async(path,payload)=>{const response=await fetch(path,{method:payload?'POST':'GET',headers:{'Content-Type':'application/json','X-HypothesisLab-Session':token},body:payload?JSON.stringify(payload):undefined});const data=await response.json();if(!response.ok)throw Error(path+': '+JSON.stringify(data));return data;};
 const artifactBytes=async artifact=>{const [project,group,name]=artifact.relative_path.split('/');const response=await fetch(`/api/projects/${encodeURIComponent(project)}/artifact/${group}/${name}`,{headers:{'X-HypothesisLab-Session':token}});if(!response.ok)throw Error('Unreadable artifact '+artifact.relative_path);return new Uint8Array(await response.arrayBuffer());};
 const molecule=root.querySelector('select[aria-label="First calculation molecule"]');
 if(!molecule||molecule.value!=='ethanol')throw Error('Ethanol is not the visible default');
 const run=async(expectedId,expectedFormula)=>{
  if(molecule.value!==expectedId)setSelect(molecule,expectedId);
  await click('Run shape calculation',root);
  const result=await wait(()=>root.querySelector('.first-result'),'saved '+expectedId+' result');
  if(!result.innerText.includes(expectedFormula)||!result.innerText.includes('MMFF94 energy · kcal/mol'))throw Error('Missing visible formula or units for '+expectedId);
  await wait(()=>{const canvas=result.querySelector('.viewer-wrap canvas');return visible(canvas)?canvas:null;},'visible 3D viewer for '+expectedId);
  if(!result.querySelector('.two-bars')||result.querySelectorAll('.two-bars strong').length!==2)throw Error('Before/after energy chart missing for '+expectedId);
  if(!result.innerText.includes('SAVED LOCAL RESULT · REAL CALCULATION')||!result.innerText.includes('Identity: MATCH')||!result.innerText.includes('Did it prove a reaction?'))throw Error('Required result provenance or feedback missing for '+expectedId);
  await click('No',result);if(!result.innerText.includes('Correct. It only relaxed the shape'))throw Error('Reaction feedback did not respond for '+expectedId);
  const project=projectInput.value;
  const event=(await api('/api/projects/'+encodeURIComponent(project)+'/events')).events.filter(item=>item.action==='molecule.relax_geometry').at(-1);
  if(!event||event.artifacts.length!==3)throw Error('Expected initial SDF, final SDF, and JSON report for '+expectedId);
  const reportArtifact=event.artifacts.find(item=>item.relative_path.endsWith('.json'));
  const report=JSON.parse(new TextDecoder().decode(await artifactBytes(reportArtifact)));
  if(report.force_field!=='MMFF94'||report.engine_provenance!=='real'||report.energy_unit!=='kcal/mol'||!Number.isFinite(report.initial_energy_kcal_mol)||!Number.isFinite(report.final_energy_kcal_mol))throw Error('Real force-field provenance/energies missing for '+expectedId);
  if(report.smiles!==({ethanol:'CCO',water:'O',methane:'C'})[expectedId])throw Error('Saved SMILES differs from selected molecule');
  for(const artifact of event.artifacts){const bytes=await artifactBytes(artifact);if(bytes.byteLength!==artifact.bytes||await sha256(bytes)!==artifact.sha256)throw Error('Artifact hash mismatch: '+artifact.relative_path);}
  return {project,event,report};
 };
 const ethanol=await run('ethanol','C2H6O');
 checks.push('Calculate command opens visible ethanol-first MMFF94 flow; real ethanol result has 3D viewer, units, convergence feedback, and three hash-verified project artifacts');

 const desktop=window.webkit?.messageHandlers?.desktop;
 if(!desktop?.postMessage)throw Error('Native desktop save bridge is unavailable');
 const saves=[];
 const originalPost=desktop.postMessage.bind(desktop);
 restorePostMessage=()=>{desktop.postMessage=originalPost;};
 desktop.postMessage=message=>{if(message?.action==='save'){saves.push(message);return;}return originalPost(message);};
 await click('Download record',root);
 await wait(()=>saves.length===1,'native record save payload');
 const saved=saves[0];
 if(saved.name!=='first-calculation-record.json'||typeof saved.base64!=='string')throw Error('Unexpected native record payload');
 const record=JSON.parse(new TextDecoder().decode(Uint8Array.from(atob(saved.base64),c=>c.charCodeAt(0))));
 const geometry=ethanol.event.artifacts.filter(item=>item.relative_path.endsWith('.sdf'));
 if(record.action!=='molecule.relax_geometry'||record.params.smiles!=='CCO'||record.model.force_field!=='MMFF94'||geometry.some(item=>!record.artifacts.some(savedArtifact=>savedArtifact.sha256===item.sha256)))throw Error('Downloaded record omits geometry artifact hashes');
 restorePostMessage();restorePostMessage=null;
 checks.push('Visible Download record uses the native save bridge and contains the selected parameters, MMFF94 values, and both geometry artifact hashes');

 setSelect(molecule,'water');await tick();
 if(root.querySelector('.first-result'))throw Error('Changing molecule left a stale ethanol result visible');
 const water=await run('water','H2O');
 setSelect(molecule,'methane');await tick();
 if(root.querySelector('.first-result'))throw Error('Changing molecule left a stale water result visible');
 const methane=await run('methane','CH4');
 checks.push('Water and methane run from their visible selector choices; each selection clears the previous result before its real local run');

 const oldProject=projectInput.value;
 window.prompt=()=> 'firstcalcqa2';
 await click('New project');await wait(()=>projectInput.value==='firstcalcqa2','new project selection');
 if(root.querySelector('.first-result'))throw Error('Switching projects left a stale result visible');
 if(oldProject==='firstcalcqa2')throw Error('Project switch did not occur');
 checks.push('Changing projects clears the prior calculation result');
 return JSON.stringify({status:'PASS',host:'Native AppKit / WKWebView',checks,ethanol:{report:ethanol.report,artifacts:ethanol.event.artifacts},water:{report:water.report,artifacts:water.event.artifacts},methane:{report:methane.report,artifacts:methane.event.artifacts},record_save:{name:saved.name,bytes:saved.base64.length}});
}catch(error){return JSON.stringify({status:'FAIL',error:String(error),stack:error.stack,checks,body:document.body.innerText.slice(-10000)});}
finally{if(restorePostMessage)restorePostMessage();}
