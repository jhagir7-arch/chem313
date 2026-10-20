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
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PRODUCT_NAME = "Chem313"
# Keep the existing on-disk project location. Renaming the executable must not
# strand a researcher's prior OpenChem records.
LEGACY_DATA_PRODUCT_NAME = "OpenChem"
WINDOWS_UCRT_BASELINE = "Windows 10 or later, or Windows Server 2022 or later"
WINDOWS_OS_RUNTIME_DLL = re.compile(
    r"(?:api-ms-win-(?:core|crt)-.+|ucrtbase)\.dll", re.IGNORECASE
)


def platform_id() -> str:
    names = {"darwin": "macos", "linux": "linux", "win32": "windows"}
    return names.get(sys.platform, sys.platform)


def write_profile(path: Path) -> None:
    engines = []
    for name, package, domain, repo, license_name, operations in [
        ("RDKit", "rdkit", "cheminformatics", "rdkit/rdkit", "BSD-3-Clause", ["molecule.inspect_smiles", "molecule.import_molfile", "molecule.fidelity_audit", "molecule.generate_conformer", "molecule.relax_geometry"]),
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


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def remove_windows_os_runtime_payloads(bundle: Path, *, system: str = sys.platform) -> list[str]:
    """Remove only UCRT/API-set DLLs supplied by the supported Windows baseline.

    These files are not cleared for redistribution.  On the supported Windows
    10+/Windows Server 2022+ baseline, the loader uses the operating system's UCRT and API
    set schema; keeping arbitrary copies collected from a build image creates
    an unnecessary, unmapped Microsoft payload.  VCRUNTIME DLLs are excluded
    from this rule and continue through the pinned-CPython notice mapping.
    """
    if system != "win32":
        return []
    internal = bundle / "_internal"
    if not internal.is_dir():
        return []
    removed = []
    for payload in sorted(internal.iterdir(), key=lambda item: item.name.lower()):
        if payload.is_file() and WINDOWS_OS_RUNTIME_DLL.fullmatch(payload.name):
            payload.unlink()
            removed.append(payload.relative_to(bundle).as_posix())
    return removed


def linux_runtime_evidence(bundle: Path) -> dict:
    path = bundle / "licenses" / "portable-core" / "linux-gcc-runtime" / "GCC-RUNTIME-PROVENANCE.json"
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def distribution_review(bundle: Path) -> dict:
    """Separate the GCC runtime exception from LGPL-only libquadmath.

    The GCC Runtime Library Exception can cover libgcc, libstdc++, and
    libgfortran only when the packaged target code came from an eligible
    compilation process.  libquadmath is LGPL-2.1-or-later and does not share
    that exception, so a releasable archive still needs its corresponding
    source or a valid LGPL source offer.
    """
    pending_gcc_exception, pending_lgpl = [], []
    for path in sorted(p for p in bundle.rglob("*") if p.is_file()):
        relative = path.relative_to(bundle).as_posix()
        name = path.name.lower()
        if re.match(r"(?:lib)?(?:gcc_s|stdc\+\+|gfortran|gomp)[-_.]", name):
            pending_gcc_exception.append(relative)
        elif re.match(r"(?:lib)?quadmath[-_.]", name):
            pending_lgpl.append(relative)
    evidence = linux_runtime_evidence(bundle)
    payloads = evidence.get("payloads", {})
    archives = evidence.get("source_archives", {})
    if not isinstance(payloads, dict) or not isinstance(archives, dict):
        payloads, archives = {}, {}
    cleared_gcc, cleared_quadmath = [], []
    for relative in pending_gcc_exception[:]:
        item = payloads.get(relative, {})
        if (isinstance(item, dict) and item.get("sha256") == sha256(bundle / relative)
                and isinstance(item.get("compiler"), str)
                and isinstance(item.get("eligible_compilation_evidence"), str)
                and (item["eligible_compilation_evidence"].startswith("https://")
                     or (bundle / item["eligible_compilation_evidence"]).is_file())):
            cleared_gcc.append(relative)
    for relative in pending_lgpl[:]:
        item = payloads.get(relative, {})
        archive_keys = item.get("source_archives") if isinstance(item, dict) else None
        if isinstance(item, dict) and isinstance(item.get("source_archive"), str):
            archive_keys = [item["source_archive"]]
        archive_records = [archives.get(key) for key in archive_keys] if isinstance(archive_keys, list) else []
        if (isinstance(item, dict) and item.get("sha256") == sha256(bundle / relative)
                and archive_records and all(isinstance(archive, dict)
                    and isinstance(archive.get("path"), str)
                    and isinstance(archive.get("sha256"), str)
                    and isinstance(archive.get("url"), str)
                    and archive["url"].startswith("https://")
                    and (bundle / archive["path"]).is_file()
                    and sha256(bundle / archive["path"]) == archive["sha256"]
                    for archive in archive_records)):
            cleared_quadmath.append(relative)
    pending_gcc_exception = [item for item in pending_gcc_exception if item not in cleared_gcc]
    pending_lgpl = [item for item in pending_lgpl if item not in cleared_quadmath]
    return {
        "schema": "openchem.distribution-review.v2",
        "passed": not pending_gcc_exception and not pending_lgpl,
        "pending_gcc_runtime_exception_verification": pending_gcc_exception,
        "pending_lgpl_corresponding_source": pending_lgpl,
        "cleared_gcc_runtime_exception": cleared_gcc,
        "cleared_lgpl_corresponding_source": cleared_quadmath,
        "scope": "GCC Runtime Library Exception and LGPL libquadmath obligations; separate from notice collection and scientific tests",
        "conditions": [
            "Each GCC Runtime Library Exception candidate remains release-blocking until retained notices and version/hash-bound evidence show that its target code was produced by an eligible compilation process.",
            "Each libquadmath payload remains release-blocking until its exact corresponding source or a valid LGPL source offer is included."
        ],
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--skip-frontend-build", action="store_true")
    parser.add_argument("--review-bundle", type=Path,
                        help="rewrite a finished bundle's hash-bound distribution review")
    args = parser.parse_args(argv)
    if args.review_bundle:
        target = args.review_bundle.resolve()
        if not target.is_dir():
            raise SystemExit(f"bundle missing: {target}")
        (target / "DISTRIBUTION_REVIEW.json").write_text(
            json.dumps(distribution_review(target), indent=2) + "\n", encoding="utf-8"
        )
        return 0
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
    removed_windows_os_runtime_payloads = remove_windows_os_runtime_payloads(target)
    if removed_windows_os_runtime_payloads:
        print(
            "excluded Windows OS UCRT/API-set payloads "
            f"(requires {WINDOWS_UCRT_BASELINE}): "
            + ", ".join(removed_windows_os_runtime_payloads)
        )
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
