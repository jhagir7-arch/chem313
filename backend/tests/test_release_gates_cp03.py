"""Keep source evidence and the public contract synchronized as peers amend code."""
from pathlib import Path
import hashlib,json
import unittest
from hypothesislab.api import app
from hypothesislab import __version__

ROOT=Path(__file__).resolve().parents[2]

class ReleaseGateTests(unittest.TestCase):
    def test_generated_openapi_is_current(self):
        actual=app.openapi()
        shipped=json.loads((ROOT/'contracts/openapi.generated.json').read_text())
        self.assertEqual(shipped,actual)
        self.assertEqual(shipped['info']['version'],__version__)
        self.assertEqual(shipped['components']['securitySchemes']['APIKeyHeader']['name'],'X-HypothesisLab-Session')

    def test_original_peer_archive_hashes(self):
        candidate = ROOT/'BUNDLE_MANIFEST.json'
        if candidate.is_file():
            package = json.loads(candidate.read_text())
            if (package.get('schema') == 'openchem.public-source-candidate.v1'
                    and 'Private Drive receipts and handoff archives' in package.get('excluded', [])
                    and not (ROOT/'evidence/originals').exists()):
                self.skipTest('Private handoff archives excluded from the public source candidate; archive integrity NOT RUN')
        lock=json.loads((ROOT/'contracts/SOURCE_LOCK.json').read_text())['sources']
        self.assertEqual(len(lock),6)
        for name,checksum in lock.items():
            self.assertEqual(hashlib.sha256((ROOT/'evidence/originals'/name).read_bytes()).hexdigest(),checksum)

    def test_no_unverified_native_claim(self):
        components=json.loads((ROOT/'contracts/UPSTREAM_COMPONENTS.json').read_text())['entries']
        native=[e for e in components if e['id']=='avogadro2']
        self.assertEqual(native[0]['status'],'MOCK_RPC_ONLY')
        self.assertFalse(any(e['status']=='TESTED_REAL_HOST' for e in components))

    def test_upstream_271_feature_register_is_planned_only(self):
        raw=json.loads((ROOT/'contracts/reference_registry/FEATURE_REGISTRY_v0.1.json').read_text())
        self.assertEqual(raw['status'],'PLANNED_NOT_IMPLEMENTED')
        self.assertEqual(len(raw['sources']),36)
        self.assertEqual(sum(len(src.get('features',[])) for src in raw['sources']),271)

    def test_competitor_outcomes_are_not_invented(self):
        import csv
        with (ROOT/'contracts/COMPETITOR_CHALLENGE.csv').open() as f: rows=list(csv.DictReader(f))
        self.assertEqual(len(rows),10)
        self.assertTrue(all(r['decision']=='HOLD' for r in rows))
