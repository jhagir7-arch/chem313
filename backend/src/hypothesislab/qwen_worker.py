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
PUBLIC_FILES = {
    'README.md':'748c964f9b7e5f2c3770ce013bbc0153be7c54311d9692c343b6188eefe77ac6',
    'chat_template.jinja':'273d8e0e683b885071fb17e08d71e5f2a5ddfb5309756181681de4f5a1822d80',
    'config.json':'8893a91e9b7763d7b94c6db181f5b7c79c6f4881a69cefb11549eefcab1823bf',
    'model.safetensors':'cdafd8bae44b62e95217e5003e11fb17f84c8a288a16b21f61697a14737ed004',
    'model.safetensors.index.json':'3b2dffa510d1d73decdbc12d5e1bc7d6a9f7b2deb631bfd84238a1f8fc4e0fd1',
    'tokenizer.json':'a5cd9732badce41de57e6efce8302930ded1c1188c5f81feb2bd6c24c4a1941f',
    'tokenizer_config.json':'3640340d27b78184da3c389832848421a8c161f412a32d01266a1fa6bb004059',
}
PUBLIC_VARIANT = 'base-4bit-no-adapter'
SYSTEM = '''Draft a molecule and ORCA calculation for a chemistry workbench. Return ONLY one JSON object with exactly these keys: action, smiles, job_type, charge, multiplicity, method, basis, message. action is proposal or clarify. For proposal: smiles is one molecular SMILES; job_type is single_point, optimization, or optimization_frequency; charge is an integer; multiplicity is a positive integer; method is HF, B3LYP, PBE0, or r2SCAN-3c; basis is def2-SVP, or built-in for r2SCAN-3c. For clarify, all six chemistry fields are null and message asks for the missing information. Ask for clarification if molecule identity, charge, multiplicity or calculation choices are missing. Preserve explicit requested choices. Never claim results, execution or chemical validation. Never invoke tools or shell commands. Optimization and frequencies always means job_type optimization_frequency, never optimization alone. For clarification message ask: Which molecule, charge, multiplicity, method and calculation type do you want? Example request: Build methane C, charge 0, multiplicity 1, HF def2-SVP single point. Example response: {"action":"proposal","smiles":"C","job_type":"single_point","charge":0,"multiplicity":1,"method":"HF","basis":"def2-SVP","message":"Review the proposed methane structure and requested calculation settings."}'''
STUDY_SYSTEM = '''You classify a beginner molecular-shape teaching request. Return ONLY one JSON object with exactly these keys: task, molecule, samples. task is one of shapes, mixture, clarify, unsupported. molecule is a lowercase named molecule or null. samples is an integer or null. For a named molecule shape request, return task shapes, its lowercase name, and 5 samples unless the user explicitly asks for 1 through 8 samples; preserve an explicit count in that range. Questions about ethanol reacting with water, mixing with water, or interacting with water are the ethanol-water teaching lesson: return task mixture, molecule null, samples null. Other reaction questions are unsupported. If the molecule is unspecified, return task clarify, molecule null, samples null. Medication, degradation, barriers, arbitrary shell commands, code, and unrelated requests are unsupported with molecule null and samples null. Do not provide scientific prose, code, explanations, or extra JSON keys.
Examples:
User: Teach the shapes of butane.
Assistant: {"task":"shapes","molecule":"butane","samples":5}
User: Show four ethanol shapes.
Assistant: {"task":"shapes","molecule":"ethanol","samples":4}
User: Show me how ethanol reacts with water.
Assistant: {"task":"mixture","molecule":null,"samples":null}
User: What happens when I mix water with ethanol?
Assistant: {"task":"mixture","molecule":null,"samples":null}
User: Show aspirin shapes.
Assistant: {"task":"shapes","molecule":"aspirin","samples":5}
User: Explain drug breakdown.
Assistant: {"task":"unsupported","molecule":null,"samples":null}
User: Show me molecular shapes.
Assistant: {"task":"clarify","molecule":null,"samples":null}'''
QCHEM_SYSTEM = 'Classify a beginner\'s question about preparing a Q-Chem single-point input. Return ONLY one JSON object with exactly this key: topic. topic is one of molecule, atoms, coordinates, charge, multiplicity, method, basis, single_point, export, limitations, unsupported. The server supplies the selected molecule, atom count, charge, multiplicity, and current step; classify the question, never alter those values. Questions about saving, downloading, sharing or using the prepared input file are export. Questions asking whether Q-Chem has run, what the lesson can do, or whether an engine is needed are limitations. Explaining a calculation is single_point; predicting a numerical energy is unsupported. Medication, biological effects, predicted reaction products, arbitrary code execution, shell commands, and unrelated requests are unsupported. Do not provide prose, code, numbers or extra keys.\nExamples:\nQuestion: Which molecule should I start with?\nAnswer: {"topic": "molecule"}\nQuestion: How do I count the hydrogens?\nAnswer: {"topic": "atoms"}\nQuestion: What do these coordinates mean?\nAnswer: {"topic": "coordinates"}\nQuestion: Why is the charge zero?\nAnswer: {"topic": "charge"}\nQuestion: What is multiplicity?\nAnswer: {"topic": "multiplicity"}\nQuestion: What does HF mean?\nAnswer: {"topic": "method"}\nQuestion: What does the basis mean?\nAnswer: {"topic": "basis"}\nQuestion: What is a single-point energy?\nAnswer: {"topic": "single_point"}\nQuestion: What do I do with this file?\nAnswer: {"topic": "export"}\nQuestion: How do I save and share the input?\nAnswer: {"topic": "export"}\nQuestion: Did Q-Chem run?\nAnswer: {"topic": "limitations"}\nQuestion: Do I need Q-Chem installed?\nAnswer: {"topic": "limitations"}\nQuestion: Can you predict a reaction product?\nAnswer: {"topic": "unsupported"}\n'


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


