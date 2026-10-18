from hypothesislab.workflows import plan


def test_literal_conversion_preserves_user_inputs_without_execution():
    result = plan('convert 1000 nm to micrometer')
    assert result['status'] == 'PROPOSED'
    assert result['inputs'] == {'value': 1000.0, 'from_unit': 'nm', 'to_unit': 'micrometer'}
    assert result['executes'] is False and result['requires_explicit_apply'] is True
    assert 'preview_token' not in result and 'result' not in result


def test_missing_quantum_inputs_are_never_invented():
    result = plan('PySCF RHF energy')
    assert result['status'] == 'NEEDS_INPUT'
    assert result['operation'] == 'pyscf.rhf_singlepoint'
    assert 'inputs' not in result and result['executes'] is False


def test_ambiguous_goals_require_selection():
    result = plan('Find mean and linear regression')
    assert result['status'] == 'NEEDS_INPUT'
    assert set(result['candidates']) == {'numpy.summary', 'scipy.line'}
    assert 'inputs' not in result


def test_unknown_or_nonfinite_goal_cannot_become_an_approved_plan():
    assert plan('invent a new drug')['status'] == 'UNSUPPORTED'
    assert plan('convert 1e999 nm to micrometer')['status'] == 'NEEDS_INPUT'
