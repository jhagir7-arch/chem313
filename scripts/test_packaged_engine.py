"""Exercise a running local engine with only Python's standard library."""
import hashlib
import json
import os
import urllib.request
import urllib.error

base=os.environ.get('OPENCHEM_TEST_URL','http://127.0.0.1:8789')
def call(path,data=None,token=None,origin=None):
    headers={'Content-Type':'application/json'}
    if token:headers['X-HypothesisLab-Session']=token
    if origin:headers['Origin']=origin
    req=urllib.request.Request(base+path,data=json.dumps(data).encode() if data else None,headers=headers)
    with urllib.request.urlopen(req) as response:
        raw=response.read()
        return json.loads(raw) if 'application/json' in response.headers.get('Content-Type','') else raw

def denied(path,status,data=None,token=None,origin=None):
    try:call(path,data,token,origin)
    except urllib.error.HTTPError as e:assert e.code==status,(e.code,e.read());return
    raise AssertionError('Expected request to be rejected')

denied('/api/session',403,origin='https://untrusted.invalid')
token=call('/api/session')['session_token']
denied('/api/workbench',403)
info=call('/api/workbench',token=token)
assert info['name']=='Chem313' and info['engines']['rdkit']
r=call('/api/execute',{'action':'molecule.generate_conformer','params':{'smiles':'CCO'},'project':'frozen-proof','approved':True},token)
assert r['result']['coordinate_count']==9 and r['result']['converged']
geometry=r['result']['sdf']
settings={'geometry_sdf':geometry,'job_type':'optimization_frequency','charge':0,'multiplicity':1,'method':'B3LYP','basis':'def2-SVP'}
payload={'action':'orca.prepare_input','params':settings,'project':'frozen-proof'}
denied('/api/preview',422,{**payload,'params':{**settings,'multiplicity':2}},token)
preview=call('/api/preview',payload,token)
assert '* xyz 0 1' in preview['prepared_input']
reply=call('/api/execute',{**payload,'approved':True,'preview_token':preview['preview_token']},token)
contents={}
for a in reply['artifacts']:
    project,group,name=a['relative_path'].split('/')
    raw=call(f'/api/projects/{project}/artifact/{group}/{name}',token=token)
    # The helper parses JSON reports, while molecular files remain exact bytes.
    contents[name.rsplit('.',1)[1]]=raw
assert contents['sdf']==geometry.encode()
assert contents['inp']==preview['prepared_input'].encode()
assert contents['json']['input_sha256']==hashlib.sha256(contents['inp']).hexdigest()
assert reply['result']['atom_count']==9
text='Frozen engine UTF-8 proof: Δ and مشاہدہ\r\n'
payload={'action':'project.save_note','params':{'text':text},'project':'frozen-proof'}
preview=call('/api/preview',payload,token)
assert preview['preview_token']
reply=call('/api/execute',{**payload,'approved':True,'preview_token':preview['preview_token']},token)
a=reply['artifacts'][0]
assert a['sha256']==hashlib.sha256(text.encode()).hexdigest()
project,group,name=a['relative_path'].split('/')
assert call(f'/api/projects/{project}/artifact/{group}/{name}',token=token)==text.encode()
denied('/api/execute',422,{**payload,'approved':True,'preview_token':preview['preview_token']},token)
params={'csv':'x,y\r\n0,1\r\n1,3\r\n2,5\r\n','x_column':'x','y_column':'y','x_unit':'s','y_unit':'V'}
payload={'action':'measurement.fit_csv','params':params,'project':'frozen-proof'}
preview=call('/api/preview',payload,token)
r=call('/api/execute',{**payload,'approved':True,'preview_token':preview['preview_token']},token)
assert r['result']['slope']==2 and r['result']['intercept']==1
svg=next(a for a in r['artifacts'] if a['relative_path'].endswith('.svg'))
project,group,name=svg['relative_path'].split('/')
assert b'<svg' in call(f'/api/projects/{project}/artifact/{group}/{name}',token=token)
# First lesson uses the included real MMFF94 engine and durable results, not a fixture.
lesson=[]
for smiles in ['CCO','O','C']:
    payload={'action':'molecule.relax_geometry','params':{'smiles':smiles,'seed':42},'project':'first-real-calculation'}
    preview=call('/api/preview',payload,token)
    reply=call('/api/execute',{**payload,'approved':True,'preview_token':preview['preview_token']},token)
    result=reply['result']
    assert result['converged'] and result['engine_provenance']=='real',result
    assert result['force_field']=='MMFF94' and result['energy_unit']=='kcal/mol'
    assert result['final_energy_kcal_mol']<=result['initial_energy_kcal_mol']+1e-5
    assert len(reply['artifacts'])==3
    for artifact in reply['artifacts']:
        project,group,name=artifact['relative_path'].split('/')
        raw=call(f'/api/projects/{project}/artifact/{group}/{name}',token=token)
        if isinstance(raw,bytes):assert hashlib.sha256(raw).hexdigest()==artifact['sha256']
        else:assert raw['inchikey']==result['inchikey'] and raw['engine_provenance']=='real'
    denied('/api/execute',422,{**payload,'approved':True,'preview_token':preview['preview_token']},token)
    lesson.append({k:result[k] for k in ['name','inchikey','converged','initial_energy_kcal_mol','final_energy_kcal_mol','energy_change_kcal_mol','rdkit_version']})
assert call('/api/projects/first-real-calculation/verify',token=token)['status']=='PASS'
print(json.dumps({'real_first_calculation':lesson},indent=2))
verify=call('/api/projects/frozen-proof/verify',token=token)
assert verify['status']=='PASS',verify
print(json.dumps({'status':'PASS','runtime':'running local Chem313 service','version':info['version'],'engines':info['engines'],'checks':['untrusted origin rejected','unauthenticated data rejected','RDKit MMFF 3D generation','ORCA input charge-spin rejection and exact source/input/report retrieval','UTF-8 byte-exact note storage/download','single-use receipt replay rejected','SciPy known-line fit','Matplotlib SVG artifact','stored artifact integrity']},indent=2))
