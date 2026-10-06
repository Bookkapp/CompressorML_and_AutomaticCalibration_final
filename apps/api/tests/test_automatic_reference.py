"""Synthetic lifecycle/cache regression tests; not equipment health evidence."""
from contextlib import contextmanager
from dataclasses import replace
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import json

import pytest
from sqlalchemy import text

from apps.api.tests.test_reference_review import store,config,selection,windows
from apps.api.app import automatic_reference as auto, reference_jobs as jobs, qualified_cache as cache
from apps.api.app.reference_review import selected_candidate


@pytest.fixture
def automatic(store,monkeypatch):
    rows = [replace(w,module=module,features=dict(w.features)) for module in range(1,9) for w in store[1] if module != 7]
    monkeypatch.setattr(auto,"connection",jobs.connection)
    monkeypatch.setattr(auto,"get_settings",config)
    monkeypatch.setattr(auto,"_latest_source_time",lambda *_:datetime(2026,10,1,12))
    monkeypatch.setattr(auto,"prime_period",lambda *a,**k:jobs.utcnow())
    monkeypatch.setattr(auto,"load_cached_windows",lambda *a,**k:[w for w in rows if w.module in k["modules"]])
    def persist(*a,transaction,reference_review):
        transaction.execute(text("INSERT INTO qa_candidate VALUES(:job)"),{"job":reference_review["parent_job_id"]})
        assert len(a[5])==7
        assert all(p["validation"]["reference_review"]["reference_acknowledged"] is False for p in a[5])
        return {"batch_id":"qa-automatic-batch","profiles":7}
    monkeypatch.setattr(auto,"persist_batch",persist)
    return store,rows


def request():
    return auto.PreparationRequest(idempotency_key="automatic-qa-0001",machine_number="MX080",history_days=7)


def test_coalesced_tabs_modules_and_manual_parity(automatic):
    store,rows=automatic
    job=auto.create_preparation(request(),"operator-a")
    assert auto.create_preparation(request().model_copy(update={"idempotency_key":"automatic-other-tab"}),"operator-b")==job
    assert jobs.get_job(job,"operator-b")["module"]==0
    # No manual job can race a machine-wide preparation.
    from apps.api.tests.test_reference_review import request as manual_request
    with pytest.raises(jobs.ReviewConflict):jobs.create_preview(manual_request(),"operator-a")
    jobs.execute_job(job);jobs.execute_job(job)
    result=jobs.get_job(job,"operator-b")["result"]
    assert result["profiles"]==7 and len(result["modules"])==8
    assert not result["modules"][6]["candidate_created"]
    assert result["modules"][6]["status"]=="INSUFFICIENT_DATA"
    assert result["auto_activation_allowed"] is False
    child=jobs.get_job(result["modules"][0]["job_id"],"operator-a")
    s=child["preview"]["selection"]
    expected=selected_candidate([w for w in rows if w.module==1],s,config())
    assert child["preview"]["baseline"]==expected["statistics"]["exact_baseline"]
    assert child["preview"]["source_digest"]==expected["source_digest"]
    with store[0].connect() as conn:
        assert conn.execute(text("SELECT COUNT(*) FROM qa_candidate")).scalar()==1
        assert conn.execute(text(f"SELECT COUNT(*) FROM {jobs.TABLE}")).scalar()==9


def test_handoff_copies_only_automatic_evidence_and_keeps_ownership(automatic):
    job=auto.create_preparation(request(),"AUTO_CALIBRATION");jobs.execute_job(job)
    child=jobs.get_job(job,"someone")["result"]["modules"][0]["job_id"]
    with pytest.raises(PermissionError):jobs.get_job(child,"engineer")
    copy=auto.copy_review(child,"engineer")
    assert auto.copy_review(child,"engineer")==copy
    value=jobs.get_job(copy,"engineer")
    assert value["result"]["batch_id"]=="qa-automatic-batch"
    assert value["status"]=="COMPLETED"
    with pytest.raises(PermissionError):jobs.get_job(copy,"someone-else")
    with pytest.raises(jobs.ReviewConflict):auto.copy_review(job,"engineer")


