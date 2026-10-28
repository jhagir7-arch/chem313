"""Project-scoped content-addressed source/derivative storage + append-only audit events."""
from __future__ import annotations
from datetime import datetime, timezone
import hashlib
import json
import os
import stat
import tempfile
from pathlib import Path
from typing import Any
try:
    import fcntl
except ImportError:  # Windows native concurrency remains a separate gate.
    fcntl = None
from .validation import InputError, PROJECT_RE


def sha256(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()

class Store:
    def __init__(self, root: str | Path):
        requested = Path(root).expanduser().absolute()
        if requested.is_symlink():
            raise InputError("Workspace root may not be a symlink")
        self.root = requested.resolve()
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)

    def _project(self, project: str) -> Path:
        if not PROJECT_RE.fullmatch(project):
            raise InputError("Invalid project identifier")
        p = self.root / project
        if p.is_symlink():
            raise InputError("Project symlinks are unsupported")
        p.mkdir(parents=True, exist_ok=True, mode=0o700)
        return p

    def put(self, project: str, group: str, ext: str, blob: bytes) -> dict:
        if group not in {"originals", "derived", "reports"} or ext not in {"mol", "sdf", "inp", "svg", "json", "csv", "txt"}:
            raise InputError("Unsupported artifact group or extension")
        if not isinstance(blob, bytes) or len(blob) > 1_000_000:
            raise InputError("Artifact must be bytes within 1 MB cap")
        folder = self._project(project) / group
        if folder.is_symlink():
            raise InputError("Artifact group symlinks are unsupported")
        folder.mkdir(mode=0o700, exist_ok=True)
        hexhash = sha256(blob)
        path = folder / f"{hexhash}.{ext}"
        if path.is_symlink():
            raise InputError("Artifact symlinks are unsupported")
        # Atomic content-addressed create. Never expose an incomplete final object.
        fd, temporary = tempfile.mkstemp(prefix=".pending-", dir=folder)
        try:
            with os.fdopen(fd, "wb") as out:
                os.fchmod(out.fileno(), 0o600) if hasattr(os, "fchmod") else None
                out.write(blob)
                out.flush()
                os.fsync(out.fileno())
            try:
                os.link(temporary, path, follow_symlinks=False)
            except FileExistsError:
                flags = getattr(os, "O_BINARY", 0) | os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
                try:
                    existing = os.open(path, flags)
                    try:
                        meta = os.fstat(existing)
                        if not stat.S_ISREG(meta.st_mode) or meta.st_nlink != 1:
                            raise InputError("Existing artifact is not a safe regular file")
                        with os.fdopen(existing, "rb", closefd=False) as inp:
                            if inp.read(1_000_001) != blob:
                                raise InputError("Existing content-addressed artifact differs from its recorded hash")
                    finally:
                        os.close(existing)
                except OSError as exc:
                    raise InputError("Existing artifact cannot be safely read") from exc
        finally:
            if os.path.lexists(temporary):
                os.unlink(temporary)
        return {"sha256": hexhash, "relative_path": f"{project}/{group}/{hexhash}.{ext}", "bytes": len(blob)}

    @staticmethod
    def _safe_regular(fd: int, name: str) -> os.stat_result:
        meta = os.fstat(fd)
        if not stat.S_ISREG(meta.st_mode) or meta.st_nlink != 1:
            raise InputError(name + " must be a single regular file")
        return meta

    def preflight_event_log(self, project: str) -> None:
        """Reject event targets that might overwrite other local files."""
        if not PROJECT_RE.fullmatch(project):
            raise InputError("Invalid project identifier")
        folder = self.root / project
        if folder.is_symlink():
            raise InputError("Project symlinks are unsupported")
        log = folder / "events.jsonl"
        if log.is_symlink():
            raise InputError("Event log symlinks are unsupported")
        if os.path.lexists(log):
            flags = getattr(os, "O_BINARY", 0) | os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
            try:
                fd = os.open(log, flags)
                try:
                    self._safe_regular(fd, "Event log")
                finally:
                    os.close(fd)
            except OSError as exc:
                raise InputError("Event log cannot be safely opened") from exc

    def _read_log_bytes(self, project: str) -> bytes:
        if not isinstance(project,str) or not PROJECT_RE.fullmatch(project):
            raise InputError("Invalid project identifier")
        folder = self.root / project
        if folder.is_symlink():
            raise InputError("Project symlinks are unsupported")
        log = folder / "events.jsonl"
        if log.is_symlink():
            raise InputError("Event log symlinks are unsupported")
        if not os.path.lexists(log):
            return b""
        flags = getattr(os, "O_BINARY", 0) | os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
        try:
            fd = os.open(log,flags)
        except OSError as exc:
            raise InputError("Event log cannot be safely opened") from exc
        try:
            size = self._safe_regular(fd,"Event log").st_size
            if size > 8_000_000:
                raise InputError("Event log exceeds bounded audit read limit")
            if fcntl:
                fcntl.flock(fd,fcntl.LOCK_SH)
            chunks=[]
            remaining=size
            while remaining:
                blob=os.read(fd,min(65536,remaining))
                if not blob:raise InputError("Unexpected truncated event log")
                chunks.append(blob)
                remaining-=len(blob)
            return b"".join(chunks)
        finally:
            if fcntl: fcntl.flock(fd,fcntl.LOCK_UN)
            os.close(fd)

    def event(self, project: str, action: str, parameters_sha256: str, outputs: list[dict], result: dict) -> dict:
        event = {
            "version": 1,
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "project": project,
            "action": action,
            "parameters_sha256": parameters_sha256,
            "artifacts": outputs,
            "result": result,
        }
        self.preflight_event_log(project)
        log = self._project(project) / "events.jsonl"
        if log.is_symlink():
            raise InputError("Event log symlinks are unsupported")
        data = (json.dumps(event, ensure_ascii=False, sort_keys=True, allow_nan=False) + "\n").encode("utf-8")
        flags = getattr(os, "O_BINARY", 0) | os.O_WRONLY | os.O_CREAT | os.O_APPEND | getattr(os,"O_NOFOLLOW",0) | getattr(os,"O_NONBLOCK",0)
        try:
            fd = os.open(log,flags,0o600)
        except OSError as exc:
            raise InputError("Event log cannot be safely opened for append") from exc
        try:
            self._safe_regular(fd,"Event log")
            if fcntl: fcntl.flock(fd,fcntl.LOCK_EX)
            if os.write(fd,data) != len(data):raise OSError("Short event append")
            os.fsync(fd)
        finally:
            if fcntl: fcntl.flock(fd,fcntl.LOCK_UN)
            os.close(fd)
        return event

    def events(self, project: str, limit: int = 50) -> list[dict]:
        raw=self._read_log_bytes(project)
        if not raw:return []
        if not raw.endswith(b"\n"):
            raise InputError("Event log has an incomplete trailing record")
        try:
            # Validate the whole bounded log before returning a tail. Otherwise an
            # earlier corrupt record could be hidden merely by pagination.
            records = [json.loads(line) for line in raw.decode("utf-8").splitlines()]
            if not all(isinstance(event, dict) for event in records):
                raise ValueError("Event log contains a non-object event")
            return records[-min(max(limit,1),100):]
        except (ValueError,UnicodeDecodeError) as exc:
            raise InputError("Event log contains malformed records") from exc

    def verify_artifacts(self, project: str) -> dict:
        """Read-only audit of event-linked bytes and unreferenced artifact candidates.

        Unsigned local events are not tamper-proof.  An unreferenced object is
        reported for review, never removed: it may be a concurrent/interrupted
        write or an operator-created note awaiting its event.
        """
        if not isinstance(project, str) or not PROJECT_RE.fullmatch(project):
            raise InputError("Invalid project identifier")
        raw = self._read_log_bytes(project)
        if raw and not raw.endswith(b"\n"):
            raise InputError("Event log has a partial final entry")
        faults: list[dict] = []
        referenced: set[str] = set()
        checked = 0
        scan_limit = 5000
        if raw:
            try:
                decoded = raw.decode("utf-8")
            except UnicodeDecodeError:
                return {"status": "FAILED", "checked": 0,
                        "faults": [{"event": 0, "reason": "INVALID_EVENT_ENCODING"}],
                        "unreferenced_candidates": [], "scan_limit": scan_limit,
                        "interpretation": "Event log is not valid UTF-8"}
            for index, line in enumerate(decoded.splitlines(), start=1):
                try:
                    event = json.loads(line)
                    if not isinstance(event, dict) or event.get("project") != project or not isinstance(event.get("artifacts"), list):
                        raise InputError("Event project or artifact array invalid")
                    for obj in event["artifacts"]:
                        rel = Path(obj["relative_path"])
                        if (rel.is_absolute() or len(rel.parts) != 3 or rel.parts[0] != project
                                or rel.parts[1] not in ("originals", "derived", "reports") or ".." in rel.parts):
                            faults.append({"event": index, "reason": "BAD_PATH"})
                            continue
                        referenced.add(rel.as_posix())
                        folder = self.root / project / rel.parts[1]
                        if folder.is_symlink():
                            faults.append({"event": index, "reason": "SYMLINK_FOLDER"})
                            continue
                        flags = getattr(os, "O_BINARY", 0) | os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
                        fd = os.open(self.root / rel, flags)
                        try:
                            meta = self._safe_regular(fd, "Artifact")
                            if meta.st_size > 1_000_000:
                                raise InputError("Artifact over size cap")
                            data = b""
                            while len(data) < meta.st_size:
                                chunk = os.read(fd, meta.st_size - len(data))
                                if not chunk:
                                    raise InputError("Artifact truncated")
                                data += chunk
                            checked += 1
                            if sha256(data) != obj["sha256"] or len(data) != obj["bytes"]:
                                faults.append({"event": index, "reason": "HASH_OR_SIZE_MISMATCH", "path": rel.as_posix()})
                        finally:
                            os.close(fd)
                except (KeyError, ValueError, TypeError, InputError, OSError) as exc:
                    faults.append({"event": index, "reason": "UNREADABLE_OR_INVALID", "type": type(exc).__name__})

        candidates: list[dict] = []
        project_path = self.root / project
        scanned = 0
        if project_path.is_symlink():
            faults.append({"reason": "SYMLINK_PROJECT"})
        elif project_path.is_dir():
            for group in ("originals", "derived", "reports"):
                folder = project_path / group
                if folder.is_symlink():
                    faults.append({"reason": "SYMLINK_FOLDER", "path": f"{project}/{group}"})
                    continue
                if not folder.exists():
                    continue
                if not folder.is_dir():
                    faults.append({"reason": "INVALID_GROUP", "path": f"{project}/{group}"})
                    continue
                with os.scandir(folder) as entries:
                    for entry in entries:
                        scanned += 1
                        if scanned > scan_limit:
                            candidates.append({"reason": "SCAN_LIMIT_REACHED", "limit": scan_limit})
                            break
                        rel = f"{project}/{group}/{entry.name}"
                        if entry.is_symlink():
                            faults.append({"reason": "SYMLINK_ARTIFACT", "path": rel})
                        elif rel not in referenced:
                            candidates.append({"reason": "UNREFERENCED_OBJECT_CANDIDATE", "path": rel})
                if scanned > scan_limit:
                    break
        status = "FAILED" if faults else "REVIEW_REQUIRED" if candidates else "PASS" if raw else "NO_EVENTS"
        return {"status": status, "checked": checked, "faults": faults,
                "unreferenced_candidates": candidates, "scan_limit": scan_limit,
                "interpretation": "Unsigned local file consistency; unreferenced files may reflect interrupted or concurrent writes"}
