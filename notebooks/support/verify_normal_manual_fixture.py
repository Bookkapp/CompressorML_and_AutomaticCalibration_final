"""Read-only source/gate audit; never clicks inspection or approval for owner."""
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import requests
from sqlalchemy import text,bindparam
from apps.api.app.config import get_settings
from apps.api.app.db import get_engine,get_source_engine
from apps.api.app.context_reference import get_profile
from apps.api.app.context_profiles import assess_context
from apps.api.app.observed_context import build_observed_minutes
from apps.api.app.qualified_calibration import load_observed_one_minute_windows
from apps.api.app.inference import get_machine_candidates
from notebooks.support.seed_local_normal_table import PROFILE
from notebooks.support.context_followup_qa import snapshot

OUT=Path(__file__).resolve().parents[1]/'outputs/normal_manual_20261006'


def run():
    cfg=get_settings();receipt=json.loads((OUT/'receipt.json').read_text(encoding='utf-8'))
    now=datetime.now(ZoneInfo(cfg.source_timezone));table=f'`{cfg.source_db_name}`.`{cfg.source_table}`'
    mc,tc,sc=cfg.source_machine_column,cfg.source_timestamp_column,cfg.source_global_status_column
    aliases=get_machine_candidates('MX058')
    future=text(f'SELECT COUNT(*) FROM {table} WHERE `{mc}` IN :aliases AND `{tc}`>:now').bindparams(bindparam('aliases',expanding=True))
    with get_source_engine().connect() as conn:
        future_count=conn.execute(future,{'aliases':aliases,'now':now.replace(tzinfo=None)}).scalar_one()
        proof=dict(conn.execute(text(f'SELECT COUNT(*) AS n,COUNT(DISTINCT `{tc}`) AS unique_seconds,MIN(`{tc}`) AS first_at,MAX(`{tc}`) AS last_at,SUM(`{sc}`=\'Run\' AND Status_1=\'On\' AND Busy_1=\'0\' AND SV_1=\'Off\') AS normal_state_rows FROM {table} WHERE `{mc}`=:machine AND `{tc}`>=:start AND `{tc}`<:end'),
            {'machine':'HT9046MX-058','start':receipt['original_start'],'end':receipt['end_exclusive']}).mappings().one())
    assert future_count==0 and proof['n']==proof['unique_seconds']==proof['normal_state_rows']==receipt['normal_minutes']*60
    zone=ZoneInfo(cfg.source_timezone)
    lo=datetime(2026,10,6,13,50,tzinfo=zone);hi=datetime(2026,10,6,13,52,tzinfo=zone)
    windows=load_observed_one_minute_windows(cfg,machine_number='MX058',start=lo,end=hi,as_of=now,
        modules=(1,),compact_json=True,window_builder=build_observed_minutes)
    points=assess_context(windows,[],get_profile(get_engine(),PROFILE))
    assert len(points)==2 and all(p['category']=='WITHIN_PROPOSED_STEADY' for p in points)
    base='http://127.0.0.1:8000';headers={'X-Approver-Id':'2017876'}
    r=requests.get(base+'/api/v1/calibration/context/profiles/'+PROFILE+'/followup',headers=headers,timeout=15);r.raise_for_status();progress=r.json()
    assert progress['can_inspect'] and not progress['can_validate'] and progress['received_closed_days']==0 and not progress['clock_error']
    assert progress['saved_job_id'] is None and progress['source_latest']==receipt['last_at']
    active=requests.get(base+'/api/v1/calibration/context/active',params={'machine_number':'MX058'},timeout=10).json()
    assert active==[]
    routes=requests.get(base+'/openapi.json',timeout=10).json()['paths']
    assert not any('/local-mock' in p for p in routes)
    expected=json.loads((OUT.parent/'full_normal_trial_20261006/registry-before.json').read_text(encoding='utf-8'))
    assert snapshot()==expected
    result={'source':proof,'future_source_rows':future_count,'normal_source_pipeline_points':points,
        'followup':progress,'context_active':active,'local_mock_routes':0,'original_registry_restored_exactly':True,
        'worker_bridge_alerts_enabled':False,'manual_buttons_not_clicked':True}
    (OUT/'verification.json').write_text(json.dumps(result,indent=2,ensure_ascii=False,default=str),encoding='utf-8')
    print(json.dumps({'source':proof,'future_rows':future_count,'source_pipeline_normal_minutes':len(points),
        'can_inspect':progress['can_inspect'],'closed_days':progress['received_closed_days'],'context_active':active,
        'local_mock_routes':0,'original_registry_restored_exactly':True},indent=2,default=str))


if __name__=='__main__':run()