def test_parent_children_and_candidate_rollback_together(automatic,monkeypatch):
    store,_=automatic
    job=auto.create_preparation(request(),"operator-a")
    def fail(*a,transaction,reference_review):
        transaction.execute(text("INSERT INTO qa_candidate VALUES(:job)"),{"job":reference_review["parent_job_id"]})
        raise RuntimeError("crash in atomic completion")
    monkeypatch.setattr(auto,"persist_batch",fail);jobs.execute_job(job)
    assert jobs.get_job(job,"operator-a")["status"]=="FAILED"
    with store[0].connect() as conn:
        assert conn.execute(text("SELECT COUNT(*) FROM qa_candidate")).scalar()==0
        assert conn.execute(text(f"SELECT COUNT(*) FROM {jobs.TABLE}")).scalar()==1


def test_expired_automatic_lease_resumes_same_job_without_duplicates(automatic):
    store,_=automatic
    job=auto.create_preparation(request(),"operator-a")
    with store[0].begin() as conn:
        conn.execute(text(f"UPDATE {jobs.TABLE} SET status='PREVIEW_RUNNING',lease_owner='dead-process',lease_until=:old WHERE job_id=:job"),
                     {"old":jobs.utcnow()-timedelta(minutes=1),"job":job})
    assert jobs.get_job(job,"operator-b")["status"]=="PREVIEW_QUEUED"
    jobs.execute_job(job);jobs.execute_job(job)
    assert jobs.get_job(job,"operator-b")["status"]=="COMPLETED"
    with store[0].connect() as conn:
        assert conn.execute(text("SELECT COUNT(*) FROM qa_candidate")).scalar()==1
        assert conn.execute(text(f"SELECT COUNT(*) FROM {jobs.TABLE}")).scalar()==9


def test_profile_only_scheduler_scopes_machines_and_registers_no_other_jobs(monkeypatch):
    from apps.api.app import worker
    registered=[]
    class Scheduler:
        def __init__(self,**kwargs):assert kwargs["timezone"]=="Asia/Bangkok"
        def add_job(self,fn,trigger,**kwargs):registered.append((fn,kwargs))
        def start(self):pass
    monkeypatch.setattr(worker,"BlockingScheduler",Scheduler)
    worker.main(profiles_only=True,machines=["MX017","MX024"])
    assert len(registered)==1
    assert registered[0][0] is worker.run_profile_candidate_job
    assert registered[0][1]["args"]==[["MX017","MX024"]]


@pytest.fixture
def cached(store,monkeypatch):
    engine,_=store
    with engine.begin() as conn:
        conn.execute(text(f"CREATE TABLE {cache.TABLE}(day_key TEXT,module INTEGER,checked_at TEXT,payload BLOB,source_revision TEXT,PRIMARY KEY(day_key,module))"))
    monkeypatch.setattr(cache,"connection",jobs.connection);monkeypatch.setattr(cache,"get_engine",lambda:engine)
    @contextmanager
    def lock(_):yield
    monkeypatch.setattr(cache,"fill_lock",lock)
    calls=[];revision=["original"]
    source=windows(selection())
    def load(*a,**k):
        calls.append(k["modules"])
        if "revision_out" in k:k["revision_out"][k["start"].date().isoformat()]=revision[0]
        return [replace(w,module=m,features=dict(w.features)) for m in k["modules"] for w in source
                if k["start"].replace(tzinfo=None)<=w.window_start<k["end"].replace(tzinfo=None)]
    monkeypatch.setattr(cache,"load_observed_one_minute_windows",load)
    monkeypatch.setattr(cache,"source_revision",lambda *a:revision[0])
    zone=ZoneInfo("Asia/Bangkok")
    args=dict(machine_number="MX080",start=datetime(2026,9,21,tzinfo=zone),end=datetime(2026,9,22,tzinfo=zone),as_of=datetime(2026,10,1,12,tzinfo=zone))
    return calls,revision,args,engine


