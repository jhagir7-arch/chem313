"""Conservative registry behavior when the public source tree has no catalog."""

from hypothesislab import engine_registry


def test_public_fallback_has_core_rows_without_commit_claims():
    catalog = engine_registry._public_core_catalog()
    names = {row["name"] for row in catalog["engines"]}
    assert {"RDKit", "Ketcher", "3DmolJS", "AvogadroApp", "OpenBabel"} <= names
    assert all(row["pinned_commit_sha"] is None for row in catalog["engines"])
    assert all(row["source_archive_url"] is None for row in catalog["engines"])


def test_manifest_reports_missing_runtimes_as_uninstalled(monkeypatch):
    monkeypatch.setattr(engine_registry, "_runtime_present", lambda name: False)

    def public_read(name, default):
        return None if name == "ENGINE_CATALOG.json" else default

    monkeypatch.setattr(engine_registry, "read", public_read)
    result = engine_registry.manifest()
    rows = {row["name"]: row for row in result["engines"]}
    assert rows["AvogadroApp"]["runtime"]["installed"] is False
    assert rows["AvogadroApp"]["runtime"]["tested"] is False
    assert rows["OpenBabel"]["runtime"]["installed"] is False
    assert rows["RDKit"]["source"]["commit"] is None


def test_manifest_marks_separately_installed_core_as_not_bundled(monkeypatch):
    monkeypatch.setattr(engine_registry, "_runtime_present", lambda name: name == "RDKit")

    def public_read(name, default):
        return None if name == "ENGINE_CATALOG.json" else default

    monkeypatch.setattr(engine_registry, "read", public_read)
    result = engine_registry.manifest()
    rdkit = next(row for row in result["engines"] if row["name"] == "RDKit")
    assert rdkit["runtime"]["installed"] is True
    assert rdkit["runtime"]["bundled"] is False
    assert rdkit["runtime"]["integrated"] is True
    assert rdkit["runtime"]["tested"] is False


def test_avogadro_status_does_not_start_host(monkeypatch, tmp_path):
    calls = []

    class Host:
        def __init__(self, root):
            self.root = root

        def status(self):
            calls.append(self.root)
            return {"status": "STOPPED", "installed": False, "version": "2.0.0"}

    monkeypatch.setattr("hypothesislab.avogadro_host.AvogadroHost", Host)
    monkeypatch.setenv("OPENCHEM_DATA", str(tmp_path))
    assert engine_registry._runtime_present("AvogadroApp") is False
    assert calls == [tmp_path]
