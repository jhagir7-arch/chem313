"""Lifecycle tests use a fake executable; they do not exercise ORCA chemistry."""
import pytest

from hypothesislab.conformers import molecule_conformer
from hypothesislab.orca_runtime import OrcaRuntime, executable_status
from hypothesislab.orca_input import prepare_orca_input
from hypothesislab.store import Store
from hypothesislab.validation import InputError


def prepared(store, project="ethanol"):
    params = {"geometry_sdf": molecule_conformer({"smiles": "CCO"})["sdf"], "job_type": "single_point",
              "charge": 0, "multiplicity": 1, "method": "B3LYP", "basis": "def2-SVP"}
    result = prepare_orca_input(params)
    source = store.put(project, "derived", "inp", result["input_text"].encode())
    store.event(project, "orca.prepare_input", "0" * 64, [source], {"simulated": True})
    return source


def fake(tmp_path, body):
    path = tmp_path / "fake-orca"
    path.write_text("#!/bin/sh\nif [ \"$1\" = \"--version\" ]; then echo 'Fake ORCA 0'; exit 0; fi\n" + body)
    path.chmod(0o700)
    return path


def test_simulated_normal_process_persists_output_and_conservative_convergence(tmp_path):
    store = Store(tmp_path / "data")
    runtime = OrcaRuntime(store, fake(tmp_path, "echo 'ORCA TERMINATED NORMALLY'\n"), timeout_seconds=2)
    job = runtime.start("ethanol", prepared(store))
    final = runtime.wait(job["id"])
    assert final["state"] == "SUCCEEDED"
    assert final["report"]["normal_termination_marker"] is True
    assert final["report"]["convergence"].startswith("UNASSESSED")
    assert len(final["artifacts"]) == 3
    assert [event["action"] for event in store.events("ethanol")] == ["orca.prepare_input", "orca.run_started", "orca.run_finished"]


def test_simulated_timeout_and_cancel_are_truthful(tmp_path):
    store = Store(tmp_path / "data")
    sleeper = fake(tmp_path, "sleep 2\necho late\n")
    timeout_runtime = OrcaRuntime(store, sleeper, timeout_seconds=1)
    timeout_job = timeout_runtime.start("timeout", prepared(store, "timeout"))
    assert timeout_runtime.wait(timeout_job["id"], 3)["state"] == "TIMED_OUT"
    cancel_runtime = OrcaRuntime(store, sleeper, timeout_seconds=5)
    cancel_job = cancel_runtime.start("cancel", prepared(store, "cancel"))
    assert cancel_runtime.cancel(cancel_job["id"])["state"] in {"QUEUED", "RUNNING"}
    assert cancel_runtime.wait(cancel_job["id"], 3)["state"] == "CANCELLED"


def test_terminal_cancel_does_not_deadlock_and_stubborn_process_group_is_killed(tmp_path):
    store = Store(tmp_path / "data")
    completed = OrcaRuntime(store, fake(tmp_path, "echo complete\n"), timeout_seconds=2)
    finished = completed.wait(completed.start("complete", prepared(store, "complete"))["id"], 3)
    assert completed.cancel(finished["id"])["state"] == "SUCCEEDED"

    stubborn = fake(tmp_path, "trap '' TERM\nwhile :; do sleep 1; done\n")
    runtime = OrcaRuntime(store, stubborn, timeout_seconds=8)
    job = runtime.start("stubborn", prepared(store, "stubborn"))
    assert runtime.cancel(job["id"])["state"] in {"QUEUED", "RUNNING"}
    assert runtime.wait(job["id"], 4)["state"] == "CANCELLED"


def test_persistence_failure_releases_active_slot_and_reports_interruption(tmp_path):
    class FailFinishStore(Store):
        def event(self, project, action, parameters_sha256, outputs, result):
            if action == "orca.run_finished":
                raise OSError("simulated audit failure")
            return super().event(project, action, parameters_sha256, outputs, result)

    store = FailFinishStore(tmp_path / "data")
    runtime = OrcaRuntime(store, fake(tmp_path, "echo complete\n"), timeout_seconds=2)
    final = runtime.wait(runtime.start("failure", prepared(store, "failure"))["id"], 3)
    assert final["state"] == "INTERRUPTED"
    assert "persistence failed" in final["detail"]
    assert runtime._active is None


def test_start_event_failure_does_not_reserve_an_active_slot(tmp_path):
    class FailStartStore(Store):
        def event(self, project, action, parameters_sha256, outputs, result):
            if action == "orca.run_started":
                raise OSError("simulated start audit failure")
            return super().event(project, action, parameters_sha256, outputs, result)

    store = FailStartStore(tmp_path / "data")
    runtime = OrcaRuntime(store, fake(tmp_path, "exit 0\n"))
    with pytest.raises(OSError, match="start audit"):
        runtime.start("startfail", prepared(store, "startfail"))
    assert runtime._active is None


def test_rejects_unlinked_or_mutated_input_and_reports_missing_configuration(tmp_path, monkeypatch):
    store = Store(tmp_path / "data")
    source = prepared(store)
    runtime = OrcaRuntime(store, fake(tmp_path, "exit 0\n"))
    mutated = dict(source)
    mutated["sha256"] = "f" * 64
    with pytest.raises(InputError):
        runtime.start("ethanol", mutated)
    unlinked = store.put("other", "derived", "inp", b"! B3LYP\n\n* xyz 0 1\nH 0 0 0\n*\n")
    with pytest.raises(InputError):
        runtime.start("other", unlinked)
    monkeypatch.delenv("OPENCHEM_ORCA_EXECUTABLE", raising=False)
    assert executable_status(None)["status"] == "NOT_CONFIGURED"


def test_durable_state_recovers_finished_and_interrupted_without_replay(tmp_path):
    import json
    store=Store(tmp_path/'data')
    runtime=OrcaRuntime(store,fake(tmp_path,"echo complete\n"))
    finished=runtime.wait(runtime.start('recover',prepared(store,'recover'))['id'],3)
    resumed=OrcaRuntime(store,runtime.executable)
    assert resumed.status(finished['id'])['state']=='SUCCEEDED'
    pending={'id':'a'*32,'project':'recover','state':'RUNNING'}
    (runtime._journal/('a'*32+'.json')).write_text(json.dumps(pending))
    recovered=OrcaRuntime(store,runtime.executable)
    assert recovered.status('a'*32)['state']=='INTERRUPTED'
    assert recovered._active is None