def deployment(resource_root=None):
    """The public bundle never needs the private training adapter."""
    if resource_root is not None:
        root = Path(resource_root)/'models/qwen'
        public = root/'public-model'
        if public.is_dir():
            return public, None, {'variant':PUBLIC_VARIANT, 'adapter_sha256':None,
                                  'model_sha256':PUBLIC_FILES['model.safetensors']}
        model, adapter = root/'model', root/'adapter'
    else:
        model, adapter = assets()
    return model, adapter, {'variant':'private-lora-pilot', 'adapter_sha256':ADAPTER_SHA,
                            'model_sha256':MODEL_SHA}


def verify_assets(model_path, adapter_path):
    if adapter_path is None:
        for name, expected in PUBLIC_FILES.items():
            if digest(model_path/name) != expected:
                raise ValueError('Bundled Qwen file failed its integrity check: '+name)
    elif digest(model_path/'model.safetensors-00001-of-00001.safetensors') != MODEL_SHA or digest(adapter_path/'adapters.safetensors') != ADAPTER_SHA:
        raise ValueError('Pinned local model or trained adapter failed its integrity check')


def study_deployment(resource_root=None):
    """Resolve only the pinned public model used by bounded study prompts."""
    if resource_root is None:
        configured = os.environ.get('OPENCHEM_QWEN_RESOURCES')
        if not configured:
            raise ValueError('Study mode requires packaged public Qwen resources')
        resource_root = Path(configured)
    model = Path(resource_root)/'models/qwen/public-model'
    if not model.is_dir():
        raise ValueError('Study mode public Qwen resources are unavailable')
    verify_assets(model, None)
    return model, None, {'variant':PUBLIC_VARIANT, 'adapter_sha256':None,
                         'model_sha256':PUBLIC_FILES['model.safetensors']}


def study_prompt(prompt):
    return [{'role':'system','content':STUDY_SYSTEM}, {'role':'user','content':prompt}]


def qchem_prompt(prompt):
    return [{'role':'system','content':QCHEM_SYSTEM}, {'role':'user','content':prompt}]


def main():
    os.environ['HF_HUB_OFFLINE'] = '1'
    os.environ['TRANSFORMERS_OFFLINE'] = '1'
    payload = json.loads(sys.stdin.buffer.read(20_000))
    prompt = payload.get('prompt')
    if not isinstance(prompt, str) or not 1 <= len(prompt.strip()) <= 4000:
        raise ValueError('A prompt of 1..4000 characters is required')
    mode = payload.get('mode')
    study = mode == 'study'
    qchem = mode == 'qchem'
    if mode not in {None, 'study', 'qchem'}:
        raise ValueError('Unsupported worker mode')
    resources = Path(sys.executable).resolve().parents[2] if getattr(sys, 'frozen', False) else None
    if study or qchem:
        model_path, adapter_path, provenance = study_deployment(resources)
    else:
        model_path, adapter_path, provenance = deployment(resources)
        verify_assets(model_path, adapter_path)
    import mlx.core as mx
    from mlx_lm import load, stream_generate
    from mlx_lm.sample_utils import make_sampler
    mx.set_memory_limit(10*1024**3)
    started = time.monotonic()
    model, tokenizer = load(str(model_path), adapter_path=str(adapter_path) if adapter_path else None, trust_remote_code=False)
    tokenizer.add_eos_token('<|im_end|>')
    messages = qchem_prompt(prompt) if qchem else study_prompt(prompt) if study else [{'role':'system','content':SYSTEM},{'role':'user','content':prompt}]
    text = tokenizer.apply_chat_template(messages, add_generation_prompt=True, enable_thinking=False)
    raw = ''
    for result in stream_generate(model, tokenizer, text, max_tokens=80 if qchem else 160 if study else 320, sampler=make_sampler(temp=0)):
        raw += result.text
        # Stop after a complete JSON object; never execute text emitted by the model.
        try:
            value = json.loads(raw)
            if isinstance(value, dict):
                break
        except ValueError:
            pass
    print(json.dumps({'raw':raw,'seconds':round(time.monotonic()-started,3),'model':MODEL_ID,**provenance}), flush=True)


if __name__ == '__main__':
    main()
