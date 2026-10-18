"""Focused RC2 guards reconciled with the desktop 0.5 storage contract."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient
from rdkit import Chem

from hypothesislab import api
from hypothesislab.approval import action_v2_digest
from hypothesislab.engine import Engine
from hypothesislab.store import Store
from hypothesislab.validation import InputError


class RC2ReconciliationTests(unittest.TestCase):
    def test_action_v2_cross_client_identifier(self):
        self.assertEqual(
            action_v2_digest("molecule.inspect_smiles", {"smiles": "N[C@@](F)(Cl)Br"}, "default"),
            "0b3c8f6192a6edf1308078c0457016375ba6b9b98955bca81f8a2c5e4922d03e",
        )

    def test_invalid_preview_does_not_create_an_approval_or_project(self):
        with tempfile.TemporaryDirectory() as root:
            engine = Engine(root)
            with self.assertRaisesRegex(InputError, "Non-finite"):
                engine.preview("measurement.fit_csv", {
                    "csv": "x,y\n0,1\n1,inf\n2,3\n", "x_column": "x", "y_column": "y",
                    "x_unit": "s", "y_unit": "a.u.",
                }, "lab")
            with self.assertRaisesRegex(InputError, "Reaction"):
                engine.preview("molecule.import_molfile", {"molfile": "$RXN\nM  END\n"}, "lab")
            self.assertFalse((Path(root) / "lab").exists())

    def test_single_sdf_metadata_still_previews_and_is_preserved_as_original_bytes(self):
        with tempfile.TemporaryDirectory() as root:
            engine = Engine(root)
            source = Chem.MolToMolBlock(Chem.MolFromSmiles("CCO")) + ">  <NOTE>\nkept only in source\n\n"
            preview = engine.preview("molecule.import_molfile", {"molfile": source}, "lab")
            result = engine.execute("molecule.import_molfile", {"molfile": source}, "lab", True, preview["preview_token"])
            original = next(a for a in result["artifacts"] if "/originals/" in a["relative_path"])
            self.assertEqual((Path(root) / original["relative_path"]).read_bytes(), source.encode("utf-8"))

    def test_unreferenced_note_is_reported_without_removal(self):
        with tempfile.TemporaryDirectory() as root:
            record = Store(root).put("lab", "originals", "txt", "raw note é".encode("utf-8"))
            audit = Store(root).verify_artifacts("lab")
            self.assertEqual(audit["status"], "REVIEW_REQUIRED")
            self.assertIn({"reason": "UNREFERENCED_OBJECT_CANDIDATE", "path": record["relative_path"]}, audit["unreferenced_candidates"])
            self.assertEqual((Path(root) / record["relative_path"]).read_bytes(), "raw note é".encode("utf-8"))

    def test_capabilities_require_session_and_describe_core_only(self):
        old = api.engine
        with tempfile.TemporaryDirectory() as root:
            api.engine = Engine(root)
            try:
                client = TestClient(api.app)
                self.assertEqual(client.get("/api/capabilities").status_code, 403)
                token = client.get("/api/session").json()["session_token"]
                body = client.get("/api/capabilities", headers={"X-HypothesisLab-Session": token}).json()
                self.assertEqual(body["contract_version"], "openchem.capabilities.v1")
                self.assertTrue(any(row["action"] == "measurement.fit_csv" for row in body["actions"]))
            finally:
                api.engine = old


if __name__ == "__main__":
    unittest.main()
