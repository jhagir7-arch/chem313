#!/bin/bash
# Build on Apple Silicon; recipients need no Python, Node or package manager.
set -euo pipefail
cd "$(dirname "$0")/.."
OUT="${1:-dist/standalone/Chem313.app}"
BUILD="${OPENCHEM_STANDALONE_BUILD_DIR:-build/standalone}"
if [ -e "$OUT" ]; then echo "Output already exists: $OUT" >&2; exit 1; fi
if [ "$(uname -s)" != Darwin ] || [ "$(uname -m)" != arm64 ]; then
  echo "Build this target on Apple Silicon macOS." >&2; exit 1
fi
mkdir -p "$BUILD"
npm --prefix frontend run build
.venv/bin/python scripts/standalone_profile.py "$BUILD/bundle.json"
.venv/bin/python -m PyInstaller --noconfirm --clean --name openchem-engine \
  --paths backend/src --distpath "$BUILD/engine-dist" --workpath "$BUILD/pyinstaller" \
  --specpath "$BUILD" --add-data "$PWD/frontend/dist:ui" --add-data "$PWD/$BUILD/bundle.json:." \
  --collect-data rdkit --copy-metadata rdkit --copy-metadata numpy --copy-metadata scipy \
  --hidden-import rdkit.Chem.rdDetermineBonds --hidden-import rdkit.Chem.inchi --hidden-import rdkit.Chem.AllChem --hidden-import rdkit.Chem.Draw \
  --hidden-import matplotlib.backends.backend_agg --hidden-import matplotlib.backends.backend_svg \
  --hidden-import uvicorn.logging --hidden-import uvicorn.loops.auto \
  --hidden-import uvicorn.protocols.http.auto --hidden-import uvicorn.protocols.http.h11_impl \
  --hidden-import uvicorn.protocols.websockets.auto --hidden-import uvicorn.lifespan.on \
  --exclude-module tkinter --exclude-module pytest --exclude-module IPython \
  --exclude-module pandas --exclude-module torch --exclude-module PyQt5 --exclude-module PySide6 \
  desktop/service.py > "$BUILD/freeze.log" 2>&1
mkdir -p "$OUT/Contents/MacOS" "$OUT/Contents/Resources/engine"
swiftc -target arm64-apple-macos14.0 -O -framework AppKit -framework WebKit desktop/OpenChem.swift -o "$OUT/Contents/MacOS/OpenChem"
cp desktop/Info.plist "$OUT/Contents/Info.plist"
/usr/libexec/PlistBuddy -c 'Set :CFBundleIdentifier org.openchem.workbench.preview' "$OUT/Contents/Info.plist"
/usr/libexec/PlistBuddy -c 'Set :CFBundleShortVersionString 1.0.0-preview.6' "$OUT/Contents/Info.plist"
/usr/libexec/PlistBuddy -c 'Set :CFBundleVersion 26' "$OUT/Contents/Info.plist"
/usr/libexec/PlistBuddy -c 'Add :OpenChemStandalone bool true' "$OUT/Contents/Info.plist"
cp -R "$BUILD/engine-dist/openchem-engine/" "$OUT/Contents/Resources/engine/"
if [ -f desktop/OpenChem.icns ]; then cp desktop/OpenChem.icns "$OUT/Contents/Resources/"; fi
cp LICENSE NOTICE THIRD_PARTY_NOTICES.md release/standalone/README.txt "$OUT/Contents/Resources/"
.venv/bin/python scripts/collect_standalone_licenses.py \
  --site-packages .venv/lib/python3.13/site-packages --package-lock frontend/package-lock.json \
  --ui-provenance frontend/dist/ui-provenance.json --node-modules frontend/node_modules --bundle "$OUT" --pyinstaller-toc "$BUILD/pyinstaller/openchem-engine/COLLECT-00.toc" --output "$OUT/Contents/Resources/licenses/standalone-core"
# PyInstaller signs embedded Mach-O files during collection. Sign the outer app last.
codesign --force --sign - "$OUT"
codesign --verify --deep --strict "$OUT"
echo "Standalone app built: $OUT"
