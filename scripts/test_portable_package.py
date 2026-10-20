"""Exercise a frozen portable core from a fresh home, with no Python/Node on PATH."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import runpy
import subprocess
import tempfile
import time
import urllib.request


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("executable", type=Path)
    parser.add_argument("report", type=Path)
    parser.add_argument("--allow-unreleased-candidate", action="store_true",
                        help="record a passing native smoke test even when distribution gates withhold the archive")
    args = parser.parse_args()
    executable, report = args.executable.resolve(), args.report.resolve()
    checks, jobs = [], []
    with tempfile.TemporaryDirectory(prefix="Chem313 portable QA ") as temporary:
        root = Path(temporary)
        home, data = root / "fresh home", root / "research data"
        home.mkdir()
        # Preserve OS runtime requirements; omit development/runtime configuration.
        env = {k: v for k, v in os.environ.items() if k.upper() in {"SYSTEMROOT", "WINDIR", "TEMP", "TMP"}}
        env.update(PATH="", HOME=str(home), USERPROFILE=str(home), LOCALAPPDATA=str(home / "Local"), XDG_DATA_HOME=str(home / ".local/share"))

        def start():
            log_path = root / "service.log"
            log = log_path.open("w", encoding="utf-8")
            process = subprocess.Popen([str(executable), "--serve", "--data", str(data)], cwd=root, env=env, stdout=log, stderr=subprocess.STDOUT)
            deadline = time.monotonic() + 90
            while time.monotonic() < deadline:
                for line in log_path.read_text(errors="replace").splitlines():
                    try:
                        record = json.loads(line)
                    except ValueError:
                        continue
                    if isinstance(record, dict) and str(record.get("url", "")).startswith("http://127.0.0.1:"):
                        return process, record["url"], log
                if process.poll() is not None:
                    break
                time.sleep(.1)
            process.kill()
            process.wait()
            log.close()
            raise RuntimeError("No readiness within 90 seconds: " + log_path.read_text(errors="replace"))

        def stop(process, log):
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
            log.close()

        process, base, log = start()
        token = None

        def api(path, payload=None):
            headers = {"Content-Type": "application/json"}
            if token:
                headers["X-HypothesisLab-Session"] = token
            request = urllib.request.Request(base + path, data=json.dumps(payload).encode() if payload is not None else None, headers=headers)
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.load(response)

        try:
            with urllib.request.urlopen(base, timeout=30) as response:
                assert response.status == 200 and b'<div id="root">' in response.read()
            checks.append("Packaged UI served from the frozen distribution")
            os.environ["OPENCHEM_TEST_URL"] = base
            runpy.run_path(str(Path(__file__).with_name("test_packaged_engine.py")), run_name="__main__")
            checks.append("RDKit geometry, reviewed ORCA input, CSV fit/SVG, session/origin/replay protections and immutable artifacts")
            token = api("/api/session")["session_token"]
            assert api("/api/assistant/status")["status"] != "READY"
            for operation, inputs, expected in [
                ("numpy.summary", {"values": [1, 2, 3, 4, 5], "unit": "V"}, {"mean": 3}),
                ("scipy.line", {"x": [0, 1, 2], "y": [1, 3, 5], "x_unit": "s", "y_unit": "V"}, {"slope": 2, "intercept": 1}),
            ]:
                payload = {"action": "science.run", "params": {"operation": operation, "inputs": inputs}, "project": "portable-proof"}
                receipt = api("/api/preview", payload)
                reply = api("/api/execute", {**payload, "approved": True, "preview_token": receipt["preview_token"]})
                deadline = time.monotonic() + 125
                while True:
                    job = api("/api/jobs/" + reply["result"]["job_id"])
                    if job["state"] not in {"QUEUED", "RUNNING"}:
                        break
                    if time.monotonic() > deadline:
                        raise RuntimeError("Worker did not terminate")
                    time.sleep(.15)
                assert job["state"] == "SUCCEEDED", job
                for key, value in expected.items():
                    assert job["result"]["output"][key] == value, job
                jobs.append(job)
            assert api("/api/projects/portable-proof/verify")["status"] == "PASS"
            checks.append("Both isolated scientific workers passed known numerical references")
        finally:
            stop(process, log)
        process, base, log = start()
        try:
            token = api("/api/session")["session_token"]
            assert api("/api/projects/portable-proof/verify")["status"] == "PASS"
            for job in jobs:
                assert api("/api/jobs/" + job["id"])["state"] == "SUCCEEDED"
            checks.append("Relaunch preserved job results and artifact integrity")
        finally:
            stop(process, log)
    distribution = executable.parent / "DISTRIBUTION_REVIEW.json"
    notices = executable.parent / "licenses" / "portable-core" / "MANIFEST.json"
    releasable = (notices.is_file() and
                  json.loads(notices.read_text(encoding="utf-8")).get("gate", {}).get("passed") and
                  distribution.is_file() and
                  json.loads(distribution.read_text(encoding="utf-8")).get("passed"))
    result = {"status": "PASS", "platform": os.name, "external_python_node": False,
              "fresh_home": True, "relocated_cwd": True, "distribution_releasable": releasable,
              "checks": checks}
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    if not releasable and not args.allow_unreleased_candidate:
        raise SystemExit("Frozen workflow passed; download archive withheld pending runtime redistribution/source review")


if __name__ == "__main__":
    main()
