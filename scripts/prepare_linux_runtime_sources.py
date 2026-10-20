#!/usr/bin/env python3
"""Stage Ubuntu source packages for GCC runtime files in a finished Linux bundle."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path


def run(*args: str) -> str:
    return subprocess.run(args, check=True, text=True, stdout=subprocess.PIPE).stdout.strip()


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def system_library_aliases(path: Path) -> list[Path]:
    """Return merged-/usr and symlink targets for one already hash-matched file."""
    candidates = [path]
    path_text = str(path)
    if path_text.startswith("/lib/"):
        candidates.append(Path("/usr/lib") / path.relative_to("/lib"))
    elif path_text.startswith("/usr/lib/"):
        candidates.append(Path("/lib") / path.relative_to("/usr/lib"))
    try:
        candidates.append(path.resolve(strict=True))
    except OSError:
        pass
    unique = []
    for candidate in candidates:
        if candidate not in unique:
            unique.append(candidate)
    return unique


def packages_from_dpkg_search(output: str) -> set[str]:
    packages = set()
    for line in output.splitlines():
        package_names, separator, _path = line.partition(": ")
        if not separator:
            continue
        for package in package_names.split(","):
            package = package.strip()
            if package:
                packages.add(package.rsplit(":", 1)[0])
    return packages


def package_for(path: Path) -> str:
    """Look up the owner through merged-/usr aliases after exact hash matching."""
    packages = set()
    queried = []
    for candidate in system_library_aliases(path):
        queried.append(str(candidate))
        try:
            packages.update(packages_from_dpkg_search(run("dpkg-query", "-S", str(candidate))))
        except subprocess.CalledProcessError:
            continue
    if len(packages) != 1:
        raise SystemExit(
            f"expected one Ubuntu owner for {path}; found {sorted(packages)} via {queried}"
        )
    return packages.pop()


def installed_equivalent(payload: Path) -> Path:
    """Find the identical runtime owned by Ubuntu, never merely a same-named file."""
    digest = sha256(payload)
    for directory in (Path("/lib"), Path("/usr/lib")):
        for candidate in directory.rglob(payload.name):
            if candidate.is_file() and sha256(candidate) == digest:
                return candidate
    raise SystemExit(f"no hash-identical Ubuntu runtime for {payload}")


def source_for(package: str) -> tuple[str, str]:
    value = run("dpkg-query", "-W", "-f=${source:Package}\t${source:Version}", package)
    source, version = value.split("\t", 1)
    return (source or package, version)


def runtime_files(bundle: Path) -> list[Path]:
    return sorted(p for p in bundle.rglob("*") if p.is_file() and re.match(
        r"(?:lib)?(?:gcc_s|stdc\+\+|gfortran|gomp|quadmath)[-_.]", p.name.lower()))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path)
    parser.add_argument("--build-command", required=True)
    args = parser.parse_args(argv)
    bundle = args.bundle.resolve()
    files = runtime_files(bundle)
    if not files:
        raise SystemExit("no GCC runtime payloads found")
    root = bundle / "licenses" / "portable-core" / "linux-gcc-runtime"
    root.mkdir(parents=True, exist_ok=True)
    sources = root / "ubuntu-source"
    sources.mkdir(exist_ok=True)
    packages = {}
    payloads = {}
    for payload in files:
        try:
            package = package_for(installed_equivalent(payload))
            source, version = source_for(package)
        except subprocess.CalledProcessError as exc:
            raise SystemExit(f"cannot identify Ubuntu package for {payload}: {exc}") from exc
        key = f"{source}={version}"
        packages[key] = (source, version)
        payloads[payload.relative_to(bundle).as_posix()] = {
            "sha256": sha256(payload), "package": package, "source_package": source,
            "source_version": version,
        }
    for key, (source, version) in packages.items():
        destination = sources / re.sub(r"[^A-Za-z0-9._+-]", "_", key)
        destination.mkdir(exist_ok=True)
        subprocess.run(("apt-get", "source", "--download-only", f"{source}={version}"),
                       cwd=destination, check=True)
    archives = {}
    for key in packages:
        folder = sources / re.sub(r"[^A-Za-z0-9._+-]", "_", key)
        files_for_source = [p for p in sorted(folder.iterdir()) if p.is_file()]
        if not files_for_source:
            raise SystemExit(f"apt source did not retain files for {key}")
        archives[key] = {
            p.name: {"path": p.relative_to(bundle).as_posix(), "sha256": sha256(p),
                     "url": "https://archive.ubuntu.com/ubuntu/"}
            for p in files_for_source
        }
    build = {"schema": "openchem.linux-runtime-build.v1", "builder": "Ubuntu native CI",
             "command": args.build_command, "gcc": run("gcc", "--version").splitlines()[0],
             "gfortran": run("gfortran", "--version").splitlines()[0]}
    build_path = root / "BUILD-PROVENANCE.json"
    build_path.write_text(json.dumps(build, indent=2) + "\n", encoding="utf-8")
    source_archives = {}
    for key, value in archives.items():
        for filename, record in value.items():
            source_archives[f"{key}/{filename}"] = record
    for relative, payload in payloads.items():
        if "quadmath" in Path(relative).name.lower():
            matching = [k for k in source_archives if k.startswith(f"{payload['source_package']}={payload['source_version']}/")]
            # A Debian/Ubuntu source package consists of the .dsc and all
            # referenced source archives; retain and verify the complete set.
            payload["source_archives"] = matching
        else:
            payload["compiler"] = build["gcc"]
            payload["eligible_compilation_evidence"] = "licenses/portable-core/linux-gcc-runtime/BUILD-PROVENANCE.json"
    provenance = {"schema": "openchem.gcc-runtime-provenance.v1", "payloads": payloads,
                  "source_archives": source_archives}
    (root / "GCC-RUNTIME-PROVENANCE.json").write_text(json.dumps(provenance, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
