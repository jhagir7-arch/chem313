"""Verify real saved geometries against a separate force-field reconstruction."""
import json
import pytest
from rdkit import Chem
from rdkit.Chem import AllChem
from hypothesislab.workbench import WorkbenchEngine
from hypothesislab.validation import InputError


@pytest.mark.parametrize('smiles,key', [('CCO','LFQSCWFLJHTTHZ-UHFFFAOYSA-N'), ('O','XLYOFNOQVPJJNP-UHFFFAOYSA-N'), ('C','VNWKTOKETHGBQD-UHFFFAOYSA-N')])
def test_saved_geometry_energy_can_be_independently_recalculated(tmp_path, smiles, key):
    engine = WorkbenchEngine(tmp_path)
    params = {'smiles': smiles, 'seed': 42}
    ticket = engine.preview('molecule.relax_geometry', params, 'lesson')['preview_token']
    assert not (tmp_path/'lesson').exists()
    reply = engine.execute('molecule.relax_geometry', params, 'lesson', True, ticket)
    result = reply['result']
    assert result['engine_provenance'] == 'real' and result['converged']
    assert result['inchikey'] == key
    assert result['final_energy_kcal_mol'] <= result['initial_energy_kcal_mol'] + 1e-5
    assert len(reply['artifacts']) == 3
    for group, field in [('originals','initial_energy_kcal_mol'), ('derived','final_energy_kcal_mol')]:
        artifact = next(a for a in reply['artifacts'] if f'/{group}/' in a['relative_path'])
        sdf = (tmp_path/artifact['relative_path']).read_text()
        mol = Chem.MolFromMolBlock(sdf.split('$$$$')[0], removeHs=False)
        assert Chem.MolToInchiKey(mol) == key
        assert mol.GetConformer().Is3D()
        ff = AllChem.MMFFGetMoleculeForceField(mol, AllChem.MMFFGetMoleculeProperties(mol, mmffVariant='MMFF94'))
        assert ff.CalcEnergy() == pytest.approx(result[field], abs=1e-9)
    report = json.loads((tmp_path/reply['artifacts'][2]['relative_path']).read_text())
    assert report['geometry_artifacts'] == reply['artifacts'][:2]
    assert report['scope'].startswith('Local force-field')
    assert engine.store.verify_artifacts('lesson')['status'] == 'PASS'
    with pytest.raises(InputError):
        engine.execute('molecule.relax_geometry', params, 'lesson', True, ticket)
    assert len(engine.store.events('lesson')) == 1


@pytest.mark.parametrize('params', [{'smiles':'C'*101}, {'smiles':'CCO','seed':True}, {'smiles':'CCO','seed':-1}, {'smiles':'O','unknown':1}, {}])
def test_bad_lesson_input_rejected_before_writing(tmp_path, params):
    engine = WorkbenchEngine(tmp_path)
    with pytest.raises(InputError):
        engine.preview('molecule.relax_geometry', params, 'lesson')
    assert not (tmp_path/'lesson').exists()


def test_review_binds_molecule_project_and_seed(tmp_path):
    engine = WorkbenchEngine(tmp_path)
    params = {'smiles':'CCO','seed':42}
    ticket = engine.preview('molecule.relax_geometry', params, 'lesson')['preview_token']
    with pytest.raises(InputError):
        engine.execute('molecule.relax_geometry', {**params,'smiles':'O'}, 'lesson', True, ticket)
    assert not (tmp_path/'lesson').exists()
