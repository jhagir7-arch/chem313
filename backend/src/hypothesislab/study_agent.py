"""Finite, project-bound molecular studies. Model output is data, never executable code."""
from __future__ import annotations
import copy
import json
import re
import subprocess
import threading
import time
import uuid
from .assistant import worker_command
from .qwen_worker import MODEL_ID, PUBLIC_FILES, PUBLIC_VARIANT
from .store import sha256
from .study_sampling import sample_shapes, _validate_molecule as validate_molecule
from .validation import InputError, PROJECT_RE

CATALOG = {
    'water':'O', 'ethanol':'CCO', 'methanol':'CO', 'butane':'CCCC',
    'propane':'CCC', 'methane':'C', 'ethane':'CC', 'benzene':'c1ccccc1',
    'acetone':'CC(=O)C', 'acetic acid':'CC(=O)O', 'aspirin':'CC(=O)Oc1ccccc1C(=O)O',
    'caffeine':'Cn1c(=O)c2c(ncn2C)n(C)c1=O', 'paracetamol':'CC(=O)Nc1ccc(O)cc1',
    'glycine':'NCC(=O)O',
}
ALIASES = {'enthanol':'ethanol','ethyl alcohol':'ethanol','acetaminophen':'paracetamol','ethanoic acid':'acetic acid'}
LESSON = {
    'title':'Ethanol and water: mixing and hydrogen bonding',
    'text':'At ordinary room conditions, ethanol and water mix. Their oxygen-containing groups can form hydrogen bonds with one another. Mixing them does not by itself demonstrate a new covalent reaction product.',
    'technical':'Hydrogen bonding is an intermolecular interaction. The dashed line in this schematic represents a possible interaction, not a new covalent bond. This lesson predicts no reaction pathway, mixing energy or reaction rate; no calculation was run.',
    'sources':[
        {'title':'PubChem: ethanol compound record','url':'https://pubchem.ncbi.nlm.nih.gov/compound/Ethanol'},
        {'title':'OpenStax Chemistry 2e: intermolecular forces','url':'https://openstax.org/books/chemistry-2e/pages/10-1-intermolecular-forces'},
    ],
}
LIMIT = 'This version can compare starting shapes of one supported small molecule and explain ethanol–water mixing. It cannot predict medication breakdown, biological interactions, unknown reaction products or activation barriers.'


def encode(value):
    return json.dumps(value,sort_keys=True,allow_nan=False,separators=(',',':')).encode()


def infer_study(prompt):
    command, env = worker_command()
    try:
        result = subprocess.run(command,input=encode({'prompt':prompt,'mode':'study'}),capture_output=True,env=env,timeout=90)
    except subprocess.TimeoutExpired as exc:
        raise InputError('Local Qwen took too long. Try a shorter question; no study ran.') from exc
    if result.returncode or len(result.stdout)>20_000:
        raise InputError('Local Qwen could not produce a study plan. Check that the bundled model is available; no study ran.')
    try:
        reply=json.loads(result.stdout)
        if reply['model']!=MODEL_ID or reply['variant']!=PUBLIC_VARIANT or reply['model_sha256']!=PUBLIC_FILES['model.safetensors'] or reply['adapter_sha256'] is not None:
            raise ValueError('unrecognized model')
        raw=reply.pop('raw')
        return raw,reply
    except (ValueError,KeyError,TypeError) as exc:
        raise InputError('Qwen returned unrecognized study provenance; no study ran.') from exc


