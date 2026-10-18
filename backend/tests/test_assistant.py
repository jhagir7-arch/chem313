import json
import pytest
from hypothesislab.assistant import validate_draft, Assistant
from hypothesislab.validation import InputError


def raw(**overrides):
    value=dict(action='proposal',smiles='O',job_type='single_point',charge=0,multiplicity=1,method='HF',basis='def2-SVP',message='Review water')
    value.update(overrides)
    return json.dumps(value)


def test_validated_draft_has_graph_and_electron_checks():
    result=validate_draft(raw())
    assert result['decision']=='proposal'
    assert result['validation']['formula']=='H2O'
    assert result['validation']['electron_count']==10
    assert result['validation']['formal_charge_matches'] is True


@pytest.mark.parametrize('changes',[
    dict(action='shell.execute'),dict(smiles='not a molecule'),dict(smiles='[Fe]'),
    dict(smiles='[13CH4]'),dict(smiles='C.O'),dict(charge=True),dict(multiplicity=2),
    dict(method='HF; rm -rf /'),dict(basis='def2-TZVP'),dict(job_type='execute'),dict(extra='tool'),
])
def test_invalid_model_output_never_reaches_editor(changes):
    with pytest.raises(InputError):
        validate_draft(raw(**changes))


def test_clarification_never_carries_applyable_fields():
    result=validate_draft(raw(action='clarify',smiles=None,job_type=None,charge=None,multiplicity=None,method=None,basis=None))
    assert result['decision']=='clarify' and result['validation'] is None
    with pytest.raises(InputError):
        validate_draft(raw(action='clarify'))


def test_trailing_code_and_incomplete_response_are_rejected():
    for text in [raw()+'; shell()',raw()[:-1],'```json\n'+raw()+'\n```']:
        with pytest.raises(InputError):
            validate_draft(text)


def test_inference_cannot_overlap(tmp_path,monkeypatch):
    assistant=Assistant(tmp_path)
    monkeypatch.setattr(assistant,'status',lambda:{'status':'READY'})
    assistant._lock.acquire()
    try:
        with pytest.raises(InputError,match='already drafting'):
            assistant.propose('water')
    finally:
        assistant._lock.release()


def test_prompt_bound_applies_before_inference(tmp_path):
    with pytest.raises(InputError):
        Assistant(tmp_path).propose('x'*4001)


def test_explicit_choices_cannot_be_changed_by_qwen():
    from hypothesislab.assistant import enforce_request
    draft=validate_draft(raw())
    enforce_request('Water O neutral singlet HF def2-SVP single point',draft)
    for prompt in ['Water optimization and frequencies','Water charge 1','Water triplet','Water PBE0 optimization']:
        with pytest.raises(InputError,match='changed an explicit'):
            enforce_request(prompt,draft)
