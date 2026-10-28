# Chem313 project index

**Version candidate:** Chem313 1.0.0-preview.6
**Purpose:** a maintained navigation map for the local Chem313 workbench. This
is a project index, not an AI memory, retrieval, or RAG system.

## Read first

- [Public package README (staged at the package root)](README.md)
- [Changelog: release history and unreleased changes](CHANGELOG.md)
- [v2 desktop shell (Tauri + engine sidecar)](app/README.md), [design tokens](design/tokens.json) and [component spec](design/COMPONENTS.md); plan in `CHEM313_V2_PLAN_2026-10-24.md` (private)
- [Standalone macOS build and signing guide](release/standalone/BUILDING.md)
- [Portable-core build scope](release/portable/README.txt)
- [Source-candidate setup, test scope, and limitations](release/public-source/README.md)
- [Source-candidate release checks](release/public-source/RELEASE_CHECKS.md)
- [Compiled native workflow harness](release/public-source/VERIFICATION.json)
- [Optional Qwen preview scope](release/qwen/RELEASE_NOTES.md)

## Source map and contributor path

| Area | Primary shipped paths | Where to add or change work |
| --- | --- | --- |
| Frontend | [application shell](frontend/src/App.tsx), [feature catalog](frontend/src/featureIndex.mjs), [API client](frontend/src/api.ts), [frontend tests](frontend/test) | Add a user-facing workspace or component in `frontend/src`; add its focused JavaScript test in `frontend/test`; maintain its catalog entry. |
| Local backend | [HTTP entry point](backend/src/hypothesislab/api.py), [engine](backend/src/hypothesislab/engine.py), [runtime modules](backend/src/hypothesislab), [backend tests](backend/tests) | Add local actions, validation, storage, or engine integration under `backend/src/hypothesislab`; put focused pytest coverage in `backend/tests`. |
| v2 desktop shell | [Rust host: engine sidecar, proxy, menus](app/src-tauri/src/lib.rs), [shell state and commands](app/src/App.tsx), [workspace tabs](app/src/workspace.tsx), [panels](app/src/panels.tsx), [host bridge](app/src/engine.ts) | Phase 2 skeleton: one app for all three OSes; replaces the Swift shell and portable launcher once Phase 3 lands. Add UI in `app/src`, host behaviour in `app/src-tauri/src`. |
| Native desktop and portable core | [macOS shell](desktop/Chem313.swift), [desktop services](desktop), [portable launcher](desktop/portable.py), [Rust helper](native/rust), [C++ helper](native/cpp) | Change native menu/window behavior in `desktop/Chem313.swift`; change local launch packaging in `desktop`; place narrow native helpers in the matching `native` language directory. |
| Contracts | [local API contract](contracts/openapi.generated.json), [desktop contract](contracts/desktop.openapi.generated.json), [tool-action schema](contracts/tool-actions.schema.json) | Update the applicable contract when a typed external or desktop-facing interface changes, then keep implementation and tests aligned. |
| Build, package, and QA scripts | [public app build](scripts/build_public_app.sh), [portable build](scripts/build_portable.py), [source packaging](scripts/package_public_source.py), [packaged QA](scripts/test_portable_package.py) | Add a deterministic maintenance, build, package, or native-QA script under `scripts`; keep release claims tied to its recorded output. |
| Release and licenses | [public-source release notes](release/public-source), [standalone build notes](release/standalone), [portable scope](release/portable/README.txt), [license](LICENSE), [notice](NOTICE), [third-party notices](THIRD_PARTY_NOTICES.md) | Update the release document that matches the artifact being built; add or revise notices with any distributed dependency or runtime change. |

For a feature change, begin in the frontend catalog and the matching product module,
trace its local request through the backend entry point and runtime, add focused test
coverage, then update the relevant feature-map row and run the index checker. For a
new build target, begin with its script and release notes before changing desktop or
portable packaging.

## Preview.6 candidate surface

| Core section | Primary surface | Current status |
| --- | --- | --- |
| Learn | [guided Q-Chem workflow](frontend/src/QchemWorkflow.tsx) | Five-stage beginner lesson with reviewed input and an honest InChI identity state. |
| Molecule | [application shell](frontend/src/App.tsx); [structure viewer](frontend/src/Viewer.tsx) | Drawing, inspection, 3D starting geometry, and force-field shape comparison. |
| Calculate | [first calculation](frontend/src/FirstCalculation.tsx); [relaxation engine](backend/src/hypothesislab/conformers.py) | Included RDKit ETKDGv3/MMFF94 shape relaxation for ethanol, water and methane; saved 3D before/after SDFs, signed energies, convergence, InChI match, report and hash record. Licensed ORCA remains optional. |
| Records | [project store](backend/src/hypothesislab/store.py); [result card](frontend/src/CalculationResult.tsx) | Local reviewed artifacts and result context, including electronic-energy unit conversion. |

