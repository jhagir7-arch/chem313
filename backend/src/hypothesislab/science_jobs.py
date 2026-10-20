"""Approved, bounded scientific subprocesses with durable recovery records.

Workers are trusted application code. This is process separation with CPU/time/
output limits, not an operating-system security sandbox.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import threading
import time
import uuid

from .validation import InputError, PROJECT_RE
from .science_contracts import OPERATIONS, validate_operation, descriptions

TERMINAL = {"SUCCEEDED", "FAILED", "CANCELLED", "INTERRUPTED"}
ID_RE = re.compile(r"[0-9a-f]{32}")


def windows_platform() -> bool:
    return os.name == "nt"


def worker_process_options() -> dict:
    if windows_platform():
        # There is no POSIX process group or rlimit API on Windows. The worker
        # itself has no shell execution path; terminate/kill below address its
        # single approved subprocess while wall/result limits remain enforced.
        return {"creationflags": getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)}
    return {"start_new_session": True}


def isolation_description() -> str:
    base = "Trusted subprocess; one CPU thread, 120 s wall / 1 MB result; observed RSS, no hard memory sandbox"
    return base if not windows_platform() else base + "; POSIX CPU/file limits unavailable on Windows"


def utc():
    return datetime.now(timezone.utc).isoformat()


def operation_info(operation):
    return next(x for x in operation_descriptions() if x["operation"] == operation)


def operation_descriptions():
    result = descriptions()
    try:
        from .extended_contracts import descriptions as extended
        result += extended()
    except ImportError:
        pass
    try:
        from .bioscience_contracts import descriptions as bioscience
        result += bioscience()
    except ImportError:
        pass
    from .runtime_profile import bundled_profile
    profile = bundled_profile()
    return [row for row in result if row["operation"] in profile["operations"]] if profile else result


def validated_params(params):
    if not isinstance(params, dict) or set(params) != {"operation", "inputs"}:
        raise InputError("Scientific jobs require exactly operation and inputs")
    try:
        op = params["operation"]
        if isinstance(op, str) and op in OPERATIONS:
            inputs = validate_operation(op, params["inputs"])
        else:
            from .extended_contracts import OPERATIONS as extended_operations, validate_operation as extended_validate
            if isinstance(op, str) and op in extended_operations:
                inputs = extended_validate(op, params["inputs"])
            else:
                from .bioscience_contracts import validate_operation as bioscience_validate
                inputs = bioscience_validate(op, params["inputs"])
        raw = json.dumps(params, ensure_ascii=False, allow_nan=False).encode()
        if len(raw) > 250000:
            raise ValueError("Scientific input exceeds 250 KB")
    except (ValueError, TypeError, ImportError) as exc:
        raise InputError(str(exc) if not isinstance(exc, ImportError) else "Operation is not in the scientific allowlist") from exc
    # Validation may add defaults. Approval remains bound to the original request;
    # the resolved input is preserved separately in the immutable job artifact.
    return {"operation": op, "inputs": inputs}


def worker_command(operation):
    from .runtime_profile import bundled_profile
    profile = bundled_profile()
    if profile:
        if operation not in profile["operations"]:
            raise InputError("This operation is not included in the standalone app")
        return [sys.executable, "--science-worker"], None
    from .extended_contracts import OPERATIONS as extended_operations
    if operation in OPERATIONS:
        group = "science"
    elif operation in extended_operations:
        group = "extended"
    else:
        try:
            from .bioscience_contracts import OPERATIONS as bioscience_operations
        except ImportError as exc:
            raise InputError("Operation is unavailable") from exc
        if operation not in bioscience_operations:
            raise InputError("Operation is not in the scientific allowlist")
        group = "bioscience"
    if getattr(sys, "frozen", False):
        # engine/openchem-engine -> Resources/workers/<group>/<group>-worker
        executable = Path(sys.executable).parent.parent / "workers" / group / f"{group}-worker"
        if not executable.is_file():
            raise InputError(f"The {group} worker is not included in this package")
        return [str(executable)], None
    root = Path(__file__).resolve().parents[3]
    python = root / ".engines" / group / "bin" / "python"
    if group == "bioscience" and not python.is_file():
        python = root / ".engines" / "probe" / "bin" / "python"
    if not python.is_file():
        raise InputError(f"The isolated {group} environment is unavailable; run the documented environment installer")
    return [str(python), "-m", f"hypothesislab.{group}_worker"], str(root / "backend" / "src")


class ScienceJobs:
    def __init__(self, store):
        self.store = store
        self.root = store.root / ".jobs"
        if self.root.is_symlink():
            raise InputError("Job directory symlinks are unsupported")
        self.root.mkdir(mode=0o700, exist_ok=True)
        self.lock = threading.RLock()
        self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="openchem-science")
        self.jobs = {}
        self.processes = {}
        self.closed = False
        # Never replay work on restart. A fresh review is required for a retry.
        def modified(path):
            try:
                return path.lstat().st_mtime_ns
            except OSError:
                return 0
        # UUID ordering is random and can omit the most recent running job.
        # Retain the newest durable records when bounding history reads.
        for path in sorted(self.root.glob("*/state.json"), key=modified)[-500:]:
            if path.is_symlink() or path.parent.is_symlink() or not ID_RE.fullmatch(path.parent.name):
                continue
            try:
                with path.open("rb") as stream:
                    raw = stream.read(2000001)
                if len(raw) > 2000000:
                    continue
                job = json.loads(raw)
                if job.get("id") != path.parent.name or job.get("state") not in TERMINAL | {"QUEUED", "RUNNING"}:
                    continue
                self.jobs[job["id"]] = job
                if job["state"] not in TERMINAL:
                    job.update(state="INTERRUPTED", error="The application stopped before a completion record. Review the input again to retry.", finished_utc=utc())
                    self._persist(job)
            except (OSError, ValueError, TypeError):
                continue

    def _persist(self, job):
        folder = self.root / job["id"]
        if self.root.is_symlink() or folder.is_symlink():
            raise InputError("Unsafe job directory")
        folder.mkdir(mode=0o700, exist_ok=True)
        path = folder / "state.json"
        temporary = folder / (".state-" + uuid.uuid4().hex)
        with temporary.open("x", encoding="utf-8") as out:
            os.chmod(temporary, 0o600)
            json.dump(job, out, ensure_ascii=False, allow_nan=False)
            out.flush()
            os.fsync(out.fileno())
        os.replace(temporary, path)

    def get(self, job_id):
        if not isinstance(job_id, str) or not ID_RE.fullmatch(job_id):
            raise InputError("Invalid job identifier")
        with self.lock:
            if job_id not in self.jobs:
                raise InputError("Job not found")
            return json.loads(json.dumps(self.jobs[job_id]))

    def submit(self, params, project):
        resolved = validated_params(params)
        command, pythonpath = worker_command(resolved["operation"])
        if not PROJECT_RE.fullmatch(project):
            raise InputError("Invalid project identifier")
        with self.lock:
            if self.closed:
                raise InputError("The scientific job service is shutting down")
            if sum(j["state"] not in TERMINAL for j in self.jobs.values()) >= 8:
                raise InputError("The local queue is full (eight jobs maximum)")
            self.store.preflight_event_log(project)
            raw = json.dumps(params, ensure_ascii=False, allow_nan=False).encode()
            source = self.store.put(project, "originals", "json", raw)
            artifacts = [source]
            # Keep exact text bytes as well as the versioned JSON request.
            if isinstance(params["inputs"].get("source"), str):
                ext = "csv" if resolved["operation"] in {"pandas.csv", "polars.csv"} else "txt"
                artifacts.append(self.store.put(project, "originals", ext, params["inputs"]["source"].encode("utf-8")))
            job = dict(id=uuid.uuid4().hex, state="QUEUED", operation=resolved["operation"], project=project,
                       created_utc=utc(), artifacts=artifacts, input_sha256=source["sha256"],
                       engine=operation_info(resolved["operation"])["engine"],
                       isolation=isolation_description())
            self._persist(job)
            self.store.event(project, "science.queued", hashlib.sha256(raw).hexdigest(), artifacts,
                             dict(job_id=job["id"], operation=job["operation"], state="QUEUED"))
            self.jobs[job["id"]] = job
            self.pool.submit(self._run, job["id"], resolved, command, pythonpath)
            return self.get(job["id"])

    @staticmethod
    def _stop(process):
        if windows_platform():
            try:
                process.terminate()
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=3)
            return
        try:
            os.killpg(process.pid, signal.SIGTERM)
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait(timeout=3)
        except ProcessLookupError:
            pass

    def cancel(self, job_id):
        with self.lock:
            job = self.get(job_id)
            if job["state"] in TERMINAL:
                return job
            current = self.jobs[job_id]
            current.update(state="CANCELLED", finished_utc=utc(), error="Cancelled by the user; no numerical result was accepted")
            self._persist(current)
            try:
                self.store.event(current["project"], "science.cancelled", current["input_sha256"], current["artifacts"],
                                 dict(job_id=job_id, operation=current["operation"], state="CANCELLED"))
            except (InputError, OSError) as exc:
                current["audit_error"] = str(exc)[:1000]
                self._persist(current)
            process = self.processes.get(job_id)
        if process:
            self._stop(process)
        return self.get(job_id)

    def _run(self, job_id, resolved, command, pythonpath):
        process = None
        start = time.monotonic()
        try:
            with self.lock:
                job = self.jobs[job_id]
                if job["state"] == "CANCELLED":
                    return
                job.update(state="RUNNING", started_utc=utc())
                self._persist(job)
                folder = self.root / job_id
                env = dict(os.environ)
                for key in list(env):
                    if key.startswith(("PYTHON", "DYLD_")):
                        env.pop(key, None)
                env.update(OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1", MKL_NUM_THREADS="1", NUMEXPR_NUM_THREADS="1", RAYON_NUM_THREADS="1", POLARS_MAX_THREADS="1", VECLIB_MAXIMUM_THREADS="1", MPLCONFIGDIR=str(folder / "matplotlib"))
                if pythonpath:
                    env["PYTHONPATH"] = pythonpath
                with (folder / "stdout.json").open("xb") as output, (folder / "stderr.log").open("xb") as errors:
                    process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=output, stderr=errors,
                                               cwd=folder, env=env, **worker_process_options())
                    self.processes[job_id] = process
            try:
                process.communicate(json.dumps(resolved, allow_nan=False).encode(), timeout=120)
            except subprocess.TimeoutExpired:
                self._stop(process)
                raise ValueError("Scientific worker exceeded the 120 second wall limit")
            with (folder / "stdout.json").open("rb") as stream:
                raw = stream.read(1000001)
            with (folder / "stderr.log").open("rb") as stream:
                logs = stream.read(12000).decode("utf-8", errors="replace")
            if len(raw) > 1000000:
                raise ValueError("Scientific worker exceeded the 1 MB result limit")
            try:
                result = json.loads(raw, parse_constant=lambda value: (_ for _ in ()).throw(ValueError("Non-finite worker result")))
            except (ValueError, UnicodeError) as exc:
                raise ValueError(f"Worker returned no valid result (exit {process.returncode}); {logs[:1500]}") from exc
            if process.returncode != 0:
                raise ValueError(result.get("error", f"Worker exited {process.returncode}"))
            if result.get("schema") != "openchem.science.result.v1" or result.get("operation") != resolved["operation"] or result.get("engine") != job["engine"] or not isinstance(result.get("output"), dict) or not isinstance(result.get("version"), str) or not result["version"]:
                raise ValueError("Worker result does not match the approved operation contract")
            # Also catches finite-looking JSON numeric literals such as 1e999.
            json.dumps(result, allow_nan=False)
            with self.lock:
                if job["state"] == "CANCELLED":
                    return
                artifact = self.store.put(job["project"], "reports", "json", raw)
                artifacts = job["artifacts"] + [artifact]
                self.store.event(job["project"], "science.completed", job["input_sha256"], artifacts,
                                 dict(job_id=job_id, operation=job["operation"], engine=result["engine"], version=result["version"], report_sha256=artifact["sha256"], resources=result.get("resources", {})))
                job.update(state="SUCCEEDED", result=result, artifacts=artifacts, logs=logs,
                           resources=result.get("resources", {}), finished_utc=utc())
                self._persist(job)
        except Exception as exc:
            with self.lock:
                job = self.jobs[job_id]
                if job["state"] != "CANCELLED":
                    job.update(state="FAILED", error=str(exc)[:4000], finished_utc=utc(), elapsed_seconds=time.monotonic()-start)
                    self._persist(job)
                    try:
                        self.store.event(job["project"], "science.failed", job["input_sha256"], job["artifacts"],
                                         dict(job_id=job_id, operation=job["operation"], error=job["error"], state="FAILED"))
                    except (InputError, OSError):
                        pass  # The durable job error remains available when an audit target fails.
        finally:
            if process is not None and process.poll() is None:
                self._stop(process)
            with self.lock:
                self.processes.pop(job_id, None)

    def shutdown(self):
        with self.lock:
            self.closed = True
            pending = [key for key, value in self.jobs.items() if value["state"] not in TERMINAL]
        for job_id in pending:
            self.cancel(job_id)
        self.pool.shutdown(wait=False, cancel_futures=True)
