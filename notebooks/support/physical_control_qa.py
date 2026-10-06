"""Read-only actual-cache regression. UI is the only workflow action source."""
import sys,json,hashlib,time
from pathlib import Path
from datetime import datetime,timedelta
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from sqlalchemy import text
from apps.api.app.config import get_settings
from apps.api.app.db import connection
from apps.api.app.qualified_cache import day_key,unpack
from apps.api.app.reference_review import ReferencePreviewRequest,resolve_selection,bounds,selected_candidate,make_preview
from apps.api.app.reference_selector import propose
from apps.api.app.qualified_scoring import ApprovedProfile,QualifiedShadowScorer
from apps.api.app.qualified_policy import THRESHOLD_VERSION
from apps.api.app.qualified_windows import FEATURES,STATE_CODE,WINDOW_VERSION
OUT=ROOT/'notebooks/outputs/physical_control_qa_20261004';OUT.mkdir(parents=True,exist_ok=True)

def audit(name):
    with connection() as c:
        rows=[dict(r) for r in c.execute(text('SELECT * FROM ht9046mx_active_calibration_profile ORDER BY machine_number,module,sv_state,state_code')).mappings()]
        running=[dict(r) for r in c.execute(text("SELECT job_id,machine_number,module,status,progress_message FROM ht9046mx_reference_review_job WHERE status IN ('PREVIEW_QUEUED','PREVIEW_RUNNING','BUILD_QUEUED','BUILD_RUNNING')")).mappings()]
    value={'active_count':len(rows),'active_sha256':hashlib.sha256(json.dumps(rows,sort_keys=True,default=str).encode()).hexdigest(),'running':running}
    (OUT/f'{name}.json').write_text(json.dumps(value,indent=2,default=str),encoding='utf-8');print(json.dumps(value))

def replay():
    settings=get_settings();results=[]
    for machine in ['MX017','MX024']:
        for module in range(1,9):
            s=resolve_selection(ReferencePreviewRequest(idempotency_key='offline-policy-qa',machine_number=machine,module=module),datetime(2026,10,1,16),settings)
            start,_,_,end=bounds(s);rows=[];day=start
            with connection() as c:
                while day<end:
                    payload=c.execute(text('SELECT payload FROM ht9046mx_qualified_day_cache WHERE day_key=:key AND module=:module'),{'key':day_key(settings,machine,day.date()),'module':module}).scalar()
                    if payload is None:raise ValueError(f'Missing cache {machine} M{module} {day}')
                    rows.extend(unpack(payload));day+=timedelta(days=1)
            stamp=time.perf_counter();proposal=propose(rows,s,settings)
            if proposal['changed']:
                s=resolve_selection(ReferencePreviewRequest(idempotency_key='offline-policy-qa',machine_number=machine,module=module,
                    reference_start=datetime.fromisoformat(proposal['selected']['start']).date(),reference_end=datetime.fromisoformat(proposal['selected']['end']).date()),datetime(2026,10,1,16),settings)
                start,_,_,end=bounds(s);rows=[w for w in rows if start<=w.window_start<end]
            c=selected_candidate(rows,s,settings);p=make_preview(rows,s,settings,candidate=c)
            shadow_start=datetime.fromisoformat(s['shadow_start']);exact=p['baseline'];differences=0
            if exact and c['threshold']['deviation_score_q995']:
                profile=ApprovedProfile(999999,'OFFLINE_NOT_ACTIVE',WINDOW_VERSION,machine,module,'Off',STATE_CODE,
                    {f:exact[f]['median'] for f in FEATURES},{f:exact[f]['scale'] for f in FEATURES},c['threshold']['deviation_score_q995'],THRESHOLD_VERSION,
                    profile_fit_end=datetime.fromisoformat(s['reference_end']))
                scorer=QualifiedShadowScorer();expected={r.minute:r for r in c['shadow'].itertuples()}
                for w in rows:
                    if w.window_start<shadow_start:continue
                    got=scorer.score(w,profile);want=expected[w.window_start]
                    if w.eligible:
                        differences+=int(got.primary_score!=want.deviation_score or got.primary_raw_flag!=bool(want.raw_flag) or got.primary_persistent_flag!=bool(want.persistent_flag))
                assert differences==0,(machine,module,differences)
            result={'machine':machine,'module':module,'summary':p['summary'],'threshold':p['diagnostics']['threshold'],
                'reference_changed':proposal['changed'],'reference_needs_review':proposal['needs_review'],'reference_proposal':proposal['selected'],
                'control':p['diagnostics']['control'],'recovery':p['diagnostics']['recovery'],'reasons':p['reason_codes'],
                'scorer_differences':differences,'calculation_seconds':round(time.perf_counter()-stamp,3)}
            results.append(result);print(json.dumps({k:v for k,v in result.items() if k not in ('recovery','reference_proposal','reasons')},ensure_ascii=True),flush=True)
    (OUT/'actual-cache-replay.json').write_text(json.dumps(results,indent=2,ensure_ascii=False),encoding='utf-8')

if __name__=='__main__':
    if len(sys.argv)>1 and sys.argv[1]=='replay':replay()
    else:audit(sys.argv[1] if len(sys.argv)>1 else 'before')
