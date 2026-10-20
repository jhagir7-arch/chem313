"""Portable one-directory launcher for the frozen Chem313 core service."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import threading
import webbrowser
from pathlib import Path


WINDOWS_RUNTIME_TERMS = "CPYTHON-3.13.16-CRTLICENSE.txt"


def platform_data_dir() -> Path:
    """Return the compatible per-user data root without starting the service."""
    local = os.environ.get("LOCALAPPDATA")
    return Path(local) / "OpenChem" if local else Path.home() / "AppData" / "Local" / "OpenChem"


def windows_runtime_terms_path() -> Path:
    """Locate the retained CPython CRT terms next to a frozen Windows bundle."""
    return Path(sys.executable).resolve().parent / "licenses" / "portable-core" / "windows-cpython-runtime" / WINDOWS_RUNTIME_TERMS


def runtime_acceptance_path(args) -> Path:
    return (Path(args.data) if args.data else platform_data_dir()) / "runtime-terms.json"


def terms_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def windows_runtime_terms_accepted(args, terms: Path) -> bool:
    """Return whether this exact retained text has a recorded user acceptance."""
    try:
        record = json.loads(runtime_acceptance_path(args).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return record == {"terms": WINDOWS_RUNTIME_TERMS, "sha256": terms_digest(terms), "accepted": True}


def accept_windows_runtime_terms(args, terms: Path, *, open_terms=None, confirm=None) -> bool:
    """Open the retained terms and require an explicit Windows Yes click."""
    if not terms.is_file():
        raise RuntimeError(f"Missing retained Microsoft runtime terms: {terms}")
    open_terms = os.startfile if open_terms is None else open_terms
    if confirm is None:
        import ctypes
        message = (
            "Chem313 includes Microsoft Distributable Code supplied with CPython.\n\n"
            "The retained CPython runtime terms will open now. Read them, then click Yes "
            "to accept those terms and start Chem313. Click No to exit."
        )
        confirm = lambda: ctypes.windll.user32.MessageBoxW(None, message, "Chem313 runtime terms", 0x00000004 | 0x00000040) == 6
    open_terms(str(terms))
    if not confirm():
        return False
    destination = runtime_acceptance_path(args)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps({
        "terms": WINDOWS_RUNTIME_TERMS,
        "sha256": terms_digest(terms),
        "accepted": True,
    }, sort_keys=True) + "\n", encoding="utf-8")
    return True


def require_windows_runtime_terms(args, *, frozen=None) -> bool:
    """Gate only the distributed Windows executable, never a source checkout."""
    if sys.platform != "win32" or not (getattr(sys, "frozen", False) if frozen is None else frozen):
        return True
    terms = windows_runtime_terms_path()
    if windows_runtime_terms_accepted(args, terms):
        return True
    return accept_windows_runtime_terms(args, terms)


def readiness_url(stream) -> str:
    """Read the service's first record and reject malformed/non-loopback URLs."""
    line = stream.readline()
    if not line:
        raise RuntimeError("Chem313 service exited before reporting readiness")
    try:
        url = json.loads(line)["url"]
    except (KeyError, TypeError, json.JSONDecodeError) as exc:
        raise RuntimeError("Chem313 service returned an invalid readiness record") from exc
    if not isinstance(url, str) or not url.startswith("http://127.0.0.1:"):
        raise RuntimeError("Chem313 service did not bind a loopback URL")
    return url


def _drain(stream) -> None:
    """Keep the child pipe writable after its readiness record was consumed."""
    for _ in stream:
        pass


def launch(args, *, process_factory=subprocess.Popen, browser_open=webbrowser.open):
    command = [sys.executable]
    if not getattr(sys, "frozen", False):
        command.append(str(Path(__file__).resolve()))
    command.append("--serve")
    if args.data:
        command.extend(("--data", args.data))
    if args.ui:
        command.extend(("--ui", args.ui))
    if args.port:
        command.extend(("--port", str(args.port)))
    process = process_factory(command, stdout=subprocess.PIPE, text=True)
    assert process.stdout is not None
    url = readiness_url(process.stdout)
    threading.Thread(target=_drain, args=(process.stdout,), daemon=True).start()
    if not args.no_browser:
        browser_open(url, new=1)
    return process, url


def service_argv(args) -> list[str]:
    forwarded = []
    if args.data:
        forwarded.extend(("--data", args.data))
    if args.ui:
        forwarded.extend(("--ui", args.ui))
    if args.port:
        forwarded.extend(("--port", str(args.port)))
    return forwarded


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data")
    parser.add_argument("--ui")
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--serve", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--science-worker", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    # Keep this dispatch before importing the desktop service: workers must not
    # initialize its UI/server modules or their process-level configuration.
    if args.science_worker:
        from hypothesislab.science_worker import main as worker_main
        worker_main()
        return 0
    if args.serve:
        from hypothesislab.desktop import main as service_main
        service_main(service_argv(args))
        return 0
    if not require_windows_runtime_terms(args):
        return 0
    process, _ = launch(args)
    try:
        return process.wait()
    except KeyboardInterrupt:
        process.terminate()
        return process.wait()


if __name__ == "__main__":
    raise SystemExit(main())
