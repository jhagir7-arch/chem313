"""Independent CP04 red-team tests: SQLite review and source preservation."""
from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
from pathlib import Path
import json
import os
import subprocess
import sys
import tempfile
import unittest
from fastapi.testclient import TestClient
from rdkit import Chem
from hypothesislab.engine import Engine
from hypothesislab.validation import InputError
from hypothesislab import api


class ReconciledApprovals(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)
        self.engine=Engine(self.root)
        self.req={"molfile":Chem.MolToMolBlock(Chem.MolFromSmiles("CCO"))}
    def tearDown(self): self.temp.cleanup()

    def test_one_ticket_two_engine_instances_one_success(self):
        token=self.engine.preview("molecule.import_molfile",self.req,"lab")["preview_token"]
        def apply():
            try:
                return Engine(self.root).execute("molecule.import_molfile",self.req,"lab",True,token)["status"]
            except InputError:
                return "DENIED"
        with ThreadPoolExecutor(max_workers=6) as pool:
            observed=list(pool.map(lambda _:apply(), range(6)))
        self.assertEqual(observed.count("EXECUTED"),1,observed)
        self.assertEqual(observed.count("DENIED"),5,observed)
        self.assertEqual(len(self.engine.store.events("lab")),1)

    def test_cross_process_preview_apply_replay(self):
        path=self.root/"input.mol";data=self.req["molfile"].encode();path.write_bytes(data)
        env={**os.environ,"PYTHONPATH":str(Path(__file__).resolve().parents[1]/"src")}
        base=[sys.executable,"-m","hypothesislab","--root",str(self.root/"db"),"--project","lab"]
        cmd=["molecule.import_molfile","--molfile-path",str(path)]
        def run(mode,more=()):
            return subprocess.run(base+[mode]+cmd+list(more),env=env,capture_output=True,text=True,timeout=25)
        first=run("apply")
        self.assertNotEqual(first.returncode,0)
        r=run("preview")
        self.assertEqual(r.returncode,0,r.stderr)
        token=json.loads(r.stdout)["preview_token"]
        self.assertTrue(token.startswith("hl_"), "CLI tickets must be shell-option safe")
        accepted=run("apply",["--preview-token",token])
        self.assertEqual(accepted.returncode,0,accepted.stderr)
        rejected=run("apply",["--preview-token",token])
        self.assertNotEqual(rejected.returncode,0)
        verify=subprocess.run(base+["verify"],env=env,capture_output=True,text=True,timeout=20)
        self.assertEqual(json.loads(verify.stdout)["status"],"PASS")
        self.assertEqual(path.read_bytes(),data)

    def test_different_action_denied_and_consumes_ticket(self):
        p=self.engine.preview("molecule.import_molfile",self.req,"lab")
        with self.assertRaises(InputError):
            self.engine.execute("avogadro.ping",{},"lab",True,p["preview_token"])
        with self.assertRaises(InputError):
            self.engine.execute("molecule.import_molfile",self.req,"lab",True,p["preview_token"])

    def test_multi_record_sdf_rejected_without_artifacts(self):
        src=self.req["molfile"]+"$$$$\n"+self.req["molfile"]+"$$$$\n"
        req={"molfile":src}
        with self.assertRaisesRegex(InputError,"SDF|Exactly one"):
            self.engine.preview("molecule.import_molfile",req,"lab")
        self.assertFalse((self.root/"lab"/"originals").exists())

    def test_artifact_tampering_detected(self):
        token=self.engine.preview("molecule.import_molfile",self.req,"lab")["preview_token"]
        a=self.engine.execute("molecule.import_molfile",self.req,"lab",True,token)
        self.assertEqual(self.engine.store.verify_artifacts("lab")["status"],"PASS")
        rel=a["artifacts"][0]["relative_path"]
        (self.root/rel).write_bytes(b"adulterated")
        faults=self.engine.store.verify_artifacts("lab")
        self.assertEqual(faults["status"],"FAILED")
        self.assertIn("HASH_OR_SIZE_MISMATCH",[x["reason"] for x in faults["faults"]])

    @unittest.skipUnless(hasattr(os,"link"),"Hard links require POSIX-style FS")
    def test_event_log_hard_link_rejected(self):
        proj=self.root/"lab";proj.mkdir()
        target=self.root/"external.txt";target.write_text("SENSITIVE")
        os.link(target,proj/"events.jsonl")
        token=self.engine.preview("molecule.import_molfile",self.req,"lab")["preview_token"]
        with self.assertRaises(InputError):
            self.engine.execute("molecule.import_molfile",self.req,"lab",True,token)
        self.assertEqual(target.read_text(),"SENSITIVE")
        self.assertFalse((proj/"originals").exists())

    def test_no_unapproved_verify_endpoint(self):
        old=api.engine;api.engine=self.engine
        try:
            client=TestClient(api.app)
            self.assertEqual(client.get("/api/projects/lab/verify").status_code,403)
            session=client.get("/api/session")
            self.assertEqual(session.headers.get("cache-control"),"no-store")
            header={"X-HypothesisLab-Session":session.json()["session_token"]}
            self.assertEqual(client.get("/api/projects/lab/verify",headers=header).json()["status"],"NO_EVENTS")
        finally:
            api.engine=old

if __name__=="__main__":unittest.main()
