"""Add a public base-only model and frozen worker to an already built core app."""
import argparse
import json
from pathlib import Path
import plistlib
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'backend/src'))
from hypothesislab.qwen_worker import MODEL_ID, PUBLIC_FILES, verify_assets, digest

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--app', type=Path, required=True)
parser.add_argument('--model', type=Path, required=True)
parser.add_argument('--upstream', type=Path, required=True)
parser.add_argument('--worker', type=Path, required=True)
parser.add_argument('--site-packages', type=Path, required=True)
parser.add_argument('--pyinstaller-toc', type=Path, required=True)
parser.add_argument('--cpython-license', type=Path, required=True)
parser.add_argument('--openssl-license', type=Path, required=True)
args = parser.parse_args()
resources = args.app/'Contents/Resources'
if any((resources/name).exists() for name in ('models','workers')):
    parser.error('Refusing to replace model or worker directories')
verify_assets(args.model, None)
license_file = args.upstream/'LICENSE'
assert digest(license_file) == '50cbab8a892c5f2993b8c7351a99182507472def3b1374558308605d99b86b32'
model = resources/'models/qwen/public-model'
model.mkdir(parents=True)
for name in PUBLIC_FILES:
    shutil.copyfile(args.model/name, model/name)
shutil.copytree(args.worker, resources/'workers/qwen', symlinks=True)
notices = resources/'licenses/qwen-model'
notices.mkdir(parents=True)
shutil.copyfile(license_file, notices/'LICENSE')
shutil.copyfile(args.upstream/'README.md', notices/'UPSTREAM_MODEL_CARD.md')
(notices/'NOTICE.txt').write_text(
    'Qwen3.5-2B-Base by the Qwen team; Apache License 2.0.\n'
    'Upstream: https://huggingface.co/Qwen/Qwen3.5-2B-Base\n'
    'Revision: b1485b2fa6dfa1287294f269f5fb618e03d52d7c\n'
    'Modified for OpenChem: MLX affine quantization, 4 bits, group size 64,\n'
    'using mlx-lm 0.32.2. No private LoRA adapter or training dataset.\n'
    'The base model is experimental for structured chemistry drafting.\n')
(notices/'MANIFEST.json').write_text(json.dumps({
    'model':MODEL_ID, 'upstream_revision':'b1485b2fa6dfa1287294f269f5fb618e03d52d7c',
    'transformation':'MLX affine 4-bit group-size 64', 'adapter':None,
    'license':'Apache-2.0', 'model_files_sha256':PUBLIC_FILES,
    'notice_files_sha256':{p.name:digest(p) for p in notices.iterdir() if p.is_file()},
}, indent=2)+'\n')
subprocess.run([sys.executable, str(ROOT/'scripts/collect_qwen_licenses.py'),
    '--worker',str(resources/'workers/qwen'),'--site-packages',str(args.site_packages),
    '--pyinstaller-toc',str(args.pyinstaller_toc),'--cpython-license',str(args.cpython_license),
    '--openssl-license',str(args.openssl_license),'--output',str(resources/'licenses/qwen-runtime')], check=True)
plist = args.app/'Contents/Info.plist'
metadata = plistlib.loads(plist.read_bytes())
metadata['LSMinimumSystemVersion'] = '26.2'
metadata['CFBundleVersion'] = '13'
plist.write_bytes(plistlib.dumps(metadata))
shutil.copyfile(ROOT/'release/qwen/README.txt', resources/'README.txt')
subprocess.run(['codesign','--force','--sign','-',str(args.app)],check=True)
subprocess.run(['codesign','--verify','--deep','--strict',str(args.app)],check=True)
print('Assembled base-only offline Qwen app:', args.app)
