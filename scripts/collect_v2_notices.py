#!/usr/bin/env python3
"""Collect v2 desktop notices from the installed build environment.

Run with the engine's Python after npm ci and cargo fetch. A nonzero exit reports
missing material; an inventory is written even on failure for review.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.metadata as metadata
import json
import re
import shutil
import subprocess
import sys
import sysconfig
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).parent))
import collect_standalone_licenses as standalone
from collect_standalone_licenses import (vendored_npm_notices, apache_fallback,
    collect_python, pyinstaller_toc, native, fonts)


def is_notice(path):
    """Recognize notice documents, not source files or prefix lookalikes."""
    name = path.name.lower()
    if path.suffix.lower() in {'.rs', '.c', '.h', '.cpp', '.js', '.ts', '.tsx', '.py', '.html', '.json'}:
        return False
    return bool(re.match(r'^(license|licence|notice|copying|copyright)(?:$|[._-])', name))

# Apply the same predicate to the reused native ownership collector.
standalone.is_notice = is_notice

def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def copy(source, dest, output):
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, dest)
    return {'path': dest.relative_to(output).as_posix(), 'sha256': sha256(dest), 'bytes': dest.stat().st_size}


def files(source):
    return sorted(p for p in source.rglob('*') if p.is_file() and is_notice(p) and 'node_modules' not in p.relative_to(source).parts)


def npm(app, output, root):
    rows, errors = [], []
    packages = json.loads((app / 'package-lock.json').read_text())['packages']
    for location, item in sorted(packages.items()):
        if not location.startswith('node_modules/') or item.get('dev') is True:
            continue
        source = app / location
        manifest = source / 'package.json'
        if not manifest.is_file():
            if not item.get('optional'): errors.append(f'npm package missing: {location}')
            continue
        data = json.loads(manifest.read_text())
        name, version = data['name'], data['version']
        if version != item.get('version'):
            errors.append(f'npm version mismatch: {location}')
        # Location rather than package name prevents nested versions from overwriting each other.
        target = output / 'npm' / location.removeprefix('node_modules/')
        notices = [copy(p, target / p.relative_to(source), output) for p in files(source)]
        if not notices:
            notices = vendored_npm_notices(name, target, output, root)
        if name.startswith('ketcher-'):
            # Only accept this fallback if source headers are actually present.
            fallback = apache_fallback(source, target, output, root)
            if any('APACHE_HEADER_SOURCES' in n['path'] for n in fallback):
                notices += fallback
        if not notices: errors.append(f'npm notice missing: {location}@{version}')
        rows.append({'location': location, 'name': name, 'version': version, 'license_expression': data.get('license'), 'notices': notices})
    return rows, errors


def rust_fallback(vendor, target, output, name, version, revision):
    """Accept only hash-verified notices matched to the packaged crate's source revision."""
    try:
        manifest = json.loads((vendor / 'provenance.json').read_text())
        if not manifest.get('complete') or (manifest['name'], manifest['version'], manifest['revision']) != (name, version, revision):
            return []
        entries = manifest['files']
        if not entries: return []
        for entry in entries:
            rel = Path(entry['path'])
            if rel.is_absolute() or '..' in rel.parts or not entry.get('url', '').startswith('https://') or sha256(vendor / rel) != entry['sha256']:
                return []
        notices = [copy(vendor / entry['path'], target / 'vendored' / entry['path'], output) for entry in entries]
        notices.append(copy(vendor / 'provenance.json', target / 'vendored' / 'provenance.json', output))
        return notices
    except (OSError, KeyError, ValueError, TypeError):
        return []


