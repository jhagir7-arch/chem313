import sys

import pytest
from fastapi.testclient import TestClient

from hypothesislab import api
from hypothesislab.science_api import register
from hypothesislab.workbench import WorkbenchEngine


ORIGINAL_ROUTES = list(api.app.router.routes)
ORIGINAL_SHUTDOWN = list(api.app.router.on_shutdown)


# The production desktop runner explicitly installs this optional route module.
# Tests register it only after legacy release-gate tests have run.



@pytest.fixture
def client(tmp_path):
    if not getattr(api.app.state, "science_test_routes_registered", False):
        register(api.app, api)
        api.app.state.science_test_routes_registered = True
    previous = api.engine
    engine = WorkbenchEngine(tmp_path)
    api.engine = engine
    try:
        with TestClient(api.app) as test_client:
            headers = {"X-HypothesisLab-Session": test_client.get("/api/session").json()["session_token"]}
            yield test_client, headers, engine
    finally:
        api.engine = previous


def test_science_routes_require_local_session_and_trusted_origin(client):
    test_client, headers, _ = client
    assert test_client.get("/api/science/operations").status_code == 403
    assert test_client.get("/api/science/operations", headers={**headers, "Origin": "http://example.invalid"}).status_code == 403
    reply = test_client.get("/api/science/operations", headers=headers)
    assert reply.status_code == 200
    assert reply.json()["schema"] == "openchem.operations.v1"
    assert any(row["operation"] == "numpy.summary" for row in reply.json()["operations"])


def test_planner_cannot_mint_approval_or_submit_science_job(client):
    test_client, headers, engine = client
    plan = test_client.post("/api/workflows/plan", headers=headers, json={"text": "convert a unit"})
    assert plan.status_code == 200
    payload = plan.json()
    assert payload["executes"] is False
    assert payload["requires_explicit_apply"] is True
    assert "preview_token" not in payload

    params = {"operation": "pint.convert", "inputs": {"value": 1000.0, "from_unit": "milligram", "to_unit": "gram"}}
    denied = test_client.post("/api/execute", headers=headers, json={"action": "science.run", "params": params, "approved": False})
    assert denied.status_code == 422
    forged = test_client.post("/api/execute", headers=headers, json={"action": "science.run", "params": params, "approved": True, "preview_token": "planner-token"})
    assert forged.status_code == 422
    assert engine.jobs.jobs == {}


def test_api_preview_execute_and_cancel_require_explicit_true(client, monkeypatch):
    # An actual child process keeps the cancellation path active without a private worker.
    command = [sys.executable, "-c", "import time; time.sleep(30)"]
    monkeypatch.setattr("hypothesislab.workbench.worker_command", lambda operation: (command, None))
    monkeypatch.setattr("hypothesislab.science_jobs.worker_command", lambda operation: (command, None))
    test_client, headers, engine = client
    params = {"operation": "numpy.summary", "inputs": {"values": [1.0, 2.0, 3.0], "unit": "a.u."}}
    preview = test_client.post("/api/preview", headers=headers, json={"action": "science.run", "params": params, "project": "science"})
    assert preview.status_code == 200
    token = preview.json()["preview_token"]

    no_apply = test_client.post("/api/execute", headers=headers, json={"action": "science.run", "params": params, "project": "science", "approved": False, "preview_token": token})
    assert no_apply.status_code == 422
    assert engine.jobs.jobs == {}

    execute = test_client.post("/api/execute", headers=headers, json={"action": "science.run", "params": params, "project": "science", "approved": True, "preview_token": token})
    assert execute.status_code == 200
    job_id = execute.json()["result"]["job_id"]
    assert test_client.post(f"/api/jobs/{job_id}/cancel", headers=headers, json={"approved": False}).status_code == 422
    assert test_client.post(f"/api/jobs/{job_id}/cancel", headers=headers, json={"approved": "true"}).status_code == 422

    cancelled = test_client.post(f"/api/jobs/{job_id}/cancel", headers=headers, json={"approved": True})
    assert cancelled.status_code == 200
    assert cancelled.json()["state"] == "CANCELLED"
    assert test_client.get(f"/api/jobs/{job_id}", headers=headers).json()["state"] == "CANCELLED"


def teardown_module():
    # Keep the shared legacy API contract untouched for its generated-schema gate.
    api.app.router.routes[:] = ORIGINAL_ROUTES
    api.app.router.on_shutdown[:] = ORIGINAL_SHUTDOWN
    api.app.openapi_schema = None
    if hasattr(api.app.state, "science_test_routes_registered"):
        delattr(api.app.state, "science_test_routes_registered")
