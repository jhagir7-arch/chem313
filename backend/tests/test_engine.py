"""Cross-platform deterministic tests. Run via PYTHONPATH=src python -m unittest discover -s tests -v."""
import csv
import io
import json
import tempfile
import unittest
from pathlib import Path
from rdkit import Chem
from hypothesislab.chemistry import from_smiles, fidelity, summary
from hypothesislab.engine import Engine
from hypothesislab.measurements import fit_csv
from hypothesislab.validation import InputError

class EngineTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.engine=Engine(self.tmp.name)
    def tearDown(self): self.tmp.cleanup()
    def test_smiles_formula(self):
        self.assertEqual(summary(from_smiles('CCO'))['formula'],'C2H6O')
    def test_isotopes_charge(self):
        report=summary(from_smiles('[13CH3][O-]'))
        self.assertEqual(report['formal_charge'],-1)
        self.assertEqual(report['isotope_atoms'][0]['mass_number'],13)
    def test_invalid_smiles_rejected(self):
        with self.assertRaises(InputError):from_smiles('Qwerty(!)')
    def test_preview_nonexecuting(self):
        p=self.engine.preview('molecule.inspect_smiles',{'smiles':'CCO'},'TestProject')
        self.assertEqual(p['status'],'PREVIEW_ONLY')
        self.assertFalse((Path(self.tmp.name)/'TestProject').exists())
    def test_explicit_approval_required(self):
        with self.assertRaises(InputError):
            self.engine.execute('molecule.inspect_smiles',{'smiles':'CCO'})
    def test_reject_artifact_directory_symlink(self):
        source=Chem.MolToMolBlock(Chem.MolFromSmiles("CCO"))
        (Path(self.tmp.name)/"test").mkdir()
        with tempfile.TemporaryDirectory() as external:
            (Path(self.tmp.name)/"test"/"originals").symlink_to(external, target_is_directory=True)
            with self.assertRaises(InputError):
                self.engine.execute("molecule.import_molfile",{"molfile":source},project="test",approved=True,preview_token=self.engine.preview("molecule.import_molfile",{"molfile":source},"test")["preview_token"])
    def test_readonly_tool_writes_nothing(self):
        r=self.engine.execute('molecule.inspect_smiles',{'smiles':'CCO'},approved=True)
        self.assertEqual(r['status'],'EXECUTED')
        self.assertFalse((Path(self.tmp.name)/'default').exists())
    def test_reject_traversal(self):
        with self.assertRaises(InputError):self.engine.preview('avogadro.ping',{},'../private')
    def test_reject_undeclared_tool(self):
        with self.assertRaises(InputError):self.engine.preview('shell.execute',{'shell':'rm -rf /'},'default')
    def test_reject_extra_params(self):
        with self.assertRaises(InputError):self.engine.preview('molecule.inspect_smiles',{'smiles':'CCO','cmd':'other'},'default')
    def test_reject_large_payload(self):
        with self.assertRaises(InputError):self.engine.preview('molecule.inspect_smiles',{'smiles':'C'*5001})
    def test_import_immutable(self):
        mol=Chem.MolFromSmiles('CCO')
        source=Chem.MolToMolBlock(mol)
        req={'molfile':source}
        one=self.engine.execute('molecule.import_molfile',req,project='alpha',approved=True,preview_token=self.engine.preview('molecule.import_molfile',req,'alpha')['preview_token'])
        two=self.engine.execute('molecule.import_molfile',req,project='alpha',approved=True,preview_token=self.engine.preview('molecule.import_molfile',req,'alpha')['preview_token'])
        orig=[a for a in one['artifacts'] if '/originals/' in a['relative_path']][0]
        self.assertEqual(orig['sha256'],[a for a in two['artifacts'] if '/originals/' in a['relative_path']][0]['sha256'])
        self.assertEqual((Path(self.tmp.name)/orig['relative_path']).read_text(), source)
        self.assertEqual(len(self.engine.store.events('alpha')),2)
        self.assertTrue(one['result']['fidelity']['all_compared_fields_preserved'])
        self.assertEqual(len(one['artifacts']),4)
    def test_mol_stereochemistry(self):
        mol=Chem.MolFromSmiles('N[C@@](F)(Cl)Br');report=fidelity(Chem.MolToMolBlock(mol))
        self.assertTrue(report['checks']['isomeric_smiles'],report['checks'])
    def test_mol_properties_flagged(self):
        mol=Chem.MolFromSmiles('CCO');text=Chem.MolToMolBlock(mol)+'>  <OperatorNote>\nTest note\n\n'
        result=fidelity(text)
        self.assertIn('OperatorNote',result['reported_property_tags'])
        self.assertTrue(result['warnings'])
    def test_bad_molfile(self):
        with self.assertRaises(InputError):fidelity('garbage')
    def test_fidelity_readonly(self):
        mol=Chem.MolToMolBlock(Chem.MolFromSmiles('CCO'))
        result=self.engine.execute('molecule.fidelity_audit',{'molfile':mol},approved=True)
        self.assertEqual(result['result']['checks']['formula'],True)
        self.assertFalse((Path(self.tmp.name)/'default').exists())
    def test_project_ids(self):
        for ident in ('a/b','.hidden','', 'a'*49):
            with self.assertRaises(InputError):self.engine.preview('avogadro.ping',{},ident)
    def test_fit_csv(self):
        result,svg=fit_csv('x,y\n0,1\n1,3\n2,5\n3,7\n','x','y','s','a.u.')
        self.assertAlmostEqual(result['slope'],2)
        self.assertEqual(result['dropped_rows'],0)
        self.assertIn(b'<svg',svg)
    def test_fit_rejects_missing(self):
        with self.assertRaises(InputError):fit_csv('x,y\n0,1\n1,\n2,4\n','x','y','s','V')
    def test_fit_rejects_infinity(self):
        with self.assertRaises(InputError):fit_csv('x,y\n0,1\n1,inf\n2,4\n','x','y','s','V')
    def test_fit_records_sources(self):
        params={'csv':'time_s,signal_au\n0,1\n1,3\n2,5\n','x_column':'time_s','y_column':'signal_au','x_unit':'s','y_unit':'a.u.'}
        response=self.engine.execute('measurement.fit_csv',params,'Experiment',True,preview_token=self.engine.preview('measurement.fit_csv',params,'Experiment')['preview_token'])
        self.assertEqual(response['result']['input_rows'],3)
        self.assertEqual(len(response['artifacts']),3)
        self.assertEqual(len(self.engine.store.events('Experiment')),1)
    def test_fit_parameter_contract(self):
        with self.assertRaises(InputError):self.engine.preview('measurement.fit_csv',{'csv':'x,y\n0,0'})

if __name__=='__main__': unittest.main()
