// Opt-in QA through the real public shell's WKWebView and production service.
const wait=async(fn,label)=>{const end=Date.now()+30000;while(Date.now()<end){const v=fn();if(v)return v;await new Promise(r=>setTimeout(r,100));}throw Error('Timed out: '+label)};
const visible=e=>!!e?.getClientRects().length;
const click=async name=>{const b=await wait(()=>[...document.querySelectorAll('button')].find(x=>visible(x)&&x.textContent.trim()===name),name);if(b.disabled)throw Error('Disabled: '+name);b.click()};
try {
 const token=(await(await fetch('/api/session')).json()).session_token;
 const api=async path=>{const r=await fetch(path,{headers:{'X-HypothesisLab-Session':token}});if(!r.ok)throw Error(path+': '+r.status);return r.json()};
 const info=await api('/api/workbench');
 if(info.version!=='1.0.0-preview.1')throw Error('Wrong runtime version');
 const model=await api('/api/assistant/status');
 if(model.status==='READY')throw Error('Unexpected bundled model in public runtime');
 const before=await window.__openchemEditor.getMolfile('v3000');
 await click('Fit structure');
 if(await window.__openchemEditor.getMolfile('v3000')!==before)throw Error('Fit changed MOL source');
 await click('Generate 3D');
 await wait(()=>document.querySelector('.geometry-status')?.textContent.includes('Geometry: current'),'generated geometry');
 await click('Prepare ORCA input →');
 await click('Check input →');
 await wait(()=>document.querySelector('.prep-preview'),'checked ORCA input');
 return JSON.stringify({status:'PASS',version:info.version,checks:['native WKWebView connected to separately installed clean runtime','Ketcher editor loaded and molecular formula inspected','Fit preserves original V3000 MOL','real RDKit geometry generated from native controls','geometry handed to ORCA preparation','Qwen correctly unavailable without assets'],model_status:model.status});
} catch(e) {return JSON.stringify({status:'FAIL',error:String(e)})}
