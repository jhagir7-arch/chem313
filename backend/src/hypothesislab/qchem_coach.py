"""Bounded, review-only coaching for Q-Chem input preparation."""
from __future__ import annotations

import json
import re
import subprocess
import threading

from .assistant import worker_command
from .qwen_worker import MODEL_ID, PUBLIC_FILES, PUBLIC_VARIANT
from .validation import InputError, PROJECT_RE

TOPICS = frozenset({'molecule','atoms','coordinates','charge','multiplicity','method','basis','single_point','export','limitations','unsupported'})
MOLECULES = {'water': (3, 10), 'methane': (5, 10), 'ethanol': (9, 26)}
STEPS = frozenset({'choose','inspect','settings','export'})
_UNSAFE = re.compile(
    r'\b(?:predict|forecast|estimate|calculate|compute)\b.{0,80}\b(?:reaction|react\w*|product\w*|medication|drug|biological|energy|barrier|outcome)\b'
    r'|\b(?:reaction|react\w*|product\w*|medication|drug|biological|energy|barrier|outcome)\b.{0,80}\b(?:predict|forecast|estimate|calculate|compute)\b'
    r'|\b(?:execute|launch|run)\b.{0,80}\b(?:shell|terminal|python|code|command)\b', re.I)


def qchem_context(*, prompt: str, step: str, molecule: str, charge: int, multiplicity: int, atom_count: int) -> str:
    """Keep UI state server-authored: the model only receives a classification task."""
    return (f'Current Q-Chem preparation context: molecule={molecule}; atom_count={atom_count}; '
            f'charge={charge}; multiplicity={multiplicity}; step={step}. User question: {prompt}')


def validate_topic(raw: str) -> str:
    try:
        reply = json.loads(raw)
    except (TypeError, ValueError) as exc:
        raise InputError('Qwen returned an incomplete coaching classification. Try a shorter question.') from exc
    if not isinstance(reply, dict) or set(reply) != {'topic'} or not isinstance(reply['topic'], str) or reply['topic'] not in TOPICS:
        raise InputError('Qwen returned unsupported coaching fields. No input was changed.')
    return reply['topic']


def _spin_name(multiplicity: int) -> str:
    return {1: 'singlet', 2: 'doublet', 3: 'triplet'}.get(multiplicity, f'multiplicity {multiplicity}')


def reviewed_help(topic: str, *, step: str, molecule: str, charge: int, multiplicity: int, atom_count: int) -> tuple[str, str, str]:
    electrons = MOLECULES[molecule][1] - charge
    state = f'The current {molecule} input has {atom_count} atoms, charge {charge}, multiplicity {multiplicity} ({_spin_name(multiplicity)}), and {electrons} electrons by this input count.'
    charge_meaning = 'Charge 0 means this input is neutral.' if charge == 0 else f'Charge {charge} means this input is not neutral.'
    texts = {
        'molecule': ('Selected molecule', f'{molecule.capitalize()} is the selected starting structure. It is the representation being prepared, not proof of an experimental or optimized structure.', 'Inspect the displayed atoms before preparing the input.'),
        'atoms': ('Atoms in the structure', f'The selected {molecule} structure has {atom_count} atoms in the exported coordinate list. Atom count describes this representation, so compare it with the list before export.', 'Compare the atom count with the coordinate list.'),
        'coordinates': ('Starting coordinates', f'The {atom_count} coordinates are a starting geometry in angstroms. They describe where the displayed atoms begin; they are not a quantum-optimized or measured structure.', 'Inspect the coordinate list before export.'),
        'charge': ('Charge', f'Charge is the whole-molecule charge entered in the Q-Chem molecule section. {charge_meaning} Charge {charge} gives {electrons} electrons by this input count. '+state, 'Review charge and multiplicity together.'),
        'multiplicity': ('Multiplicity', f'Multiplicity {multiplicity} labels the electronic spin state as a {_spin_name(multiplicity)}. Multiplicity 1 means a singlet with paired electrons in this beginner input; it is an input choice, not a result. '+state, 'Confirm the intended spin state before export.'),
        'method': ('Method', 'This beginner preparation fixes the method to HF, Hartree–Fock: an approximate electronic-structure method. It prepares settings only and does not calculate an energy.', 'Review the method line in the input preview.'),
        'basis': ('Basis', 'This beginner preparation fixes the basis to def2-SVP. A basis is the set of mathematical functions used to represent electrons in the method; this setting alone does not establish calculation quality.', 'Review the basis line in the input preview.'),
        'single_point': ('Single-point preparation', 'A single-point calculation evaluates the supplied geometry with atoms fixed at those coordinates; it does not optimize their positions. This preparation step does not run Q-Chem or report an energy. The final Run & read results step can launch a separately licensed local Q-Chem installation.', 'Review the job type and starting coordinates.'),
        'export': ('Export for review', 'Export downloads a Q-Chem input text for your review. It does not submit a job, run Q-Chem, or change the selected molecular structure.', 'Read the molecule and rem sections, then use the Run & read results step if you have a licensed installation.'),
        'limitations': ('What this preparation can explain', 'This coach explains the selected representation and fixed input fields. It cannot validate a scientific model, predict reactions or medication effects, calculate energies, or run external software.', 'Use the input as a reviewed starting point.'),
        'unsupported': ('Outside this preparation coach', 'This coach only explains the selected Q-Chem input representation. It cannot predict reactions, medication effects, energies, or outcomes, and it does not execute code or calculations.', 'Ask about the molecule, atoms, coordinates, charge, multiplicity, method, basis, single-point setup, or export.'),
    }
    title, message, action = texts[topic]
    return title, message, action


