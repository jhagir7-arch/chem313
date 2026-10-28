"""Real compiled-service preparation/connection UI QA; never simulates ORCA."""
import hashlib,json,os
from pathlib import Path
from playwright.sync_api import sync_playwright,expect
out=Path(os.environ.get('OPENCHEM_UI_QA_OUT','build/study-agent-preview/quick-calculation-qa'));out.mkdir(parents=True,exist_ok=True)
url=os.environ['OPENCHEM_TEST_URL'].rstrip('/')
with sync_playwright() as p:
 browser=p.chromium.launch(headless=True,executable_path='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome')
 page=browser.new_page(viewport={'width':1440,'height':1100},accept_downloads=True)
 errors=[];external=[]
 page.on('pageerror',lambda e:errors.append(str(e)))
 page.on('request',lambda r:external.append(r.url) if r.url.startswith(('http:','https:')) and not r.url.startswith(url+'/') else None)
 page.goto(url,wait_until='networkidle',timeout=120000)
 root=page.locator('.quick-calculation')
 expect(root).to_be_visible()
 expect(root.get_by_role('combobox',name='Molecule',exact=True)).to_have_value('water')
 root.get_by_role('combobox',name='Molecule',exact=True).focus()
 assert page.evaluate('document.activeElement.tagName')=='SELECT'
 page.keyboard.press('Tab')
 assert page.evaluate('document.activeElement.tagName')=='SELECT'
 result=json.loads(page.evaluate('async()=>{'+Path('scripts/native_quick_calculation_workflow.js').read_text()+'}'))
 assert result['status']=='PASS',result
 if result['orca_calculation']=='NOT_RUN':
  expect(root.get_by_role('button',name='Save and run reviewed calculation',exact=True)).to_be_disabled()
  root.get_by_label('ORCA executable path').fill('/not/installed/orca')
  root.get_by_role('button',name='Connect ORCA',exact=True).click()
  expect(root.get_by_role('alert')).to_be_visible()
  expect(root.get_by_role('button',name='Save and run reviewed calculation',exact=True)).to_be_disabled()
  root.get_by_label('ORCA executable path').fill('')
  result['extra_checks']=['Invalid executable path rejected; run remains disabled','Keyboard reaches molecule and calculation selects']
 else:
  page.get_by_role('button',name='Calculate',exact=True).click()
  with page.expect_download() as dl:root.get_by_role('button',name='Save readable report',exact=True).click()
  report=Path(dl.value.path()).read_text()
  assert 'Output SHA-256: '+result['output']['sha256'] in report
  with page.expect_download() as dl:root.get_by_role('button',name='Export saved output',exact=True).click()
  assert hashlib.sha256(Path(dl.value.path()).read_bytes()).hexdigest()==result['output']['sha256']
  result['extra_checks']=['Actual readable report and saved output downloads retain provenanced output hash']
 lesson=root.locator('.representation-lesson')
 with page.expect_download() as dl:lesson.get_by_role('button',name='Download complete geometry as XYZ text',exact=True).click()
 xyz=Path(dl.value.path()).read_text().splitlines()
 assert int(xyz[0])==3 and len(xyz[2:])==3
 result['extra_checks'].append('Complete water XYZ download has all 3 coordinate rows')
 qchem=root.locator('.qchem-preparation')
 with page.expect_download() as dl:qchem.get_by_role('button',name='Download Q-Chem input',exact=True).click()
 qchem_input=Path(dl.value.path()).read_text()
 assert '$molecule\n0 1\n' in qchem_input and '$rem\nJOBTYPE sp\nMETHOD hf\nBASIS def2-SVP\n$end\n' in qchem_input
 assert len([line for line in qchem_input.splitlines() if line[:1].isalpha() and len(line.split())==4])==3
 result['extra_checks'].append('Downloaded water Q-Chem input retains the complete 3-coordinate HF/def2-SVP text')
 page.set_viewport_size({'width':760,'height':1100})
 assert root.bounding_box()['width']<=760
 assert page.evaluate('document.documentElement.scrollWidth<=window.innerWidth'), 'Horizontal page overflow'
 root.locator('summary').first.click()
 expect(root.locator('.quick-geometry > details > pre')).to_be_visible()
 assert root.locator('.viewer-wrap').bounding_box()['height']==310
 page.evaluate("document.querySelector('.workspace-scroll').scrollTop=0")
 page.screenshot(path=str(out/'calculate-760.png'))
 page.set_viewport_size({'width':1440,'height':1100})
 page.evaluate("document.querySelector('.workspace-scroll').scrollTop=0")
 page.screenshot(path=str(out/'calculate-desktop.png'))
 assert not errors,errors
 assert not external,external
 result.update(console_errors=errors,external_requests=external)
 (out/'browser-workflow.json').write_text(json.dumps(result,indent=2))
 browser.close()
print(json.dumps(result,indent=2))
