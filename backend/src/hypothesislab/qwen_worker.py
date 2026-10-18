"""Offline MLX inference worker. No chemistry tools, filesystem tools, or execution."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import sys
import time

MODEL_ID = 'Qwen/Qwen3.5-2B-Base'
MODEL_SHA = '928acbf11878c32185bbd863514d191769285065ab9ea14fbfe431303f5fdf2d'
ADAPTER_SHA = '0679de73f6748d3ae49a2ce9c52beb787beee4f6178b1b8b64c00178d381a7d6'
SYSTEM = '''Draft a molecule and ORCA calculation for a chemistry workbench. Return ONLY one JSON object with exactly these keys: action, smiles, job_type, charge, multiplicity, method, basis, message. action is proposal or clarify. For proposal: smiles is one molecular SMILES; job_type is single_point, optimization, or optimization_frequency; charge is an integer; multiplicity is a positive integer; method is HF, B3LYP, PBE0, or r2SCAN-3c; basis is def2-SVP, or built-in for r2SCAN-3c. For clarify, all six chemistry fields are null and message asks for the missing information. Ask for clarification if molecule identity, charge, multiplicity or calculation choices are missing. Preserve explicit requested choices. Never claim results, execution or chemical validation. Never invoke tools or shell commands. Optimization and frequencies always means job_type optimization_frequency, never optimization alone. For clarification message ask: Which molecule, charge, multiplicity, method and calculation type do you want? Example request: Build methane C, charge 0, multiplicity 1, HF def2-SVP single point. Example response: {"action":"proposal","smiles":"C","job_type":"single_point","charge":0,"multiplicity":1,"method":"HF","basis":"def2-SVP","message":"Review the proposed methane structure and requested calculation settings."}'''


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024*1024), b''):
            h.update(chunk)
    return h.hexdigest()


def assets():
    if getattr(sys, 'frozen', False):
        root = Path(sys.executable).resolve().parents[2] / 'models' / 'qwen'
        return root / 'model', root / 'adapter'
    root = Path(__file__).resolve().parents[3]
    return root/'training/models/Qwen3.5-2B-Base', root/'training/runs/qwen35-2b-d005-pilot-001/adapter'


def main():
    os.environ['HF_HUB_OFFLINE'] = '1'
    os.environ['TRANSFORMERS_OFFLINE'] = '1'
    payload = json.loads(sys.stdin.buffer.read(20_000))
    prompt = payload.get('prompt')
    if not isinstance(prompt, str) or not 1 <= len(prompt.strip()) <= 4000:
        raise ValueError('A prompt of 1..4000 characters is required')
    model_path, adapter_path = assets()
    if digest(model_path/'model.safetensors-00001-of-00001.safetensors') != MODEL_SHA or digest(adapter_path/'adapters.safetensors') != ADAPTER_SHA:
        raise ValueError('Pinned local model or trained adapter failed its integrity check')
    import mlx.core as mx
    from mlx_lm import load, stream_generate
    from mlx_lm.sample_utils import make_sampler
    mx.set_memory_limit(10*1024**3)
    started = time.monotonic()
    model, tokenizer = load(str(model_path), adapter_path=str(adapter_path), trust_remote_code=False)
    tokenizer.add_eos_token('<|im_end|>')
    text = tokenizer.apply_chat_template([{'role':'system','content':SYSTEM},{'role':'user','content':prompt}], add_generation_prompt=True, enable_thinking=False)
    raw = ''
    for result in stream_generate(model, tokenizer, text, max_tokens=320, sampler=make_sampler(temp=0)):
        raw += result.text
        # Stop after a complete JSON object; never execute text emitted by the model.
        try:
            value = json.loads(raw)
            if isinstance(value, dict):
                break
        except ValueError:
            pass
    print(json.dumps({'raw':raw,'seconds':round(time.monotonic()-started,3),'model':MODEL_ID,'adapter_sha256':ADAPTER_SHA}), flush=True)


if __name__ == '__main__':
    main()
