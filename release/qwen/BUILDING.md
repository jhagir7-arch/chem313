# Chem313 standalone Qwen edition

Recipients download the compiled app; these steps are only for maintainers.
Use an Apple Silicon Mac and Apple's command-line tools. Build the core as
in `release/standalone/BUILDING.md`, using a separate output path.

The public worker uses a portable managed CPython 3.12 interpreter. A local
Homebrew interpreter can embed a higher deployment target; inspect every
Mach-O file with `scripts/audit_standalone_binary.py` before distribution.

```sh
uv python install 3.12 --managed-python
uv venv --python 3.12 --managed-python .venv-qwen-release
uv pip install --python .venv-qwen-release/bin/python --no-deps -r release/qwen/requirements-lock.txt
bash scripts/build_public_qwen_worker.sh
bash scripts/build_standalone_app.sh dist/qwen/OpenChem.app
```

Obtain `Qwen/Qwen3.5-2B-Base` from the official Hugging Face repository at
revision `b1485b2fa6dfa1287294f269f5fb618e03d52d7c`, including its LICENSE,
model card, tokenizer and weights. Its original weights SHA-256 is
`928acbf11878c32185bbd863514d191769285065ab9ea14fbfe431303f5fdf2d`.
Do not use an unreviewed adapter or training archive.

Convert with the locked worker environment:

```sh
.venv-qwen-release/bin/python -m mlx_lm convert --hf-path BASE_MODEL_DIRECTORY --mlx-path build/qwen-release/model-4bit -q --q-bits 4 --q-group-size 64
```

`scripts/assemble_qwen_app.py --help` lists its explicit inputs: core app,
converted model, original upstream model directory, frozen worker, exact
worker site-packages and PyInstaller COLLECT-00.toc, and retained CPython
and OpenSSL license texts. It verifies all pinned converted model files,
adds the upstream license/model card/transformation notice, generates the
worker ownership manifest, and signs the outer app ad-hoc. It refuses to
replace existing workers or model directories. It sets the Qwen edition's
minimum OS to macOS 26.2, required by the bundled MLX binary.

Run the backend/frontend tests, the packaged service test, binary audit,
and the opt-in native WKWebView workflow before packaging:

```sh
.venv/bin/python scripts/test_standalone_package.py dist/qwen/OpenChem.app build/qwen-release/api-workflow.json
.venv/bin/python scripts/audit_standalone_binary.py dist/qwen/OpenChem.app build/qwen-release/binary-audit.json
bash scripts/package_qwen_mac.sh
```

The native workflow is `scripts/native_standalone_workflow.js`, selected via
`OPENCHEM_WORKFLOW_SCRIPT`, with isolated `OPENCHEM_DATA`, a result path in
`OPENCHEM_SMOKE_RESULT`, and `OPENCHEM_SMOKE_QUIT=1`. It drives the compiled
app's production controls; it is not run during ordinary launches.

This preview is not notarized. Ad-hoc signing checks local bundle integrity;
it does not establish a verified developer identity or Gatekeeper acceptance.
The package script verifies both runtime manifests, model hashes and internal
symlinks, then produces a DMG, ZIP and SHA-256 file. Verify the final mounted
DMG and copied app again before publishing. Source ZIPs exclude model weights,
private adapters, training records, installed dependencies and Git history.
