"""Authenticated, explicit-approval API for local reviewed Q-Chem jobs."""
from fastapi import HTTPException, Request, Security
import math
from pydantic import BaseModel, ConfigDict, Field, StrictBool, field_validator

from .qchem_runtime import QchemRuntime, prepare_input
from .validation import InputError


class Configuration(BaseModel):
    model_config = ConfigDict(extra="forbid")
    installation: str = Field(min_length=1, max_length=4096)


class Atom(BaseModel):
    model_config = ConfigDict(extra="forbid")
    element: str
    x: float
    y: float
    z: float

    @field_validator("x", "y", "z", mode="before")
    @classmethod
    def finite_number(cls, value):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError("Coordinate must be a finite JSON number")
        return value


class Start(BaseModel):
    model_config = ConfigDict(extra="forbid")
    project: str = Field(min_length=1, max_length=48)
    molecule: str
    atoms: list[Atom] = Field(min_length=1, max_length=9)
    approved: StrictBool = False


class Preparation(BaseModel):
    """Read-only coordinate validation used before a beginner input is saved or downloaded."""
    model_config = ConfigDict(extra="forbid")
    molecule: str
    atoms: list[Atom] = Field(min_length=1, max_length=9)


class Cancel(BaseModel):
    model_config = ConfigDict(extra="forbid")
    approved: StrictBool = False


def register(app, api):
    runtime = QchemRuntime(api.engine.store)
    api.qchem_runtime = runtime

    @app.get("/api/qchem/status")
    def status(request: Request, token: str | None = Security(api.SESSION_HEADER)):
        api.require_session(request, token)
        return runtime.configuration()

    @app.post("/api/qchem/configure")
    def configure(payload: Configuration, request: Request, token: str | None = Security(api.SESSION_HEADER)):
        api.require_session(request, token)
        try:
            return runtime.configure(payload.installation)
        except (InputError, OSError) as exc:
            raise HTTPException(422, str(exc)) from exc

    @app.post("/api/qchem/prepare")
    def prepare(payload: Preparation, request: Request, token: str | None = Security(api.SESSION_HEADER)):
        api.require_session(request, token)
        try:
            return prepare_input(payload.molecule, [atom.model_dump() for atom in payload.atoms])
        except InputError as exc:
            raise HTTPException(422, str(exc)) from exc

    @app.post("/api/qchem/jobs")
    def start(payload: Start, request: Request, token: str | None = Security(api.SESSION_HEADER)):
        api.require_session(request, token)
        try:
            return runtime.start(payload.project, payload.molecule, [atom.model_dump() for atom in payload.atoms], payload.approved)
        except InputError as exc:
            raise HTTPException(422, str(exc)) from exc

    @app.get("/api/qchem/jobs/{job_id}")
    def job_status(job_id: str, request: Request, token: str | None = Security(api.SESSION_HEADER)):
        api.require_session(request, token)
        try:
            return runtime.status(job_id)
        except InputError as exc:
            raise HTTPException(404, str(exc)) from exc

    @app.get("/api/qchem/jobs")
    def jobs(project: str, request: Request, token: str | None = Security(api.SESSION_HEADER)):
        api.require_session(request, token)
        try:
            return {"jobs": runtime.jobs(project)}
        except InputError as exc:
            raise HTTPException(422, str(exc)) from exc

    @app.post("/api/qchem/jobs/{job_id}/cancel")
    def cancel(job_id: str, payload: Cancel, request: Request, token: str | None = Security(api.SESSION_HEADER)):
        api.require_session(request, token)
        if payload.approved is not True:
            raise HTTPException(422, "Cancellation requires explicit approved=true")
        try:
            return runtime.cancel(job_id)
        except InputError as exc:
            raise HTTPException(404, str(exc)) from exc

    @app.on_event("shutdown")
    def shutdown():
        runtime.shutdown()
