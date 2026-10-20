"""Explain persisted Q-Chem jobs; model output never supplies numerical facts."""
from __future__ import annotations
import json
import math
import re
from .qchem_coach import QchemCoach, validate_topic, _UNSAFE
from .validation import InputError, PROJECT_RE


class QchemResultCoach:
    def __init__(self, coach: QchemCoach):
        self.coach = coach

    def explain(self, *, project: str, prompt: str, job: dict) -> dict:
        if not isinstance(project, str) or not PROJECT_RE.fullmatch(project) or job.get('project') != project:
            raise InputError('This job does not belong to the selected project')
        if not isinstance(prompt, str) or not 1 <= len(prompt.strip()) <= 1000:
            raise InputError('Enter a question of 1..1000 characters')
        if job.get('state') in {'QUEUED', 'RUNNING'}:
            raise InputError('Wait for this job to finish before asking about its result')
        if not re.fullmatch(r'[a-f0-9]{32}', job.get('id', '')) or job.get('molecule') not in {'water','methane','ethanol'}:
            raise InputError('The recorded Q-Chem job is invalid')
        if not self.coach.lock.acquire(blocking=False):
            raise InputError('Qwen is already coaching. Wait for that request to finish.')
        try:
            if _UNSAFE.search(prompt):
                topic, raw, provenance = 'unsupported', '{"topic":"unsupported"}', {'guard':'Requests outside recorded result explanation are not executed'}
            else:
                # No engine-output text or client-supplied result goes into the model prompt.
                raw, provenance = self.coach.infer(
                    f'Current Q-Chem preparation context: molecule={job["molecule"]}; step=export. '
                    f'User question: {prompt.strip()}')
                topic = validate_topic(raw)
            result = job.get('result') or {}
            energy = result.get('energy_hartree')
            usable = (job.get('state') == 'SUCCEEDED' and result.get('converged') is True
                      and result.get('normal_termination') is True and type(energy) in {int,float} and math.isfinite(energy))
            if usable:
                facts = (f'The recorded {job["molecule"]} job finished with SCF convergence and normal termination. '
                         f'Its parsed HF/def2-SVP single-point electronic energy is {energy} hartree (Eh). ')
                next_action = 'Inspect the exact output and confirm what a single-point calculation establishes in the result check.'
            else:
                facts = f'This recorded {job["molecule"]} job is {job.get("state", "unknown")}. No usable converged energy is reported. '
                next_action = 'Read the job detail and engine output. Check your licensed installation before running a new job.'
            explanations = {
                'single_point': 'This energy evaluates the supplied fixed atomic positions; it does not optimize their geometry. A negative absolute energy is not a reaction energy or evidence of safety.',
                'method': 'HF is the approximate electronic-structure method used here. Numerical convergence does not establish scientific accuracy.',
                'basis': 'def2-SVP is the orbital basis used here. Changing the basis changes the model; this calculation provides no accuracy guarantee.',
                'coordinates': 'The input coordinates are the generated starting positions in angstroms. A single-point calculation holds them fixed.',
                'atoms': 'The executed input contains every atom, including hydrogens. Inspect the saved input to check the molecular representation.',
                'charge': 'This teaching job uses charge zero: a neutral molecular input.',
                'multiplicity': 'This teaching job uses multiplicity one, a singlet electronic state.',
                'export': 'The input, engine output, and result record can be downloaded together for an instructor or researcher to review.',
                'molecule': 'This result belongs only to the molecule, electronic state, coordinates, and method recorded for this job.',
                'limitations': 'A single-point energy alone does not predict reactions, reaction rates, medication effects, or experimentally correct geometry.',
                'unsupported': 'This helper explains recorded calculation facts. It cannot infer reaction outcomes, biological effects, or execute scripts from a question.',
            }
            return {'title':'Understanding your recorded calculation','topic':topic,'job_id':job['id'], 'state':job['state'],
                    'message':facts+explanations[topic], 'next_action':next_action, 'model_output':raw,
                    'input_sha256':job.get('input_sha256'), 'output_sha256':job.get('output_sha256'),
                    'provenance':{**provenance,'scope':'Qwen topic classification plus server-fetched job facts; no generated numerical results.'}}
        finally:
            self.coach.lock.release()
