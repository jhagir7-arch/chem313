"""Focused regressions adopted from independently reviewed source snapshots."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from rdkit import Chem

from hypothesislab.approval import ApprovalLedger
from hypothesislab.chemistry import fidelity, from_molfile
from hypothesislab.measurements import fit_csv
from hypothesislab.store import Store
from hypothesislab.validation import InputError, validate


class HandoffRegressions(unittest.TestCase):
    def test_csv_rejects_ambiguous_ragged_and_unstable_input(self):
        for body in (
            "time,signal,Signal\n0,1,2\n1,2,3\n2,3,4\n",
            "time,signal\n0,1,extra\n1,2,extra\n2,3,extra\n",
            "time,signal\n1e307,1\n2e307,2\n3e307,3\n",
        ):
            with self.subTest(body=body), self.assertRaises(InputError):
                fit_csv(body, "time", "signal", "s", "a.u.")
        with self.assertRaises(InputError):
            validate("measurement.fit_csv", {"csv":"time,signal\n0,1\n1,2\n2,3\n", "x_column":"time", "y_column":"signal", "x_unit":"  ", "y_unit":"a.u."}, "lab")

    def test_mol_record_and_fidelity_metadata_boundaries(self):
        mol = Chem.MolToMolBlock(Chem.MolFromSmiles("C[C@@H](O)F"))
        with self.assertRaisesRegex(InputError, "Exactly one"):
            from_molfile(mol + "\n" + mol)
        report = fidelity(mol + "> <STUDY_IDENTIFIER>\nA-18\n\n")
        self.assertTrue(report["source_metadata_lost_in_derivative"])
        self.assertFalse(report["known_fields_passed_without_detected_metadata_loss"])
        self.assertIn("atom_map_numbers", report["checks"])

    def test_audit_validates_entire_log_and_non_utf8_is_failed(self):
        with tempfile.TemporaryDirectory() as root:
            store = Store(root)
            project = Path(root) / "lab"
            project.mkdir()
            (project / "events.jsonl").write_bytes(b"not json\n" + b"{}\n" * 101)
            with self.assertRaises(InputError):
                store.events("lab", limit=1)
            (project / "events.jsonl").write_bytes(b"\xff\n")
            self.assertEqual(store.verify_artifacts("lab")["faults"][0]["reason"], "INVALID_EVENT_ENCODING")

    def test_note_bytes_use_existing_content_addressed_guards(self):
        with tempfile.TemporaryDirectory() as root:
            record = Store(root).put("lab", "originals", "txt", "A note in UTF-8: é".encode("utf-8"))
            self.assertTrue(record["relative_path"].endswith(".txt"))
            self.assertEqual((Path(root) / record["relative_path"]).read_bytes(), "A note in UTF-8: é".encode("utf-8"))

    def test_clock_rollback_revokes_cross_instance_ticket(self):
        with tempfile.TemporaryDirectory() as root:
            digest = "a" * 64
            ledger = ApprovalLedger(root)
            with patch("hypothesislab.approval.time.time", return_value=2_000_000_000.0):
                ticket = ledger.preview(digest)
            with patch("hypothesislab.approval.time.time", return_value=1_999_999_000.0):
                with self.assertRaisesRegex(InputError, "clock moved backward"):
                    ApprovalLedger(root).consume(ticket, digest)
            with patch("hypothesislab.approval.time.time", return_value=2_000_000_010.0):
                with self.assertRaisesRegex(InputError, "previously used"):
                    ledger.consume(ticket, digest)


if __name__ == "__main__":
    unittest.main()
