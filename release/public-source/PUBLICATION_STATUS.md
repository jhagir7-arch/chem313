# Release scope: Chem313 1.0.0-preview.5

Chem313 was previously named OpenChem. The new name distinguishes this application from the unrelated Mariewelt/OpenChem project. Existing repository URLs, internal identifiers and project data paths remain compatible.

The standalone core contains a frozen CPython service, Ketcher/Indigo, RDKit, 3Dmol, NumPy, SciPy and Matplotlib. It contains no ORCA or Q-Chem executable, Qwen model, private adapter, training dataset, Avogadro binary or optional science-worker environments.

Verified checks must distinguish frontend/unit tests, frozen service tests and compiled native workflow tests. These prove only the documented workflow and bounded numerical checks. A fake executable used in runner lifecycle tests is never evidence of a real licensed quantum calculation. The first real ORCA / Q-Chem calculation remains pending.

The Mac candidate is ad-hoc signed, not Developer ID signed or notarized. The binary audit determines its minimum deployment target; other OS releases and architectures remain untested unless explicitly recorded. Windows/Linux workflows must pass native smoke and notice gates before a download is offered. Failed or license-blocked builds retain evidence only.

The source archive excludes private correspondence, handoff archives, Git history, installed dependencies, model weights, training data, user projects and third-party fixtures with unresolved redistribution rights. Component notices and source-origin records accompany the permitted application code. No dependency is relicensed by the application's Apache-2.0 grant.
