# Changelog

Chem313 was named OpenChem before 1.0.0-preview.3 and is independent of
[Mariewelt/OpenChem](https://github.com/Mariewelt/OpenChem). Dates are the
GitHub release publication dates (UTC). Checksums and full notes are on each
[release page](https://github.com/jhagir7-arch/chem313/releases); QA or
verification records are attached from preview.3 on.

## Unreleased

- v2 shell opened up: Ketcher editor and 3Dmol viewer; any molecule by SMILES, drawing or
  .mol/.sdf import, with MMFF94 or UFF and bounds served by the engine's new `/api/catalog`
  (no molecule or parameter lists in the interface); saved calculations restored from the
  event log; native export of records; engine stops when the shell does (parent watchdog).
- Engineering: `scripts/freeze_engine.py` (engine for any OS), `.github/workflows/app.yml`
  (installers on macOS, Ubuntu, Windows), interface unit tests, Rust proxy-path test,
  backend catalog tests, contributor guide for `app/`, issue and pull-request templates.
- Single version source for the current app: `hypothesislab.__version__` in
  `backend/src/hypothesislab/__init__.py`. `scripts/sync_version.py` propagates
  it to the npm package files and both OpenAPI contracts; the Mac bundle and the
  interface footer read it at build time; `--check` runs as a release-gate test.
  Scripts for the retired 0.8 and Qwen editions keep their own versions.
- Both OpenAPI contracts regenerated; the desktop contract gained 13 missing
  Q-Chem/study/ORCA routes.
- The preview.6 release documents agree that the Windows x64 and Linux x86_64
  archives are published.
- CI actions updated for the Node 24 runner.
- This changelog added and included in the public source package.
- v2 desktop shell (`app/`): Tauri 2 host that runs the frozen engine as a
  sidecar on a loopback port and proxies its API; native menus; React
  interface on the instrument design tokens in `design/`. Mac release build
  verified: ethanol MMFF94 relaxation, saved artefacts, engine stops on quit.
  Not yet: Ketcher/3Dmol, import/export, add-on packs, Windows/Linux, signing.

## 1.0.0-preview.6 — 2026-10-20

- One complete beginner job: choose ethanol, water or methane, relax its shape
  with the included RDKit MMFF94 force field, inspect the 3D result and energy
  chart, and download a reproducible record with artifact hashes. No Python,
  Node, engine account or Qwen setup required.
- First published Windows x64 (portable ZIP) and Linux x86_64 (portable
  tar.gz) archives, alongside the Apple Silicon Mac DMG and ZIP. Windows and
  Linux run a compiled local service and open the interface in the browser;
  their executables are unsigned. The Mac app is ad-hoc signed, not Developer
  ID signed or notarized.
- Verified: the compiled Mac interface completed all three molecules; native
  frozen Windows and Linux workflow checks ran all three calculations without
  Python or Node on PATH. Interactive GUI checks on Windows and Linux still
  need community testers.
- Recorded ethanol change with RDKit 2026.09.1 and seed 42: 6.831185 to
  −1.336852 kcal/mol, comparing two shapes of the same molecule in the same
  force field.
- This is real molecular mechanics, not a quantum-chemistry calculation,
  reaction predictor, experimental validation or proof of a global minimum.
  ORCA and Q-Chem execution remains unverified; Qwen remains optional and is
  not bundled.
- Three source ZIPs: the original records the Mac build, portable-r2 the
  Windows build, portable-r3 the Ubuntu package-ownership correction. All use
  the same first-calculation implementation.

## 1.0.0-preview.5 — 2026-10-20

- Classic white, black and neutral-grey interface: square panels, raised
  controls and a native Mac sidebar. Completed shape calculations show results
  first with expandable activity steps.
- Four sections: Learn, Molecule, Calculate and Records; Labs hidden by default.
- Apple Silicon Mac DMG and ZIP (macOS 14+ deployment target, tested on
  macOS 27), ad-hoc signed and unnotarized. Windows/Linux binaries withheld
  pending redistribution obligations.
- Verified: 42 frontend tests, compiled AppKit/WKWebView workflow, real RDKit
  water, methane, ethanol and five butane samples, coordinate-to-InChI checks.
  Force-field energies do not establish reactions or experimental properties;
  no real ORCA or Q-Chem quantum calculation has completed.
- Reviewed source consolidated on main; contributor, project-map and community
  guides published. Notes state the former OpenChem name and independence from
  Mariewelt/OpenChem.

## 1.0.0-preview.4 — 2026-10-20

- Work organised around Learn, Molecule, Calculate and Records; experimental
  tools in Labs, hidden by default. AppKit sidebar, toolbar and monochrome
  light/dark appearance.
- First-launch choices (learn, prepare a calculation, read an ORCA output); one
  Calculate section with ORCA or Q-Chem as an engine setting; persistent
  molecule context and coordinate identity checks.
- Result cards with plain status, explicit provenance, Eh/kJ/mol/eV units, Save
  record and a downloads menu; answer cards with feedback and a practice task;
  optional Qwen help; searchable feature/project index.
- Apple Silicon Mac DMG (110 MB) with Python, RDKit, NumPy, SciPy and
  Matplotlib; macOS 14+ deployment target, tested on macOS 27; ad-hoc signed,
  unnotarized. Windows/Linux downloads withheld pending runtime redistribution
  review; portable build scripts included.
- Verified: 42 frontend and 59 focused backend tests; real bundled RDKit water,
  methane, ethanol and five butane samples. A labelled simulated browser-only
  fixture tested result presentation and did not run a quantum engine. No real
  ORCA or Q-Chem quantum calculation has completed; force-field energies do not
  establish reactions or experimental properties.

## 1.0.0-preview.3 — 2026-10-20

- Renamed from OpenChem to Chem313. One workflow: build a molecule, inspect its
  atoms, compare starting shapes and prepare a reviewed calculation input.
- Black and white interface with five main workspaces; experimental tools under
  Labs. Keyboard-accessible 3D controls, clearer atom counts, a searchable
  feature directory and an overall project index.
- Real local RDKit force-field calculations with a selectable relative-energy
  chart and units; guided Q-Chem lesson with coordinate-derived identity checks
  and learner review before input download.
- Apple Silicon Mac DMG and ZIP (macOS 14+ deployment target, tested on
  macOS 27 only), ad-hoc signed and unnotarized. Linux download withheld over
  unresolved runtime-library source obligations; the first Windows run failed
  two Linux-path test fixtures, fixed in source revision r1.
- Verified: the compiled app ran force-field calculations for water, methane
  and ethanol; 40 frontend and 69 focused backend tests. ORCA and Q-Chem
  require separate licences and neither has completed a real quantum
  calculation; force-field results are not quantum results or evidence of
  reaction pathways.

## 1.0.0-preview.2 — 2026-10-18

- Self-contained OpenChem.app DMG for Apple Silicon Macs: embedded Python,
  NumPy, SciPy and Matplotlib; Ketcher/Indigo editor, RDKit inspection and 3D
  geometry, 3Dmol visualisation. No Python or Node installation required;
  macOS 26.2 or newer, tested on macOS 27.
- Offline Qwen3.5-2B-Base, 4-bit (Apache-2.0, pinned revision
  b1485b2fa6dfa1287294f269f5fb618e03d52d7c). Upstream base model only; no
  private adapter, datasets or training records. Proposals require explicit
  review and Apply.
- Ad-hoc signed and unnotarized; no Developer ID signing.
- Verified: 160 backend tests plus 7 subtests and 19 frontend tests; the
  compiled app passed Qwen draft, explicit Apply, RDKit geometry, reviewed ORCA
  input, numerical recipes, CSV fitting and artifact integrity.
- ORCA not bundled and its execution untested; Avogadro, PySCF and tblite
  optional and not bundled. Qwen drafts may be wrong; checks do not establish
  scientific validity.
- The named Source.zip is the corresponding build snapshot; GitHub's automatic
  archives follow the tag and are not this snapshot.

## 1.0.0-preview.1 — 2026-10-18

- First research preview of OpenChem: a local chemistry workbench for molecule
  building, reviewed calculation inputs and traceable research records, with a
  native macOS interface and optional scientific engines.
- Molecule-to-input work: draw/import, inspect, generate a starting geometry,
  review calculation settings and preserve exact inputs; ORCA result review,
  CSV fitting and reviewed JSON recipes.
- Downloads: source snapshot and compiled Apple Silicon native shell. The shell
  is not a self-contained installer; install the local runtime from source
  first. No Python/npm dependencies, Avogadro, ORCA, model weights, adapter or
  datasets bundled.
- Ad-hoc signing, no notarization; macOS 27 arm64 tested, other OS versions
  unverified; licensed ORCA execution unverified; Qwen unavailable without
  separately configured assets; no independent scientific validation.
- Apache-2.0 for OpenChem-originated source; upstream dependencies retain
  their terms.
