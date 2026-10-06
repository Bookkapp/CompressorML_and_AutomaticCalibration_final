"""Synthetic unit/transaction fixtures, never healthy equipment labels."""
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
import json

import numpy as np
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import Column, DateTime, Integer, MetaData, String, Table, Text, create_engine, event, text
from sqlalchemy.exc import OperationalError

from apps.api.app.config import Settings
from apps.api.app.main import app
from apps.api.app.qualified_candidate_registry import registry_candidate_from_windows
from apps.api.app.qualified_windows import FEATURES, STATE_CODE, QualifiedWindow
from apps.api.app.reference_review import (ReferencePreviewRequest, ReferenceBuildRequest,
    bounds, make_preview, minute_detail, resolve_selection, selected_candidate, snapshot_digest)
from apps.api.app import reference_jobs as jobs


def config():
    return Settings(app_mode="live", source_timezone="Asia/Bangkok", source_pressure_unit="psig",
        profile_state_contract_version="test-codebook", profile_controller_codebook_version="test-codebook",
        profile_service_epoch_version="test-review", qualified_1m_late_arrival_seconds=0,
        profile_min_calibration_days=7, profile_min_calibration_windows=200,
        profile_min_shadow_windows=50)  # tiny synthetic fixtures, not production policy


def request(**kwargs):
    return ReferencePreviewRequest(idempotency_key="preview-unit-test-0001", machine_number="MX080", module=6,
        history_days=7, **kwargs)


def selection(**kwargs):
    return resolve_selection(request(**kwargs), datetime(2026,10,1,12), config())


def windows(s):
    start, _, _, end = bounds(s)
    rows = []
    cursor = start
    rng = np.random.default_rng(8046)
    while cursor < end:
        # 30 observed minutes each day, plus its final minute; deliberately not
        # full-day coverage. The preview must not represent this as complete.
        for minute in [*range(30), 1439]:
            t = cursor + timedelta(minutes=minute)
            features = {f: float(100 + rng.normal(0,.2)) for f in FEATURES}
            rows.append(QualifiedWindow("MX080",6,t,t+timedelta(minutes=1),"Off",STATE_CODE,
                60,60,1,1,"PASS","",features))
        cursor += timedelta(days=1)
    return rows


def test_calendar_split_and_timezone_grace():
    s = selection()
    assert bounds(s) == (datetime(2026,9,21), datetime(2026,9,28), datetime(2026,9,28), datetime(2026,10,1))
    aware = resolve_selection(request(), datetime(2026,10,1,17,0,10,tzinfo=timezone.utc),
        config().model_copy(update={"qualified_1m_late_arrival_seconds":30}))
    assert aware["shadow_end"] == "2026-10-01T00:00:00"  # Bangkok 2 Oct midnight not closed yet


@pytest.mark.parametrize("extra", [
    {"reference_start":"2026-09-21","reference_end":"2026-09-29"},
    {"reference_start":"2026-06-01","reference_end":"2026-09-28"},
    {"exclusions":[{"start":"2026-09-28T01:00","end":"2026-09-28T02:00","reason":"known case"}]},
    {"exclusions":[{"start":"2026-09-22T01:00","end":"2026-09-22T03:00","reason":"known case"},
                   {"start":"2026-09-22T02:00","end":"2026-09-22T04:00","reason":"overlap"}]},
])
def test_invalid_split_or_exclusion(extra):
    with pytest.raises(ValueError): selection(**extra)


@pytest.mark.parametrize("extra", [
    {"reference_start":"2026-09-21"},
    {"reference_start":"2026-09-22","reference_end":"2026-09-21"},
    {"exclusions":[{"start":"2026-09-22T01:00:01","end":"2026-09-22T02:00","reason":"known case"}]},
    {"exclusions":[{"start":"2026-09-22T01:00+07:00","end":"2026-09-22T02:00+07:00","reason":"known case"}]},
    {"exclusions":[{"start":"2026-09-22T01:00","end":"2026-09-22T02:00","reason":"   "}]},
])
def test_request_validation(extra):
    with pytest.raises(ValidationError): request(**extra)


