"""Typed, review-only Qwen drafts with independent molecular validation."""
from __future__ import annotations
import json
import os
import re
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import uuid

from .validation import InputError
from .chemistry import from_smiles, summary
from .qwen_worker import MODEL_ID, MODEL_SHA, ADAPTER_SHA, assets

FIELDS = {'smiles','job_type','charge','multiplicity','method','basis','message'}


def validate_draft(raw: str) -> dict:
    if not isinstance(raw, str) or len(raw.encode()) > 16_000:
        raise InputError('Qwen response exceeds the supported size')
    try:
        draft = json.loads(raw)
    except ValueError as exc:
        raise InputError('Qwen did not return a complete structured draft. Refine the request and try again.') from exc
    if not isinstance(draft, dict) or set(draft) != FIELDS | {'action'}:
        raise InputError('Qwen draft has unexpected or missing fields; nothing was applied')
    if not isinstance(draft['message'], str) or len(draft['message']) > 2000:
        raise InputError('Qwen explanation is malformed')
    decision = draft.pop('action')
    if decision == 'clarify':
        if any(draft[key] is not None for key in FIELDS - {'message'}):
            raise InputError('Qwen clarification contained conflicting calculation fields')
        return {'decision':decision, **draft, 'validation':None}
    if decision != 'proposal':
        raise InputError('Qwen draft must propose settings or ask for clarification')
    if not isinstance(draft['smiles'], str) or not 1 <= len(draft['smiles']) <= 2000:
        raise InputError('Qwen draft has no bounded molecular SMILES')
    if draft['job_type'] not in {'single_point','optimization','optimization_frequency'}:
        raise InputError('Qwen proposed an unsupported calculation')
    if draft['method'] not in {'HF','B3LYP','PBE0','r2SCAN-3c'} or draft['basis'] != ('built-in' if draft['method']=='r2SCAN-3c' else 'def2-SVP'):
        raise InputError('Qwen proposed an unsupported method or basis')
    charge, mult = draft['charge'], draft['multiplicity']
    if type(charge) is not int or not -10 <= charge <= 10 or type(mult) is not int or not 1 <= mult <= 9:
        raise InputError('Qwen proposed an unsupported electronic state')
    mol = from_smiles(draft['smiles'])
    from rdkit import Chem
    if not 1 <= mol.GetNumHeavyAtoms() <= 100 or len(Chem.GetMolFrags(mol)) != 1:
        raise InputError('Drafts support one connected molecule with 1..100 heavy atoms')
    if any(a.GetAtomicNum() not in {1,5,6,7,8,9,14,15,16,17} or a.GetIsotope() for a in mol.GetAtoms()):
        raise InputError('Qwen proposed unsupported elements or isotopes')
    explicit = Chem.AddHs(mol)
    electrons = sum(a.GetAtomicNum() for a in explicit.GetAtoms()) - charge
    if electrons <= 0 or mult > electrons + 1 or (electrons - (mult - 1)) % 2:
        raise InputError('Qwen proposed an inconsistent charge and spin electron count')
    info = summary(mol)
    return {'decision':decision, **draft, 'validation':{
        'formula':info['formula'], 'canonical_smiles':info['isomeric_smiles'], 'electron_count':electrons,
        'formal_charge_matches':info['formal_charge']==charge,
        'scope':'RDKit graph, supported fields and electron parity checked. Molecular identity, stereochemistry and suitability require researcher review.'}}


def enforce_request(prompt: str, draft: dict) -> None:
    """Reject known explicit-choice conflicts; never silently repair model output."""
    if draft['decision'] != 'proposal':
        return
    text = prompt.lower()
    expected = {}
    if re.search(r'\b(frequencies|frequency|freq)\b', text):
        expected['job_type'] = 'optimization_frequency'
    elif re.search(r'\b(optimization|optimise|optimize|optimisation)\b', text):
        expected['job_type'] = 'optimization'
    elif re.search(r'\bsingle[ -]point\b', text):
        expected['job_type'] = 'single_point'
    methods = [method for method in ['HF','B3LYP','PBE0','r2SCAN-3c'] if re.search(r'(?<![a-z0-9])'+re.escape(method.lower())+r'(?![a-z0-9])',text)]
    if len(methods) == 1:
        expected['method'] = methods[0]
    charge = re.search(r'\bcharge\s*(?:=|of|:)?\s*(-?\d+)\b',text)
    multiplicity = re.search(r'\bmultiplicity\s*(?:=|of|:)?\s*(\d+)\b',text)
    if charge:
        expected['charge'] = int(charge[1])
    elif re.search(r'\bneutral\b',text):
        expected['charge'] = 0
    if multiplicity:
        expected['multiplicity'] = int(multiplicity[1])
    else:
        for word, value in [('singlet',1),('doublet',2),('triplet',3)]:
            if re.search(r'\b'+word+r'\b',text):
                expected['multiplicity'] = value
    if 'def2-svp' in text:
        expected['basis'] = 'def2-SVP'
    conflicts = [key for key,value in expected.items() if draft[key] != value]
    if conflicts:
        raise InputError('Qwen changed an explicit requested choice ('+', '.join(conflicts)+'). Nothing was applied. Refine the request or use the calculation controls.')


