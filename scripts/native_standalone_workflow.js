// Opt-in package QA, run by the real AppKit/WKWebView against production controls.
const wait=async(fn,label)=>{const end=Date.now()+90000;while(Date.now()<end){const v=await fn();if(v)return v;await new Promise(r=>setTimeout(r,100));}throw Error('Timed out: '+label)};
const visible=e=>!!e?.getClientRects().length;
const button=name=>[...document.querySelectorAll('button')].find(e=>visible(e)&&e.textContent.trim()===name);
const click=async name=>{const b=await wait(()=>{const b=button(name);return b&&!b.disabled?b:null;},'enabled '+name);b.click();};
const set=(e,value)=>{Object.getOwnPropertyDescriptor(e instanceof HTMLTextAreaElement?HTMLTextAreaElement.prototype:HTMLInputElement.prototype,'value').set.call(e,value);e.dispatchEvent(new Event('input',{bubbles:true}));};
const checks=[];
try {
 const token=(await(await fetch('/api/session')).json()).session_token;
 const api=async path=>{const r=await fetch(path,{headers:{'X-HypothesisLab-Session':token}});if(!r.ok)throw Error(path+': '+r.status);return r.json()};
 const info=await api('/api/workbench'),registry=await api('/api/engines/registry'),ops=await api('/api/science/operations');
 if(JSON.stringify(ops.operations.map(x=>x.operation).sort())!==JSON.stringify(['numpy.summary','scipy.line']))throw Error('Unexpected worker allowlist');
 if(registry.engines.length!==7||registry.engines.some(x=>!x.runtime.bundled))throw Error('Incorrect bundled inventory');
 const model=await api('/api/assistant/status');if(model.status==='READY'&&model.variant!=='base-4bit-no-adapter')throw Error('Unexpected model deployment');
 checks.push('Self-contained core registry and exactly two bundled worker operations');
 if(model.status==='READY'){
  await click('Show Qwen');
  set(await wait(()=>document.querySelector('.assistant-prompt textarea:not(:disabled)'),'Qwen ready'),'Build water O, charge 0, multiplicity 1, HF def2-SVP single point calculation.');
  await click('Draft with Qwen');
  const proposal=await wait(()=>document.querySelector('.assistant-proposal'),'real frozen Qwen draft');
  if(!proposal.textContent.includes('H2O')||!proposal.textContent.includes('HF'))throw Error('Incorrect water draft');
  if(await window.__openchemEditor.getSmiles()==='O')throw Error('Draft automatically changed structure');
  await click('Apply proposal to current structure');
  await wait(()=>!document.querySelector('.assistant-proposal'),'proposal consumed');
  if(await window.__openchemEditor.getSmiles()!=='O')throw Error('Reviewed draft did not change the editor');
  checks.push('Bundled 4-bit base Qwen drafted water offline, independent graph checks passed, explicit Apply changed the editor');
 }

 const before=await window.__openchemEditor.getMolfile('v3000');await click('Fit structure');if(await window.__openchemEditor.getMolfile('v3000')!==before)throw Error('Fit mutated structure');
 await click('Save structure');await click('Save to project');await wait(()=>!document.querySelector('[role=dialog]'),'saved structure');
 await click('Generate 3D');await wait(()=>document.querySelector('.geometry-status')?.textContent.includes('Geometry: current'),'RDKit geometry');
 if(!button('Prepare PySCF RHF →')?.disabled||!button('Prepare GFN2-xTB →')?.disabled)throw Error('Missing quantum engines enabled');
 await click('3D view');await wait(()=>document.querySelector('canvas'),'WebGL canvas');
 await click('Prepare ORCA input →');await click('Check input →');
 const preview=await wait(()=>document.querySelector('.prep-preview pre'),'checked ORCA input');const exactInput=preview.textContent;
 await click('Save checked ORCA input');await wait(()=>document.querySelector('.orca-run'),'saved ORCA runner');
 if(!button('Run local ORCA')?.disabled)throw Error('Missing licensed ORCA not disabled');
 checks.push('Ketcher editing, byte-preserving Fit, reviewed structure save, RDKit conformer and WebGL view','Exact geometry handed to reviewed/saved ORCA input; unbundled quantum engines disabled');
 await click('Research scripts');await click('Review all steps');await click('Run reviewed recipe');
 await wait(()=>document.querySelectorAll('.recipe-results tbody tr')[1]?.children[2]?.textContent==='SUCCEEDED','two frozen subprocess jobs');
 const results=[...document.querySelectorAll('.recipe-results .science-result')].map(e=>JSON.parse(e.textContent));
 if(results[0].output.slope!==2||results[0].output.intercept!==1||results[1].output.mean!==3)throw Error('Recipe numerical references failed: '+JSON.stringify(results));
 await wait(()=>!button('Run reviewed recipe'),'consumed recipe review');
 checks.push('Reviewed SciPy calibration and NumPy summary execute in bundled worker subprocesses with reference values');
 await click('Measurements');
 set(document.querySelector('.csv-editor'),'time,signal\r\n0,1\r\n1,3\r\n2,5\r\n');
 await wait(()=>button('Review linear fit')&&!button('Review linear fit').disabled,'CSV input state');
 await click('Review linear fit');await click('Run & save fit');
 await wait(()=>document.querySelector('.fit-plot')?.complete&&document.querySelector('.fit-plot')?.naturalWidth>0,'Matplotlib SVG');
 if(document.querySelector('.fit-numbers dd')?.textContent!=='2')throw Error('CSV slope mismatch');
 checks.push('CSV review/save, SciPy slope 2 and Matplotlib SVG rendered in WKWebView');
 await click('ORCA results');await click('Load synthetic example');await wait(()=>document.querySelector('.orca-properties'),'results reader');
 if(!document.querySelector('.orca-properties').textContent.includes('normal'))throw Error('Synthetic result not parsed');
 await click('Inspect source');await wait(()=>document.querySelector('.source-panel'),'printed source evidence');
 checks.push('ORCA synthetic reader and printed source evidence (no ORCA execution claimed)');
 const project=document.querySelector('select[aria-label="Current project"]').value;
 const events=(await api(`/api/projects/${project}/events`)).events;
 const saved=events.filter(e=>e.action==='orca.prepare_input').at(-1);if(saved?.artifacts.length!==3)throw Error('Missing ORCA artifacts');
 for(const artifact of saved.artifacts){const [p,g,n]=artifact.relative_path.split('/');const bytes=await(await fetch(`/api/projects/${p}/artifact/${g}/${n}`,{headers:{'X-HypothesisLab-Session':token}})).arrayBuffer();const hash=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes))).map(b=>b.toString(16).padStart(2,'0')).join('');if(hash!==artifact.sha256)throw Error('Artifact checksum mismatch');if(n.endsWith('.inp')&&new TextDecoder().decode(bytes)!==exactInput)throw Error('Saved input differs from preview');}
 const integrity=await api(`/api/projects/${project}/verify`);if(integrity.status!=='PASS')throw Error('Integrity failure');
 checks.push('Saved input byte equivalence and project artifact integrity');
 await click('Structures');await click('2D editor');
 await new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)));await new Promise(resolve=>setTimeout(resolve,500));
 return JSON.stringify({status:'PASS',host:'Standalone native AppKit/WKWebView',version:info.version,checks,recipeResults:results,integrity,model_status:model.status,engines:registry.engines.map(x=>({name:x.name,version:x.runtime.version}))});
} catch(error) {return JSON.stringify({status:'FAIL',error:String(error),stack:error.stack,checks,body:document.body.innerText.slice(-9000)});}
