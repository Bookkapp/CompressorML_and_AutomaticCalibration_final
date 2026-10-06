"""Isolated clock/SQL fixtures; never real telemetry or Active evidence."""
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import asdict, replace
from datetime import date, datetime, timedelta, timezone
import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.pool import StaticPool

from apps.api.app import context_followup as follow, reference_jobs as jobs, automatic_reference as auto, context_api
from apps.api.app.config import Settings
from apps.api.app.context_reference import metadata as profile_meta, profiles, get_profile
from apps.api.app.context_review import metadata as review_meta, gate, active
from apps.api.app.context_storage import metadata as day_meta, days, source_namespace, pack
from apps.api.app.context_scope import make_scope
from apps.api.app.unified_events import metadata as event_meta, events
from apps.api.app.main import app
from apps.api.tests.test_context_profiles import reference, minute
from apps.api.app.context_profiles import fit_context_candidate


def config():
    return Settings(_env_file=None,app_mode='live',source_timezone='Asia/Bangkok',source_pressure_unit='psig',
        qualified_1m_late_arrival_seconds=0,profile_min_shadow_windows=200,
        profile_state_contract_version='TEST',profile_controller_codebook_version='TEST',profile_service_epoch_version='TEST')


def model(settings):
    m=fit_context_candidate(reference(),[],machine='MX017',module=1,shadow_start=datetime(2026,9,8),shadow_end=datetime(2026,9,11))
    m.update(profile_id='a'*64,source_digest='b'*64,source_namespace=source_namespace(settings),reference_start='2026-09-01T00:00:00',day_receipts={},
        reference_review={'at':'2026-10-03T08:00:00+00:00','actor':'ISOLATED QA','accepted_regime_ids':[r['regime_id'] for r in m['regimes']],
            'accepted_template_ids':[],'engineer_evidence_ref':'ISOLATED FIXTURE ONLY','evaluation_scope':make_scope(['OFF'],'isolated unsupported ON')})
    from apps.api.app.context_reference import contract_versions
    m['contracts']=contract_versions(settings)
    return m


def test_days_are_source_based_and_open_or_empty_dates_do_not_count():
    s=config();m=model(s);now=datetime(2026,10,6,8,tzinfo=timezone.utc)
    for latest,expected in [(None,False),(datetime(2026,10,3,23),False),(datetime(2026,10,5,12),False),(datetime(2026,10,6,12),False)]:
        p=follow.calendar(m,{'latest':latest,'valid_latest':latest},s,now=now)
        assert p['calendar_ready']==expected
        assert p['first_day']=='2026-10-04'
        assert (date.fromisoformat(p['window_end'])-date.fromisoformat(p['window_start'])).days<=4
    p=follow.calendar(m,{'latest':datetime(2026,10,7,12),'valid_latest':datetime(2026,10,7,12)},s,now=datetime(2026,10,7,8,tzinfo=timezone.utc))
    assert p['calendar_ready'] and (p['validation_start'],p['validation_end'])==('2026-10-04','2026-10-07')
    # Updating the frozen review resets the post-review boundary.
    m['reference_review']['at']='2026-10-06T08:00:00+00:00'
    assert not follow.calendar(m,{'latest':datetime(2026,10,7,12),'valid_latest':datetime(2026,10,7,12)},s,now=datetime(2026,10,7,8,tzinfo=timezone.utc))['calendar_ready']


def test_future_clock_does_not_manufacture_days_or_ready_status():
    s=config();m=model(s);now=datetime(2026,10,6,8,tzinfo=timezone.utc)
    head={'latest':datetime(2026,10,10,12),'valid_latest':datetime(2026,10,5,12)}
    p=follow.calendar(m,head,s,now=now)
    assert p['clock_error'] and not p['calendar_ready']
    with pytest.raises(jobs.ReviewConflict,match='FUTURE_SOURCE_TIMESTAMP'):
        follow.assert_source_clock(head['latest'],s,now=now)


