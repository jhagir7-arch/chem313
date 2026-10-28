"""Loopback-only HTTP transport for the same typed local engine."""
from __future__ import annotations
import os
from pathlib import Path
import sys
import secrets
import ipaddress
from fastapi import Request, Security
from fastapi.security import APIKeyHeader
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from starlette.responses import JSONResponse
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, ConfigDict
from .engine import Engine
from . import __version__
from .capabilities import manifest as capability_manifest
from .chemistry import HAS_RDKIT
from .validation import InputError

# Runtime state never belongs under the distributable source tree.
if sys.platform == "darwin":
    DEFAULT_DATA = Path.home() / "Library" / "Application Support" / "HypothesisLab"
else:
    DEFAULT_DATA = Path(os.getenv("XDG_DATA_HOME",str(Path.home()/".local"/"share"))) / "hypothesislab"
ROOT = Path(os.getenv("HYPOTHESISLAB_DATA",str(DEFAULT_DATA)))
app = FastAPI(title="HypothesisLab Local Engine", version=__version__, docs_url=None, redoc_url=None)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "testserver"])
app.add_middleware(CORSMiddleware, allow_origins=["http://127.0.0.1:5173","http://localhost:5173"],allow_credentials=False,allow_methods=["GET","POST"],allow_headers=["Content-Type","X-HypothesisLab-Session"])
engine = Engine(ROOT)
@app.middleware("http")
async def reject_nonlocal_clients(request: Request, call_next):
    """Prevent accidental remote access even if uvicorn was bound to 0.0.0.0."""
    peer = request.client.host if request.client else ""
    if peer != "testclient":
        try:
            local = ipaddress.ip_address(peer).is_loopback
        except ValueError:
            local = False
        if not local:
            return JSONResponse({"detail":"Local clients only"},status_code=403)
    response = await call_next(request)
    response.headers.setdefault("Cache-Control", "no-store")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    return response

LOCAL_ORIGINS = frozenset({"http://127.0.0.1:5173", "http://localhost:5173"})
SESSION = secrets.token_urlsafe(32)
SESSION_HEADER = APIKeyHeader(name="X-HypothesisLab-Session", auto_error=False)

def require_session(request: Request, presented: str | None):
    origin = request.headers.get("origin")
    if origin and origin not in LOCAL_ORIGINS and origin != str(request.base_url).rstrip("/"):
        raise HTTPException(status_code=403, detail="Untrusted origin")
    if not presented or not secrets.compare_digest(presented, SESSION):
        raise HTTPException(status_code=403, detail="Invalid local session")


class Action(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: str
    params: dict = Field(default_factory=dict)
    project: str = "default"
    approved: bool = False
    preview_token: str | None = None

@app.get("/api/session")
def session(request: Request):
    origin = request.headers.get("origin")
    if origin and origin not in LOCAL_ORIGINS and origin != str(request.base_url).rstrip("/"):
        raise HTTPException(status_code=403, detail="Untrusted origin")
    from fastapi.responses import JSONResponse
    return JSONResponse({"session_token": SESSION}, headers={"Cache-Control":"no-store"})

@app.get("/api/health")
def health():
    return {"status":"OK", "version":__version__, "network_binding_requirement":"127.0.0.1 only", "engines":{"rdkit":"available" if HAS_RDKIT else "unavailable", "avogadro":"optional local host"}}

@app.get("/api/capabilities")
def capabilities(request: Request, x_hypothesislab_session: str | None = Security(SESSION_HEADER)):
    require_session(request, x_hypothesislab_session)
    return capability_manifest()

@app.get("/api/catalog")
def catalog_route(request: Request, x_hypothesislab_session: str | None = Security(SESSION_HEADER)):
    """Starter molecules, force fields and parameter bounds; the interface shows nothing it does not read here."""
    require_session(request, x_hypothesislab_session)
    from .catalog import catalog
    return catalog()

@app.post("/api/preview")
def preview(payload: Action, request: Request, x_hypothesislab_session: str | None = Security(SESSION_HEADER)):
    require_session(request, x_hypothesislab_session)
    try:
        return engine.preview(payload.action,payload.params,payload.project)
    except InputError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e

@app.post("/api/execute")
def execute(payload: Action, request: Request, x_hypothesislab_session: str | None = Security(SESSION_HEADER)):
    require_session(request, x_hypothesislab_session)
    try:
        return engine.execute(payload.action,payload.params,payload.project,payload.approved,payload.preview_token)
    except InputError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    except (ConnectionError, OSError) as e:
        raise HTTPException(status_code=503, detail=type(e).__name__) from e

@app.get("/api/projects/{project}/events")
def events(project: str, request: Request, x_hypothesislab_session: str | None = Security(SESSION_HEADER)):
    require_session(request, x_hypothesislab_session)
    try:
        return {"project":project, "events":engine.store.events(project)}
    except InputError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e

@app.get("/api/projects/{project}/verify")
def verify(project: str, request: Request, x_hypothesislab_session: str | None = Security(SESSION_HEADER)):
    require_session(request, x_hypothesislab_session)
    try:
        return engine.store.verify_artifacts(project)
    except InputError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
