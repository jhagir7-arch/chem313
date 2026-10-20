"""Bounded local execution of a reviewed beginner Q-Chem single point.

The runtime accepts structured coordinates only.  It renders the Q-Chem input
itself, launches a configured licensed installation without a shell, and keeps
durable job records.  A configured directory is not evidence that Q-Chem or a
license has actually run successfully.
"""
from __future__ import annotations

import hashlib
import json
import math
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

from .identity import identity_check
from .store import Store, sha256
from .validation import InputError, PROJECT_RE


MAX_OUTPUT_BYTES = 1_000_000
MAX_RETURN_TEXT = 32_000
DEFAULT_TIMEOUT_SECONDS = 300
MAX_TIMEOUT_SECONDS = 900
_STATES = frozenset({"QUEUED", "RUNNING", "SUCCEEDED", "FAILED", "TIMED_OUT", "CANCELLED", "INTERRUPTED"})
_COMPOSITIONS = {
    "water": {"H": 2, "O": 1},
    "methane": {"C": 1, "H": 4},
    "ethanol": {"C": 2, "H": 6, "O": 1},
}
# Standard InChIs of the reviewed molecules; ethanol also rejects its dimethyl ether isomer.
_REFERENCE_INCHI = {
    "water": "InChI=1S/H2O/h1H2",
    "methane": "InChI=1S/CH4/h1H4",
    "ethanol": "InChI=1S/C2H6O/c1-2-3/h3H,2H2,1H3",
}
_ENERGY = re.compile(r"Total energy in the final basis set\s*=\s*([-+]?\d+(?:\.\d*)?(?:[Ee][-+]?\d+)?)")
_LICENSE_FAILURE = re.compile(r"(?:licen[cs]e\s+(?:error|failure|expired|invalid|not\s+(?:found|valid))|(?:cannot|unable\s+to|failed\s+to)\b.{0,80}\blicen[cs]e|\blicen[cs]e\b.{0,80}\b(?:cannot|not\s+(?:found|valid)|expired|invalid|failed|failure|error|denied))", re.I)
_FAILURE = re.compile(r"(?:SCF\s+failed|SCF.{0,80}not\s+converg|fatal\s+error|error\s+termination)", re.I)


def _bounded_text(blob: bytes) -> str:
    text = blob[:MAX_RETURN_TEXT].decode("utf-8", "replace")
    return text + ("\n[output truncated for display]" if len(blob) > MAX_RETURN_TEXT else "")


def _atomic_json(path: Path, value: dict[str, Any]) -> None:
    if path.is_symlink() or path.parent.is_symlink():
        raise InputError("Q-Chem configuration symlinks are unsupported")
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".qchem-pending-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            os.fchmod(stream.fileno(), 0o600) if hasattr(os, "fchmod") else None
            json.dump(value, stream, sort_keys=True, allow_nan=False)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.lexists(temporary):
            os.unlink(temporary)


def _installation(installation: str | Path) -> Path:
    candidate = Path(installation).expanduser()
    if not candidate.is_absolute():
        raise InputError("Choose an absolute Q-Chem installation directory")
    try:
        if candidate.is_symlink():
            raise OSError("installation symlink")
        root = candidate.resolve(strict=True)
        binary, aux = root / "bin" / "qchem", root / "qcaux"
        mode = binary.stat().st_mode
    except OSError as exc:
        raise InputError("Q-Chem installation is unavailable") from exc
    if not root.is_dir() or root.is_symlink() or not aux.is_dir() or aux.is_symlink() or not stat.S_ISREG(mode) or not os.access(binary, os.X_OK):
        raise InputError("Choose a Q-Chem directory containing bin/qchem and qcaux")
    return root


def configured_installation(root: Path) -> Path | None:
    path = root / "qchem.json"
    if not path.is_file() or path.is_symlink():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8")).get("installation")
        return _installation(value) if isinstance(value, str) else None
    except (OSError, ValueError, InputError):
        return None