def test_same_day_after_freeze_can_be_inspected_but_is_not_a_full_day():
    s=config();m=model(s)
    head={'latest':datetime(2026,10,3,16),'valid_latest':datetime(2026,10,3,16)}
    p=follow.calendar(m,head,s,now=datetime(2026,10,3,10,tzinfo=timezone.utc))
    assert p['available_start']=='2026-10-03T15:01:00' and p['first_day']=='2026-10-04'
    assert not p['calendar_ready']
    rows=[{'time':f'2026-10-03T15:0{i}:00','category':'WITHIN_PROPOSED_STEADY'} for i in range(2)]
    r=follow.summarize_day(rows,date(2026,10,3),closed=False,inspected_until='2026-10-03T16:00:00',not_before=p['available_start'])
    assert r['supported_minutes']==1 and r['expected_minutes']==59 and r['missing_minutes']==58


def test_daily_summary_separates_flags_unresolved_exclusions_quality_and_gaps():
    day=date(2026,10,4);names=['WITHIN_PROPOSED_STEADY']*60+['STEADY_DEVIATION','NEW_STEADY_LEVEL','STATE_GATE_EXCLUDED','DATA_UNAVAILABLE']
    points=[{'time':(datetime.combine(day,datetime.min.time())+timedelta(minutes=i)).isoformat(),'category':name} for i,name in enumerate(names)]
    r=follow.summarize_day(points,day,closed=True,inspected_until='2026-10-05T00:00:00')
    assert r['supported_minutes']==61 and r['within_minutes']==60 and r['flagged_minutes']==1
    assert r['unresolved_minutes']==1 and r['excluded_state_minutes']==1 and r['data_unavailable_minutes']==1
    assert r['missing_minutes']==1440-len(points)
    assert [e['category'] for e in r['episodes']]==['STEADY_DEVIATION','NEW_STEADY_LEVEL','DATA_UNAVAILABLE']


@pytest.fixture
def isolated(monkeypatch):
    engine=create_engine('sqlite://',connect_args={'check_same_thread':False},poolclass=StaticPool)
    for meta in (profile_meta,review_meta,day_meta,event_meta):meta.create_all(engine)
    with engine.begin() as conn:
        conn.execute(text(f'''CREATE TABLE {jobs.TABLE}(job_id VARCHAR(36) PRIMARY KEY,idempotency_key VARCHAR(100) UNIQUE,
          request_digest VARCHAR(64),actor_id VARCHAR(100),machine_number VARCHAR(64),module INTEGER,status VARCHAR(30),
          request_json TEXT,selection_json TEXT,preview_json TEXT,result_json TEXT,source_digest VARCHAR(64),
          created_at DATETIME,updated_at DATETIME,lease_owner VARCHAR(36),lease_until DATETIME,progress_message TEXT,error_code TEXT)'''))
    @contextmanager
    def connection():
        with engine.begin() as conn:yield conn
    monkeypatch.setattr(jobs,'connection',connection);monkeypatch.setattr(jobs,'get_engine',lambda:engine);monkeypatch.setattr(jobs,'get_settings',config)
    monkeypatch.setattr(follow,'get_settings',config);monkeypatch.setattr(follow,'get_engine',lambda:engine)
    m=model(config())
    with engine.begin() as conn:
        conn.execute(profiles.insert().values(profile_id=m['profile_id'],job_id='fixture',machine_number='MX017',module=1,status='REFERENCE_REVIEWED',
            version=m['version'],source_digest=m['source_digest'],created_at='2026-10-03',payload=pack(m)))
    def head(*a,**k):return {'latest':datetime(2026,10,5,12),'valid_latest':datetime(2026,10,5,12)}
    monkeypatch.setattr(follow,'source_head',head)
    def capture(settings,engine,machine,day,**kwargs):
        at=datetime.combine(day,datetime.min.time())
        rows=[minute(at+timedelta(minutes=i),200.) for i in range(65)]
        if day==date(2026,10,4):rows[62]=replace(rows[62],features=None,measurement_quality='DATA_QUALITY',reason='ISOLATED BAD SENSOR')
        if day==date(2026,10,5):rows[60]=replace(rows[60],context_key='run|on|0|on')
        key=day.isoformat()*6;receipt={'source_digest':day.isoformat(),'snapshot_key':key,'event_ids':[],'completed':day<date(2026,10,5),
            'inspected_until':(at+timedelta(days=1)).isoformat() if day<date(2026,10,5) else (at+timedelta(hours=12)).isoformat()}
        with engine.begin() as conn:
            if not conn.execute(select(days.c.day_key).where(days.c.day_key==key)).first():
                for module in range(9):
                    payload=receipt if module==0 else {'windows':[asdict(w) for w in rows if w.module==module],'event_ids':[]}
                    conn.execute(days.insert().values(day_key=key,module=module,machine_number=machine,source_day=day.isoformat(),checked_at='2026-10-06',source_revision=day.isoformat(),payload=pack(payload)))
        return rows,receipt
    monkeypatch.setattr(follow,'partial_day',capture)
    return engine,m


