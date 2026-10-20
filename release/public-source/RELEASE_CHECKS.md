# Chem313 preview.3 verification

Verified locally on Apple Silicon macOS 27. Frontend package 1.0.0-preview.3.

- TypeScript and Vite production build: passed. The large Ketcher bundle warning remains.
- Frontend: 40 tests passed, none skipped.
- Focused backend identity, Q-Chem runtime, ORCA runtime and Qwen coach checks: 43 passed. Runner lifecycle fixtures are controlled test programs, not licensed quantum engines.
- Combined focused backend suite (identity/runners/coach plus portable launcher/notices/profile): 69 passed. The portable subset passed independently too. These are local tests; they do not substitute for native Windows/Linux evidence.
- Frozen Mac package, with no Python or Node on PATH: passed real RDKit, ORCA input preparation, immutable artifacts, known NumPy/SciPy references, Matplotlib SVG output, authentication/origin/replay checks and quit/relaunch persistence.
- Compiled AppKit / WKWebView workflow: passed real MMFF calculations for water (3 atoms), methane (5) and ethanol (9); coordinate-derived identity checks; the guided Q-Chem learner review and checked-input download gate; searchable feature directory; five real butane samples, energy-chart selection and accessible 3D rotation controls.
- Fresh compiled core reports ORCA and Q-Chem NOT_CONFIGURED and Qwen UNAVAILABLE. No false quantum-run success is accepted.
- Native standard menus verified: File, Edit, View, Calculation, Window and Help.
- Ad-hoc code signature verification: passed. Developer ID signing and notarization were not performed.
- Core native payload license/checksum gate: passed. Mach-O architecture, external dependency and macOS 14 deployment-target audit: 243 native files passed in the initial final-core candidate. Other macOS versions and architectures are untested.
- Project-index links, feature IDs, catalog evidence paths and package version: checked locally and in the staged source snapshot.

Packaging verifies component ownership and archive hashes. These are bounded workflow and numerical checks, not independent scientific validation. ORCA and Q-Chem are separately licensed and neither has run a real quantum job here. Qwen has no expert-checked chemistry competency result and is not bundled in this core candidate.

Windows currently has unresolved Microsoft runtime redistribution terms. Linux needs a fresh native run to verify exact system-library notice capture. The native workflow may retain smoke evidence for blocked candidates, but cannot archive or offer downloads until both license and distribution gates pass.

The source snapshot excludes private correspondence, handoffs, research projects, training data, adapters and Git history. Use the specifically named corresponding source asset when checking a binary; GitHub's automatic tag archive only represents the repository commit the tag points to.