def test_shadow_is_never_fit_and_no_selection_keeps_exact_estimator():
    s = selection(); rows = windows(s)
    a = selected_candidate(rows,s,config())
    b = registry_candidate_from_windows(rows,settings=config(),machine_number="MX080",module=6,
        calibration_start=bounds(s)[0],shadow_start=bounds(s)[2],shadow_end=bounds(s)[3])
    assert a["statistics"] == b["statistics"] and a["threshold"] == b["threshold"]
    changed = [QualifiedWindow(**{**w.__dict__,"features":{f:10000. for f in FEATURES}})
        if w.window_start >= bounds(s)[2] else w for w in rows]
    c = selected_candidate(changed,s,config())
    assert c["statistics"] == a["statistics"] and c["threshold"] == a["threshold"]
    assert c["validation"]["shadow_flag_pct"] != a["validation"]["shadow_flag_pct"]


def test_fit_exclusion_keeps_shadow_and_has_insufficient_day_warning():
    s = selection(exclusions=[{"start":"2026-09-22T00:00","end":"2026-09-23T00:00","reason":"owner case"}])
    preview = make_preview(windows(s),s,config())
    assert preview["summary"]["reference_days"] == 6
    assert preview["summary"]["reference_minutes"] == 186
    assert not preview["can_build"]
    assert preview["summary"]["shadow_minutes"] == 93
    day = next(d for d in preview["daily"] if d["date"]=="2026-09-22")
    assert day["excluded"] == 31 and day["selected"] == 0 and day["missing"] == 1409
    assert "INSUFFICIENT_CALIBRATION_COVERAGE" in preview["reason_codes"]


def test_null_gaps_empty_data_and_duplicate_fail_closed():
    s=selection(); rows=windows(s)
    assert make_preview(rows,s,config())["chart"][1]["hp2"] is None
    p=make_preview([],s,config())
    assert not p["can_build"] and all(x["hp2"] is None for x in p["chart"])
    assert p["daily"][0]["missing"]==1440
    with pytest.raises(ValueError): snapshot_digest([*rows,rows[0]],s)
    with pytest.raises(ValueError): snapshot_digest([QualifiedWindow(**{**rows[0].__dict__,"module":1})],s)


def test_snapshot_covers_ineligible_quality_and_policy():
    s=selection(); rows=windows(s)
    a=snapshot_digest(rows,s)
    b=snapshot_digest([QualifiedWindow(**{**rows[0].__dict__,"data_quality_status":"FAIL","features":None}),*rows[1:]],s)
    assert a!=b
    assert a != snapshot_digest(rows,{**s,"source_timezone":"UTC"})


@pytest.fixture
def store(monkeypatch,tmp_path):
    engine=create_engine("sqlite:///"+str(tmp_path/"jobs.db"))
    metadata=MetaData()
    cols=[Column("job_id",String,primary_key=True),Column("idempotency_key",String,unique=True),Column("module",Integer)]
    cols += [Column(x,DateTime) for x in ("created_at","updated_at","lease_until")]
    cols += [Column(x,Text) for x in ("request_digest","actor_id","machine_number","status","request_json","selection_json","preview_json","source_digest","result_json","error_code","progress_message","lease_owner")]
    Table(jobs.TABLE,metadata,*cols); Table("qa_candidate",metadata,Column("job",String,primary_key=True))
    metadata.create_all(engine)
    @contextmanager
    def conn():
        with engine.begin() as c: yield c
    monkeypatch.setattr(jobs,"connection",conn); monkeypatch.setattr(jobs,"get_engine",lambda:engine)
    monkeypatch.setattr(jobs,"get_settings",config)
    monkeypatch.setattr(jobs,"_latest_source_time",lambda *_: datetime(2026,10,1,12))
    s=selection(); rows=windows(s)
    monkeypatch.setattr(jobs,"load_observed_one_minute_windows",lambda *a,**k: [w for w in rows if k["start"].replace(tzinfo=None)<=w.window_start<k["end"].replace(tzinfo=None)])
    def persist(*args,transaction,reference_review):
        transaction.execute(text("INSERT INTO qa_candidate VALUES (:job)"),{"job":reference_review["job_id"]})
        return {"batch_id":"qa-batch", "status":"COMPLETED"}
    monkeypatch.setattr(jobs,"persist_batch",persist)
    yield engine, rows
    engine.dispose()


