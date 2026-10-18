# OpenChem

A local chemistry workbench for building molecules, preparing calculations and keeping traceable research records. A restrained monochrome desktop interface with native macOS File, Edit, View, Calculation, Window and Help menus.

## Download the standalone Mac app

[OpenChem 1.0.0-preview.2 with offline Qwen](https://github.com/jhagir7-arch/openchem/releases/tag/v1.0.0-preview.2)

Download the DMG and drag OpenChem.app to Applications. **No Python or Node installation is required.** Requires Apple Silicon and macOS 26.2+. Tested on macOS 27; other versions are untested. Verify the release SHA256SUMS before opening.

This free research preview is **ad-hoc signed and unnotarized**, without Developer ID signing. macOS may block first launch. Follow [Apple's guidance for opening a trusted app](https://support.apple.com/102445); do not disable system security protections.

## Molecule to calculation

1. Draw with Ketcher, enter SMILES or import a MOL file. Inspect formula, charge, stereochemistry and RDKit descriptors.
2. Generate an explicit-hydrogen starting geometry with RDKit. Changes to the drawing invalidate that geometry.
3. Draft a structure and calculation settings with the bundled offline Qwen assistant. Review the draft and explicitly Apply it.
4. Review and save exact ORCA inputs with charge, multiplicity, method and basis. Running ORCA requires a separately installed, user-licensed executable.
5. Review ORCA results with source-line evidence; fit CSV data; run reviewed numerical recipes; preserve original files and derived artifacts in local project records.

## Included and optional engines

The standalone Qwen edition includes Ketcher/Indigo, RDKit, 3Dmol, CPython, NumPy, SciPy, Matplotlib, MLX and a 4-bit Qwen3.5-2B-Base. The model is pinned to upstream revision b1485b2fa6dfa1287294f269f5fb618e03d52d7c under Apache-2.0. It is the upstream base model, without the private fine-tuned adapter, datasets or training records.

ORCA, Avogadro, PySCF and tblite are not bundled. They require separate installation and applicable licenses. The registry distinguishes available operations from missing engines; this app does not contain 54 complete upstream applications.

## Verification and limits

The compiled native workflow and frozen service passed offline Qwen drafts, explicit Apply, RDKit geometry, reviewed ORCA input saving, numerical reference checks, CSV fitting, synthetic results review, persistence and artifact integrity. Backend: 160 tests plus 7 subtests; frontend: 19 tests. Packaging includes native ownership/license manifests and pinned model hashes.

Actual licensed ORCA execution, independent scientific validation and broader macOS compatibility remain unverified. Qwen can produce incorrect drafts. A passing structural check does not establish scientific correctness. Generated geometries are starting points, and calculation settings require researcher review. Worker subprocesses are not an OS security sandbox.

## Corresponding source and building

For preview.2, use **OpenChem-1.0.0-preview.2-Source.zip**, attached to the release. It contains the corresponding source, dependency locks, build scripts and verification notes. Start with release/qwen/BUILDING.md. Model weights and installed dependencies are separate from the source archive.

The repository's application source remains the earlier preview.1 baseline. GitHub's automatic “Source code” archives follow the tag; use the specifically named preview.2 Source.zip attachment for this binary. The earlier preview.1 native shell requires a separately configured runtime and remains available as a historical release.

Projects are stored locally in ~/Library/Application Support/OpenChem. Keep original scientific files and back up projects after quitting.

## License

OpenChem-originated code and documentation are [Apache-2.0](LICENSE). Third-party engines and models retain their own terms. The standalone app includes LICENSE, NOTICE, THIRD_PARTY_NOTICES.md and component license manifests. See the corresponding source archive for its current release scope and notices. Private handoffs, projects, Git history and training material are excluded.
