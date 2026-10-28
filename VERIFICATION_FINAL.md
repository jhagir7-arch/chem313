# Chem313 2.0.0-alpha.1 — final local verification

2026-10-28. This addendum supersedes the staging-time test failures described in REVIEW_2026-10-28.md. Historical staging evidence remains intact.

## Passed on Apple Silicon macOS

- Backend: 299 tests passed after the final symlink guard (13 warnings, 7 subtests), in 80.70 seconds. Earlier startup timeouts did not recur in this final full run.
- Interface: 8 unit tests; Rust host: 2 tests; notice collector: 7 tests. TypeScript, Vite production bundle and native Tauri app compilation passed.
- The new frozen engine completed water, methane and ethanol MMFF94 runs and a phenol UFF run. All 12 artifacts passed hash/size checks. Eight geometry energies were independently reconstructed with RDKit to an absolute tolerance of 0.000001 kcal/mol. See V2_FROZEN_QA.json.
- The compiled Chem313.app completed water, methane, ethanol and a custom phenol calculation through its interface. Canonical identity matched, a real 3D phenol structure rendered, the units toggle worked, and a native save dialog exported a parseable JSON record. Restart restored all eight saved calculations and their corresponding molecule identities.
- Editing the Water starter to ethane in Ketcher produced a C2H6 calculation, confirming the fresh drawing reached the engine. Quitting removed both the app and its bundled engine process.

These are real force-field geometry relaxations, not quantum calculations. Their energies are method-dependent molecular-mechanics values and do not establish reaction feasibility, experimental agreement or a global minimum.

## Release restrictions

This is a source-only alpha. The local Mac build is for local testing; it is not a cleared downloadable installer. Its notice inventory still has 12 unresolved objc2-family upstream notice gaps. It lacks Developer ID signing and notarization.

Windows and Linux source/build workflows are present, but no cross-platform interactive app verification is claimed. The first public matrix exposed optional private-worker assumptions and POSIX-only quantum-runtime simulators in legacy tests. Corrections and build reports must be reviewed before offering installers. No ORCA, Q-Chem or Qwen runtime is included.

Native file import, comprehensive keyboard/VoiceOver use and testing with beginners remain unverified. No claim of production readiness or scientific validation is made.

The initial BUNDLE_MANIFEST.json identifies the imported source snapshot; subsequent Git commits are the authoritative record of later test and verification corrections.

The final source commit e5213b012f59cc4a66e694e1e2c17b01a0310667 adds explicit event-log symlink rejection without O_NOFOLLOW. On Windows, checking and opening are separate operations; concurrent hostile replacement remains a limitation. The updated frozen engine passed the four-molecule smoke again.

The final retained Mac app was rebuilt with that frozen engine and passed an additional native water run (0.704764 to 0.000008 kcal/mol, identity match). App and child process both exited after Quit. Public Source checks passed for the tagged commit. The source prerelease is https://github.com/jhagir7-arch/chem313/releases/tag/v2.0.0-alpha.1 .

Cleanup: 31 superseded installers and duplicate apps were moved to recoverable Trash (27.0 GiB logical size). One final app remains at ~/general/Chem313-v2/Chem313.app. Source trees, source archives, saved calculations and personal documents were preserved. Work is stopped; installer notice clearance, signing and native Windows/Linux validation remain open.
