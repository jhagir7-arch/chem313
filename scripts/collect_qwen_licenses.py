#!/usr/bin/env python3
"""Collect an artifact-local Qwen worker notice bundle and native-file SBOM."""
from __future__ import annotations

import argparse
import ast
import base64
import csv
import hashlib
import json
import shutil
from pathlib import Path


NOTICE_PREFIXES = ("license", "licence", "notice", "copying", "copyright")
NATIVE_SUFFIXES = (".dylib", ".so", ".bundle", ".metallib")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def relative(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def notice(path: Path) -> bool:
    return path.name.lower().startswith(NOTICE_PREFIXES)


def native(path: Path) -> bool:
    return path.name.endswith(NATIVE_SUFFIXES) or ".so." in path.name


def copy(source: Path, destination: Path, output: Path) -> dict:
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)
    return {"path": relative(destination, output), "sha256": digest(source), "bytes": source.stat().st_size}


def record_hash(value: str) -> str | None:
    if not value.startswith("sha256="):
        return None
    try:
        value = value.removeprefix("sha256=")
        return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4)).hex()
    except ValueError:
        return None


def metadata(path: Path) -> dict:
    result: dict[str, str] = {}
    for line in path.read_text(errors="replace").splitlines():
        if ": " not in line:
            continue
        key, value = line.split(": ", 1)
        if key in {"Name", "Version", "License", "License-Expression"}:
            result.setdefault(key, value)
    return result


def collect_wheels(site: Path, output: Path) -> tuple[list[dict], dict[str, dict], dict[str, dict]]:
    distributions: list[dict] = []
    by_path: dict[str, dict] = {}
    by_hash: dict[str, dict] = {}
    for info in sorted(site.glob("*.dist-info"), key=lambda item: item.name.lower()):
        meta, record = info / "METADATA", info / "RECORD"
        if not meta.is_file() or not record.is_file():
            continue
        fields = metadata(meta)
        name = fields.get("Name", info.name.rsplit("-", 1)[0])
        notices = [
            copy(source, output / "python" / name / source.relative_to(info), output)
            for source in sorted(info.rglob("*"))
            if source.is_file() and notice(source)
        ]
        distributions.append({
            "name": name,
            "version": fields.get("Version", "UNKNOWN"),
            "license_expression": fields.get("License-Expression") or fields.get("License") or "UNDECLARED_IN_METADATA",
            "notices": notices,
        })
        for row in csv.reader(record.read_text(errors="replace").splitlines()):
            if len(row) < 2 or not row[0]:
                continue
            source = site / row[0]
            expected = record_hash(row[1])
            if not source.is_file() or expected is None or digest(source) != expected:
                continue
            owner = {
                "owner": name,
                "version": fields.get("Version", "UNKNOWN"),
                "wheel_record_path": row[0],
                "wheel_record_sha256": expected,
                "notices": notices,
            }
            by_path.setdefault(row[0], owner)
            by_hash.setdefault(expected, owner)
    return distributions, by_path, by_hash


def toc(path: Path) -> dict[str, tuple[Path, str]]:
    try:
        value = ast.literal_eval(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError, ValueError) as exc:
        raise SystemExit(f"invalid PyInstaller TOC: {exc}") from exc
    entries = value[0] if isinstance(value, tuple) and len(value) == 1 else value
    if not isinstance(entries, list):
        raise SystemExit("invalid PyInstaller TOC: expected a list")
    output: dict[str, tuple[Path, str]] = {}
    for entry in entries:
        if not (isinstance(entry, tuple) and len(entry) >= 3 and isinstance(entry[0], str) and isinstance(entry[1], str) and isinstance(entry[2], str)):
            continue
        output[entry[0]] = (Path(entry[1]), entry[2])
    return output


def external_notices(retained: Path, cpython: Path, openssl: Path, output: Path) -> dict[str, list[dict]]:
    required = {
        "CPython-3.12": cpython,
        "OpenSSL-3": openssl,
        "SQLite": retained / "SQLITE-PUBLIC-DOMAIN.txt",
        "mpdecimal": retained / "MPDECIMAL-BSD-2-CLAUSE.txt",
    }
    result: dict[str, list[dict]] = {}
    for name, source in required.items():
        if not source.is_file():
            raise SystemExit(f"required retained notice missing: {source}")
        result[name] = [copy(source, output / "external" / name / source.name, output)]
    return result


def source_owner(destination: str, source: Path, site: Path, owners: dict[str, dict], external: dict[str, list[dict]]) -> dict | None:
    try:
        site_path = source.resolve().relative_to(site.resolve()).as_posix()
    except (OSError, ValueError):
        site_path = None
    if site_path and site_path in owners:
        return {**owners[site_path], "origin": "wheel RECORD and PyInstaller COLLECT-00.toc"}
    if destination.startswith("python3.12/") or destination.startswith("libpython3.12"):
        return {"owner": "CPython-3.12", "version": "3.12", "origin": "PyInstaller COLLECT-00.toc", "notices": external["CPython-3.12"]}
    if destination in {"libcrypto.3.dylib", "libssl.3.dylib"}:
        return {"owner": "OpenSSL-3", "version": "3", "origin": "PyInstaller COLLECT-00.toc", "notices": external["OpenSSL-3"]}
    if destination == "libsqlite3.dylib":
        return {"owner": "SQLite", "version": "UNKNOWN", "origin": "PyInstaller COLLECT-00.toc", "notices": external["SQLite"]}
    if destination == "libmpdec.4.dylib":
        return {"owner": "mpdecimal", "version": "4", "origin": "PyInstaller COLLECT-00.toc", "notices": external["mpdecimal"]}
    return None


