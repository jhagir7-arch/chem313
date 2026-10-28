# Historical Qwen LoRA pilot

This is an experimental Apple Silicon training script from an earlier OpenChem effort. It is
not integrated into the Chem313 v2 app. The pinned upstream base is
[Qwen/Qwen3.5-2B-Base](https://huggingface.co/Qwen/Qwen3.5-2B-Base), revision
`b1485b2fa6dfa1287294f269f5fb618e03d52d7c`; its model card identifies Apache-2.0.
The script verifies the original model weight hash and uses `trust_remote_code=False`.

The script expects a specific historical D005 dataset with exact hashes and will not run
without it. The dataset and learned adapter are not included, and their public redistribution
rights have not been established. Do not infer permission to obtain, use or redistribute them
from this code. It is preserved to explain the experiment, not as a reproducible public
training recipe. A small pilot does not establish chemistry accuracy or safety.

The separate historical Qwen edition used a quantized base-only model; see
`release/qwen/BUILDING.md` for its source, conversion, and license procedure. The current
v2 app does not ship Qwen. Training outputs, model files, datasets and personal records are
not part of this source archive.
