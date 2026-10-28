"""Real UI checks for the beginner path, against a source or frozen local service."""
import json, os
from urllib.parse import urlparse
from pathlib import Path
from playwright.sync_api import sync_playwright, expect
OUT=Path(os.environ.get('OPENCHEM_UI_QA_OUT','build/beginner-preview/qa'));OUT.mkdir(parents=True,exist_ok=True)
(OUT/'workflow.json').unlink(missing_ok=True)
checks=[]
with sync_playwright() as p:
 browser=p.chromium.launch(headless=True,executable_path='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome')
 page=browser.new_page(viewport={'width':1440,'height':1100},accept_downloads=True)
 external=[]
 page.on('request',lambda r: external.append(r.url) if urlparse(r.url).scheme in ('http','https') and urlparse(r.url).netloc!=urlparse(os.environ['OPENCHEM_TEST_URL']).netloc else None)
 errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
 page.goto(os.environ['OPENCHEM_TEST_URL'],wait_until='networkidle',timeout=120000)
 expect(page.locator('.formula')).to_have_text('C8H9NO2',timeout=60000)
 expect(page.get_by_role('heading',name='Build a molecule, understand its shape')).to_be_in_viewport()
 page.screenshot(path=str(OUT/'beginner-start.png'),full_page=True)
 assert not page.locator('.assistant-prompt').is_visible()
 page.get_by_label('Start with a known molecule').select_option('Butane')
 decisions=[False,True]
 decide=lambda dialog:dialog.accept() if decisions.pop(0) else dialog.dismiss()
 page.on('dialog',decide)
 with page.expect_event('dialog'):
  page.get_by_role('button',name='Load example',exact=True).click()
 expect(page.get_by_role('button',name='Load example',exact=True)).to_be_enabled()
 expect(page.locator('.formula')).to_have_text('C8H9NO2')
 with page.expect_event('dialog'):
  page.get_by_role('button',name='Load example',exact=True).click()
 expect(page.locator('.formula')).to_have_text('C4H10')
 page.get_by_role('button',name='Compare 5 starting shapes',exact=True).click()
 expect(page.locator('.shape-results tbody tr')).to_have_count(5,timeout=90000)
 expect(page.locator('.sample-viewer canvas')).to_be_visible(timeout=30000)
 expect(page.locator('.geometry-status')).to_contain_text('Geometry: current')
 energies=[float(x) for x in page.locator('.shape-results tbody td:nth-child(2)').all_text_contents()]
 assert energies==sorted(energies) and energies[0]==0
 page.get_by_role('button',name='Inspect sample 5',exact=True).click()
 expect(page.locator('.shape-results tbody tr').nth(4).get_by_role('button')).to_have_attribute('aria-pressed','true')
 with page.expect_download() as dl:page.get_by_role('button',name='Export comparison report',exact=True).click()
 report=json.loads(Path(dl.value.path()).read_text());assert len(report['samples'])==5 and report['formula']=='C4H10'
 assert all(x['converged'] and x['rdkit_version'] and x['sdf'] for x in report['samples'])
 with page.expect_download() as dl:page.get_by_role('button',name='Export selected geometry',exact=True).click()
 selected=Path(dl.value.path()).read_text();assert selected==report['samples'][4]['sdf']
 checks.append('Named molecule replacement confirmed/cancelled; real RDKit five-sample ranking; selected SDF and reproducible report match')
 page.screenshot(path=str(OUT/'butane-comparison.png'),full_page=True)
 page.get_by_role('button',name='Prepare calculation input',exact=True).click()
 expect(page.get_by_label('Calculation',exact=True)).to_be_visible()
 page.get_by_role('button',name='Check input →',exact=True).click()
 expect(page.locator('.prep-preview pre')).to_contain_text('* xyz 0 1')
 preview=page.locator('.prep-preview pre').inner_text()
 page.get_by_role('button',name='Save checked ORCA input',exact=True).click()
 expect(page.locator('.prep-downloads')).to_be_visible()
 with page.expect_download() as dl:page.get_by_role('button',name='Download ORCA input',exact=True).click()
 assert Path(dl.value.path()).read_text()==preview
 checks.append('Chosen sample handed to checked/saved ORCA input with exact downloadable bytes')
 page.get_by_role('button',name='Change molecule or geometry',exact=True).click()
 page.get_by_role('button',name='2D editor',exact=True).click()
 page.evaluate("async()=>window.__openchemEditor.setMolecule('O')")
 expect(page.locator('.formula')).to_have_text('H2O')
 expect(page.get_by_role('button',name='Export comparison report',exact=True)).to_be_disabled()
 expect(page.get_by_role('button',name='Export selected geometry',exact=True)).to_be_disabled()
 expect(page.get_by_role('button',name='Export generated SDF ↗',exact=True)).to_be_disabled()
 page.get_by_role('button',name='ORCA input',exact=True).click()
 page.get_by_role('button',name='Check input →',exact=True).click()
 expect(page.locator('.orca-prep-page [role=alert]')).to_contain_text('drawing changed')
 page.get_by_role('button',name='Change molecule or geometry',exact=True).click()
 page.get_by_role('button',name='Compare 5 starting shapes',exact=True).click()
 page.evaluate("async()=>window.__openchemEditor.setMolecule('CCO')")
 expect(page.locator('.banner.error').filter(has_text='drawing or project changed')).to_be_visible(timeout=90000)
 expect(page.locator('.shape-results')).to_have_count(0)
 checks.append('Drawing changes invalidate guided and inspector exports/input; in-flight sampling discarded after edit')
 page.get_by_role('button',name='Compare 5 starting shapes',exact=True).click()
 expect(page.locator('.shape-results tbody tr')).to_have_count(5,timeout=90000)
 page.remove_listener('dialog',decide)
 page.on('dialog',lambda dialog:dialog.accept('guided-other'))
 with page.expect_event('dialog'):
  page.get_by_role('button',name='New project',exact=True).click()
 expect(page.get_by_label('Current project')).to_have_value('guided-other')
 expect(page.locator('.shape-results')).to_have_count(0)
 expect(page.get_by_role('button',name='Export selected geometry',exact=True)).to_be_disabled()
 checks.append('Switching projects clears sampling and prevents previous-project geometry export')
 page.get_by_label('Start with a known molecule').focus()
 page.keyboard.press('Tab');expect(page.get_by_role('button',name='Load example',exact=True)).to_be_focused()
 page.set_viewport_size({'width':760,'height':1100})
 page.screenshot(path=str(OUT/'beginner-760.png'),full_page=True)
 assert page.locator('.beginner-workflow').bounding_box()['width']<=760
 assert page.locator('.beginner-steps>section').nth(1).bounding_box()['y']>page.locator('.beginner-steps>section').nth(0).bounding_box()['y']
 page.get_by_role('button',name='Hide guided steps',exact=True).click()
 expect(page.locator('.beginner-workflow')).to_have_count(0)
 checks.append('Keyboard starter controls, stacked narrow layout and optional guide mode')
 assert not errors,errors
 assert not external,external
 (OUT/'workflow.json').write_text(json.dumps({'status':'PASS','checks':checks,'console_errors':errors,'external_requests':external,'energies':energies},indent=2)+'\n')
 browser.close()
print(json.dumps({'status':'PASS','checks':checks}))
