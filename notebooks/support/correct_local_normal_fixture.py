"""Owner correction: remove the future/Active trial; elapsed Normal rows only.

Plan by default. --apply backs up the exact test records before an atomic local
source/metadata correction. No original Profile, reference review or real source
row is deleted. Synthetic provenance stays in the batch ledger, not a new UI.
"""
import argparse,gzip,json
from datetime import datetime,timedelta,timezone
from pathlib import Path
from zoneinfo import ZoneInfo
from sqlalchemy import text,bindparam
from apps.api.app.config import get_settings
from apps.api.app.context_reference import get_profile
from apps.api.app.context_scope import state_of
from apps.api.app.context_profiles import assess_context
from apps.api.app.context_storage import unpack
from apps.api.app.db import get_engine,get_source_engine
from apps.api.app.inference import get_machine_candidates
from apps.api.app.observed_context import ObservedMinute
from apps.api.app.qualified_calibration import IDENTIFIER
from apps.api.app.unified_events import append_events,make_event,fingerprint
from notebooks.support.seed_local_normal_table import PROFILE,LEDGER,values
from notebooks.support.context_followup_qa import snapshot

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'notebooks/outputs/normal_manual_20261006'
FULL=ROOT/'notebooks/outputs/full_normal_trial_20261006/receipt.json'
OLD=ROOT/'notebooks/outputs/normal_table_20261006/receipt.json'
VERSION='elapsed-normal-manual-fixture-v1'


def serial(value):
    if isinstance(value,bytes):return {'bytes_hex':value.hex()}
    return value.isoformat() if hasattr(value,'isoformat') else str(value)


