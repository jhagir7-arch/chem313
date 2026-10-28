"""Production ORCA import/review UI smoke and actual CSV/JSON downloads."""
import hashlib,json,os
from pathlib import Path
from playwright.sync_api import sync_playwright,expect
out=Path('build/study-agent-preview/orca-review-qa')
out.mkdir(parents=True,exist_ok=True)
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True,executable_path='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome')
    page=browser.new_page(viewport={'width':1440,'height':1100},accept_downloads=True)
    errors=[];external=[]
    page.on('pageerror',lambda e:errors.append(str(e)))
    page.on('request',lambda r:external.append(r.url) if r.url.startswith(('http:','https:')) and not r.url.startswith(os.environ['OPENCHEM_TEST_URL'].rstrip('/')) else None)
    page.goto(os.environ['OPENCHEM_TEST_URL'],wait_until='networkidle',timeout=120000)
    expect(page.get_by_role('button',name='ORCA results',exact=True)).to_be_visible()
    result=json.loads(page.evaluate('async()=>{'+Path('scripts/native_orca_review_workflow.js').read_text()+'}'))
    assert result['status']=='PASS',result
    with page.expect_download() as dl:
        page.get_by_role('button',name='Export all extracted facts as CSV',exact=True).click()
    csv=Path(dl.value.path()).read_text()
    for value in ['review-a.out','review-b.log','unknown-scf.out','truncated.out','multi-job.out','water-synthetic-example.out',result['input_sha256']]:
        assert value in csv,value
    with page.expect_download() as dl:
        page.get_by_role('button',name='Export extracted facts',exact=True).click()
    facts=json.loads(Path(dl.value.path()).read_text())
    assert facts['source']['synthetic'] is True
    assert 'lines' not in facts and 'Static extraction only' in facts['limits']
    # Use the real browser file-input API to import a repository fixture as well.
    opener=page.get_by_role('button',name='Open ORCA output',exact=True)
    opener.focus()
    with page.expect_file_chooser() as chooser:
        page.keyboard.press('Enter')
    chooser.value.set_files('frontend/test/orca/fixtures/synthetic-good.out')
    expect(page.locator('.orca-tabs button').last).to_have_text('synthetic-good.out')
    expect(page.get_by_test_id('orca-review-missing')).to_contain_text('SCF outcome')
    source=Path('frontend/test/orca/fixtures/synthetic-good.out').read_bytes()
    expect(page.locator('.source-hash')).to_contain_text(hashlib.sha256(source).hexdigest())
    page.get_by_role('button',name='Inspect original source',exact=True).focus()
    page.keyboard.press('Enter')
    expect(page.locator('#orca-source-panel h2')).to_be_focused()
    page.set_viewport_size({'width':760,'height':1100})
    assert page.locator('.orca-workspace').bounding_box()['width']<=760
    assert page.locator('.orca-review').bounding_box()['width']<=760
    page.get_by_test_id('orca-review-summary').scroll_into_view_if_needed()
    page.screenshot(path=str(out/'review-760.png'))
    assert not errors,errors
    assert not external,external
    result.update(console_errors=errors,external_requests=external,extra_checks=['Actual CSV download retains every imported record, unresolved records and input hash','Actual JSON export distinguishes synthetic source and extraction limits','Real browser file-input imports fixture and preserves exact byte hash','Keyboard Enter opens and focuses original source','Review panel reflows at 760px'])
    (out/'browser-workflow.json').write_text(json.dumps(result,indent=2))
    browser.close()
print(json.dumps(result))

