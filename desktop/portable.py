"""Portable one-directory launcher for the frozen Chem313 core service."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import threading
import webbrowser
from pathlib import Path


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
    process, _ = launch(args)
    try:
        return process.wait()
    except KeyboardInterrupt:
        process.terminate()
        return process.wait()


if __name__ == "__main__":
    raise SystemExit(main())
