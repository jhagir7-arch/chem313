"""Black-box checks of the embedded service with no development PATH/runtime."""
import contextlib
import json
import os
from pathlib import Path
import runpy
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

app = Path(sys.argv[1]).resolve()
report_path = Path(sys.argv[2]).resolve()
engine = app / 'Contents/Resources/engine/openchem-engine'
checks = []
with tempfile.TemporaryDirectory(prefix='OpenChem standalone QA ') as temporary:
    root = Path(temporary)
    home, data = root / 'home', root / 'project data'
    home.mkdir(); data.mkdir()
    env = {'PATH':'/usr/bin:/bin', 'HOME':str(home), 'TMPDIR':'/tmp'}
    def start():
        log = (root / 'stderr.log').open('ab')
        process = subprocess.Popen([str(engine),'--data',str(data)], env=env, cwd=root, stdout=subprocess.PIPE, stderr=log, text=True)
        line = process.stdout.readline()
        if not line:
            raise RuntimeError('No readiness record: '+(root/'stderr.log').read_text())
        return process, json.loads(line)['url'], log
    def stop(process, log):
        process.terminate()
        try: process.wait(timeout=10)
        except subprocess.TimeoutExpired: process.kill(); process.wait()
        log.close()
    process, base, log = start()
    try:
        os.environ['OPENCHEM_TEST_URL'] = base
        runpy.run_path(str(Path(__file__).with_name('test_packaged_engine.py')), run_name='__main__')
        checks.append('Packaged engine: RDKit, ORCA preparation, immutable artifacts, SciPy, Matplotlib, session/origin/replay protection')
        def api(path, payload=None):
            headers = {'Content-Type':'application/json'}
            if path != '/api/session': headers['X-HypothesisLab-Session'] = token
            req = urllib.request.Request(base+path, data=json.dumps(payload).encode() if payload is not None else None, headers=headers)
            with urllib.request.urlopen(req,timeout=30) as response: return json.load(response)
        token = api('/api/session')['session_token']
        assert {op['operation'] for op in api('/api/science/operations')['operations']} == {'numpy.summary','scipy.line'}
        registry = api('/api/engines/registry')
        assert len(registry['engines']) == 7 and all(row['runtime']['bundled'] for row in registry['engines'])
        model = api('/api/assistant/status')
        if (app/'Contents/Resources/models/qwen/public-model').is_dir():
            assert model['status']=='READY' and model['variant']=='base-4bit-no-adapter' and model['adapter_sha256'] is None
            for prompt, smiles in [('Build water O, charge 0, multiplicity 1, HF def2-SVP single point calculation.','O'),('Build ethanol CCO, charge 0, multiplicity 1, B3LYP def2-SVP optimization.','CCO')]:
                draft=api('/api/assistant/propose',{'prompt':prompt})
                assert draft['decision']=='proposal' and draft['validation']['canonical_smiles']==smiles, draft
                assert draft['provenance']['variant']=='base-4bit-no-adapter' and draft['provenance']['adapter_sha256'] is None
            clarification=api('/api/assistant/propose',{'prompt':'Help me with a molecule.'})
            assert clarification['decision']=='clarify' and clarification['smiles'] is None
            frequency_prompt='Build benzene c1ccccc1 neutral singlet PBE0 def2-SVP optimization and frequencies.'
            try:
                frequency=api('/api/assistant/propose',{'prompt':frequency_prompt})
                assert frequency['decision']=='clarify' or frequency['job_type']=='optimization_frequency', frequency
            except urllib.error.HTTPError as error:
                assert error.code==422
            checks.append('Offline bundled Qwen: validated water and ethanol drafts, non-applicable clarification, frequency conflict rejected or preserved; no private adapter')
        else:
            assert model['status'] != 'READY'
        jobs = []
        for operation, inputs, expected in [('numpy.summary',{'values':[1,2,3,4,5],'unit':'V'}, {'mean':3}), ('scipy.line',{'x':[0,1,2],'y':[1,3,5],'x_unit':'s','y_unit':'V'},{'slope':2,'intercept':1})]:
            payload = {'action':'science.run','params':{'operation':operation,'inputs':inputs},'project':'frozen-proof'}
            receipt = api('/api/preview',payload)
            reply = api('/api/execute',{**payload,'approved':True,'preview_token':receipt['preview_token']})
            deadline = time.monotonic()+125
            while True:
                job = api('/api/jobs/'+reply['result']['job_id'])
                if job['state'] not in {'QUEUED','RUNNING'}: break
                if time.monotonic() > deadline: raise RuntimeError('Job did not terminate')
                time.sleep(.15)
            assert job['state']=='SUCCEEDED',job
            for key, value in expected.items(): assert job['result']['output'][key] == value,job
            jobs.append(job)
        checks.append('Both embedded subprocess worker operations passed known numerical references')
        # Missing worker fails before durable queuing, even if the scientific input itself is valid.
        unavailable={'action':'science.run','params':{'operation':'pint.convert','inputs':{'value':1000,'from_unit':'milligram','to_unit':'gram'}},'project':'frozen-proof'}
        try: api('/api/preview',unavailable)
        except urllib.error.HTTPError as error: assert error.code==422
        else: raise AssertionError('Unavailable engine accepted')
        assert api('/api/projects/frozen-proof/verify')['status']=='PASS'
        checks.append('Unavailable engine rejected before queuing; fresh project integrity passed')
    finally: stop(process,log)
    process, base, log = start()
    try:
        token = api('/api/session')['session_token']
        assert api('/api/projects/frozen-proof/verify')['status']=='PASS'
        for job in jobs: assert api('/api/jobs/'+job['id'])['state']=='SUCCEEDED'
        checks.append('Quit/relaunch preserves scientific jobs and project artifact integrity')
    finally: stop(process,log)
    result={'status':'PASS','environment':{'PATH':env['PATH'],'external_python_node':False,'fresh_home':True,'relocated_cwd':True},'checks':checks,'jobs':[{'operation':job['operation'],'state':job['state'],'output':job['result']['output']} for job in jobs]}
    report_path.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
