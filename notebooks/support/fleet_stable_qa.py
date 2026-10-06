"""Real frozen-package/source replay and isolated concurrent request QA."""
from __future__ import annotations
import os
os.environ.setdefault('OPENBLAS_NUM_THREADS','1');os.environ.setdefault('OMP_NUM_THREADS','1')
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import shutil
import tempfile
import time

import numpy as np
import pandas as pd
import requests

from apps.api.app.fleet_bundle import install,switch,pointer,current_snapshot,load_package,export_zip
from apps.api.app.fleet_assistance import FEATURES,scores,self_scores
from apps.api.app.config import get_settings
from notebooks.support.fleet_reference_qa import registry_snapshot
from notebooks.support.fleet_stable_build import ROOT,OUT,SOURCE,hash_file
from notebooks.support.fleet_reference_study import write_json


def day_rows(machine,day,module):
    path=SOURCE/'minutes'/f'{machine}_{day}.parquet'
    data=pd.read_parquet(path,filters=[('module','==',module)]).sort_values('time')
    rows=[]
    for r in data.itertuples():
        rows.append({'time':r.time.isoformat(),'quality':bool(r.quality),'context':r.context,
                     'stable_control':bool(r.stable_control),'compressor':r.compressor,'module_state':r.module_state,
                     'busy':r.busy,'sv':r.sv,'valve':float(r.valve),**{f:float(getattr(r,f)) for f in FEATURES}})
    return rows


def subset_summary(fleet,days,start,end):
    points=[]
    for day in days:
        rows=day_rows('080',day,6)
        result=fleet.evaluate('080',6,rows)
        points.extend(p for p in result['points'] if start<=p['time']<end)
    supported=[p for p in points if p['assessment'] not in {'DATA_QUALITY','NOT_EVALUATED'}]
    return {'observed_minutes':len(points),'evaluated_minutes':len(supported),
            'quality_minutes':sum(p['assessment']=='DATA_QUALITY' for p in points),
            'unsupported_minutes':sum(p['assessment']=='NOT_EVALUATED' for p in points),
            'raw_flags':sum(p['raw_flag'] for p in supported),'persistent_minutes':sum(p['persistent_flag'] for p in supported),
            'cp2_level_flags':sum(p['cp2_level_flag'] for p in supported),
            'steady_minutes':sum(p['phase']=='STEADY_OBSERVATION' for p in supported),
            'steady_flags':sum(p['phase']=='STEADY_OBSERVATION' and p['raw_flag'] for p in supported)}


def numerical_parity(fleet):
    checked=0;max_abs=0.;max_relation=0.
    for model in fleet.models():
        rows=day_rows(model['machine'],'2026-09-15',model['module'])
        response=fleet.evaluate(model['machine'],model['module'],rows)['points']
        index=[i for i,(r,p) in enumerate(zip(rows,response)) if r['context']==model['context'] and p['absolute_score'] is not None]
        if not index:continue
        x=np.asarray([[rows[i][f] for f in FEATURES] for i in index])
        a=self_scores(x,model['local_absolute_reference']);b=scores(x,model)
        max_abs=max(max_abs,float(np.max(np.abs(a-[response[i]['absolute_score'] for i in index]))))
        max_relation=max(max_relation,float(np.max(np.abs(b-[response[i]['relationship_score'] for i in index]))))
        checked+=len(index)
    assert max_abs<1e-10 and max_relation<1e-9
    return {'actual_points':checked,'max_absolute_error':max_abs,'max_relationship_error':max_relation}


def install_and_rollback(build):
    store=get_settings().fleet_stable_store or ROOT/'artifacts/fleet-stable'
    initial=pointer(store);revision=initial['revision'];receipts=[]
    for name in ('base','cp2_candidate'):
        install(store,build['packages'][name])
    base=Path(build['packages']['base']).name;candidate=Path(build['packages']['cp2_candidate']).name
    for identity,reason in [(base,'Local Shadow base package acceptance'),(candidate,'CP2 reference Candidate'),(base,'Local Shadow rollback QA'),(candidate,'Restore reviewed test Candidate for website inspection')]:
        result=switch(store,identity,expected_revision=revision,actor='Codex-local-QA',reason=reason)
        receipts.append({k:result[k] for k in ('revision','bundle_id','previous_bundle_id')});revision=result['revision']
        assert current_snapshot(store)[1].bundle_id==identity
    rejected=False
    try:switch(store,base,expected_revision=max(0,revision-1),actor='stale-tab-QA',reason='stale revision')
    except ValueError:rejected=True
    assert rejected and pointer(store)['bundle_id']==candidate
    return {'store':str(store),'initial':initial,'switches':receipts,'stale_revision_rejected':rejected,'mode':'SHADOW'}


