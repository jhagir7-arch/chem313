#!/usr/bin/env python3
"""Exercise every allowlisted science operation in a fresh isolated worker.

This is a runtime smoke/reference check.  It does not claim experimental or
method validation beyond the explicitly checked numerical identities.
"""
from __future__ import annotations

import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
WORKER = ROOT / ".engines" / "science" / "bin" / "python"
EVIDENCE = ROOT / "evidence" / "science-runtime.json"
sys.path.insert(0, str(ROOT / "backend" / "src"))
from hypothesislab.science_contracts import EXAMPLES, OPERATIONS  # noqa: E402


def call(operation: str, inputs: dict) -> dict:
    env = {**os.environ, "PYTHONPATH": str(ROOT / "backend" / "src")}
    completed = subprocess.run(
        [str(WORKER), "-m", "hypothesislab.science_worker"],
        input=json.dumps({"operation": operation, "inputs": inputs}),
        text=True, capture_output=True, cwd=ROOT, env=env, timeout=125,
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
    resources = body["resources"]
    assert resources["wall_seconds"] >= 0 and resources["user_cpu_seconds"] >= 0
    assert isinstance(resources["max_rss_bytes"], int) and resources["max_rss_bytes"] > 0
    return body


def close(actual: float, expected: float, tolerance: float = 1e-8) -> None:
    assert math.isclose(actual, expected, rel_tol=tolerance, abs_tol=tolerance), (actual, expected)


def reference_checks(results: dict[str, dict]) -> None:
    out = {operation: row["output"] for operation, row in results.items()}
    close(out["numpy.summary"]["mean"], 2.0)
    for operation in ("scipy.line", "lmfit.line"):
        close(out[operation]["slope"], 2.0)
        close(out[operation]["intercept"], 1.0)
    assert out["gemmi.cif"]["sites"] == 2
    assert out["spglib.symmetry"]["number"] == 225
    for operation in ("pymatgen.composition", "pymatgencore.composition"):
        assert out[operation]["reduced_formula"] == "NaCl"
    close(out["pint.convert"]["value"], 1.0)
    assert out["pandas.csv"]["rows"] == out["polars.csv"]["rows"] == 3
    peak = max(range(4), key=lambda i: abs(out["nmrglue.fft"]["real"][i]) + abs(out["nmrglue.fft"]["imag"][i]))
    # nmrglue.proc_base.fft already returns an fft-shifted spectrum; frequency
    # axis must therefore use fftshift(fftfreq), with the +250 Hz tone at index 3.
    assert peak == 3 and out["nmrglue.fft"]["frequency_Hz"][peak] == 250.0
    close(out["pyteomics.mass"]["monoisotopic_mass_u"], 18.010564684, 1e-10)
    assert out["biopython.dna"]["reverse_complement"] == "GCAT"
    close(out["biopython.dna"]["gc_fraction"], 0.5)
    assert out["optuna.quadratic"]["trials"] == 16
    before, after = out["cantera.equilibrium"]["element_mass_fractions_before"], out["cantera.equilibrium"]["element_mass_fractions_after"]
    for element, fraction in before.items():
        close(after[element], fraction, 1e-8)
    # E = 1/2 k (r-r0)^2 = 1/2 * 100 * 0.1^2 kJ/mol.
    close(out["openmm.harmonic"]["energy_kJ_mol"], 0.5)
    assert out["mdtraj.distance"]["distances_nm"] == [1.0, 2.0]
    close(out["mdanalysis.geometry"]["radius_of_gyration_nm"], 1.0)
    assert out["rocrate.manifest"]["manifest"]["@graph"][0]["name"] == EXAMPLES["rocrate.manifest"]["name"]
    assert out["ord.reaction"]["reaction"]["inputs"]["reactant"]["components"][0]["identifiers"][0]["value"] == "CCO"


def negative_checks() -> list[dict]:
    cases = [
        ("pint.convert", {"value": 1.0, "from_unit": "meter", "to_unit": "second"}),
        ("pandas.csv", {"source": "a,A\n1,2\n"}),
        ("polars.csv", {"source": "a,b\n1,2\n3\n"}),
        ("numpy.summary", {"values": [1.0, float("nan")], "unit": "a.u."}),
    ]
    records = []
    env = {**os.environ, "PYTHONPATH": str(ROOT / "backend" / "src")}
    for operation, inputs in cases:
        completed = subprocess.run(
            [str(WORKER), "-m", "hypothesislab.science_worker"],
            input=json.dumps({"operation": operation, "inputs": inputs}), text=True,
            capture_output=True, cwd=ROOT, env=env, timeout=125,
        )
        body = json.loads(completed.stdout)
        assert completed.returncode != 0 and body.get("status") == "FAILED", (operation, completed.returncode, body)
        records.append({"operation": operation, "returncode": completed.returncode, "error": body["error"]})
    return records


def main() -> int:
    if not WORKER.is_file():
        raise SystemExit(f"missing science worker: {WORKER}")
    started = time.monotonic()
    results: dict[str, dict] = {}
    failures: list[str] = []
    for operation, inputs in EXAMPLES.items():
        try:
            results[operation] = call(operation, inputs)
        except Exception as exc:  # Continue to capture all operation outcomes.
            failures.append(f"{operation}: {type(exc).__name__}: {exc}")
    negative = []
    if not failures:
        try:
            reference_checks(results)
            negative = negative_checks()
        except Exception as exc:
            failures.append(f"reference/negative checks: {type(exc).__name__}: {exc}")
    evidence = {
        "schema": "openchem.science-runtime.v1",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "worker_python": str(WORKER),
        "operation_count": len(OPERATIONS),
        "results": [results[key] for key in OPERATIONS if key in results],
        "negative_checks": negative,
        "failures": failures,
        "wall_seconds": time.monotonic() - started,
    }
    EVIDENCE.parent.mkdir(parents=True, exist_ok=True)
    EVIDENCE.write_text(json.dumps(evidence, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if failures or len(results) != len(OPERATIONS):
        print("science runtime verification failed; see " + str(EVIDENCE), file=sys.stderr)
        for failure in failures:
            print(failure, file=sys.stderr)
        return 1
    print(f"science runtime verification passed: {len(results)} operations; evidence: {EVIDENCE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