def rust(meta, output):
    rows, errors = [], []
    nodes = {n['id']: n for n in meta['resolve']['nodes']}
    # Exclude development-only edges while retaining build dependencies and proc macros.
    root = meta['resolve'].get('root')
    active = set()
    def visit(id):
        if id in active or id not in nodes: return
        active.add(id)
        for dep in nodes[id].get('deps', []):
            if any(k.get('kind') != 'dev' for k in dep.get('dep_kinds', [])):
                visit(dep['pkg'])
    if root: visit(root)
    else: active = set(nodes)
    for p in sorted(meta['packages'], key=lambda x: (x['name'], x['version'], x['id'])):
        if p['id'] not in active or not (p.get('source') or '').startswith('registry+'):
            continue
        source = Path(p['manifest_path']).parent
        target = output / 'rust' / f"{p['name']}-{p['version']}"
        candidates = files(source)
        if p.get('license_file'):
            f = source / p['license_file']
            if f.is_file() and f not in candidates: candidates.append(f)
        notices = [copy(f, target / f.relative_to(source), output) for f in sorted(candidates)]
        if not notices:
            try:
                revision = json.loads((source / '.cargo_vcs_info.json').read_text())['git']['sha1']
            except (OSError, KeyError, ValueError):
                revision = None
            vendor = ROOT / 'desktop' / 'licenses' / 'rust-v2' / f"{p['name']}-{p['version']}"
            notices = rust_fallback(vendor, target, output, p['name'], p['version'], revision)
        if not notices: errors.append(f"Rust notice missing: {p['name']}@{p['version']}")
        rows.append({'name': p['name'], 'version': p['version'], 'license_expression': p.get('license'), 'notices': notices})
    return rows, errors


def python_packages(output, root):
    from packaging.requirements import Requirement
    from packaging.utils import canonicalize_name
    distributions = {canonicalize_name(d.metadata['Name']): d for d in metadata.distributions() if d.metadata.get('Name')}
    queue = ['hypothesislab-local-core']
    seen, rows, errors = set(), [], []
    while queue:
        name = canonicalize_name(queue.pop())
        if name in seen: continue
        seen.add(name)
        d = distributions.get(name)
        if not d:
            errors.append(f'Python distribution missing: {name}'); continue
        for raw in d.requires or []:
            req = Requirement(raw)
            if not req.marker or req.marker.evaluate({'extra': ''}): queue.append(req.name)
        if name == 'hypothesislab-local-core': continue
        target = output / 'python' / f'{name}-{d.version}'
        candidates = []
        for item in d.files or []:
            if is_notice(Path(item.name)):
                f = Path(d.locate_file(item))
                if f.is_file(): candidates.append((f, Path(*[part for part in item.parts if part not in ('..', '.', '/')])))
        notices = [copy(f, target / rel, output) for f, rel in sorted(candidates, key=lambda x: str(x[1]))]
        if not notices:
            fallback = root / 'desktop' / 'licenses' / name
            if fallback.is_dir(): notices = [copy(f, target / 'vendored' / f.relative_to(fallback), output) for f in files(fallback)]
        if not notices: errors.append(f'Python notice missing: {name}@{d.version}')
        rows.append({'name': name, 'version': d.version, 'license_expression': d.metadata.get('License-Expression') or d.metadata.get('License'), 'notices': notices})
    return sorted(rows, key=lambda r: r['name']), errors


def bootloader(executable, license_file, version, output):
    row = {'pyinstaller_version': version, 'executable_sha256': None, 'notices': []}
    errors = []
    if not executable.is_file():
        errors.append('Frozen engine executable missing')
    else:
        row['executable_sha256'] = sha256(executable)
    if not license_file or not license_file.is_file() or 'Bootloader Exception' not in license_file.read_text(encoding='utf-8', errors='replace'):
        errors.append('Installed PyInstaller bootloader exception notice missing')
    else:
        row['notices'] = [copy(license_file, output / 'pyinstaller' / 'COPYING.txt', output)]
    return row, errors


