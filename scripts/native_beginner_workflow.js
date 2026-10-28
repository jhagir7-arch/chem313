// Opt-in packaged AppKit/WKWebView QA with isolated project storage.
const wait=async(fn,label)=>{const end=Date.now()+90000;while(Date.now()<end){const value=await fn();if(value)return value;await new Promise(r=>setTimeout(r,80));}throw Error('Timed out: '+label)};
const visible=e=>!!e?.getClientRects().length;
const button=name=>[...document.querySelectorAll('button')].find(x=>visible(x)&&x.textContent.trim()===name);
const click=async name=>{const b=await wait(()=>{const b=button(name);return b&&!b.disabled?b:null},name);b.click();await new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)));};
const checks=[];
try {
 if(!document.querySelector('.beginner-workflow'))throw Error('No beginner worksheet');
 const chooser=document.getElementById('starter-molecule');
 Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype,'value').set.call(chooser,'Butane');chooser.dispatchEvent(new Event('change',{bubbles:true}));
 await new Promise(r=>requestAnimationFrame(r));
 window.confirm=()=>true; // Fresh test project: accept replacement of the synthetic example.
 await click('Load example');await wait(()=>document.querySelector('.formula')?.textContent==='C4H10','Butane');
 await click('Compare 5 starting shapes');await wait(()=>document.querySelectorAll('.shape-results tbody tr').length===5,'five real RDKit samples');
 const energies=[...document.querySelectorAll('.shape-results tbody td:nth-child(2)')].map(x=>Number(x.textContent));
 if(energies[0]!==0||energies.some((x,i)=>i&&x<energies[i-1]))throw Error('Invalid relative energy order');
 await click('Inspect sample 5');await wait(()=>document.querySelectorAll('.shape-results tbody tr')[4]?.querySelector('button')?.getAttribute('aria-pressed')==='true','selected sample 5');
 checks.push('Named starter and five real compiled RDKit samples, relative ranking and explicit selection in WKWebView');
 await click('Prepare calculation input');await click('Check input →');
 const exact=await wait(()=>document.querySelector('.prep-preview pre')?.textContent,'ORCA review');
 await click('Save checked ORCA input');await wait(()=>document.querySelector('.prep-downloads'),'saved ORCA');
 const token=(await(await fetch('/api/session')).json()).session_token;
 const api=async path=>{const r=await fetch(path,{headers:{'X-HypothesisLab-Session':token}});if(!r.ok)throw Error('API '+r.status);return r.json()};
 const project=document.getElementById('current-project').value;
 const event=(await api('/api/projects/'+project+'/events')).events.filter(x=>x.action==='orca.prepare_input').at(-1);
 for(const a of event.artifacts){if(!a.relative_path.endsWith('.inp'))continue;const [p,g,n]=a.relative_path.split('/');const saved=await(await fetch('/api/projects/'+p+'/artifact/'+g+'/'+n,{headers:{'X-HypothesisLab-Session':token}})).text();if(saved!==exact)throw Error('Saved input differs');}
 if((await api('/api/projects/'+project+'/verify')).status!=='PASS')throw Error('Project integrity failed');
 checks.push('Selected geometry checked and saved as exact ORCA input; stored-file integrity passes');
 await click('Change molecule or geometry');await click('2D editor');
 await window.__openchemEditor.setMolecule('O');await wait(()=>document.querySelector('.formula')?.textContent==='H2O','water edit');
 if(!button('Export selected geometry')?.disabled||!button('Export comparison report')?.disabled)throw Error('Stale geometry enabled');
 checks.push('Drawing edit invalidates guided geometry and comparison exports');
 await click('Compare 5 starting shapes');await wait(()=>document.querySelector('.shape-results h3')?.textContent.includes('H2O'),'fresh water sampling');
 return JSON.stringify({status:'PASS',host:'compiled AppKit/WKWebView',checks,energies});
} catch(error){return JSON.stringify({status:'FAIL',error:String(error),stack:error.stack,checks,url:location.href,html:document.documentElement.outerHTML.slice(0,1000),body:document.body.innerText.slice(-6000)});}