def http_load(bundle_id):
    urls=[]
    for machine in ('017','024','041','058','080','081'):
        for module in range(1,9):
            urls.append(f'http://127.0.0.1:8000/api/v1/calibration/fleet/stable/reference?machine_number={machine}&module={module}')
            urls.append(f'http://127.0.0.1:8000/api/v1/calibration/fleet/stable/day?machine_number={machine}&module={module}&day=2026-09-15&bundle_id={bundle_id}')
    def get(url):
        started=time.perf_counter();r=requests.get(url,timeout=30);elapsed=(time.perf_counter()-started)*1000
        r.raise_for_status();body=r.json();assert body['bundle_id']==bundle_id
        from urllib.parse import urlparse,parse_qs
        query=parse_qs(urlparse(url).query);machine=query['machine_number'][0];module=int(query['module'][0])
        if 'chart' in body:assert body['machine']==machine and body['module']==module
        else:assert all(p['machine']==machine and p['module']==module for p in body['profiles'])
        return elapsed
    cold=[get(url) for url in urls]
    with ThreadPoolExecutor(max_workers=10) as pool:
        warm=list(pool.map(get,[urls[i%len(urls)] for i in range(120)]))
    return {'distinct_views':len(urls),'clients':10,'requests':len(warm),'successes':len(warm),
            'prepared_first_read_p95_ms':float(np.quantile(cold,.95)),'warm_p50_ms':float(np.median(warm)),
            'warm_p95_ms':float(np.quantile(warm,.95)),'warm_max_ms':max(warm),
            'scope':'Bounded prepared HTTP evidence, not cold SQL ingestion or browser rendering'}


def run(http=False):
    build=json.loads((OUT/'build-summary.json').read_text(encoding='utf-8'))
    fleet=load_package(build['packages']['cp2_candidate'])
    registry=registry_snapshot()
    known=subset_summary(fleet,['2026-09-07','2026-09-08'],'2026-09-07T12:30:00','2026-09-08T23:50:00')
    normal=subset_summary(fleet,['2026-09-07'],'2026-09-07T00:00:00','2026-09-07T08:00:00')
    suspect=subset_summary(fleet,['2026-09-07'],'2026-09-07T10:55:00','2026-09-07T11:29:00')
    post=subset_summary(fleet,['2026-09-12'],'2026-09-12T04:00:00','2026-09-13')
    assert known['cp2_level_flags']>0 and known['steady_flags']>0
    assert suspect['raw_flags']==0 and suspect['quality_minutes']>0
    parity=numerical_parity(fleet)
    rows=day_rows('080','2026-09-07',6);elapsed=[]
    for _ in range(21):
        at=time.perf_counter();fleet.evaluate('080',6,rows);elapsed.append((time.perf_counter()-at)*1000)
    # Copy outside the repository; no notebooks, source ZIPs or SQL supplied.
    with tempfile.TemporaryDirectory(prefix='fleet-portable-') as directory:
        copied=Path(directory)/'package.zip';export_zip(build['packages']['cp2_candidate'],copied)
        portable=load_package(copied)
        assert portable.evaluate('080',6,rows)==fleet.evaluate('080',6,rows)
        portable_receipt={'zip_bytes':copied.stat().st_size,'zip_sha256':hash_file(copied),'exact_reload':True,
                          'requires_source_or_sql_for_inference':False}
    qa={'bundle_id':fleet.bundle_id,'registry':registry,'known_case':known,'proposed_normal_holdout':normal,
        'suspected_acquisition':suspect,'post_intervention_unreviewed':post,'parity':parity,'portable':portable_receipt,
        'inference':{'points':len(rows),'repeats':20,'p50_ms':float(np.median(elapsed[1:])),
                     'p95_ms':float(np.quantile(elapsed[1:],.95)),'scope':'Full one-module-day numerical/control/quality/phase scoring, excludes IO'},
        'healthy_fpr_verified':False,'prospective_verified':False,
        'interpretation':'Previously inspected case/owner-proposed stable interval; neither independent healthy FPR nor prospective recall'}
    qa['local_shadow_switch']=install_and_rollback(build)
    if http:qa['http']=http_load(fleet.bundle_id)
    write_json(OUT/'qa.json',qa)
    print(json.dumps(qa,indent=2),flush=True)
    return qa


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--http',action='store_true')
    run(parser.parse_args().http)