def test_shared_cache_module_reuse_incremental_refresh_and_raw_build(cached):
    calls,revision,args,engine=cached
    a=cache.load_cached_windows(config(),**args,modules=(1,))
    b=cache.load_cached_windows(config(),**args,modules=(2,))
    assert len(calls)==1 and len(a)==len(b)>0
    with engine.begin() as conn:conn.execute(text(f"UPDATE {cache.TABLE} SET checked_at=:old"),{"old":cache.now()-timedelta(hours=1)})
    assert cache.load_cached_windows(config(),**args,modules=(1,))==a
    assert len(calls)==1 # unchanged old day: fingerprint only, no raw read
    with engine.begin() as conn:conn.execute(text(f"UPDATE {cache.TABLE} SET checked_at=:old"),{"old":cache.now()-timedelta(hours=1)})
    revision[0]="late-source-change"
    cache.load_cached_windows(config(),**args,modules=(1,))
    assert len(calls)==2 # changed day only
    cache.load_cached_windows(config(),**args,modules=(1,),fresh=True)
    assert len(calls)==3 and calls[-1]==(1,) # Build never trusts TTL


def test_cache_identity_includes_state_mapping_and_codec_lossless(cached):
    _,_,args,_=cached
    rows=cache.load_cached_windows(config(),**args,modules=(1,))
    assert cache.unpack(cache.pack(rows))==rows
    key=cache.day_key(config(),"MX080",args["start"].date())
    changed=config().model_copy(update={"source_busy_normal_values":"0"})
    assert cache.day_key(changed,"MX080",args["start"].date())!=key
    assert "psig" not in key # opaque identity, not credentials/units disclosure


def test_closed_day_reuses_snapshot_for_one_hour_and_mixed_revisions_refill(cached):
    calls,_,args,engine=cached
    cache.load_cached_windows(config(),**args,modules=(1,2))
    with engine.begin() as conn:
        conn.execute(text(f"UPDATE {cache.TABLE} SET checked_at=:old"),{"old":cache.now()-timedelta(minutes=20)})
    cache.load_cached_windows(config(),**args,modules=(1,2))
    assert len(calls)==1
    with engine.begin() as conn:
        conn.execute(text(f"UPDATE {cache.TABLE} SET source_revision='different-build' WHERE module=2"))
    cache.load_cached_windows(config(),**args,modules=(1,2))
    assert len(calls)==2


def test_streaming_keeps_whole_minutes_alias_duplicates_and_gap_gates(monkeypatch):
    from apps.api.app import qualified_calibration as reader
    from apps.api.app.qualified_windows import build_completed_windows
    settings=config().model_copy(update={"source_db_host":"localhost","source_db_name":"synthetic",
        "source_db_user":"synthetic","source_db_password":"synthetic","source_table":"readings"})
    start=datetime(2026,9,21)
    rows=[]
    for second in range(21*60):
        if second==61:continue
        row={"recorded_at":start+timedelta(seconds=second),"machine_number":"MX080","Status":"Run"}
        for module in range(1,9):
            for name in ("Hp_1st","Lp_1st","Hp_2nd","Lp_2nd","Valve","TempHi","TempLo"):
                row[f"{name}_{module}"]=100.0+second/1000
            row.update({f"Status_{module}":"On",f"Busy_{module}":0,f"SV_{module}":"Off"})
        rows.append(row)
    duplicate=dict(rows[119]);duplicate["machine_number"]="080"
    rows.insert(120,duplicate)
    class Result:
        def mappings(self):return self
        def partitions(self,size):
            assert size==1200
            for first in range(0,len(rows),43):yield rows[first:first+43]
    class Conn:
        def execution_options(self,**kwargs):
            assert kwargs["stream_results"] and kwargs["yield_per"]==1200
            return self
        def execute(self,*_):return Result()
    @contextmanager
    def source():yield Conn()
    monkeypatch.setattr(reader,"source_connection",source)
    zone=ZoneInfo("Asia/Bangkok");end=start+timedelta(minutes=21)
    expected=build_completed_windows([{**r,"machine_number":"MX080"} for r in rows],as_of=end.replace(tzinfo=zone),
        policy=reader.policy_from_settings(settings))
    actual=reader.load_observed_one_minute_windows(settings,machine_number="MX080",
        start=start.replace(tzinfo=zone),end=end.replace(tzinfo=zone))
    assert {(w.module,w.window_start):w for w in actual}=={(w.module,w.window_start):w for w in expected}
    assert any(w.reason=="DUPLICATE_MACHINE_SECOND" for w in actual)
