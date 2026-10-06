"""Read-only actual-artifact/HTTP QA. No source or registry mutations."""
import os
os.environ.setdefault('OPENBLAS_NUM_THREADS','1')
os.environ.setdefault('OMP_NUM_THREADS','1')
import gc
import hashlib
import json
import platform
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd
import requests
from sqlalchemy import text

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from apps.api.app.fleet_assistance import FEATURES,scores,self_scores
from apps.api.app.db import get_engine
from apps.api.app.config import get_settings
from sqlalchemy.engine import make_url
from notebooks.support.import_downloads_history import registry_hash
from notebooks.support.fleet_reference_study import OUT,write_json
from notebooks.support.fleet_reference_benchmark import steady,persistence


def registry_snapshot():
    if make_url(get_settings().database_url).host not in ('localhost','127.0.0.1','::1'):
        raise RuntimeError('Fleet QA permits local registry SELECTs only')
    before=json.loads((OUT/'registry-before.json').read_text(encoding='utf-8'))
    # Same sorted JSON-line hash helper as the original pre-work receipt.
    after=registry_hash(get_engine())
    with get_engine().connect() as conn:
        for table in ('ht9046mx_calibration_profile','ht9046mx_active_calibration_profile'):
            after[table]['unchanged']=all(after[table][field]==before[table][field] for field in ('rows','sha256'))
        after['context_active_count']=conn.execute(text('SELECT COUNT(*) FROM ht9046mx_context_active')).scalar()
        after['import_receipt_count']=conn.execute(text('SELECT COUNT(*) FROM ht9046mx_history_import_file')).scalar()
    assert all(after[k]['unchanged'] for k in ('ht9046mx_calibration_profile','ht9046mx_active_calibration_profile'))
    assert after['context_active_count']==before['context_active_count']==0
    assert after['import_receipt_count']==before['import_receipt_count']==567
    write_json(OUT/'registry-after.json',after)
    return after


def known_case(models):
    metadata=json.loads((ROOT/'cases/MX080_M6_2026-09-07/case.json').read_text(encoding='utf-8'))
    day=pd.read_parquet(OUT/'minutes/080_2026-09-07.parquet',filters=[('module','==',6)])
    start=pd.Timestamp(metadata['confirmed_interval']['start_inclusive']).ceil('min')
    end=pd.Timestamp(metadata['confirmed_interval']['end_exclusive'])
    results=[]
    for model in models:
        if model['machine']!='080' or model['module']!=6:continue
        local=model['local_absolute_reference']
        eligible=steady(day,local['scale'])&day.context.eq(model['context'])&day.time.ge(start)&day.time.lt(end)
        selected=day[eligible];x=selected[list(FEATURES)].to_numpy()
        if not len(x):continue
        absolute=self_scores(x,local)>model['absolute_threshold']
        relationship=scores(x,model)>model['threshold']
        results.append({'context':model['context'],'quality_supported_steady_minutes':len(x),
                        'absolute_flags':int(absolute.sum()),'relationship_flags':int(relationship.sum()),
                        'combined_flags':int((absolute|relationship).sum()),
                        'combined_persistent_minutes':persistence(absolute|relationship,selected.time)[0],
                        'fleet_weight':model['fleet_weight'],'local_level_frozen':model['center']==local['center'],
                        'local_scale_frozen':model['scale']==local['scale']})
        assert not np.any(absolute&~(absolute|relationship))
    return {'case_id':metadata['case_id'],'interval':[str(start),str(end)],'results':results,
            'interpretation':'Previously inspected known-case regression; neither prospective sensitivity nor accuracy. Unsupported/nonsteady minutes abstain.'}


