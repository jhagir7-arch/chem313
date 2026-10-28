from types import SimpleNamespace
from fastapi import FastAPI
from fastapi.testclient import TestClient
from hypothesislab import api
from hypothesislab.assistant import Assistant
from hypothesislab.calculation_api import register
from hypothesislab.workbench import WorkbenchEngine


def test_qwen_orca_routes_require_session_and_trusted_origin(tmp_path,monkeypatch):
    app=FastAPI()
    facade=SimpleNamespace(ROOT=tmp_path,engine=WorkbenchEngine(tmp_path),SESSION_HEADER=api.SESSION_HEADER,require_session=api.require_session)
    register(app,facade)
    called=[]
    monkeypatch.setattr(Assistant,'propose',lambda self,prompt:called.append(prompt) or {'decision':'clarify','message':'Specify molecule and choices'})
    headers={'X-HypothesisLab-Session':api.SESSION}
    with TestClient(app) as client:
        assert client.post('/api/assistant/propose',json={'prompt':'water'}).status_code==403
        assert client.post('/api/assistant/propose',json={'prompt':'water'},headers={**headers,'Origin':'https://untrusted.invalid'}).status_code==403
        assert not called
        assert client.post('/api/assistant/propose',json={'prompt':'water','command':'execute'},headers=headers).status_code==422
        assert client.post('/api/assistant/propose',json={'prompt':'water'},headers=headers).json()['decision']=='clarify'
        assert called==['water']
        assert client.get('/api/orca/status',headers=headers).json()['status']=='NOT_CONFIGURED'
        assert client.post('/api/orca/configure',json={'executable':'relative/path'},headers=headers).status_code==422
        assert not (tmp_path/'orca.json').exists()
        assert client.post('/api/orca/jobs/missing/cancel',json={'approved':'true'},headers=headers).status_code==422
        assert client.post('/api/orca/jobs/missing/cancel',json={'approved':False},headers=headers).status_code==422


def test_configured_path_survives_restart_without_any_automatic_calculation(tmp_path, monkeypatch):
    # Executable is a simulation used only for connection and persistence checks.
    import json
    binary=tmp_path/'simulated-orca'
    binary.write_text('#!/bin/sh\n[ "$1" = "--version" ] || exit 99\necho "SIMULATED connection probe"\n')
    binary.chmod(0o700)
    # Probe behavior is tested separately; this test checks configuration and persistence.
    monkeypatch.setattr("hypothesislab.calculation_api.executable_status", lambda path: {"status": "READY", "path": str(path)})
    app=FastAPI()
    facade=SimpleNamespace(ROOT=tmp_path,engine=WorkbenchEngine(tmp_path),SESSION_HEADER=api.SESSION_HEADER,require_session=api.require_session)
    register(app,facade)
    headers={'X-HypothesisLab-Session':api.SESSION}
    with TestClient(app) as client:
        result=client.post('/api/orca/configure',headers=headers,json={'executable':str(binary)})
        assert result.status_code==200 and result.json()['status']=='READY'
        assert facade.engine.orca._active is None
        assert json.loads((tmp_path/'orca.json').read_text())['executable']==str(binary)
    resumed=WorkbenchEngine(tmp_path)
    assert resumed.orca.executable==binary


def test_orca_discovery_requires_session_and_does_not_probe_or_configure(tmp_path, monkeypatch):
    import hypothesislab.calculation_api as calculation_api

    app=FastAPI()
    facade=SimpleNamespace(ROOT=tmp_path,engine=WorkbenchEngine(tmp_path),SESSION_HEADER=api.SESSION_HEADER,require_session=api.require_session)
    register(app,facade)
    candidate=tmp_path/'found-orca'
    candidate.write_text('#!/bin/sh\nexit 0\n')
    candidate.chmod(0o700)
    calls=[]
    monkeypatch.setattr(calculation_api, 'discover_executables', lambda preferred: calls.append(preferred) or [candidate])
    headers={'X-HypothesisLab-Session':api.SESSION}
    with TestClient(app) as client:
        assert client.get('/api/orca/discover').status_code==403
        reply=client.get('/api/orca/discover',headers=headers)
        assert reply.status_code==200
        assert reply.json()['configured'] is None
        assert reply.json()['candidates']==[str(candidate)]
        assert not (tmp_path/'orca.json').exists()
    assert calls==[None]
