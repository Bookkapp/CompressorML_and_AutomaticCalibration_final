"""Real historical data + isolated persistence QA, not Active/Server acceptance."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timedelta,date
from pathlib import Path
import json
import time
from zoneinfo import ZoneInfo
import numpy as np
import requests
from sqlalchemy import create_engine,select,func
from apps.api.app.config import get_settings
from apps.api.app.db import get_source_engine
from apps.api.app.fleet_bundle import load_package,pointer,export_zip
from apps.api.app.fleet_transitions import propose
from apps.api.app.context_api import model_for,_profile_day
from apps.api.app.context_validation import report
from apps.api.app.qualified_detector import DurableDetector,ObservedSourceReader
from apps.api.app.qualified_windows import WindowPolicy
from apps.api.app.unified_events import events
from notebooks.support.fleet_reference_qa import registry_snapshot
from notebooks.support.fleet_stable_qa import subset_summary

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'notebooks/outputs/fleet_workflow_20261006'
BASE='0a7f49abefb189c998cc999011e92fa44428b81fa8cf2995f9891b1dfb8b25a4'
REVIEWED='2a7990dd1d81a251057980c219b64c2fa7a23ffeea91331d40b2b450d9656c4e'


def save(name,value):
    OUT.mkdir(parents=True,exist_ok=True);(OUT/name).write_text(json.dumps(value,ensure_ascii=False,indent=2,default=str),encoding='utf-8')


def inspect():
    settings=get_settings();store=settings.fleet_stable_store or ROOT/'artifacts/fleet-stable'
    fleet=load_package(store/pointer(store)['bundle_id']);parent=load_package(store/'fleet-stable-v1-2f656893533033ab994e3713')
    assert fleet.models()==parent.models()
    catalog=fleet.priors()['transition_catalog'];validation=json.loads((store/fleet.bundle_id/'validation.json').read_bytes())['transition_event_holdout']
    reference_ids={e['event_id'] for g in catalog['groups'] for e in g['examples']}
    holdout_ids={e['event_id'] for e in validation['events']}
    assert not reference_ids&holdout_ids
    assert len(reference_ids)==sum(g['events'] for g in catalog['groups'])
    forecast=propose(model_for(BASE),catalog,fleet.bundle_id)
    saved=report(model_for(REVIEWED),date(2026,10,2),date(2026,10,5),lambda day:_profile_day(REVIEWED,day))
    # Owner-described historical case only; these are not certified fault labels.
    known=subset_summary(fleet,['2026-09-07','2026-09-08'],'2026-09-07T13:10:00','2026-09-08T23:59:00')
    result={'bundle_id':fleet.bundle_id,'steady_models_byte_values_unchanged':True,'groups':len(catalog['groups']),
        'reference_events':len(reference_ids),'heldout_events':len(holdout_ids),'event_overlap':0,
        'independent_screen_passed_groups':sum(g.get('holdout',{}).get('passed',False) for g in catalog['groups']),
        'holdout':{k:v for k,v in validation.items() if k!='events'},
        'MX058_M1_eligible_fleet_templates':len(forecast['templates']),'MX058_M1_rejected_templates':len(forecast['rejected']),
        'MX058_M1_saved_shadow':saved,'MX080_M6_owner_described_case':known,
        'normal_false_alert_accuracy':'NOT_IDENTIFIABLE_WITH_UNREVIEWED_HEALTH_LABELS',
        'prospective_acceptance':'NOT_RUN_NO_UNTOUCHED_THREE_DAY_POST_FREEZE_SOURCE'}
    save('real-data.json',result);export_zip(store/fleet.bundle_id,OUT/(fleet.bundle_id+'.zip'))
    return result


def worker_rehearsal():
    settings=get_settings();assert settings.source_db_host in {'127.0.0.1','localhost'}
    store=settings.fleet_stable_store or ROOT/'artifacts/fleet-stable';fleet=load_package(store/pointer(store)['bundle_id'])
    path=OUT/'worker-rehearsal.sqlite';engine=create_engine('sqlite:///'+str(path))
    policy=WindowPolicy('Asia/Bangkok',late_arrival_seconds=30)
    reader=ObservedSourceReader(get_source_engine(),settings,maximum_rows=10000)
    result=[]
    for machine,start in [('041','2026-09-15T12:00:00'),('058','2026-09-15T12:00:00'),('080','2026-09-07T13:10:00'),('081','2026-09-15T12:00:00')]:
        start=datetime.fromisoformat(start);end=start+timedelta(minutes=8)
        rows=reader.read('MX'+machine,start,end,tuple(range(1,9)))
        assert rows,'Actual source slice unavailable'
        worker=DurableDetector(engine,policy,fleet=fleet,source_namespace='local-actual-SQL-rehearsal')
        worker.create_tables();run=worker.initialize('MX'+machine,tuple(range(1,9)),{})
        middle=start+timedelta(minutes=4)
        first=[r for r in rows if r['recorded_at']<middle]
        aware=lambda d:d.replace(tzinfo=ZoneInfo('Asia/Bangkok'))
        worker.cycle(run,first,as_of=aware(middle),profiles={})
        # Reconstructed object represents process restart from committed SQL.
        worker=DurableDetector(engine,policy,fleet=fleet,source_namespace='local-actual-SQL-rehearsal')
        worker.cycle(run,rows,as_of=aware(end+timedelta(seconds=30)),profiles={})
        with engine.connect() as c:before=c.execute(select(func.count()).select_from(events)).scalar()
        retry=worker.cycle(run,rows,as_of=aware(end+timedelta(seconds=30)),profiles={})
        with engine.connect() as c:
            assert c.execute(select(func.count()).select_from(events)).scalar()==before
            found=c.execute(select(events).where(events.c.machine_number=='MX'+machine)).mappings().all()
        result.append({'machine':machine,'source_rows':len(rows),'modules':8,'minutes':len(worker.store.points(run)),
            'retry_new_source_rows':retry['new_source_rows'],'restart_retry_pass':True,
            'events_by_type':dict(__import__('collections').Counter(e['event_type'] for e in found))})
    save('worker-rehearsal.json',{'mode':'ISOLATED_SQLITE_EVIDENCE_ACTUAL_LOCAL_MYSQL_SOURCE','machines':result,
        'real_analytics_tables_written':False,'server_connected':False,'actual_context_active_required':False})
    return result


def http_load():
    root='http://127.0.0.1:8000';status=requests.get(root+'/api/v1/calibration/fleet/manage',timeout=30).json();bundle=status['pointer']['bundle_id']
    urls=[root+'/api/v1/calibration/fleet/manage',root+f'/api/v1/calibration/fleet/manage/versions/{bundle}',
        root+f'/api/v1/calibration/context/profiles/{BASE}/fleet-transitions',
        root+f'/api/v1/calibration/context/profiles/{REVIEWED}/validation-report?start=2026-10-02&end=2026-10-05']
    urls += [root+f'/api/v1/calibration/fleet/stable/day?machine_number={m}&module={module}&day=2026-09-15&bundle_id={bundle}'
             for m in ['041','058','080','081'] for module in range(1,9)]
    def fetch(url):
        at=time.perf_counter();response=requests.get(url,timeout=30);response.raise_for_status()
        return (time.perf_counter()-at)*1000
    cold=[fetch(u) for u in urls]
    before=registry_snapshot()
    with ThreadPoolExecutor(max_workers=10) as pool:times=list(pool.map(fetch,(urls*4)[:120]))
    after=registry_snapshot();assert before==after
    result={'requests':len(times),'concurrent_clients':10,'success':len(times),'warm_p50_ms':float(np.quantile(times,.5)),
            'warm_p95_ms':float(np.quantile(times,.95)),'max_ms':max(times),'cold_max_ms':max(cold),
            'registry_unchanged':True,'prepared_http_only':'No source cold load, training latency or browser render benchmark claim'}
    save('http-load.json',result);return result


if __name__=='__main__':
    OUT.mkdir(parents=True,exist_ok=True);before=registry_snapshot();save('registry-before.json',before)
    print(json.dumps({'real':{k:v for k,v in inspect().items() if k not in {'MX058_M1_saved_shadow','holdout'}},'worker':worker_rehearsal(),'http':http_load()},default=str,indent=2))
    assert before==registry_snapshot();save('registry-after.json',registry_snapshot())
