#!/usr/bin/env python3
"""Freeze the Python engine for the v2 desktop shell, on whichever OS this runs.

Output: <dest>/chem313-engine[.exe] plus its _internal/ folder (PyInstaller onedir). The Tauri
bundle ships that folder as a resource and starts the executable with --data/--port. The browser
interface is not included; the shell does not use it.

    python scripts/freeze_engine.py --dest app/src-tauri/engine
"""
import argparse
import platform
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

HIDDEN = [
    "rdkit.Chem.rdDetermineBonds", "rdkit.Chem.inchi", "rdkit.Chem.AllChem", "rdkit.Chem.Draw",
    "matplotlib.backends.backend_agg", "matplotlib.backends.backend_svg",
    "uvicorn.logging", "uvicorn.loops.auto", "uvicorn.protocols.http.auto",
    "uvicorn.protocols.http.h11_impl", "uvicorn.protocols.websockets.auto", "uvicorn.lifespan.on",
]
EXCLUDE = ["tkinter", "pytest", "IPython", "pandas", "torch", "PyQt5", "PySide6"]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dest", default="app/src-tauri/engine", help="folder that will hold chem313-engine and _internal/")
    parser.add_argument("--work", default="build/freeze-engine", help="PyInstaller work/spec folder")
    parser.add_argument("--python", default=sys.executable, help="interpreter that has the backend and PyInstaller installed")
    args = parser.parse_args()
    dest = (ROOT / args.dest).resolve()
    work = (ROOT / args.work).resolve()
    if dest.exists():
        shutil.rmtree(dest)
    work.mkdir(parents=True, exist_ok=True)
    command = [
        args.python, "-m", "PyInstaller", "--noconfirm", "--clean", "--onedir", "--name", "chem313-engine",
        "--paths", str(ROOT / "backend/src"), "--distpath", str(work / "dist"), "--workpath", str(work / "work"),
        "--specpath", str(work), "--collect-data", "rdkit", "--copy-metadata", "rdkit", "--copy-metadata", "numpy", "--copy-metadata", "scipy",
    ]
    for module in HIDDEN:
        command += ["--hidden-import", module]
    for module in EXCLUDE:
        command += ["--exclude-module", module]
    command.append(str(ROOT / "desktop/service.py"))
    print("freezing engine for", platform.system(), platform.machine(), flush=True)
    subprocess.run(command, check=True, cwd=ROOT)
    shutil.copytree(work / "dist" / "chem313-engine", dest)
    executable = dest / ("chem313-engine.exe" if sys.platform.startswith("win") else "chem313-engine")
    if not executable.is_file():
        print("freeze produced no executable at", executable, file=sys.stderr)
        return 1
    banner = subprocess.run([str(executable), "--help"], capture_output=True, text=True, timeout=120)
    if banner.returncode != 0 or "--data" not in banner.stdout:
        print("frozen engine failed its --help check:", banner.stdout, banner.stderr, file=sys.stderr)
        return 1
    print("engine ready at", executable)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
