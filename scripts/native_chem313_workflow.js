// Runs only through the compiled AppKit/WKWebView QA hook. It uses real local RDKit
// and the visible student workflow. A labeled browser-only fixture checks result
// presentation; it never stores a simulated result or launches a quantum engine.
const checks=[];
const tick=()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)));
const wait=async(fn,label,ms=60000)=>{const until=Date.now()+ms;while(Date.now()<until){const value=await fn();if(value)return value;await new Promise(resolve=>setTimeout(resolve,100));}throw Error('Timed out: '+label);};
const visible=element=>!!element?.getClientRects().length;
const buttons=()=>[...document.querySelectorAll('button')].filter(visible);
const button=name=>buttons().find(element=>element.textContent.trim()===name)??buttons().find(element=>element.textContent.trim().startsWith(name));
const click=async name=>{const element=await wait(()=>{const candidate=button(name);return candidate&&!candidate.disabled?candidate:null;},name);element.click();await tick();};
const set=(selector,value)=>{const element=document.querySelector(selector);if(!element)throw Error('Missing '+selector);const proto=element.tagName==='SELECT'?HTMLSelectElement.prototype:HTMLInputElement.prototype;Object.getOwnPropertyDescriptor(proto,'value').set.call(element,value);element.dispatchEvent(new Event(element.tagName==='SELECT'?'change':'input',{bubbles:true}));};
const command=async detail=>{window.dispatchEvent(new CustomEvent('openchem:command',{detail}));await tick();};
let restoreFetch=null;
try{
 if(document.title!=='Chem313 · Molecular studies')throw Error('Wrong title');
 if(window.__CHEM313_NATIVE_SIDEBAR__!==true)throw Error('Compiled app did not expose the native-sidebar flag');
 if(document.querySelector('.task-sidebar'))throw Error('Web sidebar rendered despite native sidebar flag');
 if(!document.querySelector('.welcome-sheet'))await command('show-welcome');
 if(!document.querySelector('.welcome-sheet'))throw Error('Welcome choice sheet is not visible');
 if(!document.querySelector('.welcome-sheet').innerText.includes('What would you like to do?'))throw Error('First-launch sheet is incomplete');
 checks.push('Compiled app exposes native sidebar mode and opens with the first-launch choice sheet');

 set('select[aria-label="Appearance"]','dark');await tick();
 if(document.documentElement.dataset.appearance!=='dark'||getComputedStyle(document.body).backgroundColor==='rgb(255, 255, 255)')throw Error('Dark appearance did not apply');
 set('select[aria-label="Appearance"]','light');await tick();
 if(document.documentElement.dataset.appearance!=='light')throw Error('Light appearance did not restore');
 checks.push('Appearance control switches the compiled UI between dark and light modes');

 const token=(await(await fetch('/api/session')).json()).session_token;
 const api=async(path,payload)=>{const response=await fetch(path,{method:payload?'POST':'GET',headers:{'Content-Type':'application/json','X-HypothesisLab-Session':token},body:payload?JSON.stringify(payload):undefined});const data=await response.json();if(!response.ok)throw Error(path+': '+JSON.stringify(data));return data;};
 const execute=async(action,params)=>(await api('/api/execute',{action,params,project:'chem313-qa',approved:true})).result;
 const realStructures=[];
 for(const [id,smiles,count] of [['water','O',3],['methane','C',5],['ethanol','CCO',9]]){
  const geometry=await execute('molecule.generate_conformer',{smiles});
  if(!Number.isFinite(geometry.energy)||!geometry.converged)throw Error('No converged bundled force-field geometry for '+id);
  const atoms=geometry.atomic_numbers.map((atomicNumber,index)=>({element:({1:'H',6:'C',8:'O'})[atomicNumber],x:geometry.coordinates[index][0],y:geometry.coordinates[index][1],z:geometry.coordinates[index][2]}));
  if(atoms.length!==count)throw Error('Unexpected atom count for '+id);
  const preparation=await api('/api/qchem/prepare',{molecule:id,atoms});
  if(preparation.identity_check.status!=='match'||!preparation.input_sha256)throw Error('Coordinate identity gate failed for '+id);
  realStructures.push({molecule:id,atom_count:count,force_field:geometry.force_field,energy:geometry.energy,unit:geometry.energy_unit,inchikey:preparation.identity_check.observed_inchikey,input_sha256:preparation.input_sha256});
 }
 checks.push('Bundled RDKit generated water, methane and ethanol; each coordinate-to-InChI preparation check passed');

 await click('Learn with a molecule');
 await click('Build starting structure');
 await wait(()=>document.querySelector('#qchem-atom-prediction'),'water lesson');
 set('#qchem-atom-prediction','3');await click('Check atom count');
 const coordinateCard=[...document.querySelectorAll('.qchem-answer-cards button')].find(element=>element.textContent.includes('Which atoms are present'));
 if(!coordinateCard)throw Error('Coordinate answer card missing');coordinateCard.click();await tick();
 await click('Continue to settings');
 const fixedCard=[...document.querySelectorAll('.qchem-answer-cards button')].find(element=>element.textContent.startsWith('No. It evaluates energy'));
 if(!fixedCard)throw Error('Single-point answer card missing');fixedCard.click();await tick();
 const transfer=document.querySelector('.qchem-transfer');
 if(!transfer||transfer.innerText.includes('Water'))throw Error('Transfer practice did not use a different molecule');
 set('#qchem-transfer-count','5');
 const transferCheck=[...transfer.querySelectorAll('button')].find(element=>element.textContent.trim()==='Check');if(!transferCheck)throw Error('Transfer count control missing');transferCheck.click();
 const transferFixed=[...transfer.querySelectorAll('button')].find(element=>element.textContent.includes('hold the supplied nuclei fixed'));if(!transferFixed)throw Error('Transfer motion card missing');transferFixed.click();await tick();
 if(!transfer.innerText.includes('Correct.'))throw Error('Transfer feedback was not visible');
 checks.push('Visible answer cards give immediate feedback, including a transfer check for a different molecule');

 await click('Review Q-Chem input');
 const lesson=document.querySelector('.qchem-workflow');
 if(!lesson.innerText.includes('Identity verified (InChI)'))throw Error('Verified water identity badge is not visible');
 lesson.querySelector('.qchem-identity summary').click();await tick();
 if(!lesson.innerText.includes('XLYOFNOQVPJJNP-UHFFFAOYSA-N'))throw Error('Expanded identity receipt has no water InChIKey');
 const exportMenu=lesson.querySelector('.qchem-export-menu');exportMenu.querySelector('summary').click();await tick();
 const download=button('Download Q-Chem input');
 if(!download?.disabled)throw Error('Download bypassed the visible review acknowledgement');
 lesson.querySelector('.qchem-ack input').click();await tick();
 if(button('Download Q-Chem input')?.disabled)throw Error('Reviewed checked input remained unavailable');
 if(lesson.querySelector('.calculation-result'))throw Error('Preparation stage rendered a result without a recorded job');
 if(!lesson.innerText.includes('Nothing has been submitted or calculated.'))throw Error('Run gate did not disclose preparation-only state');
 const reviewedInput=lesson.querySelector('[aria-label="Reviewed Q-Chem input"]')?.textContent;
 if(!reviewedInput)throw Error('Reviewed Q-Chem input is unavailable for the UI fixture');
 const fixtureJob={id:'f1f1f1f1f1f1f1f1f1f1f1f1f1f1f1f1',project:document.querySelector('#current-project')?.value,molecule:'water',input_text:reviewedInput,state:'SUCCEEDED',detail:'Simulated UI fixture only — no Q-Chem engine was launched.',method:'HF',basis:'def2-SVP',job_type:'single_point',input_sha256:'fixture-input-sha256',output_sha256:'fixture-output-sha256',output_text:'Simulated UI fixture only. No engine output exists.',engine:{provenance:'simulated'},artifacts:[],result:{energy_hartree:-75.123,converged:true,normal_termination:true}};
 restoreFetch=window.fetch;
 window.fetch=async(input,init)=>{const url=new URL(typeof input==='string'?input:input.url,location.href);const method=(init?.method??(typeof input==='string'?'GET':input.method)??'GET').toUpperCase();if(method==='GET'&&url.pathname==='/api/qchem/jobs'&&url.searchParams.get('project')===fixtureJob.project)return new Response(JSON.stringify({jobs:[fixtureJob]}),{headers:{'Content-Type':'application/json'}});return restoreFetch(input,init);};
 await click('Continue to calculation');
 await wait(()=>lesson.querySelector('.qchem-run'),'run stage');
 const resultCard=await wait(()=>lesson.querySelector('.calculation-result'),'simulated result fixture');
 window.fetch=restoreFetch;restoreFetch=null;
 if(lesson.querySelector('.qchem-run-controls')?.open)throw Error('Completed result did not collapse setup controls');
 if(document.querySelector('.workspace-scroll').scrollWidth>document.querySelector('.workspace-scroll').clientWidth+2)throw Error('Result workspace overflows horizontally');
 if(!resultCard.innerText.includes('Simulated engine fixture'))throw Error('Result fixture is not visibly marked simulated');
 if(!resultCard.innerText.includes('H2O')||!resultCard.innerText.includes('XLYOFNOQVPJJNP-UHFFFAOYSA-N'))throw Error('Result fixture lost its matching-input molecule context');
 set('select[aria-label="Energy units"]','kJ/mol');await tick();
 if(!resultCard.querySelector('[data-testid="qchem-energy"]')?.textContent?.includes('kJ/mol'))throw Error('Accessible energy-unit selector did not update the reading');
 const details=resultCard.querySelector('.result-details');if(details.open||resultCard.innerText.includes(fixtureJob.id))throw Error('Raw job ID is visible before Run details opens');
 details.querySelector('summary').click();await tick();if(!resultCard.innerText.includes(fixtureJob.id))throw Error('Run details did not disclose the raw job ID');
 const wrong=[...resultCard.parentElement.querySelectorAll('.result-feedback-card')].find(element=>element.textContent.includes('which reaction happens'));wrong.click();await tick();if(!wrong.innerText.includes('reaction claim needs'))throw Error('Wrong interpretation feedback is not visible');
 const right=[...resultCard.parentElement.querySelectorAll('.result-feedback-card')].find(element=>element.textContent.includes('It establishes an approximate electronic energy'));right.click();await tick();if(!right.innerText.includes('Correct.'))throw Error('Correct interpretation feedback is not visible');
 await click('What does this energy mean?');await wait(()=>lesson.querySelector('.qchem-error')?.innerText.includes('Qwen could not answer right now'),'friendly unavailable Qwen message');
 checks.push('Simulated UI-only result fixture is visibly labeled, keeps matching molecule context, switches units, hides raw ID by default, and gives accessible interpretation and Qwen-unavailable feedback');

 await command('help');await wait(()=>document.querySelector('.feature-index'),'feature index');
 set('#feature-search','energy');await tick();
 if(!document.querySelector('.feature-index').innerText.includes('CHEM-003'))throw Error('Feature index energy search failed');
 checks.push('Feature index finds the scoped energy task');

 await command('structures');await wait(()=>document.querySelector('#starter-molecule'),'molecule workspace');
 set('#starter-molecule','Butane');await tick();window.confirm=()=>true;await click('Load example');
 await wait(()=>document.querySelector('.formula')?.textContent==='C4H10','butane drawing');
 await click('Compare 5 starting shapes');await wait(()=>document.querySelectorAll('.energy-bars button').length===5,'five butane shape samples');
 const chart=document.querySelector('.shape-energy-chart');if(!chart?.innerText.includes('kcal/mol'))throw Error('Butane chart has no energy units');
 const bars=[...chart.querySelectorAll('.energy-bars button')];bars[4].click();await wait(()=>bars[4].getAttribute('aria-pressed')==='true','selected fifth shape');
 if(!document.querySelector('.sample-viewer button[aria-label="Rotate left"]'))throw Error('Selected shape has no visible 3D rotation control');
 checks.push('Five real local butane starting shapes render with units, selectable feedback, and 3D controls');

 const orca=await api('/api/orca/status'),qchem=await api('/api/qchem/status'),assistant=await api('/api/assistant/status');
 if(orca.status==='READY'||qchem.status==='CONFIGURED'||assistant.status==='READY')throw Error('Fresh base QA unexpectedly reports an external engine or Qwen ready');
 checks.push('No external quantum result or optional Qwen service was treated as available');
 return JSON.stringify({status:'PASS',application:'Chem313 '+(await api('/api/workbench')).version,environment:'Compiled AppKit / WKWebView with frozen Python; no Node/Python setup',checks,structures:realStructures,engine_status:{orca:orca.status,qchem:qchem.status,qwen:assistant.status},real_quantum_calculation:'NOT_RUN_NO_LICENSED_ENGINE',scientific_scope:'Real local RDKit force-field calculations and coordinate identity validation; explicitly simulated browser-only result fixture tests rendering, without launching a quantum engine'});
 }catch(error){if(restoreFetch)window.fetch=restoreFetch;return JSON.stringify({status:'FAIL',checks,error:String(error),body:document.body.innerText.slice(-6000)});}
