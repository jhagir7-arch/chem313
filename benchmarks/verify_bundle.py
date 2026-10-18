#!/usr/bin/env python3
"""Verify the packaged snapshot without installing any dependencies."""
import hashlib
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
manifest = json.loads((root / 'BUNDLE_MANIFEST.json').read_text())
failures = []
for row in manifest['files']:
    relative = Path(row['path'])
    path = root / relative
    if relative.is_absolute() or '..' in relative.parts or path.is_symlink() or not path.is_file():
        failures.append(str(relative)); continue
    if path.stat().st_size != row['bytes'] or hashlib.sha256(path.read_bytes()).hexdigest() != row['sha256']:
        failures.append(str(relative))
if failures:
    raise SystemExit('FAIL: ' + ', '.join(failures))
print('PASS:', len(manifest['files']), 'packaged files match SHA-256 and size.')