def ready(store):
    job=jobs.create_preview(request(),"reviewer-qa")
    jobs.execute_job(job)
    value=jobs.get_job(job,"reviewer-qa")
    assert value["status"]=="READY"
    return job,value["preview"]["source_digest"]


def test_durable_idempotency_build_completion_and_access(store):
    job,digest=ready(store)
    assert jobs.create_preview(request(),"reviewer-qa")==job
    with pytest.raises(jobs.ReviewConflict): jobs.create_preview(request(reference_start="2026-09-20",reference_end="2026-09-28"),"reviewer-qa")
    with pytest.raises(PermissionError): jobs.get_job(job,"other-user")
    with pytest.raises(PermissionError): jobs.queue_build(job,"other-user",digest,"reviewed")
    with pytest.raises(jobs.ReviewConflict): jobs.queue_build(job,"reviewer-qa","0"*64,"reviewed")
    jobs.queue_build(job,"reviewer-qa",digest,"reviewed"); jobs.queue_build(job,"reviewer-qa",digest,"reviewed")
    jobs.execute_job(job); jobs.execute_job(job)
    jobs.queue_build(job,"reviewer-qa",digest,"reviewed")
    assert jobs.get_job(job,"reviewer-qa")["status"]=="COMPLETED"
    with store[0].connect() as conn: assert conn.execute(text("SELECT COUNT(*) FROM qa_candidate")).scalar()==1


def test_changed_source_and_policy_refuse_to_persist(store,monkeypatch):
    job,digest=ready(store); jobs.queue_build(job,"reviewer-qa",digest,"reviewed")
    monkeypatch.setattr(jobs,"load_observed_one_minute_windows",lambda *a,**k: store[1][1:])
    jobs.execute_job(job)
    assert jobs.get_job(job,"reviewer-qa")["error_code"]=="SOURCE_CHANGED_REVIEW_AGAIN"
    with store[0].connect() as conn: assert conn.execute(text("SELECT COUNT(*) FROM qa_candidate")).scalar()==0


def test_candidate_and_completion_rollback_together(store,monkeypatch):
    job,digest=ready(store); jobs.queue_build(job,"reviewer-qa",digest,"reviewed")
    def fail(*a,transaction,reference_review):
        transaction.execute(text("INSERT INTO qa_candidate VALUES (:job)"),{"job":job})
        raise RuntimeError("simulated crash before completion")
    monkeypatch.setattr(jobs,"persist_batch",fail); jobs.execute_job(job)
    assert jobs.get_job(job,"reviewer-qa")["status"]=="FAILED"
    with store[0].connect() as conn: assert conn.execute(text("SELECT COUNT(*) FROM qa_candidate")).scalar()==0


def test_busy_context_and_expired_lease(store):
    job=jobs.create_preview(request(),"reviewer-qa")
    payload=request().model_copy(update={"idempotency_key":"new-request-0002"})
    with pytest.raises(jobs.ReviewConflict): jobs.create_preview(payload,"reviewer-qa")
    with store[0].begin() as conn:
        conn.execute(text(f"UPDATE {jobs.TABLE} SET lease_until=:t WHERE job_id=:job"),{"job":job,"t":jobs.utcnow()-timedelta(seconds=1)})
    assert jobs.get_job(job,"reviewer-qa")["error_code"]=="INTERRUPTED_OR_TIMED_OUT"
    assert jobs.create_preview(payload,"reviewer-qa")!=job


def test_live_poll_and_empty_admission_cleanup_do_not_write(store):
    job = jobs.create_preview(request(), "reviewer-qa")
    statements = []
    def capture(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement.strip().upper())
    event.listen(store[0], "before_cursor_execute", capture)
    try:
        assert jobs.get_job(job, "reviewer-qa")["status"] == "PREVIEW_QUEUED"
        with store[0].begin() as conn:
            jobs._expire(conn)
        assert not any(s.startswith(("UPDATE", "INSERT", "DELETE")) for s in statements)
    finally:
        event.remove(store[0], "before_cursor_execute", capture)


