"""Local-only MySQL rehearsal on actual archived MX080/M6 seconds.

Writes ONLY a dedicated QA schema. Candidate is not a valid Active Profile.
No source/Profile/production PM table, threshold or model is changed.
"""
import json
from dataclasses import asdict, replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from time import perf_counter
from uuid import uuid4
import pandas as pd
from sqlalchemy import Column, DateTime, Integer, MetaData, String, Table, Text, create_engine, select, text
from sqlalchemy.engine import make_url
from apps.api.app.config import Settings
from apps.api.app.qualified_detector import DurableDetector, ObservedSourceReader
from apps.api.app.qualified_bridge import DashboardBridge, windows, episodes
from apps.api.app.qualified_archive import export_episode, verify_export, retention_inventory
from apps.api.app.qualified_persistence import canonical
from apps.api.app.qualified_scoring import QualifiedShadowScorer
from apps.api.app.qualified_windows import WindowPolicy, build_completed_windows
from notebooks.support.case_incremental_replay import rows080, candidate, ZONE

QA_SCHEMA='ht9046mx_detector_qa_20261001'


def run():
    settings=Settings(_env_file='apps/api/.env')
    if settings.analytics_db_host not in {'localhost','127.0.0.1','::1'}:
        raise RuntimeError('Localhost only; no target-Server QA in this script')
    admin=create_engine(settings.database_url,pool_pre_ping=True)
    with admin.begin() as c:
        c.execute(text(f'CREATE DATABASE IF NOT EXISTS `{QA_SCHEMA}` CHARACTER SET utf8mb4'))
    admin.dispose()
    engine=create_engine(make_url(settings.database_url).set(database=QA_SCHEMA),pool_pre_ping=True)
    calibration=[]
    for day in pd.date_range('2026-09-03','2026-09-06'):
        start=day.to_pydatetime()
        calibration+=build_completed_windows(rows080(start,start+timedelta(days=1)),
            as_of=(start+timedelta(days=1)).replace(tzinfo=ZONE),policy=WindowPolicy('Asia/Bangkok'),modules=(6,))
    status,profile=candidate(calibration,'MX080',6,datetime(2026,9,3),datetime(2026,9,7),datetime(2026,9,8))
    nonce=uuid4().hex[:12]
    profile=replace(profile,profile_version=f'LOCAL_CASE_NOT_ACTIVE_{nonce}')
    profiles={('MX080',6):profile}
    left,right=datetime(2026,9,7,11,45),datetime(2026,9,7,13)
    raw=list(rows080(left,right))
    m=MetaData()
    source=Table(f'qa_source_{nonce}',m,Column('id',Integer,primary_key=True),
        Column('recorded_at',DateTime),Column('machine_number',String(32)),Column('Status',String(32)),
        *[Column(key,String(64) if key in {'Status_6','Busy_6','SV_6'} else String(64))
          for key in raw[0] if key not in {'recorded_at','machine_number','Status'}])
    m.create_all(engine)
    with engine.begin() as c:
        c.execute(source.insert(),[{'id':i+1,**row} for i,row in enumerate(raw)])
    reader_settings=settings.model_copy(update={'source_table':source.name,'source_timestamp_column':'recorded_at',
        'source_machine_column':'machine_number','source_global_status_column':'Status'})
    reader=ObservedSourceReader(engine,reader_settings)
    detector=DurableDetector(engine,WindowPolicy('Asia/Bangkok',late_arrival_seconds=30),mode='LOCAL_REHEARSAL')
    detector.create_tables()
    bridge=DashboardBridge(engine,engine,alerts_enabled=False); bridge.create_tables()
    clock=left+timedelta(minutes=5); times=[]; retries=crashes=0; run_id=None
    while clock<=right:
        began=perf_counter()
        run_id=detector.initialize('MX080',(6,),profiles)
        fetched=reader.read('MX080',left,clock,(6,))
        if clock==left+timedelta(minutes=10):
            before=detector.store.points(run_id)
            def crash(): raise RuntimeError('QA_CRASH')
            try: detector.cycle(run_id,fetched,as_of=clock.replace(tzinfo=ZONE),profiles=profiles,before_commit=crash)
            except RuntimeError as exc:
                assert str(exc)=='QA_CRASH'; crashes+=1
            assert detector.store.points(run_id)==before
        detector.poll(reader,'MX080',as_of=clock.replace(tzinfo=ZONE),profiles=profiles)
        detector.poll(reader,'MX080',as_of=clock.replace(tzinfo=ZONE),profiles=profiles); retries+=1
        bridge.deliver(now=clock.replace(tzinfo=ZONE),limit=10000)
        engine.dispose()
        detector=DurableDetector(engine,detector.policy,mode='LOCAL_REHEARSAL')
        bridge=DashboardBridge(engine,engine,alerts_enabled=False)
        times.append((perf_counter()-began)*1000); clock+=timedelta(minutes=5)
    detector.cycle(run_id,[],as_of=(right+timedelta(seconds=30)).replace(tzinfo=ZONE),profiles=profiles)
    bridge.deliver(now=right.replace(tzinfo=ZONE),limit=10000)
    observed=detector.store.points(run_id)
    scorer=QualifiedShadowScorer()
    expected=[json.loads(canonical({'window':asdict(w),'score':asdict(scorer.score(w,profile))}))
        for w in build_completed_windows(raw,as_of=(right+timedelta(seconds=30)).replace(tzinfo=ZONE),policy=detector.policy,modules=(6,))]
    assert [{'window':p['window'],'score':p['score']} for p in observed]==expected
    with engine.connect() as c:
        packets=[json.loads(r[0]) for r in c.execute(select(windows.c.payload_json).where(windows.c.run_id==run_id).order_by(windows.c.window_start))]
        archive=[json.loads(r[0])['data'] for r in c.execute(select(episodes.c.payload_json).where(episodes.c.run_id==run_id))]
    assert len(packets)==len(expected)
    root=Path('notebooks/outputs/durable_detector_qa_v1')/nonce; root.mkdir(parents=True)
    exported=export_episode(detector.store,run_id,archive[0]['episode_id'],root)
    verify_export(exported['folder'])
    points=[]
    for packet in packets:
        p=packet['data']; at=datetime.fromisoformat(p['window']['window_start']).replace(tzinfo=ZONE).astimezone(timezone.utc)
        points.append({**p,'at':at.isoformat(),'review_required':False})
    context=dict(run_id=run_id,mode='LOCAL_REHEARSAL',profile_id=profile.profile_id,
        profile_version=profile.profile_version,source_timezone='Asia/Bangkok',source_pressure_unit='source units (unverified)')
    evidence=dict(status='AVAILABLE',machine_number='MX080',module=6,points=points,episodes=archive,
        contexts=[context],selected_context=context,slice_start=left.replace(tzinfo=ZONE).isoformat(),
        slice_end_exclusive=right.replace(tzinfo=ZONE).isoformat(),truncated=False,data_issues=[],health_score=None,
        reported_start=datetime(2026,9,7,12,24).replace(tzinfo=ZONE).isoformat(),reported_end=right.replace(tzinfo=ZONE).isoformat(),
        reported_precision='APPROXIMATE')
    (root/'evidence.json').write_text(json.dumps(evidence,ensure_ascii=False),encoding='utf-8')
    report=dict(run_id=run_id,qa_schema=QA_SCHEMA,source_table=source.name,source='archived MX080/M6 seconds',
        period_start=left.isoformat(),period_end_exclusive=right.isoformat(),timezone='Asia/Bangkok',
        raw_rows=len(raw),windows=len(observed),pm_evidence_windows=len(packets),episodes=len(archive),
        parity_mismatches=0,retries=retries,precommit_crashes=crashes,reconnects=len(times),
        cycle_ms_p95=float(pd.Series(times).quantile(.95)),profile_mode='FOUR_DAY_CANDIDATE_NOT_ACTIVE',
        candidate_status=status['status'],pm_alerts_created=0,real_active_profiles_changed=0,
        exported=exported,evidence_file=str((root/'evidence.json').resolve()),
        retention=retention_inventory(detector.store,run_id,now=datetime(2026,10,8)))
    (root/'qa.json').write_text(json.dumps(report,indent=2),encoding='utf-8'); print(json.dumps(report,indent=2))
    engine.dispose(); return report


if __name__=='__main__': run()
