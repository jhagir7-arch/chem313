"""Real production UI proof. Requires the Python Playwright test dependency."""
from pathlib import Path
import hashlib
import json
import os
import re
import time
from playwright.sync_api import sync_playwright, expect

BASE = os.environ.get('OPENCHEM_TEST_URL', 'http://127.0.0.1:8788')
OUTPUT = Path('build/ui-qa'); OUTPUT.mkdir(parents=True, exist_ok=True)
project = 'qa-' + str(int(time.time()))
checks = []
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={'width':1440, 'height':1000}, accept_downloads=True)
    errors = []; outside = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.on('request', lambda r: outside.append(r.url) if r.url.startswith('http') and not r.url.startswith(BASE) else None)
    page.goto(BASE, wait_until='networkidle', timeout=120000)
    expect(page.locator('.formula')).to_have_text('C8H9NO2', timeout=60000)
    checks.append('Ketcher initializes; RDKit paracetamol formula')
    page.once('dialog', lambda d:d.accept(project))
    page.get_by_role('button', name='New project', exact=True).click()
    expect(page.get_by_label('Current project')).to_have_value(project)
    page.locator('#smiles').fill('CCO')
    page.get_by_role('button', name='Load', exact=True).click()
    expect(page.locator('.formula')).to_have_text('C2H6O')
    page.get_by_role('button', name='Save structure', exact=True).click()
    expect(page.get_by_role('dialog')).to_be_visible()
    page.evaluate("async()=>window.__openchemEditor.setMolecule('CC')")
    page.get_by_role('button',name='Save to project',exact=True).click()
    expect(page.get_by_role('alert')).to_contain_text('structure changed')
    page.get_by_label('Dismiss error').click()
    checks.append('Changed drawing rejected after save review')
    text = page.evaluate("async()=>window.__openchemEditor.getMolfile('v3000')").replace('\r\n','\n').replace('\n','\r\n')
    raw = text.encode('utf-8')
    page.locator('input[type=file][accept=".mol"]').set_input_files({'name':'source-crlf.mol','mimeType':'chemical/x-mdl-molfile','buffer':raw})
    expect(page.locator('.formula')).to_have_text('C2H6')
    page.get_by_role('button',name='Save structure',exact=True).click()
    expect(page.get_by_role('dialog')).to_be_visible()
    page.get_by_role('button',name='Save to project',exact=True).click()
    expect(page.get_by_role('status').filter(has_text='Original bytes preserved')).to_be_visible()
    token=page.request.get(BASE+'/api/session').json()['session_token']
    headers={'X-HypothesisLab-Session':token}
    events=page.request.get(BASE+f'/api/projects/{project}/events',headers=headers).json()['events']
    assert len(events)==1, events
    original=next(a for a in events[0]['artifacts'] if '/originals/' in a['relative_path'])
    assert original['sha256']==hashlib.sha256(raw).hexdigest()
    artifact=page.request.get(BASE+'/api/projects/'+original['relative_path'].replace('/originals/','/artifact/originals/'),headers=headers)
    assert artifact.ok and artifact.body()==raw
    checks.append('Imported MOL CRLF bytes preserved and retrieved unchanged')
    page.get_by_role('button',name='Generate 3D',exact=True).click()
    expect(page.locator('.conformer-result')).to_contain_text('MMFF',timeout=30000)
    expect(page.locator('.viewer canvas')).to_be_visible(timeout=30000)
    assert not page.get_by_role('alert').count()
    page.screenshot(path=str(OUTPUT/'structure-3d.png'),full_page=True)
    checks.append('Actual RDKit force-field generation and rendered WebGL molecule')
    page.get_by_role('button',name='Measurements',exact=True).click()
    csv='\ufefftime,signal\r\n0,1\r\n1,3\r\n2,5\r\n3,7\r\n'
    page.locator('input[type=file][accept=".csv"]').set_input_files({'name':'known-line.csv','mimeType':'text/csv','buffer':csv.encode()})
    page.get_by_role('button',name='Review linear fit',exact=True).click()
    expect(page.get_by_role('dialog')).to_be_visible()
    page.get_by_role('button',name='Run & save fit',exact=True).click()
    expect(page.locator('.fit-numbers')).to_contain_text('2',timeout=30000)
    events=page.request.get(BASE+f'/api/projects/{project}/events',headers=headers).json()['events']
    result=events[-1]['result'];assert result['slope']==2 and result['intercept']==1 and result['r_squared']==1,result
    expect(page.locator('.fit-plot')).to_be_visible()
    with page.expect_download() as d:
        page.get_by_role('button',name='Export CSV',exact=True).click()
    assert Path(d.value.path()).read_bytes()==csv.encode()
    page.screenshot(path=str(OUTPUT/'measurements.png'),full_page=True)
    checks.append('SciPy known line: slope=2, intercept=1, R²=1; original CSV export byte-exact')
    page.get_by_label('CSV measurements').fill('time,signal,signal\n0,1,1\n1,2,2\n2,3,3\n')
    page.get_by_role('button',name='Review linear fit',exact=True).click()
    expect(page.get_by_role('alert')).to_contain_text('Duplicate CSV headings')
    expect(page.get_by_role('dialog')).to_have_count(0)
    page.get_by_label('Dismiss error').click()
    checks.append('Ambiguous duplicate CSV headers rejected before a review receipt')
    page.get_by_role('button',name='Notebook',exact=True).click()
    note='Observed ΔG unknown.\nمشاہدہ: اصل محفوظ ہے۔'
    page.get_by_label('Project note').fill(note)
    page.get_by_role('button',name='Save note',exact=True).click()
    page.get_by_role('button',name='Save to project',exact=True).click()
    expect(page.get_by_role('status').filter(has_text='Original bytes preserved')).to_be_visible()
    page.get_by_role('button',name='Project files',exact=True).click()
    expect(page.locator('.event')).to_have_count(3)
    expect(page.locator('.note-preview')).to_have_text(note)
    page.get_by_role('button',name='Verify stored files',exact=True).click()
    expect(page.locator('.verification')).to_contain_text('match their saved hashes')
    page.screenshot(path=str(OUTPUT/'project-files.png'),full_page=True)
    checks.append('UTF-8 notes, saved history and integrity verification')
    page.get_by_role('button',name='ORCA results',exact=True).click()
    page.get_by_role('button',name='Load synthetic example',exact=True).click()
    expect(page.locator('.orca-properties')).to_contain_text('TerminationnormalOptimizationconverged')
    page.get_by_role('button',name='Inspect source',exact=True).click()
    expect(page.locator('.source-panel')).to_be_visible()
    page.screenshot(path=str(OUTPUT/'orca.png'),full_page=True)
    page.get_by_role('button',name='Notebook',exact=True).click()
    page.get_by_role('button',name='ORCA results',exact=True).click()
    expect(page.locator('.orca-tabs')).to_contain_text('water-synthetic-example.out')
    truncated = b'Program Version 6.1.0\nFINAL SINGLE POINT ENERGY -76.000000000\n'
    page.locator('input[type=file][accept=".out,.log,.txt"]').set_input_files({'name':'truncated-synthetic.out','mimeType':'text/plain','buffer':truncated})
    expect(page.locator('.orca-tabs')).to_contain_text('truncated-synthetic.out')
    expect(page.locator('.comparison')).to_contain_text('Comparison is on hold')
    expect(page.locator('.orca-properties')).to_contain_text(hashlib.sha256(truncated).hexdigest())
    checks.append('ORCA printed facts, source evidence and file SHA; incomplete comparison blocked; retained across tabs')
    page.reload(wait_until='networkidle')
    expect(page.get_by_label('Current project')).to_be_visible()
    page.get_by_label('Current project').select_option(project)
    page.get_by_role('button',name='Project files',exact=True).click()
    expect(page.locator('.event')).to_have_count(3)
    checks.append('Saved project data survives UI reload')
    assert errors==[],errors
    assert outside==[],outside
    checks.append('No uncaught browser errors; no external HTTP requests')
    browser.close()
(OUTPUT/'results.json').write_text(json.dumps({'status':'PASS','project':project,'checks':checks},indent=2))
print(json.dumps({'status':'PASS','project':project,'checks':checks},indent=2))
