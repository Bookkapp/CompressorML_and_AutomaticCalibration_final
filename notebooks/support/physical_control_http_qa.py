"""Read-only supplemental localhost load/audit; manual actions stay in GUI."""
import hashlib,json,sys,time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from urllib.request import Request,urlopen
from sqlalchemy import text
from apps.api.app.db import connection

OUT=Path(__file__).resolve().parents[1]/'outputs'/'physical_control_qa_20261004'
ACTOR='MANUAL_QA_PHYSICAL_20261004'

def audit():
    with connection() as c:
        active=[dict(r) for r in c.execute(text('SELECT * FROM ht9046mx_active_calibration_profile ORDER BY machine_number,module,sv_state,state_code')).mappings()]
        jobs=[dict(r) for r in c.execute(text("SELECT job_id,machine_number,module,status,progress_message,error_code,created_at,updated_at,selection_json,result_json FROM ht9046mx_reference_review_job WHERE actor_id=:actor ORDER BY created_at DESC"),{'actor':ACTOR}).mappings()]
    for j in jobs:
        selection=json.loads(j.pop('selection_json') or '{}');result=json.loads(j.pop('result_json') or '{}')
        j.update(selection_version=selection.get('version'),score_policy=selection.get('scoring_policy'),result=result)
    value={'active_count':len(active),'active_sha256':hashlib.sha256(json.dumps(active,sort_keys=True,default=str).encode()).hexdigest(),'jobs':jobs}
    (OUT/'final-audit.json').write_text(json.dumps(value,indent=2,default=str),encoding='utf-8')
    print(json.dumps({'active_count':value['active_count'],'active_sha256':value['active_sha256'],'parents':[{k:v for k,v in j.items() if k not in ('result','score_policy')} for j in jobs if j['module']==0]},default=str))

def load():
    with connection() as c:
        job=c.execute(text("SELECT job_id FROM ht9046mx_reference_review_job WHERE actor_id=:actor AND machine_number='MX017' AND module=1 AND result_json LIKE '%automatic_parent_id%' ORDER BY created_at DESC LIMIT 1"),{'actor':ACTOR}).scalar_one()
    url=f'http://127.0.0.1:8000/api/v1/calibration/reference/jobs/{job}/raw?start=2026-09-29T23%3A30%3A00&end=2026-09-30T00%3A00%3A00'
    def read(_):
        stamp=time.perf_counter()
        with urlopen(Request(url,headers={'X-Approver-Id':ACTOR}),timeout=30) as r:
            data=json.loads(r.read());assert r.status==200
            assert data['observed_rows']==1775 and data['unique_seconds']==1775
        return (time.perf_counter()-stamp)*1000
    initial=read(0)
    with ThreadPoolExecutor(max_workers=10) as pool:times=sorted(pool.map(read,range(40)))
    receipt={'method':'GET only; 30-minute actual-source Raw, 1775 rows per response; workflow GUI only','clients':10,'requests':40,'successful':40,'initial_ms':initial,'p50_ms':times[20],'p95_ms':times[38],'max_ms':max(times)}
    (OUT/'raw-load.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8');print(json.dumps(receipt))

if __name__=='__main__':{'audit':audit,'load':load}[sys.argv[1]]()
