import json
import threading
import time

import pytest

from hypothesislab.store import Store
from hypothesislab.study_agent import LIMIT, StudyAgent, validate_plan
from hypothesislab.validation import InputError


def _raw(task="shapes", molecule="butane", samples=2):
    return json.dumps({"task": task, "molecule": molecule, "samples": samples})


def _infer(raw):
    return lambda prompt: (raw, {"model": "fixture", "variant": "test"})


def _result(samples, cancelled=False):
    candidates = [
        {"seed": 42, "status": "unique", "energy": 0.0, "relative_energy": 0.0,
         "sdf": "fixture conformer\n  OpenChem\n\n$$$$\n"}
    ]
    return {"canonical_smiles": "CCCC", "formula": "C4H10", "requested": samples,
            "completed": 1 if cancelled else samples, "cancelled": cancelled,
            "unique_count": 1, "candidates": candidates}


def _wait(agent, project, job_id):
    for _ in range(100):
        current = agent.status(project, job_id)
        if current["status"] in {"complete", "cancelled", "failed"}:
            return current
        time.sleep(0.01)
    pytest.fail("study job did not finish")


def test_validate_plan_binds_explicit_identity_and_requested_count():
    conflicting_identity = validate_plan("Compare two shapes of butane and ethanol", _raw(samples=2))
    assert conflicting_identity["task"] == "clarify"
    with pytest.raises(InputError, match="requested number"):
        validate_plan("Compare three shapes of butane", _raw(samples=2))


def test_validate_plan_requires_the_documented_five_shape_default_when_count_is_omitted():
    prompt = "Compare shapes of butane"
    assert validate_plan(prompt, _raw(samples=5))["samples"] == 5
    with pytest.raises(InputError, match="default number"):
        validate_plan(prompt, _raw(samples=4))


def test_validate_plan_clarifies_unknown_names_and_rejects_model_fences_or_extra_keys():
    unknown = validate_plan("Compare two shapes of unobtainium", _raw(samples=2))
    assert unknown["task"] == "clarify"
    for raw, message in (
        ("```json\n" + _raw() + "\n```", "incomplete plan"),
        (json.dumps({"task": "shapes", "molecule": "butane", "samples": 2, "extra": True}), "unsupported plan fields"),
    ):
        with pytest.raises(InputError, match=message):
            validate_plan("Compare two shapes of butane", raw)


@pytest.mark.parametrize("prompt", [
    "Will butane react to form unknown products?",
    "Predict aspirin drug interactions",
    "Run shell commands for butane",
])
def test_validate_plan_keeps_reactions_drugs_and_shell_requests_out_of_scope(prompt):
    result = validate_plan(prompt, _raw("shapes", "butane", 2))
    assert result == {"task": "unsupported", "message": LIMIT}


def test_plan_is_project_bound_expiring_and_single_use(tmp_path, monkeypatch):
    agent = StudyAgent(Store(tmp_path), infer=_infer(_raw()), sampler=lambda smiles, samples, stopped, progress: _result(samples))
    plan = agent.plan("alpha", "Compare two shapes of butane")
    with pytest.raises(InputError, match="belongs to another project"):
        agent.run("beta", plan["id"])

    original_monotonic = time.monotonic
    now = original_monotonic()
    monkeypatch.setattr("hypothesislab.study_agent.time.monotonic", lambda: now + 601)
    with pytest.raises(InputError, match="expired"):
        agent.run("alpha", plan["id"])

    monkeypatch.setattr("hypothesislab.study_agent.time.monotonic", original_monotonic)
    plan = agent.plan("alpha", "Compare two shapes of butane")
    job = agent.run("alpha", plan["id"])
    _wait(agent, "alpha", job["id"])
    with pytest.raises(InputError, match="expired"):
        agent.run("alpha", plan["id"])


def test_only_one_active_study_and_cancel_keeps_partial_result(tmp_path):
    started = threading.Event()
    release = threading.Event()

    def slow_sampler(smiles, samples, stopped, progress):
        started.set()
        while not stopped() and not release.wait(0.01):
            pass
        progress(1, samples)
        return _result(samples, cancelled=stopped())

    agent = StudyAgent(Store(tmp_path), infer=_infer(_raw()), sampler=slow_sampler)
    first_plan = agent.plan("alpha", "Compare two shapes of butane")
    first = agent.run("alpha", first_plan["id"])
    assert started.wait(1)
    second_plan = agent.plan("alpha", "Compare two shapes of butane")
    with pytest.raises(InputError, match="already running"):
        agent.run("alpha", second_plan["id"])

    agent.cancel("alpha", first["id"])
    complete = _wait(agent, "alpha", first["id"])
    assert complete["status"] == "cancelled"
    assert complete["result"]["completed"] == 1
    assert complete["result"]["cancelled"] is True


def test_completed_study_persists_event_and_hash_verified_artifacts(tmp_path):
    store = Store(tmp_path)
    agent = StudyAgent(store, infer=_infer(_raw()), sampler=lambda smiles, samples, stopped, progress: _result(samples))
    plan = agent.plan("alpha", "Compare two shapes of butane")
    complete = _wait(agent, "alpha", agent.run("alpha", plan["id"])["id"])

    assert complete["status"] == "complete"
    assert len(complete["artifacts"]) == 3
    event = store.events("alpha")[-1]
    assert event["action"] == "molecule.study"
    assert event["result"]["cancelled"] is False
    assert store.verify_artifacts("alpha")["status"] == "PASS"


def test_explicit_supported_shape_request_recovers_model_clarification_transparently():
    for prompt,name,count in [('Can you compare three conformations of acetic acid?','acetic acid',3),('I need two starting geometries for glycine','glycine',2)]:
        checked=validate_plan(prompt,_raw('clarify',name,None))
        assert checked['task']=='shapes' and checked['samples']==count
        assert checked['molecule']==name and 'Qwen asked for clarification' in checked['planner_note']
    assert validate_plan('Compare cis and trans 2-butene',_raw('clarify','2-butene',None))['task']=='clarify'
    assert validate_plan('Do not compare two shapes of glycine',_raw('clarify','glycine',None))['task']=='clarify'
    with pytest.raises(InputError,match='one and eight'):
        validate_plan('Compare twenty shapes of glycine',_raw('clarify','glycine',None))
