"""Authenticated desktop routes for operations, plans, and job lifecycle."""
from fastapi import HTTPException, Request, Security
from pydantic import BaseModel, ConfigDict, Field, StrictBool
from .science_jobs import operation_descriptions
from .validation import InputError


class Goal(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=1, max_length=4000)


class Cancel(BaseModel):
    model_config = ConfigDict(extra="forbid")
    approved: StrictBool = False


def register(app, api):
    @app.get("/api/science/operations")
    def operations(request: Request, token: str | None = Security(api.SESSION_HEADER)):
        api.require_session(request, token)
        return {"schema": "openchem.operations.v1", "operations": operation_descriptions()}

    @app.get("/api/engines/registry")
    def registry(request: Request, token: str | None = Security(api.SESSION_HEADER)):
        api.require_session(request, token)
        from .engine_registry import manifest
        return manifest()

    @app.post("/api/workflows/plan")
    def workflow(payload: Goal, request: Request, token: str | None = Security(api.SESSION_HEADER)):
        api.require_session(request, token)
        from .workflows import plan
        try:
            return plan(payload.text)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc

    @app.get("/api/jobs/{job_id}")
    def job(job_id: str, request: Request, token: str | None = Security(api.SESSION_HEADER)):
        api.require_session(request, token)
        try:
            return api.engine.jobs.get(job_id)
        except InputError as exc:
            raise HTTPException(404, str(exc)) from exc

    @app.post("/api/jobs/{job_id}/cancel")
    def cancel(job_id: str, payload: Cancel, request: Request, token: str | None = Security(api.SESSION_HEADER)):
        api.require_session(request, token)
        if payload.approved is not True:
            raise HTTPException(422, "Cancellation requires explicit approved=true")
        try:
            return api.engine.jobs.cancel(job_id)
        except InputError as exc:
            raise HTTPException(404, str(exc)) from exc

    @app.on_event("shutdown")
    def shutdown():
        api.engine.jobs.shutdown()
