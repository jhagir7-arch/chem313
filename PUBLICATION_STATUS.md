# Release scope: 1.0.0-preview.1

This public research preview supplies OpenChem-originated source under Apache-2.0 and a compiled native macOS shell that uses a separately installed local source runtime. It does not supply a self-contained chemistry runtime or the earlier private development DMG.

Resolved for this scope:

- Selected and included the project license, NOTICE, source-origin statement and dependency notices.
- Removed unlicensed third-party ORCA outputs, original archives, private provenance, training data, model/adapter assets and installed dependencies from the public export.
- The compiled shell ships no browser bundles, Python packages, workers, Avogadro, Open Babel, Qt or ORCA. Their dependencies are obtained separately, so this release does not redistribute those binaries.
- Added reproducible local setup and native-shell compilation. Missing optional components are reported as unavailable, not bundled or scientifically validated.

Still outside this release: Developer ID signing/notarization, a fully bundled installer with a complete binary SBOM and applicable redistribution materials, a distributable trained Qwen adapter, independent scientific validation, real licensed ORCA execution and broad macOS compatibility testing.

The original development builds remain local. Their older license notices and included assets do not define this public preview's distribution scope.
