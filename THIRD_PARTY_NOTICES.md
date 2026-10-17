# Third-party notices and distribution boundary

Applies to OpenChem 1.0.0-preview.1 source and its compiled native shell. Apache-2.0 covers OpenChem-originated code/documentation only. The shell is built from `desktop/OpenChem.swift` against system AppKit/WebKit and contains our LICENSE/NOTICE. It includes no third-party engines, Python, generated JavaScript bundles, models, datasets or native companion applications.

Lock files identify dependencies rather than redistribute their code. Setup obtains npm/Python packages separately under upstream terms and generates browser assets locally. Any future redistribution of those assets or installed packages must retain their actual license/NOTICE files and satisfy applicable source/relinking obligations. This document does not clear the older private DMG.

## Frontend source dependencies

Exact resolved versions are from `frontend/package-lock.json` (lockfile v3). The package has direct browser/runtime dependencies below; retain their license texts/notices if their code or a generated browser bundle is later included.

| Package | Version | Reported license | Upstream |
| --- | ---: | --- | --- |
| 3dmol | 2.5.5 | BSD-3-Clause | [3Dmol.js](https://github.com/3dmol/3Dmol.js) |
| events | 3.3.0 | MIT | [npm package](https://www.npmjs.com/package/events) |
| ketcher-core | 3.18.0 | Apache-2.0 | [Ketcher](https://github.com/epam/ketcher) |
| ketcher-react | 3.18.0 | Apache-2.0 | [Ketcher](https://github.com/epam/ketcher) |
| ketcher-standalone | 3.18.0 | Apache-2.0 | [Ketcher](https://github.com/epam/ketcher) |
| react | 18.3.1 | MIT | [React](https://github.com/facebook/react) |
| react-dom | 18.3.1 | MIT | [React](https://github.com/facebook/react) |
| vite-plugin-node-polyfills | 0.28.0 | MIT | [npm package](https://www.npmjs.com/package/vite-plugin-node-polyfills) |

Build/test-only direct packages: `@types/react` 18.3.31 (MIT), `@types/react-dom` 18.3.7 (MIT), `@vitejs/plugin-react` 4.7.0 (MIT), TypeScript 5.9.3 (Apache-2.0), and Vite 6.4.4 (MIT). They are not part of the public source distribution as installed artifacts. If `frontend/dist` is later shipped, produce a bundle-specific notice inventory from the actual output; Vite supports generated bundle license reporting in its [official documentation](https://vite.dev/guide/features.html#license).

Ketcher’s upstream [NOTICE](https://github.com/epam/ketcher/blob/master/NOTICE) identifies its own third-party notices. A future bundled build must not reduce Ketcher compliance to its top-level Apache-2.0 label when it is bundled.

## Core Python source dependencies

`backend/pyproject.toml` declares ranges; `desktop/requirements-lock.txt` records the observed core build environment. The source package contains source/configuration only and does not distribute those installed wheels or libraries.

| Package | Declared range | Observed core lock | Reported license | Upstream |
| --- | --- | ---: | --- | --- |
| RDKit | >=2025.9.4,<2027 | 2026.9.1 | BSD-3-Clause | [RDKit](https://github.com/rdkit/rdkit) |
| NumPy | >=2,<3 | 2.5.4 | BSD-3-Clause | [NumPy](https://numpy.org/) |
| SciPy | >=1.14,<2 | 1.18.1 | BSD-3-Clause | [SciPy](https://scipy.org/) |
| Matplotlib | >=3.9,<4 | 3.11.2 | Matplotlib license | [Matplotlib](https://matplotlib.org/) |
| FastAPI | >=0.115,<1 | 0.143.3 | MIT | [FastAPI](https://github.com/fastapi/fastapi) |
| Uvicorn | >=0.30,<1 | 0.54.0 | BSD-3-Clause | [Uvicorn](https://github.com/encode/uvicorn) |

The core lock also names transitive/build/test packages, including PyInstaller. They remain external installs in this scope. A later binary release needs a release-specific SBOM and the original license/NOTICE files from the resulting artifact; the existing `desktop/licenses/` directory is useful evidence, not a final binary disclosure.

## Optional integration source references

The repository contains adapters, lock files, registry rows, tests or documentation referring to the following integrations. This public preview does **not** ship their executable, wheel, model, dataset, archive, or host bundle. Their source license labels are informative only and do not make the component part of this release.

| Integration area | Referenced projects / source links | Source-only treatment |
| --- | --- | --- |
| Scientific worker | [Gemmi](https://github.com/project-gemmi/gemmi), [spglib](https://github.com/spglib/spglib), [pymatgen](https://github.com/materialsproject/pymatgen), [Pint](https://github.com/hgrecco/pint), [pandas](https://github.com/pandas-dev/pandas), [Polars](https://github.com/pola-rs/polars), [lmfit](https://github.com/lmfit/lmfit-py), [nmrglue](https://github.com/jjhelmus/nmrglue), [Pyteomics](https://github.com/levitsky/pyteomics), [Biopython](https://github.com/biopython/biopython), [Optuna](https://github.com/optuna/optuna), [Cantera](https://github.com/Cantera/cantera), [OpenMM](https://github.com/openmm/openmm), [MDTraj](https://github.com/mdtraj/mdtraj), [MDAnalysis](https://github.com/MDAnalysis/mdanalysis), [RO-Crate](https://www.researchobject.org/ro-crate/) and [ORD Schema](https://github.com/Open-Reaction-Database/ord-schema) | Optional external installs; versions are recorded in `environments/science-macos-arm64.lock`. |
| Extended worker | [PySCF 2.14.0](https://pyscf.org/) (Apache-2.0), [tblite](https://github.com/tblite/tblite), [matchms](https://github.com/matchms/matchms), [Meeko](https://github.com/forlilab/Meeko) and [RDKit](https://github.com/rdkit/rdkit) | Optional external installs; no worker binary or engine package is included. |
| Bioscience worker | [PyEnzyme 1.1.5](https://github.com/EnzymeML/PyEnzyme), [PySB 1.17.0](https://github.com/pysb/pysb) and [BioNetGen 0.8.7](https://github.com/RuleWorld/bionetgen) | Optional external installs; `bng-mac` helpers are expressly excluded. |
| Local ML worker | [MLX 0.32.4](https://github.com/ml-explore/mlx), [mlx-lm 0.32.2](https://github.com/ml-explore/mlx-lm), [Transformers](https://github.com/huggingface/transformers), [Tokenizers](https://github.com/huggingface/tokenizers), [Safetensors](https://github.com/huggingface/safetensors) and [SentencePiece](https://github.com/google/sentencepiece) | Entire worker, weights, adapter and training materials are excluded. |
| Native hosts/executables | Avogadro, Open Babel, Qt and ORCA | Excluded. This draft makes no redistribution statement for their binaries or dynamic libraries. |

The 54-entry source catalog and `sources/licenses/` are research/provenance records. They do not assert that all upstream sources were built, installed, or redistributed, and they must not be represented as a complete binary license inventory.

## Source and assets

OpenChem-originated code is supplied under the root LICENSE. Installed dependencies remain external and retain their original terms. Original handoff archives, private receipts, model/adapter/training material, generated UI and researcher records are excluded. Six third-party cclib-data ORCA outputs are excluded because their redistribution license was not established; the URL/hash provenance manifest alone is retained.

The compiled shell uses system-provided AppKit and WebKit; no copy of those frameworks is included. It is ad-hoc signed and not notarized. No OpenChem endorsement by any upstream project is implied. Product names remain their respective owners' marks.
