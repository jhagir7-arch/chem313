#!/bin/bash
# Package the verified Qwen edition; never download private training material.
set -euo pipefail
cd "$(dirname "$0")/.."
APP="${1:-dist/qwen/OpenChem.app}"
PREFIX="${2:-dist/qwen/OpenChem-1.0.0-preview.2-Qwen-Mac-arm64}"
if [ -e "$PREFIX.dmg" ] || [ -e "$PREFIX.zip" ]; then echo "Output exists: $PREFIX" >&2; exit 1; fi
codesign --verify --deep --strict "$APP"
.venv/bin/python - "$APP" <<'PY'
import hashlib, json, sys
from pathlib import Path
sys.path.insert(0, 'backend/src')
from hypothesislab.qwen_worker import verify_assets
app=Path(sys.argv[1]); resources=app/'Contents/Resources'
def check(path, expected):
    assert hashlib.sha256(path.read_bytes()).hexdigest()==expected, path
for name, key, base in [('standalone-core','bundle_native_files',app),('qwen-runtime','native_payloads',resources/'workers/qwen')]:
    notices=resources/'licenses'/name
    manifest=json.loads((notices/'MANIFEST.json').read_text())
    assert manifest['gate']['passed'], manifest['gate']
    for row in manifest[key]:
        check(base/row['path'],row['packaged_sha256'])
assert not (resources/'models/qwen/adapter').exists()
verify_assets(resources/'models/qwen/public-model', None)
model_notices=resources/'licenses/qwen-model'
for name, sha in json.loads((model_notices/'MANIFEST.json').read_text())['notice_files_sha256'].items():
    check(model_notices/name,sha)
for file in app.rglob('*'):
    if file.is_symlink():
        assert file.resolve().is_relative_to(app.resolve()), file
print('Core/Qwen ownership manifests, model hashes and internal symlinks verified')
PY
mkdir -p "$(dirname "$PREFIX")"
STAGE="$(mktemp -d "${TMPDIR:-/tmp}/OpenChem-Qwen.XXXXXX")"
trap 'rm -rf "$STAGE"' EXIT
cp -R "$APP" "$STAGE/OpenChem.app"
cp release/qwen/README.txt "$STAGE/README.txt"
ln -s /Applications "$STAGE/Applications"
hdiutil create -volname 'OpenChem Qwen Preview' -srcfolder "$STAGE" -ov -format UDZO "$PREFIX.dmg"
ditto -c -k --sequesterRsrc --keepParent "$APP" "$PREFIX.zip"
shasum -a 256 "$PREFIX.dmg" "$PREFIX.zip" > "$PREFIX-SHA256SUMS.txt"
hdiutil verify "$PREFIX.dmg"
echo "Created $PREFIX.dmg and $PREFIX.zip"