def frozen_assets(bundle, toc_path, site, output, root, python_runtime):
    result = {'native': [], 'fonts': []}
    if not bundle.is_dir() or not toc_path.is_file() or not site.is_dir():
        return result, [f'Frozen engine, PyInstaller TOC, or Python site-packages missing: {bundle}, {toc_path}, {site}']
    _, owners = collect_python(site, output)
    toc = pyinstaller_toc(toc_path, site, owners, Path(sys.base_prefix), python_runtime, output, root)
    result['native'] = native(bundle, owners, python_runtime, toc)
    result['fonts'] = fonts(bundle, site, owners, output)
    errors = []
    for group in ('native', 'fonts'):
        for row in result[group]:
            if row.get('owner') == 'UNMAPPED' or not row.get('notices'):
                errors.append(f"Frozen {group} ownership or notice missing: {row['path']}")
    return result, errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'app/src-tauri/notices')
    parser.add_argument('--python-license', type=Path, help='license for the exact Python interpreter used to freeze')
    parser.add_argument('--bundle', type=Path, default=ROOT / 'app/src-tauri/engine')
    parser.add_argument('--toc', type=Path, default=ROOT / 'build/freeze-engine/work/chem313-engine/COLLECT-00.toc')
    args = parser.parse_args(); output = args.output.resolve()
    if output.exists() and any(output.iterdir()):
        raise SystemExit(f'output directory is not empty: {output}')
    output.mkdir(parents=True, exist_ok=True)
    errors = []
    project = [copy(ROOT / n, output / 'project' / n, output) for n in ('LICENSE', 'NOTICE') if (ROOT / n).is_file()]
    if len(project) != 2: errors.append('Project LICENSE or NOTICE missing')
    nr, ne = npm(ROOT / 'app', output, ROOT); errors += ne
    pr, pe = python_packages(output, ROOT); errors += pe
    rustc = subprocess.run(['rustc', '-vV'], check=True, capture_output=True, text=True).stdout
    host = next(line.split(': ', 1)[1] for line in rustc.splitlines() if line.startswith('host: '))
    command = ['cargo', 'metadata', '--locked', '--format-version', '1', '--filter-platform', host, '--manifest-path', str(ROOT / 'app/src-tauri/Cargo.toml')]
    meta = json.loads(subprocess.run(command, check=True, capture_output=True, text=True).stdout)
    rr, re = rust(meta, output); errors += re
    paths = [args.python_license, Path(sys.base_prefix) / 'LICENSE.txt', Path(sys.base_prefix) / 'LICENSE', Path(sysconfig.get_paths()['stdlib']) / 'LICENSE.txt']
    pylicense = next((p for p in paths if p and p.is_file()), None)
    py = [copy(pylicense, output / 'python-runtime' / pylicense.name, output)] if pylicense else []
    if not py: errors.append('CPython interpreter license missing; provide --python-license for the exact build interpreter')
    frozen, frozen_errors = frozen_assets(args.bundle, args.toc, Path(sysconfig.get_paths()['purelib']), output, ROOT, {'notices': py})
    errors += frozen_errors
    try:
        installer = metadata.distribution('pyinstaller')
        license_files = [Path(installer.locate_file(f)) for f in installer.files or [] if f.name == 'COPYING.txt' and 'dist-info' in str(f)]
        license_file = next((f for f in license_files if f.is_file()), None)
        version = installer.version
    except metadata.PackageNotFoundError:
        license_file, version = None, None
    executable = args.bundle / ('chem313-engine.exe' if sys.platform.startswith('win') else 'chem313-engine')
    boot, boot_errors = bootloader(executable, license_file, version, output)
    errors += boot_errors
    inventory = {'schema': 'chem313.v2-notices.v1', 'project': project, 'python_interpreter': {'version': sys.version.split()[0], 'notices': py}, 'npm': nr, 'python': pr, 'rust': rr, 'frozen_engine': frozen, 'pyinstaller_bootloader': boot, 'errors': errors,
      'limitations': ['Dependency closure is conservative, not a proof of emitted frontend or frozen Python contents.', 'Native mappings use wheel RECORD checksums and PyInstaller TOC source mappings; transformations and statically linked components require additional review.', 'Cargo metadata is filtered to the build host; verify statically linked native dependencies separately.', 'PyInstaller version and license come from the current build interpreter; freeze and collection must use the same environment.']}
    (output / 'inventory.json').write_text(json.dumps(inventory, indent=2, sort_keys=True) + '\n')
    for error in errors: print(error, file=sys.stderr)
    print(f'Wrote {output / "inventory.json"}: {len(errors)} unresolved gaps')
    return bool(errors)

if __name__ == '__main__': raise SystemExit(main())
