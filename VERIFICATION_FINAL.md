# Chem313 2.0.0-alpha.1 — final local verification

2026-10-28. This addendum supersedes the staging-time test failures described in REVIEW_2026-10-28.md. Historical staging evidence remains intact.

## Passed on Apple Silicon macOS

- Backend: 298 tests passed (13 warnings, 7 subtests), in 18.68 seconds after concurrent builds ended. Earlier startup timeouts did not recur in this sequential full run.
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
