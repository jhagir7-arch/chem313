"""Local review-only assistant and approved ORCA job routes."""
from fastapi import HTTPException, Request, Security
from pydantic import BaseModel, ConfigDict, Field, StrictBool
from .validation import InputError
from .assistant import Assistant
from .orca_runtime import executable_status
import json
import os
from pathlib import Path
import stat
import tempfile

class Prompt(BaseModel):
    model_config = ConfigDict(extra='forbid')
    prompt: str = Field(min_length=1,max_length=4000)

class OrcaPath(BaseModel):
    model_config = ConfigDict(extra="forbid")
    executable: str = Field(min_length=1,max_length=4096)

class Cancel(BaseModel):
    model_config = ConfigDict(extra='forbid')
    approved: StrictBool = False


def register(app, api):
    assistant = Assistant(api.ROOT)
    @app.get('/api/assistant/status')
    def assistant_status(request: Request, token: str | None = Security(api.SESSION_HEADER)):
        api.require_session(request,token)
        return assistant.status()

    @app.post('/api/assistant/propose')
    def propose(payload: Prompt, request: Request, token: str | None = Security(api.SESSION_HEADER)):
        api.require_session(request,token)
        try:
            return assistant.propose(payload.prompt)
        except (InputError,OSError) as exc:
            raise HTTPException(422,str(exc)) from exc

    @app.get('/api/orca/status')
    def orca_status(request: Request, token: str | None = Security(api.SESSION_HEADER)):
        api.require_session(request,token)
        try:
            if api.engine.orca.configuration_error:
                return {'status':'UNAVAILABLE','detail':api.engine.orca.configuration_error}
            return executable_status(api.engine.orca.executable, discover=False)
        except InputError as exc:
            return {'status':'UNAVAILABLE','detail':str(exc)}

    @app.post('/api/orca/configure')
    def configure(payload: OrcaPath, request: Request, token: str | None = Security(api.SESSION_HEADER)):
        api.require_session(request,token)
        candidate = Path(payload.executable).expanduser()
        try:
            if not candidate.is_absolute() or not stat.S_ISREG(candidate.stat().st_mode) or not os.access(candidate,os.X_OK):
                raise InputError('Choose an absolute path to an executable ORCA binary')
            if api.engine.orca._active is not None:
                raise InputError('Wait for the active ORCA job before changing its executable')
            candidate = candidate.resolve()
            result = executable_status(candidate)
            if result['status'] == 'UNAVAILABLE':
                raise InputError('The selected executable could not be probed')
            target = api.ROOT/'orca.json'
            if target.is_symlink():
                raise InputError('ORCA configuration symlinks are unsupported')
            fd, name = tempfile.mkstemp(prefix='.orca-config-',dir=api.ROOT)
            temporary = Path(name)
            try:
                with os.fdopen(fd,'w',encoding='utf-8') as stream:
                    json.dump({'executable':str(candidate)},stream)
                temporary.replace(target)
            finally:
                temporary.unlink(missing_ok=True)
            api.engine.orca.executable = candidate
            api.engine.orca.configuration_error = None
            return result
        except (InputError,OSError) as exc:
            raise HTTPException(422,str(exc)) from exc

    @app.get('/api/orca/jobs/{job_id}')
    def status(job_id: str, request: Request, token: str | None = Security(api.SESSION_HEADER)):
        api.require_session(request,token)
        try:
            return api.engine.orca.status(job_id)
        except InputError as exc:
            raise HTTPException(404,str(exc)) from exc

    @app.post('/api/orca/jobs/{job_id}/cancel')
    def cancel(job_id: str, payload: Cancel, request: Request, token: str | None = Security(api.SESSION_HEADER)):
        api.require_session(request,token)
        if payload.approved is not True:
            raise HTTPException(422,'Cancellation requires explicit approved=true')
        try:
            return api.engine.orca.cancel(job_id)
        except InputError as exc:
            raise HTTPException(404,str(exc)) from exc

    @app.on_event('shutdown')
    def shutdown():
        api.engine.orca.shutdown()
