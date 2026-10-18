# OpenChem

A local chemistry workbench for building molecules, preparing calculations, and keeping traceable research records.

Draw or import a structure, inspect its molecular properties, generate a starting geometry, and review the exact calculation input before saving it. The desktop interface uses a restrained monochrome layout and native macOS File, Edit, View, Calculation, Window and Help menus.

**Version 1.0.0-preview.1 — research preview.** This first public version includes source and a compiled Apple Silicon native shell. The shell requires the separately installed local runtime below; it is not a self-contained installer. Python, scientific engines, Avogadro, ORCA and model assets are not bundled.

## Start on Apple Silicon macOS

Install Python 3.13, Node.js 24.20 or later and Apple's Xcode command-line tools. Download and extract the source archive, then run in that folder:

```sh
bash scripts/setup_public_runtime.sh
bash scripts/build_public_app.sh
open "dist/OpenChem Public.app"
```

Choose that source folder when the app asks. It remembers the folder. Keep the folder in place: its `.venv` and locally built interface supply the app's runtime. The setup command downloads npm/Python dependencies under their upstream licenses; it does not fetch models or external applications. The compiled shell from Releases works with the same configured source folder, without recompiling.

The preview is ad-hoc signed, not Developer ID signed or notarized. macOS may block the downloaded shell; inspect the source and build it locally if you prefer. Tested on macOS 27 arm64; the compiled shell targets macOS 14+, but other macOS versions are unverified.

For a browser session instead of the native shell:

```sh
.venv/bin/python -m hypothesislab.desktop --ui frontend/dist
```

Open the loopback URL printed by the service. Project files are stored locally in `~/Library/Application Support/OpenChem`. No cloud service is required after dependencies are installed. You can select a different configured source folder by launching the shell with `OPENCHEM_SOURCE_ROOT` set to its absolute path.

## Molecule to calculation

1. Draw in Ketcher, enter SMILES or open a MOL file. Inspect formula, charge, stereochemistry and RDKit descriptors.
2. Generate an explicit-hydrogen 3D starting geometry with RDKit ETKDG and MMFF/UFF. Drawing changes invalidate the geometry.
3. Prepare ORCA input with explicit charge, multiplicity, method, basis and calculation type. Review and preserve the exact SDF, INP and report.
4. Configure a separately licensed ORCA executable to run an input. Its runner records output; inspect convergence separately in Results.
5. Keep original bytes and derived outputs in a content-addressed project record. Check artifact hashes and inspect job history.

The Results reader links extracted ORCA facts to source lines and distinguishes normal termination from convergence. Measurement tools fit CSV data and preserve units and reports. Research scripts run up to eight reviewed, allowlisted operations from versioned JSON; they do not execute arbitrary Python or shell commands.

## Optional integrations

- **Scientific workers:** `bash scripts/install_engines.sh` uses separately installed [uv](https://docs.astral.sh/uv/getting-started/installation/) to create isolated environments and run integration checks. It downloads substantial additional dependencies. Adapter coverage includes selected PySCF RHF and tblite GFN2 single points, units, arrays, spectra, structures and bioscience operations. An adapter does not provide every feature of the upstream application.
- **Avogadro:** install [Avogadro](https://avogadro.cc/) separately. Discovery checks normal Applications folders; set `OPENCHEM_AVOGADRO_APP` to an absolute `.app` path for a custom location. The companion transfer checks selected MOL fields. Full plugin and metadata compatibility is unverified.
- **ORCA:** obtain [ORCA](https://www.faccts.de/orca/) under its own terms. Enter its absolute executable path in calculation preparation or set `OPENCHEM_ORCA_EXECUTABLE` before launch. Real licensed ORCA execution has not been tested here; runner lifecycle tests use controlled fixtures.
- **Qwen:** experimental typed draft integration source is included. Model weights, the local 25-update training adapter and datasets are excluded. The public package cannot draft with Qwen out of the box; its unavailable state is intentional. General chemistry competence has not been established.

The runtime registry distinguishes installed components from bundled components and records limited checks. No set of 54 complete applications is compiled into OpenChem.

## Verify and benchmark

```sh
python3 benchmarks/verify_bundle.py
.venv/bin/python benchmarks/run.py --suite core --output benchmark-results
npm --prefix frontend test
npm --prefix frontend run build
```

`verify_bundle.py` applies to the packaged source snapshot and checks its manifest. The core benchmark explicitly deselects three real worker tests when their science environment is absent. The original private archive test and six third-party ORCA fixture tests skip because those files are excluded. Skips are not passing scientific tests. Optional engine checks need their own installed environments.

Generated conformers are starting geometries. Integration/reference checks do not establish method suitability, experimental accuracy or superiority to other software. Worker processes are trusted local processes, not an OS security sandbox. Independent researcher acceptance, broader compatibility and real licensed ORCA runs remain open work.

## License and contributions

OpenChem-originated code and documentation are under [Apache-2.0](LICENSE). Dependencies retain their own terms; no third-party engine or model is relicensed. See [NOTICE](NOTICE), [third-party notices](THIRD_PARTY_NOTICES.md), [source origin](SOURCE_ORIGIN.md), [release scope](PUBLICATION_STATUS.md), [contributing](CONTRIBUTING.md) and [security](SECURITY.md).
