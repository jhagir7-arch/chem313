#!/usr/bin/env python3
"""Black-box v2 engine smoke test. Usage: python test_v2_frozen_engine.py ENGINE REPORT.json.

Uses stdlib for transport and integrity checks; optional host RDKit independently recalculates
energies from saved geometries. A missing host RDKit is explicitly reported as a skipped check.
"""
import hashlib
import json
import math
import os
from pathlib import Path
import queue
import shutil
import subprocess
import sys
import tempfile
import threading
import urllib.error
import urllib.request
from urllib.parse import urlsplit

TOLERANCE = 1e-6


def main(engine, report_path):
    report = {"status": "FAIL", "engine": str(engine), "checks": [], "calculations": [],
              "independent_energy": {"status": "SKIPPED", "reason": "Host RDKit unavailable", "absolute_tolerance_kcal_mol": TOLERANCE}}
    try:
        from rdkit import Chem, rdBase
        from rdkit.Chem import AllChem
        report["independent_energy"] = {"status": "PASS", "rdkit_version": rdBase.rdkitVersion,
                                        "absolute_tolerance_kcal_mol": TOLERANCE}
    except ImportError:
        Chem = AllChem = None
    process = None
    temp = tempfile.mkdtemp(prefix="chem313-v2-smoke-")
    try:
        root = Path(temp)
        home, data = root / "home", root / "data"
        home.mkdir(); data.mkdir()
        env = os.environ.copy()
        env.update({"HOME": str(home), "USERPROFILE": str(home), "XDG_DATA_HOME": str(home / ".local/share")})
        for key in ("PYTHONPATH", "PYTHONHOME", "HYPOTHESISLAB_DATA"):
            env.pop(key, None)
        with (root / "engine.log").open("wb") as log:
            process = subprocess.Popen([str(engine), "--data", str(data), "--port", "0", "--parent-pid", str(os.getpid())],
                                       cwd=root, env=env, stdout=subprocess.PIPE, stderr=log)
            output = queue.Queue(maxsize=1)
            def read_banner():
                try:
                    output.put(process.stdout.readline(8192))
                except Exception as exc:
                    output.put(exc)
            threading.Thread(target=read_banner, daemon=True).start()
            try:
                line = output.get(timeout=60)
            except queue.Empty:
                raise RuntimeError("Engine startup timed out after 60 seconds")
            if isinstance(line, Exception):
                raise RuntimeError("Engine banner read failed") from line
            if not line.endswith(b"\n"):
                raise RuntimeError("Missing or incomplete engine banner")
            base = json.loads(line)["url"]
            parsed = urlsplit(base)
            if parsed.scheme != "http" or parsed.hostname != "127.0.0.1" or not parsed.port or parsed.path not in ("", "/") or parsed.query or parsed.fragment:
                raise RuntimeError("Unexpected engine endpoint")
            base = base.rstrip("/")
            token = None
            def api(path, payload=None):
                headers = {"Content-Type": "application/json"}
                if token:
                    headers["X-HypothesisLab-Session"] = token
                req = urllib.request.Request(base + path, data=json.dumps(payload).encode() if payload is not None else None, headers=headers)
                with urllib.request.urlopen(req, timeout=60) as response:
                    return json.load(response)
            token = api("/api/session")["session_token"]
            catalog = api("/api/catalog")
            if catalog["schema"] != "chem313.catalog.v1":
                raise AssertionError("Unexpected catalog schema")
            report["checks"].append("Session handshake and catalog")
            for name, smiles, field in [("water", "O", "MMFF94"), ("methane", "C", "MMFF94"),
                                        ("ethanol", "CCO", "MMFF94"), ("phenol", "Oc1ccccc1", "UFF")]:
                request = {"action": "molecule.relax_geometry", "project": "smoke", "params": {"smiles": smiles, "force_field": field, "seed": 42}}
                receipt = api("/api/preview", request)
                reply = api("/api/execute", {**request, "approved": True, "preview_token": receipt["preview_token"]})
                result, artifacts = reply["result"], reply["artifacts"]
                if reply["status"] != "EXECUTED" or result["identity_status"] != "MATCH" or len(artifacts) != 3:
                    raise AssertionError(f"Invalid calculation response for {name}")
                energies = []
                for artifact in artifacts:
                    rel = Path(artifact["relative_path"])
                    path = (data / rel).resolve()
                    if not path.is_relative_to(data.resolve()):
                        raise AssertionError("Artifact path escapes data directory")
                    blob = path.read_bytes()
                    digest = hashlib.sha256(blob).hexdigest()
                    if digest != artifact["sha256"] or digest != path.stem or len(blob) != artifact["bytes"]:
                        raise AssertionError(f"Artifact integrity mismatch: {rel}")
                    if Chem is not None and path.suffix == ".sdf":
                        mol = Chem.MolFromMolBlock(blob.decode().split("$$$$")[0], removeHs=False)
                        if mol is None or Chem.MolToInchiKey(mol) != result["inchikey"]:
                            raise AssertionError(f"Saved geometry identity mismatch: {name}")
                        ff = (AllChem.UFFGetMoleculeForceField(mol) if field == "UFF" else
                              AllChem.MMFFGetMoleculeForceField(mol, AllChem.MMFFGetMoleculeProperties(mol, mmffVariant="MMFF94")))
                        energies.append(ff.CalcEnergy())
                expected = [result["initial_energy_kcal_mol"], result["final_energy_kcal_mol"]]
                if not result["converged"] or not all(math.isfinite(v) for v in expected):
                    raise AssertionError(f"Non-converged or non-finite result: {name}")
                if Chem is not None and (len(energies) != 2 or any(abs(a - b) > TOLERANCE for a, b in zip(energies, expected))):
                    raise AssertionError(f"Independent energy mismatch: {name}: {energies} vs {expected}")
                report["calculations"].append({"name": name, "smiles": smiles, "force_field": field,
                    "inchikey": result["inchikey"], "converged": result["converged"], "energies_kcal_mol": expected,
                    "recalculated_energies_kcal_mol": energies if Chem is not None else None,
                    "artifact_sha256": [a["sha256"] for a in artifacts]})
            bad = {"action": "molecule.relax_geometry", "project": "smoke", "params": {"smiles": "not a molecule"}}
            try:
                api("/api/preview", bad)
            except urllib.error.HTTPError as exc:
                if exc.code != 422:
                    raise
            else:
                raise AssertionError("Unsupported input was accepted")
            if api("/api/projects/smoke/verify")["status"] != "PASS":
                raise AssertionError("Project verification failed")
            if len(api("/api/projects/smoke/events")["events"]) != 4:
                raise AssertionError("Unexpected persisted event count")
            report["checks"].extend(["Invalid input rejected", "All content-addressed artifacts hash verified", "Project event and artifact verification"])
            report["status"] = "PASS"
    except Exception as exc:
        report["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        if process is not None:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=10)
            report["shutdown"] = {"exited": process.poll() is not None, "returncode": process.returncode}
            if process.poll() is None:
                report["status"] = "FAIL"
        shutil.rmtree(temp, ignore_errors=True)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(report, indent=2))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("Usage: test_v2_frozen_engine.py ENGINE REPORT.json")
    raise SystemExit(main(Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve()))
