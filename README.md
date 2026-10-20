
# Chem313

A local molecular study workbench for beginners: build a small molecule, inspect its atoms, compare starting shapes, and prepare a calculation input you can review and keep.

Formerly OpenChem. Independent of [Mariewelt/OpenChem](https://github.com/Mariewelt/OpenChem). The repository URL stays the same so existing links continue to work.

## Download the current preview

[**Chem313 1.0.0-preview.4 — downloads, source and verification**](https://github.com/jhagir7-arch/openchem/releases/tag/v1.0.0-preview.4)

The Apple Silicon Mac DMG is **110 MB** and includes Python, RDKit, NumPy, SciPy, Matplotlib and the prebuilt interface. Drag Chem313.app to Applications; no Python or Node setup. macOS 14+ deployment target, tested on macOS 27 only. This research preview is **ad-hoc signed and unnotarized**; macOS may block an Internet download. Verify the release SHA-256 sums before opening.

## A clearer molecular workspace

- **Learn:** a guided input lesson, visible answer cards with feedback, and a different-molecule practice task.
- **Molecule:** draw, inspect atoms, generate 3D starting geometry and compare shapes with a relative-energy chart.
- **Calculate:** prepare → run → result in one section; ORCA or Q-Chem is a setting. Automatic ORCA discovery checks common installation locations.
- **Records:** local project files, notebook and saved calculation artifacts.
- **Labs:** additional tools, hidden by default.

The Mac app now uses an AppKit sidebar and toolbar, monochrome light/dark appearance and first-launch choices. Molecule context, coordinate-derived identity checks and five workflow stages remain visible. Result cards use plain status, explicit real/simulated provenance, Eh/kJ/mol/eV units, one Save action and a downloads menu. Optional Qwen help has its own panel.

## What is verified, and what is pending

Real bundled RDKit force-field calculations generated water, methane, ethanol and five butane shape samples. The compiled Mac workflow verified identity checks, answer feedback, chart/3D selection and saved interface preferences. **42 frontend tests and 59 focused backend tests passed**, along with the frozen scientific package, 243-file native-library audit and bundled-notice gate. The attached QA record describes the scope.

A clearly labelled simulated browser-only fixture tested result presentation; it did not run a quantum engine. **No real ORCA or Q-Chem quantum calculation has completed here.** Both require separately licensed installations. Force-field energies do not establish reactions, experimental properties or medication predictions. NIST CCCBDB is a lookup link; no unmatched reference energy is shown. Qwen is optional, experimental and **not bundled**. Independent learner and scientific validation remain pending.

Windows/Linux native frozen-workflow CI passed on the previous source candidate: [run 39366818959](https://github.com/jhagir7-arch/openchem/actions/runs/39366818959). Preview.4 has not yet been verified there. Compiled downloads remain withheld pending Microsoft runtime redistribution review on Windows and exact GCC/libquadmath source obligations on Linux. Portable build scripts are included; a Mac binary cannot be converted into a Windows or Linux app.

## Corresponding source and project index

Use [**Chem313-1.0.0-preview.4-Source.zip**](https://github.com/jhagir7-arch/openchem/releases/download/v1.0.0-preview.4/Chem313-1.0.0-preview.4-Source.zip) for this build's corresponding code, locks, build scripts, notices and verification record.

Start with **PROJECT_INDEX.md** inside that ZIP. It maps the architecture and each feature to code, tests and current limits. The in-app feature directory searches the same capability set. This is project navigation, not RAG.

| In the source ZIP | Purpose |
| --- | --- |
| PROJECT_INDEX.md | Overall architecture and feature-to-code-to-test map |
| frontend/src | Interface and feature catalog |
| backend/src/hypothesislab | Local API, chemistry validation and engine runtimes |
| desktop | AppKit shell and portable launcher |
| scripts | Builds, packaging, index validation and compiled-app QA |
| release/standalone/BUILDING.md | Mac build and signing guide |
| release/portable/README.txt | Windows/Linux build scope |
| release/public-source/VERIFICATION.json | Recorded verification and limits |

Run `python3 scripts/check_project_index.py` to validate index links and feature IDs.

**The repository application tree still contains the earlier preview.1 baseline.** GitHub's automatic Source code archives follow the tag commit; use the specifically named preview.4 Source.zip attachment for this binary. Private correspondence, user projects, model weights, training data and private adapters are excluded.

## Feedback and license

Use [GitHub Issues](https://github.com/jhagir7-arch/openchem/issues) for confusing steps, reproducible bugs or classroom tasks you need. Please omit private research data and license credentials.

Project-originated code and documentation use [Apache-2.0](LICENSE). Third-party components retain their own terms; consult the source snapshot's NOTICE, THIRD_PARTY_NOTICES.md and SOURCE_ORIGIN.md. Proprietary engine binaries are excluded.
