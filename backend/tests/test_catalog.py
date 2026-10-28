"""The interface may only offer what /api/catalog lists, and the engine accepts exactly that."""
import os
import pytest
from fastapi.testclient import TestClient
from rdkit import Chem

from hypothesislab.catalog import FORCE_FIELDS, RELAXATION, STARTERS, catalog
from hypothesislab.conformers import FIRST_MOLECULES, relax_geometry, validate_relaxation
from hypothesislab.workbench import WorkbenchEngine


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("HYPOTHESISLAB_DATA", str(tmp_path))
    from hypothesislab import api
    api.engine = WorkbenchEngine(tmp_path)
    with TestClient(api.app) as c:
        token = c.get("/api/session").json()["session_token"]
        c.headers.update({"X-HypothesisLab-Session": token})
        yield c


def test_catalog_route_serves_the_tables(client):
    data = client.get("/api/catalog").json()
    assert data["schema"] == "chem313.catalog.v1"
    assert [m["id"] for m in data["molecules"]] == [m["id"] for m in STARTERS]
    assert {f["id"] for f in data["relaxation"]["force_fields"]} == set(FORCE_FIELDS)
    assert data["relaxation"]["defaults"] == RELAXATION["defaults"]
    assert data["relaxation"]["limits"]["heavy_atoms"]["max"] == RELAXATION["limits"]["heavy_atoms"]["max"]


def test_catalog_route_requires_a_session(client):
    client.headers.pop("X-HypothesisLab-Session")
    assert client.get("/api/catalog").status_code == 403


def test_starters_are_valid_and_match_their_formula():
    for molecule in STARTERS:
        mol = Chem.MolFromSmiles(molecule["smiles"])
        assert mol is not None, molecule["id"]
        assert Chem.MolToSmiles(mol) == molecule["smiles"], "starter SMILES must be canonical so names resolve"
        from rdkit.Chem.rdMolDescriptors import CalcMolFormula
        assert CalcMolFormula(mol) == molecule["formula"], molecule["id"]
    assert FIRST_MOLECULES == {"CCO": "Ethanol", "O": "Water", "C": "Methane"}


@pytest.mark.parametrize("params,message", [
    ({"smiles": "[Fe]"}, "parameters are unavailable"),
    ({"smiles": "CCO.O"}, "One connected molecule"),
    ({"smiles": "not a molecule"}, "could not be read"),
    ({"smiles": "C", "force_field": "AMBER"}, "force_field must be one of"),
    ({"smiles": "C", "seed": -1}, "seed must be"),
    ({"smiles": "C", "max_iterations": 0}, "max_iterations must be"),
    ({"smiles": "C", "molblock": "x"}, "exactly one of"),
    ({"smiles": "C", "extra": 1}, "Unexpected parameter"),
    ({"smiles": "C" * 121}, "heavy atoms"),
    ({}, "exactly one of"),
])
def test_validation_rejects_what_the_catalog_does_not_offer(params, message):
    with pytest.raises(ValueError, match=message):
        validate_relaxation(params)


def test_any_covered_molecule_relaxes_with_either_force_field():
    phenol = relax_geometry({"smiles": "Oc1ccccc1", "seed": 7, "force_field": "UFF", "max_iterations": 300})
    assert phenol["force_field"] == "UFF" and phenol["iterations_limit"] == 300 and phenol["seed"] == 7
    assert phenol["name"] == phenol["formula"] == "C6H6O"  # not a starter, so the formula names it
    assert phenol["identity_status"] == "MATCH"
    named = relax_geometry({"smiles": "CC(=O)O", "name": "my acid"})
    assert named["name"] == "my acid" and named["force_field"] == "MMFF94"


def test_molblock_input_and_starter_naming(tmp_path):
    molblock = Chem.MolToMolBlock(Chem.MolFromSmiles("CCO"))
    engine = WorkbenchEngine(tmp_path)
    params = {"molblock": molblock, "seed": 42}
    ticket = engine.preview("molecule.relax_geometry", params, "draw")["preview_token"]
    reply = engine.execute("molecule.relax_geometry", params, "draw", True, ticket)
    result = reply["result"]
    assert result["name"] == "Ethanol" and result["canonical_smiles"] == "CCO"
    assert result["inchikey"] == "LFQSCWFLJHTTHZ-UHFFFAOYSA-N"
    assert len(reply["artifacts"]) == 3


def test_parameter_coverage_uses_rdkit_atom_types(tmp_path):
    engine = WorkbenchEngine(tmp_path)
    # These are covered despite being omitted from the former element lists.
    engine.preview("molecule.relax_geometry", {"smiles": "C[Hg]C", "force_field": "UFF"}, "draw")
    engine.preview("molecule.relax_geometry", {"smiles": "[Na+]", "force_field": "MMFF94"}, "draw")
    from hypothesislab.validation import InputError
    with pytest.raises(InputError, match="MMFF94 parameters are unavailable"):
        engine.preview("molecule.relax_geometry", {"smiles": "C[Hg]C"}, "draw")


def test_multi_record_sdf_rejected():
    first = Chem.MolToMolBlock(Chem.MolFromSmiles("CCO"))
    second = Chem.MolToMolBlock(Chem.MolFromSmiles("C"))
    with pytest.raises(ValueError, match="exactly one molecule"):
        validate_relaxation({"molblock": first + "$$$$\n" + second + "$$$$\n"})
    validate_relaxation({"molblock": first + "$$$$\n"})


def test_unspecified_stereo_requires_selection_and_specified_stereo_survives():
    for smiles in ("CC(O)F", "CC=CC"):
        with pytest.raises(ValueError, match="Specify stereochemistry"):
            relax_geometry({"smiles": smiles})
    result = relax_geometry({"smiles": "C[C@H](O)F"})
    assert result["identity_status"] == "MATCH"
    assert result["inchikey"] == Chem.MolToInchiKey(Chem.MolFromSmiles("C[C@H](O)F"))
