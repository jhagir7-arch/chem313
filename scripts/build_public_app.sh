#!/bin/bash
# Compile only OpenChem's native shell; no dependencies or generated UI are copied.
set -euo pipefail
cd "$(dirname "$0")/.."
OUT="${1:-dist/Chem313 Public.app}"
if [ -e "$OUT" ]; then echo "Output exists; choose a new path: $OUT" >&2; exit 1; fi
if [ "$(uname -s)" != Darwin ] || [ "$(uname -m)" != arm64 ]; then
  echo "This target requires Apple Silicon macOS and Xcode command-line tools." >&2; exit 1
fi
mkdir -p "$OUT/Contents/MacOS" "$OUT/Contents/Resources"
swiftc -target arm64-apple-macos14.0 -O -framework AppKit -framework WebKit desktop/Chem313.swift -o "$OUT/Contents/MacOS/Chem313"
cp desktop/Info.plist "$OUT/Contents/Info.plist"
cp desktop/Chem313.icns "$OUT/Contents/Resources/"
/usr/libexec/PlistBuddy -c 'Set :CFBundleIdentifier org.openchem.workbench.preview' "$OUT/Contents/Info.plist"
/usr/libexec/PlistBuddy -c 'Add :OpenChemExternalRuntime bool true' "$OUT/Contents/Info.plist"
cp LICENSE NOTICE THIRD_PARTY_NOTICES.md "$OUT/Contents/Resources/"
cp release/public-source/README.md release/public-source/SOURCE_ORIGIN.md "$OUT/Contents/Resources/"
codesign --force --sign - "$OUT"
codesign --verify --deep --strict "$OUT"
echo "Built native shell: $OUT (separate configured source runtime required)"
