"""Technical read-only parity/load QA. Manual UI steps are recorded separately."""
from pathlib import Path
import sys,json,time,hashlib
from datetime import datetime,timedelta,timezone
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import numpy as np
import httpx
from sqlalchemy import text

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'apps/api'))
from app.config import get_settings
from app.db import get_engine,get_source_engine
from app.context_reference import latest_preparation
from app.context_storage import source_namespace
from app.observed_context import build_observed_minutes
from app.qualified_calibration import policy_from_settings
from app.qualified_detector import ObservedSourceReader
from app.unified_events import TransitionTracker

OUT=ROOT/'notebooks/outputs/context_profile_uat_20261005'
s=get_settings()
assert s.source_db_host in {'localhost','127.0.0.1','::1'} and s.analytics_db_host in {'localhost','127.0.0.1','::1'}
client=httpx.Client(base_url='http://127.0.0.1:8000',timeout=30)
def get(url):
    response=client.get(url);response.raise_for_status();return response.json()
jobs={m:latest_preparation(m,True) for m in ('MX017','MX024')}
modules={m:{v['module']:v for v in j['result']['modules']} for m,j in jobs.items()}
parity=[]
reader=ObservedSourceReader(get_source_engine(),s,maximum_rows=6000)
for machine,start_text in [('MX017','2026-09-29T23:25:00'),('MX024','2026-09-30T08:00:00')]:
    start=datetime.fromisoformat(start_text);end=start+timedelta(minutes=20)
    rows=reader.read(machine,start-timedelta(seconds=1),end,range(1,9))
    expected=build_observed_minutes(rows,as_of=(end+timedelta(days=1)).replace(tzinfo=timezone.utc),policy=policy_from_settings(s),modules=range(1,9))
    comparisons=0
    for module in range(1,9):
        profile=modules[machine][module]['profile_id']
        data=get(f'/api/v1/calibration/context/profiles/{profile}/day?day={start.date()}')
        actual={p['time']:p for p in data['chart']}
        for w in expected:
            if w.module!=module or not start<=w.window_start<end:continue
            p=actual[w.window_start.isoformat()]
            assert p['quality']==w.measurement_quality and p['features']==w.features
            comparisons+=1
    generated=TransitionTracker(source_namespace(s),s.source_timezone).consume(rows)
    truth={(r['event_type'],r['module'],r['occurred_at'],json.loads(r['payload_json'])['details'].get('before'),json.loads(r['payload_json'])['details'].get('after')) for r in generated if r['family']=='CONTROL' and r['occurred_at']>=start.isoformat()}
    response=get(f'/api/v1/events?machine_number={machine}&family=CONTROL&mode=HISTORICAL&start={start.isoformat()}&end={end.isoformat()}&limit=500')
    found={(r['event_type'],r['module'],r['occurred_at'],r['payload']['details'].get('before'),r['payload']['details'].get('after')) for r in response['items']}
    assert truth==found and not response['next_cursor']
    parity.append({'machine':machine,'start':start.isoformat(),'end_exclusive':end.isoformat(),'raw_rows':len(rows),'minute_module_comparisons':comparisons,'observed_control_changes':len(truth),'exact':True})
urls=[]
for machine in modules:
    for module in range(1,9):
        pid=modules[machine][module]['profile_id']
        urls.append(f'/api/v1/calibration/context/profiles/{pid}/day?day=2026-09-30')
    pid=modules[machine][1]['profile_id']
    urls.extend([f'/api/v1/events?machine_number={machine}&module=1&limit=100',f'/api/v1/calibration/context/profiles/{pid}/raw?start=2026-09-30T08:00:00&end=2026-09-30T08:20:00'])
def timing(url):
    at=time.perf_counter();r=client.get(url);elapsed=(time.perf_counter()-at)*1000
    return {'status':r.status_code,'ms':elapsed,'decoded_bytes':len(r.content),'wire_bytes':int(r.headers.get('content-length',len(r.content))),'encoding':r.headers.get('content-encoding'),'path':url}
with ThreadPoolExecutor(max_workers=10) as pool:
    first_reads=list(pool.map(timing,urls))
    results=list(pool.map(timing,[urls[i%len(urls)] for i in range(120)]))
assert all(r['status']==200 for r in results)
assert all(r['status']==200 for r in first_reads)
with get_engine().connect() as conn:
    event_counts=[dict(r) for r in conn.execute(text('SELECT family,mode,COUNT(*) AS records FROM ht9046mx_events GROUP BY family,mode')).mappings()]
    active_rows=[dict(r) for r in conn.execute(text('SELECT * FROM ht9046mx_active_calibration_profile ORDER BY machine_number,module,sv_state,state_code')).mappings()]
    context_actives=conn.execute(text('SELECT COUNT(*) FROM ht9046mx_context_active')).scalar()
hash_value=hashlib.sha256(json.dumps(active_rows,sort_keys=True,default=str).encode()).hexdigest()
report={'scope':'Technical GET/source SELECT tests, not manual workflow clicks','source_written':False,'existing_active_rows':len(active_rows),'existing_active_sha256':hash_value,'context_actives':context_actives,
        'jobs':{m:{'job_id':j['job_id'],'modules':j['result']['modules']} for m,j in jobs.items()},'parity':parity,'event_counts':event_counts,
        'load':{'clients':10,'requests':120,'successes':sum(r['status']==200 for r in results),'cache_state':'Warm after bounded first reads; parity already opened some day/model reads',
                'first_reads':first_reads,'first_p95_ms':float(np.quantile([r['ms'] for r in first_reads],.95)),
                'p50_ms':float(np.quantile([r['ms'] for r in results],.5)),'p95_ms':float(np.quantile([r['ms'] for r in results],.95)),'max_ms':max(r['ms'] for r in results),'responses':results}}
(OUT/'technical-qa.json').write_text(json.dumps(report,indent=2,default=str),encoding='utf-8')
print(json.dumps({k:v for k,v in report.items() if k not in {'jobs','load'}},default=str))
print(json.dumps({k:v for k,v in report['load'].items() if k!='responses'}))
