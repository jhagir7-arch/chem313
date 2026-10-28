# Release scope: Chem313 2.0.0-alpha.1

This is a source alpha for the consolidated Tauri desktop workbench. Historical preview.6 portable downloads are separate artifacts and are not evidence that v2 has passed.

The v2 source provides a catalog-driven Ketcher/3Dmol interface, SMILES/molfile import, real RDKit MMFF94/UFF shape relaxation, saved immutable reports and native dialogs. It includes no ORCA or Q-Chem executable, Qwen model, private adapter, training dataset, Avogadro binary or optional science-worker environments. No real quantum-chemistry calculation is claimed.

The 2026-10-28 review corrected structure draft leakage, ignored starter edits, stale snapshots, force-field parameter validation, ambiguous stereo and multi-record SDF handling, duplicate-run prevention, startup timeout/cleanup and a returning-watchdog defect. See VERIFICATION_FINAL.md for the completed local checks and REVIEW_2026-10-28.md for the earlier staging record.

Installer publication requires native frozen-engine smoke, app checks and dependency notices on each platform. The current local macOS notice review retains 12 unresolved objc2-family notice gaps. Those are preserved as exact upstream revision evidence, not silently marked clear. Unpassed installers must not be attached as downloads. Source-only publication includes no compiled third-party crates.

A local build is not publication, an API smoke test is not a native interface test, and a Mac check does not validate Windows/Linux. Failed or blocked builds retain their reports. macOS builds remain ad-hoc signed, without Developer ID signing or notarization.

The allowlisted source archive excludes private correspondence, handoff archives, private Git history, installed dependencies, model weights, training data, user projects and third-party fixtures with unresolved redistribution rights. The app Apache-2.0 license covers project-originated code, not third-party components.
