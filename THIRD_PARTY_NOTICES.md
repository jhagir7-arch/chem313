# Third-party notices and distribution boundary

Chem313 1.0.0-preview.3 supplies the standalone molecular-study core.
Apache-2.0 applies to project-originated code and documentation. Dependencies
retain their own terms. No upstream endorsement or ownership is implied.

The preview.3 app contains only the `standalone-core` inventory below. Qwen,
MLX and model notices are retained here for the historical OpenChem preview.2
model edition and its optional source builders; they are not bundled in the
preview.3 core. The source ZIP contains no installed runtimes or weights.

## Artifact-local notices

Inside Chem313.app/Contents/Resources/licenses (historically OpenChem.app):

- `standalone-core`: exact wheel/production npm notices, CPython license,
  font notices and native payload ownership manifest for the chemistry core.
- `qwen-runtime` (preview.2 model edition only): wheel notices and native ownership manifest for the separate
  frozen CPython 3.12 / MLX worker, including Metal payloads. Retained CPython,
  OpenSSL, SQLite and mpdecimal notices accompany this inventory.
- `qwen-model` (preview.2 model edition only): original Apache-2.0 LICENSE, upstream model card, transformation
  NOTICE and pinned model-file SHA-256 manifest.

Manifests map native files to wheel RECORD or the exact PyInstaller collection
source, recording packaged hashes after load-path/signature transformations.
They are artifact inventories, not a scientific validation or a claim of
source equivalence to an unrelated downloaded development archive.
PyInstaller's bootloader is distributed under its GPL exception permitting
bundled applications; the original terms are retained among runtime notices.
System AppKit, WebKit, Metal and other macOS frameworks are not copied.

## Component inventory

This combined table includes core components and historical optional Qwen components.

| Component | Version | Upstream license family / notice location |
| --- | --- | --- |
| RDKit | 2026.9.1 | BSD-3-Clause and bundled notices; standalone-core |
| NumPy | 2.5.4 | BSD-3-Clause and bundled notices; both runtime inventories |
| SciPy | 1.18.1 | BSD-3-Clause and bundled notices; standalone-core |
| Matplotlib | 3.11.2 | Matplotlib and bundled font/library notices; standalone-core |
| Ketcher | 3.18.0 | Apache-2.0 and dependency notices; standalone-core |
| Indigo | 1.46.0 | Apache-2.0; standalone-core |
| 3DmolJS | 2.5.5 | BSD-3-Clause; standalone-core |
| React / React DOM | 18.3.1 | MIT; standalone-core |
| CPython | 3.13.14 core / 3.12.15 Qwen | PSF and bundled notices |
| MLX / mlx-metal | 0.32.4 | MIT and retained dependencies; qwen-runtime |
| mlx-lm | 0.32.2 | MIT; qwen-runtime |
| Transformers | 5.20.1 | Apache-2.0; qwen-runtime |
| Qwen3.5-2B-Base | pinned revision below | Apache-2.0; qwen-model |

The Qwen upstream revision is `b1485b2fa6dfa1287294f269f5fb618e03d52d7c`
from https://huggingface.co/Qwen/Qwen3.5-2B-Base . OpenChem converts its
weights with MLX affine 4-bit quantization, group size 64. This modification
is declared in the model NOTICE. The public app uses no private LoRA adapter,
distillation dataset, training record or model downloaded at launch.

Exact transitive package versions and complete captured notices are in the
runtime manifests. The npm inventory is conservative rather than a proof of
what tree-shaking removed. Native components statically linked into upstream
wheels depend on the original supplier's bundled notices; the inventory does
not claim to reconstruct every source-level build input.

## Excluded components and source archive

ORCA, Avogadro, Open Babel, Qt, PySCF, tblite and the broader optional workers
are not bundled. ORCA must be obtained and licensed separately. References
and optional adapters do not relicense these applications or incorporate
all their features into OpenChem.

The corresponding source ZIP excludes installed dependencies, model weights,
private adapters/datasets, researcher data, handoff archives and Git history.
It includes the build/notice-collection scripts and locked runtime requirements.
Six third-party cclib-data ORCA output fixtures remain excluded because their
redistribution license was not established. Their provenance manifest alone
is retained; missing-fixture tests explicitly skip in the public snapshot.

The earlier preview.1 native shell was source-runtime based. Its narrower
distribution scope is preserved in its original release, not used to describe
the standalone preview.2 download. Product names remain their owners' marks.
