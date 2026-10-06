"""Read-only local audit/parity/load checks. All workflow actions use the UI."""
import hashlib,json,sys,time
from pathlib import Path
from datetime import datetime,timedelta
from concurrent.futures import ThreadPoolExecutor
from urllib.request import Request,urlopen
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from sqlalchemy import text
from apps.api.app.config import get_settings
from apps.api.app.db import connection
OUT=ROOT/'notebooks/outputs/sv_comparison_20261004'

def audit():
    with connection() as c:
        active=[dict(r) for r in c.execute(text('SELECT * FROM ht9046mx_active_calibration_profile ORDER BY machine_number,module,sv_state,state_code')).mappings()]
        rows=[dict(r) for r in c.execute(text("SELECT job_id,machine_number,module,status,progress_message,error_code,created_at,updated_at,result_json FROM ht9046mx_reference_review_job WHERE module=0 AND machine_number IN ('MX017','MX024') ORDER BY created_at DESC LIMIT 4")).mappings()]
        running=c.execute(text("SELECT COUNT(*) FROM ht9046mx_reference_review_job WHERE status IN ('PREVIEW_QUEUED','PREVIEW_RUNNING','BUILD_QUEUED','BUILD_RUNNING')")).scalar()
    value={'active_count':len(active),'active_sha256':hashlib.sha256(json.dumps(active,sort_keys=True,default=str).encode()).hexdigest(),'running':running,'jobs':[]}
    for r in rows:
        result=json.loads(r.pop('result_json') or '{}')
        r.update(selector=result.get('selector_version'),profiles=result.get('profiles'),modules=result.get('modules',[]))
        if r['status']=='COMPLETED' and r['selector']:
            with connection() as c:
                for m in r['modules']:
                    p=json.loads(c.execute(text('SELECT preview_json FROM ht9046mx_reference_review_job WHERE job_id=:job'),{'job':m['job_id']}).scalar())
                    d=p.get('diagnostics',{})
                    m['diagnostic_audit']={'intervals_saved':len(d.get('intervals',[])),'intervals_total':d.get('total_intervals'),'quality':d.get('quality'),'threshold':d.get('threshold'),'quarantine_threshold':d.get('quarantine_threshold'),'selected_proposal':p.get('reference_proposal',{}).get('selected')}
        value['jobs'].append(r)
    (OUT/'final-audit.json').write_text(json.dumps(value,indent=2,default=str),encoding='utf-8')
    print(json.dumps({**{k:v for k,v in value.items() if k!='jobs'},'jobs':[{k:v for k,v in r.items() if k!='modules'} for r in value['jobs']]},default=str))

def parity():
    from apps.api.app.reference_selector import propose
    from apps.api.app.reference_review import ReferencePreviewRequest,resolve_selection,bounds
    from apps.api.app.qualified_cache import day_key,unpack
    settings=get_settings()
    old={'__package__':'apps.api.app','__name__':'apps.api.app.reference_selector_before_vector'}
    exec((OUT/'reference_selector_before_vector.py').read_text(encoding='utf-8'),old)
    results=[]
    for machine,module in [('MX017',1),('MX017',8),('MX024',1),('MX024',6)]:
        selection=resolve_selection(ReferencePreviewRequest(idempotency_key='offline-parity-only',machine_number=machine,module=module),datetime(2026,10,1,2),settings)
        begin,end,_,_=bounds(selection);windows=[];day=begin
        with connection() as c:
            while day<end:
                payload=c.execute(text('SELECT payload FROM ht9046mx_qualified_day_cache WHERE day_key=:key AND module=:module'),{'key':day_key(settings,machine,day.date()),'module':module}).scalar()
                if payload:windows.extend(unpack(payload))
                day+=timedelta(days=1)
        stamp=time.perf_counter();before=old['propose'](windows,selection,settings);old_s=time.perf_counter()-stamp
        stamp=time.perf_counter();after=propose(windows,selection,settings);new_s=time.perf_counter()-stamp
        assert before==after,(machine,module,before,after)
        results.append({'machine':machine,'module':module,'windows':len(windows),'qualified_minutes':sum(w.eligible for w in windows),'exact_result_parity':True,'old_seconds':old_s,'vector_seconds':new_s,'selected':after['selected'],'needs_review':after['needs_review']})
        print(json.dumps(results[-1]),flush=True)
    (OUT/'selector-parity.json').write_text(json.dumps(results,indent=2),encoding='utf-8')

def load():
    with connection() as c:
        row=c.execute(text("SELECT job_id FROM ht9046mx_reference_review_job WHERE actor_id='MANUAL_QA_20261003' AND machine_number='MX024' AND module=1 AND result_json LIKE '%automatic_parent_id%' ORDER BY created_at DESC LIMIT 1")).mappings().one()
    url=f"http://127.0.0.1:8000/api/v1/calibration/reference/jobs/{row['job_id']}/raw?start=2026-09-19T05%3A28%3A00&end=2026-09-19T05%3A38%3A00"
    def read(_):
        t=time.perf_counter()
        with urlopen(Request(url,headers={'X-Approver-Id':'MANUAL_QA_20261003'}),timeout=30) as r:
            data=json.loads(r.read());assert r.status==200;assert data['observed_rows']==592
        return (time.perf_counter()-t)*1000
    first=read(0)
    with ThreadPoolExecutor(max_workers=10) as pool:times=sorted(pool.map(read,range(40)))
    receipt={'method':'GET only; owner-scoped actual Raw slice; 592 observed rows per response','clients':10,'requests':40,'success':40,'initial_ms':first,'p50_ms':times[20],'p95_ms':times[38],'max_ms':max(times)}
    (OUT/'raw-load.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8');print(json.dumps(receipt))

if __name__=='__main__':{'audit':audit,'parity':parity,'load':load}[sys.argv[1]]()
