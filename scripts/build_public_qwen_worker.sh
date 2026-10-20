#!/bin/bash
# Freeze a public base-only offline Qwen runtime. No training data or adapter.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="${QWEN_BUILD_PYTHON:-$ROOT/.venv-qwen-release/bin/python}"
WORKER_DIR="$ROOT/build/qwen-release/workers/qwen-worker"
WORKER="$WORKER_DIR/qwen-worker"
cd "$ROOT"
mkdir -p build/qwen-release
"$PYTHON" -m PyInstaller --noconfirm --clean --onedir --name qwen-worker \
  --paths "$ROOT/backend/src" \
  --distpath "$ROOT/build/qwen-release/workers" \
  --workpath "$ROOT/build/qwen-release/pyinstaller" \
  --specpath "$ROOT/build/qwen-release" \
  --collect-all mlx \
  --collect-data mlx_lm \
  --collect-submodules mlx_lm.models.qwen3_5 \
  --collect-submodules mlx_lm.tuner \
  --hidden-import mlx_lm.tool_parsers.qwen3_coder \
  --hidden-import transformers.models.qwen2.tokenization_qwen2 \
  --hidden-import transformers.models.qwen3_5.configuration_qwen3_5 \
  --hidden-import transformers.models.qwen3_5.tokenization_qwen3_5 \
  --collect-all tokenizers \
  --collect-all safetensors \
  --collect-all sentencepiece \
  --copy-metadata mlx --copy-metadata mlx-lm --copy-metadata transformers \
  --copy-metadata brotli --copy-metadata hf-xet --copy-metadata httptools \
  --copy-metadata orjson --copy-metadata uvloop --copy-metadata watchfiles \
  --copy-metadata tokenizers --copy-metadata safetensors --copy-metadata sentencepiece \
  --exclude-module torch --exclude-module torchvision --exclude-module torchaudio \
  --exclude-module tensorflow --exclude-module jax --exclude-module flax \
  --exclude-module pytest --exclude-module IPython --exclude-module tkinter \
  "$ROOT/desktop/qwen_service.py"

[[ -x "$WORKER" ]] || { echo "Frozen Qwen worker was not produced" >&2; exit 1; }
[[ -f "$WORKER_DIR/_internal/mlx/lib/mlx.metallib" ]] || { echo "MLX metallib missing from worker" >&2; exit 1; }
[[ -f "$WORKER_DIR/_internal/mlx/lib/libmlx.dylib" ]] || { echo "MLX dylib missing from worker" >&2; exit 1; }

echo "Public Qwen runtime built: $WORKER_DIR"