def infer_qchem(prompt: str) -> tuple[str, dict]:
    command, env = worker_command()
    try:
        result = subprocess.run(command, input=json.dumps({'prompt': prompt, 'mode': 'qchem'}, separators=(',', ':')).encode(), capture_output=True, env=env, timeout=90)
    except subprocess.TimeoutExpired as exc:
        raise InputError('Local Qwen took too long. Try a shorter question; no input was changed.') from exc
    except OSError as exc:
        raise InputError('Local Qwen is unavailable for coaching. Check the packaged public model; no input was changed.') from exc
    if result.returncode or len(result.stdout) > 20_000:
        raise InputError('Local Qwen is unavailable for coaching. Check the packaged public model; no input was changed.')
    try:
        reply = json.loads(result.stdout)
        if reply['model'] != MODEL_ID or reply['variant'] != PUBLIC_VARIANT or reply['model_sha256'] != PUBLIC_FILES['model.safetensors'] or reply['adapter_sha256'] is not None:
            raise ValueError('unrecognized model')
        raw = reply.pop('raw')
        if not isinstance(raw, str) or len(raw.encode()) > 16_000:
            raise ValueError('invalid model output')
        return raw, reply
    except (ValueError, KeyError, TypeError) as exc:
        raise InputError('Qwen returned unrecognized coaching provenance; no input was changed.') from exc


class QchemCoach:
    def __init__(self, infer=infer_qchem):
        self.infer = infer
        self.lock = threading.Lock()

    def coach(self, *, project: str, prompt: str, step: str, molecule: str, charge: int, multiplicity: int, atom_count: int) -> dict:
        if not isinstance(project, str) or not PROJECT_RE.fullmatch(project):
            raise InputError('Invalid project identifier')
        if not isinstance(prompt, str) or not 1 <= len(prompt.strip()) <= 1000:
            raise InputError('Enter a coaching question of 1..1000 characters')
        if step not in STEPS or molecule not in MOLECULES or type(charge) is not int or type(multiplicity) is not int or type(atom_count) is not int:
            raise InputError('Invalid Q-Chem coaching context')
        expected_atoms, neutral_electrons = MOLECULES[molecule]
        if atom_count != expected_atoms or not -10 <= charge <= 10 or not 1 <= multiplicity <= 9:
            raise InputError('Q-Chem coaching context is inconsistent or out of range')
        electrons = neutral_electrons - charge
        if electrons <= 0 or multiplicity > electrons + 1 or (electrons - (multiplicity - 1)) % 2:
            raise InputError('Charge and multiplicity are not a consistent electronic state')
        if not self.lock.acquire(blocking=False):
            raise InputError('Qwen is already coaching. Wait for that request to finish.')
        try:
            context = qchem_context(prompt=prompt, step=step, molecule=molecule, charge=charge, multiplicity=multiplicity, atom_count=atom_count)
            if _UNSAFE.search(prompt):
                topic, raw, provenance = 'unsupported', json.dumps({'topic': 'unsupported'}), {'model': MODEL_ID, 'variant': PUBLIC_VARIANT, 'model_sha256': PUBLIC_FILES['model.safetensors'], 'adapter_sha256': None, 'guard': 'server-side unsafe-request classification'}
            else:
                raw, provenance = self.infer(context)
                topic = validate_topic(raw)
            title, message, next_action = reviewed_help(topic, step=step, molecule=molecule, charge=charge, multiplicity=multiplicity, atom_count=atom_count)
            return {'topic': topic, 'title': title, 'message': message, 'next_action': next_action,
                    'provenance': {**provenance, 'scope': 'Offline Qwen classification plus reviewed beginner guidance; no calculation, submission, or automatic change.'},
                    'model_output': raw}
        finally:
            self.lock.release()
