"""Read prepared local Fleet research evidence; never fit inside HTTP requests."""
from datetime import date
import json
import hashlib
from pathlib import Path
from functools import lru_cache

from fastapi import APIRouter,HTTPException,Query,Header
from .context_reads import inspection_response
from .inference import clean_machine_code
from .config import get_settings

ROOT=Path(__file__).resolve().parents[3]/'notebooks/outputs/fleet_reference_study_20261005'
router=APIRouter(prefix='/api/v1/calibration/fleet',tags=['Fleet reference evidence'])


@lru_cache(maxsize=2)
def _read_summary(path,mtime,size):
    # Private read-only artifact. Filtered HTTP payloads are serialized once;
    # repeated tabs need not deep-copy the complete research corpus each time.
    return json.loads(Path(path).read_text(encoding='utf-8'))


def summary():
    path=(get_settings().fleet_reference_root or ROOT)/'summary.json'
    if not path.exists():raise HTTPException(404,'Fleet reference is not prepared yet')
    stat=path.stat()
    return _read_summary(str(path),stat.st_mtime_ns,stat.st_size)


def machine_key(value):
    clean=clean_machine_code(value)
    # The prepared artifact has an explicit finite machine population.
    digits=clean.removeprefix('MX').removeprefix('-')
    if not digits.isdigit():raise HTTPException(422,'Choose a machine in the Fleet study')
    return digits.zfill(3)


@lru_cache(maxsize=128)
def _verify_day(path,mtime,size,expected_sha):
    # Once per immutable file revision, before both cold and cached responses.
    with Path(path).open('rb') as stream:actual=hashlib.file_digest(stream,'sha256').hexdigest()
    if actual!=expected_sha:raise HTTPException(409,'Prepared measurements changed after the frozen Fleet study')


@router.get('/reference')
def reference(machine_number:str,module:int=Query(1,ge=1,le=8),accept_encoding:str=Header(default='')):
    study=summary();machine=machine_key(machine_number)
    if machine not in study['source_machine_order']:raise HTTPException(404,'Machine is outside this prepared Fleet study')
    def payload():
        return {k:v for k,v in study.items() if k not in ('variants','coverage','transition_summary','source_days')}|{
          'machine':machine,'module':module,'mode':'RESEARCH_REFERENCE_NOT_ACTIVE',
          'coverage':[r for r in study['coverage'] if r['machine']==machine],
          'variants':[r for r in study['variants'] if r['machine']==machine and r['module']==module],
          'transitions':[r for r in study['transition_summary'] if r['machine']==machine and r['module']==module],
          'days':sorted(r['date'] for r in study['source_days'] if r['machine']==machine)}
    return inspection_response(('fleet-reference',study['study_id'],machine,module),payload,accept_encoding=accept_encoding)


@router.get('/day')
def day(machine_number:str,day:date,module:int=Query(1,ge=1,le=8),accept_encoding:str=Header(default='')):
    study=summary();machine=machine_key(machine_number)
    expected=next((r for r in study['source_days'] if r['machine']==machine and r['date']==day.isoformat()),None)
    if expected is None:raise HTTPException(422,'Choose a committed day within the prepared study')
    path=(get_settings().fleet_reference_root or ROOT)/'minutes'/f'{machine}_{day.isoformat()}.parquet';metadata=path.with_suffix('.json')
    if not path.exists() or not metadata.exists():raise HTTPException(409,'Prepared day unavailable; rerun study intake')
    source=json.loads(metadata.read_text(encoding='utf-8'))
    if source['source_sha256']!=expected['source_sha256']:
        raise HTTPException(409,'Source changed after the frozen Fleet study')
    if source.get('derived_version')!=study.get('derived_version') or not expected.get('minute_parquet_sha256'):
        raise HTTPException(409,'Prepared measurement version is not frozen in this study')
    stat=path.stat()
    _verify_day(str(path),stat.st_mtime_ns,stat.st_size,expected['minute_parquet_sha256'])
    def payload():
        import pandas as pd
        data=pd.read_parquet(path,filters=[('module','==',module)]).sort_values('time')
        chart=[]
        for row in data.itertuples():
            features={f:float(getattr(row,f)) for f in ('hp1','lp1','hp2','lp2','temphi','templo')} if row.quality else None
            if features:features.update(dp1=features['hp1']-features['lp1'],dp2=features['hp2']-features['lp2'])
            chart.append({'time':row.time.isoformat(),'features':features,'quality':'PASS' if row.quality else 'DATA_QUALITY',
                          'context':row.context,'coverage':row.coverage})
        return {'study_id':study['study_id'],'machine':machine,'module':module,'source_timezone':'Asia/Bangkok',
                'pressure_unit':'psi','mode':'RESEARCH_REFERENCE_NOT_ACTIVE','chart':chart,
                'source_sha256':source['source_sha256'],'interpretation':'Actual observed minute averages; not healthy labels or Raw seconds'}
    return inspection_response(('fleet-day',study['study_id'],machine,module,day.isoformat(),stat.st_mtime_ns),
                               payload,accept_encoding=accept_encoding)


