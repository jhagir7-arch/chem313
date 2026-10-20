"""InChI round-trip checks between source structures and exported coordinates."""
import pytest
from rdkit import Chem
from rdkit.Chem import AllChem

from hypothesislab.conformers import molecule_conformer
from hypothesislab.identity import identity_check, mol_inchi
from hypothesislab.orca_input import prepare_orca_input
from hypothesislab.qchem_runtime import render_input
from hypothesislab.validation import InputError

ETHANOL_INCHI = "InChI=1S/C2H6O/c1-2-3/h3H,2H2,1H3"


def embedded(smiles):
    mol = Chem.AddHs(Chem.MolFromSmiles(smiles))
    AllChem.EmbedMolecule(mol, randomSeed=7)
    AllChem.MMFFOptimizeMolecule(mol)
    return mol


def coordinates(mol, mirror=False):
    conf = mol.GetConformer()
    return [(a.GetSymbol(), -p.x if mirror else p.x, p.y, p.z)
            for a, p in ((a, conf.GetAtomPosition(a.GetIdx())) for a in mol.GetAtoms())]


def orca_params(sdf):
    return {"geometry_sdf": sdf, "job_type": "single_point", "charge": 0, "multiplicity": 1,
            "method": "HF", "basis": "def2-SVP"}


def test_prepared_orca_input_reports_inchi_match():
    result = prepare_orca_input(orca_params(molecule_conformer({"smiles": "CCO"})["sdf"]))
    assert result["identity_check"]["status"] == "match"
    assert result["identity_check"]["observed_inchi"] == ETHANOL_INCHI
    assert result["coordinate_checks"]["inchi_round_trip"] is True


def test_orca_export_blocks_detached_hydrogen():
    mol = Chem.MolFromMolBlock(molecule_conformer({"smiles": "CCO"})["sdf"], removeHs=False)
    conf = mol.GetConformer()
    hydrogen = next(a.GetIdx() for a in mol.GetAtoms() if a.GetSymbol() == "H")
    point = conf.GetAtomPosition(hydrogen)
    conf.SetAtomPosition(hydrogen, (point.x + 4.0, point.y, point.z))
    with pytest.raises(InputError, match="different molecule"):
        prepare_orca_input(orca_params(Chem.MolToMolBlock(mol)))


def test_same_formula_isomer_is_a_connectivity_mismatch():
    ether = embedded("COC")
    result = identity_check(coordinates(ether), expected_inchi=ETHANOL_INCHI, charge=0)
    assert result["status"] == "mismatch" and "different molecule" in result["detail"]
    atoms = [{"element": s, "x": x, "y": y, "z": z} for s, x, y, z in coordinates(ether)]
    with pytest.raises(InputError, match="different molecule"):
        render_input("ethanol", atoms)


def test_mirrored_stereocentre_is_a_stereo_mismatch():
    mol = embedded("C[C@H](O)F")
    result = identity_check(coordinates(mol, mirror=True), expected_inchi=mol_inchi(mol), charge=0)
    assert result["status"] == "mismatch" and "stereochemistry" in result["detail"]
    assert identity_check(coordinates(mol), expected_inchi=mol_inchi(mol), charge=0)["status"] == "match"


def test_qchem_starter_molecules_round_trip():
    for name, smiles in (("water", "O"), ("methane", "C"), ("ethanol", "CCO")):
        atoms = [{"element": s, "x": x, "y": y, "z": z} for s, x, y, z in coordinates(embedded(smiles))]
        assert "$molecule" in render_input(name, atoms)


def test_oversized_structure_is_inconclusive_not_blocked():
    result = identity_check([("H", float(i) * 5, 0.0, 0.0) for i in range(201)], expected_inchi="InChI=1S/H", charge=0)
    assert result["status"] == "inconclusive"
