"""Browser QA for the installed OpenChem Q-Chem preparation lesson.

Set OPENCHEM_TEST_URL to the running compiled engine URL before running this
with .venv-ui/bin/python. The only coaching request in this check is a routed,
simulated 422; real local-Qwen exercise belongs to the native worker check.
"""
import hashlib
import json
import os
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import expect, sync_playwright


OUT = Path(os.environ.get("OPENCHEM_UI_QA_OUT", "build/study-agent-preview/qchem-qa"))
OUT.mkdir(parents=True, exist_ok=True)
URL = os.environ["OPENCHEM_TEST_URL"].rstrip("/")
CHROME = os.environ.get("OPENCHEM_BROWSER_EXECUTABLE", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")


def external_request(url: str) -> bool:
    parsed, target = urlparse(url), urlparse(URL)
    return parsed.scheme in {"http", "https"} and parsed.netloc != target.netloc


def assert_no_horizontal_page_overflow(page) -> None:
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth"), "Horizontal page overflow"


checks: list[str] = []
with sync_playwright() as playwright:
    browser = playwright.chromium.launch(headless=True, executable_path=CHROME)
    page = browser.new_page(viewport={"width": 1440, "height": 1100}, accept_downloads=True)
    errors: list[str] = []
    external: list[str] = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.on("request", lambda request: external.append(request.url) if external_request(request.url) else None)
    page.goto(URL, wait_until="networkidle", timeout=120000)

    # Keyboard opens the installed lesson and keeps the default water selection.
    lesson_tab = page.get_by_role("button", name="Q-Chem lesson", exact=True)
    lesson_tab.focus()
    page.keyboard.press("Enter")
    root = page.locator(".qchem-workflow")
    expect(root).to_be_visible(timeout=60000)
    water = root.get_by_role("radio", name="Water", exact=False)
    expect(water).to_be_checked()
    water.focus()
    page.keyboard.press("Space")
    expect(water).to_be_checked()
    checks.append("Keyboard opens the Q-Chem lesson and preserves the water choice")

    # A routed failure checks the resilient help state without requiring Qwen inference.
    def coach_failure(route):
        route.fulfill(status=422, content_type="application/json", body=json.dumps({"detail": "Simulated model failure"}))

    page.route("**/api/qchem/coach", coach_failure)
    root.get_by_role("button", name="Which molecule should I start with?", exact=True).click()
    expect(root.locator(".qchem-coach .qchem-error")).to_contain_text("Simulated model failure")
    expect(root.locator(".qchem-coach .qchem-error")).to_contain_text("You can continue using the lesson notes and controls")
    page.unroute("**/api/qchem/coach", coach_failure)
    checks.append("Simulated coaching 422 is clearly labelled and leaves the lesson usable; route reset")

    # Build through the real installed engine, then complete the three learner checks.
    build = root.get_by_role("button", name="Build starting structure", exact=True)
    build.focus()
    page.keyboard.press("Enter")
    expect(root.get_by_label("How many atoms, including hydrogens?")).to_be_visible(timeout=120000)
    atom_answer = root.get_by_label("How many atoms, including hydrogens?")
    atom_answer.fill("3")
    root.get_by_role("button", name="Check atom count", exact=True).click()
    expect(root.locator(".qchem-feedback").first).to_contain_text("Correct.")
    root.get_by_text("Read the complete coordinate table", exact=True).click()
    expect(root.locator(".qchem-table-wrap tbody tr")).to_have_count(3)
    coordinate_check = root.get_by_label("What can the coordinate table tell you?")
    coordinate_check.focus()
    # Native popup arrows are not exposed by headless Chrome on macOS.
    # Exercise native select type-ahead instead: the correct option begins Which.
    page.keyboard.press("w")
    page.keyboard.press("Enter")
    expect(coordinate_check).to_have_value("positions")
    root.get_by_role("button", name="Continue to settings", exact=True).click()
    expect(root.get_by_label("Will this single-point job move the atoms?")).to_be_visible()
    root.get_by_label("Will this single-point job move the atoms?").select_option("fixed")
    note = "This input evaluates the fixed water starting coordinates and does not optimize them."
    root.get_by_label("In your own words (optional)").fill(note)
    root.get_by_role("button", name="Review Q-Chem input", exact=True).click()
    input_preview = root.get_by_label("Reviewed Q-Chem input")
    expect(input_preview).to_be_visible()
    exact_input = input_preview.text_content()
    assert exact_input is not None
    assert "$molecule\n0 1\n" in exact_input
    assert "$rem\nJOBTYPE sp\nMETHOD hf\nBASIS def2-SVP\n$end" in exact_input
    coordinate_rows = [line for line in exact_input.splitlines() if line[:1].isalpha() and len(line.split()) == 4]
    assert len(coordinate_rows) == 3
    checks.append("Installed engine builds water and the learner confirms 3 atoms, starting positions, and fixed-atom single point")

    root.get_by_label("I understand this prepares an input file; Q-Chem has not run.").check()
    with page.expect_download() as input_download:
        root.get_by_role("button", name="Download Q-Chem input", exact=True).click()
    assert Path(input_download.value.path()).read_text() == exact_input
    with page.expect_download() as record_download:
        root.get_by_role("button", name="Download study record", exact=True).click()
    record = json.loads(Path(record_download.value.path()).read_text())
    digest = hashlib.sha256(exact_input.encode()).hexdigest()
    assert record["status"] == "PREPARED_NOT_RUN"
    assert record["exact_input"] == exact_input
    assert record["input_sha256"] == digest
    assert record["geometry"]["coordinate_units"] == "angstrom"
    assert len(record["geometry"]["atomic_numbers"]) == len(record["geometry"]["coordinates"]) == 3
    assert record["learning"]["notes"] == note
    checks.append("Downloaded .in and study JSON match the reviewed input, SHA-256, note, and three-atom geometry")

    root.get_by_role("button", name="Save preparation to project", exact=True).click()
    expect(root.locator(".qchem-saved")).to_contain_text(digest, timeout=60000)
    checks.append("Reviewed preparation saves only after acknowledgement and reports the exact input hash")

    assert_no_horizontal_page_overflow(page)
    page.screenshot(path=str(OUT / "qchem-1440.png"), full_page=True)
    for width in (760, 390):
        page.set_viewport_size({"width": width, "height": 1100})
        assert root.bounding_box()["width"] <= width
        assert_no_horizontal_page_overflow(page)
        page.screenshot(path=str(OUT / f"qchem-{width}.png"), full_page=True)
    checks.append("Q-Chem lesson has no horizontal page overflow at 1440, 760, or 390 pixels")

    # UI-only fixture checks: help after a save requires a new review/snapshot.
    page.set_viewport_size({"width": 1440, "height": 1100})
    fixture = {"topic": "limitations", "title": "UI test guidance", "message": "Simulated checked lesson guidance.", "next_action": "Review again.", "provenance": {"guard": "UI test fixture; no model run"}}
    def coach_fixture(route):
        route.fulfill(status=200, content_type="application/json", body=json.dumps(fixture))
    page.route("**/api/qchem/coach", coach_fixture)
    root.get_by_role("button", name="Did Q-Chem run?", exact=True).click()
    expect(root.locator(".qchem-coach-answer")).to_contain_text("UI test guidance")
    expect(root.locator(".qchem-saved")).to_have_count(0)
    expect(root.locator(".qchem-ack input")).not_to_be_checked()
    expect(root.get_by_role("button", name="Download study record", exact=True)).to_be_disabled()
    page.unroute("**/api/qchem/coach", coach_fixture)
    checks.append("Simulated later help invalidates the old saved snapshot and requires review again")

    # A pending neutral-state answer cannot reappear after invalid settings are edited.
    root.get_by_role("button", name="Back to settings", exact=True).click()
    root.get_by_text("Inspect charge and multiplicity", exact=True).click()
    pending = []
    def hold_coach(route):
        pending.append(route)
    page.route("**/api/qchem/coach", hold_coach)
    root.get_by_role("button", name="Why is the charge zero?", exact=True).click()
    expect(root.locator(".qchem-help-status")).to_contain_text("model is running")
    charge = root.get_by_label("Q-Chem lesson charge", exact=True)
    charge.fill("")
    expect(root.get_by_role("button", name="Why is the charge zero?", exact=True)).to_be_disabled()
    expect(root.locator(".qchem-page [role=alert]")).to_contain_text("Input not ready")
    root.get_by_role("button", name="Reset neutral singlet", exact=True).click()
    expect(root.get_by_role("button", name="Why is the charge zero?", exact=True)).to_be_disabled()
    assert len(pending) == 1
    pending[0].fulfill(status=200, content_type="application/json", body=json.dumps(fixture))
    expect(root.get_by_role("button", name="Why is the charge zero?", exact=True)).to_be_enabled()
    expect(root.locator(".qchem-coach-answer")).to_have_count(0)
    page.unroute("**/api/qchem/coach", hold_coach)
    checks.append("Simulated pending response stays busy across context changes and is discarded after invalid settings")

    assert not errors, errors
    assert not external, external
    evidence = {
        "status": "PASS",
        "target": URL,
        "checks": checks,
        "input_sha256": digest,
        "geometry_atom_count": len(record["geometry"]["atomic_numbers"]),
        "console_errors": errors,
        "external_requests": external,
        "screenshots": ["qchem-1440.png", "qchem-760.png", "qchem-390.png"],
        "simulated_failure": "POST /api/qchem/coach routed to HTTP 422; model inference was not exercised by this browser script.",
    }
    (OUT / "browser-workflow.json").write_text(json.dumps(evidence, indent=2) + "\n")
    browser.close()

print(json.dumps(evidence, indent=2))
