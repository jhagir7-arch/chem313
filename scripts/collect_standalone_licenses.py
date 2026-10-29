#!/usr/bin/env python3
"""Collect release notices and an ownership manifest for a standalone core app."""
from __future__ import annotations

import argparse
import ast
import base64
import csv
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

NOTICE_PREFIXES = ("license", "licence", "notice", "copying", "copyright")
NATIVE_SUFFIXES = {".dylib", ".so", ".bundle", ".dll", ".pyd"}
FONT_SUFFIXES = {".ttf", ".otf", ".woff", ".woff2"}
REQUIRED_UI = {"3dmol", "events", "ketcher-core", "ketcher-react", "ketcher-standalone", "react", "react-dom"}
PYINSTALLER_MAPPING = "PyInstaller collection with load-path/signature transformation"
CPYTHON_EXTENSION_MAPPING = "PyInstaller TOC standard-library extension checksum"
DEBIAN_SYSTEM_MAPPING = "PyInstaller TOC Debian package checksum"
WINDOWS_CPYTHON_RUNTIME_MAPPING = "PyInstaller TOC official CPython Windows runtime checksum"
MACOS_CPYTHON_RUNTIME_MAPPING = "PyInstaller macOS replayed collection checksum"
MACOS_NCURSES_RUNTIME_VERSION = b"ncurses 6.5.20240427"
MACOS_OPENSSL_RUNTIME_VERSION = b"OpenSSL 3.0.21 9 Jun 2026"
WINDOWS_CPYTHON_RUNTIME_NOTICES = {
    "libcrypto-3.dll": ("OpenSSL-3", "OPENSSL-3-SOURCE.txt"),
    "libssl-3.dll": ("OpenSSL-3", "OPENSSL-3-SOURCE.txt"),
    "libffi-8.dll": ("libffi", "LIBFFI-3.4.6-LICENSE.txt"),
    "sqlite3.dll": ("SQLite", "SQLITE-PUBLIC-DOMAIN.txt"),
}
WINDOWS_MICROSOFT_RUNTIME_TERMS = (
    "https://learn.microsoft.com/cpp/windows/redistributing-visual-cpp-files",
    "https://raw.githubusercontent.com/python/cpython/v3.13.16/PC/crtlicense.txt",
)
WINDOWS_CPYTHON_CRT_NOTICE = "CPYTHON-3.13.16-CRTLICENSE.txt"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rel(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def is_notice(path: Path) -> bool:
    return path.name.lower().startswith(NOTICE_PREFIXES)


def is_native(path: Path) -> bool:
    return path.suffix.lower() in NATIVE_SUFFIXES or ".so." in path.name


def copy(source: Path, dest: Path, output: Path) -> dict:
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, dest)
    return {"path": rel(dest, output), "sha256": sha256(source), "bytes": source.stat().st_size}


def fields(meta: Path) -> dict:
    out = {}
    for line in meta.read_text(encoding="utf-8", errors="replace").splitlines():
        if ": " in line:
            key, value = line.split(": ", 1)
            if key in {"Name", "Version", "License", "License-Expression"}:
                out.setdefault(key, value)
    return out


def record_digest(value: str) -> str | None:
    """Decode a wheel RECORD sha256 field (PEP 376 uses URL-safe base64)."""
    if not value.startswith("sha256="):
        return None
    encoded = value.removeprefix("sha256=")
    try:
        return base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)).hex()
    except ValueError:
        return None


def safe_relative(path: Path, root: Path) -> str | None:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return None


def collect_python(site: Path, output: Path) -> tuple[list[dict], dict]:
    rows: list[dict] = []
    ownership = {"by_sha": {}, "by_path": {}}
    for info in sorted(site.glob("*.dist-info"), key=lambda p: p.name.lower()):
        meta, record = info / "METADATA", info / "RECORD"
        if not meta.is_file() or not record.is_file():
            continue
        data = fields(meta)
        name = data.get("Name", info.name.rsplit("-", 1)[0])
        target = output / "python" / name
        notices = [copy(f, target / f.relative_to(info), output) for f in sorted(info.rglob("*")) if f.is_file() and is_notice(f)]
        for row in csv.reader(record.read_text(encoding="utf-8", errors="replace").splitlines()):
            if not row or len(row) < 2:
                continue
            source = site / row[0]
            if not source.is_file():
                continue
            source_sha256 = sha256(source)
            expected_sha256 = record_digest(row[1])
            # A provenance mapping is only trusted when the installed source is
            # still the payload identified by its wheel RECORD row.
            if expected_sha256 != source_sha256:
                continue
            owner = {
                "owner": name,
                "source": row[0],
                "source_sha256": source_sha256,
                "wheel_record_sha256": expected_sha256,
                "notices": notices,
            }
            ownership["by_sha"].setdefault(source_sha256, owner)
            ownership["by_path"].setdefault(row[0], owner)
        rows.append({"name": name, "version": data.get("Version", "UNKNOWN"), "license_expression": data.get("License-Expression") or data.get("License") or "UNDECLARED_IN_METADATA", "notices": notices})
    return rows, ownership


