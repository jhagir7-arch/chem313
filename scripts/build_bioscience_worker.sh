#!/bin/bash
# Freeze only the bounded PyEnzyme/PySB worker for macOS arm64.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
if [[ -x "$ROOT/.engines/bioscience/bin/python" ]]; then
  PYTHON="$ROOT/.engines/bioscience/bin/python"
else
  PYTHON="$ROOT/.engines/probe/bin/python"
fi
SITE_PACKAGES="$("$PYTHON" -c 'import pathlib, bionetgen; print(pathlib.Path(bionetgen.__file__).resolve().parent)')"

cd "$ROOT"
"$PYTHON" -m PyInstaller --noconfirm --clean \
  --name bioscience-worker \
  --paths "$ROOT/backend/src" \
  --distpath "$ROOT/build/workers" \
  --workpath "$ROOT/build/pyinstaller-bioscience" \
  --specpath "$ROOT/build" \
  --collect-submodules pysb \
  --collect-submodules cement \
  --collect-data pysb \
  --copy-metadata pyenzyme \
  --copy-metadata pysb \
  --copy-metadata bionetgen \
  --add-data "$SITE_PACKAGES/assets:bionetgen/assets" \
  --add-data "$(dirname "$SITE_PACKAGES")/cement:cement" \
  --add-data "$SITE_PACKAGES/bng-mac:bionetgen/bng-mac" \
  "$ROOT/desktop/bioscience_service.py"
