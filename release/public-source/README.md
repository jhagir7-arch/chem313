# Chem313

A local molecular study workbench: draw a small molecule, relax its shape with RDKit, inspect the 3D structure and retain a reproducible record. Designed as an open community project for beginners and chemistry educators.

Formerly OpenChem; independent of [Mariewelt/OpenChem](https://github.com/Mariewelt/OpenChem).

## Community handoff — development paused

Maintainer development is paused as of 28 October 2026. The repository stays open for community contributions through issues and pull requests. This is a research alpha, not a finished scientific product. Start with the [community handoff and remaining gaps](COMMUNITY_HANDOFF.md). No ongoing support or delivery date is promised.

## Current development release: 2.0.0-alpha.1

This consolidates the interface into one Tauri desktop app with Structure, 3D, Setup and Results views. The included engine performs real MMFF94/UFF molecular mechanics. The desktop packaging is designed to bundle its runtime. No ready-to-run v2 installer is currently cleared for distribution; building from source requires the development tools in the build instructions.

1. Choose a starter molecule in the Navigator, or use File → New molecule to enter SMILES. You can also draw in Ketcher or import one `.mol`/`.sdf` record.
2. Open Setup, choose MMFF94 or UFF and select Run.
3. Read the convergence and identity checks, before/after energy chart, and 3D geometry.
4. Use File → Export record to save the method, results and file hashes. Calculations restore when you reopen the app.

**Scientific limits:** this is a shape-relaxation tool, not quantum chemistry, reaction prediction, experimental validation or evidence of a global minimum. Compare energies only for the same molecule and force field. Inputs must be one fragment, at most 100 heavy atoms, with defined stereochemistry and supported force-field parameters.

## Downloads and testing

This release begins as a **source alpha**. New installers are withheld until their native workflow and notice gates pass. The local macOS review still has 12 unresolved objc2-family notice gaps.

See [Releases](https://github.com/jhagir7-arch/chem313/releases) for attached installers and their platform-specific checks. Do not treat older preview.6 packages as this new interface. Windows and Linux desktop packages require their native CI checks; a Mac test does not validate those systems. macOS 14+ Apple Silicon is the locally tested platform. Packages are unsigned or ad-hoc signed, not notarized.

ORCA, Q-Chem and Qwen are **not included** in this alpha. Disabled engine/add-on rows describe future work. The complete workflow here uses the bundled RDKit engine.

## Build and contribute

See [app build instructions](app/README.md), [CONTRIBUTING.md](CONTRIBUTING.md), [community guide](docs/COMMUNITY.md) and [project index](PROJECT_INDEX.md). The older `frontend/` and Swift/portable packaging are retained source for migration; `app/` is the current desktop target.

Use [GitHub Issues](https://github.com/jhagir7-arch/chem313/issues) for bugs, beginner walkthroughs, chemistry review and accessibility feedback. Please omit private research and license credentials. The new Tauri shell stores calculations under its org.chem313.desktop application-data directory. Legacy OpenChem project data is preserved separately and is not automatically migrated.

Project-originated source and documentation use [Apache-2.0](LICENSE). Dependencies retain their terms: see [NOTICE](NOTICE), [third-party notices](THIRD_PARTY_NOTICES.md) and [source origin](SOURCE_ORIGIN.md). Binary installers carry a dependency inventory and license texts under their resources/notices directory; source-only archives do not include proprietary engines, model weights or private data.

## Qwen and historical modules

The historical assistant source and pinned base-model conversion instructions are retained in [release/qwen](release/qwen/BUILDING.md); the [training pilot](training/public/README.md) explains its reproducibility limits. Obtain upstream model weights separately under their own license. The private adapter and dataset have no completed redistribution clearance and are excluded. These modules are not integrated into the current v2 desktop workflow. See the [module index and roadmap](COMMUNITY_HANDOFF.md) before choosing work.