def test_poll_only_expires_requested_job_after_authorization(store):
    first = jobs.create_preview(request(), "reviewer-qa")
    other = jobs.create_preview(request().model_copy(update={"idempotency_key":"other-expired-job", "module":5}), "reviewer-qa")
    with store[0].begin() as conn:
        conn.execute(text(f"UPDATE {jobs.TABLE} SET lease_until=:t"), {"t":jobs.utcnow()-timedelta(seconds=5)})
    with pytest.raises(PermissionError):
        jobs.get_job(first, "other-reviewer")
    with store[0].connect() as conn:
        assert conn.execute(text(f"SELECT COUNT(*) FROM {jobs.TABLE} WHERE status='FAILED'")).scalar() == 0
    assert jobs.get_job(first, "reviewer-qa")["status"] == "FAILED"
    with store[0].connect() as conn:
        assert conn.execute(text(f"SELECT status FROM {jobs.TABLE} WHERE job_id=:job"), {"job":other}).scalar() == "PREVIEW_QUEUED"
    with store[0].begin() as conn:
        jobs._expire(conn)
    assert jobs.get_job(other, "reviewer-qa")["status"] == "FAILED"


def test_expiry_rechecks_worker_lease_renewal(store):
    job = jobs.create_preview(request(), "reviewer-qa")
    with store[0].begin() as conn:
        conn.execute(text(f"UPDATE {jobs.TABLE} SET lease_until=:t WHERE job_id=:job"), {"job":job,"t":jobs.utcnow()-timedelta(seconds=5)})
    renewed = []
    def renew_before_expiry(conn, cursor, statement, parameters, context, executemany):
        if statement.startswith(f"UPDATE {jobs.TABLE} SET status='FAILED'") and not renewed:
            renewed.append(True)
            conn.execute(text(f"UPDATE {jobs.TABLE} SET lease_until=:t WHERE job_id=:job"), {"job":job,"t":jobs.utcnow()+timedelta(minutes=15)})
    event.listen(store[0], "before_cursor_execute", renew_before_expiry)
    try:
        assert jobs.get_job(job, "reviewer-qa")["status"] == "PREVIEW_QUEUED"
        assert renewed == [True]
    finally:
        event.remove(store[0], "before_cursor_execute", renew_before_expiry)


@pytest.mark.parametrize("code,statement,expected", [
    (1213, f"UPDATE {jobs.TABLE}", "REFERENCE_STORAGE_BUSY_RETRY"),
    (1205, f"UPDATE {jobs.TABLE}", "REFERENCE_STORAGE_BUSY_RETRY"),
    (1146, f"SELECT * FROM {jobs.TABLE}", "Reference review storage unavailable; apply mysql_reference_review.sql to the analytics schema"),
    (1054, f"SELECT * FROM {jobs.TABLE}", "REFERENCE_STORAGE_SCHEMA_MISMATCH"),
    (1146, "SELECT * FROM missing_source_table", "REFERENCE_STORAGE_CONNECTION_OR_PERMISSION_ERROR"),
    (1045, f"SELECT * FROM {jobs.TABLE}", "REFERENCE_STORAGE_CONNECTION_OR_PERMISSION_ERROR"),
    (2003, f"SELECT * FROM {jobs.TABLE}", "REFERENCE_STORAGE_CONNECTION_OR_PERMISSION_ERROR"),
])
def test_database_error_does_not_always_prescribe_migration(monkeypatch, code, statement, expected):
    import apps.api.app.main as main
    import pymysql
    def fail(*args):
        raise OperationalError(statement, {}, pymysql.err.OperationalError(code, "sanitized QA error"))
    monkeypatch.setattr(main, "is_demo", lambda:False)
    monkeypatch.setattr(jobs, "get_job", fail)
    response = TestClient(app).get("/api/v1/calibration/reference/jobs/qa", headers={"X-Approver-Id":"reviewer-qa"})
    assert response.status_code == 503 and response.json()["detail"] == expected