def test_durable_interim_job_retry_and_graph_do_not_change_reference_or_active(isolated):
    engine,m=isolated;before=deepcopy(m)
    request=follow.FollowupRequest(idempotency_key='followup-test-job',machine_number='MX017',parent_profile_id=m['profile_id'])
    job=auto.create_preparation(request,'QA',mode=follow.MODE)
    # Another tab reuses the same admitted source/profile inspection.
    assert auto.create_preparation(request.model_copy(update={'idempotency_key':'followup-tab-two'}),'QB',mode=follow.MODE)==job
    jobs.execute_job(job);jobs.execute_job(job)
    result=jobs.get_job(job,'QB')['result']
    assert result is not None and not result['approval_eligible'] and not result['prospective']
    assert len(result['daily'])==3 and result['profile_id']==m['profile_id']
    assert result['start']=='2026-10-03T15:01:00' and result['daily'][0]['observed_minutes']==0
    assert get_profile(engine,m['profile_id'])==before
    assert 'PROSPECTIVE_VALIDATION_REQUIRED' in gate(m,config())['blockers']
    forged=deepcopy(m);forged['future_validation']={**result, 'supported_days':3,'supported_minutes':1000,'unresolved_minutes':0,'flag_pct':0}
    assert 'MOCK_VALIDATION_NOT_APPROVAL_EVIDENCE' in gate(forged,config())['blockers']
    with engine.connect() as conn:
        assert conn.execute(select(func.count()).select_from(profiles)).scalar()==1
        assert conn.execute(select(func.count()).select_from(active)).scalar()==0
        assert conn.execute(select(func.count()).select_from(events)).scalar()==1
    day=follow.inspection_day(engine,m,result,date(2026,10,5),config())
    assert len(day['chart'])==65 and not day['approval_eligible']
    assert any(p['category']=='STATE_GATE_EXCLUDED' for p in day['chart'])
    with pytest.raises(jobs.ReviewConflict,match='PROFILE_CHANGED'):
        follow.result_for(engine,job,'c'*64)


def test_progress_missing_day_and_supported_days_are_independent(isolated,monkeypatch):
    engine,m=isolated
    monkeypatch.setattr(follow,'shared_read',lambda key,fn,**kw:fn())
    monkeypatch.setattr(follow,'source_head',lambda *a,**k:{'latest':datetime(2026,10,7,12),'valid_latest':datetime(2026,10,7,12)})
    def inventory(*a,**kw):
        return [{'day':f'2026-10-0{n}','has_data':n!=5,'closed':n<7,'first_at':None,'last_at':None} for n in range(4,8)]
    monkeypatch.setattr(follow,'inventory',inventory)
    p=follow.progress(engine,m,config(),now=datetime(2026,10,7,8,tzinfo=timezone.utc))
    assert p['calendar_ready'] and p['received_closed_days']==2 and not p['can_validate']
    assert p['inspected_supported_days']==0 and p['reason']=='SOURCE_DAY_MISSING'


