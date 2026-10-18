# Preview verification

Version: 1.0.0-preview.1. Verified locally on Apple Silicon macOS 27.0.1, Python 3.13.14 and Node 24.20.0.

- Fresh isolated Python and npm dependency installation: passed.
- TypeScript and Vite production build: passed.
- Core backend: 150 passed, 7 subtests passed; 1 private-archive test skipped and 3 real scientific-worker tests deselected.
- Frontend: 13 passed; 6 optional third-party ORCA fixture cases skipped.
- Real RDKit conformer reference/timing cases: water, ethanol and benzene passed.
- Compiled AppKit/WKWebView shell: connected to the clean source runtime, loaded Ketcher, preserved V3000 MOL through Fit structure, generated a real conformer and prepared checked ORCA input. Qwen correctly reported UNAVAILABLE without model assets.
- Native menus dispatched through File/Edit/View/Calculation/Window/Help routing checks.
- Local API workflow: rejected untrusted origins and unauthenticated reads; checked charge/spin; saved exact SDF/INP/report; preserved UTF-8 note bytes; rejected review-token replay; fitted a known line; produced SVG; verified stored hashes.
- Compiled shell code signature: ad-hoc, strict verification passed. Developer ID signing and notarization were not performed.

These are integration/reference checks, not independent scientific validation. Real licensed ORCA execution and public Qwen inference were not run. Remote GitHub CI is a separate run and must be inspected after publication.

The npm installation reports six low-severity findings in the browser polyfill dependency tree. No forced major dependency change was applied. Build warnings include upstream 3Dmol eval usage and a large Ketcher bundle. Treat dependency updates and compatibility/performance testing as ongoing preview work.

The source archive has a SHA-256 file manifest. Release asset checksums identify the exact downloadable archives. No private development DMG or third-party runtime payload is part of this preview.
