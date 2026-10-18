"""Read-only Unix JSON-RPC 2.0 ping using Avogadro's documented framed socket."""
from __future__ import annotations
import json
import os
from pathlib import Path
import socket
import struct
import tempfile
from .validation import InputError


def ping(timeout: float = 2.0) -> dict:
    if os.name != "posix":
        raise InputError("Native Unix socket adapter is supported only on macOS/Linux")
    socket_path = Path(tempfile.gettempdir()) / "avogadro"
    req = json.dumps({"jsonrpc":"2.0","id":1,"method":"internalPing","params":{}}).encode("utf-8")
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
            sock.settimeout(timeout)
            sock.connect(str(socket_path))
            sock.sendall(struct.pack(">I",len(req))+req)
            def recv_exact(count: int) -> bytes:
                data = bytearray()
                while len(data) < count:
                    fragment = sock.recv(count - len(data))
                    if not fragment:
                        raise ConnectionError("Incomplete Avogadro RPC reply")
                    data.extend(fragment)
                return bytes(data)
            size, = struct.unpack(">I", recv_exact(4))
            if size > 1_000_000:
                raise ConnectionError("Avogadro RPC response exceeded safety cap")
            result = json.loads(recv_exact(size))
    except (FileNotFoundError, ConnectionRefusedError, TimeoutError, socket.timeout) as exc:
        return {"status":"NOT_RUNNING_OR_UNREACHABLE", "socket":str(socket_path), "error":type(exc).__name__}
    if not isinstance(result, dict) or result.get("jsonrpc") != "2.0" or result.get("id") != 1 or "error" in result or result.get("result") != "pong":
        raise ConnectionError(f"Avogadro ping did not return a valid pong: {result!r}")
    return {"status":"RESPONDED", "rpc_result":result.get("result"), "socket":str(socket_path), "host_command_execution":"NOT_TESTED"}
