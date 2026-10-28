"""Real Qwen + RDKit browser flow, download, keyboard and narrow viewport checks."""
import json,os
from pathlib import Path
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright,expect
out=Path(os.environ.get('OPENCHEM_UI_QA_OUT','build/study-agent-preview/browser-qa'));out.mkdir(parents=True,exist_ok=True)
with sync_playwright() as p:
 browser=p.chromium.launch(headless=True,executable_path='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome')
 page=browser.new_page(viewport={'width':1440,'height':1100},accept_downloads=True)
 errors=[];external=[]
 page.on('pageerror',lambda e:errors.append(str(e)))
 page.on('request',lambda r:external.append(r.url) if urlparse(r.url).scheme in ('http','https') and urlparse(r.url).netloc!=urlparse(os.environ['OPENCHEM_TEST_URL']).netloc else None)
 page.goto(os.environ['OPENCHEM_TEST_URL'],wait_until='networkidle',timeout=120000)
 page.get_by_role('button',name='Molecule study',exact=True).click()
 expect(page.get_by_label('What would you like to compare?')).to_be_visible(timeout=60000)
 page.get_by_label('What would you like to compare?').focus()
 assert page.evaluate('document.activeElement.id')=='study-question'
 page.keyboard.press('Tab');assert page.evaluate('document.activeElement.tagName')=='BUTTON'
 page.screenshot(path=str(out/'question-screen.png'),full_page=True)
 # Guided controls must create the selected question, not a canned example.
 page.get_by_role('combobox',name='Molecule',exact=True).select_option('ethanol')
 page.get_by_role('combobox',name='Starting shapes',exact=True).select_option('4')
 page.get_by_role('button',name='Plan this comparison',exact=True).click()
 expect(page.get_by_label('What would you like to compare?')).to_have_value('Compare 4 shapes of ethanol')
 expect(page.get_by_role('button',name='Run study',exact=True)).to_be_enabled(timeout=120000)
 expect(page.locator('.study-plan-record')).to_contain_text('C2H6O')
 page.get_by_role('button',name='Run study',exact=True).click()
 expect(page.locator('.study-live')).to_contain_text('Study complete.',timeout=60000)
 expect(page.locator('.study-interpretation')).to_contain_text('lowest-scoring unique shape')
 with page.expect_download() as readable:page.get_by_role('button',name='Save readable report',exact=True).click()
 report=Path(readable.value.path()).read_text()
 for content in ['Question: Compare 4 shapes of ethanol','Completed samples: 4 of 4','does not prove the true most stable shape','Qwen/Qwen3.5-2B-Base','Status: complete']:assert content in report,content
 page.set_viewport_size({'width':760,'height':1100})
 assert page.locator('.study-guided').bounding_box()['width']<=760
 assert page.get_by_role('button',name='Plan this comparison',exact=True).bounding_box()['width']>44
 page.screenshot(path=str(out/'guided-results.png'),full_page=True)
 page.set_viewport_size({'width':1440,'height':1100})
 script=Path('scripts/native_study_agent_workflow.js').read_text()
 result=json.loads(page.evaluate('async()=>{'+script+'}'))
 (out/'workflow.json').write_text(json.dumps(result,indent=2))
 assert result['status']=='PASS',result
 page.get_by_role('button',name='Compare four shapes of ethanol',exact=True).click()
 page.get_by_role('button',name='Prepare study',exact=True).click()
 expect(page.get_by_role('button',name='Run study',exact=True)).to_be_enabled(timeout=120000)
 page.get_by_role('button',name='Run study',exact=True).click()
 expect(page.locator('.study-live')).to_contain_text('Study complete.',timeout=60000)
 with page.expect_download() as dl:page.get_by_role('button',name='Export JSON',exact=True).click()
 recipe=json.loads(Path(dl.value.path()).read_text())
 assert recipe['schema']=='openchem.molecule-study.v1' and recipe['result']['completed']==4 and recipe['plan']['canonical_smiles']=='CCO'
 assert recipe['plan']['provenance']['adapter_sha256'] is None
 expect(page.locator('.study-selection canvas')).to_be_visible(timeout=30000)
 page.get_by_text('Text alternative: atoms and 3D coordinates (ångström)',exact=True).click()
 assert page.locator('.study-coordinates tbody tr').count()==9
 page.screenshot(path=str(out/'ethanol-results.png'),full_page=True)
 page.set_viewport_size({'width':760,'height':1100})
 assert page.locator('.study-agent').bounding_box()['width']<=760
 page.screenshot(path=str(out/'study-760.png'),full_page=True)
 page.get_by_label('What would you like to compare?').fill('Compare shapes')
 assert page.locator('.study-results').count()==0
 assert page.get_by_role('button',name='Run study',exact=True).count()==0
 assert not errors,errors
 assert not external,external
 result.update(console_errors=errors,external_requests=external,extra_checks=['Guided ethanol/four-shape selection uses real Qwen/RDKit and correct structure','Readable report downloaded with exact question/count and honest score limits','Guided controls reflow at760px','Keyboard question/example controls','Actual JSON download preserves exact backend recipe and public-model provenance','Selected structure has atom-coordinate text equivalent','760px study reflow','Changed question invalidates prior plan/results'])
 (out/'workflow.json').write_text(json.dumps(result,indent=2))
 browser.close()
print(json.dumps(result))
