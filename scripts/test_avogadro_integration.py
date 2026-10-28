"""Real host integration, including queued export completion and persisted fidelity.

Set OPENCHEM_AVOGADRO_APP for source runs. Synthetic molecules only. The process
created by this test is stopped after its captured exports have been verified.
"""
from pathlib import Path
import json
import os
from rdkit import Chem
from hypothesislab.workbench import WorkbenchEngine
from hypothesislab.conformers import molecule_conformer

root=Path(os.environ.get('OPENCHEM_NATIVE_TEST_DATA','build/native-integration')).resolve()
engine=WorkbenchEngine(root)

def apply(action,params):
    ticket=engine.preview(action,params,'native-test')['preview_token']
    return engine.execute(action,params,'native-test',True,ticket)

results=[]
try:
    host=apply('avogadro.start',{})['result']
    assert host['status']=='RESPONDED',host
    for name,smiles in [('ethanol','CCO'),('paracetamol','CC(=O)NC1=CC=C(O)C=C1')]:
        source=molecule_conformer({'smiles':smiles})['sdf'].split('$$$$')[0]
        response=apply('avogadro.send',{'molfile':source})
        result=response['result']
        assert result['fidelity_status']=='CHECKED_FIELDS_MATCH',result['field_checks']
        received=apply('avogadro.capture',{})
        assert received['result']['summary']==result['summary']
        for artifact in response['artifacts']+received['artifacts']:
            assert (root/artifact['relative_path']).is_file()
        results.append({'molecule':name,'formula':result['summary']['formula'],
                        'atoms':result['summary']['atom_count'],'bonds':result['summary']['bond_count'],
                        'field_checks':result['field_checks']})
    assert engine.store.verify_artifacts('native-test')['status']=='PASS'
    # Restarting only the service must reconnect to the same companion socket.
    recovered=WorkbenchEngine(root)
    assert recovered.avogadro.status()['status']=='RESPONDED'
    assert recovered.avogadro.socket==engine.avogadro.socket
    output={'status':'PASS','host':host,'checks':results,'host_reconnect':'PASS',
            'stored_files':'PASS','scope':'MOL transfer; not all native plugins'}
    (root/'result.json').write_text(json.dumps(output,indent=2))
    print(json.dumps(output,indent=2))
finally:
    if engine.avogadro.process is not None:
        engine.avogadro.process.terminate()
        engine.avogadro.process.wait(timeout=10)
