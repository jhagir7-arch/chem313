"""Visible production-UI proof for ORCA input preparation. Set OPENCHEM_TEST_URL."""
from pathlib import Path
import hashlib
import json
import os
import time

from playwright.sync_api import expect, sync_playwright

BASE = os.environ.get("OPENCHEM_TEST_URL", "http://127.0.0.1:8788")
OUTPUT = Path("build/orca-preparation-ui-qa")
OUTPUT.mkdir(parents=True, exist_ok=True)
project = "orca-ui-" + str(int(time.time()))
checks = []

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1440, "height": 1000}, accept_downloads=True)
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto(BASE, wait_until="networkidle", timeout=120000)
    page.once("dialog", lambda dialog: dialog.accept(project))
    page.get_by_role("button", name="New project", exact=True).click()
    page.get_by_role("button", name="ORCA input", exact=True).click()
    expect(page.get_by_text("No 3D geometry yet")).to_be_visible()
    assert page.get_by_role("button", name="Check input").is_disabled()
    checks.append("Empty preparation gate is visible and disabled")

    page.get_by_role("button", name="Structures", exact=True).click()
    page.locator("#smiles").fill("CCO")
    page.get_by_role("button", name="Load", exact=True).click()
    page.get_by_role("button", name="Generate 3D", exact=True).click()
    expect(page.locator(".conformer-result")).to_be_visible(timeout=30000)
    page.get_by_role("button", name="ORCA input", exact=True).click()
    page.get_by_label("ORCA charge").fill("1")
    page.get_by_label("ORCA multiplicity").fill("2")
    page.get_by_role("button", name="Check input").click()
    expect(page.locator("pre")).to_contain_text("* xyz 1 2", timeout=30000)
    expect(page.locator("pre")).to_contain_text("! B3LYP def2-SVP Opt")
    checks.append("Generated 3D geometry renders exact charge, spin, method and job input")

    page.get_by_role("button", name="Structures", exact=True).click()
    page.evaluate("async()=>window.__openchemEditor.setMolecule('CC')")
    page.get_by_role("button", name="ORCA input", exact=True).click()
    page.get_by_role("button", name="Check input").click()
    expect(page.get_by_role("alert")).to_contain_text("drawing changed")
    checks.append("Edited drawing blocks use of a stale conformer")
    page.get_by_role("button", name="Structures", exact=True).click()
    generate = page.get_by_role("button", name="Generate 3D", exact=True)
    conformer = page.locator(".conformer-result")
    generate.click()
    expect(conformer).to_be_hidden(timeout=30000)
    expect(conformer).to_be_visible(timeout=30000)
    page.get_by_role("button", name="ORCA input", exact=True).click()
    page.get_by_label("ORCA charge").fill("0")
    page.get_by_label("ORCA multiplicity").fill("1")
    page.get_by_role("button", name="Check input").click()
    expect(page.locator("pre")).to_contain_text("* xyz 0 1", timeout=30000)
    page.get_by_role("button", name="Save checked ORCA input", exact=True).click()
    expect(page.get_by_role("heading", name="Download prepared files")).to_be_visible(timeout=30000)
    token = page.request.get(BASE + "/api/session").json()["session_token"]
    headers = {"X-HypothesisLab-Session": token}
    events = page.request.get(BASE + f"/api/projects/{project}/events", headers=headers).json()["events"]
    event = events[-1]
    artifacts = event["artifacts"]
    assert [a["relative_path"].rsplit(".", 1)[1] for a in artifacts] == ["sdf", "inp", "json"]
    for name in ("source SDF", "ORCA input", "report"):
        with page.expect_download() as download:
            page.get_by_role("button", name=f"Download {name}", exact=True).click()
        payload = Path(download.value.path()).read_bytes()
        artifact = next(a for a in artifacts if (name == "source SDF" and a["relative_path"].endswith(".sdf")) or (name == "ORCA input" and a["relative_path"].endswith(".inp")) or (name == "report" and a["relative_path"].endswith(".json")))
        assert hashlib.sha256(payload).hexdigest() == artifact["sha256"]
    page.screenshot(path=str(OUTPUT / "orca-preparation.png"), full_page=True)
    assert not errors, errors
    checks.append("Apply saved and direct download controls retrieve immutable SDF, INP and report")
    browser.close()

(OUTPUT / "results.json").write_text(json.dumps({"status": "PASS", "project": project, "checks": checks}, indent=2))
print(json.dumps({"status": "PASS", "project": project, "checks": checks}, indent=2))