def test_rest_api_async_contract_and_demo_gate(store,monkeypatch):
    import apps.api.app.main as main
    client=TestClient(app)
    monkeypatch.setattr(main,"is_demo",lambda:False)
    monkeypatch.setattr(jobs,"dispatch",lambda _:None)
    p=request().model_dump(mode="json")
    assert client.post("/api/v1/calibration/reference/preview",json=p).status_code==401
    result=client.post("/api/v1/calibration/reference/preview",json=p,headers={"X-Approver-Id":"reviewer-qa"})
    assert result.status_code==202 and result.json()["status"]=="PREVIEW_QUEUED"
    id=result.json()["job_id"]
    jobs.execute_job(id)
    assert client.get(f"/api/v1/calibration/reference/jobs/{id}",headers={"X-Approver-Id":"other"}).status_code==403
    digest=jobs.get_job(id,"reviewer-qa")["preview"]["source_digest"]
    response=client.post(f"/api/v1/calibration/reference/jobs/{id}/build",headers={"X-Approver-Id":"reviewer-qa"},json={"source_digest":digest,"acknowledge_reference":False,"review_note":"QA review"})
    assert response.status_code==422
    monkeypatch.setattr(main,"is_demo",lambda:True)
    assert client.post("/api/v1/calibration/reference/preview",json=p,headers={"X-Approver-Id":"reviewer-qa"}).status_code==409


def test_build_requires_explicit_review_note():
    with pytest.raises(ValidationError): ReferenceBuildRequest(source_digest="0"*64,acknowledge_reference=True,review_note="   ")


def test_minute_zoom_keeps_gaps_and_validates_source(store):
    job,_=ready(store)
    detail=jobs.get_day(job,"reviewer-qa",date(2026,9,22))
    assert len(detail["chart"])==1440 and detail["chart"][0]["hp2"] is not None
    assert detail["chart"][30]["hp2"] is None and detail["chart"][30]["quality"]=="NO_SOURCE_ROWS"
    with pytest.raises(jobs.ReviewConflict): jobs.get_day(job,"reviewer-qa",date(2026,10,1))
    with pytest.raises(PermissionError): jobs.get_day(job,"someone-else",date(2026,9,22))


def test_zoom_rejects_changed_data_and_outside_dates():
    s=selection(); rows=[w for w in windows(s) if w.window_start.date()==date(2026,9,22)]
    with pytest.raises(ValueError): minute_detail(rows[:-1],s,date(2026,9,22),snapshot_digest(rows,s))
    with pytest.raises(ValueError): minute_detail([],s,date(2026,10,1),snapshot_digest([],s))


def test_recheck_policy_and_expired_preview(store,monkeypatch):
    job,digest=ready(store); jobs.queue_build(job,"reviewer-qa",digest,"reviewed")
    monkeypatch.setattr(jobs,"get_settings",lambda: config().model_copy(update={"source_busy_normal_values":"0"}))
    jobs.execute_job(job)
    assert jobs.get_job(job,"reviewer-qa")["error_code"]=="POLICY_CHANGED_REVIEW_AGAIN"


def test_coverage_after_quarantine_is_not_auto_ready():
    s=selection(); rows=windows(s)
    first=bounds(s)[2]
    indexes=[i for i,w in enumerate(rows) if w.window_start<first][:18]
    for i in indexes:
        rows[i]=QualifiedWindow(**{**rows[i].__dict__,"features":{f:10000. for f in FEATURES}})
    preview=make_preview(rows,s,config())
    assert not preview["can_build"]
    assert "INSUFFICIENT_RETAINED_REFERENCE_COVERAGE" in preview["reason_codes"]
    assert preview["summary"]["retained_reference_minutes"] < preview["summary"]["min_reference_minutes"]


def test_day_policy_change_is_a_recoverable_conflict(store,monkeypatch):
    job,_=ready(store)
    monkeypatch.setattr(jobs,"get_settings",lambda: config().model_copy(update={"profile_shadow_days":5}))
    with pytest.raises(jobs.ReviewConflict,match="POLICY_CHANGED_REVIEW_AGAIN"):
        jobs.get_day(job,"reviewer-qa",date(2026,9,22))


