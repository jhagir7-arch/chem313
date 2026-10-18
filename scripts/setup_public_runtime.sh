#!/bin/bash
# Install dependencies locally under their upstream licenses, never into the app.
set -euo pipefail
cd "$(dirname "$0")/.."
PYTHON="${OPENCHEM_SETUP_PYTHON:-python3.13}"
if [ -x .venv/bin/python ]; then PYTHON=.venv/bin/python; fi
command -v "$PYTHON" >/dev/null || { echo "Install Python 3.13 and retry." >&2; exit 1; }
"$PYTHON" -c 'import sys; assert sys.version_info[:2] == (3, 13), "Python 3.13 required"'
command -v npm >/dev/null || { echo "Install Node.js 24.20 or later and retry." >&2; exit 1; }
node -e 'const [a,b]=process.versions.node.split(".").map(Number); if(a<24||(a===24&&b<20))process.exit(1)' || { echo "Node.js 24.20 or later required." >&2; exit 1; }
if [ ! -d .venv ]; then "$PYTHON" -m venv .venv; fi
.venv/bin/python -m pip install -e 'backend[test]'
npm --prefix frontend ci
npm --prefix frontend run build
echo "Runtime ready. Open the native shell and choose this source folder."
echo "Optional engines, Avogadro, ORCA and Qwen are separate installations."
