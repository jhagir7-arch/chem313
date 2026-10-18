"""Host boundary regression tests; real companion is checked by integration script."""
import json
from pathlib import Path
from unittest.mock import patch
import pytest
from rdkit import Chem
from hypothesislab.workbench import WorkbenchEngine
from hypothesislab.avogadro_host import AvogadroHost
from hypothesislab.validation import InputError

MOL = Chem.MolToMolBlock(Chem.MolFromSmiles('CCO'))

def test_send_binds_source_and_project_before_host_mutation(tmp_path):
    engine=WorkbenchEngine(tmp_path)
    params={'molfile': MOL}
    token=engine.preview('avogadro.send', params, 'sample')['preview_token']
    with patch.object(engine.avogadro,'send') as send:
        with pytest.raises(InputError):
            engine.execute('avogadro.send', {'molfile':MOL+'\n'}, 'sample', True, token)
        send.assert_not_called()
    assert not (tmp_path/'sample').exists()

def test_success_preserves_source_and_host_export_with_field_report(tmp_path):
    engine=WorkbenchEngine(tmp_path)
    params={'molfile':MOL}
    token=engine.preview('avogadro.send',params,'sample')['preview_token']
    with patch.object(engine.avogadro,'send',return_value=MOL), patch.object(engine.avogadro,'status',return_value={'status':'RESPONDED'}):
        response=engine.execute('avogadro.send',params,'sample',True,token)
    assert response['result']['fidelity_status']=='CHECKED_FIELDS_MATCH'
    assert all(response['result']['field_checks'].values())
    assert len(response['artifacts'])==3
    assert (tmp_path/response['artifacts'][0]['relative_path']).read_bytes()==MOL.encode()
    assert engine.store.verify_artifacts('sample')['status']=='PASS'
    with pytest.raises(InputError):
        engine.execute('avogadro.send',params,'sample',True,token)

def test_changed_native_graph_is_reported_without_false_pass(tmp_path):
    engine=WorkbenchEngine(tmp_path);params={'molfile':MOL}
    token=engine.preview('avogadro.send',params,'sample')['preview_token']
    changed=Chem.MolToMolBlock(Chem.MolFromSmiles('CC'))
    with patch.object(engine.avogadro,'send',return_value=changed),patch.object(engine.avogadro,'status',return_value={'status':'RESPONDED'}):
        response=engine.execute('avogadro.send',params,'sample',True,token)
    assert response['result']['fidelity_status']=='DIFFERENCE_DETECTED'
    assert response['result']['field_checks']['atom_count'] is False

def test_capture_requires_receipt_and_preserves_native_bytes(tmp_path):
    engine=WorkbenchEngine(tmp_path)
    with patch.object(engine.avogadro,'capture',return_value=MOL),patch.object(engine.avogadro,'status',return_value={'status':'RESPONDED'}):
        with pytest.raises(InputError): engine.execute('avogadro.capture',{},'sample',True)
        token=engine.preview('avogadro.capture',{},'sample')['preview_token']
        response=engine.execute('avogadro.capture',{},'sample',True,token)
    assert response['result']['molfile']==MOL
    assert (tmp_path/response['artifacts'][0]['relative_path']).read_bytes()==MOL.encode()

def test_saved_socket_pointer_cannot_target_ordinary_host(tmp_path):
    (tmp_path/'.avogadro-host.json').write_text(json.dumps({'socket':'/tmp/avogadro'}))
    assert AvogadroHost(tmp_path).socket is None

def test_capture_offline_is_actionable(tmp_path):
    with pytest.raises(InputError,match='Start Avogadro'):
        AvogadroHost(tmp_path).capture()

@pytest.mark.parametrize('tail', ['$$$$\n', '> <ASSAY_ID>\nsource-123\n\n$$$$\n'])
def test_native_transfer_rejects_sdf_metadata_before_host_mutation(tmp_path, tail):
    engine=WorkbenchEngine(tmp_path)
    with patch.object(engine.avogadro,'send') as send:
        with pytest.raises(InputError,match='plain MOL only'):
            engine.preview('avogadro.send',{'molfile':MOL+tail},'sample')
        with pytest.raises(InputError,match='plain MOL only'):
            engine.execute('avogadro.send',{'molfile':MOL+tail},'sample',True,'unused')
        send.assert_not_called()
    assert not (tmp_path/'sample').exists()
