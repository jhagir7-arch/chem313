import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from rdkit import Chem

class CLITests(unittest.TestCase):
    def setUp(self): self.tmp=tempfile.TemporaryDirectory(); self.root=Path(self.tmp.name)
    def tearDown(self): self.tmp.cleanup()
    def invoke(self, *args):
        env={**os.environ,'PYTHONPATH':str(Path(__file__).resolve().parents[1]/'src')}
        return subprocess.run([sys.executable,'-m','hypothesislab','--root',str(self.root/'db'),'--project','trial',*args],
                capture_output=True,text=True,env=env,timeout=20)

    def test_cli_review_and_apply_no_bypass(self):
        file=self.root/'input.mol'
        raw=Chem.MolToMolBlock(Chem.MolFromSmiles('CCO')).replace('\n','\r\n').encode('utf-8')
        file.write_bytes(raw)
        args=('molecule.import_molfile','--molfile-path',str(file))
        preview=self.invoke('preview',*args)
        self.assertEqual(preview.returncode,0,preview.stderr)
        token=json.loads(preview.stdout)['preview_token']
        self.assertTrue(len(token)>30)
        denied=self.invoke('apply',*args)
        self.assertEqual(denied.returncode,2)
        accepted=self.invoke('apply',*args,'--preview-token',token)
        self.assertEqual(accepted.returncode,0,accepted.stderr)
        artifacts=json.loads(accepted.stdout)['artifacts']
        originals=[a for a in artifacts if '/originals/' in a['relative_path']]
        self.assertEqual(len(originals),1)
        self.assertEqual((self.root/'db'/originals[0]['relative_path']).read_bytes(),raw)

    def test_cli_fitted_csv(self):
        f=self.root/'sample.csv'; f.write_text('t,y\n0,1\n1,3\n2,5\n')
        args=('measurement.fit_csv','--csv-path',str(f),'--x-column','t','--y-column','y','--x-unit','s','--y-unit','a.u.')
        preview=self.invoke('preview',*args)
        self.assertEqual(preview.returncode,0,preview.stderr)
        token=json.loads(preview.stdout)['preview_token']
        apply=self.invoke('apply',*args,'--preview-token',token)
        self.assertEqual(apply.returncode,0,apply.stderr)
        self.assertAlmostEqual(json.loads(apply.stdout)['result']['slope'],2)

    def test_changed_source_denies_approval(self):
        f=self.root/'input.mol'; f.write_text(Chem.MolToMolBlock(Chem.MolFromSmiles('CO')))
        args=('molecule.import_molfile','--molfile-path',str(f))
        token=json.loads(self.invoke('preview',*args).stdout)['preview_token']
        f.write_text(Chem.MolToMolBlock(Chem.MolFromSmiles('CCO')))
        bad=self.invoke('apply',*args,'--preview-token',token)
        self.assertEqual(bad.returncode,2)
        self.assertFalse((self.root/'db'/'trial'/'originals').exists())