def run(apply=False):
    cfg=get_settings()
    if cfg.source_db_host not in {'localhost','127.0.0.1','::1'} or cfg.analytics_db_host not in {'localhost','127.0.0.1','::1'}:
        raise RuntimeError('Local computer only')
    if cfg.source_db_port!=cfg.analytics_db_port or cfg.detector_worker_enabled or cfg.detector_bridge_enabled or cfg.detector_alerts_enabled:
        raise RuntimeError('Require the same local SQL server with worker/bridge/alerts disabled')
    names=[cfg.source_db_name,cfg.source_table,cfg.analytics_db_name,cfg.source_machine_column,cfg.source_timestamp_column,cfg.source_global_status_column]
    if not all(IDENTIFIER.fullmatch(n) for n in names):raise RuntimeError('Unsafe mapping')
    future=json.loads(FULL.read_text(encoding='utf-8'));old=json.loads(OLD.read_text(encoding='utf-8'))
    trial_id=future['trial_id'];source=f'`{cfg.source_db_name}`.`{cfg.source_table}`';adb='`'+cfg.analytics_db_name+'`'
    mc,tc,sc=cfg.source_machine_column,cfg.source_timestamp_column,cfg.source_global_status_column
    now=datetime.now(ZoneInfo(cfg.source_timezone)).replace(tzinfo=None)
    end=now.replace(second=0,microsecond=0);start=datetime.fromisoformat(old['end_exclusive'])
    original_start=datetime.fromisoformat(old['start'])
    if now.date().isoformat()!='2026-10-06' or not start<end or end-start>timedelta(days=1):raise RuntimeError('Same-day elapsed fixture only')
    model=get_profile(get_engine(),PROFILE)
    accepted=set(model['reference_review']['accepted_regime_ids'])
    regime=max((r for r in model['regimes'] if r['coverage_supported'] and r['regime_id'] in accepted and state_of(r['context'])=='OFF'),key=lambda r:(r['days'],r['minutes'],r['regime_id']))
    count=int((end-start).total_seconds());nminutes=int((end-original_start).total_seconds()/60)
    windows=[ObservedMinute('MX058',1,original_start+timedelta(minutes=i),original_start+timedelta(minutes=i+1),60,1.,1.,'PASS','',values(regime,i),
        {'compressor':{'run':60},'module':{'on':60},'busy':{'0':60},'sv':{'off':60}},'run|on|0|off',{'valve_mean':100.}) for i in range(nminutes)]
    points=assess_context(windows,[],model)
    if not all(p['category']=='WITHIN_PROPOSED_STEADY' for p in points):raise RuntimeError('Normal fixture does not match frozen Reference')
    plan={'version':VERSION,'machine_number':'MX058','module':1,'created_at':datetime.now(timezone.utc).isoformat(),
        'source_kind':'MOCK','raw_status':'Run','module_status':'On','sv':'Off','busy':'0','other_modules':'NULL',
        'original_start':original_start.isoformat(),'extension_start':start.isoformat(),'end_exclusive':end.isoformat(),
        'last_at':(end-timedelta(seconds=1)).isoformat(),'extension_rows':count,'normal_minutes':nminutes,
        'normal_probe_flagged_minutes':sum(p['category']!='WITHIN_PROPOSED_STEADY' for p in points),
        'future_rows_to_remove':future['inserted_rows'],'trial_profile_to_remove':trial_id,'no_future_timestamps':True,
        'manual_approval_only':True,'virtual_clock_removed':True,'approval_eligible':False}
    OUT.mkdir(parents=True,exist_ok=True);(OUT/'plan.json').write_text(json.dumps(plan,indent=2),encoding='utf-8')
    if not apply:return plan
    before=snapshot()
    where=f'id BETWEEN :lo AND :hi AND `{mc}`=:machine AND `{sc}`=:marker'
    fparams={'lo':future['first_id'],'hi':future['last_id'],'machine':'HT9046MX-058','marker':'MOCK_NORMAL'}
    oparams={'lo':old['first_id'],'hi':old['last_id'],'machine':'HT9046MX-058','marker':'MOCK_NORMAL'}
    with get_source_engine().connect() as conn:
        verified=conn.execute(text(f'SELECT COUNT(*) FROM {source} WHERE {where}'),fparams).scalar_one()
        old_count=conn.execute(text(f'SELECT COUNT(*) FROM {source} WHERE {where}'),oparams).scalar_one()
        if verified!=future['inserted_rows'] or old_count!=old['inserted_rows']:raise RuntimeError('Fixture changed; correction cancelled')
        # Store exact raw rows, including the NULL columns, for reversible removal.
        with gzip.open(OUT/'future-source-backup.jsonl.gz','wt',encoding='utf-8') as archive:
            for offset in range(future['first_id'],future['last_id']+1,5000):
                rows=conn.execute(text(f'SELECT * FROM {source} WHERE {where} ORDER BY id'),{**fparams,'lo':offset,'hi':min(offset+4999,future['last_id'])}).mappings()
                for row in rows:archive.write(json.dumps(dict(row),default=serial,separators=(',',':'))+'\n')
    tables=['ht9046mx_context_active','ht9046mx_context_profile','ht9046mx_local_mock_trial']
    backup={}
    with get_engine().connect() as conn:
        for table in tables:
            col='trial_id' if table=='ht9046mx_local_mock_trial' else 'profile_id'
            backup[table]=[dict(r) for r in conn.execute(text(f'SELECT * FROM `{table}` WHERE `{col}`=:id'),{'id':trial_id}).mappings()]
        job=conn.execute(text('SELECT * FROM ht9046mx_reference_review_job WHERE job_id=:job'),{'job':'ccb29671-cec0-457b-8ebb-59f171d00d5b'}).mappings().first()
        if job:
            req=json.loads(job['request_json']);result=json.loads(job['result_json'])
            if req.get('parent_profile_id')!=PROFILE or not any(d.get('categories',{}).get('MOCK_DATA',0) for d in result.get('daily',[])):
                raise RuntimeError('Unexpected interim job')
            backup['old_interim_job']=[dict(job)]
    if len(backup['ht9046mx_context_active'])!=1 or backup['ht9046mx_context_active'][0]['previous_profile_id'] is not None:
        raise RuntimeError('Actual Active pointer changed; correction cancelled')
    if len(backup['ht9046mx_context_profile'])!=1 or unpack(backup['ht9046mx_context_profile'][0]['payload']).get('source_kind')!='MOCK':
        raise RuntimeError('Not the exact synthetic Profile')
    (OUT/'metadata-backup.json').write_text(json.dumps(backup,default=serial,indent=2),encoding='utf-8')
    overlap=text(f'SELECT COUNT(*) FROM {source} WHERE `{mc}` IN :aliases AND `{tc}`>=:start AND `{tc}`<:end').bindparams(bindparam('aliases',expanding=True))
    aliases={'aliases':get_machine_candidates('MX058'),'start':start,'end':end}
    columns=[mc,tc,sc,'Hp_1st_1','Lp_1st_1','Hp_2nd_1','Lp_2nd_1','Valve_1','TempHi_1','TempLo_1','Status_1','Busy_1','SV_1']
    insert=text(f'INSERT INTO {source} ('+','.join('`'+c+'`' for c in columns)+') VALUES ('+','.join(':v'+str(i) for i in range(len(columns)))+')')
    with get_source_engine().connect() as conn:
        lock='ht9046mx-local-history-v1-058'
        if conn.execute(text('SELECT GET_LOCK(:lock,0)'),{'lock':lock}).scalar_one()!=1:raise RuntimeError('MX058 importer is busy')
        conn.commit()
        try:
            with conn.begin():
                ptr=conn.execute(text(f'SELECT * FROM {adb}.ht9046mx_context_active WHERE machine_number=:machine AND module=1 FOR UPDATE'),{'machine':'MX058'}).mappings().one()
                if dict(ptr)!=backup['ht9046mx_context_active'][0]:raise RuntimeError('Active changed after backup')
                if conn.execute(overlap,aliases).scalar_one():raise RuntimeError('Do not overlap existing sensor data')
                removed=conn.execute(text(f'DELETE FROM {source} WHERE {where}'),fparams).rowcount
                if removed!=future['inserted_rows']:raise RuntimeError('Future fixture removal count mismatch')
                changed=conn.execute(text(f'UPDATE {source} SET `{sc}`=:normal WHERE {where}'),{**oparams,'normal':'Run'}).rowcount
                if changed!=old['inserted_rows']:raise RuntimeError('Existing same-day fixture changed')
                for offset in range(0,count,1000):
                    batch=[]
                    for second in range(offset,min(count,offset+1000)):
                        at=start+timedelta(seconds=second);v=values(regime,int((at-original_start).total_seconds())//60)
                        row=['HT9046MX-058',at,'Run',v['hp1'],v['lp1'],v['hp2'],v['lp2'],100.,v['temphi'],v['templo'],'On','0','Off']
                        batch.append({'v'+str(i):x for i,x in enumerate(row)})
                    conn.execute(insert,batch)
                proof=dict(conn.execute(text(f'SELECT COUNT(*) AS n,MIN(id) AS first_id,MAX(id) AS last_id FROM {source} WHERE `{mc}`=:machine AND `{tc}`>=:start AND `{tc}`<:end'),{'machine':'HT9046MX-058','start':start,'end':end}).mappings().one())
                if proof['n']!=count:raise RuntimeError('Extension count mismatch')
                plan.update(inserted_rows=count,first_id=proof['first_id'],last_id=proof['last_id'],future_rows_removed=removed,converted_rows=changed)
                for table in tables:
                    col='trial_id' if table=='ht9046mx_local_mock_trial' else 'profile_id'
                    conn.execute(text(f'DELETE FROM {adb}.`{table}` WHERE `{col}`=:id'),{'id':trial_id})
                if backup.get('old_interim_job'):
                    conn.execute(text(f'DELETE FROM {adb}.ht9046mx_reference_review_job WHERE job_id=:job'),{'job':'ccb29671-cec0-457b-8ebb-59f171d00d5b'})
                ledger=f'{adb}.`{LEDGER}`'
                fvoid={**future,'state':'REMOVED_AT_OWNER_REQUEST','removed_at':plan['created_at'],'backup':str(OUT/'future-source-backup.jsonl.gz')}
                oretained={**old,'raw_status_after':'Run','retained_as_elapsed_normal_fixture':True,'updated_at':plan['created_at']}
                for batch_id,receipt in ((future['batch_id'],fvoid),(old['batch_id'],oretained)):
                    conn.execute(text(f'UPDATE {ledger} SET receipt_json=:receipt WHERE batch_id=:id'),{'id':batch_id,'receipt':json.dumps(receipt)})
                plan['batch_id']=fingerprint([VERSION,PROFILE,start,end])
                conn.execute(text(f'INSERT INTO {ledger} VALUES (:id,:receipt,:stamp)'),{'id':plan['batch_id'],'receipt':json.dumps(plan),'stamp':datetime.now(timezone.utc).replace(tzinfo=None)})
                audit=make_event(source_key=[trial_id,'removed-at-owner-request',plan['batch_id']],machine='MX058',module=1,
                    occurred_at=datetime.now(timezone.utc),timezone_name=cfg.source_timezone,family='PROFILE',event_type='MOCK_TRIAL_REMOVED',
                    mode='LOCAL_REHEARSAL',assessment='TEST_REMOVED',details={'profile_id':trial_id,'source_kind':'MOCK',
                        'future_rows_removed':removed,'elapsed_normal_rows_added':count,'actual_active_removed':True,'manual_approval_only':True})
                append_events(conn.execution_options(schema_translate_map={None:cfg.analytics_db_name}),[audit])
        finally:
            conn.execute(text('SELECT RELEASE_LOCK(:lock)'),{'lock':lock});conn.commit()
    after=snapshot();expected=json.loads((FULL.parent/'registry-before.json').read_text(encoding='utf-8'))
    if after!=expected:raise RuntimeError('Original registry did not restore exactly; inspect committed correction')
    plan.update(original_registry_restored_exactly=True,actual_context_active_count=after['context_active_count'])
    for name,data in [('receipt',plan),('registry-before',before),('registry-after',after)]:
        (OUT/(name+'.json')).write_text(json.dumps(data,indent=2),encoding='utf-8')
    return plan


def extend_elapsed(apply=False):
    """One bounded continuation to the real current minute; no running generator."""
    cfg=get_settings();saved=json.loads((OUT/'receipt.json').read_text(encoding='utf-8'))
    if cfg.source_db_host not in {'127.0.0.1','localhost','::1'} or cfg.analytics_db_host not in {'127.0.0.1','localhost','::1'}:
        raise RuntimeError('Local fixture only')
    if cfg.source_db_port!=cfg.analytics_db_port or cfg.detector_worker_enabled or cfg.detector_bridge_enabled or cfg.detector_alerts_enabled:
        raise RuntimeError('Require local SQL with worker/bridge/alerts disabled')
    now=datetime.now(ZoneInfo(cfg.source_timezone)).replace(tzinfo=None)
    start=datetime.fromisoformat(saved['end_exclusive']);end=now.replace(second=0,microsecond=0)
    if start.date()!=now.date() or not 0<=(end-start).total_seconds()<=3600:raise RuntimeError('Bounded same-day continuation only')
    n=int((end-start).total_seconds())
    if not n:return saved
    model=get_profile(get_engine(),PROFILE);ids=set(model['reference_review']['accepted_regime_ids'])
    regime=max((r for r in model['regimes'] if r['coverage_supported'] and r['regime_id'] in ids and state_of(r['context'])=='OFF'),key=lambda r:(r['days'],r['minutes'],r['regime_id']))
    original=datetime.fromisoformat(saved['original_start'])
    piece={'version':VERSION,'source_kind':'MOCK','raw_status':'Run','start':start.isoformat(),'end_exclusive':end.isoformat(),
        'inserted_rows':n,'no_future_timestamps':True,'machine_number':'MX058','module':1,'manual_approval_only':True}
    if not apply:return piece
    names=[cfg.source_db_name,cfg.source_table,cfg.analytics_db_name,cfg.source_machine_column,cfg.source_timestamp_column,cfg.source_global_status_column]
    if not all(IDENTIFIER.fullmatch(x) for x in names):raise RuntimeError('Unsafe mapping')
    source=f'`{cfg.source_db_name}`.`{cfg.source_table}`';ledger=f'`{cfg.analytics_db_name}`.`{LEDGER}`'
    mc,tc,sc=cfg.source_machine_column,cfg.source_timestamp_column,cfg.source_global_status_column
    columns=[mc,tc,sc,'Hp_1st_1','Lp_1st_1','Hp_2nd_1','Lp_2nd_1','Valve_1','TempHi_1','TempLo_1','Status_1','Busy_1','SV_1']
    insert=text(f'INSERT INTO {source} ('+','.join('`'+x+'`' for x in columns)+') VALUES ('+','.join(':v'+str(i) for i in range(len(columns)))+')')
    overlap=text(f'SELECT COUNT(*) FROM {source} WHERE `{mc}` IN :aliases AND `{tc}`>=:start AND `{tc}`<:end').bindparams(bindparam('aliases',expanding=True))
    before=snapshot()
    with get_source_engine().connect() as conn:
        key='ht9046mx-local-history-v1-058'
        if conn.execute(text('SELECT GET_LOCK(:key,0)'),{'key':key}).scalar_one()!=1:raise RuntimeError('Importer is busy')
        conn.commit()
        try:
            with conn.begin():
                if conn.execute(overlap,{'aliases':get_machine_candidates('MX058'),'start':start,'end':end}).scalar_one():
                    raise RuntimeError('Do not overwrite or duplicate real source rows')
                for offset in range(0,n,1000):
                    batch=[]
                    for second in range(offset,min(n,offset+1000)):
                        at=start+timedelta(seconds=second);v=values(regime,int((at-original).total_seconds())//60)
                        row=['HT9046MX-058',at,'Run',v['hp1'],v['lp1'],v['hp2'],v['lp2'],100.,v['temphi'],v['templo'],'On','0','Off']
                        batch.append({'v'+str(i):x for i,x in enumerate(row)})
                    conn.execute(insert,batch)
                proof=dict(conn.execute(text(f'SELECT COUNT(*) AS n,MIN(id) AS first_id,MAX(id) AS last_id FROM {source} WHERE `{mc}`=:machine AND `{tc}`>=:start AND `{tc}`<:end'),{'machine':'HT9046MX-058','start':start,'end':end}).mappings().one())
                if proof['n']!=n:raise RuntimeError('Continuation count mismatch')
                piece.update(first_id=proof['first_id'],last_id=proof['last_id'],batch_id=fingerprint([VERSION,'continuation',start,end]))
                conn.execute(text(f'INSERT INTO {ledger} VALUES (:id,:receipt,:at)'),{'id':piece['batch_id'],'receipt':json.dumps(piece),'at':datetime.now(timezone.utc).replace(tzinfo=None)})
        finally:
            conn.execute(text('SELECT RELEASE_LOCK(:key)'),{'key':key});conn.commit()
    if snapshot()!=before:raise RuntimeError('Unexpected Profile registry change')
    if not (OUT/'correction-receipt.json').exists():(OUT/'correction-receipt.json').write_text(json.dumps(saved,indent=2),encoding='utf-8')
    saved.update(end_exclusive=end.isoformat(),last_at=(end-timedelta(seconds=1)).isoformat(),normal_minutes=int((end-original).total_seconds())//60,
        extensions=[*saved.get('extensions',[]),piece])
    (OUT/'receipt.json').write_text(json.dumps(saved,indent=2),encoding='utf-8')
    return saved


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--apply',action='store_true');p.add_argument('--extend',action='store_true');args=p.parse_args()
    print(json.dumps(extend_elapsed(args.apply) if args.extend else run(args.apply),indent=2,ensure_ascii=False))
