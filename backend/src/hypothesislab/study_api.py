"""Authenticated loopback routes for finite molecule studies."""
from fastapi import HTTPException, Request, Security
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field
from .qchem_coach import QchemCoach
from .qchem_results import QchemResultCoach
from .study_agent import StudyAgent
from .validation import InputError

class PlanRequest(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    project:str=Field(min_length=1,max_length=48)
    prompt:str=Field(min_length=1,max_length=4000)

class RunRequest(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    project:str=Field(min_length=1,max_length=48)
    plan_id:str=Field(min_length=32,max_length=32)

class CancelRequest(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)


class QchemCoachRequest(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    project:str=Field(min_length=1,max_length=48)
    prompt:str=Field(min_length=1,max_length=1000)
    step:Literal['choose','inspect','settings','export']
    molecule:Literal['water','methane','ethanol']
    charge:int
    multiplicity:int
    atom_count:int


class QchemResultRequest(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    project:str=Field(min_length=1,max_length=48)
    job_id:str=Field(pattern=r'^[a-f0-9]{32}$')
    prompt:str=Field(min_length=1,max_length=1000)


def register(app,api):
    agent=StudyAgent(api.engine.store)
    coach=QchemCoach()
    result_coach=QchemResultCoach(coach)
    @app.post('/api/qchem/results/coach')
    def qchem_result_coach(payload:QchemResultRequest,request:Request,token:str|None=Security(api.SESSION_HEADER)):
        api.require_session(request,token)
        try:
            job=api.qchem_runtime.status(payload.job_id)
            return result_coach.explain(project=payload.project,prompt=payload.prompt,job=job)
        except (InputError,OSError) as exc:
            raise HTTPException(422,str(exc)) from exc
    @app.post('/api/qchem/coach')
    def qchem_coach(payload:QchemCoachRequest,request:Request,token:str|None=Security(api.SESSION_HEADER)):
        api.require_session(request,token)
        try:
            return coach.coach(**payload.model_dump())
        except (InputError,OSError) as exc:
            raise HTTPException(422,str(exc)) from exc
    @app.post('/api/studies/plan')
    def plan(payload:PlanRequest,request:Request,token:str|None=Security(api.SESSION_HEADER)):
        api.require_session(request,token)
        try:
            return agent.plan(payload.project,payload.prompt)
        except (InputError,OSError) as exc:
            raise HTTPException(422,str(exc)) from exc

    @app.post('/api/studies/run')
    def run(payload:RunRequest,request:Request,token:str|None=Security(api.SESSION_HEADER)):
        api.require_session(request,token)
        try:
            return agent.run(payload.project,payload.plan_id)
        except (InputError,OSError) as exc:
            raise HTTPException(422,str(exc)) from exc

    @app.get('/api/studies/{project}/{job_id}')
    def status(project:str,job_id:str,request:Request,token:str|None=Security(api.SESSION_HEADER)):
        api.require_session(request,token)
        try:
            return agent.status(project,job_id)
        except InputError as exc:
            raise HTTPException(404,str(exc)) from exc

    @app.post('/api/studies/{project}/{job_id}/cancel')
    def cancel(project:str,job_id:str,payload:CancelRequest,request:Request,token:str|None=Security(api.SESSION_HEADER)):
        api.require_session(request,token)
        try:
            return agent.cancel(project,job_id)
        except InputError as exc:
            raise HTTPException(404,str(exc)) from exc

    @app.on_event('shutdown')
    def shutdown():
        agent.shutdown()
    return agent
