#!/usr/bin/env python3
"""Live browser proof for the local-only Science workflows tab."""
import json
import math
import os
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
SERVICE = ROOT / "build" / "science-dev-service.json"
OUT = ROOT / "evidence" / "science-ui"


def wait_state(page, state="SUCCEEDED"):
    page.get_by_text(state, exact=True).wait_for(timeout=20_000)


def preview_apply_result(page, operation):
    """Use the visible review controls and return this operation's fresh result."""
    page.get_by_role("button", name="Preview this run").click()
    page.get_by_text("Exact reviewed inputs").wait_for(timeout=20_000)
    page.get_by_role("button", name="Apply approved run").click()
    record = page.locator(".science-job")
    record.get_by_text(operation, exact=True).wait_for(timeout=20_000)
    record.get_by_text("SUCCEEDED", exact=True).wait_for(timeout=120_000)
    record.get_by_text("Result and scientific limits", exact=True).click()
    result = json.loads(record.locator("details").filter(has_text="Result and scientific limits").locator(".science-result").inner_text())
    assert result["operation"] == operation
    return result


def main():
    url = os.environ.get("OPENCHEM_TEST_URL")
    if not url:
        if not SERVICE.exists():
            raise SystemExit("Set OPENCHEM_TEST_URL or create build/science-dev-service.json")
        url = json.loads(SERVICE.read_text())["url"]
    OUT.mkdir(parents=True, exist_ok=True)
    errors, external = [], []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 900}); page.set_default_timeout(5_000)
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.on("request", lambda r: external.append(r.url) if not (r.url.startswith(url) or r.url.startswith("blob:")) else None)
        page.goto(url, wait_until="domcontentloaded")
        page.get_by_role("button", name="Science workflows").click()
        operation = page.get_by_label("Allowed operation")
        operation.select_option("numpy.summary")
        page.locator(".input-fields input").nth(0).fill("[1,2,3]")
        page.locator(".input-fields input").nth(1).fill("a.u.")
        page.get_by_role("button", name="Preview this run").click()
        page.get_by_text("Exact reviewed inputs").wait_for()
        assert page.get_by_text("Input SHA-256").count() == 1
        assert page.get_by_text('"values": [', exact=False).count() == 1
        page.get_by_role("button", name="Apply approved run").click()
        wait_state(page)
        assert '"mean": 2' in page.content()

        operation.select_option("pint.convert")
        page.locator(".input-fields input").nth(0).fill("1000")
        page.locator(".input-fields input").nth(1).fill("nm")
        page.locator(".input-fields input").nth(2).fill("um")
        page.get_by_role("button", name="Preview this run").click()
        page.get_by_role("button", name="Apply approved run").click()
        page.locator(".science-job-body").get_by_text("pint.convert", exact=True).wait_for()
        page.wait_for_timeout(1_500)
        page.get_by_text("Result and scientific limits").click()
        assert "micrometer" in page.locator(".science-job").inner_text()
        assert page.locator(".science-job .artifact-list").evaluate("el => el.scrollWidth <= el.clientWidth")

        operation.select_option("pyenzyme.document")
        page.locator(".input-fields input").nth(0).fill("OpenChem bioscience example")
        enzyme = preview_apply_result(page, "pyenzyme.document")
        assert enzyme["output"]["name"] == "OpenChem bioscience example"
        assert enzyme["output"]["method"] == "EnzymeMLDocument"

        operation.select_option("pysb.first_order_decay")
        decay_inputs = page.locator(".input-fields input")
        decay_inputs.nth(0).fill("1")
        decay_inputs.nth(1).fill("1")
        decay_inputs.nth(2).fill("[0, 1]")
        decay_inputs.nth(3).fill("s")
        decay_inputs.nth(4).fill("1/s")
        decay = preview_apply_result(page, "pysb.first_order_decay")
        assert math.isclose(decay["output"]["A"][-1], math.exp(-1), abs_tol=1e-5)

        page.get_by_label("Workflow description").fill("convert a value but do not specify source and destination units")
        page.get_by_role("button", name="Suggest allowed inputs").click()
        page.get_by_text("NEEDS INPUT", exact=True).wait_for()
        assert page.get_by_role("button", name="Apply approved run").count() == 0
        page.get_by_label("Filter registry").fill("NumPy")
        page.get_by_text("NumPy", exact=True).wait_for()
        assert page.locator(".science-table-wrap tbody tr").count() == 1
        page.screenshot(path=str(OUT / "science-workflows-1280.png"), full_page=True)
        page.set_viewport_size({"width": 390, "height": 844})
        page.screenshot(path=str(OUT / "science-workflows-390.png"), full_page=True)
        browser.close()
    assert not errors, errors
    assert not external, external
    print("science UI browser proof passed")


if __name__ == "__main__":
    main()
