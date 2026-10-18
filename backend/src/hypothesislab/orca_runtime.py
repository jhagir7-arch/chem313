"""Bounded local execution of an already prepared ORCA input.

This module deliberately has no HTTP/action registration.  Callers must bind
``start`` to the existing preview-and-approval flow.  It never accepts command
text or raw input: only an event-linked ``orca.prepare_input`` artifact may run.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import select
import signal
import stat
import subprocess
import tempfile
import threading
import time
import uuid
from typing import Any

from .store import Store, sha256
from .validation import InputError, PROJECT_RE


MAX_OUTPUT_BYTES = 1_000_000
DEFAULT_TIMEOUT_SECONDS = 300
MAX_TIMEOUT_SECONDS = 900
VERSION_TIMEOUT_SECONDS = 5
_ARTIFACT_RE = re.compile(r"^[0-9a-f]{64}\.inp$")
_JOB_STATES = frozenset({"QUEUED", "RUNNING", "SUCCEEDED", "FAILED", "TIMED_OUT", "CANCELLED", "INTERRUPTED"})


def configured_executable(root: Path | None = None) -> Path | None:
    """Return a configured absolute binary path, without searching PATH."""
    configured = os.environ.get("OPENCHEM_ORCA_EXECUTABLE")
    if not configured:
        config = (root or Path.home() / "Library/Application Support/OpenChem") / "orca.json"
        if config.is_file():
            try:
                value = json.loads(config.read_text(encoding="utf-8")).get("executable")
            except (OSError, ValueError, AttributeError):
                value = None
            configured = value if isinstance(value, str) else None
    if not configured:
        return None
    candidate = Path(configured).expanduser()
    if not candidate.is_absolute():
        raise InputError("ORCA executable must be configured with an absolute path")
    try:
        info = candidate.stat()
    except OSError as exc:
        raise InputError("Configured ORCA executable is unavailable") from exc
    if not stat.S_ISREG(info.st_mode) or not os.access(candidate, os.X_OK):
        raise InputError("Configured ORCA executable is not an executable regular file")
    return candidate.resolve()


def executable_status(executable: Path | None = None, *, discover: bool = True) -> dict[str, Any]:
    """Report configuration and a bounded version probe; never run a calculation."""
    executable = executable if executable is not None else (configured_executable() if discover else None)
    if executable is None:
        return {"status": "NOT_CONFIGURED", "detail": "Set OPENCHEM_ORCA_EXECUTABLE to an absolute licensed ORCA binary path."}
    try:
        probe = subprocess.run([str(executable), "--version"], stdin=subprocess.DEVNULL,
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                               timeout=VERSION_TIMEOUT_SECONDS, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"status": "UNAVAILABLE", "path": str(executable), "detail": type(exc).__name__}
    text = probe.stdout[:4096].decode("utf-8", "replace")
    return {"status": "READY" if probe.returncode == 0 else "UNVERIFIED", "path": str(executable),
            "version_output": text, "version_exit_code": probe.returncode}


def _safe_input(blob: bytes) -> None:
    """Defence in depth: prepared input has only the current renderer grammar."""
    try:
        lines = blob.decode("utf-8").splitlines()
    except UnicodeDecodeError as exc:
        raise InputError("Prepared ORCA input is not valid UTF-8") from exc
    if len(lines) < 4 or any("%" in line for line in lines):
        raise InputError("Prepared ORCA input has an unsupported block or shape")
    if not lines[0].startswith("! ") or lines[1] != "" or not re.fullmatch(r"\* xyz -?\d+ [1-9]\d*", lines[2]):
        raise InputError("Prepared ORCA input no longer matches the approved renderer")
    if lines[-1] != "*" or any(not re.fullmatch(r"[A-Z][a-z]?\s+[-+0-9.eE]+\s+[-+0-9.eE]+\s+[-+0-9.eE]+", line) for line in lines[3:-1]):
        raise InputError("Prepared ORCA coordinates no longer match the approved renderer")


class OrcaRuntime:
    """One local serial ORCA process at a time, with truthful terminal states."""

    def __init__(self, store: Store, executable: Path | None = None, *, timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
                 max_output_bytes: int = MAX_OUTPUT_BYTES):
        if not isinstance(timeout_seconds, int) or not 1 <= timeout_seconds <= MAX_TIMEOUT_SECONDS:
            raise InputError("ORCA timeout must be 1 through 900 seconds")
        if not isinstance(max_output_bytes, int) or not 1024 <= max_output_bytes <= MAX_OUTPUT_BYTES:
            raise InputError("ORCA output limit must be 1 KB through 1 MB")
        self.store = store
        self.configuration_error = None
        try:
            self.executable = executable if executable is not None else configured_executable(store.root)
        except InputError as exc:
            self.executable = None
            self.configuration_error = str(exc)
        self.timeout_seconds, self.max_output_bytes = timeout_seconds, max_output_bytes
        self._jobs: dict[str, dict[str, Any]] = {}
        self._lock = threading.Lock()
        self._active: str | None = None
        self._journal = self.store.root / '.orca-runtime' / 'state'
        if self._journal.is_symlink() or self._journal.parent.is_symlink():
            raise InputError('ORCA state symlinks are unsupported')
        self._journal.mkdir(mode=0o700, parents=True, exist_ok=True)
        self._recover()

    def _save_state(self, job):
        path = self._journal / (job['id'] + '.json')
        if path.is_symlink():
            raise InputError('ORCA state symlinks are unsupported')
        fd, temporary = tempfile.mkstemp(prefix='.pending-', dir=self._journal)
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as stream:
                json.dump(self._snapshot(job), stream, allow_nan=False)
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    def _recover(self):
        for path in list(self._journal.glob('*.json'))[:1000]:
            if path.is_symlink() or not re.fullmatch(r'[0-9a-f]{32}\.json',path.name):
                continue
            try:
                if path.stat().st_size > 100_000:
                    continue
                job = json.loads(path.read_text(encoding='utf-8'))
                if job.get('id') != path.stem or not PROJECT_RE.fullmatch(job.get('project','')) or job.get('state') not in _JOB_STATES:
                    continue
                if job['state'] in {'QUEUED','RUNNING'}:
                    job.update(state='INTERRUPTED',detail='The desktop service stopped before a terminal result was recorded. This job was not replayed.',finished_utc=time.time())
                    self._save_state(job)
                job['cancel'] = threading.Event()
                self._jobs[job['id']] = job
            except (OSError,ValueError,TypeError):
                continue

    def _source(self, project: str, artifact: dict[str, Any]) -> tuple[bytes, dict[str, Any]]:
        if not isinstance(project, str) or not PROJECT_RE.fullmatch(project) or not isinstance(artifact, dict):
            raise InputError("Project and prepared input artifact are required")
        relative, expected_hash, expected_bytes = artifact.get("relative_path"), artifact.get("sha256"), artifact.get("bytes")
        prefix = f"{project}/derived/"
        if (not isinstance(relative, str) or not relative.startswith(prefix) or not _ARTIFACT_RE.fullmatch(relative[len(prefix):])
                or not isinstance(expected_hash, str) or not re.fullmatch(r"[0-9a-f]{64}", expected_hash)
                or not isinstance(expected_bytes, int) or expected_bytes < 1):
            raise InputError("Prepared input artifact reference is invalid")
        known = False
        for event in self.store.events(project, 100):
            if event.get("action") == "orca.prepare_input" and artifact in event.get("artifacts", []):
                known = True
                break
        if not known:
            raise InputError("ORCA runs require an event-linked prepared input artifact")
        path = self.store.root / relative
        try:
            if path.is_symlink() or not path.is_file():
                raise OSError("unsafe input")
            blob = path.read_bytes()
        except OSError as exc:
            raise InputError("Prepared input artifact cannot be safely read") from exc
        if len(blob) != expected_bytes or sha256(blob) != expected_hash or path.name != f"{expected_hash}.inp":
            raise InputError("Prepared input artifact hash or size differs from its event record")
        _safe_input(blob)
        return blob, artifact

    def executable_identity(self):
        if self.executable is None:
            raise InputError('ORCA is not configured')
        try:
            info = self.executable.stat()
            if not stat.S_ISREG(info.st_mode) or not os.access(self.executable,os.X_OK):
                raise OSError('Not executable')
            digest = hashlib.sha256()
            with self.executable.open('rb') as stream:
                for chunk in iter(lambda: stream.read(1024*1024),b''):
                    digest.update(chunk)
            return {'path':str(self.executable), 'sha256':digest.hexdigest()}
        except OSError as exc:
            raise InputError('Configured ORCA executable is unavailable') from exc

    def start(self, project: str, source_artifact: dict[str, Any]) -> dict[str, Any]:
        if self.executable is None:
            raise InputError("ORCA is not configured; set OPENCHEM_ORCA_EXECUTABLE to an absolute licensed binary path")
        identity = self.executable_identity()
        blob, source = self._source(project, source_artifact)
        self.store.preflight_event_log(project)
        job_id = uuid.uuid4().hex
        job = {"id": job_id, "project": project, "state": "QUEUED", "source_artifact": source,
               "input_sha256": sha256(blob), "created_utc": time.time(), "executable":identity, "cancel": threading.Event()}
        with self._lock:
            if self._active is not None:
                raise InputError("One local ORCA job is already active")
            # Persist the start record before the active slot becomes visible;
            # a storage failure cannot strand a reservation.
            self.store.event(project, "orca.run_started", job["input_sha256"], [source],
                             {"job_id": job_id, "state": "QUEUED", "scope": "Local serial process; execution result is not chemical validation."})
            self._save_state(job)
            self._jobs[job_id] = job
            self._active = job_id
        thread = threading.Thread(target=self._run, args=(job_id, blob), daemon=True, name=f"openchem-orca-{job_id[:8]}")
        job["thread"] = thread
        try:
            thread.start()
        except RuntimeError:
            with self._lock:
                self._jobs.pop(job_id, None)
                if self._active == job_id:
                    self._active = None
            raise
        return self.status(job_id)

    @staticmethod
    def _snapshot(job: dict[str, Any]) -> dict[str, Any]:
        return {key: value for key, value in job.items() if key not in {"thread", "cancel", "process", "cancel_deadline"}}

    def status(self, job_id: str) -> dict[str, Any]:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                raise InputError("Unknown ORCA job")
            return self._snapshot(job)

    def cancel(self, job_id: str) -> dict[str, Any]:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                raise InputError("Unknown ORCA job")
            if job["state"] in _JOB_STATES - {"QUEUED", "RUNNING"}:
                return self._snapshot(job)
            job["cancel"].set()
            job["cancel_deadline"] = time.monotonic() + 2
            process = job.get("process")
            self._stop_group(process, force=False)
        return self.status(job_id)

    @staticmethod
    def _stop_group(process: subprocess.Popen[bytes] | None, *, force: bool) -> None:
        if process is None or (os.name != "posix" and process.poll() is not None):
            return
        try:
            if os.name == "posix":
                os.killpg(process.pid, signal.SIGKILL if force else signal.SIGTERM)
            elif force:
                process.kill()
            else:
                process.terminate()
        except (OSError, ProcessLookupError):
            pass

    def shutdown(self, timeout: float = 2) -> dict[str, Any]:
        """Request cancellation, then force-kill any remaining local process group."""
        with self._lock:
            job_id = self._active
        if job_id is None:
            return {"status": "IDLE"}
        self.cancel(job_id)
        state = self.wait(job_id, timeout)
        with self._lock:
            job = self._jobs.get(job_id)
            if job is not None:
                self._stop_group(job.get("process"), force=True)
        return self.wait(job_id, timeout)

    def wait(self, job_id: str, timeout: float = 10) -> dict[str, Any]:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                raise InputError("Unknown ORCA job")
            thread = job.get("thread")
        if thread is not None:
            thread.join(timeout)
        return self.status(job_id)

    def _run(self, job_id: str, blob: bytes) -> None:
        with self._lock:
            job = self._jobs[job_id]
            job["state"] = "RUNNING"
        captured = bytearray()
        detail: str | None = None
        exit_code: int | None = None
        state = "FAILED"
        try:
            scratch_root = self.store.root / ".orca-runtime"
            scratch_root.mkdir(mode=0o700, exist_ok=True)
            with tempfile.TemporaryDirectory(prefix=f"{job_id}-", dir=scratch_root) as work:
                input_path = Path(work) / "input.inp"
                input_path.write_bytes(blob)
                if job["cancel"].is_set():
                    state, detail = "CANCELLED", "Cancellation requested before process launch"
                    raise InterruptedError(detail)
                process = subprocess.Popen([job["executable"]["path"], input_path.name], cwd=work, stdin=subprocess.DEVNULL,
                                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT, start_new_session=True)
                with self._lock:
                    job["process"] = process
                started = time.monotonic()
                while True:
                    if job["cancel"].is_set() and state != "CANCELLED":
                        state, detail = "CANCELLED", "Cancellation requested"
                        self._stop_group(process, force=False)
                    if job["cancel"].is_set() and time.monotonic() >= job.get("cancel_deadline", 0):
                        self._stop_group(process, force=True)
                    elif state != "TIMED_OUT" and time.monotonic() - started > self.timeout_seconds:
                        state, detail = "TIMED_OUT", f"Exceeded {self.timeout_seconds}-second limit"
                        self._stop_group(process, force=True)
                    if process.stdout is not None:
                        ready, _, _ = select.select([process.stdout], [], [], 0.05)
                        if ready:
                            chunk = os.read(process.stdout.fileno(), min(65536, self.max_output_bytes + 1 - len(captured)))
                            if chunk:
                                captured.extend(chunk)
                            if len(captured) > self.max_output_bytes:
                                state, detail = "FAILED", "Output exceeded configured 1 MB limit"
                                self._stop_group(process, force=True)
                    if process.poll() is not None:
                        break
                # A finished parent must not leave helper processes or a pipe open.
                self._stop_group(process, force=True)
                if process.stdout is not None:
                    drain_deadline = time.monotonic() + 1
                    while len(captured) <= self.max_output_bytes and time.monotonic() < drain_deadline:
                        ready, _, _ = select.select([process.stdout], [], [], 0.05)
                        if not ready:
                            break
                        remainder = os.read(process.stdout.fileno(), min(65536, self.max_output_bytes + 1 - len(captured)))
                        if not remainder:
                            break
                        captured.extend(remainder)
                exit_code = process.returncode
                if len(captured) > self.max_output_bytes:
                    captured = captured[:self.max_output_bytes]
                    state, detail = "FAILED", "Output exceeded configured 1 MB limit"
                elif state not in {"CANCELLED", "TIMED_OUT"}:
                    state = "SUCCEEDED" if exit_code == 0 else "FAILED"
                    detail = None if exit_code == 0 else f"ORCA process exited with code {exit_code}"
        except InterruptedError:
            pass
        except OSError as exc:
            state, detail = "INTERRUPTED", f"Process launch or runtime error: {type(exc).__name__}"
        finally:
            text = bytes(captured)
            normal = b"ORCA TERMINATED NORMALLY" in text
            report = {"job_id": job_id, "state": state, "exit_code": exit_code, "detail": detail,
                      "executable":job["executable"], "input_sha256": job["input_sha256"], "output_sha256": hashlib.sha256(text).hexdigest(),
                      "output_bytes": len(text), "normal_termination_marker": normal,
                      "convergence": "UNASSESSED: normal termination does not establish SCF or optimization convergence.",
                      "scope": "Local process record only; no chemistry or result validity is certified."}
            artifacts: list[dict[str, Any]] = []
            try:
                output = self.store.put(job["project"], "derived", "txt", text)
                report_artifact = self.store.put(job["project"], "reports", "json", json.dumps(report, sort_keys=True).encode("utf-8"))
                artifacts = [job["source_artifact"], output, report_artifact]
                self.store.event(job["project"], "orca.run_finished", job["input_sha256"], artifacts, report)
            except Exception as exc:  # Storage errors must never strand the active process slot.
                state, detail = "INTERRUPTED", f"Result persistence failed: {type(exc).__name__}"
                report.update(state=state, detail=detail)
            with self._lock:
                job.update(report=report, artifacts=artifacts, state=state,
                           exit_code=exit_code, detail=detail, finished_utc=time.time())
                job.pop("process", None)
                try:
                    self._save_state(job)
                except (OSError,ValueError):
                    job.update(state='INTERRUPTED',detail='The final job status could not be persisted; inspect saved project events.')
                if self._active == job_id:
                    self._active = None