def validate_plan(prompt, raw):
    try:
        proposal=json.loads(raw)
    except (ValueError,TypeError) as exc:
        raise InputError('Qwen returned an incomplete plan. Try one of the examples; nothing ran.') from exc
    if not isinstance(proposal,dict) or set(proposal)!={'task','molecule','samples'} or not isinstance(proposal['task'],str) or proposal['task'] not in {'shapes','mixture','clarify','unsupported'}:
        raise InputError('Qwen returned unsupported plan fields; nothing ran.')
    task=proposal['task']
    text=prompt.lower()
    for alias,name in ALIASES.items():
        text=re.sub(r'\b'+re.escape(alias)+r'\b',name,text)
    names=[name for name in CATALOG if re.search(r'\b'+re.escape(name)+r'\b',text)]
    if re.search(r'\b(drug interactions?|medication|metaboli\w*|degrad\w*|break\s*down|barriers?|transition states?|shell|python|execute|terminal)\b',text):
        return {'task':'unsupported','message':LIMIT}
    if 'ethanol' in names and 'water' in names and re.search(r'\b(react\w*|mix\w*|interact\w*|dissolv\w*)\b',text):
        if task!='mixture':
            raise InputError('Qwen did not recognize the ethanol/water teaching request. Try the example; nothing ran.')
        if proposal['molecule'] is not None or proposal['samples'] is not None:
            raise InputError('A teaching plan cannot contain calculation arguments.')
        return {'task':'mixture','message':'A sourced teaching illustration. No calculation or reaction simulation runs.','lesson':copy.deepcopy(LESSON)}
    if re.search(r'\b(react\w*|mix\w*|interact\w*|dissolv\w*|products?|kinetic\w*)\b',text):
        return {'task':'unsupported','message':LIMIT}
    if task=='clarify' and proposal['samples'] is None and isinstance(proposal['molecule'],str) and len(proposal['molecule'])<=80:
        # A model clarification never authorizes work. For an explicit supported
        # shape request only, prepare a separately labelled deterministic plan
        # for the user to review. Preserve the original model output in the audit.
        normalized=ALIASES.get(proposal['molecule'].lower().strip(),proposal['molecule'].lower().strip())
        safe_request=re.search(r'\b(shapes?|conformers?|conformations?|geometries)\b',text) and not re.search(r"\b(don't|do not|never|avoid)\b",text)
        if len(names)==1 and normalized==names[0] and normalized in CATALOG and safe_request:
            counts=[int(x) for x in re.findall(r'\b\d+\b',text)]
            counts.extend(value for word,value in {'one':1,'two':2,'three':3,'four':4,'five':5,'six':6,'seven':7,'eight':8,'nine':9,'ten':10,'twenty':20,'hundred':100}.items() if re.search(r'\b'+word+r'\b',text))
            if len(set(counts))>1 or counts and not 1<=counts[0]<=8:
                raise InputError('Choose one count between one and eight; nothing ran.')
            checked=validate_plan(prompt,json.dumps({'task':'shapes','molecule':normalized,'samples':counts[0] if counts else 5}))
            checked['planner_note']='Qwen asked for clarification. Chem313 recognized the explicit molecule and shape request and prepared this checked fallback plan. Review it before Run.'
            checked['message']=checked['planner_note']+' '+checked['message']
            return checked
        return {'task':'clarify','message':'Please choose one supported molecule and a count from one to eight. Available: '+', '.join(CATALOG)+'. No structure was guessed.'}
    if task in {'clarify','unsupported'}:
        if proposal['molecule'] is not None or proposal['samples'] is not None:
            raise InputError('Qwen returned conflicting task arguments; nothing ran.')
        return {'task':task,'message':LIMIT if task=='unsupported' else 'Which molecule would you like to study? Try “Compare five shapes of butane”. Supported names: '+', '.join(CATALOG)+'.'}
    if task!='shapes':
        return {'task':'unsupported','message':LIMIT}
    name=proposal['molecule']
    if not isinstance(name,str):
        raise InputError('Qwen did not identify a molecule; try a supported example.')
    name=ALIASES.get(name.lower().strip(),name.lower().strip())
    if len(names)!=1 or name!=names[0] or name not in CATALOG:
        return {'task':'clarify','message':'Use one unambiguous supported molecule name. Available: '+', '.join(CATALOG)+'. No structure was guessed.'}
    count=proposal['samples']
    if type(count) is not int or not 1<=count<=8:
        raise InputError('Choose between one and eight starting shapes. Nothing ran.')
    numbers=[int(x) for x in re.findall(r'\b\d+\b',text)]
    words={'one':1,'two':2,'three':3,'four':4,'five':5,'six':6,'seven':7,'eight':8,'nine':9,'ten':10,'twenty':20,'hundred':100}
    numbers += [value for word,value in words.items() if re.search(r'\b'+word+r'\b',text)]
    if numbers and (len(set(numbers))!=1 or numbers[0]!=count):
        raise InputError('Qwen changed the requested number of shapes. Use one count from one to eight; nothing ran.')
    if not numbers and count!=5:
        raise InputError('Qwen changed the default number of shapes (five). Nothing ran.')
    mol=validate_molecule(CATALOG[name])
    from rdkit import Chem
    from rdkit.Chem import rdMolDescriptors
    from rdkit.Chem.Draw import rdMolDraw2D
    drawer=rdMolDraw2D.MolDraw2DSVG(300,160)
    drawer.DrawMolecule(mol)
    drawer.FinishDrawing()
    return {'task':'shapes','molecule':name,'canonical_smiles':Chem.MolToSmiles(mol,isomericSmiles=True),
            'formula':rdMolDescriptors.CalcMolFormula(mol),'samples':count,'depiction_svg':drawer.GetDrawingText(),
            'message':f'Generate {count} starting shapes of {name}, remove duplicates, and compare compatible force-field energies. No quantum calculation runs.'}


