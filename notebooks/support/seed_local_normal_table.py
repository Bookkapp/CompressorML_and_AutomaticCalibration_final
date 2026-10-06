"""Explicit owner-requested local source insertion, marked MOCK_NORMAL.

Plan by default; --apply inserts one batch atomically with an analytics receipt.
The batch contains only MX058/M1 and post-review, already elapsed seconds.
No future timestamps, overwrite, Active decision or fabricated healthy label.
"""
import argparse
from datetime import datetime, timedelta, timezone
import json
import math
from pathlib import Path
from zoneinfo import ZoneInfo

from sqlalchemy import bindparam, text
from sqlalchemy.engine import make_url

from apps.api.app.config import get_settings
from apps.api.app.context_profiles import assess_context
from apps.api.app.context_reference import get_profile
from apps.api.app.context_scope import state_of
from apps.api.app.db import get_engine, get_source_engine
from apps.api.app.inference import get_machine_candidates
from apps.api.app.observed_context import ObservedMinute, PHYSICAL
from apps.api.app.qualified_calibration import IDENTIFIER
from apps.api.app.unified_events import fingerprint
from notebooks.support.context_followup_qa import snapshot

PROFILE='2a7990dd1d81a251057980c219b64c2fa7a23ffeea91331d40b2b450d9656c4e'
OUT=Path(__file__).resolve().parents[1]/'outputs/normal_table_20261006'
LEDGER='ht9046mx_local_mock_batch'
MARKER='MOCK_NORMAL'
VERSION='local-normal-source-mock-v1'


def values(regime, minute):
    result={name:float(regime['center'][j]+.04*regime['scale'][j]*
        (math.sin(58*.137+minute*.045+j*.21)+.2*math.sin(minute*.19+j)))
        for j,name in enumerate(PHYSICAL) if name not in {'dp1','dp2'}}
    result.update(dp1=result['hp1']-result['lp1'],dp2=result['hp2']-result['lp2'])
    return result


