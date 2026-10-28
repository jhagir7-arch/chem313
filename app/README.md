# Chem313 desktop alpha

Tauri 2 + React with an included frozen Python/RDKit engine. The catalog owns molecule examples, parameter defaults and validation. The UI provides Ketcher drawing, SMILES/molfile import, 3Dmol viewing, force-field relaxation, immutable saved records and native dialogs.

## Build

Python 3.13, Node 22, Rust and platform Tauri build prerequisites are required for developers. End users need none of those runtimes.

```sh
python -m pip install -e "backend[test]" "pyinstaller>=6.19,<7"
npm --prefix app ci
python scripts/sync_version.py --check
python -m pytest backend/tests -q
python scripts/freeze_engine.py
python scripts/test_v2_frozen_engine.py app/src-tauri/engine/chem313-engine frozen-engine-qa.json
python scripts/collect_v2_notices.py
npm --prefix app test
cargo test --manifest-path app/src-tauri/Cargo.toml --locked
cargo install tauri-cli --version "^2" --locked
cd app && cargo tauri build
```

The notice collector must pass before packaging. Its inventory identifies scope and gaps; it is not a blanket legal clearance. Installers are built independently on each platform by `.github/workflows/app.yml`.

## Architecture

`src-tauri/src/lib.rs` starts a loopback engine, validates its banner with a timeout, and proxies session-authenticated requests. `src/engine.ts` is the sole interface bridge. `src/App.tsx` coordinates jobs; `src/editor.tsx` preserves per-molecule drafts and reads a fresh structure before running. Reports supply actual canonical identity. A parent watchdog prevents an orphan engine.

The Tauri shell stores data under its org.chem313.desktop application-data directory. Legacy OpenChem data is preserved separately and is not automatically migrated. This alpha has no persistent long-job queue, working add-on installer, updater or quantum-engine runner. ORCA and Q-Chem are separately licensed and not included. Qwen is not bundled or needed. macOS packages are not Developer ID signed or notarized.

Only small single-fragment molecules whose full structure is covered by MMFF94 or UFF are supported. Undefined stereochemistry must be specified. Energies compare shapes of the same molecule within the same force field; they do not rank reactions or predict drug behavior.