def stable_snapshot():
    from .fleet_bundle import current_snapshot
    settings=get_settings()
    try:
        return current_snapshot(settings.fleet_stable_store or settings.project_root/'artifacts/fleet-stable')
    except FileNotFoundError as exc:
        raise HTTPException(404,'Fleet Stable package is not installed') from exc
    except (ValueError,KeyError,OSError) as exc:
        raise HTTPException(409,'Fleet Stable package verification failed; inspect the installed version') from exc


@router.get('/stable/reference')
def stable_reference(machine_number:str,module:int=Query(1,ge=1,le=8)):
    machine=machine_key(machine_number);pointer,fleet=stable_snapshot()
    if machine not in fleet.status()['source_machines']:
        raise HTTPException(404,'Machine is outside this frozen Fleet package')
    return {**fleet.status(machine,module),'pointer_revision':pointer['revision']}


@router.get('/stable/day')
def stable_day(machine_number:str,day:date,module:int=Query(1,ge=1,le=8),
               bundle_id:str|None=None,accept_encoding:str=Header(default='')):
    import pandas as pd
    from .fleet_stable import FEATURES
    machine=machine_key(machine_number);pointer,fleet=stable_snapshot()
    # Pin the version displayed to the reviewer; a switch requires refreshing.
    if bundle_id and bundle_id!=fleet.bundle_id:
        raise HTTPException(409,'Fleet version changed; refresh the reference before viewing evidence')
    study=summary()
    expected=next((r for r in study['source_days'] if r['machine']==machine and r['date']==day.isoformat()),None)
    if expected is None:raise HTTPException(422,'Choose a committed day within the prepared study')
    path=(get_settings().fleet_reference_root or ROOT)/'minutes'/f'{machine}_{day.isoformat()}.parquet'
    stat=path.stat()
    _verify_day(str(path),stat.st_mtime_ns,stat.st_size,expected['minute_parquet_sha256'])
    def payload():
        data=pd.read_parquet(path,filters=[('module','==',module)]).sort_values('time')
        rows=[]
        for r in data.itertuples():
            # Audited invalid-second interval rounds OUTWARD to avoid mixed
            # minute averages concealing a burst at either boundary.
            rows.append({'time':r.time.isoformat(),'quality':bool(r.quality),'context':r.context,
                         'stable_control':bool(r.stable_control),'compressor':r.compressor,
                         'module_state':r.module_state,'busy':r.busy,'sv':r.sv,'valve':float(r.valve),
                         **{f:float(getattr(r,f)) for f in FEATURES}})
        result=fleet.evaluate(machine,module,rows)
        chart=[]
        for row,point in zip(rows,result.pop('points')):
            observed={f:row[f] for f in FEATURES} if row['quality'] else None
            import math
            chart.append({**point,'features':observed,'context':row['context'],
                          'control':{k:row[k] for k in ('compressor','module_state','busy','sv')}
                          |{'valve':row['valve'] if math.isfinite(row['valve']) else None}})
        return {**result,'chart':chart,'pressure_unit':'psi','source_timezone':'Asia/Bangkok',
                'pointer_revision':pointer['revision'],'source_sha256':expected['source_sha256']}
    return inspection_response(('fleet-stable-day',fleet.bundle_id,pointer['revision'],study['study_id'],machine,module,day.isoformat(),stat.st_mtime_ns),
                               payload,accept_encoding=accept_encoding)