class StudyAgent:
    def __init__(self,store,infer=infer_study,sampler=sample_shapes):
        self.store,self.infer,self.sampler=store,infer,sampler
        self.lock=threading.RLock()
        self.planning=threading.Lock()
        self.plans={}
        self.jobs={}
        self.active=None

    def plan(self,project,prompt):
        if not isinstance(project,str) or not PROJECT_RE.fullmatch(project):
            raise InputError('Invalid project identifier')
        if not isinstance(prompt,str) or not 1<=len(prompt.strip())<=4000:
            raise InputError('Enter a question of 1..4000 characters')
        if not self.planning.acquire(blocking=False):
            raise InputError('Qwen is already planning a study. Wait for it to finish.')
        try:
            raw,provenance=self.infer(prompt)
            validated=validate_plan(prompt,raw)
            plan={'id':uuid.uuid4().hex,'project':project,'prompt':prompt,**validated,'provenance':provenance,'model_output':raw}
            with self.lock:
                now=time.monotonic()
                self.plans={k:v for k,v in self.plans.items() if now-v['created']<600}
                if len(self.plans)>=32:
                    self.plans.pop(next(iter(self.plans)))
                if plan['task']=='shapes':
                    self.plans[plan['id']]={'created':now,'plan':copy.deepcopy(plan)}
            return plan
        finally:
            self.planning.release()

    def run(self,project,plan_id):
        with self.lock:
            item=self.plans.get(plan_id)
            if not item or item['plan']['project']!=project or time.monotonic()-item['created']>=600:
                raise InputError('This study plan expired or belongs to another project. Ask again.')
            if self.active is not None:
                raise InputError('A study is already running. Wait or cancel it first.')
            self.store.preflight_event_log(project)
            plan=copy.deepcopy(item['plan'])
            self.plans.pop(plan_id)
            # Keep a bounded result cache; durable results live in project artifacts.
            while len(self.jobs)>=32:
                self.jobs.pop(next(iter(self.jobs)))
            job={'id':uuid.uuid4().hex,'project':project,'status':'running','completed':0,'requested':plan['samples'],'plan':plan,'cancel':threading.Event()}
            self.jobs[job['id']]=job
            self.active=job['id']
            thread=threading.Thread(target=self._execute,args=(job,),daemon=True)
            job['thread']=thread
            thread.start()
            return self.status(project,job['id'])

    def _execute(self,job):
        try:
            plan=job['plan']
            def progress(completed,total):
                with self.lock:
                    job['completed']=completed
            result=self.sampler(plan['canonical_smiles'],plan['samples'],job['cancel'].is_set,progress)
            result['summary']=f"Completed {result['completed']} of {result['requested']} starting samples; {result['unique_count']} unique converged shapes. Energies compare only this molecule within the same force field."
            recipe={'schema':'openchem.molecule-study.v1','plan':plan,'sampling':{'seeds':[42,137,271,811,1297,1879,2081,3557][:plan['samples']],'rmsd_threshold_angstrom':0.25,'maximum_seconds':60},'result':result}
            outputs=[self.store.put(job['project'],'originals','json',encode(plan))]
            for candidate in result['candidates']:
                if candidate['status']=='unique':
                    candidate['artifact']=self.store.put(job['project'],'derived','sdf',candidate['sdf'].encode())
                    outputs.append(candidate['artifact'])
            recipe['result']=result
            outputs.append(self.store.put(job['project'],'reports','json',encode(recipe)))
            self.store.event(job['project'],'molecule.study',sha256(encode(plan)),outputs,{'summary':result['summary'],'cancelled':result['cancelled'],'model':plan['provenance']})
            with self.lock:
                job.update(result=result,recipe=recipe,artifacts=outputs,status='cancelled' if result['cancelled'] else 'complete',completed=result['completed'])
        except Exception as exc:
            with self.lock:
                job.update(status='failed',error=str(exc)[:1000])
        finally:
            with self.lock:
                self.active=None

    def status(self,project,job_id):
        with self.lock:
            job=self.jobs.get(job_id)
            if not job or job['project']!=project:
                raise InputError('Study not found in this project')
            return copy.deepcopy({k:v for k,v in job.items() if k not in {'cancel','thread'}})

    def cancel(self,project,job_id):
        with self.lock:
            self.status(project,job_id)
            self.jobs[job_id]['cancel'].set()
            return self.status(project,job_id)

    def shutdown(self):
        with self.lock:
            jobs=list(self.jobs.values())
            for job in jobs:
                job['cancel'].set()
        for job in jobs:
            job['thread'].join(timeout=3)
