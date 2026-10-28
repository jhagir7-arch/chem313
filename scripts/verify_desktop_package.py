#!/usr/bin/env python3
"""Extract a native installer and verify its bundled notices and real engine.

Run on the package's own OS. No host Python/Node is needed by the installed app;
this release check uses build Python to drive the extracted runtime over HTTP.
"""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def run(*args, **kw):
    return subprocess.run([str(a) for a in args], check=True, **kw)


def verify_notices(folder):
    inventory = json.loads((folder / 'inventory.json').read_text(encoding='utf-8'))
    if inventory.get('errors'):
        raise RuntimeError(f"Incomplete notices: {inventory['errors']}")
    checked = set()
    def walk(value):
        if isinstance(value, dict):
            # Only notice copies use a relative path plus sha256 and bytes. Native
            # mappings use source_sha256/packaged_sha256 and are not notice files.
            if {'path', 'sha256', 'bytes'} <= value.keys():
                path = (folder / value['path']).resolve()
                if not path.is_relative_to(folder.resolve()):
                    raise RuntimeError('Notice path escapes resources')
                data = path.read_bytes()
                if len(data) != value['bytes'] or hashlib.sha256(data).hexdigest() != value['sha256']:
                    raise RuntimeError(f"Notice integrity failure: {value['path']}")
                checked.add(value['path'])
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)
    walk(inventory)
    if not checked:
        raise RuntimeError('No license texts verified')
    return len(checked)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('package', type=Path)
    parser.add_argument('report', type=Path)
    args = parser.parse_args()
    package, report = args.package.resolve(), args.report.resolve()
    report.parent.mkdir(parents=True, exist_ok=True)
    result = {'status': 'FAIL', 'package': package.name, 'platform': platform.platform(),
              'sha256': hashlib.sha256(package.read_bytes()).hexdigest(),
              'bytes': package.stat().st_size,
              'scope': 'Extracted installer resources and real bundled chemistry engine; does not assert GUI or OS signing acceptance'}
    try:
        with tempfile.TemporaryDirectory(prefix='chem313-package-') as temp:
            dest = Path(temp)
            if package.suffix == '.dmg':
                mount = dest / 'mounted'
                mount.mkdir()
                run('hdiutil', 'attach', package, '-readonly', '-nobrowse', '-mountpoint', mount)
                try:
                    apps = list(mount.glob('*.app'))
                    if len(apps) != 1:
                        raise RuntimeError('Expected one app in DMG')
                    run('ditto', apps[0], dest / 'Chem313.app')
                finally:
                    run('hdiutil', 'detach', mount)
            elif package.suffix == '.msi':
                run('msiexec.exe', '/a', package, '/qn', f'TARGETDIR={dest}')
            elif package.suffix == '.deb':
                run('dpkg-deb', '-x', package, dest)
            elif package.suffix == '.AppImage':
                package.chmod(package.stat().st_mode | 0o111)
                run(package, '--appimage-extract', cwd=dest, stdout=subprocess.DEVNULL)
            else:
                raise RuntimeError('Unsupported package format')
            executable = 'chem313-engine.exe' if sys.platform == 'win32' else 'chem313-engine'
            engines = [p for p in dest.rglob(executable) if p.is_file() and p.parent.name == 'engine']
            if len(engines) != 1:
                raise RuntimeError(f'Expected one packaged engine, found {len(engines)}')
            engine = engines[0]
            result['notice_files_verified'] = verify_notices(engine.parent.parent / 'notices')
            qa_path = dest / 'engine-qa.json'
            run(sys.executable, ROOT / 'scripts/test_v2_frozen_engine.py', engine, qa_path)
            result['engine_workflow'] = json.loads(qa_path.read_text(encoding='utf-8'))
            if result['engine_workflow']['status'] != 'PASS' or result['engine_workflow']['independent_energy']['status'] != 'PASS':
                raise RuntimeError('Bundled calculation or independent energy check did not pass')
            result['status'] = 'PASS'
    except Exception as exc:
        result['error'] = f'{type(exc).__name__}: {exc}'
    report.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, indent=2))
    return 0 if result['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
