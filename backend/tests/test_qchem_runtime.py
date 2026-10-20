"""Lifecycle tests use a simulated executable; they do not exercise Q-Chem chemistry."""
import json
import os
import time
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from hypothesislab import api
from hypothesislab.qchem_api import register
from hypothesislab.qchem_runtime import QchemRuntime, prepare_input, render_input
from hypothesislab.store import Store
from hypothesislab.validation import InputError
from hypothesislab.conformers import molecule_conformer


WATER = [
    {"element": "O", "x": 0.0, "y": 0.0, "z": 0.0},
    {"element": "H", "x": 0.0, "y": 0.0, "z": 0.96},
    {"element": "H", "x": 0.90, "y": 0.0, "z": -0.24},
]


def same_formula_ether_atoms():
    geometry = molecule_conformer({"smiles": "COC"})
    return [{"element": {1: "H", 6: "C", 8: "O"}[atomic_number], "x": point[0], "y": point[1], "z": point[2]}
            for atomic_number, point in zip(geometry["atomic_numbers"], geometry["coordinates"])]


def simulated_installation(tmp_path, body):
    root = tmp_path / "simulated-qchem"
    (root / "bin").mkdir(parents=True)
    (root / "qcaux").mkdir()
    binary = root / "bin" / "qchem"
    binary.write_text("#!/bin/sh\n" + body)
    binary.chmod(0o700)
    return root


def test_renderer_is_fixed_neutral_singlet_and_rejects_unreviewed_composition():
    text = render_input("water", WATER)
    assert "$molecule\n0 1\n" in text
    assert text == "$molecule\n0 1\nO 0.00000000 0.00000000 0.00000000\nH 0.00000000 0.00000000 0.96000000\nH 0.90000000 0.00000000 -0.24000000\n$end\n\n$rem\nJOBTYPE sp\nMETHOD hf\nBASIS def2-SVP\n$end\n"
    with pytest.raises(InputError, match="composition"):
        render_input("water", [*WATER[:-1], {"element": "C", "x": 0, "y": 0, "z": 0}])


def test_preparation_returns_a_coordinate_identity_receipt_and_blocks_nonmatching_coordinates():
    receipt = prepare_input("water", WATER)
    assert receipt["identity_check"]["status"] == "match"
    assert receipt["identity_check"]["expected_inchikey"] == receipt["identity_check"]["observed_inchikey"]
    assert receipt["input_text"] == render_input("water", WATER)
    with pytest.raises(InputError, match="different molecule"):
        prepare_input("ethanol", same_formula_ether_atoms())


def test_simulated_process_requires_real_qchem_success_markers_and_persists_authoritative_record(tmp_path):
    installation = simulated_installation(tmp_path, "cat > \"$4\" <<'EOF'\nSCF converged\nTotal energy in the final basis set = -75.123\nThank you very much for using Q-Chem\nEOF\nexit 0\n")
    runtime = QchemRuntime(Store(tmp_path / "data"), installation, timeout_seconds=2)
    job = runtime.start("water", "water", WATER, True)
    finished = runtime.wait(job["id"], 3)
    assert finished["state"] == "SUCCEEDED"
    assert finished["result"] == {"energy_hartree": -75.123, "converged": True, "normal_termination": True}
    assert finished["molecule"] == "water" and finished["atom_count"] == 3
    assert finished["method"] == "HF" and finished["basis"] == "def2-SVP"
    assert "$molecule" in finished["input_text"] and "Thank you" in finished["output_text"]
    assert len(finished["artifacts"]) == 3
    assert [event["action"] for event in runtime.store.events("water")] == ["qchem.run_started", "qchem.run_finished"]


def test_license_or_missing_convergence_cannot_be_reported_successful(tmp_path):
    installation = simulated_installation(tmp_path, "cat > \"$4\" <<'EOF'\nQ-Chem license error\nTotal energy in the final basis set = -1.0\nThank you very much for using Q-Chem\nEOF\nexit 0\n")
    runtime = QchemRuntime(Store(tmp_path / "data"), installation, timeout_seconds=2)
    final = runtime.wait(runtime.start("water", "water", WATER, True)["id"], 3)
    assert final["state"] == "FAILED"
    assert final["result"]["energy_hartree"] is None
    assert "license" in final["detail"].lower()


def test_license_header_is_not_a_failure_and_environment_contains_qchem_requirements(tmp_path):
    installation = simulated_installation(tmp_path, "test \"$QC\" = \"$(cd \"$(dirname \"$0\")/..\" && pwd)\" || exit 11\ntest \"$QCAUX\" = \"$QC/qcaux\" || exit 12\ntest -n \"$QCSCRATCH\" && test -n \"$HOME\" || exit 13\ncat > \"$4\" <<'EOF'\nLicense information loaded\nSCF converged\nTotal energy in the final basis set = -75.0\nThank you very much for using Q-Chem\nEOF\n")
    runtime = QchemRuntime(Store(tmp_path / "data"), installation, timeout_seconds=2)
    final = runtime.wait(runtime.start("water", "water", WATER, True)["id"], 3)
    assert final["state"] == "SUCCEEDED"


