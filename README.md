# Chem313

A local molecular study workbench for beginners: build a small molecule, inspect its atoms, compare starting shapes, and prepare a calculation input you can review and keep.

Formerly OpenChem. Independent of [Mariewelt/OpenChem](https://github.com/Mariewelt/OpenChem). The repository URL stays the same so existing links continue to work.

## Download the current preview

[**Chem313 1.0.0-preview.3 — downloads, source and verification**](https://github.com/jhagir7-arch/openchem/releases/tag/v1.0.0-preview.3)

The Apple Silicon Mac DMG is **111 MB**. Drag Chem313.app to Applications; no Python or Node setup. macOS 14+ deployment target, tested on macOS 27 only. This research preview is **ad-hoc signed and unnotarized**. macOS may block an Internet download. Verify the release SHA-256 sums before opening.

![Compiled Chem313 interface](https://github.com/jhagir7-arch/openchem/releases/download/v1.0.0-preview.3/Chem313-1.0.0-preview.3-screenshot.png)

## What changed

- Black and white interface with five main workspaces; experimental tools are under Labs.
- Real local RDKit force-field calculations, complete-geometry atom counts and a selectable relative-energy chart with units.
- Guided Q-Chem input lesson for water, methane and ethanol, with coordinate-derived identity checks and learner review before download.
- Keyboard-accessible 3D controls, local project records and a searchable feature directory.
- An overall project index connecting architecture, features, source files, tests and verified limits.

Force-field results are not quantum results, reaction pathways or medication predictions. Neither ORCA nor Q-Chem has completed a real quantum calculation on the maintainer’s machine. Both require separately licensed installations. Qwen is optional, experimental and **not bundled** in this core release.

## Verification and platform status

The compiled Mac app passed real force-field workflows for water, methane and ethanol, checked input preparation, learner review gating and five butane samples with chart/3D selection. Frontend: 40 tests passed. Focused backend: 69 passed. Frozen service, native ownership/license and deployment audits passed. See the release verification record for scope. Independent learner and scientific validation remain pending.

Windows and Linux native builders are included in the source snapshot. Downloads remain withheld until native workflow and redistribution checks pass. Linux passed native frozen-workflow and notice checks; exact bundled-runtime source obligations remain unresolved. Windows test-fixture fixes are published in source revision r1 and a native rerun is in progress; Microsoft runtime redistribution terms remain unresolved. A Mac binary cannot be converted into a Windows or Linux app.

## Corresponding source and project index

Use **Chem313-1.0.0-preview.3-Source-r1.zip** attached to the current release. It contains the corresponding code, dependency locks, build scripts, notices and verification record. Start with **PROJECT_INDEX.md** for the overall architecture and feature-to-code-to-test map, and **release/standalone/BUILDING.md** for Mac builds. Run `python3 scripts/check_project_index.py` to check index links and feature IDs.

The repository application tree still contains the earlier preview.1 baseline. GitHub’s automatic Source code archives follow the tag commit; use the specifically named preview.3 Source-r1.zip attachment for this binary. Revision r1 updates the project map, platform evidence and test fixtures; the compiled Mac app is unchanged. The older preview.2 Qwen edition remains a historical release. Private correspondence, user projects, training data and private adapters are excluded.

## Feedback and license

Use [GitHub Issues](https://github.com/jhagir7-arch/openchem/issues) for confusing steps, reproducible bugs or classroom tasks you need. Please omit private research data and license credentials.

Project-originated code and documentation use [Apache-2.0](LICENSE). Third-party components retain their own terms; consult the source snapshot’s NOTICE, THIRD_PARTY_NOTICES.md and SOURCE_ORIGIN.md. Proprietary engine binaries are excluded.
