import json
import sys
import pytest
from hypothesislab import runtime_profile, science_jobs, engine_registry
from hypothesislab.validation import InputError


def profile(monkeypatch, tmp_path):
    data = {"schema": "openchem.standalone.v1", "operations": ["numpy.summary", "scipy.line"], "engines": [
        {"name": "NumPy", "domain": "numerical", "repo": "https://github.com/numpy/numpy", "version": "test", "license": "BSD-3-Clause", "operations": ["numpy.summary"]}]}
    (tmp_path / "bundle.json").write_text(json.dumps(data))
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
    return data


def test_source_mode_ignores_bundle_file(monkeypatch, tmp_path):
    profile(monkeypatch, tmp_path)
    monkeypatch.setattr(sys, "frozen", False)
    assert runtime_profile.bundled_profile() is None


def test_standalone_exposes_only_shipped_operations(monkeypatch, tmp_path):
    data = profile(monkeypatch, tmp_path)
    assert {x["operation"] for x in science_jobs.operation_descriptions()} == set(data["operations"])
    assert science_jobs.worker_command("scipy.line") == ([sys.executable, "--science-worker"], None)
    with pytest.raises(InputError, match="not included"):
        science_jobs.worker_command("pyscf.rhf_singlepoint")
    registry = engine_registry.manifest()
    assert registry["counts"]["installed"] == 1
    assert registry["counts"]["tested"] == 0
    assert registry["engines"][0]["runtime"]["bundled"] is True


def test_corrupt_profile_fails_closed(monkeypatch, tmp_path):
    profile(monkeypatch, tmp_path)
    (tmp_path / "bundle.json").write_text('{"schema":"wrong"}')
    with pytest.raises(RuntimeError, match="Invalid standalone"):
        science_jobs.worker_command("numpy.summary")
