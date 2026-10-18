import tempfile
import unittest
from fastapi.testclient import TestClient
from hypothesislab import api
from hypothesislab.engine import Engine

class APIContractTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.old=api.engine
        api.engine=Engine(self.tmp.name)
        self.client=TestClient(api.app)
        self.headers={"X-HypothesisLab-Session":self.client.get("/api/session").json()["session_token"]}
    def tearDown(self):
        api.engine=self.old
        self.tmp.cleanup()
    def test_health(self):
        self.assertEqual(self.client.get('/api/health').json()['status'],'OK')
    def test_preview(self):
        res=self.client.post('/api/preview',headers=self.headers,json={'action':'molecule.inspect_smiles','params':{'smiles':'CCO'}})
        self.assertEqual(res.status_code,200)
        self.assertEqual(res.json()['status'],'PREVIEW_ONLY')
    def test_cannot_apply_without_approval(self):
        res=self.client.post('/api/execute',headers=self.headers,json={'action':'molecule.inspect_smiles','params':{'smiles':'CCO'}})
        self.assertEqual(res.status_code,422)
    def test_execute(self):
        res=self.client.post('/api/execute',headers=self.headers,json={'action':'molecule.inspect_smiles','params':{'smiles':'CCO'},'approved':True})
        self.assertEqual(res.json()['result']['formula'],'C2H6O')
    def test_unrecognized_tool(self):
        res=self.client.post('/api/execute',headers=self.headers,json={'action':'program.run','params':{},'approved':True})
        self.assertEqual(res.status_code,422)
    def test_history_empty(self):
        res=self.client.get('/api/projects/alpha/events',headers=self.headers)
        self.assertEqual(res.json()['events'],[])