The macOS shell renders these four sections in its native sidebar. Labs is an
opt-in area for additional tools. The result card links to NIST CCCBDB as a
reference lookup only; it makes no direct NIST comparison or experimental claim.
Windows x64 and Linux x86_64 portable core archives are published with preview.6 after their native workflow, notice, and distribution gates passed. Interactive GUI checks on those platforms still need testers.

## Capability boundary

The locally evidenced molecular calculation in this index is **RDKit ETKDG
plus MMFF/UFF force-field conformer generation and energy evaluation**. It is
a starting-geometry and model-energy workflow; it is not an experimental
measurement, a quantum result, or evidence of a global minimum.

ORCA and Q-Chem entries below cover checked preparation, lifecycle code, and
configuration handling only. Neither records a real quantum-chemistry run in
this checkout. The captured native workflow reports ORCA as
`NOT_CONFIGURED`; the Q-Chem lesson remains `PREPARED_NOT_RUN`.

## Feature map

| Feature | Product surface and source | Focused test or local evidence | Current status |
| --- | --- | --- | --- |
| `CHEM-015` First shape calculation | [beginner calculation](frontend/src/FirstCalculation.tsx); [MMFF94 relaxation](backend/src/hypothesislab/conformers.py) | [independent saved-geometry energy check](backend/tests/test_first_calculation.py); [compiled UI workflow](scripts/native_first_calculation_workflow.js) | Included real ETKDGv3/MMFF94 relaxation, initial/final SDF, signed energies, convergence, InChI match and reproducible report/hash record; ethanol `6.831185 -> -1.336852` kcal/mol; not quantum chemistry. |
| `CHEM-001` Build and count atoms | [feature catalog](frontend/src/featureIndex.mjs); [structure viewer](frontend/src/Viewer.tsx) | [beginner workflow test](frontend/test/beginner.test.js) | Local structure editing and RDKit inspection are implemented. |
| `CHEM-002` Compare starting shapes | [feature catalog](frontend/src/featureIndex.mjs); [RDKit conformer adapter](backend/src/hypothesislab/conformers.py) | [conformer handoff test](backend/tests/test_conformer_handoff.py) | Real local force-field conformer generation; no quantum interpretation. |
| `CHEM-003` Energy comparison chart | [shape-energy chart](frontend/src/ShapeEnergyChart.tsx) | [RDKit conformer adapter](backend/src/hypothesislab/conformers.py) | Relative MMFF/UFF model energies for one molecule and unit set only. |
| `CHEM-004` 3D keyboard controls | [3D viewer](frontend/src/Viewer.tsx) | [beginner workflow test](frontend/test/beginner.test.js) | Implemented UI control surface. |
| `CHEM-005` ORCA calculation | [feature catalog](frontend/src/featureIndex.mjs); [ORCA runtime](backend/src/hypothesislab/orca_runtime.py) | [runtime lifecycle test](backend/tests/test_orca_runtime.py); [native workflow harness](scripts/native_chem313_workflow.js) | Input preparation and lifecycle coverage exist; the native harness is not a passing-result artifact. Licensed ORCA is unconfigured and no quantum run is recorded. |
| `CHEM-006` Q-Chem guided lesson | [lesson record builder](frontend/src/qchemStudy.mjs); [Q-Chem runtime](backend/src/hypothesislab/qchem_runtime.py) | [lesson test](frontend/test/qchemStudy.test.js); [runtime lifecycle test](backend/tests/test_qchem_runtime.py) | Guided reviewed input preparation with learner gates; `PREPARED_NOT_RUN`. |
| `CHEM-007` Molecule identity check | [identity API](backend/src/hypothesislab/qchem_runtime.py) | [identity test](backend/tests/test_identity.py) | Coordinate-derived InChI match guard. The verified label appears only for a server match; it is not experimental identity or geometry validation. |
| `CHEM-008` Export and project records | [project store](backend/src/hypothesislab/store.py) | [workflow test](backend/tests/test_workflows.py) | Local immutable artifact and event-record support; recorded results distinguish provenance and electronic-energy units. |
| `CHEM-009` Qwen assistance | [feature catalog](frontend/src/featureIndex.mjs) | [coach test](backend/tests/test_qchem_coach.py) | Optional experimental drafting aid; proposals require review and are not scientific results. |
| `CHEM-010` Additional engines and scripts | [engine registry](backend/src/hypothesislab/engine_registry.py) | [registry test](backend/tests/test_public_runtime_registry.py) | Availability, installation, licensing, and validation vary by engine; inspect its declared integration before use. |

## Maintenance rule

When a catalog feature, module, focused test, or shipped source reference changes,
update its row in this file and run:

```sh
python3 scripts/check_project_index.py
```

The checker only confirms that this index's local links and feature IDs still
resolve. It does not run chemistry, certify a build, or establish scientific
validity.
