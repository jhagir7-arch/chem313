import hashlib
import json
import sys
import threading
import time

import pytest

from hypothesislab.science_jobs import ScienceJobs
from hypothesislab.validation import InputError
from hypothesislab.workbench import WorkbenchEngine


def wait_for_job(engine, job_id, timeout=20):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        job = engine.jobs.get(job_id)
        if job["state"] in {"SUCCEEDED", "FAILED", "CANCELLED", "INTERRUPTED"}:
            return job
        time.sleep(0.03)
    raise AssertionError(f"job {job_id} did not finish: {engine.jobs.get(job_id)}")


def submit(engine, params, project="science"):
    ticket = engine.preview("science.run", params, project)["preview_token"]
    return engine.execute("science.run", params, project, True, ticket)["result"]["job_id"]


def fixture_worker_command(operation):
    script = (
        "import json,time; time.sleep(5); "
        "print(json.dumps({'schema':'openchem.science.result.v1',"
        f"'operation':{operation!r},'engine':'Pandas','version':'fixture',"
        "'output':{},'resources':{}}))"
    )
    return [sys.executable, "-c", script], None


def test_science_requires_bound_single_use_approval_and_rejects_invalid_inputs(tmp_path):
    engine = WorkbenchEngine(tmp_path)
    try:
        params = {"operation": "numpy.summary", "inputs": {"values": [1.0, 2.0], "unit": "a.u."}}
        ticket = engine.preview("science.run", params, "science")["preview_token"]
        changed = {"operation": "numpy.summary", "inputs": {"values": [1.0, 3.0], "unit": "a.u."}}
        with pytest.raises(InputError):
            engine.execute("science.run", changed, "science", True, ticket)
        with pytest.raises(InputError):
            engine.execute("science.run", params, "science", True, ticket)
        with pytest.raises(InputError):
            engine.execute("science.run", params, "science", True, None)
        assert engine.jobs.jobs == {}
        assert not (tmp_path / "science").exists()

        for invalid in (
            {"operation": "numpy.summary", "inputs": {"values": [1.0, 2.0], "unit": "a.u.", "extra": 1}},
            {"operation": "numpy.summary", "inputs": {"values": [1.0, float("nan")], "unit": "a.u."}},
            {"operation": "numpy.summary", "inputs": {"values": [1.0, 1e13], "unit": "a.u."}},
        ):
            with pytest.raises(InputError):
                engine.preview("science.run", invalid, "science")
        assert engine.jobs.jobs == {}
    finally:
        engine.jobs.shutdown()


def test_real_numpy_and_pint_jobs_persist_reports_and_verify_project(tmp_path):
    engine = WorkbenchEngine(tmp_path)
    try:
        numpy_id = submit(engine, {"operation": "numpy.summary", "inputs": {"values": [1.0, 2.0, 3.0], "unit": "a.u."}})
        numpy = wait_for_job(engine, numpy_id)
        assert numpy["state"] == "SUCCEEDED"
        assert numpy["result"]["engine"] == "NumPy"
        assert numpy["result"]["output"]["mean"] == pytest.approx(2.0)
        assert any(item["relative_path"].endswith(".json") for item in numpy["artifacts"])

        pint_id = submit(engine, {"operation": "pint.convert", "inputs": {"value": 1000.0, "from_unit": "milligram", "to_unit": "gram"}})
        pint = wait_for_job(engine, pint_id)
        assert pint["state"] == "SUCCEEDED"
        assert pint["result"]["engine"] == "Pint"
        assert pint["result"]["output"]["value"] == pytest.approx(1.0)
        assert pint["result"]["output"]["unit"] == "gram"
        assert engine.store.verify_artifacts("science")["status"] == "PASS"
    finally:
        engine.jobs.shutdown()


def test_csv_source_bytes_and_hash_survive_worker_failure(tmp_path, monkeypatch):
    engine = WorkbenchEngine(tmp_path)
    source = "name,value\r\nα,1\r\n"
    params = {"operation": "pandas.csv", "inputs": {"source": source}}
    failure = [sys.executable, "-c", "import json; print(json.dumps({'status':'FAILED','error':'fixture worker failure'})); raise SystemExit(2)"]
    monkeypatch.setattr("hypothesislab.science_jobs.worker_command", lambda operation: (failure, None))
    monkeypatch.setattr("hypothesislab.workbench.worker_command", lambda operation: (failure, None))
    try:
        job_id = submit(engine, params)
        job = wait_for_job(engine, job_id)
        assert job["state"] == "FAILED"
        assert "fixture worker failure" in job["error"]
        csv_artifact = next(item for item in job["artifacts"] if item["relative_path"].endswith(".csv"))
        assert csv_artifact["sha256"] == hashlib.sha256(source.encode("utf-8")).hexdigest()
        assert (tmp_path / csv_artifact["relative_path"]).read_bytes() == source.encode("utf-8")
        assert [event["action"] for event in engine.store.events("science")] == ["science.queued", "science.failed"]
    finally:
        engine.jobs.shutdown()


