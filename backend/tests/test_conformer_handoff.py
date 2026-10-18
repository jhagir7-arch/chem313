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