def scoring_speed(models):
    model=next(m for m in models if m['machine']=='041' and m['module']==1)
    day=pd.read_parquet(OUT/'minutes/041_2026-09-15.parquet',filters=[('module','==',1)])
    x=day.loc[day.quality,list(FEATURES)].to_numpy();elapsed=[]
    for _ in range(31):
        start=time.perf_counter();scores(x,model);self_scores(x,model['local_absolute_reference'])
        elapsed.append((time.perf_counter()-start)*1000)
    return {'actual_points':len(x),'repeats':30,'p50_ms':float(np.median(elapsed[1:])),
            'p95_ms':float(np.quantile(elapsed[1:],.95)),
            'interpretation':'In-process batch numerical score only, excludes IO, model fit, UI and future validation'}


def http_load():
    base='http://127.0.0.1:8000/api/v1/calibration/fleet'
    urls=[]
    for machine in ('041','058','080','081'):
        for module in range(1,9):
            urls += [f'{base}/reference?machine_number={machine}&module={module}',
                     f'{base}/day?machine_number={machine}&module={module}&day=2026-09-15']
    def get(url):
        start=time.perf_counter();response=requests.get(url,timeout=30)
        result={'url':url.removeprefix('http://127.0.0.1:8000'),'status':response.status_code,
                'ms':(time.perf_counter()-start)*1000,'bytes_decoded':len(response.content)}
        if response.status_code==200:
            data=response.json();assert str(data['module'])==url.split('module=')[1].split('&')[0]
            assert data['machine']==url.split('machine_number=')[1].split('&')[0]
            assert not data.get('activation_eligible',False)
            if 'chart' in data:assert len(data['chart'])<=1440
        return result
    # Bounded first reads at 4 clients; API is newly restarted, no Fleet request cache warmed by this process.
    with ThreadPoolExecutor(max_workers=4) as executor:first=list(executor.map(get,urls))
    assert all(r['status']==200 for r in first),first
    with ThreadPoolExecutor(max_workers=10) as executor:
        warm=list(executor.map(get,[urls[i%len(urls)] for i in range(120)]))
    assert all(r['status']==200 for r in warm),warm
    invalid=[requests.get(base+'/day',params={'machine_number':'041','module':1,'day':'2026-07-01'}).status_code,
             requests.get(base+'/day',params={'machine_number':'041','module':9,'day':'2026-09-15'}).status_code]
    assert invalid==[422,422]
    return {'clients':10,'requests':120,'successes':120,'first_reads':first,
            'first_read_clients':4,'first_p95_ms':float(np.quantile([r['ms'] for r in first],.95)),
            'p50_ms':float(np.median([r['ms'] for r in warm])),
            'p95_ms':float(np.quantile([r['ms'] for r in warm],.95)),
            'max_ms':max(r['ms'] for r in warm),'responses':warm,'invalid_day_and_module':invalid,
            'interpretation':'Prepared artifact GETs only, not live SQL intake, rendered browser time, model building, or Active approval'}


def run():
    manifest=json.loads((OUT/'intake_manifest.json').read_text(encoding='utf-8'))
    summary=json.loads((OUT/'summary.json').read_text(encoding='utf-8'))
    models=json.loads((OUT/'model_proposals.json').read_text(encoding='utf-8'))['models']
    assert len(manifest['files'])==555 and all(r.get('valve_completeness_verified') for r in manifest['files'])
    qa={'study_id':summary['study_id'],'environment':{'python':platform.python_version(),'platform':platform.platform(),
        'numpy':np.__version__,'pandas':pd.__version__,'thread_policy':'OPENBLAS=1 OMP=1, intake POLARS=2'},
        'quality':{'source_files':555,'raw_rows':manifest['raw_rows'],
                   'duplicate_timestamp_occurrence_rows':sum(r['duplicate_rows'] for r in manifest['files']),
                   'invalid_valve_observations':sum(r.get('invalid_valve_observations',0) for r in manifest['files']),
                   'healthy_labels':False,'sql_snapshot':False},
        'known_case':known_case(models),'scoring':scoring_speed(models),'http':http_load(),'registry':registry_snapshot()}
    write_json(OUT/'technical-qa.json',qa)
    print(json.dumps({**qa,'http':{k:v for k,v in qa['http'].items() if k not in ('first_reads','responses')}},indent=2))


if __name__=='__main__':run()