def test_simulated_timeout_cancel_overflow_and_recovery_are_terminal_and_never_replayed(tmp_path):
    sleeper = simulated_installation(tmp_path, "sleep 3\n")
    timeout = QchemRuntime(Store(tmp_path / "timeout"), sleeper, timeout_seconds=1)
    assert timeout.wait(timeout.start("water", "water", WATER, True)["id"], 3)["state"] == "TIMED_OUT"
    cancel = QchemRuntime(Store(tmp_path / "cancel"), sleeper, timeout_seconds=5)
    job = cancel.start("water", "water", WATER, True)
    assert cancel.cancel(job["id"])["state"] in {"QUEUED", "RUNNING"}
    assert cancel.wait(job["id"], 3)["state"] == "CANCELLED"
    overflow_installation = simulated_installation(tmp_path / "overflow", "head -c 2048 /dev/zero > \"$4\"\n")
    overflow = QchemRuntime(Store(tmp_path / "overflow-data"), overflow_installation, timeout_seconds=2, max_output_bytes=1024)
    assert overflow.wait(overflow.start("water", "water", WATER, True)["id"], 3)["state"] == "FAILED"
    runtime = QchemRuntime(Store(tmp_path / "recover"), sleeper, timeout_seconds=5)
    pending = {"id": "a" * 32, "project": "water", "state": "RUNNING", "input_text": "reviewed"}
    (runtime._journal / ("a" * 32 + ".json")).write_text(json.dumps(pending))
    recovered = QchemRuntime(runtime.store, sleeper, timeout_seconds=5)
    assert recovered.status("a" * 32)["state"] == "INTERRUPTED"


def test_silent_process_times_out_without_a_result(tmp_path):
    runtime = QchemRuntime(Store(tmp_path / "data"), simulated_installation(tmp_path, "sleep 3\n"), timeout_seconds=1)
    final = runtime.wait(runtime.start("water", "water", WATER, True)["id"], 3)
    assert final["state"] == "TIMED_OUT"
    assert final["result"]["energy_hartree"] is None
    assert final["output_text"] == ""


def test_cancel_terminates_the_qchem_process_group(tmp_path):
    installation = simulated_installation(tmp_path, "sleep 30 &\necho $! > \"$QC/child.pid\"\nwait\n")
    runtime = QchemRuntime(Store(tmp_path / "data"), installation, timeout_seconds=10)
    job = runtime.start("water", "water", WATER, True)
    pid_path = installation / "child.pid"
    for _ in range(30):
        if pid_path.exists():
            break
        time.sleep(.05)
    assert pid_path.exists()
    child = int(pid_path.read_text())
    runtime.cancel(job["id"])
    assert runtime.wait(job["id"], 4)["state"] == "CANCELLED"
    with pytest.raises(ProcessLookupError):
        os.kill(child, 0)


def test_output_file_growth_is_bounded_before_a_success_can_be_recorded(tmp_path):
    installation = simulated_installation(tmp_path, "head -c 2048 /dev/zero > \"$4\"\nsleep 2\n")
    runtime = QchemRuntime(Store(tmp_path / "data"), installation, timeout_seconds=5, max_output_bytes=1024)
    final = runtime.wait(runtime.start("water", "water", WATER, True)["id"], 3)
    assert final["state"] == "FAILED"
    assert "1 MB limit" in final["detail"]
    assert final["result"]["energy_hartree"] is None


def test_exit_zero_energy_without_all_required_markers_is_not_success(tmp_path):
    installation = simulated_installation(tmp_path, "cat > \"$4\" <<'EOF'\nTotal energy in the final basis set = -5.0\nEOF\nexit 0\n")
    runtime = QchemRuntime(Store(tmp_path / "data"), installation, timeout_seconds=2)
    final = runtime.wait(runtime.start("water", "water", WATER, True)["id"], 3)
    assert final["state"] == "FAILED"
    assert final["result"] == {"energy_hartree": None, "converged": False, "normal_termination": False}
    assert "SCF convergence" in final["detail"]


def test_stdout_only_license_failure_is_saved_as_a_diagnostic(tmp_path):
    installation = simulated_installation(tmp_path, "echo 'Q-Chem license error: cannot locate license'\nexit 9\n")
    runtime = QchemRuntime(Store(tmp_path / "data"), installation, timeout_seconds=2)
    final = runtime.wait(runtime.start("water", "water", WATER, True)["id"], 3)
    assert final["state"] == "FAILED"
    assert "license error" in final["output_text"].lower()
    assert "license failure" in final["detail"].lower()


