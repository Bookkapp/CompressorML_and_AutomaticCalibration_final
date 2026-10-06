"""Immutable Fleet inventory, isolated training, and revision checked Shadow release."""
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid
from functools import lru_cache

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field
from .config import get_settings
from .fleet_bundle import ID, load_package, pointer, switch, canonical, atomic_replace

router = APIRouter(prefix='/api/v1/calibration/fleet/manage', tags=['Fleet model management'])


def paths():
    s=get_settings()
    return s.fleet_stable_store or s.project_root/'artifacts/fleet-stable', s.fleet_reference_root or s.project_root/'notebooks/outputs/fleet_reference_study_20261005'


def save(path, value):
    path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_name(path.name+'.'+uuid.uuid4().hex+'.tmp')
    try:
        with temp.open('wb') as f:
            f.write(canonical(value));f.flush();os.fsync(f.fileno())
        atomic_replace(temp,path)
    finally:temp.unlink(missing_ok=True)


@contextmanager
def lease(path):
    """Kernel lock releases on process death; no stale PID file deadlocks."""
    from .file_lock import exclusive_lock
    with exclusive_lock(path,message='Another Fleet training job is running'):yield


def jobs(store):
    root=Path(store)/'training';rows=[]
    for p in sorted(root.glob('*/job.json'),key=lambda p:p.stat().st_mtime_ns,reverse=True)[:50]:
        value=json.loads(p.read_bytes());rows.append(value)
    # Recover abandoned jobs only while exclusively holding the child lease.
    try:
        with lease(root/'worker.lock'):
            for r in rows:
                if r['status'] in {'RUNNING','QUEUED'} and time.time()-r['updated_epoch']>60:
                    r.update(status='INTERRUPTED',message='Training stopped; existing frozen release is unchanged',updated_epoch=time.time())
                    save(root/r['job_id']/'job.json',r)
    except ValueError:pass
    return sorted(rows,key=lambda r:r['created_epoch'],reverse=True)


def version(store, bundle_id):
    if not ID.fullmatch(bundle_id):raise ValueError('invalid Fleet version')
    path=Path(store)/bundle_id
    from .fleet_bundle import FILES
    signatures=tuple((name,(path/name).stat().st_mtime_ns,(path/name).stat().st_size) for name in sorted(FILES|{'manifest.json'}))
    return _version(str(path),signatures)


@lru_cache(maxsize=32)
def _version(path,signatures):
    path=Path(path);fleet=load_package(path)
    validation=json.loads((path/'validation.json').read_bytes())
    curation=json.loads((path/'curation.json').read_bytes())
    catalog=fleet.priors().get('transition_catalog',{})
    holdout=validation.get('transition_event_holdout',{})
    return {**fleet.status(),'build_plan':curation.get('build_plan'),
            'transition_groups':len(catalog.get('groups',[])),
            'transition_reference_events':sum(g['events'] for g in catalog.get('groups',[])),
            'transition_passed_groups':sum(g.get('holdout',{}).get('passed') is True for g in catalog.get('groups',[])),
            'validation':{k:v for k,v in validation.items() if k!='transition_event_holdout'},
            'transition_holdout':{k:v for k,v in holdout.items() if k!='events'},
            'healthy_review':curation.get('healthy_review','PENDING'),
            'created_order':path.stat().st_mtime_ns}


def inventory(store):
    rows=[]
    for p in sorted(Path(store).glob('fleet-stable-v1-*'),key=lambda p:p.stat().st_mtime_ns,reverse=True)[:100]:
        if not p.is_dir() or not ID.fullmatch(p.name):continue
        try:
            v=version(store,p.name)
            rows.append({k:v[k] for k in ('bundle_id','models_total','source_machines','transition_groups','transition_reference_events','healthy_review','created_order')})
        except (ValueError,KeyError,OSError):rows.append({'bundle_id':p.name,'status':'VERIFICATION_FAILED'})
    public=[{k:v for k,v in j.items() if k not in {'source_root','store'}} for j in jobs(store)]
    return {'pointer':pointer(store),'versions':rows,'jobs':public,'release_mode':'SHADOW',
            'interpretation':'Approval selects a frozen Shadow version. Active machine profiles retain their own engineering and future-data gates.'}


class TrainRequest(BaseModel):
    fit: list[str]=Field(min_length=2,max_length=2)
    calibration: list[str]=Field(min_length=2,max_length=2)
    machines: list[str]=Field(min_length=1,max_length=32)
    reason: str=Field(min_length=8,max_length=1000)


