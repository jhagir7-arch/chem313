#!/bin/bash
# Create a drag-to-Applications DMG and app ZIP from a verified standalone build.
set -euo pipefail
cd "$(dirname "$0")/.."
APP="${1:-dist/chem313/Chem313.app}"
PREFIX="${2:-dist/chem313/Chem313-$(.venv/bin/python scripts/sync_version.py --print)-Mac-arm64}"
if [ -e "$PREFIX.dmg" ] || [ -e "$PREFIX.zip" ]; then echo "Package output exists: $PREFIX" >&2; exit 1; fi
codesign --verify --deep --strict "$APP"
.venv/bin/python - "$APP" <<'PY'
import hashlib, json, sys
from pathlib import Path
app = Path(sys.argv[1]); notices = app/'Contents/Resources/licenses/standalone-core'
manifest = json.loads((notices/'MANIFEST.json').read_text())
assert manifest['gate']['passed'], manifest['gate']
for row in manifest['bundle_native_files']:
    assert hashlib.sha256((app/row['path']).read_bytes()).hexdigest() == row['packaged_sha256'], row['path']
assert not any((app/'Contents/Resources'/name).exists() for name in ('models','workers','avogadro'))
assert (app/'Contents/Resources/engine/_internal/bundle.json').is_file()
print('Native payload checksums and standalone capability profile verified')
PY
mkdir -p "$(dirname "$PREFIX")"
STAGE="$(mktemp -d "${TMPDIR:-/tmp}/OpenChem-dmg.XXXXXX")"
trap 'rm -rf "$STAGE"' EXIT
cp -R "$APP" "$STAGE/Chem313.app"
cp release/standalone/README.txt "$STAGE/README.txt"
ln -s /Applications "$STAGE/Applications"
hdiutil create -volname 'Chem313 Research Preview' -srcfolder "$STAGE" -ov -format UDZO "$PREFIX.dmg"
ditto -c -k --sequesterRsrc --keepParent "$APP" "$PREFIX.zip"
shasum -a 256 "$PREFIX.dmg" "$PREFIX.zip" > "$PREFIX-SHA256SUMS.txt"
hdiutil verify "$PREFIX.dmg"
echo "Created $PREFIX.dmg and $PREFIX.zip"
