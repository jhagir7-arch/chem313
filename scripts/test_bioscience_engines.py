#!/usr/bin/env python3
"""Reference checks for bounded bioscience workers, direct or frozen."""
from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend" / "src"))
from hypothesislab import bioscience_contracts as contracts  # noqa: E402


def call(command: list[str], request: dict, cwd: Path) -> tuple[int, dict, str]:
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    completed = subprocess.run(
        command,
        input=json.dumps(request),
        text=True,
        capture_output=True,
        cwd=cwd,
        env=env,
        timeout=130,
        check=False,
    )
    try:
        response = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise AssertionError(f"worker did not return JSON: {completed.stdout!r}; stderr={completed.stderr!r}") from exc
    return completed.returncode, response, completed.stderr


def test_worker(command: list[str], cwd: Path) -> dict:
    outcomes: list[dict] = []
    enzyme_request = {"operation": "pyenzyme.document", "inputs": contracts.EXAMPLES["pyenzyme.document"]}
    code, result, stderr = call(command, enzyme_request, cwd)
    assert code == 0 and result["engine"] == "PyEnzyme", (code, result, stderr)
    assert result["output"] == {"name": "OpenChem bioscience example", "level": 3, "version": 2, "method": "EnzymeMLDocument"}
    outcomes.append({"operation": enzyme_request["operation"], "engine": result["engine"], "version": result["version"], "status": "passed"})

    decay_request = {"operation": "pysb.first_order_decay", "inputs": contracts.EXAMPLES["pysb.first_order_decay"]}
    code, result, stderr = call(command, decay_request, cwd)
    assert code == 0 and result["engine"] == "PySB", (code, result, stderr)
    output = result["output"]
    assert isinstance(result["version"], str)
    assert isinstance(output["dependencies"]["bionetgen"], str)
    for actual, t in zip(output["A"], decay_request["inputs"]["times"]):
        expected = math.exp(-t)
        assert abs(actual - expected) <= 1e-5, (actual, expected)
    outcomes.append({"operation": decay_request["operation"], "engine": result["engine"], "version": result["version"], "status": "passed", "reference": "A(t)=A0*exp(-k*t), tolerance=1e-5"})

    malformed = [
        {"operation": "pysb.first_order_decay", "inputs": {**decay_request["inputs"], "rate_per_time": 0}},
        {"operation": "pysb.first_order_decay", "inputs": {**decay_request["inputs"], "times": [1.0, 0.0]}},
        {"operation": "pysb.first_order_decay", "inputs": {**decay_request["inputs"], "rate_unit": "s"}},
        {"operation": "pyenzyme.document", "inputs": {"name": "bad\nname"}},
        {"operation": "pyenzyme.document", "inputs": {"name": "ok", "path": "/tmp/nope"}},
    ]
    rejected = []
    for request in malformed:
        code, result, _stderr = call(command, request, cwd)
        assert code == 2 and result.get("status") == "FAILED", (request, code, result)
        rejected.append({"operation": request["operation"], "error": result["error"]})
    return {"results": outcomes, "rejected": rejected}


def solver_runtime(frozen_worker: Path | None) -> dict:
    if frozen_worker:
        bngpath = frozen_worker.resolve().parent / "_internal" / "bionetgen" / "bng-mac"
    else:
        bngpath = ROOT / ".engines" / "probe" / "lib" / "python3.12" / "site-packages" / "bionetgen" / "bng-mac"
    perl = subprocess.run(["/usr/bin/perl", "-e", "print $^V"], capture_output=True, text=True, check=True)
    assert (bngpath / "BNG2.pl").is_file(), bngpath
    return {
        "bngpath": str(bngpath),
        "bng2_pl_present": True,
        "system_perl": {"path": "/usr/bin/perl", "version": perl.stdout},
        "native_helpers": ["bin/NFsim", "bin/run_network"],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--frozen-worker", type=Path)
    parser.add_argument("--cwd", type=Path, required=True, help="private empty working directory")
    parser.add_argument("--evidence", type=Path, required=True)
    args = parser.parse_args()
    if not args.cwd.is_dir():
        raise SystemExit("--cwd must be an existing private directory")
    if args.frozen_worker:
        command = [str(args.frozen_worker.resolve())]
        kind = "frozen"
    else:
        configured_python = os.environ.get("OPENCHEM_BIOSCIENCE_PYTHON")
        canonical_python = ROOT / ".engines" / "bioscience" / "bin" / "python"
        probe_python = ROOT / ".engines" / "probe" / "bin" / "python"
        worker_python = Path(configured_python) if configured_python else (canonical_python if canonical_python.is_file() else probe_python)
        command = [str(worker_python), str(ROOT / "backend" / "src" / "hypothesislab" / "bioscience_worker.py")]
        kind = "direct"
    checked = test_worker(command, args.cwd.resolve())
    evidence = {
        "schema": "openchem.bioscience-runtime.v1",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "worker_kind": kind,
        "command": command,
        "private_cwd": str(args.cwd.resolve()),
        "pythonpath_removed": True,
        "solver_runtime": solver_runtime(args.frozen_worker),
        **checked,
    }
    args.evidence.parent.mkdir(parents=True, exist_ok=True)
    args.evidence.write_text(json.dumps(evidence, indent=2) + "\n")
    print(json.dumps(evidence, indent=2))


if __name__ == "__main__":
    main()