def worker_command():
    if getattr(sys, 'frozen', False):
        worker = Path(sys.executable).resolve().parent.parent / 'workers/qwen/qwen-worker'
        return [str(worker)], None
    root = Path(__file__).resolve().parents[3]
    env = os.environ.copy()
    env['PYTHONPATH'] = str(root/'backend/src')
    return [str(root/'.venv-training/bin/python'), '-m', 'hypothesislab.qwen_worker'], env


class Assistant:
    def __init__(self, root: Path):
        self.root = root
        self._lock = threading.Lock()

    def status(self):
        model, adapter = assets()
        # Core is frozen under Resources/engine; worker assets use a different depth.
        if getattr(sys, 'frozen', False):
            root = Path(sys.executable).resolve().parent.parent/'models/qwen'
            model, adapter = root/'model', root/'adapter'
        command, _ = worker_command()
        ready = Path(command[0]).is_file() and (model/'config.json').is_file() and (model/'model.safetensors-00001-of-00001.safetensors').is_file() and (adapter/'adapters.safetensors').is_file()
        return {'status':'READY' if ready else 'UNAVAILABLE', 'model':MODEL_ID,
                'detail':'Local experimental LoRA pilot: 25 updates. Drafts require review; no autonomous calculations.',
                'adapter_sha256':ADAPTER_SHA, 'model_sha256':MODEL_SHA}

    def propose(self, prompt):
        if not isinstance(prompt,str) or not 1 <= len(prompt.strip()) <= 4000:
            raise InputError('A prompt of 1..4000 characters is required')
        if self.status()['status'] != 'READY':
            raise InputError('Local Qwen worker, model or trained adapter is unavailable')
        if not self._lock.acquire(blocking=False):
            raise InputError('Qwen is already drafting. Wait for that request to finish.')
        try:
            command, env = worker_command()
            # Temporary regular files bound stdout memory independently of the worker.
            with tempfile.TemporaryFile() as out, tempfile.TemporaryFile() as err:
                try:
                    proc = subprocess.run(command, input=json.dumps({'prompt':prompt}).encode(), stdout=out, stderr=err, env=env, timeout=120, check=False)
                except subprocess.TimeoutExpired as exc:
                    raise InputError('Qwen exceeded its 120-second inference limit; nothing was applied') from exc
                out.seek(0); raw = out.read(20_001)
                if proc.returncode or len(raw)>20_000:
                    raise InputError('Local Qwen inference failed; nothing was applied')
            try:
                result = json.loads(raw)
                if result['model'] != MODEL_ID or result['adapter_sha256'] != ADAPTER_SHA:
                    raise ValueError('Worker provenance mismatch')
                draft = validate_draft(result['raw'])
                enforce_request(prompt,draft)
            except (ValueError,KeyError,TypeError) as exc:
                if isinstance(exc, InputError):
                    raise
                raise InputError('Qwen worker returned an invalid draft or provenance') from exc
            draft.update(id=uuid.uuid4().hex, provenance={'model':MODEL_ID,'model_sha256':MODEL_SHA,'adapter_sha256':ADAPTER_SHA,'seconds':result['seconds'],'scope':'Experimental local draft, not chemical validation or a calculated result.'})
            directory = self.root/'.assistant'
            directory.mkdir(mode=0o700,parents=True,exist_ok=True)
            path = directory/f"{draft['id']}.json"
            with path.open('x',encoding='utf-8') as stream:
                json.dump({'prompt':prompt,'raw':result['raw'],'validated':draft},stream,ensure_ascii=False,indent=2)
            path.chmod(0o600)
            return draft
        finally:
            self._lock.release()