def native_inventory(bundle: Path, site: Path, toc_rows: dict[str, tuple[Path, str]], owners: dict[str, dict], external: dict[str, list[dict]]) -> list[dict]:
    rows: list[dict] = []
    for file in sorted(item for item in bundle.rglob("*") if item.is_file() and native(item)):
        path = relative(file, bundle)
        # The PyInstaller COLLECT file is rooted at `_internal`, while a
        # one-dir worker stores that collection below its executable wrapper.
        toc_path = path.removeprefix("_internal/")
        toc_entry = toc_rows.get(path) or toc_rows.get(toc_path)
        if toc_entry is None:
            rows.append({"path": path, "packaged_sha256": digest(file), "owner": "UNMAPPED", "reason": "absent from COLLECT-00.toc"})
            continue
        source, kind = toc_entry
        owner = source_owner(toc_path, source, site, owners, external)
        if owner is None:
            rows.append({"path": path, "packaged_sha256": digest(file), "owner": "UNMAPPED", "reason": "TOC source has no verified wheel or retained external notice", "toc_kind": kind})
            continue
        rows.append({
            "path": path,
            "packaged_sha256": digest(file),
            "owner": owner["owner"],
            "version": owner["version"],
            "origin": owner["origin"],
            "toc_kind": kind,
            "wheel_record_path": owner.get("wheel_record_path"),
            "wheel_record_sha256": owner.get("wheel_record_sha256"),
            "notices": owner["notices"],
        })
    # PyInstaller can emit a second top-level copy of a library already
    # collected below a package directory.  Its TOC has one source record, so
    # retain the checksum relationship instead of inventing a second owner.
    mapped_by_hash = {row["packaged_sha256"]: row for row in rows if row["owner"] != "UNMAPPED"}
    for row in rows:
        if row["owner"] != "UNMAPPED" or row["packaged_sha256"] not in mapped_by_hash:
            continue
        target = mapped_by_hash[row["packaged_sha256"]]
        row.update({
            "owner": target["owner"],
            "version": target["version"],
            "origin": "checksum duplicate of TOC-mapped payload",
            "toc_kind": target["toc_kind"],
            "wheel_record_path": target.get("wheel_record_path"),
            "wheel_record_sha256": target.get("wheel_record_sha256"),
            "notices": target["notices"],
        })
        row.pop("reason", None)
    return rows


def hidden_metadata_gaps(bundle: Path, inventory: list[dict]) -> list[str]:
    copied = {
        metadata(item / "METADATA").get("Name", item.name).lower().replace("_", "-")
        for item in (bundle / "_internal").glob("*.dist-info")
        if (item / "METADATA").is_file()
    }
    owners = {row["owner"].lower().replace("_", "-") for row in inventory if row["owner"] not in {"UNMAPPED", "CPython-3.12", "OpenSSL-3", "SQLite", "mpdecimal"}}
    return sorted(owners - copied)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worker", type=Path, required=True, help="qwen-worker directory, not a source tree")
    parser.add_argument("--site-packages", type=Path, required=True)
    parser.add_argument("--pyinstaller-toc", type=Path, required=True)
    parser.add_argument("--cpython-license", type=Path, required=True)
    parser.add_argument("--openssl-license", type=Path, required=True)
    parser.add_argument("--retained-notices", type=Path, default=Path("desktop/licenses/qwen"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit(f"refusing to overwrite existing output: {args.output}")
    if not args.worker.is_dir() or not args.site_packages.is_dir() or not args.pyinstaller_toc.is_file():
        raise SystemExit("worker, site-packages, and PyInstaller TOC must exist")

    args.output.mkdir(parents=True)
    distributions, owners, _ = collect_wheels(args.site_packages, args.output)
    external = external_notices(args.retained_notices, args.cpython_license, args.openssl_license, args.output)
    inventory = native_inventory(args.worker, args.site_packages, toc(args.pyinstaller_toc), owners, external)
    unmapped = [row["path"] for row in inventory if row["owner"] == "UNMAPPED"]
    manifest = {
        "scope": "qwen-worker-runtime only; excludes model weights, adapters, datasets, and training records",
        "python_distributions": distributions,
        "external_runtime_notices": external,
        "native_payloads": inventory,
        "hidden_import_metadata_gaps": hidden_metadata_gaps(args.worker, inventory),
        "gate": {"passed": not unmapped, "unmapped_native_payloads": unmapped},
    }
    (args.output / "MANIFEST.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"wrote {args.output / 'MANIFEST.json'}; native gate={'passed' if not unmapped else 'failed'}")
    if unmapped:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
