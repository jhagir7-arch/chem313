"""Exercise installed production UI with an explicitly simulated Q-Chem process.

Requires the isolated native QA app, OPENCHEM_TEST_URL, and a mode-switchable
simulated installation. No result from this check is a scientific calculation.
"""
import hashlib
import json
import os
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import expect, sync_playwright

URL = os.environ['OPENCHEM_TEST_URL'].rstrip('/')
OUT = Path('build/study-agent-preview/qchem-qa/execution')
MODE = OUT / 'simulated-qchem/mode'
checks = []
errors, external = [], []

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, executable_path='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome')
    page = browser.new_page(viewport={'width': 1440, 'height': 1100}, accept_downloads=True)
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.on('request', lambda req: external.append(req.url) if urlparse(req.url).scheme in {'http', 'https'} and urlparse(req.url).netloc != urlparse(URL).netloc else None)

    def enter_run():
        page.goto(URL, wait_until='networkidle', timeout=120000)
        root = page.locator('.qchem-workflow')
        build = root.get_by_role('button', name='Build starting structure', exact=True)
        build.focus()
        page.keyboard.press('Enter')
        expect(root.get_by_label('How many atoms, including hydrogens?')).to_be_visible(timeout=120000)
        root.get_by_label('How many atoms, including hydrogens?').fill('3')
        root.get_by_role('button', name='Check atom count', exact=True).click()
        root.get_by_label('What can the coordinate table tell you?').select_option('positions')
        root.get_by_role('button', name='Continue to settings', exact=True).click()
        root.get_by_label('Will this single-point job move the atoms?').select_option('fixed')
        root.get_by_role('button', name='Review Q-Chem input', exact=True).click()
        root.get_by_label('I understand this prepares an input file; Q-Chem has not run.').check()
        root.get_by_role('button', name='Continue to calculation', exact=True).click()
        expect(root.get_by_test_id('qchem-engine-status')).to_contain_text('Installation connected')
        return root.locator('.qchem-run')

    run = enter_run()
    expect(run.locator('.qchem-state')).to_contain_text('SUCCEEDED')
    expect(run.get_by_test_id('qchem-energy')).to_contain_text('-75.123')
    checks.append('Server-persisted native QA result restores in installed production UI')
    with page.expect_download() as output:
        run.get_by_role('button', name='Download engine output', exact=True).click()
    raw = Path(output.value.path()).read_bytes()
    assert b'SIMULATED QA PROCESS: NOT A Q-CHEM CALCULATION' in raw
    with page.expect_download() as record:
        run.get_by_role('button', name='Download result record', exact=True).click()
    saved = json.loads(Path(record.value.path()).read_text())
    assert saved['output_sha256'] == hashlib.sha256(raw).hexdigest()
    with page.expect_download() as inp:
        run.get_by_role('button', name='Download executed input', exact=True).click()
    assert saved['input_sha256'] == hashlib.sha256(Path(inp.value.path()).read_bytes()).hexdigest()
    checks.append('Executed input, full output and result JSON downloads match recorded hashes')

    def coach_failure(route):
        route.fulfill(status=422, content_type='application/json', body=json.dumps({'detail': 'Simulated model failure'}))
    page.route('**/api/qchem/results/coach', coach_failure)
    run.get_by_role('button', name='What does this energy mean?', exact=True).click()
    expect(run.locator('.qchem-coach [role=alert]')).to_contain_text('recorded output and explanations remain available')
    expect(run.get_by_test_id('qchem-energy')).to_be_visible()
    page.unroute('**/api/qchem/results/coach', coach_failure)
    checks.append('Explicitly simulated Qwen failure leaves the saved result and downloads usable')

    for width in (1440, 760, 360):
        page.set_viewport_size({'width': width, 'height': 1100})
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), f'Overflow at {width}'
        page.screenshot(path=str(OUT / f'execution-{width}.png'), full_page=True)
    checks.append('Run/results layout has no page overflow at 1440, 760 and 360 pixels')
    page.set_viewport_size({'width': 1440, 'height': 1100})

    def launch(mode):
        previous = run.locator('.qchem-state').text_content() if run.locator('.qchem-state').count() else None
        MODE.write_text(mode)
        run.get_by_label('I reviewed this molecule and settings and want to run this local calculation.').check()
        run.get_by_role('button', name='Run Q-Chem calculation', exact=True).click()
        if previous is not None:
            expect(run.locator('.qchem-state')).not_to_have_text(previous, timeout=15000)

    launch('license')
    expect(run.locator('.qchem-state')).to_contain_text('FAILED', timeout=30000)
    expect(run).to_contain_text('license failure')
    expect(run.get_by_test_id('qchem-energy')).to_have_count(0)
    checks.append('Simulated license checkout failure cannot display a successful energy')
    launch('nonconverged')
    expect(run.locator('.qchem-state')).to_contain_text('FAILED', timeout=30000)
    expect(run).to_contain_text('convergence marker was not found')
    expect(run.get_by_test_id('qchem-energy')).to_have_count(0)
    checks.append('Simulated non-converged output with an energy line remains a failed job')
    # An old history response must never replace a newly launched job.
    pending = []
    def hold_history(route):
        pending.append(route)
    page.route('**/api/qchem/jobs?project=*', hold_history)
    run = enter_run()
    assert len(pending) == 1
    launch('slow')
    expect(run.get_by_role('button', name='Stop calculation', exact=True)).to_be_visible(timeout=15000)
    expect(run.locator('.qchem-state')).to_contain_text('RUNNING', timeout=15000)
    pending[0].fulfill(status=200, content_type='application/json', body=json.dumps({'jobs': [saved]}))
    page.wait_for_timeout(300)
    expect(run.locator('.qchem-state')).to_contain_text('RUNNING')
    expect(run.get_by_test_id('qchem-energy')).to_have_count(0)
    page.unroute('**/api/qchem/jobs?project=*', hold_history)
    checks.append('Explicitly delayed old history cannot replace a newly launched calculation or display its energy')
    expect(run.get_by_role('button', name='Run Q-Chem calculation', exact=True)).to_be_disabled()
    run.get_by_role('button', name='Stop calculation', exact=True).click()
    expect(run.locator('.qchem-state')).to_contain_text('CANCELLED', timeout=30000)
    expect(run.get_by_test_id('qchem-energy')).to_have_count(0)
    checks.append('Native runtime accepts UI cancellation; active job blocks another launch')
    run = enter_run()
    expect(run.locator('.qchem-state')).to_contain_text('CANCELLED')
    checks.append('Reload restores the terminal cancellation without replaying the process')
    assert not errors, errors
    assert not external, external
    MODE.write_text('success')
    evidence = {'status': 'PASS', 'target': URL, 'engine_test': 'SIMULATED_PROCESS_ONLY', 'real_qchem_calculation': 'NOT_RUN_NO_LICENSED_INSTALLATION', 'checks': checks, 'console_errors': errors, 'external_requests': external}
    (OUT / 'browser-execution.json').write_text(json.dumps(evidence, indent=2) + '\n')
    browser.close()
print(json.dumps(evidence, indent=2))