def validate_plan(request, source):
    # Validation is pure; heavy fitting is performed in a fresh subprocess.
    from datetime import date
    for interval in (request.fit,request.calibration):
        a,b=map(date.fromisoformat,interval)
        if list(map(date.isoformat,(a,b)))!=interval or not 3<=(b-a).days<=90:raise ValueError('Choose 3–90 days per period')
    if request.fit[1]>request.calibration[0]:raise ValueError('Reference and calibration must not overlap')
    study=json.loads((Path(source)/'summary.json').read_bytes())
    if len(set(request.machines))!=len(request.machines) or not set(request.machines)<=set(study['source_machine_order']):
        raise ValueError('Choose unique machines with verified prepared data')
    for machine in request.machines:
        for start,end in (request.fit,request.calibration):
            if not any(r['machine']==machine and start<=r['date']<end for r in study['source_days']):
                raise ValueError(f'No prepared data for MX{machine} in this period')
    # Preserve the owner described fault quarantine and proposed CP2 stable blocks.
    overrides=[{'machine':'080','module':6,'fit':['2026-08-27','2026-08-31'],
                'calibration':['2026-09-03','2026-09-07']}] if '080' in request.machines else []
    return {'fit':request.fit,'calibration':request.calibration,'machines':request.machines,'overrides':overrides}


def create_job(request, actor, *, launch=True):
    store,source=paths();plan=validate_plan(request,source);root=Path(store)/'training'
    with lease(root/'queue.lock'):
        if any(r['status'] in {'RUNNING','QUEUED'} for r in jobs(store)):raise ValueError('Another Fleet training job is running')
        job_id=uuid.uuid4().hex;folder=root/job_id;now=time.time()
        job={'job_id':job_id,'status':'QUEUED','created_epoch':now,'updated_epoch':now,
             'actor':actor,'reason':request.reason,'plan':plan,'source_root':str(Path(source).resolve()),
             'store':str(Path(store).resolve()),'message':'Waiting for isolated training process','bundle_id':None}
        save(folder/'job.json',job)
        if launch:
            env=os.environ.copy();env.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
            try:
                with (folder/'training.log').open('ab') as log:
                    subprocess.Popen([sys.executable,'-m','apps.api.app.fleet_training','--job',str(folder/'job.json')],
                        cwd=str(get_settings().project_root),env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=log,
                        creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0,start_new_session=os.name!='nt')
            except OSError:
                job.update(status='FAILED',message='Could not start training process',updated_epoch=time.time());save(folder/'job.json',job);raise
        return {k:v for k,v in job.items() if k not in {'source_root','store'}}


def checked(fn):
    try:return fn()
    except FileNotFoundError as exc:raise HTTPException(404,'Prepared Fleet artifact is unavailable') from exc
    except (ValueError,KeyError) as exc:raise HTTPException(409,str(exc)) from exc


def actor(value):
    if not value or not 2<=len(value.strip())<=100:raise HTTPException(422,'Enter reviewer name or ID')
    return value.strip()


@router.get('')
def status():return checked(lambda:inventory(paths()[0]))


@router.get('/versions/{bundle_id}')
def detail(bundle_id:str):return checked(lambda:version(paths()[0],bundle_id))


@router.get('/compare/{left}/{right}')
def compare(left:str,right:str):
    def result():
        store,_=paths();a=version(store,left);b=version(store,right)
        from .fleet_stable import FEATURES
        old={(m['machine'],m['module'],m['context']):m for m in load_package(store/left).models()}
        new={(m['machine'],m['module'],m['context']):m for m in load_package(store/right).models()}
        rows=[]
        for key in sorted(old.keys()|new.keys()):
            x,y=old.get(key),new.get(key)
            rows.append({'machine':key[0],'module':key[1],'context':key[2],'status':'ADDED' if not x else 'REMOVED' if not y else 'COMPARED',
                'center_delta':dict(zip(FEATURES,[v-u for u,v in zip(x['center'],y['center'])])) if x and y else None,
                'absolute_threshold':[x['absolute_threshold'] if x else None,y['absolute_threshold'] if y else None],
                'relationship_threshold':[x['threshold'] if x else None,y['threshold'] if y else None]})
        return {'left':a,'right':b,'profiles':rows}
    return checked(result)


@router.post('/train',status_code=202)
def train(request:TrainRequest,x_approver_id:str|None=Header(default=None)):
    who=actor(x_approver_id)
    return checked(lambda:create_job(request,who))


class ReleaseRequest(BaseModel):
    bundle_id:str
    expected_revision:int=Field(ge=0)
    reason:str=Field(min_length=8,max_length=1000)


@router.post('/release')
def release(request:ReleaseRequest,x_approver_id:str|None=Header(default=None)):
    who=actor(x_approver_id)
    return checked(lambda:switch(paths()[0],request.bundle_id,expected_revision=request.expected_revision,actor=who,reason=request.reason))
