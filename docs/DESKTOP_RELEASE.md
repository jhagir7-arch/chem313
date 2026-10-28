# Chem313 2.0.0-beta.1 — community desktop release

A standalone molecular study workbench for drawing small molecules, relaxing their shape with RDKit MMFF94/UFF, inspecting 3D structures and saving reproducible records. Python, Node and an engine account are not required to run the application.

## Choose your download

| Platform | Download | Requirements |
| --- | --- | --- |
| Mac | `Chem313-2.0.0-beta.1-mac-arm64.dmg` | Apple Silicon, macOS 14 or newer; Intel Macs are not supported by this package |
| Windows | `Chem313-2.0.0-beta.1-windows-amd64.msi` | Windows 10/11 x64; installer can download Microsoft WebView2 if absent |
| Linux | `Chem313-2.0.0-beta.1-linux-x86_64.deb` | Ubuntu 22.04+ or a compatible Debian-based x64 desktop; use the package manager to install dependencies |
| Other Linux desktops | `Chem313-2.0.0-beta.1-linux-x86_64.AppImage` | x64, compatible WebKitGTK 4.1 libraries and FUSE 2; distribution support varies |

Download the matching installer attached below. `SHA256SUMS.txt` contains installer checksums, and each `.qa.json` records the native extraction and bundled-engine check. GitHub's **Source code** archives are for developers, not installers.

Mac and Windows packages do not carry a paid publisher identity. The Mac app is ad-hoc signed and not notarized; macOS may require a user-approved exception in Privacy & Security. Windows may show an unknown-publisher warning. Do not disable operating-system protections globally. No silent auto-updater is included.

## First calculation — about two minutes

1. Install and open Chem313. Choose **Water** in the Navigator.
2. Open **Setup**, keep **MMFF94**, and select **Run**.
3. Open **Results**: check that the run converged and the molecule identity matched. The chart compares the starting and relaxed shape energies.
4. Inspect the shape in **3D** and use **File → Export record** to save the calculation record. Close and reopen the app to see the saved calculation again.
5. Try ethanol, or use **File → New molecule** to enter a SMILES string. The app explains unsupported inputs before running.

These are real local molecular-mechanics calculations. Energies compare shapes of the same molecule using the same force field. They cannot establish a reaction, a drug effect, experimental accuracy or a global minimum. Only one fragment, at most 100 heavy atoms, defined stereochemistry and supported parameters are accepted.

## What's included and what's open

Included: Ketcher editor, SMILES/molfile import, 3Dmol viewer, bundled RDKit/Python runtime, MMFF94/UFF, energy charts, identity checks, persisted calculations, native menus and record export. Dependency license texts and their inventory are included inside the installed resources.

ORCA, Q-Chem and Qwen are not included in the current desktop workflow. Historical integration/training source and model setup instructions remain available in the repository; proprietary engines and private adapters/datasets are excluded. This release does not claim a validated AI chemistry assistant or quantum-calculation workflow.

Each installer is built on its own operating system. Release checks run backend/UI/Rust tests, four real calculations (water, methane, ethanol and phenol), independent energy reconstruction, artifact hashes and notices again from extracted installer resources. These checks do not substitute for human GUI and accessibility testing on every supported machine. The Mac UI was reviewed locally; community Windows/Linux walkthroughs remain welcome.

## Community handoff

Maintainer development pauses after this release. Contributions, forks and issues remain welcome; no delivery date or ongoing support is promised. Start with [CONTRIBUTING.md](https://github.com/jhagir7-arch/chem313/blob/main/CONTRIBUTING.md) and [COMMUNITY_HANDOFF.md](https://github.com/jhagir7-arch/chem313/blob/main/COMMUNITY_HANDOFF.md).

Priority gaps: native accessibility review, signing/notarization, clean-machine Windows/Linux GUI validation, automated updates, a persistent long-job queue, legacy-data migration and expert evaluation before reconnecting optional AI or quantum engines. Report bugs using GitHub Issues without private research or credentials.

Project-originated source is Apache-2.0. Third-party dependencies retain their licenses. This is a community beta with a deliberately limited scientific scope.
