#!/usr/bin/env python3
"""Stage a source-only release candidate. This never publishes. See LICENSE and NOTICE for the grant boundary."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import zipfile

ROOT = Path(__file__).resolve().parents[1]
TREES = ('backend/src', 'backend/tests', 'frontend/src', 'frontend/test',
         'frontend/scripts', 'native', 'environments', 'examples', 'release/public-source',
         'release/standalone', 'release/portable', 'release/qwen', 'desktop/licenses/standalone-npm', 'desktop/licenses/qwen',
         'desktop/licenses/portable-runtime')
FILES = ('PROJECT_INDEX.md', 'CONTRIBUTING.md', 'docs/COMMUNITY.md', 'scripts/check_project_index.py', 'scripts/native_chem313_workflow.js', 'scripts/native_first_calculation_workflow.js', 'backend/pyproject.toml', 'frontend/package.json', 'frontend/package-lock.json',
         'frontend/tsconfig.json', 'frontend/vite.config.ts', 'frontend/index.html',
         'desktop/OpenChem.swift', 'desktop/Info.plist', 'desktop/service.py', 'desktop/portable.py',
         'desktop/science_service.py', 'desktop/extended_service.py',
         'desktop/bioscience_service.py', 'desktop/qwen_service.py',
         'scripts/build_public_app.sh', 'scripts/setup_public_runtime.sh',
         'scripts/build_standalone_app.sh', 'scripts/package_standalone_mac.sh',
         'scripts/build_portable.py', 'scripts/test_build_portable.py', 'scripts/prepare_linux_runtime_sources.py', 'scripts/test_prepare_linux_runtime_sources.py', 'scripts/test_portable_package.py',
         'scripts/build_public_qwen_worker.sh', 'scripts/assemble_qwen_app.py',
         'scripts/package_qwen_mac.sh', 'scripts/collect_qwen_licenses.py',
         'release/qwen/requirements-lock.txt',
         'scripts/standalone_profile.py', 'scripts/collect_standalone_licenses.py',
         'scripts/audit_standalone_binary.py', 'scripts/test_standalone_package.py',
         'scripts/native_standalone_workflow.js', 'desktop/OpenChem.icns',
         'scripts/render_app_icon.swift', 'desktop/branding/OpenChem.png',
         'desktop/licenses/indigo-ketcher/LICENSE',
         'scripts/test_packaged_engine.py', 'scripts/native_public_workflow.js',
         'desktop/requirements-lock.txt', 'scripts/install_engines.sh', 'scripts/build_science_workers.sh',
         'scripts/build_bioscience_worker.sh', 'scripts/test_science_engines.py',
         'scripts/test_extended_engines.py', 'scripts/test_bioscience_engines.py',
         'scripts/package_public_source.py', 'benchmarks/run.py', 'benchmarks/verify_bundle.py',
         'contracts/openapi.generated.json', 'contracts/desktop.openapi.generated.json',
         'contracts/tool-actions.schema.json', 'contracts/example-fit.json',
         'contracts/SOURCE_LOCK.json', 'contracts/UPSTREAM_COMPONENTS.json',
         'contracts/COMPETITOR_CHALLENGE.csv', 'contracts/reference_registry/FEATURE_REGISTRY_v0.1.json')
EXCLUDED = {'__pycache__', '.pytest_cache', 'node_modules', '.DS_Store', 'public'}


def eligible(relative):
    return not any(p in EXCLUDED or p.endswith('.egg-info') for p in relative.parts) and relative.suffix not in {'.pyc', '.pyo'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    destination = args.output.resolve()
    if destination.exists():
        parser.error('Output exists; choose a new path to preserve previous snapshots')
    destination.mkdir(parents=True)
    paths = {ROOT / name for name in FILES}
    for name in TREES:
        paths.update(p for p in (ROOT / name).rglob('*') if p.is_file())
    for path in sorted(paths):
        relative = path.relative_to(ROOT)
        if not eligible(relative):
            continue
        if path.is_symlink() or not path.is_file():
            raise ValueError('Missing or symlinked source: ' + str(relative))
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
    for path in sorted((ROOT / 'release/public-source').rglob('*')):
        if path.is_file():
            if path.name == 'CONTRIBUTING.md':
                continue
            if path.is_symlink():
                raise ValueError('Symlinked release document')
            target = destination / path.relative_to(ROOT / 'release/public-source')
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
    rows = []
    violations = []
    for path in sorted(destination.rglob('*')):
        if not path.is_file():
            continue
        relative = path.relative_to(destination).as_posix()
        raw = path.read_bytes()
        for marker in (b'/Users/', b'drive.google.com/', b'docs.google.com/', b'ghp_', b'github_pat_', b'-----BEGIN PRIVATE KEY-----'):
            if marker in raw:
                # The scanner's literal patterns are code, not leaked data.
                if relative != 'scripts/package_public_source.py':
                    violations.append({'file': relative, 'marker': marker.decode()})
        rows.append({'path': relative, 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()})
    if violations:
        raise ValueError('Public source scan failed: ' + json.dumps(violations))
    manifest = {'schema': 'openchem.public-source-candidate.v1', 'code_version': '1.0.0-preview.6',
                'publication_status': 'PUBLIC_RESEARCH_PREVIEW',
                'scope': 'Source only. No compiled application or installed engines.',
                'excluded': ['Git history', 'Private Drive receipts and handoff archives',
                             'Generated browser bundles', 'Installed dependencies',
                             'Public fixtures with unresolved redistribution rights',
                             'Avogadro and ORCA binaries', 'Qwen weights and adapter',
                             'Training datasets', 'Researcher projects', 'Local runtime evidence'],
                'files': rows}
    (destination / 'BUNDLE_MANIFEST.json').write_text(json.dumps(manifest, indent=2) + '\n')
    archive_path = destination.parent / (destination.name + '.zip')
    with zipfile.ZipFile(archive_path, 'x', zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(destination.rglob('*')):
            if path.is_file():
                archive.write(path, Path(destination.name) / path.relative_to(destination))
    if archive_path.stat().st_size >= 200_000_000:
        raise ValueError('Source archive exceeds 200 MB')
    with zipfile.ZipFile(archive_path) as archive:
        if archive.testzip() is not None:
            raise ValueError('ZIP CRC verification failed')
    digest = hashlib.sha256(archive_path.read_bytes()).hexdigest()
    archive_path.with_suffix('.zip.sha256').write_text(digest + '  ' + archive_path.name + '\n')
    print(json.dumps({'status': 'STAGED_NOT_PUBLISHED', 'path': str(destination),
                      'archive': str(archive_path), 'bytes': archive_path.stat().st_size,
                      'files': len(rows), 'sha256': digest}, indent=2))


if __name__ == '__main__':
    main()
