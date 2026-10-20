#!/usr/bin/env python3
"""Build the current OS's Chem313 portable core with PyInstaller one-dir."""
from __future__ import annotations

import argparse
import importlib.metadata as metadata
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import sysconfig
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PRODUCT_NAME = "Chem313"
# Keep the existing on-disk project location. Renaming the executable must not
# strand a researcher's prior OpenChem records.
LEGACY_DATA_PRODUCT_NAME = "OpenChem"


def platform_id() -> str:
    names = {"darwin": "macos", "linux": "linux", "win32": "windows"}
    return names.get(sys.platform, sys.platform)


def write_profile(path: Path) -> None:
    engines = []
    for name, package, domain, repo, license_name, operations in [
        ("RDKit", "rdkit", "cheminformatics", "rdkit/rdkit", "BSD-3-Clause", ["molecule.inspect_smiles", "molecule.import_molfile", "molecule.fidelity_audit", "molecule.generate_conformer"]),
        ("NumPy", "numpy", "numerical_analysis", "numpy/numpy", "BSD-3-Clause and bundled notices", ["numpy.summary"]),
        ("SciPy", "scipy", "measurement_analysis", "scipy/scipy", "BSD-3-Clause and bundled notices", ["scipy.line", "measurement.fit_csv"]),
        ("Matplotlib", "matplotlib", "plotting", "matplotlib/matplotlib", "Matplotlib license and bundled notices", ["measurement.fit_csv"]),
    ]:
        engines.append({"name": name, "version": metadata.version(package), "domain": domain, "repo": f"https://github.com/{repo}", "license": license_name, "operations": operations})
    profile = {"schema": "openchem.standalone.v1", "distribution": "chem313-portable-core",
               "product_name": PRODUCT_NAME, "legacy_data_product_name": LEGACY_DATA_PRODUCT_NAME,
               "platform": platform_id(), "architecture": platform.machine().lower(),
               "operations": ["numpy.summary", "scipy.line"], "engines": engines}
    path.write_text(json.dumps(profile, indent=2) + "\n")


def run(command: list[str], *, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(command, cwd=ROOT, check=check)


def distribution_review(bundle: Path) -> dict:
    # A retained license is necessary but does not supply corresponding source
    # for independent GCC/quadmath runtime binaries. Keep these out of download
    # artifacts until the exact runtime sources and redistribution terms pass.
    pending = [p.relative_to(bundle).as_posix() for p in sorted(bundle.rglob("*"))
               if p.is_file() and re.match(r"(?:lib)?(?:gcc_s|stdc\+\+|gfortran|quadmath|gomp)[-_.]", p.name, re.I)]
    return {"schema": "openchem.distribution-review.v1", "passed": not pending,
            "pending_corresponding_source": pending,
            "scope": "GCC and quadmath runtime source obligations; separate from notice collection and scientific tests"}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--skip-frontend-build", action="store_true")
    args = parser.parse_args(argv)
    target = args.output or ROOT / "dist" / "portable" / f"{PRODUCT_NAME}-core-{platform_id()}-{platform.machine().lower()}"
    target = target.resolve()
    if target.exists():
        raise SystemExit(f"refusing to overwrite existing output: {target}")
    build = ROOT / "build" / "portable"
    build.mkdir(parents=True, exist_ok=True)
    if not args.skip_frontend_build:
        npm = shutil.which("npm")
        if npm is None:
            raise SystemExit("npm is required to build the interface")
        run([npm, "--prefix", "frontend", "run", "build"])
    ui = ROOT / "frontend" / "dist"
    if not ui.is_dir():
        raise SystemExit("built interface missing: run the frontend build first")
    profile = build / "bundle.json"
    write_profile(profile)
    python = sys.executable
    # PyInstaller's destination is a directory. Runtime profile loading expects
    # this file directly under _MEIPASS, alongside the frozen Python payload.
    profile_data = f"{profile}{os.pathsep}."
    run([python, "-m", "PyInstaller", "--noconfirm", "--clean", "--onedir", "--name", PRODUCT_NAME, "--paths", str(ROOT / "backend" / "src"), "--distpath", str(target.parent), "--workpath", str(build / "pyinstaller"), "--specpath", str(build), "--add-data", profile_data, "--collect-data", "rdkit", "--copy-metadata", "rdkit", "--copy-metadata", "numpy", "--copy-metadata", "scipy", "--hidden-import", "rdkit.Chem.AllChem", "--hidden-import", "rdkit.Chem.Draw", "--hidden-import", "matplotlib.backends.backend_agg", "--hidden-import", "matplotlib.backends.backend_svg", "--hidden-import", "uvicorn.logging", "--hidden-import", "uvicorn.loops.auto", "--hidden-import", "uvicorn.protocols.http.auto", "--hidden-import", "uvicorn.protocols.http.h11_impl", "--hidden-import", "uvicorn.protocols.websockets.auto", "--hidden-import", "uvicorn.lifespan.on", "--exclude-module", "tkinter", "--exclude-module", "readline", "--exclude-module", "_curses", "--exclude-module", "_curses_panel", "--exclude-module", "pytest", "--exclude-module", "IPython", "--exclude-module", "pandas", "--exclude-module", "torch", "--exclude-module", "PyQt5", "--exclude-module", "PySide6", str(ROOT / "desktop" / "portable.py")])
    produced = target.parent / PRODUCT_NAME
    if produced != target:
        produced.rename(target)
    bundled_ui = target / "_internal" / "ui"
    if bundled_ui.exists():
        shutil.rmtree(bundled_ui)
    shutil.copytree(ui, bundled_ui)
    if not (bundled_ui / "index.html").is_file():
        raise SystemExit("Portable bundle is missing ui/index.html after staging")
    licenses = target / "licenses" / "portable-core"
    site = Path(sysconfig.get_paths()["purelib"])
    toc = build / "pyinstaller" / PRODUCT_NAME / "COLLECT-00.toc"
    # Retain the complete failed manifest and distribution review for a native
    # candidate.  The final nonzero exit still prevents a release archive from
    # being mistaken for cleared distribution material.
    notice_result = run([python, str(ROOT / "scripts" / "collect_standalone_licenses.py"), "--site-packages", str(site), "--package-lock", str(ROOT / "frontend" / "package-lock.json"), "--node-modules", str(ROOT / "frontend" / "node_modules"), "--bundle", str(target), "--output", str(licenses), "--project-root", str(ROOT), "--python-runtime", sys.base_prefix, "--pyinstaller-toc", str(toc), "--ui-provenance", str(ui / "ui-provenance.json")], check=False)
    if notice_result.returncode not in {0, 2}:
        raise SystemExit(notice_result.returncode)
    for name in ("LICENSE", "NOTICE", "THIRD_PARTY_NOTICES.md"):
        shutil.copy2(ROOT / name, target / name)
    shutil.copy2(ROOT / "release" / "portable" / "README.txt", target / "README.txt")
    (target / "DISTRIBUTION_REVIEW.json").write_text(json.dumps(distribution_review(target), indent=2) + "\n", encoding="utf-8")
    print(target)
    return notice_result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