def run(apply=False):
    settings=get_settings()
    for url in (settings.source_database_url,settings.database_url):
        if make_url(url).host not in {'localhost','127.0.0.1','::1'}:
            raise RuntimeError('This insertion is localhost-only')
    if settings.detector_worker_enabled or settings.detector_bridge_enabled or settings.detector_alerts_enabled:
        raise RuntimeError('Stop the live detector/alert bridge before source mock insertion')
    identifiers=[settings.source_db_name,settings.source_table,settings.analytics_db_name,
        settings.source_timestamp_column,settings.source_machine_column]
    if not all(IDENTIFIER.fullmatch(v) for v in identifiers):raise RuntimeError('Unsafe source mapping')
    model=get_profile(get_engine(),PROFILE)
    if model['machine_number']!='MX058' or model['module']!=1:raise RuntimeError('Wrong frozen Profile')
    ids=set(model['reference_review']['accepted_regime_ids'])
    regimes=[r for r in model['regimes'] if r['regime_id'] in ids and r['coverage_supported'] and state_of(r['context'])=='OFF']
    regime=max(regimes,key=lambda r:(r['days'],r['minutes'],r['regime_id']))
    zone=ZoneInfo(settings.source_timezone)
    now=datetime.now(zone).replace(tzinfo=None)
    start=datetime.fromisoformat(model['reference_review']['at']).astimezone(zone).replace(tzinfo=None,second=0,microsecond=0)+timedelta(minutes=1)
    end=(now-timedelta(seconds=settings.qualified_1m_late_arrival_seconds)).replace(second=0,microsecond=0)
    count=int((end-start).total_seconds())
    if count<=0 or count>86400 or start.date()!=now.date():raise RuntimeError('Expected an elapsed same-day post-review interval of at most one day')
    # Numerical probe uses Run only in memory. The inserted rows stay MOCK_NORMAL.
    probe=[]
    for i in range(count//60):
        at=start+timedelta(minutes=i)
        probe.append(ObservedMinute('MX058',1,at,at+timedelta(minutes=1),60,1.,1.,'PASS','',values(regime,i),
            {'compressor':{'run':60},'module':{'on':60},'busy':{'0':60},'sv':{'off':60}},'run|on|0|off',
            {'valve_mean':100.,'valve_min':100.,'valve_max':100.,'valve_samples':60}))
    points=assess_context(probe,[],model)
    if not all(p['category']=='WITHIN_PROPOSED_STEADY' for p in points):raise RuntimeError('Physical values do not match frozen Normal Reference')
    aliases=get_machine_candidates('MX058')
    table=f'`{settings.source_db_name}`.`{settings.source_table}`'
    ledger=f'`{settings.analytics_db_name}`.`{LEDGER}`'
    mc,tc=settings.source_machine_column,settings.source_timestamp_column
    overlap=text(f'SELECT COUNT(*) FROM {table} WHERE `{mc}` IN :aliases AND `{tc}`>=:start AND `{tc}`<:end').bindparams(bindparam('aliases',expanding=True))
    with get_source_engine().connect() as conn:
        existing=conn.execute(overlap,{'aliases':aliases,'start':start,'end':end}).scalar_one()
    if existing:raise RuntimeError(f'Interval already contains {existing} source rows; no overwrite or duplicate insertion')
    receipt={'version':VERSION,'source_kind':'MOCK','marker':MARKER,'approval_eligible':False,
        'machine_number':'MX058','module':1,'source_table':table,'start':start.isoformat(),'end_exclusive':end.isoformat(),
        'expected_rows':count,'cadence_seconds':1,'profile_id':PROFILE,'regime_id':regime['regime_id'],'seed':58,
        'numerical_probe_minutes':len(points),'numerical_probe_within_reference':len(points),
        'generated_modules':[1],'other_module_columns':'NULL; not fabricated','timezone':settings.source_timezone,
        'no_future_timestamps':True,'created_at':datetime.now(timezone.utc).isoformat()}
    receipt['batch_id']=fingerprint([VERSION,PROFILE,start,end,58])
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/'plan.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
    if not apply:return receipt
    before=snapshot()
    with get_engine().begin() as conn:
        conn.execute(text(f'CREATE TABLE IF NOT EXISTS {ledger} (batch_id CHAR(64) PRIMARY KEY, receipt_json LONGTEXT NOT NULL, created_at DATETIME(6) NOT NULL) ENGINE=InnoDB'))
    names=[mc,tc,settings.source_global_status_column,'Hp_1st_1','Lp_1st_1','Hp_2nd_1','Lp_2nd_1','Valve_1','TempHi_1','TempLo_1','Status_1','Busy_1','SV_1']
    if not all(IDENTIFIER.fullmatch(n) for n in names):raise RuntimeError('Unsafe configured column')
    insert=text(f'INSERT INTO {table} ('+','.join('`'+n+'`' for n in names)+') VALUES ('+','.join(':v'+str(i) for i in range(len(names)))+')')
    lock='ht9046mx-local-history-v1-058'
    with get_source_engine().connect() as conn:
        if conn.execute(text('SELECT GET_LOCK(:key,0)'),{'key':lock}).scalar_one()!=1:raise RuntimeError('Another local MX058 importer owns the lock')
        conn.commit()
        try:
            with conn.begin():
                if conn.execute(overlap,{'aliases':aliases,'start':start,'end':end}).scalar_one():raise RuntimeError('Source changed before insertion')
                minimum=None
                for offset in range(0,count,1000):
                    batch=[]
                    for second in range(offset,min(count,offset+1000)):
                        at=start+timedelta(seconds=second);v=values(regime,second//60)
                        vals=['HT9046MX-058',at,MARKER,v['hp1'],v['lp1'],v['hp2'],v['lp2'],100.,v['temphi'],v['templo'],'On','0','Off']
                        batch.append({'v'+str(i):val for i,val in enumerate(vals)})
                    result=conn.execute(insert,batch)
                    if minimum is None:minimum=result.lastrowid
                proof=conn.execute(text(f'SELECT COUNT(*) AS n, MIN(id) AS first_id, MAX(id) AS last_id, MIN(`{tc}`) AS first_at, MAX(`{tc}`) AS last_at FROM {table} WHERE `{mc}`=:machine AND `{tc}`>=:start AND `{tc}`<:end AND `{settings.source_global_status_column}`=:marker'),
                    {'machine':'HT9046MX-058','start':start,'end':end,'marker':MARKER}).mappings().one()
                if proof['n']!=count:raise RuntimeError('Inserted row count mismatch')
                receipt.update(inserted_rows=proof['n'],first_id=proof['first_id'],last_id=proof['last_id'],
                    first_at=proof['first_at'].isoformat(),last_at=proof['last_at'].isoformat())
                conn.execute(text(f'INSERT INTO {ledger} VALUES (:batch,:receipt,:stamp)'),
                    {'batch':receipt['batch_id'],'receipt':json.dumps(receipt),'stamp':datetime.now(timezone.utc).replace(tzinfo=None)})
        finally:
            conn.execute(text('SELECT RELEASE_LOCK(:key)'),{'key':lock});conn.commit()
    after=snapshot()
    if before!=after:raise RuntimeError('Profile/Active registry changed concurrently; source batch is committed and must be audited')
    receipt['profile_active_registry_unchanged']=True
    (OUT/'receipt.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
    (OUT/'registry-before.json').write_text(json.dumps(before,indent=2),encoding='utf-8')
    (OUT/'registry-after.json').write_text(json.dumps(after,indent=2),encoding='utf-8')
    return receipt


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--apply',action='store_true')
    print(json.dumps(run(parser.parse_args().apply),ensure_ascii=True,indent=2))
