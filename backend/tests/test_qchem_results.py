import json
import pytest
from hypothesislab.qchem_coach import QchemCoach
from hypothesislab.qchem_results import QchemResultCoach
from hypothesislab.validation import InputError


def job(**updates):
    return {'id':'a'*32,'project':'lesson','molecule':'water','state':'SUCCEEDED','input_sha256':'b'*64,'output_sha256':'c'*64,
            'result':{'energy_hartree':-75.9,'converged':True,'normal_termination':True},**updates}


def helper(topic='single_point'):
    seen=[]
    def infer(prompt):
        seen.append(prompt)
        return json.dumps({'topic':topic}), {'model':'test classifier'}
    return QchemResultCoach(QchemCoach(infer)),seen


def test_result_is_server_job_energy_and_model_only_classifies():
    coach,seen=helper()
    result=coach.explain(project='lesson',prompt='What does this energy mean?',job=job())
    assert '-75.9 hartree' in result['message']
    assert 'fixed atomic positions' in result['message']
    assert '-75.9' not in seen[0]
    assert result['input_sha256']=='b'*64


@pytest.mark.parametrize('record',[job(state='FAILED'),job(result={'energy_hartree':-9999,'converged':False,'normal_termination':True}),job(result={'energy_hartree':float('nan'),'converged':True,'normal_termination':True})])
def test_unusable_jobs_never_disclose_an_energy(record):
    coach,_=helper()
    result=coach.explain(project='lesson',prompt='What happened?',job=record)
    assert 'No usable converged energy' in result['message']
    assert '-9999' not in result['message']


def test_foreign_project_running_job_and_injected_model_output_rejected():
    coach,_=helper()
    with pytest.raises(InputError,match='project'):
        coach.explain(project='other',prompt='Help',job=job())
    with pytest.raises(InputError,match='Wait'):
        coach.explain(project='lesson',prompt='Help',job=job(state='RUNNING'))
    coach=QchemResultCoach(QchemCoach(lambda _:('{"topic":"single_point","energy":123}',{})))
    with pytest.raises(InputError):
        coach.explain(project='lesson',prompt='Help',job=job())


def test_outside_scope_does_not_run_model_or_invent_a_prediction():
    coach=QchemResultCoach(QchemCoach(lambda _:pytest.fail('must not infer')))
    result=coach.explain(project='lesson',prompt='Predict the medication reaction outcome',job=job())
    assert result['provenance']['guard']
    assert 'cannot infer reaction outcomes' in result['message']
