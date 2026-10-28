"""Adversarial regression tests for request approval and local transport."""
from __future__ import annotations
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from rdkit import Chem
from hypothesislab import api
from hypothesislab.engine import Engine
from hypothesislab.validation import InputError
from hypothesislab.approval import ApprovalLedger, MAX_PENDING

class AuthorizationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.engine = Engine(self.tmp.name)
        self.payload = {'molfile': Chem.MolToMolBlock(Chem.MolFromSmiles('CO'))}

    def tearDown(self): self.tmp.cleanup()

    def issue(self, params=None, project='alpha', action='molecule.import_molfile'):
        return self.engine.preview(action, params if params is not None else self.payload,project)

    def apply(self, token, params=None, project='alpha', action='molecule.import_molfile'):
        return self.engine.execute(action,params if params is not None else self.payload,project,True,token)

    def test_requires_preview_for_write(self):
        with self.assertRaisesRegex(InputError,'preview token'):
            self.apply(None)

    def test_preview_has_no_project_write(self):
        p=self.issue()
        self.assertEqual(p['status'],'PREVIEW_ONLY')
        self.assertRegex(p['request_sha256'],r'^[a-f0-9]{64}$')
        self.assertFalse((Path(self.tmp.name)/'alpha').exists())

    def test_reviewed_request_executes(self):
        p=self.issue()
        r=self.apply(p['preview_token'])
        self.assertEqual(r['status'],'EXECUTED')
        self.assertTrue((Path(self.tmp.name)/'alpha').exists())

    def test_changed_molecule_consumes_ticket(self):
        p=self.issue()
        altered={'molfile':Chem.MolToMolBlock(Chem.MolFromSmiles('CCO'))}
        with self.assertRaisesRegex(InputError,'changed'):
            self.apply(p['preview_token'],altered)
        with self.assertRaisesRegex(InputError,'previously used'):
            self.apply(p['preview_token'])
        self.assertFalse((Path(self.tmp.name)/'alpha').exists())

    def test_changed_project_denied(self):
        p=self.issue()
        with self.assertRaises(InputError):
            self.apply(p['preview_token'],project='beta')
        self.assertFalse((Path(self.tmp.name)/'beta').exists())

    def test_cross_action_denied(self):
        p=self.issue()
        with self.assertRaises(InputError):
            self.engine.execute('avogadro.ping',{},'alpha',True,p['preview_token'])
        self.assertFalse((Path(self.tmp.name)/'alpha').exists())

    def test_replay_denied(self):
        p=self.issue(); self.apply(p['preview_token'])
        with self.assertRaisesRegex(InputError,'previously used'):
            self.apply(p['preview_token'])
        self.assertEqual(len(self.engine.store.events('alpha')),1)

    def test_expires(self):
        p=self.issue()
        with patch('hypothesislab.approval.time.time',return_value=time.time()+3600):
            with self.assertRaisesRegex(InputError,'expired'):
                self.apply(p['preview_token'])

    def test_backend_restart_preserves_one_use_approval(self):
        p=self.issue()
        new_engine=Engine(self.tmp.name)
        self.assertEqual(new_engine.execute('molecule.import_molfile',self.payload,'alpha',True,p['preview_token'])['status'],'EXECUTED')
        with self.assertRaises(InputError):
            self.apply(p['preview_token'])

    def test_pending_capacity(self):
        ledger=ApprovalLedger(self.tmp.name)
        for i in range(MAX_PENDING): ledger.preview(f"{i:064x}")
        with self.assertRaisesRegex(InputError,'Too many'):
            ledger.preview('f'*64)

    def test_event_log_symlink_rejected(self):
        p=self.issue()
        directory=Path(self.tmp.name)/'alpha';directory.mkdir()
        with tempfile.TemporaryDirectory() as outside:
            target=Path(outside)/'external.txt'; target.write_text('original')
            (directory/'events.jsonl').symlink_to(target)
            with self.assertRaises(InputError): self.apply(p['preview_token'])
            self.assertEqual(target.read_text(),'original')
            self.assertFalse((directory/'originals').exists())
            with self.assertRaises(InputError): self.engine.store.events('alpha')

    def test_event_log_symlink_rejected_without_nofollow(self):
        from unittest.mock import patch
        with patch.object(os, 'O_NOFOLLOW', 0, create=True):
            self.test_event_log_symlink_rejected()

    def test_readonly_does_not_consume_foreign_ticket(self):
        p=self.issue()
        res=self.engine.execute('molecule.inspect_smiles',{'smiles':'CCO'},'alpha',True,p['preview_token'])
        self.assertEqual(res['status'],'EXECUTED')
        self.assertEqual(self.apply(p['preview_token'])['status'],'EXECUTED')

    def test_events_read_has_no_write(self):
        self.assertEqual(self.engine.store.events('not_created'),[])
        self.assertFalse((Path(self.tmp.name)/'not_created').exists())

class HTTPBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.old=api.engine
        api.engine=Engine(self.tmp.name)
        self.client=TestClient(api.app)
        self.session=self.client.get('/api/session').json()['session_token']
        self.headers={'X-HypothesisLab-Session':self.session}
        self.data={'action':'molecule.import_molfile','params':{'molfile':Chem.MolToMolBlock(Chem.MolFromSmiles('CCO'))},'project':'alpha'}
    def tearDown(self): api.engine=self.old;self.tmp.cleanup()

    def test_extra_action_fields_are_rejected(self):
        # Never interpret a caller's undeclared switches as safe future expansion.
        payload={**self.data, 'debug_shell':True}
        result=self.client.post('/api/preview',headers=self.headers,json=payload)
        self.assertEqual(result.status_code,422)

    def test_remote_asgi_client_with_local_host_is_denied(self):
        import asyncio
        import httpx
        async def attempt():
            transport=httpx.ASGITransport(app=api.app,client=('203.0.113.77',40200))
            async with httpx.AsyncClient(transport=transport,base_url='http://127.0.0.1:8765') as client:
                return await client.get('/api/projects/alpha/events',headers={'Host':'127.0.0.1:8765'})
        self.assertEqual(asyncio.run(attempt()).status_code,403)

    def test_post_needs_session(self):
        self.assertEqual(self.client.post('/api/preview',json=self.data).status_code,403)

    def test_bad_session(self):
        self.assertEqual(self.client.post('/api/preview',headers={'X-HypothesisLab-Session':'wrong'},json=self.data).status_code,403)

    def test_foreign_origin_rejected(self):
        headers={**self.headers,'Origin':'https://unrelated.example'}
        self.assertEqual(self.client.post('/api/preview',headers=headers,json=self.data).status_code,403)
        self.assertEqual(self.client.get('/api/session',headers={'Origin':'https://unrelated.example'}).status_code,403)

    def test_dns_rebinding_host_rejected(self):
        r=self.client.get('/api/session',headers={'Host':'malicious.example'})
        self.assertEqual(r.status_code,400)

    def test_write_needs_preview(self):
        r=self.client.post('/api/execute',headers=self.headers,json={**self.data,'approved':True})
        self.assertEqual(r.status_code,422)

    def test_remote_client_denied(self):
        # Mock a remote peer without trusting any proxy-provided headers.
        from starlette.requests import Request
        import asyncio
        from hypothesislab.api import reject_nonlocal_clients
        scope={"type":"http","method":"GET","path":"/api/session","raw_path":b"/api/session",
               "headers":[],"client":("203.0.113.2",51000),"server":("127.0.0.1",8765),"scheme":"http"}
        request=Request(scope)
        async def proceed(r):
            raise AssertionError("remote peer reached application")
        res=asyncio.run(reject_nonlocal_clients(request,proceed))
        self.assertEqual(res.status_code,403)

    def test_http_happy_path_and_replay(self):
        p=self.client.post('/api/preview',headers=self.headers,json=self.data)
        self.assertEqual(p.status_code,200,p.text)
        receipt=p.json()['preview_token']
        req={**self.data,'approved':True,'preview_token':receipt}
        self.assertEqual(self.client.post('/api/execute',headers=self.headers,json=req).status_code,200)
        self.assertEqual(self.client.post('/api/execute',headers=self.headers,json=req).status_code,422)
