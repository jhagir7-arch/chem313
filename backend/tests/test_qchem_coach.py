import json
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from hypothesislab import qchem_coach
from hypothesislab.qchem_coach import QchemCoach, qchem_context, validate_topic
from hypothesislab.qwen_worker import MODEL_ID, PUBLIC_FILES, PUBLIC_VARIANT
from hypothesislab.study_api import QchemCoachRequest
from hypothesislab.validation import InputError


def _reply(topic='coordinates'):
    return json.dumps({'topic': topic}), {'model': MODEL_ID, 'variant': PUBLIC_VARIANT,
                                          'model_sha256': PUBLIC_FILES['model.safetensors'], 'adapter_sha256': None, 'seconds': .1}


def _coach(topic='coordinates'):
    seen = []
    def infer(prompt):
        seen.append(prompt)
        return _reply(topic)
    return QchemCoach(infer=infer), seen


def test_qchem_context_is_server_authored_and_return_is_reviewed_prose():
    coach, seen = _coach('coordinates')
    result = coach.coach(project='alpha', prompt='What do these coordinates represent?', step='inspect', molecule='water', charge=0, multiplicity=1, atom_count=3)
    assert 'molecule=water' in seen[0] and 'atom_count=3' in seen[0] and 'step=inspect' in seen[0]
    assert result['topic'] == 'coordinates'
    assert 'starting geometry' in result['message']
    assert 'quantum-optimized' in result['message']
    assert result['model_output'] == json.dumps({'topic': 'coordinates'})
    assert result['provenance']['model'] == MODEL_ID
    assert result['provenance']['adapter_sha256'] is None


@pytest.mark.parametrize(('molecule','atoms','electrons'), [('water',3,10),('methane',5,10),('ethanol',9,26)])
def test_reviewed_charge_guidance_uses_selected_representation(molecule, atoms, electrons):
    coach, _ = _coach('charge')
    result = coach.coach(project='alpha', prompt='What does charge mean?', step='settings', molecule=molecule, charge=0, multiplicity=1, atom_count=atoms)
    assert f'{atoms} atoms' in result['message']
    assert f'{electrons} electrons' in result['message']


def test_dangerous_requests_are_server_guarded_regardless_of_model():
    coach = QchemCoach(infer=lambda _: pytest.fail('unsafe prompt must not call Qwen'))
    result = coach.coach(project='alpha', prompt='Predict a medication reaction', step='settings', molecule='methane', charge=0, multiplicity=1, atom_count=5)
    assert result['topic'] == 'unsupported'
    assert result['provenance']['guard'] == 'server-side unsafe-request classification'
    assert 'cannot predict reactions' in result['message']


def test_energy_and_code_explanations_are_classified_but_predictions_and_execution_are_guarded():
    coach, seen = _coach('single_point')
    energy = coach.coach(project='alpha', prompt='What is a single-point energy?', step='settings', molecule='water', charge=0, multiplicity=1, atom_count=3)
    code = coach.coach(project='alpha', prompt='Do I need to write code?', step='settings', molecule='water', charge=0, multiplicity=1, atom_count=3)
    assert energy['topic'] == code['topic'] == 'single_point'
    assert len(seen) == 2
    guarded = QchemCoach(infer=lambda _: pytest.fail('guarded prompt must not call Qwen'))
    result = guarded.coach(project='alpha', prompt='Predict the numeric energy for water', step='settings', molecule='water', charge=0, multiplicity=1, atom_count=3)
    assert result['topic'] == 'unsupported'


@pytest.mark.parametrize('raw', [
    '{"topic":"atoms","extra":true}', '{"topic":"unknown"}', '```json\n{"topic":"atoms"}\n```', '[]'
])
def test_model_topic_schema_rejects_extra_or_malformed_output(raw):
    with pytest.raises(InputError, match='coaching'):
        validate_topic(raw)


def test_invalid_context_and_model_errors_fail_without_guidance():
    coach, _ = _coach()
    with pytest.raises(InputError, match='inconsistent'):
        coach.coach(project='alpha', prompt='Help', step='inspect', molecule='water', charge=0, multiplicity=1, atom_count=5)
    unavailable = QchemCoach(infer=lambda _: (_ for _ in ()).throw(InputError('Local Qwen is unavailable for coaching.')))
    with pytest.raises(InputError, match='unavailable'):
        unavailable.coach(project='alpha', prompt='Help with atoms', step='inspect', molecule='water', charge=0, multiplicity=1, atom_count=3)


def test_mock_worker_provenance_is_pinned_before_its_classification_is_used(monkeypatch):
    good = {'raw': json.dumps({'topic': 'atoms'}), 'model': MODEL_ID, 'variant': PUBLIC_VARIANT,
            'model_sha256': PUBLIC_FILES['model.safetensors'], 'adapter_sha256': None, 'seconds': .1}
    monkeypatch.setattr(qchem_coach, 'worker_command', lambda: (['fixture-worker'], None))
    monkeypatch.setattr(qchem_coach.subprocess, 'run', lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout=json.dumps(good).encode()))
    raw, provenance = qchem_coach.infer_qchem('server supplied context')
    assert validate_topic(raw) == 'atoms'
    assert provenance['model'] == MODEL_ID
    good['model_sha256'] = 'untrusted'
    with pytest.raises(InputError, match='provenance'):
        qchem_coach.infer_qchem('server supplied context')


def test_http_payload_schema_is_strict_and_closed():
    payload = QchemCoachRequest(project='alpha', prompt='Explain atoms', step='inspect', molecule='water', charge=0, multiplicity=1, atom_count=3)
    assert payload.atom_count == 3
    with pytest.raises(ValidationError):
        QchemCoachRequest(project='alpha', prompt='Explain atoms', step='inspect', molecule='water', charge='0', multiplicity=1, atom_count=3)
    with pytest.raises(ValidationError):
        QchemCoachRequest(project='alpha', prompt='Explain atoms', step='inspect', molecule='water', charge=0, multiplicity=1, atom_count=3, extra=True)
