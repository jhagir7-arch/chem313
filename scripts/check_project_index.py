#!/usr/bin/env python3
"""Check that Chem313's maintained project index resolves in a source tree.

This is a documentation-integrity check. It does not execute application code
or make any claim about scientific validity.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path


LINK = re.compile(r"\[[^]]+\]\(([^)]+)\)")
FEATURE_ROW = re.compile(r"^\| `(?P<id>CHEM-\d{3})`")
CATALOG_ID = re.compile(r"id:'(CHEM-\d{3})'")
CATALOG_EVIDENCE = re.compile(r"evidence:'([^']+)'")


def relative_path(destination: str) -> Path:
    """Return a safe project-relative path from an index or catalog reference."""
    path = Path(destination)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"unsafe non-local path: {destination}")
    if not destination or destination == ".":
        raise ValueError(f"empty or root path is not an indexed file: {destination!r}")
    return path


def local_links(text: str) -> list[Path]:
    paths: list[Path] = []
    for destination in LINK.findall(text):
        destination = destination.strip()
        if destination.startswith(("http://", "https://", "mailto:", "#")):
            continue
        if "#" in destination:
            destination = destination.split("#", 1)[0]
        paths.append(relative_path(destination))
    return paths


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root", type=Path, default=Path(__file__).resolve().parents[1],
        help="source-tree root to validate (default: this script's project root)",
    )
    args = parser.parse_args()
    root = args.root.resolve()
    index = root / "PROJECT_INDEX.md"
    feature_catalog = root / "frontend/src/featureIndex.mjs"
    frontend_package = root / "frontend/package.json"
    errors: list[str] = []
    if not index.is_file():
        errors.append("missing PROJECT_INDEX.md")
        text = ""
    else:
        text = index.read_text(encoding="utf-8")
        if "/" + "Users/" in text:
            errors.append("index contains an absolute machine path")
        if re.search(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b", text):
            errors.append("index contains an email address")

        feature_ids = {
            match.group("id")
            for line in text.splitlines()
            if (match := FEATURE_ROW.match(line))
        }
        if not feature_catalog.is_file():
            errors.append("missing frontend/src/featureIndex.mjs")
            catalog_ids: set[str] = set()
            catalog_evidence: set[Path] = set()
        else:
            catalog_text = feature_catalog.read_text(encoding="utf-8")
            catalog_ids = set(CATALOG_ID.findall(catalog_text))
            try:
                catalog_evidence = {relative_path(path) for path in CATALOG_EVIDENCE.findall(catalog_text)}
            except ValueError as exc:
                errors.append(str(exc))
                catalog_evidence = set()
        if catalog_ids != feature_ids:
            errors.append(
                "documented feature IDs do not match frontend/src/featureIndex.mjs: "
                f"documented {sorted(feature_ids)}, catalog {sorted(catalog_ids)}"
            )
        if not frontend_package.is_file():
            errors.append("missing frontend/package.json")
        else:
            package_version = json.loads(frontend_package.read_text(encoding="utf-8"))["version"]
            if f"Chem313 {package_version}" not in text:
                errors.append(f"index version does not match frontend package version {package_version!r}")

        try:
            indexed_paths = local_links(text)
        except ValueError as exc:
            errors.append(str(exc))
            indexed_paths = []
        for relative in indexed_paths:
            target = root / relative
            if not target.exists():
                errors.append(f"missing indexed path: {relative.as_posix()}")
        for relative in catalog_evidence:
            target = root / relative
            if not target.exists():
                errors.append(f"missing feature-catalog evidence path: {relative.as_posix()}")

    if errors:
        for error in errors:
            print(f"PROJECT_INDEX FAIL: {error}", file=sys.stderr)
        return 1
    print(f"PROJECT_INDEX PASS: links, catalog IDs/evidence, and package version resolve under {root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
