"""Coordinate/atom identity at the structure-to-energy-adapter boundary."""
import pytest
from rdkit import Chem
from hypothesislab.conformers import molecule_conformer
from hypothesislab.extended_contracts import validate_operation

@pytest.mark.parametrize('smiles', ['O', 'CCO', '[NH4+]'])
def test_conformer_handoff_matches_explicit_sdf(smiles):
    result = molecule_conformer({'smiles': smiles})
    mol = Chem.MolFromMolBlock(result['sdf'].split('$$$$')[0], removeHs=False)
    assert result['atomic_numbers'] == [atom.GetAtomicNum() for atom in mol.GetAtoms()]
    assert result['formal_charge'] == Chem.GetFormalCharge(mol)
    assert len(result['coordinates']) == len(result['atomic_numbers']) == result['atom_count']
    for source, encoded in zip(result['coordinates'], mol.GetConformer().GetPositions()):
        assert source == pytest.approx(encoded, abs=0.000051)
    params = {'atomic_numbers': result['atomic_numbers'], 'coordinates_angstrom': result['coordinates'], 'charge': result['formal_charge'], 'basis': 'sto-3g'}
    assert validate_operation('pyscf.rhf_singlepoint', params) == params


def test_workbench_sampling_seeds_are_reproducible_and_keep_geometry_identity(tmp_path):
    from hypothesislab.workbench import WorkbenchEngine
    engine = WorkbenchEngine(tmp_path)
    def generate(seed):
        return engine.execute('molecule.generate_conformer', {'smiles':'CCCC','seed':seed}, 'sampling', True)['result']
    first, repeated, other = generate(42), generate(42), generate(137)
    assert first['seed'] == 42 and other['seed'] == 137
    assert first['coordinates'] == repeated['coordinates']
    assert first['energy'] == repeated['energy']
    assert first['atomic_numbers'] == other['atomic_numbers']
    assert first['force_field'] == other['force_field']
    assert not (tmp_path/'sampling').exists()

@pytest.mark.parametrize('seed', [True, -1, 2147483648, 3.2, '42', None])
def test_sampling_seed_rejected_before_execution(tmp_path, seed):
    from hypothesislab.workbench import WorkbenchEngine
    from hypothesislab.validation import InputError
    with pytest.raises(InputError, match='seed must be an integer'):
        WorkbenchEngine(tmp_path).preview('molecule.generate_conformer', {'smiles':'CCCC','seed':seed}, 'sampling')

def test_sampling_rejects_unrecognized_extra_parameters(tmp_path):
    from hypothesislab.workbench import WorkbenchEngine
    from hypothesislab.validation import InputError
    with pytest.raises(InputError):
        WorkbenchEngine(tmp_path).preview('molecule.generate_conformer', {'smiles':'CCCC','seed':42,'extra':True}, 'sampling')
