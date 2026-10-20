# Chem313

Chem313 is a local molecular study workbench for beginners. Build a small
molecule, count its atoms, compare starting shapes, and prepare a calculation
input you can inspect and keep.

Formerly called OpenChem. This project is independent of
[Mariewelt/OpenChem](https://github.com/Mariewelt/OpenChem); the repository URL
stays the same so existing links continue to work.

## Download

[Chem313 1.0.0-preview.6: downloads, source and checks](https://github.com/jhagir7-arch/openchem/releases/tag/v1.0.0-preview.6). Standalone packages for Windows x64, Linux x86_64 and Apple Silicon Mac. No Python or Node setup required.

## What works in preview.6

- **First calculation:** open Calculate, choose ethanol, then Run shape calculation.
  The included RDKit/MMFF94 engine relaxes its shape and saves both SDF files
  plus a report. See signed before/after energy values, convergence and 3D
  geometry; download a reproducible record with file hashes. Water and methane
  are also available. This is real force-field molecular mechanics, not quantum
  chemistry or a reaction predictor. No engine account or AI setup is required.

- Classic white, black and neutral grey desktop controls, square panels and a native sidebar. No beige or decorative gradients.
- Four core sections organise the app: **Learn**, **Molecule**, **Calculate**,
  and **Records**. The native macOS shell supplies the same section sidebar;
  optional engineering tools remain under Labs.
- Molecule supports Ketcher drawing, RDKit inspection, explicit-hydrogen 3D
  generation, and real MMFF/UFF force-field calculations. Shape-chart values
  compare starting geometries of one molecule within one force field.
- Calculate has an ORCA/Q-Chem engine setting. It prepares reviewed input and
  configuration for separately licensed installations; choosing an engine does
  not establish that it is installed or that a job ran.
- The guided Q-Chem lesson presents formula, charge, multiplicity, and an
  InChI identity state. “Identity verified” appears only for a server-reported
  match; it does not validate geometry quality, electronic state, or method.
- A recorded terminal result can show an electronic energy in Eh, kJ/mol, or
  eV. The [NIST CCCBDB](https://cccbdb.nist.gov/) link is a reference lookup:
  Chem313 makes no direct NIST comparison or experimental-validation claim.
- Local records retain reviewed inputs and outputs. Qwen remains optional and
  experimental; no model is bundled or downloaded for the core workflow.

**Scientific boundary:** the locally evidenced calculation is RDKit ETKDG plus
MMFF/UFF force-field conformer generation and energy evaluation. It is not a
quantum result, an experimental measurement, or evidence of a global minimum.
No actual ORCA or Q-Chem quantum-chemistry run is recorded for this candidate.

## Screens from the compiled Mac app

![Real local force-field shape comparison (preview.5 screenshot)](https://github.com/jhagir7-arch/openchem/releases/download/v1.0.0-preview.5/Chem313-shape-chart.png)

![Checked input preparation; no quantum run (preview.5 screenshot)](https://github.com/jhagir7-arch/openchem/releases/download/v1.0.0-preview.5/Chem313-input-review.png)

## Downloads and platforms

- **Windows x64:** [download ZIP](https://github.com/jhagir7-arch/openchem/releases/download/v1.0.0-preview.6/Chem313-core-windows-amd64.zip). Extract the entire folder and open `Chem313.exe`. Windows 10+ / Server 2022+; native automated checks ran on Server 2022.
- **Linux x86_64:** [download tar.gz](https://github.com/jhagir7-arch/openchem/releases/download/v1.0.0-preview.6/Chem313-core-linux-x86_64.tar.gz). Extract the entire folder and run `./Chem313`. Tested on Ubuntu 22.04; requires glibc 2.35+. Other distributions and ARM systems are unverified.
- **Apple Silicon Mac, macOS 14+:** [download DMG](https://github.com/jhagir7-arch/openchem/releases/download/v1.0.0-preview.6/Chem313-1.0.0-preview.6-Mac-arm64.dmg). See [Mac installation and scope](release/standalone/README.txt). Ad-hoc signed, **not Apple Developer ID signed or notarized**; macOS may block an Internet download.

Windows and Linux open the interface in your browser from a compiled local
service. Keep the launcher running while you work. No system Python or Node
is needed. The executables are unsigned. On first Windows launch, review the
retained Microsoft runtime terms and choose Yes only if you accept them.
See [portable installation instructions](release/portable/README.txt).

The compiled Mac interface passed all three beginner molecules, 3D/chart
rendering, record bridge payload and stale-result checks. Native frozen
Windows and Linux workflow checks passed all three real calculations from a
fresh home and relocated directory without Python or Node on PATH. Interactive
GUI checks on Windows and Linux still need community testers. Published
packages passed runtime notice and distribution gates; platform QA reports
and SHA-256 checksums are attached to the release.

## Try the beginner workflow

1. Open **Calculate → First calculation**.
2. Choose **Ethanol**, then click **Run shape calculation**. No engine account,
   scripting or AI setup is required.
3. Inspect the relaxed 3D molecule and the signed before/after energy chart.
   The values compare shapes of this same molecule using MMFF94.
4. Click **Download record** to keep parameters, model version and artifact hashes.
5. Try water or methane. Do not compare their raw force-field energies against
   ethanol's energy to rank reactions or stability.

ORCA and Q-Chem input preparation remains a separate advanced workflow for
people who have installed and licensed those engines.

## Build and verify

Maintainers need Python 3.13, Node 24, and the platform build tools. End users
of a standalone package do not.

```sh
bash scripts/setup_public_runtime.sh
npm --prefix frontend test
npm --prefix frontend run build
python3 scripts/check_project_index.py
bash scripts/build_standalone_app.sh dist/chem313/Chem313.app
.venv/bin/python scripts/test_standalone_package.py dist/chem313/Chem313.app build/chem313/api-check.json
.venv/bin/python scripts/audit_standalone_binary.py dist/chem313/Chem313.app build/chem313/binary-audit.json
```

See [Mac build instructions](release/standalone/BUILDING.md). Existing local
project data stays in the `OpenChem` application-support folder for
compatibility. Renaming the product does not migrate or erase it.

## Build this with us

Chem313 is a community research preview. Start with [CONTRIBUTING.md](CONTRIBUTING.md), the [community guide](docs/COMMUNITY.md), and [PROJECT_INDEX.md](PROJECT_INDEX.md). Beginner walkthroughs, keyboard/accessibility checks, chemistry review and focused code changes are welcome. Use GitHub Issues for public feedback; no private email is published.

## Feedback, provenance and license

This is a research preview. Report reproducible bugs, confusing steps, or
useful classroom tasks through [GitHub Issues](https://github.com/jhagir7-arch/openchem/issues).
Do not include private research data or license credentials.

Project-originated code and documentation are under [Apache-2.0](LICENSE).
Third-party components retain their own terms. See [NOTICE](NOTICE),
[third-party notices](THIRD_PARTY_NOTICES.md), [source origin](SOURCE_ORIGIN.md),
[release scope](PUBLICATION_STATUS.md), [contributing](CONTRIBUTING.md), and
[security](SECURITY.md). Proprietary engine binaries, private training data,
and adapters are excluded.
