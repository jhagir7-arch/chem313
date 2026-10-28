# Chem313

A local molecular study workbench: draw a small molecule, relax its shape with RDKit, inspect the 3D structure and retain a reproducible record. Designed as an open community project for beginners and chemistry educators.

Formerly OpenChem; independent of [Mariewelt/OpenChem](https://github.com/Mariewelt/OpenChem).

## Community handoff — development paused

Maintainer development is paused as of 28 October 2026. The repository stays open for community contributions through issues and pull requests. The desktop beta has a deliberately limited scientific scope. Start with the [community handoff and remaining gaps](COMMUNITY_HANDOFF.md). No ongoing support or delivery date is promised.

## Community desktop beta: 2.0.0-beta.1

The current desktop target is one Tauri app with Structure, 3D, Setup and Results views. Its bundled RDKit engine performs real MMFF94/UFF molecular mechanics. End users do not install Python or Node.

1. Choose a starter molecule in the Navigator, or use File → New molecule to enter SMILES. You can also draw in Ketcher or import one `.mol`/`.sdf` record.
2. Open Setup, choose MMFF94 or UFF and select Run.
3. Read the convergence and identity checks, before/after energy chart, and 3D geometry.
4. Use File → Export record to save the method, results and file hashes. Calculations restore when you reopen the app.

**Scientific limits:** this is a shape-relaxation tool, not quantum chemistry, reaction prediction, experimental validation or evidence of a global minimum. Compare energies only for the same molecule and force field. Inputs must be one fragment, at most 100 heavy atoms, with defined stereochemistry and supported force-field parameters.

## Downloads and testing

The [desktop release page](https://github.com/jhagir7-arch/chem313/releases/tag/v2.0.0-beta.1) is the download destination once the native release workflow passes. A failed candidate is withheld; an absent asset is not a supported download. See [platform requirements, installation and first calculation](docs/DESKTOP_RELEASE.md).

| Platform | Package | Requirements |
| --- | --- | --- |
| Mac | `.dmg` | Apple Silicon, macOS 14 or newer; ad-hoc signed, not notarized |
| Windows | `.msi` | Windows 10/11 x64; WebView2 bootstrapper may need internet |
| Linux | `.deb` or `.AppImage` | x86_64; WebKitGTK 4.1 and distribution libraries; see release notes |

Each published package must pass notice verification and real calculations using its extracted engine. These checks do not establish full native GUI or accessibility coverage. Please report platform-specific problems with the package version and steps to reproduce. Older preview.6 packages are a separate interface.

ORCA, Q-Chem and Qwen are **not included** in this beta. Disabled add-on rows describe future work. The complete supported workflow uses bundled RDKit.

## Build and contribute

See [app build instructions](app/README.md), [CONTRIBUTING.md](CONTRIBUTING.md), [community guide](docs/COMMUNITY.md) and [project index](PROJECT_INDEX.md). The older `frontend/` and Swift/portable packaging are retained source for migration; `app/` is the current desktop target.

Use [GitHub Issues](https://github.com/jhagir7-arch/chem313/issues) for bugs, beginner walkthroughs, chemistry review and accessibility feedback. Please omit private research and license credentials. The new Tauri shell stores calculations under its org.chem313.desktop application-data directory. Legacy OpenChem project data is preserved separately and is not automatically migrated.

Project-originated source and documentation use [Apache-2.0](LICENSE). Dependencies retain their terms: see [NOTICE](NOTICE), [third-party notices](THIRD_PARTY_NOTICES.md) and [source origin](SOURCE_ORIGIN.md). Binary installers carry a dependency inventory and license texts under their resources/notices directory; source-only archives do not include proprietary engines, model weights or private data.

## Qwen and historical modules

The historical assistant source and pinned base-model conversion instructions are retained in [release/qwen](release/qwen/BUILDING.md); the [training pilot](training/public/README.md) explains its reproducibility limits. Obtain upstream model weights separately under their own license. The private adapter and dataset have no completed redistribution clearance and are excluded. These modules are not integrated into the current v2 desktop workflow. See the [module index and roadmap](COMMUNITY_HANDOFF.md) before choosing work.
