"""Dedicated Avogadro host: bounded RPC, isolated socket and verified file export.

The original application is a bundled companion, not a reimplementation of its UI.
Never connect to the user's ordinary Avogadro socket or replace its active document.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import socket
import stat
import struct
import subprocess
import sys
import tempfile
import threading
import time

from .validation import InputError


def rpc(path: Path, method: str, params: dict, timeout: float = 5.0):
    packet = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as stream:
        stream.settimeout(timeout)
        stream.connect(str(path))
        stream.sendall(struct.pack(">I", len(packet)) + packet)

        def exact(size):
            data = bytearray()
            while len(data) < size:
                fragment = stream.recv(size - len(data))
                if not fragment:
                    raise ConnectionError("Avogadro closed an incomplete RPC reply")
                data.extend(fragment)
            return bytes(data)

        size, = struct.unpack(">I", exact(4))
        if not 0 < size <= 1_000_000:
            raise ConnectionError("Avogadro reply exceeded the supported size")
        response = json.loads(exact(size))
    if not isinstance(response, dict) or response.get("id") != 1 or response.get("jsonrpc") != "2.0":
        raise ConnectionError("Avogadro returned an invalid RPC envelope")
    if "error" in response:
        error = response["error"]
        raise InputError("Avogadro: " + str(error.get("message", error) if isinstance(error, dict) else error))
    if "result" not in response:
        raise ConnectionError("Avogadro reply has no result")
    return response["result"]


def application_path() -> Path | None:
    candidates = [Path(sys.executable).resolve().parents[1] / "hosts/Avogadro2.app"]
    if os.environ.get("OPENCHEM_AVOGADRO_APP"):
        candidates.insert(0, Path(os.environ["OPENCHEM_AVOGADRO_APP"]).expanduser())
    candidates.extend([Path.home()/"Applications/Avogadro2.app", Path("/Applications/Avogadro2.app")])
    return next((p for p in candidates if (p/"Contents/MacOS/Avogadro2").is_file()), None)


class AvogadroHost:
    def __init__(self, root: Path):
        self.root = root
        self.state_file = root / ".avogadro-host.json"
        self.lock = threading.RLock()
        self.process = None
        self.socket = None
        try:
            saved = json.loads(self.state_file.read_text())
            folder = Path(saved["socket"]).parent
            meta = folder.lstat()
            # A saved pointer may only reference our private, short socket directory.
            if (folder.parent == Path("/tmp") and folder.name.startswith(f"oc-avo-{os.getuid()}-")
                    and stat.S_ISDIR(meta.st_mode) and meta.st_uid == os.getuid()
                    and stat.S_IMODE(meta.st_mode) == 0o700 and Path(saved["socket"]).name == "avogadro"):
                self.socket = Path(saved["socket"])
        except (OSError, ValueError, KeyError, TypeError):
            pass

    def status(self):
        with self.lock:
            live = False
            if self.socket:
                try:
                    live = rpc(self.socket, "internalPing", {}, .4) == "pong"
                except (OSError, ValueError, ConnectionError):
                    pass
            app = application_path()
            return {"status": "RESPONDED" if live else "STOPPED", "version": "2.0.0",
                    "installed": app is not None, "application": str(app) if app else None,
                    "socket": str(self.socket) if self.socket else None,
                    "scope": "Dedicated Chem313 companion window; native plugins are not all verified"}

    def start(self):
        with self.lock:
            if self.status()["status"] == "RESPONDED":
                return self.status()
            app = application_path()
            if app is None:
                raise InputError("Avogadro is missing. Use the Chem313 Mac package.")
            if self.process is None or self.process.poll() is not None:
                # macOS Unix socket names have a small fixed length limit. Create the
                # directory before Qt starts, outside a potentially long data path.
                folder = Path(tempfile.mkdtemp(prefix=f"oc-avo-{os.getuid()}-", dir="/tmp"))
                self.socket = folder / "avogadro"
                home = self.root / ".avogadro-home"
                for name in ["Documents", "Library/Preferences", "Library/Application Support"]:
                    (home/name).mkdir(parents=True, exist_ok=True, mode=0o700)
                environment = os.environ.copy()
                for key in ["PYTHONHOME", "PYTHONPATH", "DYLD_LIBRARY_PATH", "QT_PLUGIN_PATH", "QT_QPA_PLATFORM_PLUGIN_PATH"]:
                    environment.pop(key, None)
                environment.update(HOME=str(home), TMPDIR=str(folder))
                fd = os.open(self.root/"avogadro.log", os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
                with os.fdopen(fd, "ab") as log:
                    self.process = subprocess.Popen([str(app/"Contents/MacOS/Avogadro2")],
                        env=environment, stdout=log, stderr=log, start_new_session=True)
                self.state_file.write_text(json.dumps({"socket": str(self.socket), "pid": self.process.pid}))
                self.state_file.chmod(0o600)
            deadline = time.monotonic() + 40
            while time.monotonic() < deadline:
                if self.status()["status"] == "RESPONDED":
                    return self.status()
                if self.process.poll() is not None:
                    raise InputError("Avogadro exited during startup. See avogadro.log in the data folder.")
                time.sleep(.15)
            raise InputError("Avogadro has not opened its connection. Check its window for a startup dialog, then try again.")

    def _export(self) -> str:
        if self.status()["status"] != "RESPONDED":
            raise InputError("Start Avogadro from Engines & tools first")
        with tempfile.TemporaryDirectory(prefix="export-", dir=self.socket.parent) as temporary:
            path = Path(temporary)/"molecule.mol"
            if rpc(self.socket, "exportFile", {"fileName": str(path)}) is not True:
                raise InputError("Avogadro did not accept the export")
            # exportFile acknowledges a queued write, not a completed file.
            deadline = time.monotonic() + 10
            previous = None
            stable = 0
            while time.monotonic() < deadline:
                if path.exists() and not path.is_symlink():
                    with path.open("rb") as stream:
                        content = stream.read(250_001)
                    if len(content) > 250_000:
                        raise InputError("Avogadro export exceeds the 250 KB import limit")
                    stable = stable + 1 if content and content == previous else 0
                    previous = content
                    if stable >= 2:
                        text = content.decode("utf-8")
                        from .chemistry import from_molfile
                        from_molfile(text)
                        return text
                time.sleep(.1)
            raise InputError("Avogadro accepted the export but no complete MOL file arrived")

    def send(self, molfile: str):
        with self.lock:
            self.start()
            if rpc(self.socket, "loadMolecule", {"content": molfile, "format": "mol"}) is not True:
                raise InputError("Avogadro did not accept the molecule")
            return self._export()

    def capture(self):
        with self.lock:
            return self._export()
