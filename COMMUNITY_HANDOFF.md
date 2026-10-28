# Community handoff

This repository contains the community desktop beta source and historical modules. Development is paused; historical plans are
preserved for context, not promises or current release instructions. The repository does not
include installed engines, datasets, private adapters or model weights.

| Area | Source | Status and boundary |
| --- | --- | --- |
| Current desktop | `app/` | Tauri v2 shell and Structure, 3D, Setup and Results workflow. The RDKit sidecar relaxes supported single molecules with MMFF94 or UFF. |
| Engine and records | `backend/` | Local API, validation and content-addressed calculation artifacts. Force-field energy is not a quantum result, experiment or proof of a global minimum. |
| Historical interface | `frontend/`, `desktop/` | Earlier Swift/WKWebView and portable work remain as source. They are not the current v2 shell. |
| Qwen | `backend/src/hypothesislab/qwen_worker.py`, `release/qwen/`, `training/public/` | Experimental historical workflows, separate from v2. The earlier public Qwen edition used a quantized base-only model; the training pilot and its private adapter are distinct. No weights, dataset or adapter are included. |
| External engines | backend adapters and `native/` | ORCA and Q-Chem require independent licensed installations; no quantum engine or license is bundled by this source archive. |
| Plans | `docs/history/` | Sanitized historical design records; outcomes and future proposals require fresh verification. |

The native release workflow builds each target independently and withholds the entire release if a package fails its tests, notice coverage or extracted-engine calculation check. See [desktop release scope](docs/DESKTOP_RELEASE.md). The earlier 12 objc2-family notice gaps now have full upstream license texts and revision provenance; upstream Apple SDK derivation boundaries remain documented. Signing, notarization and GUI testing are separate from these automated gates.

Known product gaps include accessibility and keyboard operation of the 3D viewer, broad molecule
and stereochemistry support, robust process lifecycle and record migration, and independent
scientific and usability review. External engine integration, Qwen, add-on tiers and persistent
long-running queues are not presented as completed v2 features. Consult the tests and current
source before relying on a historical plan. Contributions should preserve input provenance and
report convergence and model limits honestly.

Historical scripts in `scripts/` include opt-in UI and engine checks. They target the
earlier application, require locally installed test dependencies and sometimes a simulated
engine or a locally configured Qwen model. Some browser checks use the standard macOS
Chrome application path. They are not v2 release checks or evidence of a scientific result.

The following historical scripts are intentionally excluded from the public archive:

- `scripts/build_app.sh` and `scripts/build_qwen_worker.sh`: depend on the private trained adapter and local model artifacts.
- `scripts/native_calculation_workflow.js` and `scripts/native_research_workflow.js`: assert the identity of that private adapter and require it to run.
- `scripts/native_qchem_execution.js`: embeds a machine-specific simulated engine path.
- `scripts/package_framework.py`: gathers private training and source receipt metadata.
- `scripts/prepare_release.py`: depends on private provenance and acquisition receipts.
- `scripts/package_mac.sh`: packages the old private-dependent application build, not the public source release.

The public Q-Chem execution UI check requires a separately provisioned simulated engine;
its expected outputs are explicitly synthetic. Historical checks have not been revalidated
as current release tests.