def test_followup_routes_enforce_job_profile_scope_and_raw_boundaries(isolated,monkeypatch):
    engine,m=isolated
    monkeypatch.setattr(context_api,'engine',lambda:engine);monkeypatch.setattr(context_api,'get_settings',config)
    monkeypatch.setattr(jobs,'dispatch',lambda job:None)
    client=TestClient(app)
    base='/api/v1/calibration/context/profiles/'+m['profile_id']+'/followup'
    assert client.post(base,json={'idempotency_key':'followup-http-test'}).status_code==422
    response=client.post(base,json={'idempotency_key':'followup-http-test'},headers={'X-Approver-Id':'QA'})
    assert response.status_code==202
    job=response.json()['job_id'];jobs.execute_job(job)
    assert client.get(base+'/'+job+'/day?day=2026-10-05').status_code==200
    assert client.get(base+'/'+job+'/day?day=2026-10-02').status_code==422
    monkeypatch.setattr(context_api,'cached_raw',lambda *a,**k:{'chart':[{'time':'2026-10-05T00:10:00','hp2':200.}],'source_written':False})
    raw=client.get(base+'/'+job+'/raw?start=2026-10-05T00:10:00&end=2026-10-05T00:20:00')
    assert raw.status_code==200 and raw.json()['source_written'] is False
    assert client.get(base+'/'+job+'/raw?start=2026-10-05T12:00:00&end=2026-10-05T12:05:00').status_code==409
    other=base.replace(m['profile_id'],'c'*64)
    assert client.get(other+'/'+job+'/day?day=2026-10-05').status_code==404


def test_interrupted_inspection_requeues_without_partial_profile_commit(isolated):
    engine,m=isolated
    request=follow.FollowupRequest(idempotency_key='followup-restart-test',machine_number='MX017',parent_profile_id=m['profile_id'])
    job=auto.create_preparation(request,'QA',mode=follow.MODE)
    with engine.begin() as conn:
        conn.execute(text(f"UPDATE {jobs.TABLE} SET status='PREVIEW_RUNNING',lease_until=:old WHERE job_id=:job"),{'job':job,'old':jobs.utcnow()-timedelta(hours=1)})
        jobs._expire(conn,job)
    assert jobs.get_job(job,'QA')['status']=='PREVIEW_QUEUED'
    jobs.execute_job(job);jobs.execute_job(job)
    assert jobs.get_job(job,'QA')['status']=='COMPLETED'
    with engine.connect() as conn:
        assert conn.execute(select(func.count()).select_from(profiles)).scalar()==1
        assert conn.execute(select(func.count()).select_from(events)).scalar()==1


def test_partial_snapshot_is_all_module_shared_and_keeps_closed_day_pointer(isolated,monkeypatch):
    engine,m=isolated
    from apps.api.app import context_storage
    monkeypatch.undo()
    calls=[]
    @contextmanager
    def lock(*a,**k):yield
    monkeypatch.setattr(follow,'fill_lock',lock)
    def load(*a,**k):
        calls.append(k);return [replace(minute(datetime(2026,10,5,8),200.),module=i) for i in range(1,9)]
    monkeypatch.setattr(follow,'load_observed_one_minute_windows',load)
    first=follow.partial_day(config(),engine,'MX017',date(2026,10,5),as_of=datetime(2026,10,5,8,14,tzinfo=timezone(timedelta(hours=7))))
    second=follow.partial_day(config(),engine,'MX017',date(2026,10,5),as_of=datetime(2026,10,5,8,13,tzinfo=timezone(timedelta(hours=7))))
    assert len(calls)==1 and len(first[0])==8 and len(second[0])==8
    assert not first[1]['completed'] and not first[1]['approval_eligible']
    assert first[1]['snapshot_key']==second[1]['snapshot_key']
    assert context_storage.read_day(engine,context_storage.day_key(config(),'MX017',date(2026,10,5))) is None
