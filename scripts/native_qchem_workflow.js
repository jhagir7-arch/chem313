// Runs inside the actual compiled WKWebView through the explicit package QA hook.
const checks=[];const tick=()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)));
const wait=async(fn,label,ms=30000)=>{const end=Date.now()+ms;while(Date.now()<end){const value=await fn();if(value)return value;await new Promise(r=>setTimeout(r,100));}throw Error('Timed out: '+label);};
const assert=(ok,label)=>{if(!ok)throw Error(label);};
const root=document.querySelector('.qchem-workflow');
const btn=name=>[...root.querySelectorAll('button')].find(e=>e.getClientRects().length&&e.textContent.trim()===name);
const click=async name=>{const button=await wait(()=>{const e=btn(name);return e&&!e.disabled?e:null;},name);button.click();await tick();};
const input=(selector,value)=>{const e=root.querySelector(selector);const proto=e.tagName==='SELECT'?HTMLSelectElement.prototype:e.tagName==='TEXTAREA'?HTMLTextAreaElement.prototype:HTMLInputElement.prototype;Object.getOwnPropertyDescriptor(proto,'value').set.call(e,value);e.dispatchEvent(new Event(e.tagName==='SELECT'?'change':'input',{bubbles:true}));};
const coach=async(question,topic)=>{await click(question);const answer=await wait(()=>root.querySelector('.qchem-coach-answer'),'Qwen '+question,100000);assert(answer.querySelector('.eyebrow').textContent==='QWEN-ASSISTED GUIDANCE','Qwen did not actually classify '+question);if(topic)assert(answer.querySelector('h4').textContent===topic,'Wrong Qwen topic: '+answer.querySelector('h4').textContent);checks.push('Real packaged Qwen help: '+question+' -> '+answer.querySelector('h4').textContent);};
try{
 assert(root&&root.getClientRects().length,'Q-Chem lesson is not the initial workspace');
 const token=(await(await fetch('/api/session')).json()).session_token;
 const api=async path=>{const r=await fetch(path,{headers:{'X-HypothesisLab-Session':token}});if(!r.ok)throw Error('API '+r.status);return r.json();};
 const project=document.querySelector('#current-project').value;
 const before=(await api('/api/projects/'+project+'/events')).events;
 const records=[];
 for(const [name,count,formula] of [['water',3,'H2O'],['methane',5,'CH4'],['ethanol',9,'C2H6O']]){
  root.querySelector('input[name="qchem-molecule"][value="'+name+'"]').click();await tick();
  if(name==='water')await coach('Which molecule should I start with?','Selected molecule');
  await click('Build starting structure');
  await wait(()=>root.querySelector('#qchem-atom-prediction'),'generated structure '+name);
  assert(root.querySelectorAll('.qchem-representations figure').length===2,'2D/3D representations absent');
  await wait(()=>root.querySelector('.qchem-representations canvas'),'real 3D '+name);
  input('#qchem-atom-prediction',String(count-1));await tick();await click('Check atom count');
  assert(btn('Continue to settings').disabled,'Wrong atom count passed');
  input('#qchem-atom-prediction',String(count));await tick();await click('Check atom count');
  input('#qchem-coordinate-check','products');await tick();assert(btn('Continue to settings').disabled,'Wrong coordinate interpretation passed');
  input('#qchem-coordinate-check','positions');await tick();
  const details=root.querySelector('.qchem-coordinates');details.open=true;await tick();assert(root.querySelectorAll('tbody tr').length===count,'Wrong coordinate count');
  if(name!=='methane'){root.querySelector('a[href="#qchem-oxygen"]').click();await tick();assert(document.activeElement?.id==='qchem-oxygen','Oxygen row did not receive focus');}
  if(name==='water')await coach('What do these coordinates mean?','Starting coordinates');
  await click('Continue to settings');
  assert(document.activeElement?.id==='qchem-step-title','Step heading did not receive keyboard focus');
  root.querySelector('.qchem-advanced').open=true;await tick();
  input('[aria-label="Q-Chem lesson charge"]','');await tick();assert(root.querySelector('[role="alert"]'),'Blank charge accepted');
  input('[aria-label="Q-Chem lesson charge"]','0');input('[aria-label="Q-Chem lesson multiplicity"]','2');await tick();assert(root.querySelector('[role="alert"]')?.textContent.includes('parity'),'Bad spin not rejected');
  input('[aria-label="Q-Chem lesson charge"]','1');await tick();assert(root.querySelector('[role="alert"]')?.textContent.includes('neutral singlet'),'Untested charged state accepted');
  await click('Reset neutral singlet');
  input('#qchem-single-point-check','relax');await tick();assert(btn('Review Q-Chem input').disabled,'Wrong single-point interpretation passed');
  input('#qchem-single-point-check','fixed');input('#qchem-own-words','The atoms stay in place. This file requests energy; no energy was calculated here.');await tick();
  if(name==='water')await coach('What is a single-point energy?','Single-point preparation');
  await click('Review Q-Chem input');
  const text=root.querySelector('pre[aria-label="Reviewed Q-Chem input"]').textContent;
  assert(text.includes('$molecule\n0 1\n')&&text.includes('$rem\nJOBTYPE sp\nMETHOD hf\nBASIS def2-SVP\n$end'),'Wrong exact Q-Chem settings');
  assert(text.split('\n').filter(row=>/^[A-Z][a-z]?\s+[-+\d]/.test(row)).length===count,'Wrong exported atom count');
  assert(btn('Download Q-Chem input').disabled,'Download before reviewed-state acknowledgement');
  if(name==='water')await coach('What do I do with this file?','Export for review');
  root.querySelector('.qchem-ack input').click();await tick();
  await click('Save preparation to project');
  await wait(()=>root.querySelector('.qchem-saved'),'saved project snapshot '+name);
  const events=(await api('/api/projects/'+project+'/events')).events;
  const event=events.filter(e=>e.action==='project.save_note').at(-1);
  const value=JSON.parse(event.result.text);assert(value.status==='PREPARED_NOT_RUN'&&value.exact_input===text,'Saved record differs from review');
  assert(value.molecule.formula===formula&&value.geometry.coordinates.length===count,'Saved molecule differs');
  const digest=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(text)))).map(v=>v.toString(16).padStart(2,'0')).join('');assert(value.input_sha256===digest,'Input hash mismatch');
  const a=event.artifacts[0];const [p,g,f]=a.relative_path.split('/');const response=await fetch('/api/projects/'+p+'/artifact/'+g+'/'+f,{headers:{'X-HypothesisLab-Session':token}});assert(response.ok,'Saved file unreadable');const bytes=await response.arrayBuffer();assert(JSON.parse(new TextDecoder().decode(bytes)).exact_input===text,'Stored file content mismatch');
  const artifactHash=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes))).map(v=>v.toString(16).padStart(2,'0')).join('');assert(artifactHash===a.sha256,'Artifact digest mismatch');
  records.push({molecule:name,input_sha256:digest,artifact:a,assistance:value.assistance.map(h=>({step:h.step,topic:h.topic,provenance:h.provenance}))});
  checks.push(name+': real RDKit 2D/3D, '+count+' atoms; incorrect count/interpretations and invalid charge/spin blocked; exact reviewed input and full study saved with verified hashes');
  if(name!=='ethanol')await click('Choose another molecule');
 }
 const after=(await api('/api/projects/'+project+'/events')).events;
 assert(after.filter(e=>e.action==='orca.run_started').length===before.filter(e=>e.action==='orca.run_started').length,'Unexpected calculation launch');
 assert((await api('/api/projects/'+project+'/verify')).status==='PASS','Project integrity check failed');
 checks.push('No quantum engine launch, no fabricated energies; project integrity PASS');
 return JSON.stringify({status:'PASS',scope:'Compiled beginner Q-Chem preparation with real local Qwen; licensed Q-Chem execution NOT_RUN',checks,records,project,url:location.href});
}catch(error){return JSON.stringify({status:'FAIL',error:String(error),stack:error.stack,checks,body:document.body.innerText.slice(-6500),url:location.href});}