def render_input(molecule: str, atoms: list[dict[str, Any]]) -> str:
    if molecule not in _COMPOSITIONS:
        raise InputError("Choose water, methane, or ethanol")
    if not isinstance(atoms, list) or len(atoms) != sum(_COMPOSITIONS[molecule].values()):
        raise InputError("Coordinates do not match the reviewed molecule atom count")
    counts: dict[str, int] = {}
    lines: list[str] = []
    for atom in atoms:
        if not isinstance(atom, dict) or set(atom) != {"element", "x", "y", "z"} or atom["element"] not in {"H", "C", "O"}:
            raise InputError("Each coordinate needs element, x, y, and z")
        coords = [atom[axis] for axis in ("x", "y", "z")]
        if any(isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or abs(value) > 50 for value in coords):
            raise InputError("Coordinates must be finite numbers within 50 angstroms")
        element = atom["element"]
        counts[element] = counts.get(element, 0) + 1
        # Match frontend qchemInput.mjs: one symbol-space then JS toFixed(8).
        fixed = [0.0 if value == 0 else float(value) for value in coords]
        lines.append(f"{element} {fixed[0]:.8f} {fixed[1]:.8f} {fixed[2]:.8f}")
    if counts != _COMPOSITIONS[molecule]:
        raise InputError("Elements do not match the reviewed molecule composition")
    identity = identity_check([(atom["element"], float(atom["x"]), float(atom["y"]), float(atom["z"])) for atom in atoms],
                              expected_inchi=_REFERENCE_INCHI[molecule], charge=0)
    if identity["status"] != "match":
        raise InputError(identity["detail"])
    return "$molecule\n0 1\n" + "\n".join(lines) + "\n$end\n\n$rem\nJOBTYPE sp\nMETHOD hf\nBASIS def2-SVP\n$end\n"


def prepare_input(molecule: str, atoms: list[dict[str, Any]]) -> dict[str, Any]:
    """Render a checked beginner input without configuring or invoking Q-Chem.

    This is the download/preparation boundary: callers receive only input that
    passed the same coordinate-to-InChI check used immediately before a run.
    """
    input_text = render_input(molecule, atoms)
    identity = identity_check(
        [(atom["element"], float(atom["x"]), float(atom["y"]), float(atom["z"])) for atom in atoms],
        expected_inchi=_REFERENCE_INCHI[molecule], charge=0,
    )
    # render_input already requires this, but keeping the guard adjacent to the
    # returned receipt makes future changes unable to silently widen the gate.
    if identity["status"] != "match":
        raise InputError(identity["detail"])
    return {
        "input_text": input_text,
        "input_sha256": sha256(input_text.encode("utf-8")),
        "identity_check": identity,
        "coordinate_checks": {"inchi_round_trip": True, "coordinate_units": "angstrom"},
        "scope": "The exported coordinates reproduce the selected molecule's standard InChI. This does not validate the geometry, electronic state, method choice, or a Q-Chem result.",
    }


def _parse_result(output: bytes, exit_code: int | None) -> dict[str, Any]:
    text = output.decode("utf-8", "replace")
    normal = "Thank you very much for using Q-Chem" in text
    convergence_markers = ("SCF converged", "SCF Converged", "SCF has converged", "Convergence criterion met")
    converged = any(marker in text for marker in convergence_markers)
    match = _ENERGY.search(text)
    energy = float(match.group(1)) if match else None
    if energy is not None and not math.isfinite(energy):
        energy = None
    license_failure = _LICENSE_FAILURE.search(text)
    failure = license_failure or _FAILURE.search(text)
    success = exit_code == 0 and normal and converged and not failure and energy is not None
    detail = None
    if not success:
        if license_failure:
            detail = "Q-Chem reported a license failure. Check the licensed installation and license configuration."
        elif not converged:
            detail = "The SCF convergence marker was not found; no energy is reported as a successful result."
        elif not normal:
            detail = "Q-Chem did not report normal termination."
        elif exit_code != 0:
            detail = f"Q-Chem exited with code {exit_code}."
        elif energy is None:
            detail = "The final-basis total energy line was not found."
        else:
            detail = "Q-Chem output reported a failure."
    return {"energy_hartree": energy if success else None, "converged": converged,
            "normal_termination": normal, "successful": success, "detail": detail}


