import json

import pytest

from hypothesislab.conformers import molecule_conformer
from hypothesislab.validation import InputError
from hypothesislab.workbench import WorkbenchEngine


def generated_geometry():
    return molecule_conformer({"smiles": "CCO"})["sdf"]


def request(geometry=None, **overrides):
    data = {
        "geometry_sdf": generated_geometry() if geometry is None else geometry,
        "job_type": "optimization_frequency",
        "charge": 0,
        "multiplicity": 1,
        "method": "B3LYP",
        "basis": "def2-SVP",
    }
    data.update(overrides)
    return data


def test_prepared_input_binds_exact_generated_geometry_settings_and_artifacts(tmp_path):
    engine = WorkbenchEngine(tmp_path)
    params = request()
    preview = engine.preview("orca.prepare_input", params, "ethanol")
    assert preview["prepared_input"].startswith("! B3LYP def2-SVP Opt Freq\n\n* xyz 0 1\n")
    assert preview["checks"] == {"has_3d_conformer": True, "all_coordinates_finite": True, "all_hydrogens_explicit": True, "common_main_group_scope": True, "charge_spin_consistent": True, "inchi_round_trip": True}
    assert preview["electron_count"] == 26
    assert not (tmp_path / "ethanol").exists()
    with pytest.raises(InputError):
        engine.execute("orca.prepare_input", request(charge=1, multiplicity=2), "ethanol", True, preview["preview_token"])
    fresh_preview = engine.preview("orca.prepare_input", params, "ethanol")
    reply = engine.execute("orca.prepare_input", params, "ethanol", True, fresh_preview["preview_token"])
    assert [artifact["relative_path"].split(".")[-1] for artifact in reply["artifacts"]] == ["sdf", "inp", "json"]
    assert reply["result"]["atom_count"] == 9
    assert reply["result"]["settings"] == {key: params[key] for key in ("job_type", "charge", "multiplicity", "method", "basis")}
    report = next(artifact for artifact in reply["artifacts"] if artifact["relative_path"].endswith(".json"))
    assert json.loads((tmp_path / report["relative_path"]).read_text())["input_sha256"] == reply["result"]["input_sha256"]
    assert engine.store.verify_artifacts("ethanol")["status"] == "PASS"


@pytest.mark.parametrize("overrides", [
    {"method": "B3LYP; %pal nprocs 999 end"},
    {"basis": "def2-TZVP"},
    {"job_type": "shell.execute"},
    {"charge": 0, "multiplicity": 2},
])
def test_rejects_unapproved_settings_without_creating_project(tmp_path, overrides):
    engine = WorkbenchEngine(tmp_path)
    with pytest.raises(InputError):
        engine.preview("orca.prepare_input", request(**overrides), "ethanol")
    assert not (tmp_path / "ethanol").exists()


def test_rejects_a_2d_mol_record_and_preserves_no_partial_project(tmp_path):
    from rdkit import Chem
    two_d = Chem.MolToMolBlock(Chem.MolFromSmiles("CCO"))
    with pytest.raises(InputError, match="3D"):
        WorkbenchEngine(tmp_path).preview("orca.prepare_input", request(two_d), "ethanol")
    assert not (tmp_path / "ethanol").exists()


def test_rejects_implicit_hydrogens_and_an_impossible_high_spin_state(tmp_path):
    from rdkit import Chem

    carbon = Chem.MolFromSmiles("C")
    carbon_conf = Chem.Conformer(1)
    carbon_conf.Set3D(True)
    carbon_conf.SetAtomPosition(0, (0.0, 0.0, 0.0))
    carbon.AddConformer(carbon_conf)
    with pytest.raises(InputError, match="implicit hydrogens"):
        WorkbenchEngine(tmp_path).preview("orca.prepare_input", request(Chem.MolToMolBlock(carbon)), "methane")

    hydrogen = Chem.RWMol()
    atom = Chem.Atom(1)
    atom.SetNoImplicit(True)
    hydrogen.AddAtom(atom)
    hydrogen = hydrogen.GetMol()
    hydrogen_conf = Chem.Conformer(1)
    hydrogen_conf.Set3D(True)
    hydrogen_conf.SetAtomPosition(0, (0.0, 0.0, 0.0))
    hydrogen.AddConformer(hydrogen_conf)
    with pytest.raises(InputError, match="incompatible"):
        WorkbenchEngine(tmp_path).preview("orca.prepare_input", request(Chem.MolToMolBlock(hydrogen), multiplicity=3), "hydrogen")


def test_rejects_isotopic_source_without_creating_a_partial_project(tmp_path):
    isotopic = molecule_conformer({"smiles": "[13CH3]O"})["sdf"]
    with pytest.raises(InputError, match="Isotope masses"):
        WorkbenchEngine(tmp_path).preview("orca.prepare_input", request(isotopic), "isotopic")
    assert not (tmp_path / "isotopic").exists()
