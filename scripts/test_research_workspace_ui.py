"""Exercise the research workspace against the real local core and workers."""
import json, math, os, time
from pathlib import Path
from playwright.sync_api import sync_playwright, expect
BASE=os.environ['OPENCHEM_TEST_URL']
OUT=Path(os.environ.get('OPENCHEM_UI_QA_OUT','build/desktop-ui-refinement-qa'));OUT.mkdir(parents=True,exist_ok=True)
checks=[]
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True,**({'executable_path':os.environ['OPENCHEM_BROWSER_EXECUTABLE']} if os.environ.get('OPENCHEM_BROWSER_EXECUTABLE') else {}))
    page=browser.new_page(viewport={'width':1440,'height':940},accept_downloads=True)
    errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
    page.goto(BASE,wait_until='networkidle',timeout=120000)
    expect(page.locator('.formula')).to_have_text('C8H9NO2',timeout=60000)
    page.screenshot(path=str(OUT/'structure-1440.png'),full_page=True)
    assert not page.locator('.assistant-prompt').is_visible()
    assert page.locator('.editor-stage').bounding_box()['width']>1100
    page.get_by_role('button',name='Show Qwen',exact=True).click()
    assert page.locator('.assistant-prompt').is_visible()
    assert page.locator('.editor-stage').bounding_box()['width']>450
    assert page.locator('.page-heading h1').evaluate('e=>parseInt(getComputedStyle(e).fontSize)')<24
    page.get_by_role('button',name='Water · HF single point',exact=True).click()
    expect(page.locator('.assistant-prompt textarea')).to_have_value('Build water O, charge 0, multiplicity 1, HF def2-SVP single point calculation.')
    page.screenshot(path=str(OUT/'qwen-inspector.png'),full_page=True)
    page.get_by_role('button',name='Properties',exact=True).click()
    checks.append('Document workspace with large canvas; Qwen templates in optional inspector')
    page.locator('#smiles').fill('O');page.get_by_role('button',name='Load',exact=True).click()
    expect(page.locator('.formula')).to_have_text('H2O')
    page.get_by_role('button',name='Generate 3D',exact=True).click()
    expect(page.locator('.conformer-result').first).to_be_visible(timeout=30000)
    page.wait_for_timeout(500)  # Delayed drawing notifications must preserve fresh geometry.
    expect(page.locator('.geometry-status')).to_contain_text('Geometry: current')
    page.get_by_role('button',name='Prepare PySCF RHF →',exact=True).click()
    expect(page.get_by_label('Allowed operation')).to_have_value('pyscf.rhf_singlepoint')
    fields=page.locator('.input-fields input')
    assert json.loads(fields.nth(0).input_value())==[8,1,1]
    page.get_by_role('button',name='Preview this run',exact=True).click()
    page.get_by_role('button',name='Apply approved run',exact=True).click()
    page.get_by_role('button',name='Notebook',exact=True).click()
    page.get_by_role('button',name='Scientific tools',exact=True).click()
    expect(page.locator('.science-state')).to_have_text('SUCCEEDED',timeout=130000)
    page.locator('.science-job summary',has_text='Result and scientific limits').click()
    result=json.loads(page.locator('.science-job .science-result').first.inner_text())
    energy=result['output'].get('energy_hartree')
    assert energy is not None and math.isfinite(energy) and -76<energy<-73,result
    checks.append('Drawing→RDKit water geometry→real PySCF RHF energy; running view persists')
    page.screenshot(path=str(OUT/'water-energy.png'),full_page=True)
    page.get_by_role('button',name='Research scripts',exact=True).click()
    source=page.get_by_label('Recipe JSON source').input_value()
    page.get_by_role('button',name='Review all steps',exact=True).click()
    expect(page.get_by_role('button',name='Run reviewed recipe')).to_be_enabled()
    page.get_by_label('Recipe JSON source').fill(source+' ')
    expect(page.get_by_role('button',name='Run reviewed recipe')).to_have_count(0)
    page.get_by_role('button',name='Review all steps',exact=True).click()
    page.get_by_role('button',name='Run reviewed recipe',exact=True).click()
    expect(page.locator('.recipe-results tbody tr').nth(1).locator('td').nth(2)).to_have_text('SUCCEEDED',timeout=130000)
    for summary in page.locator('.recipe-results summary').all():summary.click()
    results=[json.loads(text) for text in page.locator('.recipe-results .science-result').all_text_contents()]
    assert results[0]['output']['value']==1,results
    assert results[1]['output']['mean']==3,results
    checks.append('Recipe source edit invalidates receipts; real Pint and NumPy sequential results')
    with page.expect_download() as dl:page.get_by_role('button',name='Export source ↗',exact=True).click()
    assert Path(dl.value.path()).read_text()==source+' '
    page.screenshot(path=str(OUT/'scripts.png'),full_page=True)
    page.get_by_role('button',name='Structures',exact=True).click()
    page.get_by_role('button',name='ORCA input',exact=True).click()
    page.get_by_role('button',name='Check input →',exact=True).click()
    expect(page.locator('.prep-preview pre')).to_contain_text('* xyz 0 1')
    page.get_by_role('button',name='Save checked ORCA input',exact=True).click()
    expect(page.locator('.orca-run')).to_be_visible()
    page.get_by_role('button',name='Notebook',exact=True).click()
    page.get_by_role('button',name='ORCA input',exact=True).click()
    expect(page.locator('.orca-run')).to_be_visible()
    checks.append('Saved ORCA input/run controls persist across navigation')
    page.get_by_role('button',name='Structures',exact=True).click()
    page.evaluate("async()=>window.__openchemEditor.setMolecule('CCO')")
    expect(page.locator('.formula')).to_have_text('C2H6O')
    expect(page.get_by_role('button',name='Prepare PySCF RHF →')).to_be_disabled()
    expect(page.locator('.geometry-status')).to_contain_text('drawing changed')
    checks.append('Drawing changes refresh properties and invalidate generated geometry')
    page.set_viewport_size({'width':1280,'height':850})
    page.get_by_role('button',name='Show Qwen',exact=True).click()
    assert page.locator('.assistant-slot').bounding_box()['x']>page.locator('.drawing-panel').bounding_box()['x']+page.locator('.drawing-panel').bounding_box()['width']
    assert page.locator('.drawing-panel').bounding_box()['width']>400
    checks.append('Qwen shares the property inspector at 1280px; no competing column')
    page.get_by_role('button',name='Properties',exact=True).click()
    page.get_by_role('button',name='2D editor',exact=True).click()
    original_mol=page.evaluate("async()=>window.__openchemEditor.getMolfile('v3000')")
    page.set_viewport_size({'width':850,'height':650})
    page.wait_for_timeout(250)  # Allow the 150 ms viewport-fit debounce to settle.
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
    assert page.locator('.drawing-panel').bounding_box()['width']>530
    assert page.locator('.workspace-footer').bounding_box()['y']<650
    page.get_by_role('button',name='Fit structure',exact=True).click()
    assert page.locator('.drawing-panel').bounding_box()['width']>800
    assert page.evaluate('()=>window.__openchemEditor.editor.zoom()')>=0.5
    assert page.evaluate("async()=>window.__openchemEditor.getMolfile('v3000')")==original_mol
    checks.append('850px layout gives editor full width; Fit structure preserves exact MOL source')
    page.screenshot(path=str(OUT/'structure-850.png'),full_page=True)
    page.set_viewport_size({'width':1440,'height':940})
    page.get_by_role('button',name='Help',exact=True).click()
    expect(page.locator('.guide-workflow')).to_contain_text('Molecule to calculation')
    assert not errors,errors
    browser.close()
(OUT/'result.json').write_text(json.dumps({'status':'PASS','checks':checks,'pyscf_result':result,'recipes':results},indent=2)+'\n')
print(json.dumps({'status':'PASS','checks':checks}))