def test_recovery_keeps_terminal_jobs_and_marks_active_jobs_interrupted_without_replay(tmp_path):
    installation = simulated_installation(tmp_path, "cat > \"$4\" <<'EOF'\nSCF converged\nTotal energy in the final basis set = -1.0\nThank you very much for using Q-Chem\nEOF\n")
    store = Store(tmp_path / "data")
    runtime = QchemRuntime(store, installation, timeout_seconds=2)
    finished = runtime.wait(runtime.start("water", "water", WATER, True)["id"], 3)
    pending = {"id": "b" * 32, "project": "water", "state": "RUNNING", "created_utc": 1, "input_text": "reviewed"}
    (runtime._journal / ("b" * 32 + ".json")).write_text(json.dumps(pending))
    resumed = QchemRuntime(store, installation, timeout_seconds=2)
    assert resumed.status(finished["id"])["state"] == "SUCCEEDED"
    assert resumed.status("b" * 32)["state"] == "INTERRUPTED"
    assert resumed._active is None


def test_history_is_project_scoped_and_newest_first(tmp_path):
    installation = simulated_installation(tmp_path, "exit 0\n")
    runtime = QchemRuntime(Store(tmp_path / "data"), installation)
    runtime._jobs = {
        "1" * 32: {"id": "1" * 32, "project": "water", "state": "FAILED", "created_utc": 1, "input_text": "old"},
        "2" * 32: {"id": "2" * 32, "project": "methane", "state": "FAILED", "created_utc": 3, "input_text": "other"},
        "3" * 32: {"id": "3" * 32, "project": "water", "state": "SUCCEEDED", "created_utc": 2, "input_text": "new"},
    }
    assert [job["id"] for job in runtime.jobs("water")] == ["3" * 32, "1" * 32]


def test_configuration_and_api_are_authenticated_and_require_explicit_approval(tmp_path):
    app = FastAPI()
    facade = SimpleNamespace(ROOT=tmp_path, engine=SimpleNamespace(store=Store(tmp_path)), SESSION_HEADER=api.SESSION_HEADER, require_session=api.require_session)
    register(app, facade)
    headers = {"X-HypothesisLab-Session": api.SESSION}
    installation = simulated_installation(tmp_path, "exit 9\n")
    with TestClient(app) as client:
        assert client.get("/api/qchem/status").status_code == 403
        assert client.get("/api/qchem/status", headers=headers).json()["status"] == "NOT_CONFIGURED"
        assert client.post("/api/qchem/configure", headers=headers, json={"installation": str(installation)}).json()["status"] == "CONFIGURED"
        assert json.loads((tmp_path / "qchem.json").read_text())["installation"] == str(installation)
        refused = client.post("/api/qchem/jobs", headers=headers, json={"project": "water", "molecule": "water", "atoms": WATER, "approved": False})
        assert refused.status_code == 422 and "approved" in refused.json()["detail"]
        assert client.post("/api/qchem/jobs/missing/cancel", headers=headers, json={"approved": "true"}).status_code == 422
        invalid = client.post("/api/qchem/jobs", headers=headers, json={"project": "water", "molecule": "water", "atoms": [{**WATER[0], "x": True}, *WATER[1:]], "approved": True})
        assert invalid.status_code == 422
        assert client.get("/api/qchem/jobs?project=water", headers=headers).json() == {"jobs": []}


def test_preparation_api_requires_session_and_returns_only_checked_input(tmp_path):
    app = FastAPI()
    facade = SimpleNamespace(ROOT=tmp_path, engine=SimpleNamespace(store=Store(tmp_path)), SESSION_HEADER=api.SESSION_HEADER, require_session=api.require_session)
    register(app, facade)
    headers = {"X-HypothesisLab-Session": api.SESSION}
    with TestClient(app) as client:
        assert client.post("/api/qchem/prepare", json={"molecule": "water", "atoms": WATER}).status_code == 403
        checked = client.post("/api/qchem/prepare", headers=headers, json={"molecule": "water", "atoms": WATER})
        assert checked.status_code == 200 and checked.json()["identity_check"]["status"] == "match"
        assert client.post("/api/qchem/prepare", headers=headers, json={"molecule": "ethanol", "atoms": same_formula_ether_atoms()}).status_code == 422


def test_qchem_iteration_convergence_marker_and_normal_license_notice():
    from hypothesislab.qchem_runtime import _parse_result
    output = b"Licensed to researcher\n7 -76.123 4.67e-09 Convergence criterion met\nTotal energy in the final basis set = -76.123\nThank you very much for using Q-Chem\n"
    result = _parse_result(output, 0)
    assert result['successful'] is True
    assert result['energy_hartree'] == -76.123


def test_license_checkout_failure_reports_the_actionable_license_problem():
    from hypothesislab.qchem_runtime import _parse_result
    result = _parse_result(b"License checkout failed", 2)
    assert result["successful"] is False
    assert result["energy_hartree"] is None
    assert "license failure" in result["detail"]
