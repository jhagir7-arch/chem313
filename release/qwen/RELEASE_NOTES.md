# OpenChem 1.0.0-preview.2 — standalone Apple Silicon preview

OpenChem is a local chemistry workbench for molecule editing, checked input
preparation, results review, and traceable project records. This preview adds
an offline 4-bit Qwen3.5-2B-Base calculation-draft assistant to the bundled
core workflow.

## Download and install

Download the Apple Silicon archive, verify its published SHA-256 checksum,
then drag `OpenChem.app` to Applications.

Apple Silicon (M-series) Mac; macOS 26.2 or newer. Tested on macOS 27. No Python or Node installation is required.

The app is ad-hoc signed and unnotarized because this preview does not use an
Apple Developer Program signing identity. macOS may block an Internet download.
After verifying the archive, use Apple's Privacy & Security > Open Anyway
control to open this copy. Do not disable macOS security protections in
Terminal.

## Included

- Ketcher and Indigo molecule editing; RDKit structure inspection and 3D
  preparation; 3Dmol visualization.
- NumPy, SciPy, Matplotlib, Python runtime, reviewed recipes, and the
  input/results workflow.
- A bundled 4-bit `Qwen/Qwen3.5-2B-Base`, pinned to upstream revision
  `b1485b2fa6dfa1287294f269f5fb618e03d52d7c` under Apache-2.0.

## Excluded and optional components

No private LoRA adapter, dataset, or training records are included. ORCA is
external and requires the user's separately installed licensed copy.
Avogadro, PySCF, and tblite are optional and are not bundled.

## Known limitations

Qwen writes local drafts. It can produce invalid or conflicting proposals;
OpenChem's independent checks can reject detected problems, but passing a
check does not establish scientific correctness. Review all drafts and every
structure, charge, multiplicity, method, and generated input before use.
This preview makes no scientific benchmark claim.

OpenChem code is Apache-2.0. Third-party components and the Qwen model retain
their respective terms; see the bundled license and notice materials.
