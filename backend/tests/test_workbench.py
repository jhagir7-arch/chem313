"""Desktop workflows: source preservation and physically bounded generated geometry."""
import math
from pathlib import Path

import pytest
from rdkit import Chem

from hypothesislab.workbench import WorkbenchEngine
from hypothesislab.validation import InputError


def test_note_preserves_utf8_crlf_and_requires_bound_single_use_receipt(tmp_path):
    engine = WorkbenchEngine(tmp_path)
    text = "Observation: ΔG is unknown.\r\nمشاہدہ\r\n"
    params = {"text": text}
    ticket = engine.preview("project.save_note", params, "experiment")["preview_token"]
    with pytest.raises(InputError):
        engine.execute("project.save_note", {"text": text + "changed"}, "experiment", True, ticket)
    with pytest.raises(InputError):
        engine.execute("project.save_note", params, "experiment", True, ticket)
    assert not (tmp_path / "experiment").exists()
    ticket = engine.preview("project.save_note", params, "experiment")["preview_token"]
    reply = engine.execute("project.save_note", params, "experiment", True, ticket)
    artifact = reply["artifacts"][0]
    assert (tmp_path / artifact["relative_path"]).read_bytes() == text.encode("utf-8")
    with pytest.raises(InputError):
        engine.execute("project.save_note", params, "experiment", True, ticket)
    assert len(engine.store.events("experiment")) == 1
    assert engine.store.verify_artifacts("experiment")["status"] == "PASS"


@pytest.mark.parametrize("text", ["", "  ", "x" * 250001, None])
def test_invalid_note_does_not_create_project(tmp_path, text):
    engine = WorkbenchEngine(tmp_path)
    with pytest.raises(InputError):
        engine.preview("project.save_note", {"text": text}, "experiment")
    assert not (tmp_path / "experiment").exists()


def test_generated_ethanol_has_3d_coordinates_and_valid_bond_lengths(tmp_path):
    engine = WorkbenchEngine(tmp_path)
    result = engine.execute("molecule.generate_conformer", {"smiles": "CCO"}, "experiment", True)["result"]
    molecule = Chem.MolFromMolBlock(result["sdf"].split("$$$$")[0], removeHs=False)
    assert molecule is not None and molecule.GetNumAtoms() == 9
    assert molecule.GetConformer().Is3D()
    assert result["coordinate_units"] == "angstrom"
    assert result["energy_unit"] == "kcal/mol" and math.isfinite(result["energy"])
    assert result["converged"] is True
    for bond in molecule.GetBonds():
        a = molecule.GetConformer().GetAtomPosition(bond.GetBeginAtomIdx())
        b = molecule.GetConformer().GetAtomPosition(bond.GetEndAtomIdx())
        assert 0.8 < (a - b).Length() < 1.8
    assert not (tmp_path / "experiment").exists()


def test_conformer_size_limit_prevents_expensive_embedding(tmp_path):
    with pytest.raises(InputError, match="100 heavy atoms"):
        WorkbenchEngine(tmp_path).execute("molecule.generate_conformer", {"smiles": "C" * 101}, "experiment", True)