class QchemRuntime:
    def __init__(self, store: Store, installation: Path | None = None, *, timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
                 max_output_bytes: int = MAX_OUTPUT_BYTES):
        if not isinstance(timeout_seconds, int) or not 1 <= timeout_seconds <= MAX_TIMEOUT_SECONDS:
            raise InputError("Q-Chem timeout must be 1 through 900 seconds")
        if not isinstance(max_output_bytes, int) or not 1024 <= max_output_bytes <= MAX_OUTPUT_BYTES:
            raise InputError("Q-Chem output limit must be 1 KB through 1 MB")
        self.store, self.timeout_seconds, self.max_output_bytes = store, timeout_seconds, max_output_bytes
        self.installation = installation if installation is not None else configured_installation(store.root)
        self._jobs: dict[str, dict[str, Any]] = {}
        self._lock = threading.Lock()
        self._active: str | None = None
        self._journal = store.root / ".qchem-runtime" / "state"
        if self._journal.is_symlink() or self._journal.parent.is_symlink():
            raise InputError("Q-Chem state symlinks are unsupported")
        self._journal.mkdir(mode=0o700, parents=True, exist_ok=True)
        self._recover()

    def configuration(self) -> dict[str, Any]:
        if self.installation is None:
            if (self.store.root / "qchem.json").exists():
                return {"status": "UNAVAILABLE", "installation": None, "detail": "Saved Q-Chem installation is unavailable or invalid."}
            return {"status": "NOT_CONFIGURED", "installation": None, "detail": "Choose a licensed Q-Chem installation directory."}
        try:
            path = _installation(self.installation)
        except InputError as exc:
            return {"status": "UNAVAILABLE", "installation": str(self.installation), "detail": str(exc)}
        return {"status": "CONFIGURED", "installation": str(path), "detail": "Installation structure checked; a Q-Chem run is still required to verify engine and license."}

    def configure(self, installation: str) -> dict[str, Any]:
        with self._lock:
            if self._active is not None:
                raise InputError("Wait for the active Q-Chem job before changing installation")
            path = _installation(installation)
            _atomic_json(self.store.root / "qchem.json", {"installation": str(path)})
            self.installation = path
        return self.configuration()

    def _identity(self) -> dict[str, str]:
        config = self.configuration()
        if config["status"] != "CONFIGURED":
            raise InputError(config["detail"])
        binary = Path(config["installation"]) / "bin" / "qchem"
        digest = hashlib.sha256()
        try:
            with binary.open("rb") as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(chunk)
        except OSError as exc:
            raise InputError("Q-Chem executable is unavailable") from exc
        return {"installation": config["installation"], "executable": str(binary), "executable_sha256": digest.hexdigest(),
                "qcaux": str(Path(config["installation"]) / "qcaux")}

    def _save(self, job: dict[str, Any]) -> None:
        _atomic_json(self._journal / f"{job['id']}.json", self._snapshot(job))

    def _recover(self) -> None:
        for path in list(self._journal.glob("*.json"))[:1000]:
            if path.is_symlink() or not re.fullmatch(r"[0-9a-f]{32}\.json", path.name):
                continue
            try:
                if path.stat().st_size > 250_000:
                    continue
                job = json.loads(path.read_text(encoding="utf-8"))
                if job.get("id") != path.stem or job.get("state") not in _STATES or not PROJECT_RE.fullmatch(job.get("project", "")):
                    continue
                if job["state"] in {"QUEUED", "RUNNING"}:
                    job.update(state="INTERRUPTED", detail="The desktop service stopped before a terminal result was recorded. This job was not replayed.", finished_utc=time.time())
                    self._save(job)
                job["cancel"] = threading.Event()
                self._jobs[job["id"]] = job
            except (OSError, ValueError, TypeError):
                continue

    @staticmethod
    def _snapshot(job: dict[str, Any]) -> dict[str, Any]:
        result = {key: value for key, value in job.items() if key not in {"cancel", "thread", "process", "cancel_deadline"}}
        result["input_text"] = _bounded_text(result.pop("input_bytes", b"")) if isinstance(result.get("input_bytes"), bytes) else result.get("input_text", "")
        result.pop("input_bytes", None)
        return result

    def status(self, job_id: str) -> dict[str, Any]:
        if not isinstance(job_id, str) or not re.fullmatch(r"[0-9a-f]{32}", job_id):
            raise InputError("Unknown Q-Chem job")
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                raise InputError("Unknown Q-Chem job")
            return self._snapshot(job)

    def jobs(self, project: str) -> list[dict[str, Any]]:
        if not isinstance(project, str) or not PROJECT_RE.fullmatch(project):
            raise InputError("Invalid project identifier")
        with self._lock:
            matching = [self._snapshot(job) for job in self._jobs.values() if job["project"] == project]
        return sorted(matching, key=lambda job: job.get("created_utc", 0), reverse=True)[:20]

    def start(self, project: str, molecule: str, atoms: list[dict[str, Any]], approved: bool) -> dict[str, Any]:
        if approved is not True:
            raise InputError("Q-Chem execution requires explicit approved=true")
        if not isinstance(project, str) or not PROJECT_RE.fullmatch(project):
            raise InputError("Invalid project identifier")
        input_text = render_input(molecule, atoms)
        identity = self._identity()
        self.store.preflight_event_log(project)
        job_id = uuid.uuid4().hex
        input_bytes = input_text.encode("utf-8")
        job = {"id": job_id, "project": project, "molecule": molecule, "atom_count": len(atoms),
               "method": "HF", "basis": "def2-SVP", "job_type": "single_point", "charge": 0, "multiplicity": 1,
               "state": "QUEUED", "detail": "Queued for one local Q-Chem process.", "created_utc": time.time(),
               "input_sha256": sha256(input_bytes), "input_bytes": input_bytes, "output_text": "", "engine": identity,
               "cancel": threading.Event()}
        with self._lock:
            if self._active is not None:
                raise InputError("One local Q-Chem job is already active")
            self.store.event(project, "qchem.run_started", job["input_sha256"], [], {"job_id": job_id, "state": "QUEUED", "engine": identity})
            self._save(job)
            self._jobs[job_id] = job
            self._active = job_id
        thread = threading.Thread(target=self._run, args=(job_id,), daemon=True, name=f"openchem-qchem-{job_id[:8]}")
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
    def _stop_group(process: subprocess.Popen[bytes] | None, force: bool = False) -> None:
        if process is None:
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

    def cancel(self, job_id: str) -> dict[str, Any]:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                raise InputError("Unknown Q-Chem job")
            if job["state"] not in {"QUEUED", "RUNNING"}:
                return self._snapshot(job)
            job["cancel"].set()
            job["cancel_deadline"] = time.monotonic() + 2
            self._stop_group(job.get("process"))
        return self.status(job_id)

    def wait(self, job_id: str, timeout: float = 10) -> dict[str, Any]:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                raise InputError("Unknown Q-Chem job")
            thread = job.get("thread")
        if thread is not None:
            thread.join(timeout)
        return self.status(job_id)

    def shutdown(self) -> dict[str, Any]:
        with self._lock:
            active = self._active
        if active is None:
            return {"status": "IDLE"}
        self.cancel(active)
        final = self.wait(active, 2)
        with self._lock:
            job = self._jobs.get(active)
            if job is not None and job.get("state") in {"QUEUED", "RUNNING"}:
                self._stop_group(job.get("process"), True)
        return self.wait(active, 2)

    def _run(self, job_id: str) -> None:
        captured = bytearray()
        state, detail, exit_code = "RUNNING", None, None
        with self._lock:
            job = self._jobs[job_id]
            job["state"] = "RUNNING"
        try:
            root = self.store.root / ".qchem-runtime" / "jobs"
            root.mkdir(mode=0o700, parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(prefix=f"{job_id}-", dir=root) as work:
                input_path, output_path = Path(work) / "input.in", Path(work) / "output.out"
                input_path.write_bytes(job["input_bytes"])
                if job["cancel"].is_set():
                    state, detail = "CANCELLED", "Cancellation requested before process launch"
                    raise InterruptedError
                # Preserve user/installer environment (including HOME, TMPDIR and
                # any vendor license setting), then pin the Q-Chem runtime paths.
                env = os.environ.copy()
                qc = job["engine"]["installation"]
                env.update({"QC": qc, "QCAUX": job["engine"]["qcaux"], "QCSCRATCH": str(Path(work) / "scratch"),
                            "PATH": str(Path(qc) / "bin") + os.pathsep + env.get("PATH", "")})
                Path(env["QCSCRATCH"]).mkdir(mode=0o700)
                process = subprocess.Popen([job["engine"]["executable"], "-nt", "1", input_path.name, output_path.name], cwd=work,
                                           env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                           start_new_session=True, shell=False)
                with self._lock:
                    job["process"] = process
                started = time.monotonic()
                while process.poll() is None:
                    if job["cancel"].is_set():
                        state, detail = "CANCELLED", "Cancellation requested"
                        self._stop_group(process)
                        if time.monotonic() >= job.get("cancel_deadline", 0):
                            self._stop_group(process, True)
                    elif time.monotonic() - started > self.timeout_seconds:
                        state, detail = "TIMED_OUT", f"Exceeded {self.timeout_seconds}-second limit"
                        self._stop_group(process, True)
                    if process.stdout is not None:
                        ready, _, _ = select.select([process.stdout], [], [], 0.05)
                        if ready:
                            chunk = os.read(process.stdout.fileno(), min(65536, self.max_output_bytes + 1 - len(captured)))
                            captured.extend(chunk)
                            if len(captured) > self.max_output_bytes:
                                state, detail = "FAILED", "Output exceeded configured 1 MB limit"
                                self._stop_group(process, True)
                    if output_path.exists():
                        if output_path.is_symlink():
                            state, detail = "FAILED", "Q-Chem output path became a symlink"
                            self._stop_group(process, True)
                        elif output_path.stat().st_size > self.max_output_bytes:
                            state, detail = "FAILED", "Output exceeded configured 1 MB limit"
                            self._stop_group(process, True)
                exit_code = process.returncode
                if job["cancel"].is_set() and state not in {"TIMED_OUT", "FAILED"}:
                    state, detail = "CANCELLED", "Cancellation requested"
                self._stop_group(process, True)
                if process.stdout is not None:
                    drain_deadline = time.monotonic() + 1
                    while len(captured) <= self.max_output_bytes and time.monotonic() < drain_deadline:
                        ready, _, _ = select.select([process.stdout], [], [], 0.05)
                        if not ready:
                            break
                        tail = os.read(process.stdout.fileno(), min(65536, self.max_output_bytes + 1 - len(captured)))
                        if not tail:
                            break
                        captured.extend(tail)
                if output_path.exists():
                    if output_path.is_symlink() or not output_path.is_file():
                        state, detail = "FAILED", "Q-Chem output path is not a safe regular file"
                    elif output_path.stat().st_size > self.max_output_bytes:
                        state, detail = "FAILED", "Output exceeded configured 1 MB limit"
                    else:
                        with output_path.open("rb") as output_stream:
                            captured = bytearray(output_stream.read(self.max_output_bytes + 1))
                if len(captured) > self.max_output_bytes:
                    captured = captured[:self.max_output_bytes]
                    state, detail = "FAILED", "Output exceeded configured 1 MB limit"
                elif state not in {"CANCELLED", "TIMED_OUT", "FAILED"}:
                    parsed = _parse_result(bytes(captured), exit_code)
                    state, detail = ("SUCCEEDED", None) if parsed["successful"] else ("FAILED", parsed["detail"])
        except InterruptedError:
            pass
        except OSError as exc:
            state, detail = "INTERRUPTED", f"Process launch or runtime error: {type(exc).__name__}"
        finally:
            result = _parse_result(bytes(captured), exit_code)
            result.pop("successful", None)
            result.pop("detail", None)
            if state != "SUCCEEDED":
                result["energy_hartree"] = None
            artifacts: list[dict[str, Any]] = []
            report = {"job_id": job_id, "state": state, "detail": detail, "exit_code": exit_code, "engine": job["engine"],
                      "input_sha256": job["input_sha256"], "output_sha256": hashlib.sha256(captured).hexdigest(), "result": result}
            try:
                source = self.store.put(job["project"], "derived", "inp", job["input_bytes"])
                output = self.store.put(job["project"], "derived", "txt", bytes(captured))
                record = self.store.put(job["project"], "reports", "json", json.dumps(report, sort_keys=True, allow_nan=False).encode())
                artifacts = [source, output, record]
                self.store.event(job["project"], "qchem.run_finished", job["input_sha256"], artifacts, report)
            except Exception as exc:
                state, detail = "INTERRUPTED", f"Result persistence failed: {type(exc).__name__}"
                result["energy_hartree"] = None
            with self._lock:
                job.update(state=state, detail=detail, exit_code=exit_code, result=result, artifacts=artifacts,
                           output_text=_bounded_text(bytes(captured)), output_sha256=hashlib.sha256(captured).hexdigest(), finished_utc=time.time())
                job.pop("process", None)
                try:
                    self._save(job)
                except (OSError, ValueError):
                    job.update(state="INTERRUPTED", detail="The final job status could not be persisted; inspect saved project events.")
                if self._active == job_id:
                    self._active = None
