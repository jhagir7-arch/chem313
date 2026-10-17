# OpenChem 1.0.0-preview.1 — first research preview

Local chemistry workbench for molecule building, reviewed calculation inputs, and traceable research records. Native macOS interface with optional scientific engines.

This preview focuses on molecule-to-input work: draw/import, inspect, generate a starting geometry, review calculation settings and preserve exact inputs. It also supplies ORCA result review, CSV fitting, reviewed JSON recipes and optional scientific adapters.

Downloads: source snapshot and compiled Apple Silicon native shell. **Install the local runtime from source first; the shell is not a self-contained installer.** Follow README.md. No Python/npm dependencies, Avogadro, ORCA, model weights, training adapter or datasets are bundled.

Apache-2.0 for OpenChem-originated source; upstream dependencies retain their terms. The public export excludes unlicensed third-party calculation fixtures and private development material.

Known limits: ad-hoc signing/no notarization; macOS 27 arm64 tested, other OS versions unverified; licensed ORCA execution unverified; Qwen unavailable without separately configured assets; no independent scientific validation. This is a prerelease for research evaluation.