def apache_fallback(source: Path, target: Path, output: Path, project_root: Path) -> list[dict]:
    headers = []
    for f in sorted(source.rglob("*")):
        if f.is_file() and "node_modules" not in f.relative_to(source).parts and f.suffix in {".js", ".ts", ".tsx", ".d.ts"} and "Licensed under the Apache License, Version 2.0" in f.read_text(encoding="utf-8", errors="ignore"):
            headers.append(rel(f, source))
    notices = []
    if headers:
        out = target / "APACHE_HEADER_SOURCES.txt"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text("\n".join(headers) + "\n", encoding="utf-8")
        notices.append({"path": rel(out, output), "sha256": sha256(out), "bytes": out.stat().st_size})
    apache = project_root / "desktop/licenses/indigo-ketcher/LICENSE"
    if apache.is_file():
        notices.append(copy(apache, target / "APACHE-2.0.txt", output))
    return notices


def ui_provenance(path: Path) -> dict:
    """Validate a complete, hash-bound inventory of the emitted UI directory."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"invalid UI provenance: {exc}") from exc
    if data.get("schema") != "openchem.ui-provenance.v1" or not isinstance(data.get("packages"), list) or not isinstance(data.get("files"), list):
        raise SystemExit("invalid UI provenance: expected openchem.ui-provenance.v1 packages and files")
    packages = data["packages"]
    files = data["files"]
    if len(packages) != len(set(packages)) or not all(isinstance(item, str) and item.startswith("node_modules/") for item in packages):
        raise SystemExit("invalid UI provenance: packages must be unique node_modules locations")
    expected = {}
    for item in files:
        if not isinstance(item, dict) or not isinstance(item.get("path"), str) or not isinstance(item.get("sha256"), str):
            raise SystemExit("invalid UI provenance: files must contain path and sha256")
        relative = Path(item["path"])
        if relative.is_absolute() or ".." in relative.parts or relative.as_posix() != item["path"] or not re.fullmatch(r"[0-9a-f]{64}", item["sha256"]):
            raise SystemExit("invalid UI provenance: unsafe file path or sha256")
        if item["path"] in expected:
            raise SystemExit("invalid UI provenance: duplicate file path")
        expected[item["path"]] = item["sha256"]
    parent = path.parent.resolve()
    actual = {rel(file, parent): sha256(file) for file in parent.rglob("*") if file.is_file() and file.resolve() != path.resolve()}
    if actual != expected:
        raise SystemExit("invalid UI provenance: emitted UI files or hashes do not match inventory")
    return {"packages": set(packages), "file_hashes": set(expected.values()), "path": str(path)}


def vendored_npm_notices(name: str, target: Path, output: Path, project_root: Path) -> list[dict]:
    """Copy reviewed notice material retained for npm tarballs that omit it."""
    source = project_root / "desktop" / "licenses" / "standalone-npm" / name.replace("/", "__")
    if not source.is_dir():
        return []
    return [copy(f, target / "vendored" / f.relative_to(source), output) for f in sorted(source.rglob("*")) if f.is_file()]


def package_emits_ui_file(source: Path, ui_hashes: set[str]) -> bool:
    return any(sha256(file) in ui_hashes for file in source.rglob("*")
               if file.is_file() and "node_modules" not in file.relative_to(source).parts)


def collect_npm(lockfile: Path, modules: Path, output: Path, project_root: Path, ui: dict | None = None) -> list[dict]:
    rows = []
    lock_packages = json.loads(lockfile.read_text(encoding="utf-8")).get("packages", {})
    if ui is not None and not ui["packages"].issubset(lock_packages):
        raise SystemExit("invalid UI provenance: emitted package is absent from package-lock")
    for location, item in sorted(lock_packages.items()):
        emitted = ui is not None and location in ui["packages"]
        if not location or (item.get("dev") is True and not emitted) or not location.startswith("node_modules/"):
            continue
        source = modules / location.removeprefix("node_modules/")
        package_json = source / "package.json"
        if not package_json.is_file():
            if emitted:
                raise SystemExit(f"invalid UI provenance: emitted package is not installed: {location}")
            rows.append({"path": location, "state": "NOT_INSTALLED_FROM_LOCKFILE", "review": "EXCLUDE_UNLESS_PRESENT_IN_RELEASE"})
            continue
        package = json.loads(package_json.read_text(encoding="utf-8"))
        name = package.get("name", source.name)
        target = output / "npm" / name.replace("/", "__")
        notices = [copy(f, target / f.relative_to(source), output) for f in sorted(source.rglob("*")) if f.is_file() and "node_modules" not in f.relative_to(source).parts and is_notice(f)]
        notice_origin = "installed package" if notices else ""
        if not notices:
            notices = vendored_npm_notices(name, target, output, project_root)
            notice_origin = "reviewed retained npm notice material" if notices else ""
        if name.startswith("ketcher-"):
            headers = apache_fallback(source, target, output, project_root)
            if headers:
                notices.extend(headers)
                notice_origin = (notice_origin + "; " if notice_origin else "") + "Ketcher source headers"
        state = "INSTALLED"
        review = "NOTICE_CAPTURED"
        if not notices:
            if ui is not None and not emitted and not package_emits_ui_file(source, ui["file_hashes"]):
                state = "NOT_EMITTED_BUILD_DEPENDENCY"
                review = "NOT_EMITTED_BY_HASHED_UI_PROVENANCE"
            else:
                review = "MISSING_NOTICE_FOR_EMITTED_UI_PACKAGE" if ui is not None else "MISSING_NOTICE_FOR_INSTALLED_PRODUCTION_PACKAGE"
        rows.append({"path": location, "name": name, "version": item.get("version", package.get("version", "UNKNOWN")), "state": state, "license": package.get("license", "UNDECLARED_IN_PACKAGE_JSON"), "notices": notices, "notice_origin": notice_origin or "MISSING", "review": review})
    return rows

def project(root: Path, output: Path) -> dict:
    notices = [copy(root / name, output / "project" / name, output) for name in ("LICENSE", "NOTICE") if (root / name).is_file()]
    return {"name": "hypothesislab-local-core", "license_expression": "Apache-2.0", "notices": notices}


def runtime(root: Path, output: Path, required: bool) -> dict:
    candidates = [root / name for name in ("LICENSE.txt", "LICENSE", "COPYING")]
    candidates.extend(root.glob("lib/python*/LICENSE.txt"))
    source = next((item for item in candidates if item.is_file()), None)
    notices = [copy(source, output / "python-runtime" / source.name, output)] if source else []
    return {"runtime": "CPython", "required": required, "notices": notices, "review": "NOTICE_CAPTURED" if notices else "MISSING_RUNTIME_LICENSE"}


def font_extra_notices(owner: str, site: Path, output: Path) -> list[dict]:
    if owner == "matplotlib":
        source = site / "matplotlib" / "mpl-data" / "fonts" / "ttf"
        return [copy(f, output / "fonts" / "matplotlib" / f.name, output) for f in sorted(source.glob("LICENSE*")) if f.is_file()]
    if owner == "rdkit":
        source = site / "rdkit" / "license.txt"
        return [copy(source, output / "fonts" / "rdkit" / "license.txt", output)] if source.is_file() else []
    return []


def fonts(bundle: Path, site: Path, ownership: dict, output: Path) -> list[dict]:
    rows = []
    for f in sorted(x for x in bundle.rglob("*") if x.is_file() and x.suffix.lower() in FONT_SUFFIXES):
        packaged_sha256 = sha256(f)
        owner = ownership["by_sha"].get(packaged_sha256)
        if owner:
            notices = owner["notices"] + font_extra_notices(owner["owner"], site, output)
            rows.append({"path": rel(f, bundle), "owner": owner["owner"], "source": owner["source"], "source_sha256": owner["source_sha256"], "packaged_sha256": packaged_sha256, "mapping_method": "wheel RECORD checksum", "notices": notices})
        else:
            rows.append({"path": rel(f, bundle), "owner": "UNMAPPED", "source": "UNMAPPED", "packaged_sha256": packaged_sha256, "notices": []})
    return rows


def standard_extension_dirs(runtime: Path) -> list[Path]:
    """Return only CPython's own standard-library extension directories."""
    return [candidate.resolve() for candidate in runtime.glob("lib/python*/lib-dynload") if candidate.is_dir()]


