"""Exercise the real companion through the production UI and frozen service.

Only synthetic molecules and a separate test project are used. The companion
window is left open so that the installed application can reconnect to it.
"""
from pathlib import Path
import json
import os
import socket
import struct
import time
from playwright.sync_api import sync_playwright, expect

base = os.environ.get('OPENCHEM_TEST_URL', 'http://127.0.0.1:8789')
output = Path('build/avogadro-ui-qa'); output.mkdir(parents=True, exist_ok=True)
project = 'native-ui-' + str(int(time.time()))
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={'width':1440, 'height':1000})
    errors = []; outside = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.on('request', lambda r: outside.append(r.url) if r.url.startswith('http') and not r.url.startswith(base) else None)
    page.goto(base, wait_until='networkidle', timeout=120000)
    expect(page.locator('.formula')).to_have_text('C8H9NO2', timeout=60000)
    page.once('dialog', lambda d: d.accept(project))
    page.get_by_role('button', name='New project', exact=True).click()
    page.get_by_role('button', name='Engines & tools', exact=True).click()
    expect(page.locator('.structure-layout')).to_be_hidden()
    page.get_by_role('button', name='Run engine checks', exact=True).click()
    expect(page.locator('.connection-row').filter(has_text='RDKit')).to_contain_text('PASS', timeout=30000)
    expect(page.locator('.connection-row').filter(has_text='SciPy')).to_contain_text('PASS')
    start = page.get_by_role('button', name='Start Avogadro', exact=True)
    if start.count(): start.click()
    expect(page.locator('.connection-row').filter(has_text='Avogadro 2')).to_contain_text('Connected · dedicated', timeout=60000)
    page.evaluate('window.scrollTo(0,0)')
    page.screenshot(path=str(output/'connections.png'), full_page=True)
    page.get_by_role('button', name='Structures', exact=True).click()
    page.get_by_role('button', name='Send current structure ↗', exact=True).click()
    page.evaluate("async()=>window.__openchemEditor.setMolecule('CCO')")
    page.get_by_role('button', name='Send & verify', exact=True).click()
    expect(page.get_by_role('alert')).to_contain_text('structure changed')
    page.get_by_label('Dismiss error').click()
    page.locator('#smiles').fill('CC(=O)NC1=CC=C(O)C=C1')
    page.get_by_role('button', name='Load', exact=True).click()
    expect(page.locator('.formula')).to_have_text('C8H9NO2')
    page.get_by_role('button', name='Generate 3D', exact=True).click()
    expect(page.locator('.conformer-result').filter(has_text='MMFF')).to_be_visible(timeout=30000)
    page.get_by_role('button', name='Send current structure ↗', exact=True).click()
    page.get_by_role('button', name='Send & verify', exact=True).click()
    expect(page.get_by_role('status').filter(has_text='Checked molecular fields match')).to_be_visible(timeout=60000)
    token = page.request.get(base+'/api/session').json()['session_token']
    headers = {'X-HypothesisLab-Session':token}
    info = page.request.get(base+'/api/workbench',headers=headers).json()
    assert info['avogadro']['status']=='RESPONDED'
    # A change made directly in the native host must be what Receive imports.
    result = page.request.post(base+'/api/execute',headers=headers,data={
        'action':'molecule.generate_conformer','params':{'smiles':'CCO'},'project':project,'approved':True}).json()
    molfile = result['result']['sdf'].split('$$$$')[0]
    payload = json.dumps({'jsonrpc':'2.0','id':1,'method':'loadMolecule','params':{'format':'mol','content':molfile}}).encode()
    with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as sock:
        sock.settimeout(10); sock.connect(info['avogadro']['socket'])
        sock.sendall(struct.pack('>I',len(payload))+payload)
        def exact(n):
            data=b''
            while len(data)<n:
                block=sock.recv(n-len(data)); assert block; data+=block
            return data
        size,=struct.unpack('>I',exact(4))
        assert json.loads(exact(size))['result'] is True
    page.get_by_role('button', name='Receive from Avogadro', exact=True).click()
    page.get_by_role('button', name='Receive & save', exact=True).click()
    expect(page.locator('.formula')).to_have_text('C2H6O',timeout=30000)
    expect(page.locator('#smiles')).not_to_have_value('CC(NC1C=CC(O)=CC=1)=O')
    inspected=page.request.post(base+'/api/execute',headers=headers,data={
        'action':'molecule.inspect_smiles','params':{'smiles':page.locator('#smiles').input_value()},'project':project,'approved':True}).json()
    assert inspected['result']['isomeric_smiles']=='CCO',inspected
    expect(page.get_by_role('status').filter(has_text='Native export preserved')).to_be_visible()
    expect(page.locator('.viewer canvas')).to_be_visible(timeout=30000)
    page.evaluate('window.scrollTo(0,0)')
    page.screenshot(path=str(output/'native-received.png'), full_page=True)
    events=page.request.get(base+f'/api/projects/{project}/events',headers=headers).json()['events']
    assert len(events)==2,events
    assert events[0]['result']['fidelity_status']=='CHECKED_FIELDS_MATCH'
    assert all(events[0]['result']['field_checks'].values())
    assert events[1]['result']['summary']['formula']=='C2H6O'
    assert page.request.get(base+f'/api/projects/{project}/verify',headers=headers).json()['status']=='PASS'
    page.set_viewport_size({'width':850,'height':650})
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    expect(page.get_by_role('button',name='Save structure',exact=True)).to_be_visible()
    page.evaluate('window.scrollTo(0,0)')
    page.screenshot(path=str(output/'compact.png'), full_page=True)
    assert errors==[],errors
    assert outside==[],outside
    browser.close()
record={'status':'PASS','project':project,'host':info['avogadro'],
        'checks':['live RDKit and SciPy probes','bundled host start and ping',
                  'stale send receipt rejected','paracetamol 3D send and nine field checks',
                  'native host changed to ethanol and received into editor and WebGL',
                  'original/export/report hashes verified','850px layout without horizontal overflow',
                  'no uncaught browser errors or external HTTP requests']}
(output/'results.json').write_text(json.dumps(record,indent=2))
print(json.dumps(record,indent=2))
