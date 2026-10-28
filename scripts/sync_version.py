#!/usr/bin/env python3
"""Propagate hypothesislab.__version__, the only hand-edited version, and regenerate the API contracts.

Change the version in backend/src/hypothesislab/__init__.py, then run this script.
--check reports stale files without writing (CI); --print echoes the version for shell scripts."""
import argparse
import json
import os
from pathlib import Path
import re
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
INIT = ROOT / 'backend/src/hypothesislab/__init__.py'


def package_version() -> str:
    match = re.search(r'^__version__ = "([^"]+)"$', INIT.read_text(encoding='utf-8'), re.M)
    if not match:
        raise SystemExit(f'No __version__ assignment in {INIT}')
    return match.group(1)


def contracts(data_dir: str) -> dict:
    """Build the base contract, then register routes in desktop.main() order for the desktop contract."""
    os.environ['HYPOTHESISLAB_DATA'] = data_dir  # never touch real user projects
    sys.path.insert(0, str(ROOT / 'backend/src'))
    from hypothesislab import api, desktop
    from hypothesislab.science_api import register as register_science
    from hypothesislab.calculation_api import register as register_calculations
    from hypothesislab.study_api import register as register_studies
    from hypothesislab.qchem_api import register as register_qchem
    base = api.app.openapi()
    for register in (register_science, register_calculations, register_studies, register_qchem, desktop.register_desktop):
        register(api.app, api)
    api.app.openapi_schema = None
    return {'contracts/openapi.generated.json': base, 'contracts/desktop.openapi.generated.json': api.app.openapi()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='exit 1 if any file is stale; write nothing')
    parser.add_argument('--print', action='store_true', help='print the version and exit')
    args = parser.parse_args()
    version = package_version()
    if args.print:
        print(version)
        return
    expected = {}
    # app/src-tauri/tauri.conf.json reads its version from app/package.json, so the shell is covered too.
    for name in ('frontend/package.json', 'frontend/package-lock.json', 'app/package.json', 'app/package-lock.json'):
        data = json.loads((ROOT / name).read_text(encoding='utf-8'))
        data['version'] = version
        if 'packages' in data:
            data['packages']['']['version'] = version
        expected[name] = data
    with tempfile.TemporaryDirectory(prefix='chem313-contracts-') as data_dir:
        expected.update(contracts(data_dir))
    rendered = {name: json.dumps(data, indent=2) + '\n' for name, data in expected.items()}

    def is_stale(name: str) -> bool:
        current = (ROOT / name).read_text(encoding='utf-8')
        if name.endswith('package-lock.json'):
            # npm rewrites the lockfile in its own formatting; only the version fields matter here.
            data = json.loads(current)
            return data.get('version') != version or data.get('packages', {}).get('', {}).get('version') != version
        return current != rendered[name]

    stale = [name for name in rendered if is_stale(name)]
    if args.check:
        if stale:
            sys.exit(f'Stale for version {version}: ' + ', '.join(stale) + '\nRun: python scripts/sync_version.py')
        print(f'{version}: all derived files current')
        return
    for name in stale:
        (ROOT / name).write_text(rendered[name], encoding='utf-8')
    print(f'{version}: updated ' + (', '.join(stale) if stale else 'nothing'))


if __name__ == '__main__':
    main()