def in_directories(source: Path, directories: list[Path]) -> bool:
    return any(safe_relative(source, directory) is not None for directory in directories)


def is_cpython_runtime_source(source: Path, runtime: Path, extension_dirs: list[Path]) -> bool:
    """Recognize only CPython-owned native locations, never arbitrary runtime DLLs."""
    if in_directories(source, extension_dirs):
        return True
    runtime_root = runtime.resolve()
    parent = source.resolve().parent
    if parent == (runtime_root / "DLLs").resolve() and source.suffix.lower() == ".pyd":
        return True
    name = source.name.lower()
    return parent == runtime_root and name.endswith(".dll") and (name == "python3.dll" or (name.startswith("python") and name[6:-4].isdigit()))


def debian_system_aliases(source: Path) -> list[Path]:
    """Return verified /lib <-> /usr/lib aliases for one existing system file."""
    candidates = [source]
    source_text = str(source)
    if source_text.startswith("/lib/"):
        candidates.append(Path("/usr/lib") / source.relative_to("/lib"))
    elif source_text.startswith("/usr/lib/"):
        candidates.append(Path("/lib") / source.relative_to("/usr/lib"))
    try:
        candidates.append(source.resolve(strict=True))
    except OSError:
        pass
    verified = []
    try:
        source_sha256 = sha256(source)
    except OSError:
        return []
    for candidate in candidates:
        try:
            if candidate.is_file() and candidate.samefile(source) and sha256(candidate) == source_sha256:
                if candidate not in verified:
                    verified.append(candidate)
        except OSError:
            continue
    return verified