def test_nonfinite_worker_json_is_failed_without_accepting_a_report(tmp_path, monkeypatch):
    engine = WorkbenchEngine(tmp_path)
    params = {"operation": "pandas.csv", "inputs": {"source": "a,b\n1,2\n"}}
    # JSON accepts this exponent literal, but Python decodes it as infinity.
    # The job boundary must reject it before report persistence.
    raw = ('{"schema":"openchem.science.result.v1","operation":"pandas.csv",'
           '"engine":"Pandas","version":"fixture","output":{"value":1e999},"resources":{}}')
    worker = [sys.executable, "-c", f"import sys; sys.stdout.write({raw!r})"]
    monkeypatch.setattr("hypothesislab.science_jobs.worker_command", lambda operation: (worker, None))
    monkeypatch.setattr("hypothesislab.workbench.worker_command", lambda operation: (worker, None))
    try:
        job = wait_for_job(engine, submit(engine, params))
        assert job["state"] == "FAILED"
        assert "Out of range float values" in job["error"]
        assert "result" not in job
        assert all("/reports/" not in item["relative_path"] for item in job["artifacts"])
        assert [event["action"] for event in engine.store.events("science")] == ["science.queued", "science.failed"]
    finally:
        engine.jobs.shutdown()


def test_startup_marks_unfinished_job_interrupted_without_replay(tmp_path):
    engine = WorkbenchEngine(tmp_path)
    job_id = "a" * 32
    engine.jobs._persist({"id": job_id, "state": "RUNNING", "project": "science", "operation": "numpy.summary"})
    engine.jobs.shutdown()
    recovered = ScienceJobs(engine.store)
    try:
        job = recovered.get(job_id)
        assert job["state"] == "INTERRUPTED"
        assert "retry" in job["error"]
        assert recovered.processes == {}
    finally:
        recovered.shutdown()


def test_cancelling_queued_or_running_worker_never_accepts_result(tmp_path, monkeypatch):
    engine = WorkbenchEngine(tmp_path)
    monkeypatch.setattr("hypothesislab.science_jobs.worker_command", fixture_worker_command)
    monkeypatch.setattr("hypothesislab.workbench.worker_command", fixture_worker_command)
    gate = threading.Event()
    blocker = engine.jobs.pool.submit(gate.wait)
    params = {"operation": "pandas.csv", "inputs": {"source": "a,b\n1,2\n"}}
    try:
        queued_id = submit(engine, params)
        assert engine.jobs.get(queued_id)["state"] == "QUEUED"
        assert engine.jobs.cancel(queued_id)["state"] == "CANCELLED"
        gate.set()
        blocker.result(timeout=2)
        assert wait_for_job(engine, queued_id)["state"] == "CANCELLED"

        running_id = submit(engine, params)
        deadline = time.monotonic() + 5
        while engine.jobs.get(running_id)["state"] == "QUEUED" and time.monotonic() < deadline:
            time.sleep(0.02)
        assert engine.jobs.get(running_id)["state"] == "RUNNING"
        assert engine.jobs.cancel(running_id)["state"] == "CANCELLED"
        time.sleep(0.1)
        job = engine.jobs.get(running_id)
        assert job["state"] == "CANCELLED"
        assert "result" not in job
        assert [event["action"] for event in engine.store.events("science")] == [
            "science.queued", "science.cancelled", "science.queued", "science.cancelled"
        ]
    finally:
        gate.set()
        engine.jobs.shutdown()


def test_recovery_keeps_recent_active_job_after_history_limit(tmp_path):
    import os
    from hypothesislab.store import Store
    root = tmp_path / '.jobs'
    root.mkdir()
    for number in range(501):
        job_id = f'{number:032x}'
        folder = root / job_id
        folder.mkdir()
        state = folder / 'state.json'
        state.write_text(json.dumps({'id': job_id, 'state': 'RUNNING' if number == 0 else 'SUCCEEDED'}))
        os.utime(state, (1000 if number == 0 else 100, 1000 if number == 0 else 100))
    jobs = ScienceJobs(Store(tmp_path))
    try:
        assert len(jobs.jobs) == 500
        assert jobs.get('0' * 32)['state'] == 'INTERRUPTED'
    finally:
        jobs.shutdown()