def test_dispatch_deduplicates_polling_and_bounds_queue(monkeypatch):
    class Future:
        def add_done_callback(self,fn): self.done=fn
    class Pool:
        def __init__(self): self.calls=[]
        def submit(self,*args): self.calls.append(args); return Future()
    pool=Pool()
    monkeypatch.setattr(jobs,"POOL",pool);monkeypatch.setattr(jobs,"DISPATCHED",set())
    for _ in range(100): jobs.dispatch("same-job")
    for i in range(10): jobs.dispatch(str(i))
    assert len(pool.calls)==4 and len(jobs.DISPATCHED)==4


def test_explicit_shadow_cutoff_is_auditable_and_disjoint():
    s = selection(shadow_end=date(2026,9,20), shadow_selection_reason="Recent days missing")
    assert bounds(s) == (datetime(2026,9,10), datetime(2026,9,17), datetime(2026,9,17), datetime(2026,9,20))
    assert s["source_latest"] == "2026-10-01T12:00:00"
    assert s["latest_complete_end"] == "2026-10-01T00:00:00"
    assert s["shadow_selection_reason"] == "Recent days missing"


@pytest.mark.parametrize("cutoff", [date(2026,10,2),date(2026,6,1)])
def test_future_or_unbounded_shadow_cutoff_rejected(cutoff):
    with pytest.raises(ValueError): selection(shadow_end=cutoff, shadow_selection_reason="test range")


def test_explicit_shadow_requires_reason():
    with pytest.raises(ValidationError): request(shadow_end=date(2026,9,20))


def test_enough_reference_cannot_build_with_missing_shadow_day():
    s = selection(); rows = [w for w in windows(s) if w.window_start.date() != date(2026,9,29)]
    p = make_preview(rows,s,config())
    assert p["summary"]["retained_reference_minutes"] >= 200
    assert p["summary"]["shadow_minutes"] >= 50
    assert p["summary"]["shadow_days"] == 2 and not p["can_build"]
    assert "SHADOW_NO_SOURCE:2026-09-29" in p["coverage_issues"]


def test_shadow_three_days_below_minimum_is_not_buildable():
    s = selection()
    p = make_preview(windows(s),s,config().model_copy(update={"profile_min_shadow_windows":200}))
    assert p["summary"]["shadow_days"] == 3 and p["summary"]["shadow_minutes"] == 93
    assert not p["can_build"] and not p["summary"]["shadow_ready"]


def test_populated_shadow_day_without_qualified_minutes_is_not_buildable():
    s = selection()
    rows = [QualifiedWindow(**{**w.__dict__,"data_quality_status":"NOT_SCORED", "reason":"LOW_SAMPLE_COVERAGE", "features":None})
        if w.window_start.date() == date(2026,9,29) else w for w in windows(s)]
    p = make_preview(rows,s,config())
    assert not p["can_build"] and "SHADOW_NO_QUALIFIED_MINUTES:2026-09-29" in p["coverage_issues"]


def test_missing_shadow_blocks_build_request(store, monkeypatch):
    monkeypatch.setattr(jobs,"load_observed_one_minute_windows",lambda *a,**k:
        [w for w in store[1] if w.window_start < datetime(2026,9,29)])
    job,digest = ready(store)
    with pytest.raises(jobs.ReviewConflict,match="REFERENCE_NOT_READY"):
        jobs.queue_build(job,"reviewer-qa",digest,"reviewed")


def test_historical_cutoff_survives_job_day_build_and_retry(store):
    # Explicit cutoff equal to the latest closed date is valid and persists
    # the same policy/digest across detail, queue/build and duplicate requests.
    p = request(shadow_end=date(2026,10,1),shadow_selection_reason="Inventory reviewed")
    job = jobs.create_preview(p,"reviewer-qa"); jobs.execute_job(job)
    value = jobs.get_job(job,"reviewer-qa")
    assert value["preview"]["summary"]["shadow_ready"]
    jobs.get_day(job,"reviewer-qa",date(2026,9,29))
    jobs.queue_build(job,"reviewer-qa",value["preview"]["source_digest"],"reviewed")
    jobs.execute_job(job)
    assert jobs.get_job(job,"reviewer-qa")["status"] == "COMPLETED"
    assert jobs.create_preview(p,"reviewer-qa") == job