def debian_system_owner_detail(source: Path, output: Path, doc_root: Path = Path("/usr/share/doc"),
                               common_root: Path = Path("/usr/share/common-licenses")) -> tuple[dict | None, dict | None]:
    """Capture Debian ownership, returning a safe diagnostic when it cannot be proven."""
    if sys.platform != "linux" or not (str(source).startswith("/lib/") or str(source).startswith("/usr/lib/")):
        return None, None
    aliases = debian_system_aliases(source)
    if not aliases:
        return None, {"code": "SYSTEM_SOURCE_NOT_A_VERIFIED_FILE", "source_path": str(source)}
    packages = set()
    query_paths = []
    for candidate in aliases:
        try:
            owner = subprocess.run(
                ["dpkg-query", "--search", "--", str(candidate)], text=True, capture_output=True, check=True
            ).stdout.strip()
        except (OSError, subprocess.CalledProcessError):
            continue
        query_paths.append(str(candidate))
        packages.update(line.split(": ", 1)[0].split(",", 1)[0] for line in owner.splitlines() if ": " in line)
    if not query_paths:
        return None, {"code": "DPKG_OWNERSHIP_LOOKUP_FAILED", "source_path": str(source), "queried_paths": [str(item) for item in aliases]}
    if len(packages) != 1:
        return None, {"code": "DPKG_OWNERSHIP_NOT_UNIQUE", "source_path": str(source), "queried_paths": query_paths, "packages": sorted(packages)}
    package_id = packages.pop()
    package = package_id.split(":", 1)[0]
    try:
        version = subprocess.run(
            ["dpkg-query", "--showformat=${Version}", "--show", package_id], text=True, capture_output=True, check=True
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None, {"code": "DPKG_VERSION_LOOKUP_FAILED", "source_path": str(source), "package": package_id}
    copyright_notice = doc_root / package / "copyright"
    if not version or not copyright_notice.is_file():
        return None, {"code": "DEBIAN_COPYRIGHT_MISSING", "source_path": str(source), "package": package_id}
    notices = [copy(copyright_notice, output / "system" / package / "copyright", output)]
    # A sentence-ending period is punctuation, not part of Debian's common
    # license filename (for example, ".../GPL-2.").
    common_names = sorted({name.rstrip(".") for name in re.findall(
        r"/usr/share/common-licenses/([A-Za-z0-9.+_-]+)",
        copyright_notice.read_text(encoding="utf-8", errors="replace"))
    })
    for common_name in common_names:
        common_notice = common_root / common_name
        if not common_notice.is_file():
            return None, {"code": "DEBIAN_COMMON_LICENSE_MISSING", "source_path": str(source), "package": package_id, "common_license": common_name}
        notices.append(copy(common_notice, output / "system" / package / "common-licenses" / common_name, output))
    return {
        "owner": package,
        "package": package_id,
        "package_version": version,
        "source": str(source),
        "source_sha256": sha256(source),
        "strict_source_sha256": True,
        "notices": notices,
    }, None


def debian_system_owner(source: Path, output: Path, doc_root: Path = Path("/usr/share/doc"),
                        common_root: Path = Path("/usr/share/common-licenses")) -> dict | None:
    """Backward-compatible Debian package ownership lookup."""
    owner, _diagnostic = debian_system_owner_detail(source, output, doc_root, common_root)
    return owner


def windows_cpython_runtime_owner(source: Path, runtime: Path | None, output: Path,
                                  project_root: Path) -> dict | None:
    """Map only documented third-party DLLs from an official CPython runtime.

    The Microsoft API-set/UCRT/VCRUNTIME payloads deliberately do not appear
    here: their redistribution terms must be retained from Microsoft, rather
    than inferred from CPython's presence on PATH.
    """
    if sys.platform != "win32" or runtime is None or safe_relative(source, runtime) is None:
        return None
    detail = WINDOWS_CPYTHON_RUNTIME_NOTICES.get(source.name.lower())
    if detail is None:
        return None
    owner, filename = detail
    notice = project_root / "desktop" / "licenses" / "portable-runtime" / filename
    if not notice.is_file():
        return None
    return {
        "owner": owner,
        "source": str(source),
        "source_sha256": sha256(source),
        "strict_source_sha256": True,
        "notices": [copy(notice, output / "windows-cpython-runtime" / filename, output)],
    }


def macos_cpython_runtime_owner(source: Path, runtime: Path | None, output: Path,
                                project_root: Path) -> dict | None:
    """Map only CPython's top-level macOS OpenSSL runtime dylibs.

    A later replay check must prove the exact PyInstaller-produced payload.
    The marker is present in libcrypto; libssl is bounded by that sibling.
    No other third-party CPython dylib is inferred from its filename.
    """
    if sys.platform != "darwin" or runtime is None:
        return None
    runtime_lib = (runtime / "lib").resolve()
    try:
        if source.resolve().parent != runtime_lib or source.name.lower() not in {"libcrypto.3.dylib", "libssl.3.dylib"}:
            return None
        marker_source = source if source.name.lower() == "libcrypto.3.dylib" else runtime_lib / "libcrypto.3.dylib"
        if not marker_source.is_file() or MACOS_OPENSSL_RUNTIME_VERSION not in marker_source.read_bytes():
            return None
    except OSError:
        return None
    notice_root = project_root / "desktop" / "licenses" / "portable-runtime"
    terms = notice_root / "OPENSSL-3.0.21-LICENSE.txt"
    provenance = notice_root / "OPENSSL-3.0.21-PROVENANCE.txt"
    if not terms.is_file() or not provenance.is_file():
        return None
    return {
        "owner": "OpenSSL-3.0.21",
        "source": str(source),
        "source_sha256": sha256(source),
        "strict_source_sha256": True,
        "notices": [
            copy(terms, output / "macos-cpython-runtime" / terms.name, output),
            copy(provenance, output / "macos-cpython-runtime" / provenance.name, output),
        ],
    }


def macos_ncurses_runtime_owner(source: Path, runtime: Path | None, output: Path,
                                project_root: Path) -> dict | None:
    """Map only the diagnosed ncurses runtime build from the CPython lib dir."""
    if sys.platform != "darwin" or runtime is None:
        return None
    runtime_lib = (runtime / "lib").resolve()
    try:
        if source.resolve().parent != runtime_lib or source.name.lower() != "libncurses.6.dylib":
            return None
        if MACOS_NCURSES_RUNTIME_VERSION not in source.read_bytes():
            return None
    except OSError:
        return None
    notice_root = project_root / "desktop" / "licenses" / "portable-runtime"
    terms = notice_root / "NCURSES-6.5.20240427-LICENSE.txt"
    provenance = notice_root / "NCURSES-6.5.20240427-PROVENANCE.txt"
    if not terms.is_file() or not provenance.is_file():
        return None
    return {
        "owner": "ncurses-6.5.20240427",
        "source": str(source),
        "source_sha256": sha256(source),
        "strict_source_sha256": True,
        "notices": [
            copy(terms, output / "macos-cpython-runtime" / terms.name, output),
            copy(provenance, output / "macos-cpython-runtime" / provenance.name, output),
        ],
    }


def macos_pyinstaller_replay_sha256(source: Path, destination: str, kind: str) -> str | None:
    """Return PyInstaller's exact macOS collection digest for one TOC entry.

    This replays the collector in an isolated binary cache; it never changes
    the source or the release bundle.  A failure deliberately returns no
    mapping so the release gate remains fail-closed.
    """
    if sys.platform != "darwin" or kind not in {"BINARY", "EXTENSION"}:
        return None
    try:
        from PyInstaller.building.utils import process_collected_binary
        from PyInstaller.config import CONF
    except ImportError:
        return None
    prior_cachedir = CONF.get("cachedir")
    had_cachedir = "cachedir" in CONF
    try:
        with tempfile.TemporaryDirectory(prefix="chem313-pyinstaller-replay-") as cache:
            CONF["cachedir"] = cache
            replayed = Path(process_collected_binary(
                str(source), destination, use_strip=False, use_upx=False,
                upx_exclude=[], target_arch="arm64", codesign_identity=None,
                entitlements_file=None, strict_arch_validation=(kind == "EXTENSION"),
            ))
            return sha256(replayed) if replayed.is_file() else None
    except (OSError, ValueError, RuntimeError, SystemError):
        return None
    finally:
        if had_cachedir:
            CONF["cachedir"] = prior_cachedir
        else:
            CONF.pop("cachedir", None)


def windows_cpython_microsoft_runtime_owner(source: Path, runtime: Path | None, output: Path,
                                            project_root: Path) -> dict | None:
    """Map CPython's bundled Microsoft code only with CPython's exact terms.

    CPython 3.13.16's official ``PC/crtlicense.txt`` permits downstream
    distribution subject to its conditions.  This mapping is intentionally
    confined to files in the pinned CPython runtime and copies those conditions
    into the portable notice set; arbitrary Microsoft DLLs remain unmapped.
    """
    if sys.platform != "win32" or runtime is None or safe_relative(source, runtime) is None:
        return None
    name = source.name.lower()
    if not (name.startswith("api-ms-win-core-") or name.startswith("api-ms-win-crt-")
            or name in {"ucrtbase.dll", "vcruntime140.dll", "vcruntime140_1.dll"}):
        return None
    notice = project_root / "desktop" / "licenses" / "portable-runtime" / WINDOWS_CPYTHON_CRT_NOTICE
    if not notice.is_file():
        return None
    return {
        "owner": "Microsoft Distributable Code via CPython 3.13.16",
        "source": str(source),
        "source_sha256": sha256(source),
        "strict_source_sha256": True,
        "notices": [copy(notice, output / "windows-cpython-runtime" / notice.name, output)],
        "official_terms": list(WINDOWS_MICROSOFT_RUNTIME_TERMS),
        "review": "CPython CRT redistribution conditions retained; do not alter Microsoft notices, imply endorsement, or distribute for non-Microsoft platforms.",
    }


def pyinstaller_toc(path: Path | None, site: Path, ownership: dict, python_runtime: Path | None = None,
                    py_runtime: dict | None = None, output: Path | None = None,
                    project_root: Path | None = None) -> dict:
    if path is None:
        return {}
    try:
        parsed = ast.literal_eval(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError, ValueError) as exc:
        raise SystemExit(f"invalid PyInstaller TOC: {exc}") from exc
    entries = parsed[0] if isinstance(parsed, tuple) and len(parsed) == 1 else parsed
    if not isinstance(entries, list):
        raise SystemExit("invalid PyInstaller TOC: expected a list of collection tuples")
    mapped = {}
    extension_dirs = standard_extension_dirs(python_runtime) if python_runtime else []
    for entry in entries:
        if not (isinstance(entry, tuple) and len(entry) >= 3 and all(isinstance(value, str) for value in entry[:3])):
            continue
        destination, source_text, kind = entry[:3]
        if kind not in {"BINARY", "EXTENSION", "SYMLINK"} or not is_native(Path(destination)):
            continue
        source = Path(source_text)
        if not source.is_absolute():
            source = site / source
        source_rel = safe_relative(source, site)
        if not source.is_file():
            continue
        source_sha256 = sha256(source)
        owner = ownership["by_path"].get(source_rel) if source_rel is not None else None
        if owner and source_sha256 == owner["source_sha256"]:
            mapped[destination] = owner
        elif py_runtime and py_runtime.get("notices") and python_runtime and is_cpython_runtime_source(source, python_runtime, extension_dirs):
            owner = {
                "owner": "CPython",
                "source": str(source),
                "source_sha256": source_sha256,
                "strict_source_sha256": True,
                "notices": py_runtime["notices"],
            }
            replay_sha256 = macos_pyinstaller_replay_sha256(source, destination, kind)
            if replay_sha256:
                owner["macos_pyinstaller_replay_sha256"] = replay_sha256
            mapped[destination] = owner
        elif output is not None:
            owner = windows_cpython_runtime_owner(source, python_runtime, output, project_root) if project_root else None
            if owner is None and project_root:
                owner = windows_cpython_microsoft_runtime_owner(source, python_runtime, output, project_root)
            if owner is None and project_root:
                owner = macos_cpython_runtime_owner(source, python_runtime, output, project_root)
            if owner is None and project_root:
                owner = macos_ncurses_runtime_owner(source, python_runtime, output, project_root)
            diagnostic = None
            if owner is None:
                debian_owner, debian_diagnostic = debian_system_owner_detail(source, output)
                owner = debian_owner
                diagnostic = diagnostic or debian_diagnostic
            if owner:
                replay_sha256 = macos_pyinstaller_replay_sha256(source, destination, kind)
                if replay_sha256 and owner["owner"] in {"OpenSSL-3.0.21", "ncurses-6.5.20240427"}:
                    owner["macos_pyinstaller_replay_sha256"] = replay_sha256
                mapped[destination] = owner
            elif diagnostic:
                mapped[destination] = {"owner": "UNMAPPED", "diagnostic": diagnostic}
    return mapped


def toc_owner(bundle_path: str, toc: dict) -> dict | None:
    if bundle_path in toc:
        return toc[bundle_path]
    if bundle_path.startswith("_internal/"):
        return toc.get(bundle_path.removeprefix("_internal/"))
    marker = "/_internal/"
    if marker in bundle_path:
        return toc.get(bundle_path.split(marker, 1)[1])
    return None


def mapped_native_row(path: str, packaged_sha256: str, owner: dict, mapping_method: str) -> dict:
    """Keep owner provenance intact without claiming wheel metadata for non-wheels."""
    row = {"path": path, "owner": owner["owner"], "source": owner["source"],
           "source_sha256": owner["source_sha256"], "packaged_sha256": packaged_sha256,
           "mapping_method": mapping_method, "notices": owner["notices"]}
    for key in ("wheel_record_sha256", "package", "package_version", "official_terms", "review", "macos_pyinstaller_replay_sha256"):
        if key in owner:
            row[key] = owner[key]
    return row


def native(bundle: Path, ownership: dict, py_runtime: dict, toc: dict) -> list[dict]:
    out = []
    mapped_by_bundle_path = {}
    bundle_root = bundle.resolve()
    for f in sorted(x for x in bundle.rglob("*") if x.is_file() and is_native(x)):
        path = rel(f, bundle)
        packaged_sha256 = sha256(f)
        owner = ownership["by_sha"].get(packaged_sha256)
        if owner:
            row = mapped_native_row(path, packaged_sha256, owner, "wheel RECORD checksum")
        else:
            owner = toc_owner(path, toc)
            if owner and owner.get("owner") == "UNMAPPED":
                row = {"path": path, "owner": "UNMAPPED", "source": "UNMAPPED", "packaged_sha256": packaged_sha256,
                       "notices": [], "diagnostic": owner["diagnostic"]}
            elif owner and (not owner.get("strict_source_sha256") or owner["source_sha256"] == packaged_sha256
                            or owner.get("macos_pyinstaller_replay_sha256") == packaged_sha256):
                method = (MACOS_CPYTHON_RUNTIME_MAPPING if owner.get("macos_pyinstaller_replay_sha256") == packaged_sha256
                          and owner["source_sha256"] != packaged_sha256 else
                          CPYTHON_EXTENSION_MAPPING if owner["owner"] == "CPython" else (
                    WINDOWS_CPYTHON_RUNTIME_MAPPING if owner["owner"] in {"OpenSSL-3", "libffi", "SQLite", "Microsoft Distributable Code via CPython 3.13.16"} else
                    DEBIAN_SYSTEM_MAPPING if "package" in owner else PYINSTALLER_MAPPING))
                row = mapped_native_row(path, packaged_sha256, owner, method)
            elif owner:
                row = {"path": path, "owner": "UNMAPPED", "source": "UNMAPPED", "packaged_sha256": packaged_sha256, "notices": []}
            elif f.name.startswith("libpython"):
                row = {"path": path, "owner": "CPython", "source": "embedded runtime", "packaged_sha256": packaged_sha256, "mapping_method": "embedded runtime", "notices": py_runtime["notices"]}
            else:
                resolved_rel = safe_relative(f, bundle_root)
                target = mapped_by_bundle_path.get(resolved_rel) if resolved_rel and resolved_rel != path else None
                if target:
                    row = {**target, "path": path, "packaged_sha256": packaged_sha256, "mapping_method": "symlink to mapped bundle payload", "symlink_target": resolved_rel}
                else:
                    row = {"path": path, "owner": "UNMAPPED", "source": "UNMAPPED", "packaged_sha256": packaged_sha256, "notices": []}
        mapped_by_bundle_path[path] = row
        out.append(row)
    return out


def gate(project_notice: dict, py_runtime: dict, natives: list[dict], font_rows: list[dict], npm: list[dict], ui: dict | None = None) -> dict:
    errors = []
    if len(project_notice["notices"]) != 2:
        errors.append("project Apache-2.0 LICENSE and NOTICE were not both captured")
    if py_runtime["required"] and not py_runtime["notices"]:
        errors.append("embedded CPython runtime has no captured license")
    unknown = [r["path"] for r in natives if r["owner"] == "UNMAPPED"]
    if unknown:
        errors.append("unmapped native payloads: " + ", ".join(unknown))
    unknown_fonts = [r["path"] for r in font_rows if r["owner"] == "UNMAPPED" or not r["notices"]]
    if unknown_fonts:
        errors.append("bundled fonts are missing mapped owner/notices: " + ", ".join(unknown_fonts))
    required = {row.get("name") for row in npm if row.get("path") in ui["packages"]} if ui is not None else REQUIRED_UI
    direct = {row.get("name"): row for row in npm if row.get("name") in required}
    missing = sorted(name for name in required if name not in direct or not direct[name]["notices"])
    if missing:
        errors.append("required UI package notices missing: " + ", ".join(missing))
    missing_production = [row["path"] for row in npm if row.get("state") == "INSTALLED" and not row.get("notices")]
    if missing_production:
        errors.append("installed production npm packages missing notices: " + ", ".join(missing_production))
    return {"passed": not errors, "failures": errors}


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--site-packages", type=Path, required=True)
    p.add_argument("--package-lock", type=Path, required=True)
    p.add_argument("--node-modules", type=Path, required=True)
    p.add_argument("--bundle", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--project-root", type=Path, default=Path.cwd())
    p.add_argument("--python-runtime", type=Path, default=Path(sys.base_prefix))
    p.add_argument("--pyinstaller-toc", type=Path, help="COLLECT-00.toc used to prove transformed native payload origins")
    p.add_argument("--ui-provenance", type=Path, help="complete hash inventory for the emitted frontend directory")
    a = p.parse_args()
    if a.output.exists():
        raise SystemExit(f"refusing to overwrite existing output: {a.output}")
    a.output.mkdir(parents=True)
    python, owners = collect_python(a.site_packages, a.output)
    ui = ui_provenance(a.ui_provenance) if a.ui_provenance else None
    npm = collect_npm(a.package_lock, a.node_modules, a.output, a.project_root, ui)
    has_python = any(f.name.startswith("libpython") or
                     (f.name.lower().startswith("python") and f.suffix.lower() == ".dll")
                     for f in a.bundle.rglob("*") if f.is_file())
    py_runtime = runtime(a.python_runtime, a.output, has_python)
    project_notice = project(a.project_root, a.output)
    font_rows = fonts(a.bundle, a.site_packages, owners, a.output)
    toc = pyinstaller_toc(a.pyinstaller_toc, a.site_packages, owners, a.python_runtime, py_runtime, a.output, a.project_root)
    natives = native(a.bundle, owners, py_runtime, toc)
    manifest = {
        "scope": "standalone-core-runtime",
        "python_distributions": python,
        "npm_production_packages": npm,
        "project": project_notice,
        "python_runtime": py_runtime,
        "bundle_native_files": natives,
        "bundle_fonts": font_rows,
        "ui_provenance": ui and {"path": ui["path"], "package_count": len(ui["packages"])},
        "gate": gate(project_notice, py_runtime, natives, font_rows, npm, ui),
        "limitations": ["The npm lockfile is not a tree-shaking proof; add a bundle license report for transitive UI code outside the required UI set.", "Mappings use wheel RECORD checksums or an audited PyInstaller COLLECT-00.toc source mapping; statically linked components absent from wheel notices remain outside this inventory."],
    }
    (a.output / "MANIFEST.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {a.output / 'MANIFEST.json'}; gate={'passed' if manifest['gate']['passed'] else 'failed'}")
    if not manifest["gate"]["passed"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
