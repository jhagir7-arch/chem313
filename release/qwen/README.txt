OpenChem 1.0.0-preview.2 — Apple Silicon Mac

Install

1. Download the release archive and verify its published SHA-256 checksum.
2. Open the archive and drag OpenChem.app to Applications.
3. Open OpenChem from Applications.

Apple Silicon (M-series) Mac; macOS 26.2 or newer. Tested on macOS 27. No Python or Node installation is required.

This preview is ad-hoc signed and is not notarized because it does not use an
Apple Developer Program signing identity. macOS may block an app downloaded
from the Internet. After confirming the archive checksum and source, use
Apple's Privacy & Security > Open Anyway option to open this copy. Do not
disable macOS security protections in Terminal.

Included

OpenChem bundles Ketcher and Indigo for molecule editing, RDKit structure
inspection and 3D preparation, 3Dmol, NumPy, SciPy, Matplotlib, a Python
runtime, and the recipes plus input/results workflow. It also bundles a 4-bit
Qwen3.5-2B-Base model for local calculation drafts. The upstream model is
Qwen/Qwen3.5-2B-Base revision
b1485b2fa6dfa1287294f269f5fb618e03d52d7c, under Apache-2.0.

Not included

This release contains no LoRA adapter, training dataset, or training records.
ORCA is not included; running it requires a separately installed,
user-licensed ORCA executable. Avogadro, PySCF, and tblite are optional and
are not bundled.

Use and limits

Qwen produces drafts only. It can produce invalid or internally conflicting
proposals, which OpenChem may reject through its independent checks. Review
every surviving proposal, molecular structure, charge, multiplicity, method,
and generated input before use. It does not replace chemical judgment or
scientific validation.

Project data is stored locally in ~/Library/Application Support/OpenChem.
Keep original source files and back up projects after quitting the app.

OpenChem code is Apache-2.0. Bundled components retain their own terms; see
LICENSE, NOTICE, THIRD_PARTY_NOTICES.md, and the app's bundled licenses.
