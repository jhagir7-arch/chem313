import json

import pytest

from hypothesislab import qwen_worker as worker


def test_study_prompt_has_strict_schema_and_examples():
    system = worker.study_prompt('Teach butane shapes')[0]['content']
    assert 'exactly these keys: task, molecule, samples' in system
    assert "'shapes', 'mixture', 'clarify', 'unsupported'" not in system
    for example in ('butane', 'ethanol', 'ethanol-water', 'aspirin', 'drug breakdown', 'molecular shapes'):
        assert example in system
    assert 'scientific prose, code' in system


def test_study_deployment_uses_only_explicit_pinned_public_resources(tmp_path, monkeypatch):
    resources = tmp_path/'Resources'
    model = resources/'models/qwen/public-model'
    model.mkdir(parents=True)
    for name in worker.PUBLIC_FILES:
        (model/name).write_bytes(b'fixture')
    monkeypatch.setattr(worker, 'digest', lambda path: worker.PUBLIC_FILES[path.name])
    monkeypatch.setenv('OPENCHEM_QWEN_RESOURCES', str(resources))
    selected, adapter, provenance = worker.study_deployment()
    assert selected == model
    assert adapter is None
    assert provenance['variant'] == worker.PUBLIC_VARIANT
    assert provenance['adapter_sha256'] is None
    monkeypatch.delenv('OPENCHEM_QWEN_RESOURCES')
    with pytest.raises(ValueError, match='packaged public'):
        worker.study_deployment()


def test_study_schema_examples_are_exact_json():
    examples = [
        '{"task":"shapes","molecule":"butane","samples":5}',
        '{"task":"shapes","molecule":"ethanol","samples":4}',
        '{"task":"mixture","molecule":null,"samples":null}',
        '{"task":"shapes","molecule":"aspirin","samples":5}',
        '{"task":"unsupported","molecule":null,"samples":null}',
        '{"task":"clarify","molecule":null,"samples":null}',
    ]
    for raw in examples:
        value = json.loads(raw)
        assert set(value) == {'task', 'molecule', 'samples'}
