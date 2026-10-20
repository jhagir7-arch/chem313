import json
from types import SimpleNamespace

import pytest

from hypothesislab import assistant, qwen_worker as worker
from hypothesislab.validation import InputError


def public_resources(tmp_path):
    model = tmp_path/'models/qwen/public-model'
    model.mkdir(parents=True)
    for name in worker.PUBLIC_FILES:
        (model/name).write_bytes(b'fixture')
    return model


def test_public_model_never_requires_private_adapter(tmp_path, monkeypatch):
    model = public_resources(tmp_path)
    selected, adapter, provenance = worker.deployment(tmp_path)
    assert selected == model and adapter is None
    assert provenance['variant'] == worker.PUBLIC_VARIANT
    assert provenance['adapter_sha256'] is None
    monkeypatch.setattr(worker, 'digest', lambda path: worker.PUBLIC_FILES[path.name])
    worker.verify_assets(selected, adapter)
    monkeypatch.setattr(worker, 'digest', lambda path: 'corrupt')
    with pytest.raises(ValueError, match='integrity'):
        worker.verify_assets(selected, adapter)


def test_public_status_uses_engine_relative_resources(tmp_path, monkeypatch):
    model = public_resources(tmp_path)
    executable = tmp_path/'engine/openchem-engine'
    runtime = tmp_path/'workers/qwen/qwen-worker'
    runtime.parent.mkdir(parents=True); runtime.touch()
    monkeypatch.setattr(assistant.sys, 'frozen', True, raising=False)
    monkeypatch.setattr(assistant.sys, 'executable', str(executable))
    service = assistant.Assistant(tmp_path/'data')
    status = service.status()
    assert status['status'] == 'READY'
    assert status['adapter_sha256'] is None
    assert 'no OpenChem fine-tuning' in status['detail']
    (model/'tokenizer.json').unlink()
    assert service.status()['status'] == 'UNAVAILABLE'


def test_public_worker_provenance_is_bound_before_accepting_draft(tmp_path, monkeypatch):
    service = assistant.Assistant(tmp_path)
    provenance = worker.deployment(public_resources(tmp_path).parents[2])[2]
    status = {'status':'READY', 'model':worker.MODEL_ID, **provenance}
    monkeypatch.setattr(service, 'status', lambda:status)
    monkeypatch.setattr(assistant, 'worker_command', lambda:(['fixture-worker'], None))
    draft = dict(action='proposal',smiles='O',job_type='single_point',charge=0,
                 multiplicity=1,method='HF',basis='def2-SVP',message='Review water')
    result = dict(raw=json.dumps(draft),seconds=1,model=worker.MODEL_ID,**provenance)
    def run(*args, stdout, **kwargs):
        stdout.write(json.dumps(result).encode())
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(assistant.subprocess, 'run', run)
    accepted = service.propose('Water O charge 0 multiplicity 1 HF def2-SVP single point')
    assert accepted['provenance']['variant'] == worker.PUBLIC_VARIANT
    assert accepted['provenance']['adapter_sha256'] is None
    result['model_sha256'] = 'untrusted'
    with pytest.raises(InputError, match='provenance'):
        service.propose('Water O charge 0 multiplicity 1 HF def2-SVP single point')
    assert len(list((tmp_path/'.assistant').glob('*.json'))) == 1
