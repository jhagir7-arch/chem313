#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [ "$(uname -m)" != arm64 ] || [ "$(uname -s)" != Darwin ]; then
  echo "These environment locks were verified on macOS arm64 only." >&2; exit 1
fi
command -v uv >/dev/null || { echo "Install uv first: https://docs.astral.sh/uv/getting-started/installation/" >&2; exit 1; }
uv venv --allow-existing --python 3.13 .venv
uv pip sync --python .venv/bin/python environments/core-macos-arm64.lock --only-binary=:all:
uv pip install --python .venv/bin/python --no-deps -e backend
uv venv --allow-existing --python 3.13 .engines/science
uv pip sync --python .engines/science/bin/python environments/science-macos-arm64.lock --only-binary=:all:
uv venv --allow-existing --python 3.12 .engines/extended
uv pip sync --python .engines/extended/bin/python environments/extended-macos-arm64.lock --only-binary=:all:
uv venv --allow-existing --python 3.12 .engines/bioscience
uv pip sync --python .engines/bioscience/bin/python environments/bioscience-macos-arm64.lock --only-binary=:all:
npm --prefix frontend ci
PYTHONPATH=backend/src .venv/bin/python -m pytest backend/tests -q
PYTHONPATH=backend/src .engines/science/bin/python scripts/test_science_engines.py
PYTHONPATH=backend/src .engines/extended/bin/python scripts/test_extended_engines.py
PYTHONPATH=backend/src .engines/bioscience/bin/python scripts/test_bioscience_engines.py
echo "Environments installed and reference checks passed. Build the public native shell with bash scripts/build_public_app.sh."
