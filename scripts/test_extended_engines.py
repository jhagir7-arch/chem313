#!/usr/bin/env python3
"""Exercise every allowlisted extended operation in a fresh isolated worker.

This is a bounded local runtime/reference check. It does not validate a
quantum method, identify a spectrum, or establish a docking prediction.
"""
from __future__ import annotations

from datetime import datetime, timezone
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time


ROOT = Path(__file__).resolve().parents[1]
DEVELOPMENT_WORKER = ROOT / ".engines" / "extended" / "bin" / "python"
WORKER = DEVELOPMENT_WORKER
EVIDENCE = ROOT / "evidence" / "extended-runtime.json"
RUN_CWD = ROOT
DEVELOPMENT_MODE = True
sys.path.insert(0, str(ROOT / "backend" / "src"))
from hypothesislab.extended_contracts import EXAMPLES, OPERATIONS  # noqa: E402


def call(operation: str, inputs: dict) -> dict:
    env = dict(os.environ)
    if DEVELOPMENT_MODE:
        env["PYTHONPATH"] = str(ROOT / "backend" / "src")
    else:
        env.pop("PYTHONPATH", None)
    completed = subprocess.run(
        [str(WORKER), "-m", "hypothesislab.extended_worker"],
        input=json.dumps({"operation": operation, "inputs": inputs}),
        text=True,
        capture_output=True,
        cwd=RUN_CWD,
        env=env,
        timeout=125,
    )
    try:
        body = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise AssertionError(f"{operation}: worker did not emit JSON: {completed.stdout!r}") from exc
    if completed.returncode != 0:
        raise AssertionError(f"{operation}: worker failed: {body}; stderr={completed.stderr[-1000:]!r}")
    for key in ("schema", "operation", "engine", "version", "output", "resources"):
        assert key in body, f"{operation}: missing {key}"
    assert body["schema"] == "openchem.science.result.v1"
    assert body["operation"] == operation
    assert isinstance(body["version"], str) and body["version"]
    return body


def reference_checks(results: dict[str, dict]) -> None:
    output = {operation: row["output"] for operation, row in results.items()}
    assert output["pyscf.rhf_singlepoint"]["converged"] is True
    assert math.isclose(output["pyscf.rhf_singlepoint"]["energy_hartree"], -1.1167593074, rel_tol=1e-8)
    assert math.isclose(output["tblite.gfn2_singlepoint"]["energy_hartree"], -0.9819836947, rel_tol=1e-8)
    assert output["matchms.cosine_greedy"]["matched_peak_pairs"] == 2
    assert math.isclose(output["matchms.cosine_greedy"]["cosine_score"], 0.9954954726, rel_tol=1e-8)
    prepared = output["meeko.prepare_pdbqt"]
    # Meeko writes polar hydrogens but omits nonpolar hydrogens in PDBQT.
    assert prepared["pdbqt_atom_records"] == 4 and prepared["atoms"] == 9
    assert prepared["pdbqt"].startswith("REMARK SMILES CCO\n")
    assert len(prepared["pdbqt_sha256"]) == 64


def negative_checks() -> list[dict]:
    cases = [
        ("pyscf.rhf_singlepoint", {"atomic_numbers": [1, 1, 1], "coordinates_angstrom": [[0, 0, 0], [0, 0, 0.74], [0, 0, 1.48]], "charge": 0, "basis": "sto-3g"}),
        ("matchms.cosine_greedy", {"reference_mz": [100.0], "reference_intensities": [1.0], "query_mz": [100.0, 200.0], "query_intensities": [1.0], "tolerance_da": 0.01}),
        ("meeko.prepare_pdbqt", {"smiles": "not-a-smiles"}),
        ("tblite.gfn2_singlepoint", {"atomic_numbers": [1, 1], "coordinates_angstrom": [[0, 0, 0], [0, 0, 0.74]], "charge": 0, "unexpected": 1}),
    ]
    records = []
    env = dict(os.environ)
    if DEVELOPMENT_MODE:
        env["PYTHONPATH"] = str(ROOT / "backend" / "src")
    else:
        env.pop("PYTHONPATH", None)
    for operation, inputs in cases:
        completed = subprocess.run(
            [str(WORKER), "-m", "hypothesislab.extended_worker"],
            input=json.dumps({"operation": operation, "inputs": inputs}),
            text=True, capture_output=True, cwd=RUN_CWD, env=env, timeout=125,
        )
        body = json.loads(completed.stdout)
        assert completed.returncode != 0 and body.get("status") == "FAILED", (operation, completed.returncode, body)
        records.append({"operation": operation, "returncode": completed.returncode, "error": body["error"]})
    completed = subprocess.run(
        [str(WORKER), "-m", "hypothesislab.extended_worker"],
        input=json.dumps({"operation": "tblite.gfn2_singlepoint", "inputs": EXAMPLES["tblite.gfn2_singlepoint"], "extra": 1}),
        text=True, capture_output=True, cwd=RUN_CWD, env=env, timeout=125,
    )
    body = json.loads(completed.stdout)
    assert completed.returncode != 0 and body.get("status") == "FAILED", (completed.returncode, body)
    records.append({"operation": "request-envelope", "returncode": completed.returncode, "error": body["error"]})
    return records


def frozen_worker_sha256() -> str | None:
    if DEVELOPMENT_MODE:
        return None
    with WORKER.open("rb") as worker_file:
        return hashlib.file_digest(worker_file, "sha256").hexdigest()


def main() -> int:
    global WORKER, EVIDENCE, RUN_CWD, DEVELOPMENT_MODE
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worker", type=Path, default=DEVELOPMENT_WORKER)
    parser.add_argument("--evidence", type=Path, default=EVIDENCE)
    parser.add_argument("--cwd", type=Path, default=ROOT, help="directory in which to invoke the worker")
    args = parser.parse_args()
    WORKER = args.worker
    EVIDENCE = args.evidence.resolve()
    RUN_CWD = args.cwd.resolve()
    if not WORKER.is_file():
        raise SystemExit(f"missing extended worker: {WORKER}")
    DEVELOPMENT_MODE = WORKER.samefile(DEVELOPMENT_WORKER)
    started = time.monotonic()
    results: dict[str, dict] = {}
    failures: list[str] = []
    for operation, inputs in EXAMPLES.items():
        try:
            results[operation] = call(operation, inputs)
        except Exception as exc:
            failures.append(f"{operation}: {type(exc).__name__}: {exc}")
    negative = []
    if not failures:
        try:
            reference_checks(results)
            negative = negative_checks()
        except Exception as exc:
            failures.append(f"reference/negative checks: {type(exc).__name__}: {exc}")
    evidence = {
        "schema": "openchem.extended-runtime.v1",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "worker_python": str(WORKER),
        "worker_sha256": frozen_worker_sha256(),
        "invocation_cwd": str(RUN_CWD),
        "pythonpath_used": DEVELOPMENT_MODE,
        "operation_count": len(OPERATIONS),
        "results": [results[key] for key in OPERATIONS if key in results],
        "negative_checks": negative,
        "failures": failures,
        "wall_seconds": time.monotonic() - started,
    }
    EVIDENCE.parent.mkdir(parents=True, exist_ok=True)
    EVIDENCE.write_text(json.dumps(evidence, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if failures or len(results) != len(OPERATIONS):
        print("extended runtime verification failed; see " + str(EVIDENCE), file=sys.stderr)
        for failure in failures:
            print(failure, file=sys.stderr)
        return 1
    print(f"extended runtime verification passed: {len(results)} operations; evidence: {EVIDENCE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
