#!/usr/bin/env python3
"""Record local runtime feasibility for the complete source catalog.

Only import availability and executable discovery are checked. This script
never installs, executes a third-party engine, downloads models, or claims
source-pin equivalence with wheels in local virtual environments.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CATALOG = ROOT / "sources" / "registry" / "ENGINE_CATALOG.json"
PROBE = """import importlib, importlib.metadata as m, json, sys
name=sys.argv[1]
try:
    importlib.import_module(name)
    root=name.split('.')[0]
    candidates={'Bio':'biopython','MDAnalysis':'MDAnalysis','ord_schema':'ord-schema','rocrate':'rocrate'}
    dist=candidates.get(root,root)
    try: version=m.version(dist)
    except m.PackageNotFoundError: version=None
    print(json.dumps({'status':'IMPORTABLE','version':version}))
except Exception as exc:
    print(json.dumps({'status':'UNAVAILABLE','error':f'{type(exc).__name__}: {exc}'}))
"""

# These are PyPI distribution names, not replacements for catalog source pins.
# The list is limited to the catalog's Python modules absent from the original
# science/extended environments; dry runs use wheels only and mutate nothing.
WHEEL_SPECS = {
    "Psi4": "psi4",
    "OpenFFToolkit": "openff-toolkit",
    "OpenFFInterchange": "openff-interchange",
    "Chemprop": "chemprop",
    "DeepChem": "deepchem",
    "TorchANI": "torchani",
    "MACE": "mace-torch",
    "SchNetPack": "schnetpack",
    "TorchMDNet": "torchmd-net",
    "BoTorch": "botorch",
    "BayBE": "baybe",
    "matchms": "matchms",
    "RMGPy": "rmgpy",
    "PyEnzyme": "pyenzyme",
    "AutoDockVina": "vina",
    "Meeko": "meeko",
    "MultiQC": "multiqc",
    "ChemGraph": "chemgraph",
    "PySB": "pysb",
}


def import_probe(python: Path, module: str) -> dict:
    if not python.is_file():
        return {"status": "ENVIRONMENT_MISSING", "error": f"Python not found: {python}"}
    try:
        p = subprocess.run([str(python), "-c", PROBE, module], capture_output=True, text=True, timeout=20, check=False)
    except subprocess.TimeoutExpired:
        return {"status": "UNAVAILABLE", "error": "TimeoutExpired: import exceeded 20 seconds"}
    try:
        result = json.loads(p.stdout)
    except json.JSONDecodeError:
        result = {"status": "UNAVAILABLE", "error": f"probe exited {p.returncode}; stdout was not JSON"}
    result["returncode"] = p.returncode
    return result


def executable_probe(executable: str) -> dict:
    resolved = shutil.which(executable)
    if resolved:
        return {"status": "FOUND_ON_PATH", "path": resolved}
    return {"status": "UNAVAILABLE", "error": f"FileNotFoundError: executable '{executable}' not on PATH"}


def wheel_dry_run(python: Path, spec: str) -> dict:
    if not python.is_file():
        return {"status": "NOT_RUN", "error": f"Python not found: {python}"}
    try:
        completed = subprocess.run(
            ["uv", "pip", "install", "--python", str(python), "--dry-run", "--only-binary=:all:", spec],
            capture_output=True, text=True, timeout=120, check=False,
        )
    except subprocess.TimeoutExpired:
        return {"status": "UNRESOLVED", "error": "TimeoutExpired: wheel dry run exceeded 120 seconds"}
    text = (completed.stdout + completed.stderr).strip()
    detail = "\n".join(text.splitlines()[-8:])
    return {
        "status": "WHEEL_RESOLVABLE" if completed.returncode == 0 else "NO_BINARY_WHEEL_OR_UNRESOLVABLE",
        "returncode": completed.returncode,
        "detail": detail,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    parser.add_argument("--science-python", type=Path, default=ROOT / ".engines/science/bin/python")
    parser.add_argument("--extended-python", type=Path, default=ROOT / ".engines/extended/bin/python")
    parser.add_argument("--wheel-dry-runs", action="store_true", help="run wheel-only, non-mutating uv resolver checks for each absent catalog module")
    args = parser.parse_args()
    catalog = json.loads(args.catalog.read_text(encoding="utf-8"))
    if catalog.get("schema") != "openchem.engine.source_catalog.v1":
        raise ValueError("unexpected catalog schema")
    results = []
    for entry in catalog["engines"]:
        module, executable = entry.get("python_module"), entry.get("executable")
        record = {key: entry.get(key) for key in ("name", "tier", "repo", "pinned_commit_sha", "python_module", "executable", "license_reported_unverified", "download_includes_dependencies")}
        if module:
            record["science_env"] = import_probe(args.science_python, module)
            record["extended_env"] = import_probe(args.extended_python, module)
            if entry["name"] in {"PySCF", "tblite", "matchms", "Meeko"} and record["extended_env"]["status"] == "IMPORTABLE":
                record["runtime_feasibility"] = "RUNNABLE_EXERCISED_EXTENDED_WORKER"
            elif record["science_env"]["status"] == "IMPORTABLE":
                record["runtime_feasibility"] = "AVAILABLE_IN_EXISTING_SCIENCE_ENV"
            elif record["extended_env"]["status"] == "IMPORTABLE":
                record["runtime_feasibility"] = "IMPORTABLE_NOT_WIRED"
            else:
                record["runtime_feasibility"] = "NOT_INSTALLED"
            if args.wheel_dry_runs and entry["name"] in WHEEL_SPECS:
                record["wheel_dry_run"] = wheel_dry_run(args.extended_python, WHEEL_SPECS[entry["name"]])
        elif executable:
            record["executable_probe"] = executable_probe(executable)
            record["runtime_feasibility"] = "EXECUTABLE_ON_PATH" if record["executable_probe"]["status"] == "FOUND_ON_PATH" else "EXECUTABLE_NOT_AVAILABLE"
        else:
            record["runtime_feasibility"] = "NO_LOCAL_PYTHON_OR_EXECUTABLE_INTERFACE_DECLARED"
            record["evidence"] = "Catalog has neither python_module nor executable; no runtime install was attempted."
        results.append(record)
    output = {
        "schema": "openchem.extended_engine_feasibility.v1",
        "time_utc": datetime.now(timezone.utc).isoformat(),
        "host": {"platform": sys.platform, "machine": __import__("platform").machine()},
        "catalog": str(args.catalog),
        "probe_boundary": "Imports and PATH discovery only; no source archive was extracted, installed, or executed.",
        "results": results,
    }
    print(json.dumps(output, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
