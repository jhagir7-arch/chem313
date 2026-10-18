import pytest
from hypothesislab.workbench import WorkbenchEngine
from hypothesislab.conformers import molecule_conformer
from hypothesislab.validation import InputError


def prepared(engine):
    params=dict(geometry_sdf=molecule_conformer({'smiles':'O'})['sdf'],job_type='single_point',charge=0,multiplicity=1,method='HF',basis='def2-SVP')
    preview=engine.preview('orca.prepare_input',params,'water')
    saved=engine.execute('orca.prepare_input',params,'water',True,preview['preview_token'])
    return next(a for a in saved['artifacts'] if a['relative_path'].endswith('.inp'))


def test_run_requires_exact_review_and_single_use_approval(tmp_path,monkeypatch):
    engine=WorkbenchEngine(tmp_path)
    artifact=prepared(engine)
    engine.orca.executable=tmp_path/'simulated-only'
    engine.orca.executable.write_text('#!/bin/sh\nexit 0\n')
    engine.orca.executable.chmod(0o700)
    started=[]
    monkeypatch.setattr(engine.orca,'start',lambda project,source:started.append((project,source)) or {'id':'simulated','state':'QUEUED'})
    params={'source_artifact':artifact}
    preview=engine.preview('orca.run',params,'water')
    with pytest.raises(InputError):
        engine.execute('orca.run',params,'water',True)
    assert not started
    result=engine.execute('orca.run',params,'water',True,preview['preview_token'])
    assert result['job']['id']=='simulated' and len(started)==1
    with pytest.raises(InputError):
        engine.execute('orca.run',params,'water',True,preview['preview_token'])
    assert len(started)==1


def test_missing_engine_and_unlinked_artifact_cannot_run(tmp_path):
    engine=WorkbenchEngine(tmp_path)
    artifact=prepared(engine)
    engine.orca.executable=None
    with pytest.raises(InputError,match='not configured'):
        engine.preview('orca.run',{'source_artifact':artifact},'water')
    engine.orca.executable=tmp_path/'simulated-only'
    engine.orca.executable.write_text('#!/bin/sh\nexit 0\n')
    engine.orca.executable.chmod(0o700)
    with pytest.raises(InputError):
        engine.preview('orca.run',{'source_artifact':{**artifact,'sha256':'0'*64}},'water')


def test_executable_change_invalidates_review(tmp_path,monkeypatch):
    engine=WorkbenchEngine(tmp_path)
    artifact=prepared(engine)
    engine.orca.executable=tmp_path/'simulation-only'
    engine.orca.executable.write_text('#!/bin/sh\nexit 0\n')
    engine.orca.executable.chmod(0o700)
    params={'source_artifact':artifact}
    preview=engine.preview('orca.run',params,'water')
    engine.orca.executable.write_text('#!/bin/sh\nexit 1\n')
    with pytest.raises(InputError,match='changed after preview'):
        engine.execute('orca.run',params,'water',True,preview['preview_token'])
    assert engine.orca._active is None
