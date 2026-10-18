"""Cross-process single-use approvals bound to exact review inputs.

This is a local interaction guard, not OS authentication or a hardened multi-user
sandbox. Tokens persist across CLI invocations until one use or expiry.
"""
from __future__ import annotations
from hashlib import sha256
import hmac
import json
import os
from pathlib import Path
import secrets
import sqlite3
import stat
import time
from typing import Any

from .validation import InputError

TTL_SECONDS = 180
MAX_PENDING = 128


def request_digest(action: str, params: dict[str, Any], project: str, effect: str) -> str:
    payload = {"schema": "hypothesislab.request.v2", "action": action,
               "project": project, "effect": effect, "params": params}
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")
    return sha256(blob).hexdigest()


def action_v2_digest(action: str, params: dict[str, Any], project: str) -> str:
    """Stable cross-client review identifier, independent of the action effect."""
    payload = {
        "contract": "hypothesislab.action.v2",
        "action": action,
        "project": project,
        "params": params,
    }
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")
    return sha256(blob).hexdigest()


class ApprovalLedger:
    """SQLite transactions prevent double consumption across workers/processes."""
    def __init__(self, root: str | Path):
        self.root = Path(root).expanduser().absolute()
        if self.root.is_symlink():
            raise InputError("Approval root symlinks are unsupported")
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        if not self.root.is_dir():
            raise InputError("Approval root must be a directory")
        self.path = self.root / ".approval_ledger.sqlite3"
        if self.path.is_symlink():
            raise InputError("Approval database symlinks are unsupported")
        try:
            fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY |
                         getattr(os, "O_NOFOLLOW", 0), 0o600)
            os.close(fd)
        except FileExistsError:
            pass
        self._regular_path()
        db = self._connect()
        try:
            db.execute("""CREATE TABLE IF NOT EXISTS approvals (
                token_hash TEXT PRIMARY KEY,
                request_hash TEXT NOT NULL,
                expires_epoch REAL NOT NULL,
                consumed INTEGER NOT NULL DEFAULT 0 CHECK (consumed IN (0,1))
            )""")
            db.execute("""CREATE TABLE IF NOT EXISTS time_guard (
                id INTEGER PRIMARY KEY CHECK(id=1),
                last_epoch REAL NOT NULL
            )""")
        finally:
            db.close()

    def _regular_path(self) -> None:
        try:
            meta = os.lstat(self.path)
        except OSError as exc:
            raise InputError("Approval ledger unavailable") from exc
        if not stat.S_ISREG(meta.st_mode) or meta.st_nlink != 1:
            raise InputError("Approval ledger must be a single regular file")
        if os.name == "posix" and meta.st_mode & 0o077:
            raise InputError("Approval ledger permissions are too broad")

    def _connect(self) -> sqlite3.Connection:
        self._regular_path()
        db = sqlite3.connect(self.path, timeout=8, isolation_level=None)
        db.execute("PRAGMA busy_timeout=8000")
        return db

    @staticmethod
    def _clock_guard(db: sqlite3.Connection, now: float) -> None:
        """Fail closed across restarts if the persisted wall clock moves back."""
        row = db.execute("SELECT last_epoch FROM time_guard WHERE id=1").fetchone()
        if row is not None and now + 2.0 < row[0]:
            db.execute("UPDATE approvals SET consumed=1 WHERE consumed=0")
            # Persist the revocation before raising: the outer error path rolls
            # back an open transaction, which would otherwise restore tickets.
            db.commit()
            raise InputError("System clock moved backward; outstanding approvals revoked")
        db.execute("INSERT INTO time_guard(id,last_epoch) VALUES(1,?) "
                   "ON CONFLICT(id) DO UPDATE SET last_epoch=max(last_epoch,excluded.last_epoch)", (now,))

    def preview(self, digest: str, ttl: float = TTL_SECONDS) -> str:
        if not isinstance(digest, str) or len(digest) != 64:
            raise InputError("Invalid review request digest")
        if not (0 < ttl <= TTL_SECONDS):
            raise InputError("Approval lifetime invalid")
        token = "hl_" + secrets.token_urlsafe(32)
        db = self._connect()
        try:
            db.execute("BEGIN IMMEDIATE")
            now = time.time()
            self._clock_guard(db, now)
            db.execute("DELETE FROM approvals WHERE expires_epoch < ?", (now-3600,))
            active = db.execute("SELECT COUNT(*) FROM approvals WHERE consumed=0 AND expires_epoch > ?", (now,)).fetchone()[0]
            if active >= MAX_PENDING:
                raise InputError("Too many outstanding previews")
            db.execute("INSERT INTO approvals VALUES (?,?,?,0)", (sha256(token.encode()).hexdigest(), digest, now + ttl))
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()
        return token

    def consume(self, token: str | None, digest: str) -> None:
        if not isinstance(token, str) or not (30 <= len(token) <= 256):
            raise InputError("A valid preview token is required")
        digest_token = sha256(token.encode()).hexdigest()
        db = self._connect()
        expired_or_used = False
        changed = False
        try:
            db.execute("BEGIN IMMEDIATE")
            now = time.time()
            self._clock_guard(db, now)
            row = db.execute("SELECT request_hash, expires_epoch, consumed FROM approvals WHERE token_hash=?", (digest_token,)).fetchone()
            if row is None or row[2] or row[1] <= now:
                expired_or_used = True
            else:
                changed = not hmac.compare_digest(row[0], digest)
                # Consume mismatched approvals too. A changed request cannot restore approval.
                db.execute("UPDATE approvals SET consumed=1 WHERE token_hash=? AND consumed=0", (digest_token,))
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()
        if expired_or_used:
            raise InputError("Preview token missing, expired, or previously used")
        if changed:
            raise InputError("Reviewed action, project, or input changed after preview")
