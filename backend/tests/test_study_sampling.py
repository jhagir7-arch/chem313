import math

import pytest

from hypothesislab import study_sampling


def test_butane_sampling_records_duplicates_and_relative_energies():
    result = study_sampling.sample_shapes("CCCC", count=4)
    assert result["canonical_smiles"] == "CCCC"
    assert result["formula"] == "C4H10"
    assert result["completed"] == 4 and result["cancelled"] is False
    assert result["unique_count"] >= 1
    assert all(row["status"] in {"unique", "duplicate", "failed", "not_converged"} for row in result["candidates"])
    assert all(math.isfinite(row["energy"]) for row in result["candidates"] if row["energy"] is not None)
    unique = [row for row in result["candidates"] if row["status"] == "unique"]
    assert all("relative_energy" in row for row in unique)
    assert min(row["relative_energy"] for row in unique) == pytest.approx(0.0)
    assert max(row["relative_energy"] for row in unique) > 0.01
    assert any(row["status"] == "duplicate" for row in result["candidates"])
    for row in result["candidates"]:
        if row["status"] == "duplicate":
            assert row["duplicate_of"] < row["seed"]
            assert row["rmsd"] <= 0.25


def test_sampling_is_repeatable():
    first = study_sampling.sample_shapes("CCCO", count=3)
    second = study_sampling.sample_shapes("CCCO", count=3)
    assert first["canonical_smiles"] == second["canonical_smiles"]
    for left, right in zip(first["candidates"], second["candidates"]):
        assert (left["seed"], left["status"], left.get("duplicate_of")) == (right["seed"], right["status"], right.get("duplicate_of"))
        if left.get("rmsd") is None:
            assert right.get("rmsd") is None
        else:
            assert left["rmsd"] == pytest.approx(right["rmsd"])
        if left.get("energy") is None:
            assert right.get("energy") is None
        else:
            assert left["energy"] == pytest.approx(right["energy"])


@pytest.mark.parametrize("smiles", ["[NH4+]", "[CH3]", "[13CH3]O", "CC.O", "[Na+]", "[SeH2]"])
def test_sampling_rejects_out_of_scope_identity(smiles):
    with pytest.raises(ValueError):
        study_sampling.sample_shapes(smiles)


@pytest.mark.parametrize("count", [True, 0, 9, 1.5, "2", None])
def test_sampling_rejects_invalid_counts(count):
    with pytest.raises(ValueError):
        study_sampling.sample_shapes("CC", count=count)


def test_sampling_cancellation_preserves_completed_candidates():
    calls = []
    result = study_sampling.sample_shapes("CCCO", count=5, stop_requested=lambda: len(calls) >= 2,
                                          on_progress=lambda completed, total: calls.append((completed, total)))
    assert result["cancelled"] is True
    assert result["completed"] == 2
    assert calls == [(1, 5), (2, 5)]


def test_sampling_records_conformer_failures(monkeypatch):
    original = study_sampling.molecule_conformer
    def flaky(params):
        if params["seed"] == 137:
            raise RuntimeError("intentional adapter failure")
        return original(params)
    monkeypatch.setattr(study_sampling, "molecule_conformer", flaky)
    result = study_sampling.sample_shapes("CCCO", count=3)
    failed = result["candidates"][1]
    assert failed["seed"] == 137 and failed["status"] == "failed"
    assert failed["energy"] is None and "intentional adapter failure" in failed["error"]
