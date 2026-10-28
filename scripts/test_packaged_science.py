"""Run every scientific adapter through a frozen service and saved artifacts."""
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'backend/src'), str(ROOT / 'scripts')]
from hypothesislab.science_contracts import EXAMPLES as SCIENCE
from hypothesislab.extended_contracts import EXAMPLES as EXTENDED
from hypothesislab.bioscience_contracts import EXAMPLES as BIOSCIENCE
from test_science_engines import reference_checks as science_reference
from test_extended_engines import reference_checks as extended_reference

BASE = os.environ['OPENCHEM_TEST_URL']
TOKEN = None
PROJECT = 'compiled-science-' + str(int(time.time()))


def call(path, data=None, raw_bytes=False):
    headers = {'Content-Type': 'application/json'}
    if TOKEN:
        headers['X-HypothesisLab-Session'] = TOKEN
    request = urllib.request.Request(BASE + path, data=json.dumps(data).encode() if data is not None else None, headers=headers)
    with urllib.request.urlopen(request, timeout=130) as response:
        raw = response.read()
        return json.loads(raw) if not raw_bytes and 'application/json' in response.headers.get('Content-Type', '') else raw


def wait(job_id):
    until = time.monotonic() + 130
    while time.monotonic() < until:
        job = call('/api/jobs/' + job_id)
        if job['state'] in {'SUCCEEDED', 'FAILED', 'CANCELLED', 'INTERRUPTED'}:
            return job
        time.sleep(.25)
    raise AssertionError('Job did not reach a terminal state')


def submit(operation, inputs):
    payload = {'action': 'science.run', 'params': {'operation': operation, 'inputs': inputs}, 'project': PROJECT}
    preview = call('/api/preview', payload)
    assert preview['operation']['operation'] == operation
    assert preview['requires_explicit_apply'] is True
    queued = call('/api/execute', {**payload, 'approved': True, 'preview_token': preview['preview_token']})
    return queued['result']['job_id']


TOKEN = call('/api/session')['session_token']
assert call('/api/workbench')['version'] == os.environ.get('OPENCHEM_EXPECTED_VERSION', '0.8.0')
registry = call('/api/engines/registry')
assert registry['counts']['registered'] == registry['counts']['downloaded'] == 54
assert len(call('/api/science/operations')['operations']) == len(SCIENCE) + len(EXTENDED) + len(BIOSCIENCE)
results = {}
started = time.monotonic()
for operation, inputs in {**SCIENCE, **EXTENDED, **BIOSCIENCE}.items():
    inputs = dict(inputs)
    if operation in {'pandas.csv', 'polars.csv'}:
        inputs['source'] = inputs['source'].replace('\n', '\r\n')
    job = wait(submit(operation, inputs))
    assert job['state'] == 'SUCCEEDED', (operation, job)
    assert job['result']['operation'] == operation
    assert job['resources']['gpu'] is False
    for artifact in job['artifacts']:
        project, group, filename = artifact['relative_path'].split('/')
        raw = call(f'/api/projects/{project}/artifact/{group}/{filename}', raw_bytes=True)
        if isinstance(raw, dict):
            # Original artifact bytes must not be parsed and serialized again.
            raise AssertionError('Artifact was unexpectedly transformed')
        assert hashlib.sha256(raw).hexdigest() == artifact['sha256']
        if filename.endswith('.csv'):
            assert raw == inputs['source'].encode()
    results[operation] = job['result']
    print(operation, 'PASS', flush=True)
science_reference(results)
extended_reference(results)
assert results['pyenzyme.document']['output']['name'] == BIOSCIENCE['pyenzyme.document']['name']
import math
assert math.isclose(results['pysb.first_order_decay']['output']['A'][-1], math.exp(-1), abs_tol=1e-5)
failed = wait(submit('meeko.prepare_pdbqt', {'smiles': 'not-a-smiles'}))
assert failed['state'] == 'FAILED' and failed.get('error')
assert not any('/reports/' in a['relative_path'] for a in failed['artifacts'])
job_id = submit('pyscf.rhf_singlepoint', EXTENDED['pyscf.rhf_singlepoint'])
cancelled = call('/api/jobs/' + job_id + '/cancel', {'approved': True})
assert cancelled['state'] == 'CANCELLED'
assert wait(job_id)['state'] == 'CANCELLED'
assert call('/api/projects/' + PROJECT + '/verify')['status'] == 'PASS'
evidence = {'status': 'PASS', 'runtime': 'frozen service with three compiled isolated workers', 'project': PROJECT,
            'results': results, 'registry_counts': registry['counts'], 'failed_input': failed, 'cancelled_job': cancelled,
            'checks': ['all26 approved queued jobs', 'numerical references', 'every saved artifact SHA256', 'exact CRLF CSV source',
                       'real invalid molecule fails without report', 'explicit cancellation', 'project integrity'],
            'wall_seconds': time.monotonic() - started}
(ROOT / 'evidence/packaged-science.json').write_text(json.dumps(evidence, indent=2) + '\n')
print('26 packaged scientific workflows passed')
